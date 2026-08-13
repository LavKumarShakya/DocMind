"""End-to-end document API tests (upload → process → list/detail → patch → delete)."""

import pytest

from app.core.enums import Role
from app.tests.helpers import auth_headers, build_pdf, multipart_file


@pytest.fixture()
def owner(user_factory):
    return user_factory(name="Owner", role=Role.STUDENT)


@pytest.fixture()
def other(user_factory):
    return user_factory(name="Other")


@pytest.fixture()
def admin(user_factory):
    return user_factory(name="Admin", role=Role.ADMIN)


def upload_doc(client, user, filename="ordinance.pdf", **data):
    return client.post(
        "/api/documents",
        headers=auth_headers(user),
        files=multipart_file(build_pdf(["Attendance policy", "80% attendance required."]), filename),
        data=data or None,
    )


def test_full_lifecycle(client, owner, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    up = upload_doc(client, owner)
    assert up.status_code == 201
    doc_id = up.json()["id"]
    assert up.json()["status"] == "UPLOADED"

    listed = client.get("/api/documents", headers=auth_headers(owner)).json()
    assert any(d["id"] == doc_id for d in listed)

    detail = client.get(f"/api/documents/{doc_id}", headers=auth_headers(owner))
    assert detail.status_code == 200
    assert detail.json()["chunk_count"] == 0

    processed = client.post(f"/api/documents/{doc_id}/process", headers=auth_headers(owner))
    assert processed.status_code == 200
    body = processed.json()
    assert body["status"] == "ACTIVE"
    assert body["page_count"] == 1
    assert body["chunk_count"] == 1
    assert body["processed_at"] is not None
    assert "processing_error" not in body

    detail_after = client.get(f"/api/documents/{doc_id}", headers=auth_headers(owner)).json()
    assert detail_after["chunk_count"] == 1

    patched = client.patch(
        f"/api/documents/{doc_id}",
        headers=auth_headers(owner),
        json={"title": "Renamed", "description": None},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Renamed"
    assert patched.json()["description"] is None

    deleted = client.delete(f"/api/documents/{doc_id}", headers=auth_headers(owner))
    assert deleted.status_code == 200

    gone = client.get(f"/api/documents/{doc_id}", headers=auth_headers(owner))
    assert gone.status_code == 404


def test_process_replaces_chunks_no_duplicates(client, owner, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    doc_id = upload_doc(client, owner).json()["id"]

    first = client.post(f"/api/documents/{doc_id}/process", headers=auth_headers(owner)).json()
    second = client.post(f"/api/documents/{doc_id}/process", headers=auth_headers(owner)).json()
    assert first["status"] == "ACTIVE"
    assert second["chunk_count"] == first["chunk_count"]

    detail = client.get(f"/api/documents/{doc_id}", headers=auth_headers(owner)).json()
    assert detail["chunk_count"] == first["chunk_count"]


def test_unauthorized_users_cannot_manage_or_view(client, owner, other, admin, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    doc_id = upload_doc(client, owner).json()["id"]

    # PUBLIC documents are viewable by everyone, but only the owner/ADMIN manage.
    visible = client.get(f"/api/documents/{doc_id}", headers=auth_headers(other))
    assert visible.status_code == 200
    listed = client.get("/api/documents", headers=auth_headers(other)).json()
    assert any(d["id"] == doc_id for d in listed)

    # Manage operations rejected with 403.
    for method, body in [
        ("patch", {"title": "hacked"}),
    ]:
        res = getattr(client, method)(f"/api/documents/{doc_id}", headers=auth_headers(other), json=body)
        assert res.status_code == 403
    assert client.post(f"/api/documents/{doc_id}/process", headers=auth_headers(other)).status_code == 403
    assert client.delete(f"/api/documents/{doc_id}", headers=auth_headers(other)).status_code == 403

    # After the owner restricts access to ADMIN, it becomes invisible (404).
    client.patch(
        f"/api/documents/{doc_id}",
        headers=auth_headers(owner),
        json={"access_level": "ADMIN"},
    )
    assert client.get(f"/api/documents/{doc_id}", headers=auth_headers(other)).status_code == 404

    # ADMIN can still manage.
    admin_detail = client.get(f"/api/documents/{doc_id}", headers=auth_headers(admin))
    assert admin_detail.status_code == 200
    assert client.post(f"/api/documents/{doc_id}/process", headers=auth_headers(admin)).status_code == 200
    assert client.delete(f"/api/documents/{doc_id}", headers=auth_headers(admin)).status_code == 200
    assert client.get(f"/api/documents/{doc_id}", headers=auth_headers(owner)).status_code == 404


def test_patch_cannot_change_immutable_fields(client, owner, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    doc_id = upload_doc(client, owner).json()["id"]

    res = client.patch(
        f"/api/documents/{doc_id}",
        headers=auth_headers(owner),
        json={"id": "00000000-0000-0000-0000-000000000000", "status": "ACTIVE"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == doc_id
    assert body["status"] == "UPLOADED"


def test_documents_require_auth_for_all_methods(client, owner, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    doc_id = upload_doc(client, owner).json()["id"]

    assert client.get("/api/documents").status_code == 401
    assert client.get(f"/api/documents/{doc_id}").status_code == 401
    assert client.post(f"/api/documents/{doc_id}/process").status_code == 401
    assert client.patch(f"/api/documents/{doc_id}", json={"title": "x"}).status_code == 401
    assert client.delete(f"/api/documents/{doc_id}").status_code == 401


def test_access_level_visibility(client, owner, other, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    doc_id = upload_doc(client, owner).json()["id"]

    # Owner raises the access level to ADMIN: no longer visible to STUDENT.
    client.patch(
        f"/api/documents/{doc_id}",
        headers=auth_headers(owner),
        json={"access_level": "ADMIN"},
    )
    assert client.get(f"/api/documents/{doc_id}", headers=auth_headers(other)).status_code == 404
    assert client.get(f"/api/documents/{doc_id}", headers=auth_headers(owner)).status_code == 200