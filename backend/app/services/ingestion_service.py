"""Document ingestion pipeline orchestrator.

Flow: load file → validate → extract pages → clean → chunk → embed →
persist chunks → mark ACTIVE. Any failure marks the document FAILED with a
safe, internal-only error description and leaves the database consistent, so
processing can be retried safely (old chunks for the document are replaced,
never duplicated).

The embedding service is injected for testability; production uses the shared
singleton from ``embedding_service.get_embedding_service()``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import DocumentStatus
from app.core.errors import ApiError
from app.db.models import Document, DocumentChunk, User
from app.rag.chunking import Chunk, chunk_pages
from app.services import pdf_service, storage_service
from app.services.document_service import get_manageable_document

logger = logging.getLogger(__name__)

NO_TEXT_ERROR = "No extractable text was found in the document."


def _status_to_processing(db: Session, document: Document) -> None:
    document.status = DocumentStatus.PROCESSING
    document.processing_error = None
    db.add(document)
    db.commit()


def _mark_failed(db: Session, document: Document, reason: str) -> None:
    """Persist the FAILED state (never returns; used before raising)."""
    db.rollback()
    document = db.get(Document, document.id)
    document.status = DocumentStatus.FAILED
    document.processing_error = reason[:2000]
    try:
        db.add(document)
        db.commit()
    except Exception:  # pragma: no cover - DB write failure during failure path
        db.rollback()
        logger.exception("Could not persist FAILED state for document %s", document.id)


def _safe_reason(exc: Exception) -> str:
    if isinstance(exc, pdf_service.PdfExtractionError):
        return "The PDF could not be read."
    message = str(exc)
    if not message:
        return "Document processing failed."
    return message[:300]


def _persist_chunks(
    db: Session,
    document: Document,
    chunks: list[Chunk],
    vectors: list[list[float]],
    *,
    page_count: int,
) -> None:
    """Replace all chunks for a document in a single transaction."""
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    now = datetime.now(timezone.utc)
    for chunk, vector in zip(chunks, vectors):
        db.add(
            DocumentChunk(
                document_id=document.id,
                content=chunk.text,
                embedding=vector,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                metadata_={
                    "document_id": str(document.id),
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                },
            )
        )
    document.status = DocumentStatus.ACTIVE
    document.page_count = page_count
    document.processed_at = now
    document.processing_error = None
    db.add(document)
    db.commit()


def process_document(
    db: Session,
    document_id: uuid.UUID,
    user: User,
    *,
    embedding_service=None,
) -> Document:
    """Run the full ingestion pipeline; raises on failure after persisting FAILED."""
    document = get_manageable_document(db, document_id, user)
    if embedding_service is None:
        from app.services.embedding_service import get_embedding_service

        embedding_service = get_embedding_service()

    _status_to_processing(db, document)

    embedding_dim = settings.EMBEDDING_DIM
    try:
        content = storage_service.read_document_file(document.file_path)
        pdf_service.validate_upload(filename=document.original_filename, content=content)

        pages = pdf_service.extract_pages(content)
        if not pages:
            raise ApiError("DOCUMENT_PROCESSING_FAILED", NO_TEXT_ERROR, status_code=500)

        chunks = chunk_pages(
            pages,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        if not chunks:
            raise ApiError("DOCUMENT_PROCESSING_FAILED", NO_TEXT_ERROR, status_code=500)

        vectors = embedding_service.embed([chunk.text for chunk in chunks])
        if any(len(vector) != embedding_dim for vector in vectors):
            raise ApiError(
                "DOCUMENT_PROCESSING_FAILED",
                "Embedding dimension did not match the configured EMBEDDING_DIM.",
                status_code=500,
            )

        page_count = max(p.page_number for p in pages)
        _persist_chunks(db, document, chunks, vectors, page_count=page_count)
        return _reload(db, document.id)
    except ApiError as exc:
        if exc.code == "DOCUMENT_PROCESSING_FAILED":
            _mark_failed(db, document, exc.message)
        raise
    except Exception as exc:
        logger.exception("Document %s processing failed", document.id)
        reason = _safe_reason(exc)
        _mark_failed(db, document, reason)
        raise ApiError(
            "DOCUMENT_PROCESSING_FAILED",
            "The document could not be processed.",
            status_code=500,
        ) from exc


def _reload(db: Session, document_id: uuid.UUID) -> Document:
    return db.scalar(select(Document).where(Document.id == document_id))