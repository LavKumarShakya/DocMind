"""Public demo mode: a single pre-indexed document + grounded demo chat.

The demo PDF is processed exactly once by ``python -m scripts.build_demo_index``
(which reads the PDF, extracts text, chunks it and stores pgvector embeddings in
the database — the same persistent vector store used by normal ingestion). At
runtime the demo path never re-reads the PDF, re-chunks or re-embeds it.

Unlike the local/Docker RAG pipeline, the public demo never loads the embedding
model (``BAAI/bge-base-en-v1.5``) or the cross-encoder reranker: query-time
retrieval is a lightweight pure-Python TF-IDF cosine search over the already
stored demo chunks (see ``retrieve_demo_evidence``). This keeps a hosted demo
instance well under the memory limit while still supporting arbitrary
visitor questions — the preset frontend chips are real questions, not hardcoded
answer mappings.

Retrieval is scoped to the demo document id (``DEMO_DOCUMENT_ID``) in SQL and
permission filtering is unchanged (the demo document is PUBLIC, so the in-memory
guest user may see it). If the demo index is missing the chat endpoint returns a
clear server-side error instead of silently falling back to an empty store.
"""

from __future__ import annotations

import logging
import math
import re
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
from app.services.document_service import visible_condition
from app.services.retrieval_types import RetrievalCandidate

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


# ─── Lightweight demo retrieval (no embedding model, no reranker) ───

# Tokens that carry no meaning for matching a demo question to an evidence
# chunk. Kept deliberately small and generic so custom questions work too.
_DEMO_STOPWORDS = frozenset(
    {
        "the", "and", "for", "that", "this", "with", "was", "were", "are",
        "what", "how", "much", "many", "why", "which", "when", "who", "whom",
        "whose", "did", "does", "do", "of", "a", "an", "is", "in", "on", "as",
        "it", "at", "by", "be", "or", "if", "to", "its", "than", "from",
        "about", "compared", "within", "acceptable", "limit", "latency",
    }
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _demo_tokens(text: str) -> list[str]:
    """Lowercase alphanumeric word tokens with the stopword list applied."""
    return [word for word in _WORD_RE.findall(text.lower()) if word not in _DEMO_STOPWORDS]


def retrieve_demo_evidence(
    db: Session,
    question: str,
    user: User,
    *,
    top_k: int = 5,
) -> list[RetrievalCandidate]:
    """Pure-Python TF-IDF cosine retrieval over the prebuilt demo chunks.

    The stored pgvector embeddings are *not* used here (they are retained so
    the build tool and the local/Docker path still work, but loading the model
    to embed the query would defeat the whole point of a memory-safe public
    demo). Instead the chunks' stored text is scored with TF-IDF cosine
    similarity against the tokenized question — a fully offline, dependency-free
    retriever that keeps the hosted demo process light.
    """
    query_tokens = _demo_tokens(question)
    if not query_tokens:
        return []

    visibility = visible_condition(user)
    rows = db.execute(
        select(DocumentChunk, Document.title)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.status == DocumentStatus.ACTIVE,
            visibility,
            DocumentChunk.document_id == DEMO_DOCUMENT_ID,
            DocumentChunk.searchable_content.isnot(None),
        )
        .order_by(DocumentChunk.chunk_index.asc())
    ).all()

    documents = [_demo_tokens(row[0].content) for row in rows]
    titles = [row[1] for row in rows]
    chunks = [row[0] for row in rows]
    if not documents:
        return []

    n_docs = len(documents)
    document_frequency: dict[str, int] = {}
    for tokens in documents:
        for term in set(tokens):
            document_frequency[term] = document_frequency.get(term, 0) + 1
    idf = {
        term: math.log((n_docs + 1) / (df + 1)) + 1.0
        for term, df in document_frequency.items()
    }

    document_vectors: list[dict[str, float]] = []
    document_norms: list[float] = []
    for tokens in documents:
        term_frequency: dict[str, int] = {}
        for term in tokens:
            term_frequency[term] = term_frequency.get(term, 0) + 1
        vector = {term: freq * idf.get(term, 0.0) for term, freq in term_frequency.items()}
        norm = math.sqrt(sum(w * w for w in vector.values()))
        document_vectors.append(vector)
        document_norms.append(norm if norm else 1.0)

    query_frequency: dict[str, int] = {}
    for term in query_tokens:
        query_frequency[term] = query_frequency.get(term, 0) + 1
    query_vector = {term: freq * idf.get(term, 0.0) for term, freq in query_frequency.items()}
    query_norm = math.sqrt(sum(w * w for w in query_vector.values()))
    if query_norm == 0.0:
        return []

    scored: list[tuple[float, int]] = []
    for index, vector in enumerate(document_vectors):
        dot = sum(weight * vector.get(term, 0.0) for term, weight in query_vector.items())
        similarity = dot / (query_norm * document_norms[index])
        scored.append((similarity, index))
    scored.sort(key=lambda item: item[1])
    scored.sort(key=lambda item: item[0], reverse=True)

    results: list[RetrievalCandidate] = []
    for similarity, index in scored[:top_k]:
        chunk = chunks[index]
        results.append(
            RetrievalCandidate(
                chunk_id=chunk.id,
                document_id=DEMO_DOCUMENT_ID,
                document_title=titles[index],
                page_number=chunk.page_number,
                section=chunk.section,
                chunk_index=chunk.chunk_index,
                text=chunk.content,
                dense_score=round(max(0.0, similarity), 6),
                # The confidence gate (rag_service) falls back to the fused
                # hybrid score when no reranker ran — which is always the case
                # in demo mode. Carrying the TF-IDF similarity there lets the
                # gate apply DEMO_CONFIDENCE_THRESHOLD without a reranker.
                hybrid_score=round(max(0.0, similarity), 6),
            )
        )
    return results


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

    Retrieval uses the lightweight, model-free TF-IDF search over the prebuilt
    demo index (``retrieve_demo_evidence``), so the embedding model and the
    reranker are never loaded in demo mode. The LLM is only called when the
    retrieval evidence clears the demo confidence gate; otherwise the demo
    fallback (grounded refusal) is returned so the demo never hallucinates from
    general knowledge.
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
            retrieval_pipeline=retrieve_demo_evidence,
            confidence_threshold=settings.DEMO_CONFIDENCE_THRESHOLD,
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