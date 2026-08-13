"""Score normalization for hybrid retrieval fusion.

Dense cosine similarities and BM25 ``ts_rank`` outputs live on different
scales, so they cannot be added directly. Phase 5 normalizes each retriever's
scores to the same [0, 1] range before weighted fusion.

Choice: **min-max normalization**. Rationale:

- It is simple, deterministic, and easy to explain and audit.
- It maps the observed spread of each retriever's scores onto the same
  interval, which makes the fusion weights interpretable (HYBRID_DENSE_WEIGHT
  / HYBRID_BM25_WEIGHT) regardless of the raw scale.
- Limitation: it is sensitive to outliers and to the size of the candidate
  pool. A single outlier compresses the rest of the range. For our bounded
  candidate pools (DENSE_CANDIDATE_K / BM25_CANDIDATE_K ≤ 20) this is
  acceptable and is documented as the trade-off.

A candidate found by only one retriever gets the minimum (0.0) normalized
score for the retriever that did not surface it, so it still contributes to
the fused score through the other retriever's weight.
"""

from __future__ import annotations


def min_max_normalize(values: list[float]) -> list[float]:
    """Normalize ``values`` in place-safe way into [0, 1] via min-max.

    Returns a new list. A constant or single-value list maps every entry to
    1.0 (degenerate min == max case) so the fused score stays meaningful.
    """
    if not values:
        return []
    low, high = min(values), max(values)
    if high - low < 1e-12:
        return [1.0 for _ in values]
    return [(value - low) / (high - low) for value in values]
