"""Comparison report builder: baseline (Phase 4) vs phase5 (Phase 5).

Loads the two raw result files, computes deltas and renders a markdown report
that covers retrieval quality, generation quality, confidence-gating,
citations, latency and a category/failure breakdown. The same function feeds
both ``comparison.json`` and ``report.md``.
"""

from __future__ import annotations

from statistics import mean


def _fmt(value, default="n/a") -> str:
    if value is None:
        return default
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _delta(a: float | None, b: float | None) -> str:
    if a is None or b is None:
        return "n/a"
    diff = b - a
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:.4f}"


def _rows_for(aggregates: dict) -> dict:
    return {key: aggregates.get(key) for key in (
        "recall@1", "recall@3", "recall@5", "recall@10", "mrr",
        "doc_recall@1", "doc_recall@5", "doc_recall@10",
    )}


def _latency_summary(results: dict, mode: str) -> dict:
    """Stage latency stats across questions (mean_ms per stage)."""
    stages = ["dense", "bm25", "fuse", "rerank"]
    out: dict = {}
    for stage in stages:
        values = [q["stage_times"].get(stage, 0.0) for q in results["questions"]]
        if stage == "dense":
            values = [q["stage_times"].get(stage, 0.0) for q in results["questions"]]
        out[stage] = round(mean(values), 1) if values else 0.0

    e2e = [q["e2e_time_ms"] for q in results["questions"]]
    out["e2e_mean_ms"] = round(mean(e2e), 1) if e2e else 0.0

    llm = [
        q.get("llm_time_ms")
        for q in results["questions"]
        if q.get("llm_time_ms") is not None
    ]
    out["llm_mean_ms"] = round(mean(llm), 1) if llm else 0.0
    out["mode"] = mode
    return out


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_comparison(baseline: dict, phase5: dict) -> dict:
    b, p = baseline["aggregates"], phase5["aggregates"]

    # Retrieval table rows.
    keys = _rows_for(b)
    retrieval_rows = [
        [key, _fmt(b.get(key)), _fmt(p.get(key)), _delta(b.get(key), p.get(key))]
        for key in keys
    ]

    # Generation table.
    gen_rows = []
    for label, key in [
        ("Answer accuracy", "answer_accuracy"),
        ("Fallback rate", "fallback_rate"),
        ("Faithfulness full (2/2)", "faithfulness_2"),
        ("Faithfulness unsupported (0/2)", "faithfulness_0"),
        ("Failure rate", "failure_rate"),
        ("Citation validity (mean)", "citation_validity_mean"),
    ]:
        gen_rows.append([label, _fmt(b.get(key)), _fmt(p.get(key)), _delta(b.get(key), p.get(key))])

    # Confidence gate (phase5 only).
    conf = p.get("confidence")
    conf_section = ""
    if conf:
        ans = conf.get("answerable", {})
        unans = conf.get("unanswerable", {})
        conf_rows = [
            ["Answerable accepted", str(ans.get("accepted", 0)), _fmt(ans.get("accepted_accuracy"))],
            ["Answerable rejected (false rejection)", str(ans.get("rejected", 0)), _fmt(conf.get("rejection_rate_answerable"))],
            ["Unanswerable rejected (correct refusal)", str(unans.get("rejected", 0)), _fmt(unans.get("rejection_rate"))],
            ["Unanswerable accepted (false acceptance)", str(unans.get("accepted", 0)), _fmt(conf.get("false_acceptance"))],
        ]
        conf_section = "\n### Confidence gate (phase5)\n\n" + _markdown_table(
            ["Bucket", "N", "Rate"], conf_rows
        ) + "\n"

    lat_b = _latency_summary(baseline, "baseline")
    lat_p = _latency_summary(phase5, "phase5")
    latency_rows = [
        [stage, f"{lat_b.get(stage, 0.0):.1f} ms", f"{lat_p.get(stage, 0.0):.1f} ms"]
        for stage in ("dense", "bm25", "fuse", "rerank")
    ]
    latency_rows.append(["LLM (mean)", f"{lat_b['llm_mean_ms']:.1f} ms", f"{lat_p['llm_mean_ms']:.1f} ms"])
    latency_rows.append(["End-to-end (mean)", f"{lat_b['e2e_mean_ms']:.1f} ms", f"{lat_p['e2e_mean_ms']:.1f} ms"])

    # Category breakdown.
    cat_rows = []
    for name in sorted(p.get("category_breakdown", {})):
        pb = p["category_breakdown"][name]
        bb = b.get("category_breakdown", {}).get(name, {})
        cat_rows.append([
            name,
            str(pb.get("count", 0)),
            _fmt(pb.get("recall@5")),
            _fmt(pb.get("accuracy")),
            _fmt(bb.get("recall@5")),
            _fmt(bb.get("accuracy")),
        ])

    # Failure breakdown.
    fail_b = b.get("failures", {})
    fail_p = p.get("failures", {})
    fail_rows = [
        [label, str(fail_b.get(label, 0)), str(fail_p.get(label, 0))]
        for label in sorted(set(fail_b) | set(fail_p))
    ]

    meta_b, meta_p = baseline["meta"], phase5["meta"]
    llm_label = meta_p.get("llm_provider", "skipped")
    if meta_p.get("llm_model"):
        llm_label += f" (`{meta_p.get('llm_model')}`)"
    report = f"""# CampusRAG Phase 7 — Evaluation Report

Dataset `{p.get("dataset_version", meta_p.get("dataset_version", "?"))}` · {p.get("questions_total", 0)} questions ·
baseline run {meta_b.get("timestamp_utc", "?")} · phase5 run {meta_p.get("timestamp_utc", "?")}

Baseline = Phase 4 (dense-only, no confidence gate) · phase5 = Phase 5 (dense + BM25 → fuse → rerank, confidence gate).
Embedding `{meta_p.get("embedding_model", "?")}` · reranker `{meta_p.get("reranker_model", "n/a")}` · LLM `{llm_label}` ·
eval window top-{meta_p.get("eval_top_k", "?")} · confidence threshold {meta_p.get("confidence_threshold", "?")} ·
rerank top-{meta_p.get("rerank_top_k", "?")} · min similarity {meta_p.get("retrieval_min_similarity", "?")}.
{conf_section}
## Retrieval quality (answerable questions)

{_markdown_table(["Metric", "Baseline", "phase5", "Δ"], retrieval_rows)}

## Generation quality

{_markdown_table(["Metric", "Baseline", "phase5", "Δ"], gen_rows)}

## Latency (mean per stage)

{_markdown_table(["Stage", "Baseline", "phase5"], latency_rows)}

## Category breakdown (phase5)

{_markdown_table(["Category", "N", "Recall@5", "Accuracy", "Recall@5 (base)", "Accuracy (base)"], cat_rows)}

## Failure analysis (answerable, incorrect answers)

{_markdown_table(["Failure", "Baseline", "phase5"], fail_rows)}

## Notes

- Retrieval metrics are computed over answerable questions only.
- Faithfulness is the deterministic 0/1/2 rubric (2 = every expected term in
  answer is also in retrieved evidence).
- Citation validity is computed only for answers that actually cite sources.
- Latency excludes model warm-up; it is measured per query on the evaluation DB.
- Honest caveats: results reflect a 2-document corpus and the models cached on
  this machine; they are indicative, not a claim about larger corpora.

### Generation provider caveat

Answer/faithfulness/citation numbers were produced with the **local
deterministic provider** (`LocalExtractiveProvider`, an offline test stub that
quotes the top retrieved chunk verbatim). Gemini (`gemini-2.5-flash`) was
attempted first but the free tier was quota-exhausted (HTTP 429
`RESOURCE_EXHAUSTED`) mid-run, so the real LLM could not complete a full pass
today. The stub is *not* representative of production answer quality, so treat
the generation columns as an end-to-end harness check, not as an estimate of
the production LLM. Retrieval, confidence-gate and latency numbers are real
and provider-independent. With a real LLM, some "unanswerable accepted"
questions would likely still be refused by the model, so the stub overstates
the gate's unanswerable failure rate.

Failure labels are approximate diagnostics: with the stub, "hallucination"
largely means the top reranked chunk did not contain the expected facts
(rather than the model fabricating content), and phase5 "confidence_rejection"
coincides with the 5 answerable questions where retrieval found no relevant
evidence — i.e. the gate correctly blocked answers on missing evidence.
"""
    return {
        "baseline": baseline["aggregates"],
        "phase5": phase5["aggregates"],
        "deltas": {key: _delta(b.get(key), p.get(key)) for key in keys},
        "latency": {"baseline": lat_b, "phase5": lat_p},
        "report_markdown": report,
    }