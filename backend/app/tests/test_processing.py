"""Ingestion pipeline tests: status transitions, failures, DB rows, cascade cleanup."""

import uuid

import pytest

from app.core.config import settings
from app.core.enums import DocumentStatus, Role
from app.core.errors import ApiError
from app.db.models import DocumentChunk
from app.services import document_service, ingestion_service, storage_service
from app.tests.helpers import build_pdf


def make_stored_document(db, user, tmp_path, monkeypatch, pages=None, filename="ordinance.pdf"):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    content = build_pdf(*([["Attendance policy text here."]] if pages is None else pages))
    document_id = uuid.uuid4()
    stored = storage_service.save_document_file(document_id, content)
    return document_service.create_document(
        db,
        document_id=document_id,
        uploader=user,
        original_filename=filename,
        mime_type="application/pdf",
        file_size=len(content),
        file_path=stored,
    )


def chunk_rows(db, document_id):
    from sqlalchemy import select

    return list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document_id)))


def test_status_transition_uploaded_processing_active(db_session, user_factory, tmp_path, monkeypatch, fake_embedding_service):
    user = user_factory()
    doc = make_stored_document(db_session, user, tmp_path, monkeypatch)

    assert doc.status == DocumentStatus.UPLOADED
    result = ingestion_service.process_document(db_session, doc.id, user)
    assert result.status == DocumentStatus.ACTIVE
    assert result.page_count is not None
    assert result.processed_at is not None
    assert result.processing_error is None


def test_chunks_persist_with_embeddings_and_metadata(db_session, user_factory, tmp_path, monkeypatch, fake_embedding_service):
    user = user_factory()
    doc = make_stored_document(
        db_session,
        user,
        tmp_path,
        monkeypatch,
        pages=[["Line one of page one", "Line two of page one"], ["Page two line"]],
    )
    ingestion_service.process_document(db_session, doc.id, user)

    chunks = chunk_rows(db_session, doc.id)
    assert len(chunks) == 2
    indices = [c.chunk_index for c in chunks]
    assert indices == sorted(indices)
    assert {c.page_number for c in chunks} == {1, 2}
    for c in chunks:
        assert c.content
        assert c.embedding is not None
        assert len(c.embedding) == settings.EMBEDDING_DIM
        assert c.metadata_["document_id"] == str(doc.id)
        assert c.metadata_["page_number"] == c.page_number
        assert c.metadata_["chunk_index"] == c.chunk_index
        assert c.metadata_["token_count"] > 0


def test_failure_marks_failed_and_retry_recovers(db_session, user_factory, tmp_path, monkeypatch, fake_embedding_service):
    user = user_factory()
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    doc = make_stored_document(db_session, user, tmp_path, monkeypatch)
    # Corrupt the stored file so extraction fails.
    storage_path = storage_service.get_storage_root() / doc.file_path
    storage_path.write_bytes(b"%PDF-1.4 broken garbage")

    with pytest.raises(ApiError) as exc:
        ingestion_service.process_document(db_session, doc.id, user)
    assert exc.value.code == "DOCUMENT_PROCESSING_FAILED"

    failed = document_service.get_document(db_session, doc.id)
    assert failed.status == DocumentStatus.FAILED
    assert failed.processing_error  # safe, internal-only description

    # Replace the stored file with a valid PDF and reprocess successfully.
    storage_path.write_bytes(build_pdf(["Recovered after failure"]))

    recovered = ingestion_service.process_document(db_session, doc.id, user)
    assert recovered.status == DocumentStatus.ACTIVE
    assert recovered.processing_error is None
    assert len(chunk_rows(db_session, doc.id)) == 1


def test_reprocess_replaces_chunks_without_duplicates(db_session, user_factory, tmp_path, monkeypatch, fake_embedding_service):
    user = user_factory()
    # ~4000 characters across many lines so chunking yields multiple chunks.
    long_text = ["word " * 40] * 20
    doc = make_stored_document(db_session, user, tmp_path, monkeypatch, pages=[long_text])
    ingestion_service.process_document(db_session, doc.id, user)
    first_count = len(chunk_rows(db_session, doc.id))
    assert first_count > 1

    ingestion_service.process_document(db_session, doc.id, user)
    assert len(chunk_rows(db_session, doc.id)) == first_count


def test_delete_document_removes_chunks_and_file(db_session, user_factory, tmp_path, monkeypatch, fake_embedding_service):
    user = user_factory()
    doc = make_stored_document(db_session, user, tmp_path, monkeypatch)
    ingestion_service.process_document(db_session, doc.id, user)
    stored = storage_service.get_storage_root() / doc.file_path
    assert stored.is_file()
    assert chunk_rows(db_session, doc.id)

    document_service.delete_document(db_session, doc)
    assert chunk_rows(db_session, doc.id) == []
    assert not stored.exists()


def test_non_owner_cannot_process(db_session, user_factory, tmp_path, monkeypatch, fake_embedding_service):
    owner = user_factory(role=Role.STUDENT)
    intruder = user_factory()
    doc = make_stored_document(db_session, owner, tmp_path, monkeypatch)

    with pytest.raises(ApiError) as exc:
        ingestion_service.process_document(db_session, doc.id, intruder)
    assert exc.value.code == "FORBIDDEN"