# DocMind

**University knowledge retrieval and question-answering platform** built on a hybrid RAG pipeline. Students and faculty ask natural-language questions about official university documents — academic regulations, examination ordinances, attendance policies, syllabi, and more — and receive grounded answers with structured source and page citations. If the evidence is insufficient, the system says so instead of hallucinating.

---

## Features

- **PDF ingestion** — upload, validate, extract text (PyMuPDF), page-aware chunking, BGE embeddings, pgvector storage
- **Hybrid retrieval** — dense vector search (pgvector HNSW) + BM25 keyword search (PostgreSQL FTS), weighted score fusion
- **Cross-encoder reranking** — `ms-marco-MiniLM-L-6-v2` re-scores fused candidates for final ordering
- **Confidence gating** — weak evidence returns a grounded refusal; the LLM is never called without sufficient support
- **Grounded answers** — the LLM answers only from retrieved context, with prompt-injection hardening
- **Source citations** — every answer includes document title, page number, section (when available), and relevance score
- **Authentication & RBAC** — JWT auth, bcrypt passwords, `STUDENT` / `FACULTY` / `ADMIN` roles enforced server-side
- **Persistent conversations** — threaded chat with history, deterministic LLM-free titles
- **Feedback** — 1–5 star ratings on answers with optional text, upsert semantics
- **Document versioning** — upload new versions, reprocess to activate, version history
- **Admin dashboard** — system stats, user management, role changes, document overview
- **User-facing search** — clean search results with match percentages, no raw internals
- **Public demo mode** — pre-indexed PDF, no auth required, TF-IDF retrieval (no ML models at runtime)

---

## Architecture

### RAG Pipeline

```
User question
   │
   ▼
Permission filtering ──► Dense retrieval (pgvector)
                    └──► BM25 retrieval (PostgreSQL FTS)
                              │
                              ▼
                     Hybrid fusion (normalize + weight)
                              │
                              ▼
                     Cross-encoder reranking
                              │
                              ▼
                     Confidence gate ──► fallback (weak evidence)
                              │
                              ▼
                     Context builder ──► LLM ──► Answer + citations
```

### Document Ingestion

```
PDF upload ──► Validation ──► Text extraction ──► Cleaning
   ──► Page-aware chunking ──► BGE embeddings ──► pgvector storage
   ──► Document → ACTIVE
```

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Lucide |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 16 + pgvector |
| RAG | sentence-transformers / BGE (`BAAI/bge-base-en-v1.5`), BM25 (PostgreSQL FTS), cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`), pluggable LLM provider (Gemini / local) |
| Documents | PyMuPDF (text extraction) |
| Auth | JWT (PyJWT), bcrypt, role-based access control |
| Infra | Docker, Docker Compose |

---

## Quick Start (Docker — recommended)

Docker provides the complete environment: Python, Node.js, PostgreSQL+pgvector, ML models — nothing else to install.

```bash
git clone <repo-url> DocMind
cd DocMind
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD, SECRET_KEY, GEMINI_API_KEY
docker compose up -d --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |

Register an account (always created as `STUDENT`), log in, upload a PDF, process it, and ask questions.

**Requirements:** Docker Desktop (8 GB RAM recommended, ~10 GB disk). First run downloads ML models from Hugging Face (~500 MB); subsequent runs use the cached volumes.

> For the **development stack** with hot-reload, see [docs/development.md](docs/development.md).

---

## Local Development (without Docker containers)

The full application requires **PostgreSQL 16 + pgvector** in all configurations. There is no SQLite fallback — the codebase uses pgvector for embeddings and PostgreSQL FTS for BM25 retrieval.

The easiest way to get the database without installing PostgreSQL on your host:

```bash
# Start only the database container
docker compose up -d db
```

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                # Windows (Linux/macOS: source .venv/bin/activate)
pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.3,<3.0"
pip install -r requirements.txt
cp .env.example .env                  # defaults point to localhost:5432

python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                           # http://localhost:3000
```

> **Full local setup details:** [docs/development.md](docs/development.md)

---

## Public Demo

When `DEMO_MODE=true`, the landing page becomes an unauthenticated chat UI anchored to a single pre-indexed document. No uploads, no account required.

- **Pre-indexed:** the demo PDF is processed once; runtime uses lightweight TF-IDF retrieval (no embedding model or reranker loaded)
- **Grounded answers:** out-of-scope questions are refused, not hallucinated
- **Example questions:** clickable chips that run real retrieval, not hardcoded answers
- **Auto-seeded:** in production, the demo index is automatically seeded from a committed artifact on startup — no manual build step needed on hosted instances

```bash
# Local / Docker: build the index once, then enable demo mode
cd backend
python -m scripts.build_demo_index
# Set DEMO_MODE=true in .env, restart the backend
```

> **Full demo guide:** [docs/demo.md](docs/demo.md)

---

## Configuration

Key environment variables (see `.env.example` for all defaults):

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection (`postgresql+psycopg://…`) | localhost dev URL |
| `SECRET_KEY` | JWT signing key (**change in production**) | dev placeholder |
| `GEMINI_API_KEY` | Google AI Studio API key | (empty) |
| `LLM_PROVIDER` | `gemini` or `local` (offline dev) | `gemini` |
| `LLM_MODEL` | Model name for the provider | `gemini-flash-latest` |
| `EMBEDDING_MODEL` | sentence-transformers model | `BAAI/bge-base-en-v1.5` |
| `RERANKER_MODEL` | Cross-encoder model | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| `DEMO_MODE` | Enable public demo (`true`/`false`) | `false` |
| `NEXT_PUBLIC_API_URL` | Backend URL baked into frontend build | `http://localhost:8000` |
| `CONFIDENCE_THRESHOLD` | Min reranker score to answer (0–1) | `0.35` |

> **Complete variable reference:** [`.env.example`](.env.example), [`backend/.env.example`](backend/.env.example)

---

## API Overview

Interactive documentation is available at [`/docs`](http://localhost:8000/docs) (Swagger) and [`/redoc`](http://localhost:8000/redoc).

| Group | Endpoints |
|-------|-----------|
| **Health** | `GET /api/health` |
| **Auth** | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| **Documents** | `POST /api/documents`, `GET /api/documents`, `GET /api/documents/{id}`, `PATCH /api/documents/{id}`, `DELETE /api/documents/{id}`, `POST /api/documents/{id}/process` |
| **Versions** | `GET /api/documents/{id}/versions`, `POST /api/documents/{id}/versions` |
| **Chat** | `POST /api/chat` |
| **Search** | `POST /api/search` (developer), `POST /api/search/results` (user-facing) |
| **Conversations** | `GET /api/conversations`, `GET /api/conversations/{id}`, `DELETE /api/conversations/{id}` |
| **Feedback** | `POST /api/feedback` |
| **Admin** | `GET /api/admin/users`, `GET /api/admin/documents`, `GET /api/admin/stats`, `PATCH /api/admin/users/{id}/role` |
| **Demo** | `GET /api/demo/info`, `POST /api/demo/chat` *(demo mode only)* |

> **Detailed API reference:** [docs/api.md](docs/api.md)

---

## RAG Pipeline

The implemented pipeline runs entirely server-side with backend-enforced permission filtering:

1. **Query embedding** — the question is embedded with the same BGE model used for ingestion.
2. **Permission filtering** — chunks are retrieved only from documents the user can access (SQL `WHERE` clause, both retrievers).
3. **Dense retrieval** — top-K chunks by cosine distance via the pgvector HNSW index.
4. **BM25 retrieval** — top-K chunks by PostgreSQL FTS `ts_rank_cd` over a generated tsvector column.
5. **Hybrid fusion** — both pools are deduplicated, min-max normalized, and combined with configurable weights.
6. **Cross-encoder reranking** — a cross-encoder re-scores fused candidates; sigmoid-transformed logits become `rerank_score`.
7. **Confidence gate** — if the best evidence falls below the threshold, the LLM is skipped and a grounded refusal is returned.
8. **Context construction** — winning chunks are labelled `[1]…[n]` and assembled within the context character limit.
9. **LLM generation** — a provider-agnostic client answers strictly from supplied context (prompt-injection hardened).
10. **Citation mapping** — source tags in the answer are resolved into structured citations with document title, page, section, and relevance score.

**Graceful degradation:** BM25 failure → dense-only; dense failure → BM25-only; reranker outage → hybrid-fused order preserved.

---

## Evaluation

Measured on a 2-document corpus using the Phase 7 evaluation harness (`backend/evaluation/`). These numbers are indicative of this specific corpus and setup, not a claim about larger corpora.

**Dataset:** 56 questions (43 answerable, 13 unanswerable), hand-verified ground truth.

### Retrieval (answerable questions)

| Metric | Baseline (dense-only) | Phase 5 (hybrid + rerank) | Δ |
|--------|----------------------|--------------------------|---|
| Recall@1 | 0.5814 | 0.8837 | **+0.3023** |
| MRR@10 | 0.5814 | 0.8837 | +0.3023 |

> On this 2-document corpus, a relevant chunk either ranks #1 or is missed entirely, so Recall@1/3/5/10 and MRR coincide.

### Confidence Gate (Phase 5)

| Metric | Value |
|--------|-------|
| Answerable accepted | 38 / 43 |
| Answerable rejected (false rejections) | 5 / 43 (11.63%) |
| Unanswerable rejected (correct refusals) | 7 / 13 |
| Unanswerable accepted (false acceptances) | **6 / 13 (46.15%)** |

### Latency (mean / median / P95, milliseconds)

| Stage | Baseline | Phase 5 |
|-------|----------|---------|
| Dense | 73.4 / 71.4 / 83.7 | 70.3 / 70.4 / 73.4 |
| BM25 | — | 2.3 / 2.2 / 3.1 |
| Rerank | — | 56.4 / 49.1 / 140.2 |
| End-to-end | 73.5 / 71.6 / 83.8 | 120.1 / 101.4 / 207.1 |

**Honest caveats:** Answer/faithfulness columns in the full report were produced with the **local deterministic provider** (offline test stub) because the Gemini free tier was quota-exhausted (HTTP 429). Retrieval, confidence-gate, and latency numbers are real and provider-independent. No threshold was tuned and no dataset labels were changed.

> **Full methodology and raw results:** [docs/evaluation.md](docs/evaluation.md)

---

## Known Limitations

- **Small evaluation corpus** — 2 documents, 56 questions. Metrics are indicative, not a benchmark claim.
- **Confidence gate ≠ hallucination shield** — 46.15% false acceptance rate on unanswerable questions.
- **5 false rejections** — answerable questions where retrieval misses evidence (dense below 0.65 cutoff + BM25 term mismatch).
- **`section` citations often null** — chunking does not extract section headings.
- **Gemini free-tier quota** — the free tier can be exhausted (HTTP 429); the system degrades to grounded refusal.
- **Synchronous ingestion** — PDF processing blocks the API; designed for demo/small-instance workloads.
- **JWT in `localStorage`** — dev-tier persistence; production should use httpOnly cookies.

---

## Roadmap

- Background ingestion workers (Celery / arq)
- OCR pipeline for scanned documents
- Streaming LLM responses
- Fine-grained analytics over feedback
- Deployment hardening: reverse proxy (TLS), secrets manager, read replicas, pgvector index tuning

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, routers, lifespan
│   │   ├── api/routes/              # health, auth, admin, documents, chat, conversations, feedback, demo
│   │   ├── core/                    # config, enums, errors, logging, security
│   │   ├── db/                      # engine, session, ORM models
│   │   ├── rag/                     # chunking, confidence, prompts, score normalization
│   │   ├── schemas/                 # Pydantic request/response models
│   │   ├── services/               # auth, ingestion, retrieval, RAG, BM25, reranking, demo, etc.
│   │   └── tests/                   # 252 tests
│   ├── evaluation/                  # dataset, metrics, runner, results
│   ├── scripts/                     # build_demo_index.py
│   ├── alembic/                     # migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/                         # Next.js App Router (login, register, dashboard, search, admin)
│   ├── components/                  # UI primitives, SiteHeader, DemoChat, RequireAuth
│   ├── lib/                         # API client, auth context, demo client
│   └── Dockerfile
├── Doc/                             # Demo PDF
├── docs/                            # Detailed documentation
├── docker-compose.yml               # Production stack
├── docker-compose.dev.yml           # Development stack (hot-reload)
└── .env.example                     # Configuration template
```

---

## Documentation

| Document | Contents |
|----------|----------|
| [Architecture](docs/architecture.md) | Layer details, design principles, phase scope |
| [Development](docs/development.md) | Dev stack, host setup, tests, database, Alembic |
| [Deployment](docs/deployment.md) | Self-hosted Docker guide, Render + Vercel, production checklist |
| [API Reference](docs/api.md) | Full endpoint documentation, auth flow, error codes |
| [Evaluation](docs/evaluation.md) | Methodology, dataset, full results, reproduction |
| [Demo Guide](docs/demo.md) | Public demo setup, seed mechanism, deployment |
| [Security](docs/security.md) | Auth architecture, prompt hardening, credential hygiene |

---

## License

Academic project — internal use. See your institution's project guidelines.
