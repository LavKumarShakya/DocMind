"""Confidence-gate analysis for the phase5 pipeline.

The retrieval confidence gate (``app.rag.confidence.is_confident``) decides
whether the LLM is called. For evaluation we classify each question into one of
four buckets:

- **answerable / accepted**: gate passed, LLM ran (hopefully answered).
- **answerable / rejected**: gate refused → fallback → a correct answer is lost.
- **unanswerable / rejected**: correct refusal.
- **unanswerable / accepted**: gate passed → LLM ran on a question with no
  answerable evidence; correct only if it still refuses.

The 2x2 matrix drives the false-acceptance / false-rejection analysis.
"""

from __future__ import annotations

from evaluation.dataset import Question


def classify(question: Question, confident: bool) -> str:
    """Return one of the four gate-bucket labels for a question."""
    return f"{'answerable' if question.answerable else 'unanswerable'}::{'accepted' if confident else 'rejected'}"


def confusion_matrix(rows: list[dict]) -> dict:
    """Aggregate per-question ``{bucket, correct}`` rows into a 2x2 summary.

    ``rows`` entries carry ``bucket`` (from :func:`classify`) and ``correct``.
    """
    buckets = {
        "answerable::accepted": 0,
        "answerable::rejected": 0,
        "unanswerable::accepted": 0,
        "unanswerable::rejected": 0,
    }
    correct_by_bucket = dict(buckets)

    for row in rows:
        bucket = row["bucket"]
        if bucket not in buckets:
            continue
        buckets[bucket] += 1
        if row["correct"]:
            correct_by_bucket[bucket] += 1

    def rate(bucket: str) -> float:
        return round(correct_by_bucket[bucket] / buckets[bucket], 4) if buckets[bucket] else None

    return {
        "answerable": {
            "accepted": buckets["answerable::accepted"],
            "rejected": buckets["answerable::rejected"],
            "accepted_correct": correct_by_bucket["answerable::accepted"],
            "accepted_accuracy": rate("answerable::accepted"),
        },
        "unanswerable": {
            "accepted": buckets["unanswerable::accepted"],
            "rejected": buckets["unanswerable::rejected"],
            "rejected_correct": correct_by_bucket["unanswerable::rejected"],
            "rejection_rate": rate("unanswerable::rejected"),
        },
        "rejection_rate_answerable": (
            round(buckets["answerable::rejected"] / max(1, buckets["answerable::accepted"] + buckets["answerable::rejected"]), 4)
        ),
        "false_acceptance": (
            round(correct_by_bucket["unanswerable::accepted"] / buckets["unanswerable::accepted"], 4)
            if buckets["unanswerable::accepted"]
            else None
        ),
    }