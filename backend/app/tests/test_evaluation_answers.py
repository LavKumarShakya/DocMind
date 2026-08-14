"""Unit tests for answer correctness and the deterministic faithfulness rubric."""

from evaluation.answers import (
    answer_is_correct,
    faithfulness_label,
    faithfulness_score,
    is_fallback,
)
from evaluation.dataset import Question

FALLBACK = "I couldn't find sufficient information in the available university documents."


def _question(**overrides) -> Question:
    base = {
        "id": "Q1",
        "question": "question?",
        "expected_answer": "75 percent attendance",
        "expected_answer_terms": ["75", "attendance"],
        "relevant_documents": ["academic_regulations"],
        "relevant_pages": [1],
        "supporting_text": ["75% of total classes"],
        "category": "numeric",
        "difficulty": "easy",
        "answerable": True,
    }
    base.update(overrides)
    return Question(base)


def test_correct_answer_matches_all_terms():
    q = _question()
    assert answer_is_correct(q, "You need 75% attendance.")
    assert not answer_is_correct(q, "Attendance is required.")
    assert not answer_is_correct(q, FALLBACK)


def test_fallback_answer_is_wrong_for_answerable():
    assert answer_is_correct(_question(), FALLBACK) is False


def test_unanswerable_question_is_correct_only_when_refusing():
    q = _question(answerable=False, expected_answer=None, expected_answer_terms=[])
    assert answer_is_correct(q, FALLBACK) is True
    assert answer_is_correct(q, "The CEO is someone.") is False
    assert answer_is_correct(q, "") is False


def test_numeric_equivalence_fallback():
    q = _question(expected_answer_terms=["75%"])
    assert answer_is_correct(q, "The requirement is 75% of classes.") is True


def test_is_fallback_normalized():
    assert is_fallback(FALLBACK) is True
    assert is_fallback("Based on the top document match: something") is False


def test_faithfulness_full_partial_unsupported():
    q = _question()
    evidence = "Students must maintain 75% attendance to sit the examination."
    assert faithfulness_score(q, "Students need 75% attendance.", evidence) == 2
    assert faithfulness_score(q, "Students need 75% attendance.", "Completely unrelated evidence text.") == 0
    assert faithfulness_score(q, "The attendance rule is described in the regulations.", evidence) == 1
    assert faithfulness_score(q, FALLBACK, evidence) == 0


def test_faithfulness_label():
    assert faithfulness_label(2) == "full"
    assert faithfulness_label(1) == "partial"
    assert faithfulness_label(0) == "unsupported"
