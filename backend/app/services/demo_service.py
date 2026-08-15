"""Public demo mode: a single pre-indexed document + grounded demo chat.

The demo PDF is processed exactly once by ``python -m scripts.build_demo_index``
(which reads the PDF, extracts text, chunks it and stores pgvector embeddings in
the database — the same persistent vector store used by normal ingestion). At
runtime the demo path never re-reads the PDF, re-chunks or re-embeds it: every
question only runs query embedding + hybrid retrieval over the already-stored
chunks, so a public deployment stays cheap on RAM.

Retrieval is scoped to the demo document id (``DEMO_DOCUMENT_ID``) in SQL and
permission filtering is unchanged (the demo document is PUBLIC, so the in-memory
guest user may see it). If the demo index is missing the chat endpoint returns a
clear server-side error instead of silently falling back to an empty store.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import AccessLevel, DocumentStatus, Role
from app.core.errors import ApiError
from app.db.models import Document, DocumentChunk, DocumentVersion, User
from app.rag.chunking import chunk_pages
from app.rag.prompts import DEMO_FALLBACK_ANSWER, build_demo_system_prompt
from app.services import pdf_service, rag_service, storage_service
from app.services.citation_service import Citation

logger = logging.getLogger(__name__)

# Fixed, deterministic id shared by the build script, readiness checks and
# retrieval scoping so they always refer to the same row.
DEMO_DOCUMENT_ID = uuid.UUID(settings.DEMO_DOCUMENT_ID)

# In-memory user used for demo retrieval. Only used to satisfy the shared
# permission predicates; the demo document is PUBLIC, so this guest sees it.
_GUEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

_DEMO_INDEX_MISSING_MESSAGE = (
    "The demo document index has not been built yet. "
    "Run `python -m scripts.build_demo_index` from the backend directory "
    "(see the README 'Public demo mode' section)."
)


@dataclass(frozen=True)
class DemoAnswer:
    """The demo chat endpoint's response payload."""

    answer: str
    citations: list[Citation] = field(default_factory=list)


def resolve_demo_document_path() -> Path:
    """Resolve ``DEMO_DOCUMENT_PATH`` to an existing file.

    Absolute paths are used as-is. Relative paths are tried against the current
    working directory and then each parent, so the default (``../Doc/...``)
    works from ``backend/`` and the Docker container working directory alike.
    """
    configured = Path(settings.DEMO_DOCUMENT_PATH)
    if configured.is_absolute():
        return configured
    for base in (Path.cwd(), *Path.cwd().parents):
        candidate = base / configured
        if candidate.is_file():
            return candidate
    return Path.cwd() / configured


def _demo_guest() -> User:
    """An in-memory, non-persisted visitor used to run the shared pipeline."""
    return User(
        id=_GUEST_USER_ID,
        name="Demo Visitor",
        email="demo@docmind.local",
        password_hash="",
        role=Role.STUDENT,
    )


def get_demo_document(db: Session) -> Document | None:
    return db.get(Document, DEMO_DOCUMENT_ID)


def demo_chunk_count(db: Session) -> int:
    return (
        db.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == DEMO_DOCUMENT_ID
            )
        )
        or 0
    )


def demo_index_ready(db: Session) -> bool:
    """True when the demo document exists, is ACTIVE and has stored chunks."""
    document = get_demo_document(db)
    if document is None or document.status != DocumentStatus.ACTIVE:
        return False
    return demo_chunk_count(db) > 0


def build_demo_index(db: Session, *, embedding_service=None) -> Document:
    """Create (or recreate) the pre-indexed demo document from the demo PDF.

    Idempotent in effect: existing chunks for the demo document are replaced,
    never duplicated. This is the one-time cost — the runtime chat path never
    calls it.
    """
    if embedding_service is None:
        from app.services.embedding_service import get_embedding_service

        embedding_service = get_embedding_service()

    pdf_path = resolve_demo_document_path()
    if not pdf_path.is_file():
        raise ApiError(
            "DEMO_DOCUMENT_MISSING",
            f"Demo PDF not found at {pdf_path}. Set DEMO_DOCUMENT_PATH.",
            status_code=500,
        )

    content = pdf_path.read_bytes()
    pdf_service.validate_upload(filename=pdf_path.name, content=content)

    pages = pdf_service.extract_pages(content)
    if not pages:
        raise ApiError(
            "DEMO_INDEX_BUILD_FAILED",
            "No text could be extracted from the demo PDF.",
            status_code=500,
        )

    chunks = chunk_pages(
        pages,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )
    if not chunks:
        raise ApiError(
            "DEMO_INDEX_BUILD_FAILED",
            "No chunks were produced from the demo PDF.",
            status_code=500,
        )

    vectors = embedding_service.embed([chunk.text for chunk in chunks])
    if any(len(vector) != settings.EMBEDDING_DIM for vector in vectors):
        raise ApiError(
            "DEMO_INDEX_BUILD_FAILED",
            "Embedding dimension did not match the configured EMBEDDING_DIM.",
            status_code=500,
        )

    stored_path = storage_service.save_document_file(DEMO_DOCUMENT_ID, content)

    document = get_demo_document(db)
    if document is None:
        document = Document(
            id=DEMO_DOCUMENT_ID,
            title=settings.DEMO_DOCUMENT_TITLE,
            description="Pre-indexed document used by the public DocMind demo.",
            status=DocumentStatus.ACTIVE,
            access_level=AccessLevel.PUBLIC,
            file_path=stored_path,
            original_filename=pdf_path.name,
            mime_type="application/pdf",
            file_size=len(content),
            uploaded_by=None,
        )
        db.add(document)
        db.flush()
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            status=DocumentStatus.ACTIVE,
            filename=pdf_path.name,
            storage_path=stored_path,
            file_size=len(content),
        )
        db.add(version)
        db.flush()
        document.current_version_id = version.id
    else:
        document.file_path = stored_path
        document.status = DocumentStatus.ACTIVE
        document.original_filename = pdf_path.name
        document.mime_type = "application/pdf"
        document.file_size = len(content)
        document.processing_error = None
        if document.current_version_id is not None:
            version = db.get(DocumentVersion, document.current_version_id)
            if version is not None:
                version.status = DocumentStatus.ACTIVE
                version.filename = pdf_path.name
                version.storage_path = stored_path
                version.file_size = len(content)
                db.add(version)

    now = datetime.now(timezone.utc)
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == DEMO_DOCUMENT_ID))
    for chunk, vector in zip(chunks, vectors):
        db.add(
            DocumentChunk(
                document_id=DEMO_DOCUMENT_ID,
                content=chunk.text,
                embedding=vector,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                metadata_={
                    "document_id": str(DEMO_DOCUMENT_ID),
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                },
            )
        )
    document.page_count = max(page.page_number for page in pages)
    document.processed_at = now
    db.add(document)
    db.commit()

    rebuilt = db.get(Document, DEMO_DOCUMENT_ID)
    logger.info(
        "Built demo index: %d chunks from %d pages (%s)",
        len(chunks),
        len(pages),
        pdf_path.name,
    )
    return rebuilt


def answer_demo_question(db: Session, *, question: str) -> DemoAnswer:
    """Run the shared RAG pipeline over the demo document only.

    The LLM is only called when retrieval evidence clears the confidence gate;
    otherwise the demo fallback (grounded refusal) is returned so the demo
    never hallucinates from general knowledge.
    """
    if not question.strip():
        raise ApiError("MESSAGE_EMPTY", "Message must not be empty.", status_code=422)
    if len(question) > settings.MAX_MESSAGE_LENGTH:
        raise ApiError(
            "MESSAGE_TOO_LONG",
            f"Message exceeds the {settings.MAX_MESSAGE_LENGTH} character limit.",
            status_code=422,
        )

    if not demo_index_ready(db):
        raise ApiError("DEMO_INDEX_MISSING", _DEMO_INDEX_MISSING_MESSAGE, status_code=503)

    try:
        result = rag_service.answer_question(
            db,
            question=question,
            user=_demo_guest(),
            document_ids=[DEMO_DOCUMENT_ID],
            system_prompt_builder=build_demo_system_prompt,
            fallback_answer=DEMO_FALLBACK_ANSWER,
        )
    except ApiError:
        raise
    except Exception as exc:
        # Provider failures (construction or transient API/network errors, e.g.
        # Gemini 429/503) must not surface a 500 to every visitor: refuse
        # gracefully instead of hallucinating or erroring.
        logger.warning(
            "Demo question could not be answered (provider/retrieval failure); "
            "returning grounded refusal: %s",
            exc,
        )
        return DemoAnswer(answer=DEMO_FALLBACK_ANSWER)

    return DemoAnswer(answer=result.answer, citations=result.citations)