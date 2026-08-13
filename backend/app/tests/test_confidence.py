"""Confidence gate tests: strong/weak evidence, thresholds, empty pools."""

import dataclasses
import uuid

import pytest

from app.rag.confidence import best_relevance_score, is_confident
from app.services.retrieval_types import RetrievalCandidate


def _candidate(rerank=None, hybrid=None):
    return RetrievalCandidate(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Doc",
        page_number=1,
        section=None,
        chunk_index=0,
        text="evidence",
        dense_score=0.5,
        hybrid_score=hybrid,
        rerank_score=rerank,
    )


def test_best_relevance_score_prefers_rerank():
    candidates = [
        _candidate(rerank=0.9, hybrid=0.5),
        _candidate(rerank=0.95, hybrid=0.6),
    ]
    assert best_relevance_score(candidates) == 0.95


def test_best_relevance_score_falls_back_to_hybrid():
    candidates = [_candidate(rerank=None, hybrid=0.7)]
    assert best_relevance_score(candidates) == 0.7


def test_best_relevance_score_zero_without_scores():
    candidates = [_candidate(rerank=None, hybrid=None)]
    assert best_relevance_score(candidates) == 0.0
    assert best_relevance_score([]) == 0.0


def test_strong_evidence_is_confident(monkeypatch):
    candidates = [_candidate(rerank=0.9)]
    assert is_confident(candidates) is True


def test_weak_evidence_is_not_confident(monkeypatch):
    candidates = [_candidate(rerank=0.05)]
    assert is_confident(candidates) is False


def test_empty_pool_is_not_confident():
    assert is_confident([]) is False


def test_custom_threshold(monkeypatch):
    candidates = [_candidate(rerank=0.5)]
    assert is_confident(candidates, threshold=0.4) is True
    assert is_confident(candidates, threshold=0.6) is False


def test_rerank_score_boundaries(monkeypatch):
    """Exact threshold equality is accepted (>= semantics)."""
    candidates = [_candidate(rerank=0.35)]
    assert is_confident(candidates) is True
    slightly_below = [_candidate(rerank=0.349)]
    assert is_confident(slightly_below) is False