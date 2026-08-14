"""Phase 6 admin tests: access control, role management, real statistics."""

import pytest
from sqlalchemy import select

from app.core.enums import MessageRole, Role
from app.core.security import create_access_token
from app.db.models import User
from app.tests.helpers import auth_headers, auth_header, build_pdf, multipart_file

ADMIN_PATHS = ["/api/admin/users", "/api/admin/documents", "/api/admin/stats"]


def _upload_and_process(client, user, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    doc_id = client.post(
        "/api/documents",
        headers=auth_headers(user),
        files=multipart_file(build_pdf(["admin content"]), "doc.pdf"),
    ).json()["id"]
    client.post(f"/api/documents/{doc_id}/process", headers=auth_headers(user))
    return doc_id


@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_admin_endpoints_require_admin(client, user_factory, path):
    token = create_access_token(user_factory(role=Role.STUDENT).id, Role.STUDENT)
    assert client.get(path, headers=auth_header(token)).status_code == 403

    token = create_access_token(user_factory(role=Role.FACULTY).id, Role.FACULTY)
    assert client.get(path, headers=auth_header(token)).status_code == 403

    token = create_access_token(user_factory(role=Role.ADMIN).id, Role.ADMIN)
    assert client.get(path, headers=auth_header(token)).status_code == 200


@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_admin_endpoints_require_auth(client, path):
    assert client.get(path).status_code == 401


def test_admin_users_returns_safe_fields(client, user_factory):
    admin = user_factory(role=Role.ADMIN)
    user_factory(name="Alice", email="alice@example.com", role=Role.STUDENT)

    res = client.get("/api/admin/users", headers=auth_headers(admin))
    assert res.status_code == 200
    users = res.json()
    assert any(u["email"] == "alice@example.com" and u["role"] == "STUDENT" for u in users)
    for user in users:
        assert "password_hash" not in user
        assert "password" not in user


def test_admin_can_change_role(client, user_factory, db_session):
    admin = user_factory(role=Role.ADMIN)
    target = user_factory(role=Role.STUDENT)

    res = client.patch(
        f"/api/admin/users/{target.id}/role",
        headers=auth_headers(admin),
        json={"role": "FACULTY"},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "FACULTY"
    assert db_session.get(User, target.id).role == Role.FACULTY


def test_non_admin_cannot_change_role(client, user_factory):
    student = user_factory(role=Role.STUDENT)
    target = user_factory(role=Role.STUDENT)

    res = client.patch(
        f"/api/admin/users/{target.id}/role",
        headers=auth_headers(student),
        json={"role": "ADMIN"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_invalid_role_rejected(client, user_factory):
    admin = user_factory(role=Role.ADMIN)
    target = user_factory(role=Role.STUDENT)

    res = client.patch(
        f"/api/admin/users/{target.id}/role",
        headers=auth_headers(admin),
        json={"role": "SUPERUSER"},
    )
    assert res.status_code == 422


def test_cannot_demote_last_admin(client, user_factory, db_session):
    admin = user_factory(role=Role.ADMIN)

    res = client.patch(
        f"/api/admin/users/{admin.id}/role",
        headers=auth_headers(admin),
        json={"role": "STUDENT"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "LAST_ADMIN"
    assert db_session.get(User, admin.id).role == Role.ADMIN


def test_can_demote_admin_when_another_exists(client, user_factory, db_session):
    admin1 = user_factory(role=Role.ADMIN)
    admin2 = user_factory(role=Role.ADMIN)

    res = client.patch(
        f"/api/admin/users/{admin1.id}/role",
        headers=auth_headers(admin2),
        json={"role": "FACULTY"},
    )
    assert res.status_code == 200
    assert db_session.get(User, admin1.id).role == Role.FACULTY


def test_admin_statistics_are_real(client, user_factory, tmp_path, monkeypatch, db_session):
    from app.db.models import Conversation, Feedback, Message

    admin = user_factory(role=Role.ADMIN)
    student = user_factory(role=Role.STUDENT)
    user_factory(role=Role.FACULTY)

    doc_id = _upload_and_process(client, admin, tmp_path, monkeypatch)
    failed = client.post(
        "/api/documents",
        headers=auth_headers(admin),
        # Page containing only a page number: extraction cleans it to nothing.
        files=multipart_file(build_pdf(["1"]), "blank.pdf"),
    ).json()["id"]
    client.post(f"/api/documents/{failed}/process", headers=auth_headers(admin))

    # One conversation with one message.
    conversation = Conversation(user_id=student.id, title="T")
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    db_session.add(Message(conversation_id=conversation.id, role=MessageRole.ASSISTANT, content="hi"))
    db_session.add(Feedback(user_id=student.id, message_id=db_session.scalars(
        select(Message).where(Message.conversation_id == conversation.id)
    ).first().id, rating=5))
    db_session.commit()

    res = client.get("/api/admin/stats", headers=auth_headers(admin))
    assert res.status_code == 200
    stats = res.json()
    assert stats["users"] == 3
    assert stats["documents"] == 2
    assert stats["active_documents"] == 1
    assert stats["failed_documents"] == 1
    assert stats["conversations"] == 1
    assert stats["feedback_entries"] == 1
    assert doc_id  # silence unused


def test_admin_documents_include_owner_and_status(client, user_factory, tmp_path, monkeypatch):
    admin = user_factory(role=Role.ADMIN)
    owner = user_factory(name="Owner Doc", role=Role.STUDENT)
    _upload_and_process(client, owner, tmp_path, monkeypatch)

    res = client.get("/api/admin/documents", headers=auth_headers(admin))
    assert res.status_code == 200
    docs = res.json()
    assert any(d["owner_name"] == "Owner Doc" and d["status"] == "ACTIVE" for d in docs)


def test_admin_can_change_document_access_level(client, user_factory, tmp_path, monkeypatch):
    from app.core.enums import AccessLevel

    admin = user_factory(role=Role.ADMIN)
    owner = user_factory(role=Role.STUDENT)
    other = user_factory(role=Role.STUDENT)
    doc_id = _upload_and_process(client, owner, tmp_path, monkeypatch)

    # ADMIN can change access level of someone else's document (existing doc API).
    res = client.patch(
        f"/api/documents/{doc_id}",
        headers=auth_headers(admin),
        json={"access_level": "ADMIN"},
    )
    assert res.status_code == 200
    assert res.json()["access_level"] == "ADMIN"

    # The other student can no longer see it (access control respected).
    assert (
        client.get(f"/api/documents/{doc_id}", headers=auth_headers(other)).status_code
        == 404
    )


def test_admin_documents_never_expose_paths(client, user_factory, tmp_path, monkeypatch):
    admin = user_factory(role=Role.ADMIN)
    _upload_and_process(client, admin, tmp_path, monkeypatch)

    docs = client.get("/api/admin/documents", headers=auth_headers(admin)).json()
    for doc in docs:
        assert "file_path" not in doc
        assert "storage_path" not in doc
        assert "processing_error" not in doc