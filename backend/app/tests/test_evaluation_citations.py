"""Unit tests for the confidence-gate 2x2 analysis and citation metrics."""

import uuid

from app.services.retrieval_types import RetrievalCandidate
from evaluation.citations import analyze_citations, citation_recall
from evaluation.confidence import classify, confusion_matrix
from evaluation.dataset import Question


def _question(**overrides) -> Question:
    base = {
        "id": "Q1",
        "question": "What is the attendance rule?",
        "expected_answer": "75%",
        "expected_answer_terms": ["75"],
        "relevant_documents": ["academic_regulations"],
        "relevant_pages": [1],
        "supporting_text": ["75% of total classes"],
        "category": "numeric",
        "difficulty": "easy",
        "answerable": True,
    }
    base.update(overrides)
    return Question(base)


def _candidate(title: str, text: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title=title,
        page_number=1,
        section=None,
        chunk_index=0,
        text=text,
        rerank_score=0.9,
    )


def test_classify_buckets():
    assert classify(_question(), True) == "answerable::accepted"
    assert classify(_question(), False) == "answerable::rejected"
    assert classify(_question(answerable=False), True) == "unanswerable::accepted"
    assert classify(_question(answerable=False), False) == "unanswerable::rejected"


def test_confusion_matrix_counts_and_rates():
    rows = [
        {"bucket": "answerable::accepted", "correct": True},
        {"bucket": "answerable::accepted", "correct": False},
        {"bucket": "answerable::rejected", "correct": False},
        {"bucket": "unanswerable::rejected", "correct": True},
        {"bucket": "unanswerable::accepted", "correct": True},
    ]
    m = confusion_matrix(rows)
    assert m["answerable"]["accepted"] == 2
    assert m["answerable"]["rejected"] == 1
    assert m["answerable"]["accepted_accuracy"] == 0.5
    assert m["rejection_rate_answerable"] == 0.3333
    assert m["unanswerable"]["rejected"] == 1
    assert m["unanswerable"]["rejection_rate"] == 1.0
    assert m["false_acceptance"] == 1.0


def test_confusion_matrix_empty_bucket_rate_is_none():
    m = confusion_matrix([{"bucket": "answerable::accepted", "correct": True}])
    assert m["unanswerable"]["rejection_rate"] is None


def test_analyze_citations_valid_and_supported():
    q = _question()
    candidates = [
        _candidate("academic_regulations", "Students need 75% of total classes attendance."),
        _candidate("other_doc", "Unrelated content here."),
    ]
    result = analyze_citations("You need 75% attendance. Sources: [1]", candidates, q)
    assert result["cited_tags"] == 1
    assert result["valid_tags"] == 1
    assert result["valid_ratio"] == 1.0
    assert result["supported_tags"] == 1
    assert result["supported_ratio"] == 1.0
    assert result["documents_cited"] == ["academic_regulations"]


def test_analyze_citations_unknown_and_wrong_doc():
    q = _question()
    candidates = [
        _candidate("academic_regulations", "No attendance text here."),
    ]
    result = analyze_citations("Answer. Sources: [2]", candidates, q)
    assert result["cited_tags"] == 1
    assert result["valid_tags"] == 0
    assert result["valid_ratio"] == 0.0

    wrong = analyze_citations("Answer. Sources: [1]", candidates, q)
    assert wrong["valid_tags"] == 1  # right document...
    assert wrong["supported_tags"] == 0  # ...but text does not support ground truth


def test_analyze_citations_fallback_has_no_tags():
    q = _question()
    result = analyze_citations("I couldn't find sufficient information.", [], q)
    assert result["cited_tags"] == 0
    assert result["valid_ratio"] is None


def test_citation_recall():
    rows = [
        {"cited_tags": 2, "valid_ratio": 1.0},
        {"cited_tags": 1, "valid_ratio": 0.0},
        {"cited_tags": 0, "valid_ratio": None},
    ]
    assert citation_recall(rows) == 0.5
    assert citation_recall([{"cited_tags": 0, "valid_ratio": None}]) == 0.0
