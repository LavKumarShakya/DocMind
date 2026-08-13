"""Hybrid retrieval: dense (pgvector) + BM25 (PostgreSQL FTS) + reranking.

Pipeline (Phase 5):
  1. Dense retrieval returns its top ``DENSE_CANDIDATE_K`` chunks.
  2. BM25 keyword retrieval returns its top ``BM25_CANDIDATE_K`` chunks.
  3. The two pools are merged and deduplicated by chunk id.
  4. Dense and BM25 scores are min-max normalized separately, then fused with
     the configured weights to give ``hybrid_score``.
  5. The top ``RERANK_TOP_K`` fused candidates are re-scored by a cross-encoder
     and returned ordered by ``rerank_score``.

Permission filtering happens inside both retrievers (SQL-level), so a query
can never surface chunks the user may not see. The service degrades
gracefully: if one retriever fails it falls back to the other, and if the
reranker fails the fused hybrid order is used.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User
from app.rag.score_normalization import min_max_normalize
from app.services.bm25_service import Bm25Service
from app.services.retrieval_service import RetrievalService
from app.services.retrieval_types import RetrievalCandidate

logger = logging.getLogger(__name__)


class HybridRetrievalService:
    """Combine dense and keyword retrieval into a single reranked list."""

    def __init__(self, *, dense_service=None, bm25_service=None, reranking_service=None) -> None:
        self._dense = dense_service or RetrievalService()
        self._bm25 = bm25_service or Bm25Service()
        if reranking_service is None:
            from app.services.reranking_service import get_reranking_service

            reranking_service = get_reranking_service()
        self._rerank = reranking_service

    def _dense_results(
        self, db: Session, *, query: str, user: User
    ) -> list[RetrievalCandidate]:
        try:
            query_embedding = self._dense.embed_query(query)
            chunks = self._dense.retrieve(
                db,
                query_embedding=query_embedding,
                user=user,
                top_k=settings.DENSE_CANDIDATE_K,
            )
        except Exception as exc:  # pragma: no cover - defensive degradation
            logger.warning("Dense retrieval failed, using BM25 only: %s", exc)
            return []
        return [
            RetrievalCandidate(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                page_number=c.page_number,
                section=c.section,
                chunk_index=c.chunk_index,
                text=c.text,
                dense_score=getattr(c, "score", None) or c.dense_score,
            )
            for c in chunks
        ]

    def _bm25_results(
        self, db: Session, *, query: str, user: User
    ) -> list[RetrievalCandidate]:
        try:
            return self._bm25.search(
                db, query=query, user=user, top_k=settings.BM25_CANDIDATE_K
            )
        except Exception as exc:  # pragma: no cover - defensive degradation
            logger.warning("BM25 retrieval failed, using dense only: %s", exc)
            return []

    @staticmethod
    def _fuse(
        candidates: list[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        """Dedupe by chunk id, normalize per-source scores, fuse with weights."""
        by_id: dict = {}
        for candidate in candidates:
            existing = by_id.get(candidate.chunk_id)
            if existing is None:
                by_id[candidate.chunk_id] = candidate
            else:
                # Keep the first occurrence but carry over whichever scores
                # each stage produced (they are disjoint by construction).
                merged = RetrievalCandidate(
                    chunk_id=existing.chunk_id,
                    document_id=existing.document_id,
                    document_title=existing.document_title,
                    page_number=existing.page_number,
                    section=existing.section,
                    chunk_index=existing.chunk_index,
                    text=existing.text,
                    dense_score=(
                        existing.dense_score
                        if existing.dense_score is not None
                        else candidate.dense_score
                    ),
                    bm25_score=(
                        existing.bm25_score
                        if existing.bm25_score is not None
                        else candidate.bm25_score
                    ),
                )
                by_id[candidate.chunk_id] = merged

        deduped = list(by_id.values())

        dense_scores = [c.dense_score or 0.0 for c in deduped]
        bm25_scores = [c.bm25_score or 0.0 for c in deduped]
        norm_dense = min_max_normalize(dense_scores)
        norm_bm25 = min_max_normalize(bm25_scores)

        w_dense = settings.HYBRID_DENSE_WEIGHT
        w_bm25 = settings.HYBRID_BM25_WEIGHT
        total = w_dense + w_bm25

        fused: list[RetrievalCandidate] = []
        for candidate, nd, nb in zip(deduped, norm_dense, norm_bm25):
            hybrid = (w_dense * nd + w_bm25 * nb) / total
            fused.append(
                RetrievalCandidate(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    document_title=candidate.document_title,
                    page_number=candidate.page_number,
                    section=candidate.section,
                    chunk_index=candidate.chunk_index,
                    text=candidate.text,
                    dense_score=candidate.dense_score,
                    bm25_score=candidate.bm25_score,
                    hybrid_score=round(hybrid, 6),
                )
            )
        fused.sort(key=lambda c: c.hybrid_score or 0.0, reverse=True)
        return fused

    def retrieve(
        self, db: Session, *, query: str, user: User
    ) -> list[RetrievalCandidate]:
        """Run the full hybrid pipeline and return reranked candidates."""
        dense = self._dense_results(db, query=query, user=user)
        bm25 = self._bm25_results(db, query=query, user=user)
        pool = self._fuse(dense + bm25)
        if not pool:
            return []

        top = pool[: settings.RERANK_TOP_K]
        try:
            return self._rerank.rerank(query, top)
        except Exception as exc:  # pragma: no cover - defensive degradation
            logger.warning("Reranker failed, returning hybrid-fused order: %s", exc)
            return top
