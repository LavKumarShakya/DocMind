# CampusRAG Phase 7 — Evaluation Report

Dataset `1.0` · 56 questions ·
baseline run 2026-08-14T06:40:29.700707+00:00 · phase5 run 2026-08-14T06:40:14.146107+00:00

Baseline = Phase 4 (dense-only, no confidence gate) · phase5 = Phase 5 (dense + BM25 → fuse → rerank, confidence gate).
Embedding `BAAI/bge-base-en-v1.5` · reranker `cross-encoder/ms-marco-MiniLM-L-6-v2` · LLM `local` ·
eval window top-10 · confidence threshold 0.35 ·
rerank top-10 · min similarity 0.65.

### Confidence gate (phase5)

| Bucket | N | Rate |
| --- | --- | --- |
| Answerable accepted | 38 | 0.4474 |
| Answerable rejected (false rejection) | 5 | 0.1163 |
| Unanswerable rejected (correct refusal) | 7 | 1.0000 |
| Unanswerable accepted (false acceptance) | 6 | 0.0000 |

## Retrieval quality (answerable questions)

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

## Generation quality

| Metric | Baseline | phase5 | Δ |
| --- | --- | --- | --- |
| Answer accuracy | 0.3929 | 0.4286 | +0.0357 |
| Fallback rate | 0.4821 | 0.2143 | -0.2678 |
| Faithfulness full (2/2) | 0.1964 | 0.2857 | +0.0893 |
| Faithfulness unsupported (0/2) | 0.6786 | 0.6250 | -0.0536 |
| Failure rate | 0.5357 | 0.4643 | -0.0714 |
| Citation validity (mean) | n/a | n/a | n/a |

## Latency (mean per stage)

| Stage | Baseline | phase5 |
| --- | --- | --- |
| dense | 73.6 ms | 72.2 ms |
| bm25 | 0.0 ms | 2.3 ms |
| fuse | 0.0 ms | 0.0 ms |
| rerank | 0.0 ms | 47.6 ms |
| LLM (mean) | 0.0 ms | 0.0 ms |
| End-to-end (mean) | 73.7 ms | 122.4 ms |

## Category breakdown (phase5)

| Category | N | Recall@5 | Accuracy | Recall@5 (base) | Accuracy (base) |
| --- | --- | --- | --- | --- | --- |
| edge | 5 | 1.0000 | 0.4000 | 1.0000 | 0.2000 |
| entity | 8 | 0.8750 | 0.3750 | 0.3750 | 0.1250 |
| keyword | 6 | 0.8333 | 0.5000 | 0.6667 | 0.6667 |
| numeric | 21 | 0.8571 | 0.3810 | 0.5238 | 0.2857 |
| semantic | 3 | 1.0000 | 0.3333 | 0.6667 | 0.3333 |
| unanswerable | 13 | 0.0000 | 0.5385 | 0.0000 | 0.6923 |

## Failure analysis (answerable, incorrect answers)

| Failure | Baseline | phase5 |
| --- | --- | --- |
| confidence_rejection | 0 | 5 |
| hallucination | 6 | 16 |
| retrieval_miss | 18 | 0 |
| wrong_answer | 6 | 5 |

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
