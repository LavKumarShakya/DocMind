"""Phase 6 conversation tests: CRUD, ownership, persistence, ordering, citations."""

import uuid

import pytest
from sqlalchemy import select

from app.db.models import Citation, Conversation, Document, DocumentChunk, Message
from app.services import rag_service
from app.services.retrieval_types import RetrievalCandidate
from app.tests.helpers import auth_headers, build_pdf, multipart_file


def _candidate(
    text: str,
    *,
    chunk_id=None,
    document_id=None,
    document_title: str = "Academic Regulations",
    rerank_score: float = 0.92,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=document_id or uuid.uuid4(),
        document_title=document_title,
        page_number=2,
        section=None,
        chunk_index=0,
        text=text,
        dense_score=0.9,
        rerank_score=rerank_score,
    )


def _stub_pipeline(monkeypatch, candidate):
    monkeypatch.setattr(
        rag_service, "_retrieve", lambda db, q, user, rs=None: [candidate]
    )


def upload_and_process(client, user, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    res = client.post(
        "/api/documents",
        headers=auth_headers(user),
        files=multipart_file(build_pdf(["80% attendance required."]), "regs.pdf"),
    )
    doc_id = res.json()["id"]
    client.post(f"/api/documents/{doc_id}/process", headers=auth_headers(user))
    return doc_id


def test_create_conversation(client, user_factory):
    user = user_factory()
    res = client.post(
        "/api/conversations",
        headers=auth_headers(user),
        json={"title": "Attendance"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "Attendance"
    assert body["id"]


def test_create_conversation_without_title_uses_default(client, user_factory):
    user = user_factory()
    res = client.post("/api/conversations", headers=auth_headers(user), json={})
    assert res.status_code == 201
    assert res.json()["title"] == "New conversation"


def test_list_own_conversations_ordered_by_updated_at(client, user_factory):
    user = user_factory()
    first = client.post(
        "/api/conversations", headers=auth_headers(user), json={"title": "First"}
    ).json()["id"]
    second = client.post(
        "/api/conversations", headers=auth_headers(user), json={"title": "Second"}
    ).json()["id"]

    listed = client.get("/api/conversations", headers=auth_headers(user)).json()
    assert [c["id"] for c in listed] == [second, first]
    assert all(c["title"] in {"First", "Second"} for c in listed)


def test_get_own_conversation(client, user_factory):
    user = user_factory()
    created = client.post(
        "/api/conversations", headers=auth_headers(user), json={"title": "Exams"}
    ).json()
    res = client.get(
        f"/api/conversations/{created['id']}", headers=auth_headers(user)
    )
    assert res.status_code == 200
    assert res.json()["id"] == created["id"]
    assert res.json()["messages"] == []


def test_delete_own_conversation(client, user_factory):
    user = user_factory()
    created = client.post(
        "/api/conversations", headers=auth_headers(user), json={}
    ).json()
    res = client.delete(
        f"/api/conversations/{created['id']}", headers=auth_headers(user)
    )
    assert res.status_code == 200
    gone = client.get(
        f"/api/conversations/{created['id']}", headers=auth_headers(user)
    )
    assert gone.status_code == 404


def test_cannot_access_another_users_conversation(client, user_factory):
    owner = user_factory(name="Owner")
    other = user_factory(name="Other")
    created = client.post(
        "/api/conversations", headers=auth_headers(owner), json={"title": "Secret"}
    ).json()

    assert (
        client.get(
            f"/api/conversations/{created['id']}", headers=auth_headers(other)
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/conversations/{created['id']}", headers=auth_headers(other)
        ).status_code
        == 404
    )
    assert all(
        c["id"] != created["id"]
        for c in client.get("/api/conversations", headers=auth_headers(other)).json()
    )


def test_conversations_require_auth(client, user_factory):
    assert client.get("/api/conversations").status_code == 401
    assert client.post("/api/conversations", json={}).status_code == 401
    assert client.get("/api/conversations/00000000-0000-0000-0000-000000000000").status_code == 401


def test_chat_creates_conversation_and_persists_exchange(
    client, user_factory, db_session, monkeypatch
):
    user = user_factory()
    candidate = _candidate("80% attendance is required.")
    _stub_pipeline(monkeypatch, candidate)

    res = client.post(
        "/api/chat",
        headers=auth_headers(user),
        json={"message": "What is the attendance policy?"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["conversation_id"]
    assert body["message_id"]
    # Deterministic title generated from the first question (no LLM).
    assert body["answer"]

    detail = client.get(
        f"/api/conversations/{body['conversation_id']}", headers=auth_headers(user)
    ).json()
    assert detail["title"] == "Attendance policy"
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["USER", "ASSISTANT"]
    assert detail["messages"][0]["content"] == "What is the attendance policy?"
    assert "attendance" in detail["messages"][1]["content"].lower()


def test_chat_appends_to_existing_conversation(
    client, user_factory, monkeypatch
):
    user = user_factory()
    created = client.post(
        "/api/conversations", headers=auth_headers(user), json={"title": "Policies"}
    ).json()
    candidate = _candidate("80% attendance is required.")
    _stub_pipeline(monkeypatch, candidate)

    res = client.post(
        "/api/chat",
        headers=auth_headers(user),
        json={"message": "What is the attendance policy?", "conversation_id": created["id"]},
    )
    assert res.status_code == 200
    assert res.json()["conversation_id"] == created["id"]

    detail = client.get(
        f"/api/conversations/{created['id']}", headers=auth_headers(user)
    ).json()
    assert detail["title"] == "Policies"  # title untouched when appending
    assert [m["role"] for m in detail["messages"]] == ["USER", "ASSISTANT"]


def test_cannot_chat_into_another_users_conversation(client, user_factory, monkeypatch):
    owner = user_factory(name="Owner")
    other = user_factory(name="Other")
    created = client.post(
        "/api/conversations", headers=auth_headers(owner), json={}
    ).json()
    candidate = _candidate("evidence")
    _stub_pipeline(monkeypatch, candidate)

    res = client.post(
        "/api/chat",
        headers=auth_headers(other),
        json={"message": "question?", "conversation_id": created["id"]},
    )
    assert res.status_code == 404


def test_messages_ordered_correctly(client, user_factory, monkeypatch):
    user = user_factory()
    candidate = _candidate("evidence one")
    _stub_pipeline(monkeypatch, candidate)
    conv_id = client.post(
        "/api/chat", headers=auth_headers(user), json={"message": "first question"}
    ).json()["conversation_id"]
    client.post(
        "/api/chat",
        headers=auth_headers(user),
        json={"message": "second question", "conversation_id": conv_id},
    )

    detail = client.get(
        f"/api/conversations/{conv_id}", headers=auth_headers(user)
    ).json()
    user_contents = [
        m["content"] for m in detail["messages"] if m["role"] == "USER"
    ]
    assert user_contents == ["first question", "second question"]
    # Assistant answers are interleaved after each question (odd positions).
    assert [m["role"] for m in detail["messages"]] == [
        "USER",
        "ASSISTANT",
        "USER",
        "ASSISTANT",
    ]


def test_citations_persist_with_assistant_message(
    client, user_factory, db_session, tmp_path, monkeypatch
):
    user = user_factory()
    doc_id = upload_and_process(client, user, tmp_path, monkeypatch)
    document = db_session.get(Document, uuid.UUID(doc_id))

    chunk = db_session.scalar(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc_id))
    )
    candidate = _candidate(
        "80% attendance is required.",
        chunk_id=chunk.id,
        document_id=uuid.UUID(doc_id),
        document_title=document.title,
    )
    _stub_pipeline(monkeypatch, candidate)

    res = client.post(
        "/api/chat",
        headers=auth_headers(user),
        json={"message": "What is the attendance policy?"},
    )
    assert res.status_code == 200
    conv_id = res.json()["conversation_id"]

    detail = client.get(
        f"/api/conversations/{conv_id}", headers=auth_headers(user)
    ).json()
    assistant = detail["messages"][1]
    assert len(assistant["citations"]) == 1
    citation = assistant["citations"][0]
    assert citation["document_id"] == doc_id
    assert citation["document_title"] == "regs"
    assert citation["page_number"] == 2
    assert citation["relevance_score"] == 0.92


def test_delete_removes_messages_and_citations(
    client, user_factory, db_session, tmp_path, monkeypatch
):
    user = user_factory()
    doc_id = upload_and_process(client, user, tmp_path, monkeypatch)
    chunk = db_session.scalar(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc_id))
    )
    _stub_pipeline(
        monkeypatch,
        _candidate("evidence", chunk_id=chunk.id, document_id=uuid.UUID(doc_id)),
    )
    conv_id = client.post(
        "/api/chat", headers=auth_headers(user), json={"message": "a question"}
    ).json()["conversation_id"]

    assert db_session.scalar(select(Conversation).where(Conversation.id == uuid.UUID(conv_id)))

    client.delete(f"/api/conversations/{conv_id}", headers=auth_headers(user))

    assert db_session.scalar(select(Conversation).where(Conversation.id == uuid.UUID(conv_id))) is None
    assert (
        db_session.scalar(
            select(Message).where(Message.conversation_id == uuid.UUID(conv_id))
        )
        is None
    )
    assert (
        db_session.scalar(
            select(Citation).where(Citation.message_id.in_(
                select(Message.id).where(Message.conversation_id == uuid.UUID(conv_id))
            ))
        )
        is None
    )


def test_generate_title_removes_question_words():
    from app.services.conversation_service import generate_title

    assert generate_title("What is the minimum attendance requirement?") == "Minimum attendance requirement"
    assert generate_title("How do I apply for a scholarship?") == "Apply for a scholarship"
    assert generate_title("nothing") == "Nothing"
    assert generate_title("???") == "New conversation"