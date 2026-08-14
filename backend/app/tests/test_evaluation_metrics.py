"""Unit tests for retrieval quality metrics (pure functions, no DB)."""

from evaluation.metrics import (
    aggregate_mrr,
    aggregate_recall,
    document_recall_at_k,
    first_relevant_rank,
    mrr,
    mean_of,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_hit_in_window():
    assert recall_at_k({"b"}, ["a", "b", "c"], 2) == 1.0
    assert recall_at_k({"c"}, ["a", "b", "c"], 2) == 0.0
    assert recall_at_k({"x"}, ["a", "b", "c"], 5) == 0.0


def test_recall_at_k_empty_relevant_is_zero():
    assert recall_at_k(set(), ["a", "b"], 3) == 0.0


def test_precision_at_k():
    assert precision_at_k({"a", "b"}, ["a", "x", "b"], 2) == 0.5
    assert precision_at_k({"z"}, ["a", "b"], 2) == 0.0
    assert precision_at_k({"a"}, ["a"], 0) == 0.0


def test_reciprocal_rank_and_mrr():
    assert reciprocal_rank({"b"}, ["a", "b", "c"]) == 0.5
    assert mrr({"a"}, ["a", "b"]) == 1.0
    assert reciprocal_rank({"z"}, ["a", "b"]) == 0.0


def test_document_recall_at_k():
    assert document_recall_at_k({"d1"}, ["d2", "d1", "d3"], 3) == 1.0
    assert document_recall_at_k({"d1"}, ["d2", "d3"], 2) == 0.0


def test_first_relevant_rank():
    assert first_relevant_rank({"c"}, ["a", "b", "c"]) == 3
    assert first_relevant_rank({"z"}, ["a", "b"]) is None


def test_mean_of_empty_is_zero():
    assert mean_of([]) == 0.0


def test_aggregate_recall_and_mrr():
    relevant = [{"a"}, {"x"}]
    retrieved = [["a", "b"], ["y", "x"]]
    agg = aggregate_recall(relevant, retrieved, ks=(1, 2))
    assert agg["recall@1"] == 0.5
    assert agg["recall@2"] == 1.0
    assert aggregate_mrr(relevant, retrieved) == 0.75


def test_aggregate_recall_rejects_mismatched_lengths():
    import pytest

    with pytest.raises(ValueError):
        aggregate_recall([{"a"}], [["a"], ["b"]])
