"""Retrieval confidence gating (Phase 5).

Before calling the LLM, the pipeline checks whether the best retrieved
evidence is strong enough to answer from. Confidence is defined as the top
reranker relevance score (sigmoid-transformed cross-encoder output, 0..1)
among the retrieved candidates.

If the reranker did not produce a score (e.g. reranker unavailable and the
pipeline degraded to hybrid-fused ordering), the gate falls back to the fused
hybrid score so the system keeps working during a reranker outage. When no
score of any kind exists the query is rejected as not confident.

Weak evidence returns the fixed grounded fallback answer; the LLM is never
called in that case.
"""

from __future__ import annotations

from app.core.config import settings


def best_relevance_score(candidates: list) -> float:
    """Highest reranker score, then highest hybrid score, else 0.0."""
    rerank_scores = [c.rerank_score for c in candidates if c.rerank_score is not None]
    if rerank_scores:
        return max(rerank_scores)
    hybrid_scores = [c.hybrid_score for c in candidates if c.hybrid_score is not None]
    if hybrid_scores:
        return max(hybrid_scores)
    return 0.0


def is_confident(candidates: list, *, threshold: float | None = None) -> bool:
    """True when the strongest evidence clears the confidence threshold."""
    threshold = threshold if threshold is not None else settings.CONFIDENCE_THRESHOLD
    return best_relevance_score(candidates) >= threshold
