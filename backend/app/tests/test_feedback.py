"""Phase 6 feedback tests: rating, validation, authorization, upsert persistence."""

import uuid

from sqlalchemy import select

from app.db.models import Feedback
from app.tests.helpers import auth_headers


def _make_assistant_message(client, user, monkeypatch):
    """Create a conversation with an assistant answer and return its message id."""
    from app.services import rag_service
    from app.services.retrieval_types import RetrievalCandidate

    candidate = RetrievalCandidate(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Academic Regulations",
        page_number=1,
        section=None,
        chunk_index=0,
        text="80% attendance is required.",
        dense_score=0.9,
        rerank_score=0.92,
    )
    monkeypatch.setattr(
        rag_service, "_retrieve", lambda db, q, user, rs=None: [candidate]
    )
    res = client.post(
        "/api/chat", headers=auth_headers(user), json={"message": "What is the attendance policy?"}
    )
    assert res.status_code == 200
    return res.json()["message_id"]


def test_positive_rating(client, user_factory, monkeypatch, db_session):
    user = user_factory()
    message_id = _make_assistant_message(client, user, monkeypatch)

    res = client.post(
        "/api/feedback",
        headers=auth_headers(user),
        json={"message_id": message_id, "rating": 5, "reason": "Helpful answer"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["message_id"] == message_id
    assert body["rating"] == 5
    assert body["reason"] == "Helpful answer"

    saved = db_session.scalar(
        select(Feedback).where(Feedback.message_id == uuid.UUID(message_id))
    )
    assert saved is not None
    assert saved.user_id == user.id
    assert saved.rating == 5


def test_negative_rating(client, user_factory, monkeypatch, db_session):
    user = user_factory()
    message_id = _make_assistant_message(client, user, monkeypatch)

    res = client.post(
        "/api/feedback",
        headers=auth_headers(user),
        json={"message_id": message_id, "rating": 1},
    )
    assert res.status_code == 200
    assert res.json()["rating"] == 1
    assert db_session.scalar(
        select(Feedback).where(Feedback.message_id == uuid.UUID(message_id))
    ).rating == 1


def test_invalid_rating_rejected(client, user_factory, monkeypatch):
    user = user_factory()
    message_id = _make_assistant_message(client, user, monkeypatch)

    for bad in (0, 6, -1):
        res = client.post(
            "/api/feedback",
            headers=auth_headers(user),
            json={"message_id": message_id, "rating": bad},
        )
        assert res.status_code == 422


def test_missing_message_rejected(client, user_factory):
    user = user_factory()
    res = client.post(
        "/api/feedback",
        headers=auth_headers(user),
        json={
            "message_id": "00000000-0000-0000-0000-000000000000",
            "rating": 5,
        },
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "MESSAGE_NOT_FOUND"


def test_cannot_rate_user_message(client, user_factory, monkeypatch):
    user = user_factory()
    conv = client.post("/api/conversations", headers=auth_headers(user), json={}).json()
    # First exchange produces a USER message (id 0) and an ASSISTANT message.
    from app.services import rag_service
    from app.services.retrieval_types import RetrievalCandidate

    monkeypatch.setattr(
        rag_service,
        "_retrieve",
        lambda db, q, user, rs=None: [
            RetrievalCandidate(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                document_title="D",
                page_number=1,
                section=None,
                chunk_index=0,
                text="evidence",
                rerank_score=0.9,
            )
        ],
    )
    res = client.post(
        "/api/chat",
        headers=auth_headers(user),
        json={"message": "hello?", "conversation_id": conv["id"]},
    )
    assert res.status_code == 200
    detail = client.get(
        f"/api/conversations/{conv['id']}", headers=auth_headers(user)
    ).json()
    user_message_id = detail["messages"][0]["id"]

    res = client.post(
        "/api/feedback",
        headers=auth_headers(user),
        json={"message_id": user_message_id, "rating": 5},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "FEEDBACK_NOT_ALLOWED"


def test_cannot_rate_another_users_answer(client, user_factory, monkeypatch):
    owner = user_factory(name="Owner")
    other = user_factory(name="Other")
    message_id = _make_assistant_message(client, owner, monkeypatch)

    res = client.post(
        "/api/feedback",
        headers=auth_headers(other),
        json={"message_id": message_id, "rating": 5},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_feedback_requires_auth(client, user_factory, monkeypatch):
    user = user_factory()
    message_id = _make_assistant_message(client, user, monkeypatch)
    res = client.post("/api/feedback", json={"message_id": message_id, "rating": 5})
    assert res.status_code == 401


def test_duplicate_feedback_updates_existing(client, user_factory, monkeypatch, db_session):
    user = user_factory()
    message_id = _make_assistant_message(client, user, monkeypatch)

    first = client.post(
        "/api/feedback",
        headers=auth_headers(user),
        json={"message_id": message_id, "rating": 1, "reason": "Not helpful"},
    ).json()
    second = client.post(
        "/api/feedback",
        headers=auth_headers(user),
        json={"message_id": message_id, "rating": 5, "reason": "Actually helpful"},
    ).json()

    assert second["id"] == first["id"]  # same row updated, not duplicated
    assert second["rating"] == 5
    count = len(
        db_session.scalars(
            select(Feedback).where(Feedback.message_id == uuid.UUID(message_id))
        ).all()
    )
    assert count == 1