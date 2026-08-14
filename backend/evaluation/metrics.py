"""Retrieval quality metrics: Recall@K, MRR, Precision@K, document recall.

All functions are pure and operate on plain sequences of identifiers (chunk
ids, document titles, ...) so they are trivially unit-testable without a
database or model. ``relevant`` should be a set/list of the relevant
identifiers and ``retrieved`` the ranked identifiers from a retrieval run
(best first).
"""

from __future__ import annotations

from statistics import mean

_EMPTY = frozenset()


def recall_at_k(relevant: set[str] | list[str], retrieved: list[str], k: int) -> float:
    """1.0 when any relevant item is among the first ``k`` results, else 0.0."""
    if not relevant:
        return 0.0
    return 1.0 if any(item in relevant for item in retrieved[:k]) else 0.0


def precision_at_k(relevant: set[str] | list[str], retrieved: list[str], k: int) -> float:
    """Fraction of the first ``k`` results that are relevant (0 when k <= 0)."""
    if k <= 0:
        return 0.0
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    hits = sum(1 for item in retrieved[:k] if item in relevant_set)
    return hits / k


def reciprocal_rank(relevant: set[str] | list[str], retrieved: list[str]) -> float:
    """1/rank of the first relevant result; 0 when nothing relevant is present."""
    relevant_set = set(relevant)
    for index, item in enumerate(retrieved, start=1):
        if item in relevant_set:
            return 1.0 / index
    return 0.0


def mrr(relevant: set[str] | list[str], retrieved: list[str]) -> float:
    """Mean reciprocal rank (single-query alias for readability)."""
    return reciprocal_rank(relevant, retrieved)


def document_recall_at_k(
    relevant_docs: set[str] | list[str], retrieved_docs: list[str], k: int
) -> float:
    """1.0 when a relevant document appears among the first ``k`` docs."""
    return recall_at_k(set(relevant_docs), retrieved_docs, k)


def first_relevant_rank(relevant: set[str] | list[str], retrieved: list[str]) -> int | None:
    """1-based rank of the first relevant result (``None`` when none found)."""
    relevant_set = set(relevant)
    for index, item in enumerate(retrieved, start=1):
        if item in relevant_set:
            return index
    return None


def hit_at_1(relevant: set[str] | list[str], retrieved: list[str]) -> float:
    """1.0 when the top result is relevant (accuracy of the #1 recommendation)."""
    return recall_at_k(relevant, retrieved, 1)


def mean_of(values: list[float]) -> float:
    """Arithmetic mean; 0.0 for an empty list (never NaN in reports)."""
    return mean(values) if values else 0.0


def aggregate_recall(
    relevant_list: list[set[str] | list[str]],
    retrieved_list: list[list[str]],
    ks: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, float]:
    """Mean Recall@K for a batch of queries, one dict key per K."""
    if len(relevant_list) != len(retrieved_list):
        raise ValueError("relevant_list and retrieved_list must have equal length")
    out: dict[str, float] = {}
    for k in ks:
        values = [
            recall_at_k(relevant, retrieved, k)
            for relevant, retrieved in zip(relevant_list, retrieved_list)
        ]
        out[f"recall@{k}"] = round(mean_of(values), 4)
    return out


def aggregate_mrr(relevant_list: list[set[str] | list[str]], retrieved_list: list[list[str]]) -> float:
    """Mean MRR for a batch of queries."""
    values = [
        reciprocal_rank(relevant, retrieved)
        for relevant, retrieved in zip(relevant_list, retrieved_list)
    ]
    return round(mean_of(values), 4)