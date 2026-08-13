"""Shared retrieval result type used across Phase 5 retrieval services.

``RetrievalCandidate`` is the common currency between the dense (pgvector),
BM25 (PostgreSQL FTS), fusion and cross-encoder reranking stages. Every stage
fills in the scores it knows and leaves the rest ``None``; the provenance
fields (document, page, section, chunk index) are always copied verbatim from
the database row so no stage can invent source metadata.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalCandidate:
    """A retrieved evidence chunk plus its per-stage relevance scores."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_number: int | None
    section: str | None
    chunk_index: int
    text: str
    # Cosine similarity from the dense stage (0..1), when available.
    dense_score: float | None = None
    # Normalized BM25 rank from the keyword stage (0..1), when available.
    bm25_score: float | None = None
    # Weighted fusion of normalized dense + BM25 scores (0..1), when computed.
    hybrid_score: float | None = None
    # Final cross-encoder relevance score (sigmoid of logit, 0..1), when set.
    rerank_score: float | None = None
