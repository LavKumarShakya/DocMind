"""Citation correctness metrics for an evaluated answer.

A citation is **valid** when its tag resolves to a retrieved chunk whose
document is one of the question's relevant documents. It is **supported**
when the cited chunk's text contains a ground-truth fragment for the question.
Unknown tags (the model citing evidence that was never retrieved) count as
invalid. Fallback answers cite nothing and are excluded from citation ratios
(``None``), since there is no citation behaviour to judge.
"""

from __future__ import annotations

from app.services.citation_service import extract_tags
from evaluation.dataset import Question, chunk_is_relevant


def analyze_citations(answer: str, candidates: list, question: Question) -> dict:
    """Return citation validity/support statistics for one answer.

    ``candidates`` is the ranked retrieval list the answer was generated from.
    """
    tags = extract_tags(answer)
    if not tags:
        return {
            "cited_tags": 0,
            "valid_tags": 0,
            "supported_tags": 0,
            "valid_ratio": None,
            "supported_ratio": None,
            "documents_cited": [],
        }

    by_index = {index + 1: candidate for index, candidate in enumerate(candidates)}
    relevant_docs = set(question.relevant_documents)

    valid = 0
    supported = 0
    cited_docs: list[str] = []
    for tag in tags:
        candidate = by_index.get(tag)
        if candidate is None:
            continue
        if candidate.document_title not in cited_docs:
            cited_docs.append(candidate.document_title)
        if candidate.document_title in relevant_docs:
            valid += 1
            if chunk_is_relevant(candidate.text, question.supporting_text):
                supported += 1

    return {
        "cited_tags": len(tags),
        "valid_tags": valid,
        "supported_tags": supported,
        "valid_ratio": round(valid / len(tags), 4),
        "supported_ratio": round(supported / len(tags), 4),
        "documents_cited": cited_docs,
    }


def citation_recall(citations: list[dict]) -> float:
    """Fraction of answerable, answered questions with at least one valid citation."""
    evaluated = [c for c in citations if c["cited_tags"] > 0]
    if not evaluated:
        return 0.0
    return round(sum(1 for c in evaluated if c["valid_ratio"] and c["valid_ratio"] > 0) / len(evaluated), 4)