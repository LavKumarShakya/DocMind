"""Unit tests for the confidence-gate analysis and citation metrics."""

import uuid

from app.services.retrieval_types import RetrievalCandidate
from evaluation.citations import analyze_citations, citation_recall
from evaluation.confidence import confusion_matrix
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


def _row(answerable, confident, correct, evidence=True) -> dict:
    return {
        "answerable": answerable,
        "confident": confident,
        "correct": correct,
        "evidence_in_corpus": evidence,
    }


def test_confusion_matrix_counts_and_rates():
    rows = [
        _row(answerable=True, confident=True, correct=True),
        _row(answerable=True, confident=True, correct=False),
        _row(answerable=True, confident=False, correct=False),
        _row(answerable=False, confident=False, correct=False),
        _row(answerable=False, confident=True, correct=False),
    ]
    m = confusion_matrix(rows)
    assert m["answerable"]["total"] == 3
    assert m["answerable"]["accepted"] == 2
    assert m["answerable"]["rejected"] == 1
    assert m["answerable"]["accepted_accuracy"] == 0.5
    assert m["unanswerable"]["total"] == 2
    assert m["unanswerable"]["accepted"] == 1
    assert m["unanswerable"]["rejected"] == 1
    assert m["false_acceptance_count"] == 1
    assert m["false_acceptance_rate"] == 0.5
    assert m["correct_rejection_count"] == 1
    assert m["correct_rejection_rate"] == 0.5


def test_confusion_matrix_false_rejection_requires_corpus_evidence():
    m = confusion_matrix([
        _row(answerable=True, confident=False, correct=False, evidence=False),
    ])
    assert m["false_rejection_count"] == 0
    assert m["false_rejection_rate"] is None
    assert m["answerable_with_evidence"] == 0

    m = confusion_matrix([
        _row(answerable=True, confident=False, correct=False, evidence=True),
    ])
    assert m["false_rejection_count"] == 1
    assert m["false_rejection_rate"] == 1.0
    assert m["answerable_with_evidence"] == 1


def test_confusion_matrix_zero_denominators_are_none_not_nan():
    empty = confusion_matrix([])
    assert empty["false_acceptance_rate"] is None
    assert empty["correct_rejection_rate"] is None
    assert empty["false_rejection_rate"] is None
    assert empty["abstention_rate"] is None

    no_unanswerable = confusion_matrix([
        _row(answerable=True, confident=True, correct=True),
    ])
    assert no_unanswerable["false_acceptance_rate"] is None
    assert no_unanswerable["correct_rejection_rate"] is None

    no_answerable = confusion_matrix([
        _row(answerable=False, confident=False, correct=False),
    ])
    assert no_answerable["false_rejection_rate"] is None
    assert no_answerable["answerable_with_evidence"] == 0


def test_confusion_matrix_phase5_scale_false_acceptance():
    rows = (
        [_row(answerable=False, confident=False, correct=False) for _ in range(7)]
        + [_row(answerable=False, confident=True, correct=False) for _ in range(6)]
        + [_row(answerable=True, confident=True, correct=False) for _ in range(38)]
        + [_row(answerable=True, confident=False, correct=False) for _ in range(5)]
    )
    m = confusion_matrix(rows)
    assert m["false_acceptance_count"] == 6
    assert m["false_acceptance_rate"] == round(6 / 13, 4)
    assert m["correct_rejection_count"] == 7
    assert m["correct_rejection_rate"] == round(7 / 13, 4)
    assert m["abstention_rate"] == round((5 + 7) / 56, 4)


def test_confusion_matrix_no_false_acceptance_when_all_rejected():
    rows = [_row(answerable=False, confident=False, correct=False) for _ in range(13)]
    m = confusion_matrix(rows)
    assert m["false_acceptance_count"] == 0
    assert m["false_acceptance_rate"] == 0.0
    assert m["correct_rejection_count"] == 13
    assert m["correct_rejection_rate"] == 1.0


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
