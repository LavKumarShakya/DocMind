"""Upload + validation tests for POST /api/documents."""

import pytest

from app.core.config import settings
from app.tests.helpers import auth_headers, build_pdf, multipart_file


@pytest.fixture()
def user(user_factory):
    return user_factory()


def upload(client, user, content, filename, mime="application/pdf", **data):
    return client.post(
        "/api/documents",
        headers=auth_headers(user),
        files=multipart_file(content, filename, mime),
        data=data or None,
    )


def test_upload_valid_pdf(client, user, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    content = build_pdf(["Examination Ordinance 2026", "Section 1: Attendance", "75% is required."])
    res = upload(client, user, content, "Examination Ordinance 2026.pdf")

    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "UPLOADED"
    assert body["mime_type"] == "application/pdf"
    assert body["file_size"] == len(content)
    assert body["page_count"] is None
    assert body["original_filename"] == "Examination Ordinance 2026.pdf"
    assert body["title"] == "Examination Ordinance 2026"
    assert body["uploader_name"] == user.name
    assert "file_path" not in body


def test_upload_rejects_non_pdf_extension(client, user):
    res = upload(client, user, b"hello world", "notes.txt", "text/plain")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_DOCUMENT_TYPE"


def test_upload_rejects_fake_pdf_extension(client, user):
    res = upload(client, user, b"this is not a pdf at all", "fake.pdf")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_DOCUMENT_TYPE"


def test_upload_rejects_empty_file(client, user):
    res = upload(client, user, b"", "empty.pdf")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "EMPTY_DOCUMENT"


def test_upload_rejects_wrong_mime_type(client, user):
    res = upload(client, user, b"%PDF-1.4 fake", "doc.pdf", "image/png")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_DOCUMENT_TYPE"


def test_upload_rejects_oversized_file(client, user, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 1024)
    content = b"%PDF-1.4" + b"x" * 2048
    res = upload(client, user, content, "big.pdf")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "DOCUMENT_TOO_LARGE"


def test_upload_requires_authentication(client):
    content = build_pdf(["Some text"])
    res = client.post(
        "/api/documents",
        files=multipart_file(content, "doc.pdf"),
    )
    assert res.status_code == 401


def test_upload_custom_title_and_metadata(client, user, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    content = build_pdf(["Hostel rules 2026"])
    res = upload(
        client,
        user,
        content,
        "hostel_rules.pdf",
        title="Hostel Rules 2026",
        description="Residential guidelines",
        department="Student Affairs",
        category="Hostel",
        effective_date="2026-01-01",
    )
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "Hostel Rules 2026"
    assert body["description"] == "Residential guidelines"
    assert body["department"] == "Student Affairs"
    assert body["category"] == "Hostel"
    assert body["effective_date"] == "2026-01-01"


def test_upload_stores_file_under_server_generated_path(client, user, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    content = build_pdf(["Stored content"])
    res = upload(client, user, content, "path traversal.txt.pdf")
    assert res.status_code == 201
    doc_id = res.json()["id"]

    stored = list(tmp_path.rglob("original.pdf"))
    assert len(stored) == 1
    assert str(doc_id) in str(stored[0])
    assert stored[0].read_bytes() == content