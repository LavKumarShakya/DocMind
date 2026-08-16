# Public Demo Guide

Complete guide to DocMind's public demo mode.

---

## Overview

When `DEMO_MODE=true`, the landing page becomes an unauthenticated chat UI anchored to a single **pre-indexed** demo document (`Doc/DocMind_Public_Demo_Test_Document.pdf`). No uploads, no account required.

```
Public demo                        Local / self-hosted
DEMO_MODE=true                     DEMO_MODE=false
        │                                  │
        ▼                                  ▼
Pre-indexed demo document            User uploads own PDF
        │                                  │
        ▼                                  ▼
User asks question ──► Retriever    PDF processing ──► RAG
        │                                  │
        ▼                                  ▼
Relevant chunks ──► LLM ──►        Chat / search (auth required)
Answer + sources
```

---

## How It Works

- **Index once.** `python -m scripts.build_demo_index` (run from `backend/`) reads `DEMO_DOCUMENT_PATH`, extracts text, chunks with the project's existing chunking settings, embeds with `EMBEDDING_MODEL`, and stores the vectors in the **same persistent pgvector store** used by normal ingestion. Re-running is idempotent (existing demo chunks are replaced, never duplicated); use `--force` to rebuild from the current PDF.

- **Auto-seeding in production.** On startup with `DEMO_MODE=true`, the backend checks if the demo index exists. If not, it imports the committed `demo_seed.json` artifact (Document + chunk text, no embeddings) without loading any ML models. This means hosted instances don't need to run `build_demo_index` manually.

- **Runtime reuses the index.** The demo chat endpoint never calls the build path. If the index is missing, `GET /api/demo/info` reports `status: "missing"` and `POST /api/demo/chat` returns a clear `503 DEMO_INDEX_MISSING` error.

- **Query-time retrieval is model-free.** Each visitor question is answered by a lightweight TF-IDF cosine search over the stored demo chunks, then gated by `DEMO_CONFIDENCE_THRESHOLD` before the LLM is called. The embedding model and the cross-encoder reranker are **not** loaded in demo mode. The preset "Try asking" chips are real questions run through this same pipeline — never hardcoded answers.

- **Upload is disabled.** `POST /api/documents` (upload, process, version) returns `403 DEMO_MODE` while demo mode is on. Set `DEMO_MODE=false` to restore the upload workflow.

- **Grounded answers only.** The demo system prompt refuses out-of-scope questions with *"I couldn't find that information in the demo document. Try asking a question about the evaluation, metrics, or findings."* — general knowledge is never used. Provider/LLM failures degrade to this grounded refusal rather than a 500.

- **Frontend.** The landing page calls `GET /api/demo/info` at runtime. When demo mode is active it renders the demo chat (document card, message history with Sources, "Try asking" chip row, chat input); otherwise the standard landing page is shown unchanged. No frontend build flag is required.

---

## Enable the Demo

### Local / Docker

```bash
# 1. Build the pre-indexed demo document (from backend/)
cd backend
python -m scripts.build_demo_index          # use --force to rebuild

# 2. Run the API in demo mode
set DEMO_MODE=true                          # PowerShell
# export DEMO_MODE=true                     # bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker Compose

The demo PDF is mounted into the backend container at `/Doc` (read-only), so the default `DEMO_DOCUMENT_PATH=../Doc/…` resolves inside the container:

```bash
docker compose exec backend python -m scripts.build_demo_index
# Then set DEMO_MODE=true in your .env and restart:
docker compose up -d
```

> **Model note.** The default `LLM_MODEL=gemini-flash-latest` can be unavailable during Google free-tier capacity spikes (HTTP 503). The demo then returns the grounded refusal, never a wrong answer. If that happens, set `LLM_MODEL` to a currently-available model (e.g. `gemini-2.5-flash`).

---

## Configuration Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEMO_MODE` | `false` | Enable/disable public demo |
| `DEMO_DOCUMENT_PATH` | `../Doc/DocMind_Public_Demo_Test_Document.pdf` | Path to demo PDF (absolute or relative to backend working dir) |
| `DEMO_DOCUMENT_ID` | `11111111-1111-4111-8111-111111111111` | Fixed row id (do not change after building the index) |
| `DEMO_DOCUMENT_TITLE` | `DocMind Public Demo Test Document` | Display title |
| `DEMO_CONFIDENCE_THRESHOLD` | `0.05` | TF-IDF confidence gate (lower than the reranker-based threshold) |

---

## Public Deployment (Render + Vercel)

The demo runs on the same Render + Vercel setup described in [deployment.md](deployment.md), with two extra steps:

1. Make the demo PDF reachable by the backend process — upload it to the persistent disk (e.g. `/data/demo/DocMind_Public_Demo_Test_Document.pdf`) and set `DEMO_DOCUMENT_PATH` to that path, or bake the PDF into the image.
2. Set `DEMO_MODE=true`, `DEMO_DOCUMENT_ID`, `DEMO_DOCUMENT_TITLE`, and a working `LLM_MODEL`.

The demo frontend is still the static Next.js build on Vercel; it needs no extra environment variables (demo detection is a runtime API call).

> **Auto-seeding:** On Render, if the database is empty, the backend will automatically seed the demo index from the committed `demo_seed.json` artifact at startup. No manual `build_demo_index` step is needed for hosted deployments.

---

## Demo Walkthrough

With `DEMO_MODE=true`:

1. **Landing page** — `http://localhost:3000` renders the demo chat (no upload, no account): a "Demo Document / DocMind Public Demo Test Document" card with a "Public demo" badge.
2. **Example questions** — click any "Try asking" chip; it is sent automatically and appears as your own chat message.
3. **Grounded answers** — e.g. *"What were the retrieval recall and answer accuracy of Hybrid + Reranking?"* → a sourced answer with a "Sources (n)" list pointing at the demo document.
4. **Refusal** — *"What is the capital of France?"* → *"I couldn't find that information in the demo document…"* (no hallucination from general knowledge).
5. **Loading state** — while the LLM answers, the thread shows *"Retrieving relevant sections…"*.
6. **Missing index** — if the index was never built and auto-seeding failed, `/api/demo/info` reports `missing` and the page shows the build-script instruction.
