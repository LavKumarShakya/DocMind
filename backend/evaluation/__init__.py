"""Phase 7 evaluation framework for CampusRAG.

Reproducible, version-controlled evaluation of retrieval quality, ranking,
confidence gating, citations, faithfulness, correctness and latency. Two modes
are compared: ``baseline`` (Phase 4 dense-only) and ``phase5`` (dense + BM25 +
hybrid fusion + cross-encoder reranking).
"""

from __future__ import annotations

__version__ = "1.0"
