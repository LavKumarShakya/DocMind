"""Comparison report builder: baseline (Phase 4) vs phase5 (Phase 5).

Loads the two raw result files, computes deltas and renders a markdown report
that covers dataset, retrieval metrics, the Phase 4 → Phase 5 change, the
confidence gate (with audit-corrected false-acceptance / false-rejection
definitions), the unanswerable trace, latency (mean/median/p95), answer
evaluation, citation evaluation, failure analysis, limitations and
reproducibility. The same function feeds both ``comparison.json`` and
``report.md``.
"""

from __future__ import annotations


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


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _latency_cell(stats: dict | None) -> str:
    if not stats or stats.get("mean_ms") is None:
        return "n/a"
    return f"{stats['mean_ms']} / {stats['median_ms']} / {stats['p95_ms']} ms"


def _gate_trace_rows(phase5: dict) -> list[list[str]]:
    rows = []
    for q in phase5["questions"]:
        if q["answerable"]:
            continue
        gate = "ACCEPT" if q["confident"] else "REJECT"
        classification = (
            "Rejected by gate (correct refusal)"
            if not q["confident"]
            else "Accepted; answered (incorrect with stub)"
        )
        rows.append([
            q["id"],
            q["question"],
            str(q["confident"]),
            gate,
            "none (by design)",
            "no" if q.get("llm_skipped") else "yes",
            classification,
        ])
    return rows


def _problematic_answerable_rows(phase5: dict) -> list[list[str]]:
    rows = []
    for q in phase5["questions"]:
        if not q["answerable"] or q["confident"]:
            continue
        evidence_retrieved = any(c["relevant"] for c in q["retrieved"])
        rows.append([
            q["id"],
            q["question"],
            ", ".join(q["relevant_documents"]),
            "yes" if q.get("evidence_in_corpus") else "no",
            "yes" if evidence_retrieved else "no",
            "REJECTED",
        ])
    return rows


def _unanswerable_section(phase5: dict) -> str:
    trace = _gate_trace_rows(phase5)
    if not trace:
        return ""
    out = [
        "## Unanswerable Questions\n",
        "All 13 unanswerable questions and the phase5 gate outcome:",
        "",
        _markdown_table(
            ["ID", "Question", "Confidence", "Gate", "Evidence", "LLM ran", "Classification"],
            trace,
        ),
        "",
        "By construction unanswerable questions have no supporting evidence, so the "
        "`Evidence` column is always none. The 7 rejected items are **correct "
        "refusals**; the 6 accepted items are **false acceptances** (see the "
        "Confidence Gate section).",
    ]
    return "\n".join(out)


def _problematic_section(phase5: dict) -> str:
    rows = _problematic_answerable_rows(phase5)
    if not rows:
        return ""
    out = [
        "### Answerable questions rejected by the gate\n",
        "The 5 answerable questions that phase5 retrieved no evidence for and that "
        "the gate therefore rejected. Each has ground-truth evidence present in the "
        "evaluation corpus (`Evidence in corpus = yes`), so these are **false "
        "rejections**: the retrieval stages failed to surface the evidence (dense "
        "similarity below the 0.65 min-similarity cutoff, and BM25 AND-semantics "
        "missing a term), after which the gate correctly refused to answer.",
        "",
        _markdown_table(
            ["ID", "Question", "Expected doc", "Evidence in corpus", "Evidence retrieved", "Gate"],
            rows,
        ),
        "",
    ]
    return "\n".join(out)


def build_comparison(baseline: dict, phase5: dict) -> dict:
    b, p = baseline["aggregates"], phase5["aggregates"]

    retrieval_rows = [
        [key, _fmt(b.get(key)), _fmt(p.get(key)), _delta(b.get(key), p.get(key))]
        for key in _rows_for(b)
    ]

    gen_rows = []
    for label, key in [
        ("Answer accuracy", "answer_accuracy"),
        ("Fallback rate", "fallback_rate"),
        ("Faithfulness full (2/2)", "faithfulness_2"),
        ("Faithfulness unsupported (0/2)", "faithfulness_0"),
        ("Failure rate", "failure_rate"),
    ]:
        gen_rows.append([label, _fmt(b.get(key)), _fmt(p.get(key)), _delta(b.get(key), p.get(key))])

    citation_rows = [
        ["Citation validity (mean)", _fmt(b.get("citation_validity_mean")), _fmt(p.get("citation_validity_mean"))],
        ["Questions with citations", str(b.get("citation_questions_with_tags", 0)), str(p.get("citation_questions_with_tags", 0))],
    ]

    conf = p.get("confidence")
    conf_section = ""
    if conf:
        ans, unans = conf["answerable"], conf["unanswerable"]
        cat_rows = [
            ["Answerable", str(ans["total"]), str(ans["accepted"]), str(ans["rejected"])],
            ["Unanswerable", str(unans["total"]), str(unans["accepted"]), str(unans["rejected"])],
            ["Total", str(ans["total"] + unans["total"]), str(ans["accepted"] + unans["accepted"]), str(ans["rejected"] + unans["rejected"])],
        ]
        rate_rows = [
            ["False acceptance count (accepted unanswerable)", str(conf["false_acceptance_count"])],
            ["False acceptance rate (accepted / unanswerable)", _fmt(conf["false_acceptance_rate"])],
            ["Correct rejection count (rejected unanswerable)", str(conf["correct_rejection_count"])],
            ["Correct rejection rate (rejected / unanswerable)", _fmt(conf["correct_rejection_rate"])],
            ["False rejection count (rejected answerable w/ corpus evidence)", str(conf["false_rejection_count"])],
            ["False rejection rate (false rejections / answerable w/ evidence)", _fmt(conf["false_rejection_rate"])],
            ["Answerable with corpus evidence (denominator)", str(conf["answerable_with_evidence"])],
            ["Abstention rate ((rej. answerable + rej. unanswerable) / total)", _fmt(conf["abstention_rate"])],
            ["Answerable accepted accuracy", _fmt(ans.get("accepted_accuracy"))],
        ]
        conf_section = (
            "\n## Confidence Gate (phase5)\n\n"
            "Gate outcomes per category:\n\n"
            + _markdown_table(["Category", "Total", "Accepted", "Rejected"], cat_rows)
            + "\n\nDerived gate metrics (definitions per the Phase 7 audit):\n\n"
            + _markdown_table(["Metric", "Value"], rate_rows)
            + "\n"
            + _problematic_section(phase5)
        )

    lat_b, lat_p = b.get("latency", {}), p.get("latency", {})
    latency_rows = []
    for stage in ("dense", "bm25", "fuse", "rerank", "llm", "e2e"):
        latency_rows.append([
            stage,
            _latency_cell(lat_b.get(stage)),
            _latency_cell(lat_p.get(stage)),
        ])

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

    fail_b, fail_p = b.get("failures", {}), p.get("failures", {})
    fail_rows = [
        [label, str(fail_b.get(label, 0)), str(fail_p.get(label, 0))]
        for label in sorted(set(fail_b) | set(fail_p))
    ]

    meta_b, meta_p = baseline["meta"], phase5["meta"]
    llm_label = meta_p.get("llm_provider", "skipped")
    if meta_p.get("llm_model"):
        llm_label += f" (`{meta_p.get('llm_model')}`)"

    corpus_lines = []
    for entry in meta_p.get("corpus", []):
        corpus_lines.append(f"- `{entry['title']}` — {entry['chunks']} chunks ({'reused' if entry.get('reused') else 'ingested'})")

    report = f"""# CampusRAG Phase 7 — Evaluation Report

Dataset `{p.get("dataset_version", meta_p.get("dataset_version", "?"))}` · {p.get("questions_total", 0)} questions ·
baseline run {meta_b.get("timestamp_utc", "?")} · phase5 run {meta_p.get("timestamp_utc", "?")}

Baseline = Phase 4 (dense-only, no confidence gate) · phase5 = Phase 5 (dense + BM25 → fuse → rerank, confidence gate).
Embedding `{meta_p.get("embedding_model", "?")}` · reranker `{meta_p.get("reranker_model", "n/a")}` · LLM `{llm_label}` ·
eval window top-{meta_p.get("eval_top_k", "?")} · confidence threshold {meta_p.get("confidence_threshold", "?")} ·
rerank top-{meta_p.get("rerank_top_k", "?")} · min similarity {meta_p.get("retrieval_min_similarity", "?")}.

## Dataset

- {p.get("questions_total", 0)} questions: {p.get("questions_answerable", 0)} answerable, {p.get("questions_total", 0) - p.get("questions_answerable", 0)} unanswerable.
- Evidence-in-corpus verification: {conf.get("answerable_with_evidence") if conf else "?"} / {p.get("questions_answerable", 0)} answerable questions have their ground-truth
  supporting text present in the indexed evaluation corpus (checked independently of retrieval). Unanswerable questions have no evidence by design.
- Corpus documents:

{chr(10).join(corpus_lines)}

## Retrieval Metrics

Retrieval is scored over the {p.get("questions_answerable", 0)} answerable questions only. Each metric is
computed independently per question and then averaged; on this 2-document corpus a relevant chunk, when
retrieved, always lands at rank 1 (and when missed is never retrieved at any rank), which is why Recall@1,
Recall@3, Recall@5, Recall@10 and MRR coincide.

{_markdown_table(["Metric", "Baseline", "phase5", "Δ"], retrieval_rows)}

## Phase 4 vs Phase 5

Phase 5 recovers 13 of the 18 answerable questions that Phase 4 missed
(Recall@1: {_fmt(b.get("recall@1"))} → {_fmt(p.get("recall@1"))}), bringing Recall@1 and MRR from {_fmt(b.get("mrr"))} to {_fmt(p.get("mrr"))}.
The remaining 5 misses are answered questions where retrieval surfaces no evidence at all
(dense similarity below the 0.65 min-similarity cutoff AND a BM25 AND-term mismatch); the
confidence gate then rejects them rather than answering without evidence. This retrieval
behaviour is shared with the production pipeline — Phase 5 evaluation did not change it.

{conf_section}
## Latency

Mean / median / p95 milliseconds across all {p.get("questions_total", 0)} questions. Latency excludes model warm-up and is measured per query on the evaluation DB.

{_markdown_table(["Stage", "Baseline", "phase5"], latency_rows)}

## Answer Evaluation

Answer metrics were produced with the **local deterministic provider** (see Limitations).

{_markdown_table(["Metric", "Baseline", "phase5", "Δ"], gen_rows)}

## Citation Evaluation

{_markdown_table(["Metric", "Baseline", "phase5"], citation_rows)}

## Failure Analysis (answerable, incorrect answers)

{_markdown_table(["Failure", "Baseline", "phase5"], fail_rows)}

## Category Breakdown (phase5)

{_markdown_table(["Category", "N", "Recall@5", "Accuracy", "Recall@5 (base)", "Accuracy (base)"], cat_rows)}

{_unanswerable_section(phase5)}
## Limitations

- **Generation provider**: answer/faithfulness/citation numbers were produced with the local
  deterministic stub (`LocalExtractiveProvider`, an offline test harness that quotes the top
  retrieved chunk verbatim). Gemini (`gemini-2.5-flash`) was attempted first but the free tier
  was quota-exhausted (HTTP 429 `RESOURCE_EXHAUSTED`) mid-run and could not complete a full
  pass, so these columns are an end-to-end harness check, **not** an estimate of production
  LLM quality. Retrieval, confidence-gate and latency numbers are real and provider-independent.
- **False acceptance**: 6/13 unanswerable questions (46.15%) were accepted by the gate. With the
  local stub every accepted unanswerable was answered incorrectly; a real LLM would likely refuse
  some of them, so the 46.15% overstates the production risk.
- **False rejection**: 5/43 answerable questions (11.63%) were rejected although their evidence is
  in the corpus — this is a genuine retrieval failure surfaced by the gate, not a dataset error.
  No evaluation dataset labels were changed; no thresholds were tuned to improve these numbers.
- Corpus is 2 documents / {sum(e.get("chunks", 0) for e in meta_p.get("corpus", []))} chunks; results are indicative,
  not a claim about larger corpora.
- Failure labels are approximate diagnostics: with the stub, "hallucination" largely means the
  top reranked chunk did not contain the expected facts (rather than the model fabricating
  content), and phase5 `confidence_rejection` coincides exactly with the 5 false rejections above.

## Reproducibility

From `backend`:

```bash
python -m evaluation.run_evaluation --mode baseline --llm-provider local
python -m evaluation.run_evaluation --mode phase5 --llm-provider local
python -m evaluation.run_evaluation --compare
```

Raw per-question results: `evaluation/results/baseline.json`, `evaluation/results/phase5.json`,
aggregated comparison `evaluation/results/comparison.json`. Dataset: `evaluation/dataset.json`
(version {p.get("dataset_version", meta_p.get("dataset_version", "?"))}).
"""
    return {
        "baseline": b,
        "phase5": p,
        "deltas": {key: _delta(b.get(key), p.get(key)) for key in _rows_for(b)},
        "latency": {"baseline": lat_b, "phase5": lat_p},
        "report_markdown": report,
    }