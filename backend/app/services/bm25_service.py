"""BM25 keyword retrieval backed by PostgreSQL full-text search.

PostgreSQL FTS (tsvector + ``websearch_to_tsquery`` + ``ts_rank_cd``) is used
as the keyword counterpart to dense semantic retrieval. This keeps Phase 5
dependency-free: no extra engine (Solr/Elasticsearch/Typesense) is required,
and it runs entirely in SQL against the same ``document_chunks`` table.

Ranking is PostgreSQL's ``ts_rank_cd``, a BM25-style lexical relevance score
based on term frequency, proximity and document length. Like the dense stage,
permission filtering is part of the SQL WHERE clause — keyword retrieval never
retrieves-then-filters on the Python side.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import DocumentStatus
from app.db.models import Document, DocumentChunk, User
from app.services.document_service import visible_condition
from app.services.retrieval_types import RetrievalCandidate

logger = logging.getLogger(__name__)


class Bm25Service:
    """Rank chunks by PostgreSQL FTS relevance with permission filtering."""

    def search(
        self,
        db: Session,
        *,
        query: str,
        user: User,
        top_k: int | None = None,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[RetrievalCandidate]:
        """Return the top ``top_k`` keyword matches visible to ``user``."""
        top_k = top_k or settings.BM25_CANDIDATE_K

        ts_query = func.websearch_to_tsquery("english", query)
        match = DocumentChunk.searchable_content.op("@@")(ts_query)
        rank = func.ts_rank_cd(
            DocumentChunk.searchable_content, ts_query
        ).label("_rank")

        visibility = visible_condition(user)

        rows = db.execute(
            select(
                DocumentChunk,
                Document.title,
                rank,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.status == DocumentStatus.ACTIVE,
                visibility,
                DocumentChunk.document_id.in_(document_ids)
                if document_ids
                else True,
                match,
                DocumentChunk.searchable_content.isnot(None),
            )
            .order_by(rank.desc())
            .limit(top_k)
        ).all()

        results: list[RetrievalCandidate] = []
        for row in rows:
            chunk: DocumentChunk = row[0]
            title: str = row[1]
            results.append(
                RetrievalCandidate(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=title,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    chunk_index=chunk.chunk_index,
                    text=chunk.content,
                    bm25_score=round(float(row[2]), 6),
                )
            )
        if not results:
            logger.info("No BM25 matches for query %r", query)
        return results
