"""Cross-encoder reranking for Phase 5 hybrid retrieval.

The reranker re-scores the top fused candidates against the user's question
using a cross-encoder model (default ``cross-encoder/ms-marco-MiniLM-L-6-v2``).
Unlike bi-encoder dense retrieval, the query and the candidate are encoded
together, so the model can judge *premise-pair* relevance instead of relying on
a pre-computed vector dot product.

The model is loaded exactly once per process (lazy singleton, mirroring
``embedding_service``) and inference is batched. Raw cross-encoder logits are
transformed through a sigmoid so ``rerank_score`` lives in [0, 1]; this value
is the citation relevance score surfaced to the frontend.
"""

from __future__ import annotations

import logging
import threading

from app.core.config import settings
from app.services.retrieval_types import RetrievalCandidate

logger = logging.getLogger(__name__)


class RerankingService:
    """Wrap a sentence-transformers cross-encoder and re-rank candidates."""

    def __init__(self, model_name: str | None = None, batch_size: int | None = None) -> None:
        self.model_name = model_name or settings.RERANKER_MODEL
        self.batch_size = batch_size or settings.RERANKER_BATCH_SIZE
        self._model = None
        self._lock = threading.Lock()

    @property
    def model(self):
        """Lazily load the cross-encoder (thread-safe, once per process)."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import CrossEncoder
                    except ImportError as exc:  # pragma: no cover - dependency is required
                        raise RuntimeError("sentence-transformers is not installed.") from exc
                    logger.info("Loading cross-encoder reranker %s", self.model_name)
                    self._model = CrossEncoder(self.model_name)
        return self._model

    @staticmethod
    def _sigmoid(logit: float) -> float:
        return 1.0 / (1.0 + (2.718281828459045 ** -logit))

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        """Re-score ``candidates`` for ``query`` and return them sorted desc.

        Provenance fields are preserved verbatim; only ``rerank_score`` is
        written. An empty candidate list short-circuits without loading the
        model.
        """
        if not candidates:
            return []

        model = self.model
        pairs = [(query, candidate.text) for candidate in candidates]
        logits = model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
        )

        reranked: list[RetrievalCandidate] = []
        for candidate, logit in zip(candidates, logits):
            score = round(self._sigmoid(float(logit)), 6)
            reranked.append(
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
                    hybrid_score=candidate.hybrid_score,
                    rerank_score=score,
                )
            )
        reranked.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)
        return reranked


_instance: RerankingService | None = None


def get_reranking_service() -> RerankingService:
    """Return the shared reranking service, creating it on first use."""
    global _instance
    if _instance is None:
        _instance = RerankingService()
    return _instance


def set_reranking_service(service: RerankingService | None) -> None:
    """Override the shared service (used by tests to avoid model downloads)."""
    global _instance
    _instance = service
