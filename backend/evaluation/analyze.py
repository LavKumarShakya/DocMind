"""Failure classification for answerable questions.

Every answerable question gets exactly one primary failure label when its
answer is not correct (``None`` when correct). Classification is deterministic
and ordered:

1. **confidence_rejection** — the phase5 gate refused an answerable question
   (LLM never ran).
2. **retrieval_miss** — no relevant chunk was retrieved at all.
3. **llm_refusal** — evidence was retrieved but the answer is the fallback
   (baseline mode has no gate; the LLM still could not find the answer).
4. **hallucination** — the answer asserts ground-truth terms that are not
   present in the retrieved evidence (faithfulness 0).
5. **wrong_answer** — the answer is wrong but grounded in the retrieved
   evidence (faithfulness > 0).
"""

from __future__ import annotations

from evaluation.answers import is_fallback


def classify_failure(
    *,
    question,
    answer: str,
    candidates: list,
    confident,
    gate_applied: bool,
    llm_error: str | None = None,
) -> str | None:
    if question.answerable and not _answer_correct(question, answer):
        if gate_applied and not confident:
            return "confidence_rejection"
        if llm_error is not None:
            return "llm_error"
        if not _any_relevant(candidates, question):
            return "retrieval_miss"
        if is_fallback(answer):
            return "llm_refusal"
        if _hallucinated(question, answer, candidates):
            return "hallucination"
        return "wrong_answer"
    return None


def _answer_correct(question, answer: str) -> bool:
    from evaluation.answers import answer_is_correct

    return answer_is_correct(question, answer)


def _any_relevant(candidates: list, question) -> bool:
    from evaluation.dataset import chunk_is_relevant

    return any(chunk_is_relevant(c.text, question.supporting_text) for c in candidates)


def _hallucinated(question, answer: str, candidates: list) -> bool:
    from evaluation.answers import faithfulness_score

    evidence = "\n\n".join(c.text for c in candidates)
    return faithfulness_score(question, answer, evidence) == 0


def failure_summary(failures: list[str | None]) -> dict:
    """Count failure labels across a run."""
    counts: dict[str, int] = {}
    for label in failures:
        if label is not None:
            counts[label] = counts.get(label, 0) + 1
    total = max(1, len([f for f in failures if f is not None]))
    return {
        label: {"count": count, "share_of_failures": round(count / total, 4)}
        for label, count in sorted(counts.items())
    }