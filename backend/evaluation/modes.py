"""Retrieval mode drivers: baseline (Phase 4 dense-only) vs phase5 (hybrid).

Both drivers reuse the exact production services (``RetrievalService``,
``Bm25Service``, ``HybridRetrievalService``/``RerankingService``) so the
evaluation measures the real pipeline, not a re-implementation. The only
difference is the retrieval recipe:

- **baseline** mirrors Phase 4: a single dense pgvector lookup.
- **phase5** mirrors Phase 5: dense + BM25 candidate pools fused with the
  configured weights, then cross-encoder reranking.

The evaluation window is ``EVAL_TOP_K`` (10) so Recall@10 is well defined in
both modes. The phase5 reranker is fed ``EVAL_TOP_K`` candidates by overriding
``settings.RERANK_TOP_K`` for the duration of a run (recorded in metadata).

Each driver returns the ranked ``RetrievalCandidate`` list plus per-stage
timings in seconds.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User
from app.services.bm25_service import Bm25Service
from app.services.retrieval_service import RetrievalService
from app.services.retrieval_types import RetrievalCandidate

logger = logging.getLogger(__name__)

EVAL_TOP_K = 10


@dataclass
class RetrievalOutcome:
    """Ranked candidates plus per-stage wall-clock timings (seconds)."""

    candidates: list[RetrievalCandidate] = field(default_factory=list)
    times: dict[str, float] = field(default_factory=dict)


class BaselineRetriever:
    """Phase 4 recipe: dense pgvector lookup only."""

    name = "baseline"

    def __init__(self, *, dense_service: RetrievalService | None = None) -> None:
        self._dense = dense_service or RetrievalService()

    def retrieve(self, db: Session, *, query: str, user: User, top_k: int = EVAL_TOP_K) -> RetrievalOutcome:
        start = time.perf_counter()
        query_embedding = self._dense.embed_query(query)
        chunks = self._dense.retrieve(db, query_embedding=query_embedding, user=user, top_k=top_k)
        elapsed = time.perf_counter() - start

        candidates = [
            RetrievalCandidate(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                page_number=c.page_number,
                section=c.section,
                chunk_index=c.chunk_index,
                text=c.text,
                dense_score=c.score,
            )
            for c in chunks
        ]
        return RetrievalOutcome(candidates=candidates, times={"dense": elapsed})


class Phase5Retriever:
    """Phase 5 recipe: dense + BM25 → fuse → cross-encoder rerank."""

    name = "phase5"

    def __init__(
        self,
        *,
        dense_service: RetrievalService | None = None,
        bm25_service: Bm25Service | None = None,
        reranking_service=None,
    ) -> None:
        self._dense = dense_service or RetrievalService()
        self._bm25 = bm25_service or Bm25Service()
        if reranking_service is None:
            from app.services.reranking_service import get_reranking_service

            reranking_service = get_reranking_service()
        self._rerank = reranking_service

    def retrieve(self, db: Session, *, query: str, user: User, top_k: int = EVAL_TOP_K) -> RetrievalOutcome:
        from app.services.hybrid_retrieval_service import HybridRetrievalService

        times: dict[str, float] = {}

        start = time.perf_counter()
        query_embedding = self._dense.embed_query(query)
        dense = self._dense.retrieve(
            db,
            query_embedding=query_embedding,
            user=user,
            top_k=settings.DENSE_CANDIDATE_K,
        )
        times["dense"] = time.perf_counter() - start

        start = time.perf_counter()
        bm25 = self._bm25.search(db, query=query, user=user, top_k=settings.BM25_CANDIDATE_K)
        times["bm25"] = time.perf_counter() - start

        dense_candidates = [
            RetrievalCandidate(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                page_number=c.page_number,
                section=c.section,
                chunk_index=c.chunk_index,
                text=c.text,
                dense_score=c.score,
            )
            for c in dense
        ]

        start = time.perf_counter()
        fused = HybridRetrievalService._fuse(dense_candidates + bm25)
        times["fuse"] = time.perf_counter() - start

        if not fused:
            return RetrievalOutcome(candidates=[], times=times)

        start = time.perf_counter()
        reranked = self._rerank.rerank(query, fused[:top_k])
        times["rerank"] = time.perf_counter() - start

        return RetrievalOutcome(candidates=reranked[:top_k], times=times)