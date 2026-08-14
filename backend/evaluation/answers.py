"""Answer correctness and faithfulness scoring (deterministic rubric).

Correctness is judged against the dataset's hand-written expected answer:

- **Unanswerable questions** are correct when the system returns the grounded
  fallback answer (i.e. it refuses to guess).
- **Answerable questions** are correct when every ``expected_answer_terms``
  term appears in the normalized answer, OR numeric equivalence holds.

Faithfulness uses a conservative 0/1/2 rubric purely from the retrieved
evidence (no LLM judge in the primary run):

- **2 (fully grounded)**: every expected term is present in the answer and the
  same terms are present in the retrieved evidence.
- **1 (partially grounded)**: the answer uses only evidence-supported terms but
  omits some ground-truth facts.
- **0 (unsupported)**: the answer asserts a ground-truth term that is absent
  from the retrieved evidence (hallucinated/supported by nothing), or asserts
  no expected terms at all.

Both checks are deterministic and reproducible; any LLM-based judge would be
reported separately, never mixed into these numbers.
"""

from __future__ import annotations

import re

from app.rag.prompts import FALLBACK_ANSWER
from evaluation.dataset import normalize, Question

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_NUMERIC_WORD = re.compile(r"(\d+)")


def is_fallback(answer: str) -> bool:
    """True when the answer is the grounded fallback (normalized match)."""
    return normalize(answer) == normalize(FALLBACK_ANSWER)


def _numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text))


def answer_is_correct(question: Question, answer: str) -> bool:
    """Deterministic correctness check against the question's ground truth."""
    if not answer.strip():
        return False
    if not question.answerable:
        return is_fallback(answer)

    norm_answer = normalize(answer)
    if is_fallback(answer):
        return False

    terms = [normalize(t) for t in question.expected_answer_terms if t]
    if terms:
        if all(term in norm_answer for term in terms):
            return True
        # Numeric equivalence fallback for hard-to-tokenize numbers.
        answer_numbers = _numbers(norm_answer)
        expected_numbers = set()
        for term in terms:
            expected_numbers |= _numbers(normalize(term))
        if answer_numbers and expected_numbers and answer_numbers & expected_numbers:
            return True
    return False


def faithfulness_score(question: Question, answer: str, evidence_text: str) -> int:
    """0/1/2 deterministic faithfulness of ``answer`` against retrieved evidence."""
    if not question.answerable or not answer.strip():
        return 0
    if is_fallback(answer):
        return 0

    norm_answer = normalize(answer)
    norm_evidence = normalize(evidence_text)
    terms = [normalize(t) for t in question.expected_answer_terms if t]

    asserted = [t for t in terms if t in norm_answer]
    supported = [t for t in asserted if t in norm_evidence]

    if not asserted:
        return 0
    if len(supported) == len(asserted) and len(asserted) == len(terms):
        return 2
    if supported:
        return 1
    return 0


def faithfulness_label(score: int) -> str:
    return {0: "unsupported", 1: "partial", 2: "full"}.get(score, "unsupported")