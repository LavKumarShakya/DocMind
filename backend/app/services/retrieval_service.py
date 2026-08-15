"""Semantic retrieval over pgvector with document-level permission filtering.

Retrieval executes entirely in SQL: the query embedding is compared against
``document_chunks.embedding`` using pgvector's cosine distance operator and
the vector's HNSW index. Permission rules (uploader or access-level match,
mirroring document_service) are part of the WHERE clause — the chat API never
filters out unretrievable evidence on the Python side.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import DocumentStatus
from app.db.models import Document, DocumentChunk, User
from app.services.document_service import visible_condition

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    """A single retrieved evidence chunk plus its provenance."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_number: int | None
    section: str | None
    chunk_index: int
    text: str
    score: float  # cosine similarity, 0..1 (higher = better)


class RetrievalService:
    """Retrieve chunks whose documents are visible to the requesting user."""

    def __init__(self, *, embedding_service=None) -> None:
        if embedding_service is None:
            from app.services.embedding_service import get_embedding_service

            embedding_service = get_embedding_service()
        self._embedding_service = embedding_service

    def embed_query(self, query: str) -> list[float]:
        vectors = self._embedding_service.embed([query])
        return vectors[0]

    def retrieve(
        self,
        db: Session,
        *,
        query_embedding: list[float],
        user: User,
        top_k: int | None = None,
        min_similarity: float | None = None,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[RetrievedChunk]:
        top_k = top_k or settings.RETRIEVAL_TOP_K
        min_similarity = settings.RETRIEVAL_MIN_SIMILARITY if min_similarity is None else min_similarity
        # pgvector cosine_distance = 1 - cosine_similarity.
        max_distance = 1.0 - min_similarity

        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        visibility = visible_condition(user)

        rows = db.execute(
            select(
                DocumentChunk,
                Document.title,
                distance.label("_distance"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.status == DocumentStatus.ACTIVE,
                visibility,
                DocumentChunk.document_id.in_(document_ids)
                if document_ids
                else True,
                distance <= max_distance,
                DocumentChunk.embedding.isnot(None),
            )
            .order_by(distance.asc())
            .limit(top_k)
        ).all()

        results = []
        for row in rows:
            chunk: DocumentChunk = row[0]
            title: str = row[1]
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=title,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    chunk_index=chunk.chunk_index,
                    text=chunk.content,
                    score=round(1.0 - row[2], 4),
                )
            )
        if not results:
            logger.info("No chunks retrieved above similarity %.2f", min_similarity)
        return results


def search(
    db: Session,
    *,
    query: str,
    user: User,
    service: RetrievalService | None = None,
    top_k: int | None = None,
    min_similarity: float | None = None,
) -> list[RetrievedChunk]:
    """One-shot convenience wrapper for embed + retrieve."""
    svc = service or RetrievalService()
    query_embedding = svc.embed_query(query)
    return svc.retrieve(
        db,
        query_embedding=query_embedding,
        user=user,
        top_k=top_k,
        min_similarity=min_similarity,
    )