# CampusRAG Phase 7 — Evaluation Report

Dataset `1.0` · 56 questions ·
baseline run 2026-08-14T06:58:51.218286+00:00 · phase5 run 2026-08-14T06:59:17.457269+00:00

Baseline = Phase 4 (dense-only, no confidence gate) · phase5 = Phase 5 (dense + BM25 → fuse → rerank, confidence gate).
Embedding `BAAI/bge-base-en-v1.5` · reranker `cross-encoder/ms-marco-MiniLM-L-6-v2` · LLM `local` ·
eval window top-10 · confidence threshold 0.35 ·
rerank top-10 · min similarity 0.65.

## Dataset

- 56 questions: 43 answerable, 13 unanswerable.
- Evidence-in-corpus verification: 43 / 43 answerable questions have their ground-truth
  supporting text present in the indexed evaluation corpus (checked independently of retrieval). Unanswerable questions have no evidence by design.
- Corpus documents:

- `academic_regulations` — 2 chunks (reused)
- `RAG_Test_Document_Edge_Cases` — 9 chunks (reused)

## Retrieval Metrics

Retrieval is scored over the 43 answerable questions only. Each metric is
computed independently per question and then averaged; on this 2-document corpus a relevant chunk, when
retrieved, always lands at rank 1 (and when missed is never retrieved at any rank), which is why Recall@1,
Recall@3, Recall@5, Recall@10 and MRR coincide.

| Metric | Baseline | phase5 | Δ |
| --- | --- | --- | --- |
| recall@1 | 0.5814 | 0.8837 | +0.3023 |
| recall@3 | 0.5814 | 0.8837 | +0.3023 |
| recall@5 | 0.5814 | 0.8837 | +0.3023 |
| recall@10 | 0.5814 | 0.8837 | +0.3023 |
| mrr | 0.5814 | 0.8837 | +0.3023 |
| doc_recall@1 | 0.5814 | 0.8837 | +0.3023 |
| doc_recall@5 | 0.5814 | 0.8837 | +0.3023 |
| doc_recall@10 | 0.5814 | 0.8837 | +0.3023 |

## Phase 4 vs Phase 5

Phase 5 recovers 13 of the 18 answerable questions that Phase 4 missed
(Recall@1: 0.5814 → 0.8837), bringing Recall@1 and MRR from 0.5814 to 0.8837.
The remaining 5 misses are answered questions where retrieval surfaces no evidence at all
(dense similarity below the 0.65 min-similarity cutoff AND a BM25 AND-term mismatch); the
confidence gate then rejects them rather than answering without evidence. This retrieval
behaviour is shared with the production pipeline — Phase 5 evaluation did not change it.


## Confidence Gate (phase5)

Gate outcomes per category:

| Category | Total | Accepted | Rejected |
| --- | --- | --- | --- |
| Answerable | 43 | 38 | 5 |
| Unanswerable | 13 | 6 | 7 |
| Total | 56 | 44 | 12 |

Derived gate metrics (definitions per the Phase 7 audit):

| Metric | Value |
| --- | --- |
| False acceptance count (accepted unanswerable) | 6 |
| False acceptance rate (accepted / unanswerable) | 0.4615 |
| Correct rejection count (rejected unanswerable) | 7 |
| Correct rejection rate (rejected / unanswerable) | 0.5385 |
| False rejection count (rejected answerable w/ corpus evidence) | 5 |
| False rejection rate (false rejections / answerable w/ evidence) | 0.1163 |
| Answerable with corpus evidence (denominator) | 43 |
| Abstention rate ((rej. answerable + rej. unanswerable) / total) | 0.2143 |
| Answerable accepted accuracy | 0.4474 |
### Answerable questions rejected by the gate

The 5 answerable questions that phase5 retrieved no evidence for and that the gate therefore rejected. Each has ground-truth evidence present in the evaluation corpus (`Evidence in corpus = yes`), so these are **false rejections**: the retrieval stages failed to surface the evidence (dense similarity below the 0.65 min-similarity cutoff, and BM25 AND-semantics missing a term), after which the gate correctly refused to answer.

| ID | Question | Expected doc | Evidence in corpus | Evidence retrieved | Gate |
| --- | --- | --- | --- | --- | --- |
| Q004 | What grade is worth 9 points? | academic_regulations | yes | no | REJECTED |
| Q016 | After how long of inactivity does a session time out? | RAG_Test_Document_Edge_Cases | yes | no | REJECTED |
| Q024 | When did the first production pilot begin? | RAG_Test_Document_Edge_Cases | yes | no | REJECTED |
| Q030 | Are API keys allowed to be committed to public repositories? | RAG_Test_Document_Edge_Cases | yes | no | REJECTED |
| Q042 | What are the names of the three locations the team works from? | RAG_Test_Document_Edge_Cases | yes | no | REJECTED |

## Latency

Mean / median / p95 milliseconds across all 56 questions. Latency excludes model warm-up and is measured per query on the evaluation DB.

| Stage | Baseline | phase5 |
| --- | --- | --- |
| dense | 73.4 / 71.4 / 83.7 ms | 70.3 / 70.4 / 73.4 ms |
| bm25 | n/a | 2.3 / 2.2 / 3.1 ms |
| fuse | n/a | 0.0 / 0.0 / 0.0 ms |
| rerank | n/a | 56.4 / 49.1 / 140.2 ms |
| llm | 0.0 / 0.0 / 0.0 ms | 0.0 / 0.0 / 0.0 ms |
| e2e | 73.5 / 71.6 / 83.8 ms | 120.1 / 101.4 / 207.1 ms |

## Answer Evaluation

Answer metrics were produced with the **local deterministic provider** (see Limitations).

| Metric | Baseline | phase5 | Δ |
| --- | --- | --- | --- |
| Answer accuracy | 0.3929 | 0.4286 | +0.0357 |
| Fallback rate | 0.4821 | 0.2143 | -0.2678 |
| Faithfulness full (2/2) | 0.1964 | 0.2857 | +0.0893 |
| Faithfulness unsupported (0/2) | 0.6786 | 0.6250 | -0.0536 |
| Failure rate | 0.5357 | 0.4643 | -0.0714 |

## Citation Evaluation

| Metric | Baseline | phase5 |
| --- | --- | --- |
| Citation validity (mean) | n/a | n/a |
| Questions with citations | 0 | 0 |

## Failure Analysis (answerable, incorrect answers)

| Failure | Baseline | phase5 |
| --- | --- | --- |
| confidence_rejection | 0 | 5 |
| hallucination | 6 | 16 |
| retrieval_miss | 18 | 0 |
| wrong_answer | 6 | 5 |

## Category Breakdown (phase5)

| Category | N | Recall@5 | Accuracy | Recall@5 (base) | Accuracy (base) |
| --- | --- | --- | --- | --- | --- |
| edge | 5 | 1.0000 | 0.4000 | 1.0000 | 0.2000 |
| entity | 8 | 0.8750 | 0.3750 | 0.3750 | 0.1250 |
| keyword | 6 | 0.8333 | 0.5000 | 0.6667 | 0.6667 |
| numeric | 21 | 0.8571 | 0.3810 | 0.5238 | 0.2857 |
| semantic | 3 | 1.0000 | 0.3333 | 0.6667 | 0.3333 |
| unanswerable | 13 | 0.0000 | 0.5385 | 0.0000 | 0.6923 |

## Unanswerable Questions

All 13 unanswerable questions and the phase5 gate outcome:

| ID | Question | Confidence | Gate | Evidence | LLM ran | Classification |
| --- | --- | --- | --- | --- | --- | --- |
| Q044 | What is the CEO's name? | False | REJECT | none (by design) | no | Rejected by gate (correct refusal) |
| Q045 | What is the PostgreSQL database password? | True | ACCEPT | none (by design) | yes | Accepted; answered (incorrect with stub) |
| Q046 | What is the embedding API key? | True | ACCEPT | none (by design) | yes | Accepted; answered (incorrect with stub) |
| Q047 | How many employees does the company have? | False | REJECT | none (by design) | no | Rejected by gate (correct refusal) |
| Q048 | What is the annual cost of the project? | True | ACCEPT | none (by design) | yes | Accepted; answered (incorrect with stub) |
| Q049 | Which cloud provider hosts the production database? | True | ACCEPT | none (by design) | yes | Accepted; answered (incorrect with stub) |
| Q050 | What is the average monthly number of uploaded documents? | True | ACCEPT | none (by design) | yes | Accepted; answered (incorrect with stub) |
| Q051 | What is the university's tuition fee for undergraduate programmes? | False | REJECT | none (by design) | no | Rejected by gate (correct refusal) |
| Q052 | What is the exact final release date of version 3.0? | True | ACCEPT | none (by design) | yes | Accepted; answered (incorrect with stub) |
| Q053 | How much does it cost to apply for the graduate programme? | False | REJECT | none (by design) | no | Rejected by gate (correct refusal) |
| Q054 | What is the university's official mascot? | False | REJECT | none (by design) | no | Rejected by gate (correct refusal) |
| Q055 | How many scholarships does the university offer? | False | REJECT | none (by design) | no | Rejected by gate (correct refusal) |
| Q056 | What is the maximum number of uploads allowed per user per day? | False | REJECT | none (by design) | no | Rejected by gate (correct refusal) |

By construction unanswerable questions have no supporting evidence, so the `Evidence` column is always none. The 7 rejected items are **correct refusals**; the 6 accepted items are **false acceptances** (see the Confidence Gate section).
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
- Corpus is 2 documents / 11 chunks; results are indicative,
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
(version 1.0).
