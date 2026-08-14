"""Unit tests for failure classification (deterministic ordering)."""

from evaluation.analyze import classify_failure, failure_summary
from evaluation.dataset import Question

FALLBACK = "I couldn't find sufficient information in the available university documents."


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


class _Candidate:
    def __init__(self, text):
        self.text = text


def test_no_failure_when_answer_correct():
    q = _question()
    candidates = [_Candidate("Students need 75% attendance.")]
    assert (
        classify_failure(
            question=q,
            answer="The rule is 75% attendance.",
            candidates=candidates,
            confident=True,
            gate_applied=True,
        )
        is None
    )


def test_confidence_rejection_takes_precedence():
    q = _question()
    assert (
        classify_failure(
            question=q,
            answer=FALLBACK,
            candidates=[_Candidate("75% attendance required.")],
            confident=False,
            gate_applied=True,
        )
        == "confidence_rejection"
    )


def test_llm_error_before_retrieval_miss():
    q = _question()
    assert (
        classify_failure(
            question=q,
            answer=FALLBACK,
            candidates=[],
            confident=True,
            gate_applied=True,
            llm_error="429 RESOURCE_EXHAUSTED",
        )
        == "llm_error"
    )


def test_retrieval_miss_when_nothing_relevant():
    q = _question()
    assert (
        classify_failure(
            question=q,
            answer="Wrong.",
            candidates=[_Candidate("Unrelated content.")],
            confident=True,
            gate_applied=False,
        )
        == "retrieval_miss"
    )


def test_llm_refusal_when_evidence_present_but_fallback():
    q = _question()
    assert (
        classify_failure(
            question=q,
            answer=FALLBACK,
            candidates=[_Candidate("75% of total classes is the rule.")],
            confident=True,
            gate_applied=False,
        )
        == "llm_refusal"
    )


def test_hallucination_when_terms_unsupported():
    q = _question()
    # Wrong answer that asserts nothing supported by the evidence.
    assert (
        classify_failure(
            question=q,
            answer="The answer is 100 percent.",
            candidates=[_Candidate("Students need 75% of total classes attendance.")],
            confident=True,
            gate_applied=False,
        )
        == "hallucination"
    )


def test_failure_summary_counts():
    summary = failure_summary(["retrieval_miss", "hallucination", "retrieval_miss", None])
    assert summary["retrieval_miss"]["count"] == 2
    assert summary["retrieval_miss"]["share_of_failures"] == 0.6667
    assert summary["hallucination"]["count"] == 1