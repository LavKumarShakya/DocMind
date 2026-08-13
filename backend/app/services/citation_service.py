"""Citation mapping: turn the LLM's source tags back into document references.

Citation metadata is sourced exclusively from the database retrieval results
(document title, page number, section). The ``section`` column is nullable and
Phase 3 chunking does not populate it, so citations surface ``section=None``
rather than fabricating one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.retrieval_types import RetrievalCandidate

_TAG_RE = re.compile(r"\[\s*(\d+)\s*\]")


@dataclass(frozen=True)
class Citation:
    """A single cited evidence source."""

    chunk_id: str
    document_id: str
    document_title: str
    page_number: int | None
    section: str | None
    chunk_index: int
    relevance_score: float | None = None


def extract_tags(answer: str) -> list[int]:
    """Return the citation tags referenced in an LLM answer, in order."""
    matches = [int(m) for m in _TAG_RE.findall(answer)]
    seen: set[int] = set()
    ordered: list[int] = []
    for tag in matches:
        if tag not in seen:
            seen.add(tag)
            ordered.append(tag)
    return ordered


def build_citations(
    answer: str, results: list[RetrievalCandidate]
) -> list[Citation]:
    """Map cited tags to their retrieval results.

    Tags are 1-based indexes into ``results``. Unknown tags (the model citing
    evidence that does not exist) are ignored. The citation carries the final
    reranker relevance score (0..1) for display purposes.
    """
    by_index = {index + 1: chunk for index, chunk in enumerate(results)}
    citations: list[Citation] = []
    for tag in extract_tags(answer):
        chunk = by_index.get(tag)
        if chunk is None:
            continue
        citations.append(
            Citation(
                chunk_id=str(chunk.chunk_id),
                document_id=str(chunk.document_id),
                document_title=chunk.document_title,
                page_number=chunk.page_number,
                section=chunk.section,
                chunk_index=chunk.chunk_index,
                relevance_score=getattr(chunk, "rerank_score", None),
            )
        )
    return citations