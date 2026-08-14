"""Phase 6 document versioning tests."""

import uuid

import pytest
from sqlalchemy import select

from app.core.enums import DocumentStatus, Role
from app.db.models import Document, DocumentChunk, DocumentVersion
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


def upload_doc(client, user, pages, filename="regs.pdf", tmp_path=None, monkeypatch=None):
    if tmp_path is not None and monkeypatch is not None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    return client.post(
        "/api/documents",
        headers=auth_headers(user),
        files=multipart_file(build_pdf(pages), filename),
    )


def process(client, user, doc_id):
    return client.post(f"/api/documents/{doc_id}/process", headers=auth_headers(user)).json()


def upload_version(client, user, doc_id, pages, filename="new.pdf"):
    return client.post(
        f"/api/documents/{doc_id}/versions",
        headers=auth_headers(user),
        files=multipart_file(build_pdf(pages), filename),
    )


def test_create_version_and_numbering(client, owner, tmp_path, monkeypatch, db_session):
    doc_id = upload_doc(client, owner, ["v1 content"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]
    assert process(client, owner, doc_id)["status"] == "ACTIVE"

    res = upload_version(client, owner, doc_id, ["v2 content", "page two"])
    assert res.status_code == 201
    version = res.json()
    assert version["version_number"] == 2
    assert version["status"] == "UPLOADED"
    assert version["document_id"] == doc_id

    saved = db_session.get(DocumentVersion, uuid.UUID(version["id"]))
    assert saved is not None
    assert saved.version_number == 2
    assert "versions/2/original.pdf" in saved.storage_path


def test_uploading_version_archives_previous_and_updates_current(
    client, owner, tmp_path, monkeypatch, db_session
):
    doc_id = upload_doc(client, owner, ["v1 content"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]
    process(client, owner, doc_id)

    v1 = db_session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == uuid.UUID(doc_id),
            DocumentVersion.version_number == 1,
        )
    )
    assert v1.status == DocumentStatus.ACTIVE

    res = upload_version(client, owner, doc_id, ["v2 content"])
    assert res.status_code == 201
    v2_id = res.json()["id"]

    document = db_session.get(Document, uuid.UUID(doc_id))
    assert document.version == "2"
    assert str(document.current_version_id) == v2_id
    assert document.status == DocumentStatus.UPLOADED

    db_session.refresh(v1)
    assert v1.status == DocumentStatus.ARCHIVED


def test_list_versions_newest_first(client, owner, tmp_path, monkeypatch):
    doc_id = upload_doc(client, owner, ["v1 content"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]
    upload_version(client, owner, doc_id, ["v2 content"])
    upload_version(client, owner, doc_id, ["v3 content"])

    versions = client.get(
        f"/api/documents/{doc_id}/versions", headers=auth_headers(owner)
    ).json()
    assert [v["version_number"] for v in versions] == [3, 2, 1]


def test_retrieve_version(client, owner, tmp_path, monkeypatch):
    doc_id = upload_doc(client, owner, ["v1 content"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]
    v2 = upload_version(client, owner, doc_id, ["v2 content"]).json()

    res = client.get(
        f"/api/documents/{doc_id}/versions/{v2['id']}", headers=auth_headers(owner)
    )
    assert res.status_code == 200
    assert res.json()["version_number"] == 2


def test_version_requires_management_rights(client, owner, other, admin, tmp_path, monkeypatch):
    doc_id = upload_doc(client, owner, ["v1 content"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]

    # PUBLIC documents: any user can list/read versions...
    assert (
        client.get(f"/api/documents/{doc_id}/versions", headers=auth_headers(other)).status_code
        == 200
    )
    # ...but only the uploader or ADMIN can upload a new one.
    assert (
        upload_version(client, other, doc_id, ["hacked"]).status_code == 403
    )
    assert (
        upload_version(client, admin, doc_id, ["admin version"]).status_code == 201
    )


def test_version_invisible_when_document_invisible(client, owner, other, tmp_path, monkeypatch):
    doc_id = upload_doc(client, owner, ["v1 content"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]
    client.patch(
        f"/api/documents/{doc_id}",
        headers=auth_headers(owner),
        json={"access_level": "ADMIN"},
    )
    assert (
        client.get(f"/api/documents/{doc_id}/versions", headers=auth_headers(other)).status_code
        == 404
    )


def test_versions_require_auth(client, owner, tmp_path, monkeypatch):
    doc_id = upload_doc(client, owner, ["v1 content"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]
    assert client.get(f"/api/documents/{doc_id}/versions").status_code == 401
    assert client.post(f"/api/documents/{doc_id}/versions").status_code == 401


def test_processing_new_version_makes_it_active_and_replaces_chunks(
    client, owner, tmp_path, monkeypatch, db_session
):
    doc_id = upload_doc(client, owner, ["attendance old policy 60"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]
    process(client, owner, doc_id)
    v2 = upload_version(client, owner, doc_id, ["attendance new policy 75 percent"]).json()

    processed = process(client, owner, doc_id)
    assert processed["status"] == "ACTIVE"
    assert processed["version"] == "2"

    document = db_session.get(Document, uuid.UUID(doc_id))
    assert document.current_version_id is not None
    assert str(document.current_version_id) == v2["id"]

    v2_row = db_session.get(DocumentVersion, uuid.UUID(v2["id"]))
    assert v2_row.status == DocumentStatus.ACTIVE
    assert v2_row.page_count == 1

    chunks = db_session.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc_id))
    ).all()
    # Chunks now reflect the CURRENT (v2) content — the RAG default.
    assert any("75" in c.content for c in chunks)
    assert all("60" not in c.content for c in chunks)


def test_reprocessing_version_is_safe(client, owner, tmp_path, monkeypatch, db_session):
    doc_id = upload_doc(client, owner, ["v1 content"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]
    upload_version(client, owner, doc_id, ["v2 content"])

    first = process(client, owner, doc_id)
    second = process(client, owner, doc_id)
    assert first["status"] == "ACTIVE"
    assert second["chunk_count"] == first["chunk_count"]


def test_old_version_remains_intact_after_new_version(
    client, owner, tmp_path, monkeypatch, db_session
):
    doc_id = upload_doc(client, owner, ["v1 content"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]
    process(client, owner, doc_id)
    v1 = db_session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == uuid.UUID(doc_id),
            DocumentVersion.version_number == 1,
        )
    )
    v1_path = v1.storage_path

    v2 = upload_version(client, owner, doc_id, ["v2 content"]).json()
    process(client, owner, doc_id)

    # The v1 row survives, archived, with its storage path untouched.
    db_session.expire_all()
    v1_after = db_session.get(DocumentVersion, v1.id)
    assert v1_after.status == DocumentStatus.ARCHIVED
    assert v1_after.storage_path == v1_path

    # Its file still exists on disk.
    from pathlib import Path

    from app.core.config import settings

    root = Path(settings.STORAGE_DIR)
    if not root.is_absolute():
        root = Path.cwd() / root
    assert (root / v1_path).is_file()

    # And the new version's file exists separately (never overwritten).
    v2_row = db_session.get(DocumentVersion, uuid.UUID(v2["id"]))
    assert (root / v2_row.storage_path).is_file()
    assert v2_row.storage_path != v1_path


def test_document_upload_creates_version_one(client, owner, tmp_path, monkeypatch, db_session):
    doc_id = upload_doc(client, owner, ["v1 content"], tmp_path=tmp_path, monkeypatch=monkeypatch).json()["id"]
    versions = client.get(
        f"/api/documents/{doc_id}/versions", headers=auth_headers(owner)
    ).json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["status"] == "UPLOADED"

    document = db_session.get(Document, uuid.UUID(doc_id))
    assert document.current_version_id is not None