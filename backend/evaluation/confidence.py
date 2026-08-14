"""Confidence-gate analysis for the phase5 pipeline.

Definitions (Phase 7 audit, consistent terminology):

- **Accepted**: the confidence gate allows the question to proceed to answer
  generation (top reranker relevance score >= threshold).
- **Rejected**: the gate blocks the question before generation.
- **False acceptance**: an UNANSWERABLE question is accepted by the gate.
  ``false_acceptance_rate = accepted_unanswerable / total_unanswerable``.
- **Correct rejection**: an UNANSWERABLE question is rejected by the gate.
  ``correct_rejection_rate = rejected_unanswerable / total_unanswerable``.
- **False rejection**: an ANSWERABLE question is rejected even though valid
  supporting evidence exists in the indexed evaluation corpus.
  ``false_rejection_rate = rejected_answerable_with_evidence / answerable_with_evidence``.
- **Abstention**: the gate refuses to answer a question at all:
  ``(rejected_answerable + rejected_unanswerable) / total_questions``.

Rates are rounded to 4 decimals. Any rate with a zero denominator is ``None``
(explicitly undefined) — never NaN, Infinity or a division-by-zero exception.
"""

from __future__ import annotations


def _safe_rate(numerator: int, denominator: int) -> float | None:
    """Return ``numerator / denominator`` rounded, or ``None`` when undefined."""
    return round(numerator / denominator, 4) if denominator else None


def confusion_matrix(rows: list[dict]) -> dict:
    """Aggregate per-question gate outcomes into a consistent summary.

    Each ``row`` must carry:

    - ``answerable`` (bool): question ground-truth label from the dataset.
    - ``confident`` (bool): the gate's decision (True = accepted).
    - ``correct`` (bool): answer correctness after generation.
    - ``evidence_in_corpus`` (bool): whether the question's ground-truth
      evidence exists in the indexed evaluation corpus (independent of
      retrieval — never derived from what retrieval happened to return).
    """
    total = len(rows)
    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]

    ans_accepted = [r for r in answerable if r["confident"]]
    ans_rejected = [r for r in answerable if not r["confident"]]
    unans_accepted = [r for r in unanswerable if r["confident"]]
    unans_rejected = [r for r in unanswerable if not r["confident"]]

    answerable_with_evidence = [r for r in answerable if r["evidence_in_corpus"]]
    false_rejections = [r for r in ans_rejected if r["evidence_in_corpus"]]

    accepted_accuracy = _safe_rate(
        sum(1 for r in ans_accepted if r["correct"]), len(ans_accepted)
    )

    return {
        "answerable": {
            "total": len(answerable),
            "accepted": len(ans_accepted),
            "rejected": len(ans_rejected),
            "accepted_correct": sum(1 for r in ans_accepted if r["correct"]),
            "accepted_accuracy": accepted_accuracy,
        },
        "unanswerable": {
            "total": len(unanswerable),
            "accepted": len(unans_accepted),
            "rejected": len(unans_rejected),
            "rejected_correct": sum(1 for r in unans_rejected if r["correct"]),
            # Supplementary: of the accepted unanswerable, how many ended with a
            # correct refusal after generation (separate from the gate metric).
            "accepted_correct": sum(1 for r in unans_accepted if r["correct"]),
        },
        # Gate-level metrics (per the definitions above).
        "false_acceptance_count": len(unans_accepted),
        "false_acceptance_rate": _safe_rate(len(unans_accepted), len(unanswerable)),
        "correct_rejection_count": len(unans_rejected),
        "correct_rejection_rate": _safe_rate(len(unans_rejected), len(unanswerable)),
        "false_rejection_count": len(false_rejections),
        "false_rejection_rate": _safe_rate(
            len(false_rejections), len(answerable_with_evidence)
        ),
        "answerable_with_evidence": len(answerable_with_evidence),
        "abstention_rate": _safe_rate(
            len(ans_rejected) + len(unans_rejected), total
        ),
    }