# DocMind

**University knowledge retrieval and question-answering platform.**

DocMind lets students and faculty ask natural-language questions about
official university documents (academic regulations, examination ordinances,
attendance policies, syllabi, scholarships, placement guidelines, hostel
rules, circulars, and more). Answers are grounded in the uploaded documents,
are produced by a Retrieval-Augmented Generation (RAG) pipeline, and include
structured citations pointing to the source document and page.

> **Status: Phase 9 (Public demo mode) complete.** All eight planned phases are
> implemented and regression-tested, plus a public demo mode that showcases the
> system on a single pre-indexed PDF without uploads. The same repository also
> ships a production-oriented **self-hosted Docker** workflow
> ([Self-hosted Docker](#self-hosted-docker)) for the full authenticated
> application. This README documents the full system, its measured evaluation
> results, and the remaining known
> limitations (see [Development roadmap](#development-roadmap),
> [Evaluation methodology](#evaluation-methodology) and
> [Known limitations](#known-limitations)).

---

## Table of contents

1. [Project overview](#project-overview)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Tech stack](#tech-stack)
5. [Repository structure](#repository-structure)
6. [Prerequisites](#prerequisites)
7. [Environment setup](#environment-setup)
8. [Database setup](#database-setup)
9. [Docker setup](#docker-setup)
10. [Self-hosted Docker](#self-hosted-docker)
11. [Running locally](#running-locally)
12. [API documentation](#api-documentation)
13. [RAG pipeline](#rag-pipeline)
14. [Evaluation methodology](#evaluation-methodology)
15. [Development roadmap](#development-roadmap)
16. [Future improvements](#future-improvements)
17. [Known limitations](#known-limitations)
18. [Security](#security)
19. [Deployment](#deployment)
20. [Demo checklist](#demo-checklist)

---

## Project overview

The system is built around a simple, defensible RAG architecture:

```
User question
   │
   ▼
Query processing ──► permission filtering ──► dense retrieval (pgvector)
   │                              │               └─► BM25 retrieval (PostgreSQL FTS)
   │                              ▼
   │                     hybrid fusion (normalize + weight)
   │                              ▼
   │                     cross-encoder reranking
   │                              ▼
   │                     confidence gate ──► fallback answer (weak evidence)
   │                              │
   ▼                              ▼
   └────────────────► context builder ──► LLM ──► answer + structured citations
```

Document ingestion follows a separate pipeline:

```
Upload ─► validation ─► text extraction ─► cleaning ─► metadata extraction
   ─► chunking ─► embeddings ─► vector storage (pgvector)
   ─► document ACTIVE
```

Key design principles:

- **Grounded answers.** The LLM may only answer from retrieved context; if
  evidence is insufficient, it says so instead of hallucinating.
- **Backend-enforced permissions.** Retrieval is filtered by the user's role
  server-side. The frontend is never trusted for authorization.
- **Provider-agnostic LLM.** The model is behind a service interface so
  Gemini, OpenAI, or another provider can be swapped without touching the RAG
  pipeline.
- **Transparent retrieval.** Retrieval is hybrid: dense vector search over
  pgvector plus BM25 keyword search over PostgreSQL full-text search, fused
  with weighted scores and re-ranked by a cross-encoder, then gated on
  confidence before the LLM is called.

---

## Architecture

### Layers

| Layer            | Technology                                   | Responsibility |
|------------------|----------------------------------------------|----------------|
| Frontend         | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui | Chat UI, dashboards, document search, admin |
| API              | FastAPI, Pydantic                            | REST endpoints, validation, auth, RBAC |
| Services         | Python (SQLAlchemy, domain services)         | Auth, ingestion, retrieval, RAG, citations, evaluation |
| RAG core         | sentence-transformers / BGE, pgvector         | Embeddings, semantic retrieval (BM25 + reranking in Phase 5) |
| Data             | PostgreSQL 16 + pgvector, Alembic            | Relational schema, vector search, migrations |

### Phase 1 scope (implemented)

Phase 1 delivers the application shell and data foundation:

- Docker Compose stack: **PostgreSQL 16 + pgvector**, **FastAPI backend**,
  **Next.js frontend**.
- Centralized settings via `pydantic-settings` (`.env`, env vars).
- Structured logging.
- Structured error responses — no raw stack traces are ever returned.
- ORM models for every core entity, with constraints, indexes and
  relationships.
- The pgvector `vector` extension and an **HNSW index** for future semantic
  search.
- Alembic migrations (autogenerated from models, verified with `alembic check`).
- Health checks: API root and `GET /api/health` (verifies DB connectivity).
- A minimal Next.js landing page that renders live backend health.

Everything beyond Phase 1 (auth, ingestion, retrieval, chat, admin) builds
incrementally on this foundation; implemented parts are described in [Features](#features)
and later phases are laid out in the [roadmap](#development-roadmap).

---

## Features

**Implemented (Phase 1):**

- Repository structure for the full system (backend + frontend + infra).
- Docker Compose orchestration with dependency health-checks.
- PostgreSQL + pgvector with the initial schema for all core entities.
- Alembic migrations (baseline applied; `alembic check` clean).
- FastAPI shell: CORS, structured errors, logging, health endpoint.
- Next.js shell: TypeScript, Tailwind, typed API client, health UI.

**Implemented (Phase 2):**

- Registration, login and current-user endpoints.
- bcrypt password hashing (never stored/logged in plaintext).
- JWT access tokens (signed, expiring) issued on login.
- Reusable auth dependencies (`get_current_user`, `require_role`) enforcing
  access control server-side.
- Roles `STUDENT` / `FACULTY` / `ADMIN`; new users always start as `STUDENT`;
  clients can never self-assign a role.
- Structured auth errors (`AUTHENTICATION_REQUIRED`, `INVALID_CREDENTIALS`,
  `INVALID_TOKEN`, `TOKEN_EXPIRED`, `EMAIL_ALREADY_REGISTERED`, `FORBIDDEN`).
- Frontend auth flow: login/register pages, persistent session (JWT in
  `localStorage`), authenticated dashboard with logout, protected client-side
  route guard, and an API client that attaches the Bearer token automatically.
- Backend test suite (28 tests) covering registration, login, token
  validation and RBAC.

**Implemented (Phase 3):**

- PDF upload endpoint with strict validation: extension, MIME type, `%PDF-`
  magic bytes, size limit and empty-file rejection. A file renamed to `.pdf`
  is still rejected.
- Local, replaceable storage layer (`app/services/storage_service.py`) storing
  files under `<STORAGE_DIR>/documents/<id>/original.pdf`; server-generated
  paths are stored in the DB, never exposed to clients.
- Page-aware text extraction with PyMuPDF, deterministic text cleaning, and
  present-only PDF metadata reading.
- Character-based chunking (`CHUNK_SIZE` / `CHUNK_OVERLAP`) that never merges
  text across page boundaries and preserves page number + global chunk order.
- Embedding service using sentence-transformers / BGE
  (`BAAI/bge-base-en-v1.5`, 768 dims) with a single reused model instance and
  an explicit dimension check against `EMBEDDING_DIM`.
- Ingestion pipeline (`app/services/ingestion_service.py`) with the
  `UPLOADED → PROCESSING → ACTIVE` lifecycle and a `FAILED` state storing a
  safe internal error description; reprocessing replaces old chunks (no
  duplicates) and can recover a failed document.
- Document API: upload, list, detail (with chunk count), metadata PATCH,
  process, and delete (removes chunks + stored file). Authorization is
  server-side: only the uploader or an ADMIN can manage; visibility is
  access-level based.
- Frontend document management in the authenticated dashboard: upload with
  progress/disabled states, status badges, process/delete actions, empty and
  error states.
- Backend test suite grown to 73 tests covering validation, extraction,
  chunking, embedding, DB rows, processing status transitions and the full
  document API.

**Implemented (Phase 4):**

- Semantic retrieval over pgvector (`app/services/retrieval_service.py`): the
  question is embedded with the same BGE model used for ingestion, then chunks
  are ranked by cosine distance (`embedding <=> query`) through the HNSW index.
- Permission filtering happens **in the SQL query** — chunks are joined to
  documents and filtered by the same visibility rules as the document API
  (uploader or access-level match). The chat endpoint never filters evidence
  in application code.
- Retrieval is configurable: `RETRIEVAL_TOP_K` (default 5) and
  `RETRIEVAL_MIN_SIMILARITY` (default 0.65) prune weak matches.
- Context builder (`app/services/context_service.py`) labels each retrieved
  chunk `[n]` and truncates whole chunks to `MAX_CONTEXT_CHARS` so citation
  tags always point at fully-included evidence.
- LLM provider abstraction (`app/services/llm_service.py`): `gemini` (Google
  Gemini via `google-genai`, default) and `local` (offline development provider
  that answers from the top chunk — never used in production). Providers are
  swappable without touching the RAG pipeline.
- Grounded prompting (`app/rag/prompts.py`): the model is told evidence is
  data, not instructions (prompt-injection hardening), and must answer with
  the fixed fallback *"I couldn't find sufficient information in the available
  university documents."* when evidence is insufficient.
- Citation mapping (`app/services/citation_service.py`): tags in the model's
  answer are resolved against the retrieved chunks, producing structured
  citations (document title, page, section). `section` is surfaced as `null`
  when the document does not provide one — never fabricated.
- RAG orchestrator (`app/services/rag_service.py`) with graceful degradation:
  empty retrieval or an LLM failure returns the grounded fallback instead of
  an error, keeping the chat API usable during upstream outages.
- Chat and search endpoints (`POST /api/chat`, `POST /api/search`): answers
  with citations, plus a developer-facing raw retrieval endpoint.
- Dashboard chat panel in the authenticated frontend: question input, loading
  state, rendered answer with a Sources list, and error/empty handling.
- Backend test suite grown to **107 tests** covering retrieval ranking and
  permission filtering, context truncation, the local LLM provider, citation
  mapping, the full RAG pipeline (grounded answer, fallbacks, validation) and
  the chat/search API.

**Implemented (Phase 5):**

- **BM25 keyword retrieval** (`app/services/bm25_service.py`): PostgreSQL
  full-text search ranks chunks with `ts_rank_cd` over a generated `tsvector`
  column on `document_chunks` (`searchable_content`, backed by a GIN index).
  Course codes, regulation numbers and orphaned keywords are matched that pure
  vectors miss. Permission filtering is part of the SQL `WHERE` clause, exactly
  like the dense stage.
- **Hybrid fusion** (`app/services/hybrid_retrieval_service.py`): dense and
  BM25 pools (each `DENSE_CANDIDATE_K` / `BM25_CANDIDATE_K` = 20) are merged
  and deduplicated by chunk id, min-max normalized, then fused with
  `HYBRID_DENSE_WEIGHT` / `HYBRID_BM25_WEIGHT` into `hybrid_score`. The top
  `RERANK_TOP_K` (= 8) fused candidates go to the re-ranker — never thousands
  of chunks.
- **Cross-encoder reranking** (`app/services/reranking_service.py`):
  `cross-encoder/ms-marco-MiniLM-L-6-v2` (sentence-transformers) re-scores the
  top fused candidates against the question. Raw logits are sigmoid-transformed
  to a 0..1 `rerank_score`. The model is a lazy singleton loaded once per
  process, and inference is batched (`RERANKER_BATCH_SIZE`).
- **Confidence gating** (`app/rag/confidence.py`): the LLM is only called when
  the best evidence clears `CONFIDENCE_THRESHOLD`. Weak or empty evidence
  returns the grounded fallback without invoking the LLM.
- **Citations carry relevance**: each citation exposes `relevance_score`, the
  final reranker score for that source.
- **Graceful degradation**: if BM25 fails the pipeline falls back to dense, if
  dense fails it falls back to BM25, and if the reranker is unavailable the
  hybrid-fused order is used instead of erroring.
- Backend test suite grown to **137 tests** covering BM25 ranking/permissions,
  score normalization, fusion weights, dedupe, reranker ordering and metadata
  preservation, confidence thresholds, hybrid E2E, and permissive/restrictive
  permission paths.

**Implemented (Phase 6):**

- **Persistent conversations** (`app/services/conversation_service.py`):
  `POST /api/chat` accepts an optional `conversation_id`; when omitted a new
  conversation is created with a deterministic, LLM-free title (leading question
  words stripped, truncated to 60 chars — e.g. *"What is the minimum attendance
  requirement?"* → *"Minimum attendance requirement"*). The exchange (user
  message → answer → citations) is persisted, and conversation history is never
  fed back into the LLM — the Phase 5 pipeline is untouched.
- **Conversation API**: `GET /api/conversations`, `GET /api/conversations/{id}`
  (full thread with citations), `DELETE /api/conversations/{id}`. Ownership is
  enforced server-side: users only ever see their own conversations, and a
  non-owner gets a 404 (existence hidden).
- **Message ordering** is deterministic: a `position` column (int, server
  default `0`) orders messages within a conversation, since same-transaction
  `now()` timestamps collide.
- **Feedback** (`app/services/feedback_service.py`): `POST /api/feedback` rates
  an assistant answer 1–5 with an optional reason. One entry per (user,
  message) via a unique constraint — resubmission upserts. Only assistant
  messages can be rated, and only the conversation owner can rate them.
- **Document versioning** (`app/services/document_service.py`): every upload
  creates a version-1 `DocumentVersion`. `GET/POST /api/documents/{id}/versions`
  list and upload new versions (v1 lives at `documents/<id>/original.pdf`,
  vN at `documents/<id>/versions/<n>/original.pdf`). Uploading a version
  archives the previous current version and switches the document's file
  pointers; the new version is `UPLOADED` until the existing
  `POST /{id}/process` makes it `ACTIVE` (and replaces the old chunks). The
  circular `document ↔ document_version` FK is resolved with a named
  `use_alter=True` FK and explicit relationship join conditions.
- **Citations gain provenance**: `Citation` now stores `document_id`,
  `document_title` and `section`, and the chat response already carries these
  alongside `relevance_score`.
- **User-facing search** (`POST /api/search/results`): runs the Phase 5
  retrieval and returns clean results (document title, page, snippet, relevance
  percentage) with **no** raw scores, chunk ids or vector internals — those
  remain on the developer endpoint `/api/search`.
- **Admin API + dashboard** (`app/api/routes/admin.py`): `GET /api/admin/users`,
  `GET /api/admin/documents`, `GET /api/admin/stats` (real DB counts), and
  `PATCH /api/admin/users/{id}/role`. All require `ADMIN`; responses never
  include password hashes or storage paths. The last remaining `ADMIN` cannot
  be demoted (`LAST_ADMIN`). The new `/admin` frontend page surfaces stats,
  user role management and a document overview.
- **Frontend**: dashboard reworked into a conversation layout — sidebar with
  conversation list/new/delete, threaded chat with per-answer 👍/👎 feedback,
  and a per-document version history with "Upload new version". New `/search`
  page (clean, permission-aware search UI). New `/admin` page (ADMIN only).
- Backend test suite grown to **239 tests** (conversations, feedback,
  versioning, admin, search, evaluation added).

**Phase 7 (done):** a reproducible evaluation harness that measures retrieval
and RAG quality on a version-controlled dataset grounded in the two corpus
documents (`backend/evaluation/dataset.json`, 56 questions), comparing the
Phase 4 (dense-only) baseline against Phase 5 (hybrid + rerank + confidence
gate). Results live in `backend/evaluation/results/` (`baseline.json`,
`phase5.json`, `comparison.json`, `report.md`). See
[Evaluation methodology](#evaluation-methodology).

**Phase 8 (done): final polish, hardening and release preparation.**

- **Responsive navigation** — the three authenticated pages (dashboard,
  search, admin) now share a single `SiteHeader` component
  (`frontend/components/site-header.tsx`) with a mobile hamburger menu, so
  every page is reachable on phones (320 px and up) and the active link is
  highlighted consistently via `usePathname`.
- **Chat UX hardening** — the dashboard chat no longer loses your question on a
  failed request (the input is restored), message state updates use functional
  setters (no stale-closure double renders), and the loading indicator now
  reads *"DocMind is searching your documents…"* with an accessible
  `role="status"`.
- **Configuration clarity** — `.env.example` files and `docker-compose.yml`
  now carry explicit "production-sensitive" notes next to the dev-default
  `SECRET_KEY` / `POSTGRES_PASSWORD` placeholders.
- **Regression & release verification** — full suite re-run (241 tests),
  `alembic check` clean, frontend `typecheck` + production `build`, and a
  clean `docker compose up --build` with health-checked startup of all three
  services. A final secrets scan confirmed no API keys or credentials are
  tracked in version control.
- Backend test suite remains at **241 tests** covering every phase from
  foundation through evaluation.

**Phase 9 (done): public demo mode.**

- **Pre-indexed demo document** — `Doc/DocMind_Public_Demo_Test_Document.pdf`
  is processed once by `backend/scripts/build_demo_index.py` (read → extract →
  chunk → embed → store in the existing pgvector store). The script is
  idempotent; the runtime never re-reads, re-chunks or re-embeds the PDF.
- **Demo API** — unauthenticated `GET /api/demo/info` (mode + readiness +
  title/chunk count) and `POST /api/demo/chat` (grounded answer + citations,
  scoped to the demo document). `DEMO_MODE` gates the routes; upload/process/
  version return `403 DEMO_MODE` while enabled. A missing index returns a
  clear `503 DEMO_INDEX_MISSING` instead of a silent empty store.
- **Demo UI** — the landing page detects demo mode at runtime and renders a
  chat with a "Demo Document" card, "Try asking" example chips, grounded
  answers with Sources, and a "Retrieving relevant sections…" loading state.
- **RAM discipline** — demo chat runs query embedding + hybrid retrieval over
  already-stored chunks only; no PDF bytes or per-request vectors.
- Backend test suite grown to **252 tests** (`app/tests/test_demo.py` adds
  mode gating, index build/idempotency, scoped chat wiring, LLM-failure
  fallback, and upload blocking).

---

## Tech stack

| Area | Choice |
|------|--------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Lucide icons |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 16, pgvector |
| RAG | Sentence-transformers / BGE embeddings, BM25, cross-encoder reranker, pluggable LLM provider |
| Documents | PyMuPDF (PDF text extraction); OCR integration designed for later |
| Auth | JWT, bcrypt password hashing, role-based access control |
| Infra | Docker, Docker Compose, environment variables |

Python version compatibility was validated against **3.13** (local venv and
`python:3.13-slim` container image). Dependencies are pinned as major-version
ranges in `backend/requirements.txt`; the resolver picks current compatible
patch releases (validated at build time on Python 3.13).

Notable compatibility decisions:

- **psycopg (v3) + `postgresql+psycopg://`** — the maintained PostgreSQL
  driver that works with SQLAlchemy 2 and pgvector.
- **`pgvector/pgvector:pg16` image** — ships PostgreSQL 16 with the pgvector
  extension preinstalled (no init-script hacks).
- **Tailwind CSS v4** with `@tailwindcss/postcss` and the modern
  `@import "tailwindcss"` setup (shadcn/ui supports this configuration).
- **Non-native enum columns** — enums are stored as `VARCHAR(32)` with Python
  `Enum` + CHECK-style ORM validation, which keeps future enum migrations simple.

---

## Repository structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app factory, CORS, handlers, routers
│   │   ├── api/
│   │   │   ├── deps.py             # auth deps: get_current_user, require_role
│   │   │   └── routes/             # health, auth, admin, documents, chat, conversations, feedback, demo (Phase 9)
│   │   ├── core/
│   │   │   ├── config.py           # centralized settings (pydantic-settings)
│   │   │   ├── enums.py            # Role, DocumentStatus, AccessLevel, MessageRole
│   │   │   ├── errors.py           # structured error responses
│   │   │   ├── logging.py          # logging setup
│   │   │   └── security.py         # bcrypt hashing, JWT encode/decode
│   │   ├── db/
│   │   │   ├── database.py         # engine, session factory, Base, get_db
│   │   │   └── models/             # ORM models (users, documents, versions, chunks, ...)
│   │   ├── rag/
│   │   │   ├── chunking.py         # page-aware chunking (chunk_size/overlap)
│   │   │   ├── confidence.py       # retrieval confidence gate (Phase 5)
│   │   │   ├── prompts.py          # grounded system prompt + fallback (+ demo variant)
│   │   │   └── score_normalization.py # min-max score normalization (Phase 5)
│   │   ├── schemas/                # Pydantic request/response schemas (incl. demo)
│   │   └── services/
│   │       ├── auth_service.py     # register_user, authenticate_user
│   │       ├── bm25_service.py     # PostgreSQL FTS keyword retrieval (Phase 5)
│   │       ├── citation_service.py # answer tags → structured citations
│   │       ├── context_service.py  # labelled evidence → context block
│   │       ├── conversation_service.py # conversations, messages, citations persistence (Phase 6)
│   │       ├── demo_service.py     # public demo index build + scoped demo chat (Phase 9)
│   │       ├── document_service.py # CRUD, visibility, authorization, versioning (Phase 6)
│   │       ├── embedding_service.py# sentence-transformers/BGE, model reuse
│   │       ├── feedback_service.py # answer ratings, upsert (Phase 6)
│   │       ├── hybrid_retrieval_service.py # dense+BM25 fusion + rerank (Phase 5)
│   │       ├── ingestion_service.py# upload→extract→chunk→embed→ACTIVE
│   │       ├── llm_service.py      # LLM provider abstraction (gemini/local)
│   │       ├── pdf_service.py      # validation, page extraction, cleaning
│   │       ├── rag_service.py      # question → evidence → answer → citations
│   │       ├── reranking_service.py# cross-encoder re-scoring (Phase 5)
│   │       ├── retrieval_service.py# pgvector cosine retrieval + permissions
│   │       ├── retrieval_types.py  # shared RetrievalCandidate (Phase 5)
│   │       └── storage_service.py  # local file storage (replaceable)
│   ├── scripts/
│   │   └── build_demo_index.py     # one-time, idempotent demo index build (Phase 9)
│   ├── tests/                      # backend tests (auth, RBAC, docs, RAG, product, evaluation, demo; 252 passing)
│   ├── evaluation/                 # Phase 7 harness: dataset.json, corpus/, metrics, modes, runner, results/
│   ├── alembic/                    # migration env + versions/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt        # pytest, httpx
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── app/                        # Next.js App Router pages (login, register, dashboard, search, admin)
│   ├── components/                 # ui primitives, RequireAuth guard, shared SiteHeader, DemoChat (Phase 9)
│   ├── lib/                        # api client, auth context/helpers, demo client
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── Dockerfile
│   └── .env.example
├── Doc/
│   └── DocMind_Public_Demo_Test_Document.pdf   # demo PDF indexed by scripts/build_demo_index.py
├── docker-compose.yml        # self-hosted production stack
├── docker-compose.dev.yml    # development stack (hot-reload)
├── .env.example
└── README.md
```

Planned backend modules (created in their phases, not present yet):

```
app/services/        remaining service layer
app/db/repositories/ data-access layer
```

> Note: BM25, hybrid fusion, reranking and confidence are implemented (Phase 5);
> they live in `app/services/bm25_service.py`, `app/services/hybrid_retrieval_service.py`,
> `app/services/reranking_service.py` and `app/rag/confidence.py`. Phase 7
> evaluation tooling lives in `backend/evaluation/`.

---

## Prerequisites

### Self-hosted (Docker)

The easiest way to run the full DocMind application is with Docker:

- **Docker Desktop** (with the Linux engine / WSL2 backend on Windows, or the
  Docker Engine + Compose v2 plugin on Linux/macOS)
- **~8 GB of available RAM** (the embedding and reranker models run in-process
  on CPU; more RAM makes ingestion and first-load smoother)
- **~10 GB of free disk space** for images, the model cache and your documents
- Internet access on first run so the BGE embedder and cross-encoder reranker
  can be downloaded from Hugging Face (they are cached afterwards)

No Python, Node.js, PostgreSQL or other runtime is installed on the host — the
containers provide everything.

### Local development (host runtimes)

- Python 3.13 (for local backend development)
- Node.js 20+ (for local frontend development)
- Docker (for the PostgreSQL + pgvector database)
- Optional: `make`, Git

---

## Environment setup

### Self-hosted (Docker)

For the Docker stack, only the root `.env` is needed — `docker-compose.yml`
reads it for variable substitution. **Never commit real credentials.**

```bash
cp .env.example .env
# edit .env and set at minimum:
#   POSTGRES_PASSWORD=<strong random password>
#   SECRET_KEY=<strong random string, 32+ bytes>
#   GEMINI_API_KEY=<your Google AI Studio API key>
```

### Local development (host runtimes)

```bash
# backend (local development)
cp backend/.env.example backend/.env

# frontend (local development)
cp frontend/.env.example frontend/.env.local
```

The defaults are safe for local development. In production you must change at
minimum `POSTGRES_PASSWORD`, `SECRET_KEY`, and `CORS_ORIGINS`. To enable the
Gemini-backed chat endpoint, set `GEMINI_API_KEY` in the root `.env` (read by
`docker-compose`) or in `backend/.env` (local backend). Without it, set
`LLM_PROVIDER=local` for an offline development answerer.

### Key variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy URL (`postgresql+psycopg://…`). Docker overrides the host to `db`. |
| `POSTGRES_USER/PASSWORD/DB` | PostgreSQL credentials (used by Compose). |
| `SECRET_KEY` | JWT signing key (used from Phase 2). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime. |
| `TEST_DATABASE_URL` | Dedicated test database (tests create it if missing; defaults to `docmind_test`). |
| `CORS_ORIGINS` | Comma-separated allowed browser origins. |
| `DEBUG` | Enables verbose logging. |
| `EMBEDDING_DIM` | Vector dimension of the embedding model (768 for BGE-base). Must equal the model's output. |
| `EMBEDDING_MODEL` | sentence-transformers model name (default `BAAI/bge-base-en-v1.5`). |
| `STORAGE_DIR` | Local document storage root (replaceable storage layer). In Docker this maps to a persistent named volume. |
| `HF_HOME` | Hugging Face / sentence-transformers model cache directory (persistent named volume in Docker). |
| `MAX_UPLOAD_SIZE_BYTES` | Maximum accepted PDF upload size (20 MiB default). |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Character-based chunking parameters. |
| `RETRIEVAL_TOP_K` | Number of semantically similar chunks retrieved per question (default 5). |
| `RETRIEVAL_MIN_SIMILARITY` | Minimum cosine similarity for a chunk to count as evidence (default 0.65). |
| `MAX_CONTEXT_CHARS` | Maximum evidence characters assembled into the LLM prompt (default 8000). |
| `MAX_MESSAGE_LENGTH` | Maximum length of a chat question (default 2000). |
| `LLM_PROVIDER` | `gemini` (default, needs `GEMINI_API_KEY`) or `local` (offline dev only). |
| `LLM_MODEL` | Model name for the configured provider (default `gemini-flash-latest`). |
| `GEMINI_API_KEY` | Google Gemini API key. **Never commit a real key.** |
| `DENSE_CANDIDATE_K` | Dense candidate pool size for hybrid fusion (default 20). |
| `BM25_CANDIDATE_K` | BM25 candidate pool size for hybrid fusion (default 20). |
| `RERANK_TOP_K` | Number of fused candidates sent to the cross-encoder (default 8). |
| `HYBRID_DENSE_WEIGHT` / `HYBRID_BM25_WEIGHT` | Fusion weights for normalized scores (default 0.6 / 0.4). |
| `RERANKER_MODEL` | Cross-encoder model (default `cross-encoder/ms-marco-MiniLM-L-6-v2`). |
| `RERANKER_BATCH_SIZE` | Cross-encoder inference batch size (default 8). |
| `CONFIDENCE_THRESHOLD` | Minimum top reranker relevance (0..1) before answering (default 0.35). |
| `DEMO_MODE` | `true` exposes the unauthenticated public demo (pre-indexed PDF, no upload); `false` keeps the local/self-hosted upload workflow (default). |
| `DEMO_DOCUMENT_PATH` | Path to the demo PDF. Absolute paths are used as-is; relative paths resolve against the backend working directory, walking up to the repo root (default `../Doc/DocMind_Public_Demo_Test_Document.pdf`). |
| `DEMO_DOCUMENT_ID` | Fixed row id of the demo document (default `11111111-1111-4111-8111-111111111111`). Do not change after building the index. |
| `DEMO_DOCUMENT_TITLE` | Display title of the demo document (default `DocMind Public Demo Test Document`). |
| `DEMO_CONFIDENCE_THRESHOLD` | Demo-only confidence gate over the lightweight TF-IDF retrieval score (default `0.05`). Not used by the local/Docker pipeline. |
| `NEXT_PUBLIC_API_URL` | Backend base URL baked into the frontend build (public, not a secret). |

---

## Public demo mode

Phase 9 adds a **public demo mode** so a deployed DocMind can be showcased
without asking visitors to upload a PDF, parse it, or wait for indexing. When
`DEMO_MODE=true`, the landing page becomes an unauthenticated chat UI anchored
to a single **pre-indexed** demo document (`Doc/DocMind_Public_Demo_Test_Document.pdf`)
with predefined example questions. The PDF is processed **once** at build time;
every visitor question only runs lightweight retrieval over the already-stored
chunks, so a public instance stays cheap on RAM and never re-reads, re-chunks or
re-embeds the PDF per request.

> **Memory-safe demo.** The public demo **never loads the embedding model
> (`BAAI/bge-base-en-v1.5`) or the cross-encoder reranker.** Query-time
> retrieval is a pure-Python TF-IDF cosine search over the prebuilt demo chunks
> (`retrieve_demo_evidence`), so the hosted process stays well under the Render
> memory limit. The full embedding + hybrid + rerank pipeline remains available
> for the local/Docker workflow (`DEMO_MODE=false`).

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

### How it works

- **Index once.** `python -m scripts.build_demo_index` (run from `backend/`)
  reads `DEMO_DOCUMENT_PATH`, extracts text, chunks with the project's existing
  chunking settings, embeds with `EMBEDDING_MODEL`, and stores the vectors in
  the **same persistent pgvector store** used by normal ingestion — no new
  vector database. Re-running is idempotent (existing demo chunks are replaced,
  never duplicated); use `--force` to rebuild from the current PDF.
- **Runtime reuses the index.** On startup, demo mode only *checks* readiness
  (logged); the demo chat endpoint never calls the build path. If the index is
  missing, `GET /api/demo/info` reports `status: "missing"` and
  `POST /api/demo/chat` returns a clear `503 DEMO_INDEX_MISSING` error instead
  of silently falling back to an empty store.
- **Query-time retrieval is model-free.** Each visitor question is answered by
  a lightweight TF-IDF cosine search over the stored demo chunks, then gated by
  `DEMO_CONFIDENCE_THRESHOLD` before the LLM is called. The embedding model and
  the cross-encoder reranker are **not** loaded in demo mode (only the build
  tool loads the embedding model to produce the stored vectors). The preset
  "Try asking" chips are real questions run through this same pipeline — they
  are never hardcoded answers — and visitors may ask their own questions too.
- **Upload is disabled while demo mode is on.** `POST /api/documents` (upload,
  process, version) returns `403 DEMO_MODE` so visitors cannot trigger arbitrary
  PDF processing. Set `DEMO_MODE=false` to restore the upload workflow.
- **Grounded answers only.** Demo chat reuses the exact Phase 5 RAG pipeline
  (hybrid retrieval → fusion → rerank → confidence gate → context → LLM →
  citations) scoped to the demo document id. The demo system prompt refuses
  out-of-scope questions with *"I couldn't find that information in the demo
  document. Try asking a question about the evaluation, metrics, or findings."*
  — general knowledge is never used for document questions. Provider/LLM
  failures also degrade to this grounded refusal rather than a 500.
- **Frontend.** The landing page calls `GET /api/demo/info` at runtime. When
  demo mode is active it renders the demo chat (document card, message history
  with Sources, a "Try asking" chip row, and the chat input); otherwise the
  standard landing page is shown unchanged. No frontend build flag is required.

### Enable the demo

```bash
# 1. Build the pre-indexed demo document (from backend/)
cd backend
python -m scripts.build_demo_index          # adds --force to rebuild

# 2. Run the API in demo mode
set DEMO_MODE=true                          # PowerShell; export DEMO_MODE=true on bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. (optional) a model that is currently available; see note below
set LLM_MODEL=gemini-2.5-flash
```

With Docker Compose the demo PDF is mounted into the backend container at
`/Doc` (read-only), so the default `DEMO_DOCUMENT_PATH=../Doc/…` resolves
inside the container:

```bash
docker compose exec backend python -m scripts.build_demo_index
# then set DEMO_MODE=true in your environment / root .env and restart the stack.
```

> **Model note.** The default `LLM_MODEL=gemini-flash-latest` can be unavailable
> during Google free-tier capacity spikes (HTTP 503 "high demand"); the demo
> then returns the grounded refusal, never a wrong answer. If that happens, set
> `LLM_MODEL` to a currently-available model (e.g. `gemini-2.5-flash`) in the
> environment before building/running the demo.

### Public deployment (Render + Vercel)

The demo runs on the same Render + Vercel setup described in
[Deployment](#deployment), with two extra steps:

1. Make the demo PDF reachable by the backend process — upload it to the
   persistent disk (e.g. `/data/demo/DocMind_Public_Demo_Test_Document.pdf`)
   and set `DEMO_DOCUMENT_PATH` to that path (absolute paths are used as-is),
   or bake the PDF into the image.
2. Set `DEMO_MODE=true`, `DEMO_DOCUMENT_ID`,
   `DEMO_DOCUMENT_TITLE`, and a working `LLM_MODEL` (see the note above).

The demo frontend is still the static Next.js build on Vercel; it needs no
extra environment variables (demo detection is a runtime API call).

---

## Database setup

The schema is managed with Alembic. The initial migration creates the
pgvector extension, all tables, indexes (including an HNSW index on
`document_chunks.embedding`), and the `feedback.rating` CHECK constraint.

```bash
cd backend

# create a new migration from the ORM models
python -m alembic revision --autogenerate -m "describe change"

# apply migrations
python -m alembic upgrade head

# verify the DB schema matches the models (should print "No new upgrade operations detected.")
python -m alembic check

# show current revision
python -m alembic current
```

> The Docker backend runs `alembic upgrade head` automatically on startup,
> so `docker compose up` keeps the schema current without manual steps.

---

## Docker setup

DocMind ships two Compose stacks:

| File | Purpose |
|------|---------|
| `docker-compose.yml` | **Self-hosted production** — the full application, production build, persistent volumes. This is what end users run. |
| `docker-compose.dev.yml` | **Development** — hot-reload, bind-mounted sources, `uvicorn --reload`, `next dev`. |

The self-hosted stack is the primary way to run DocMind. The development stack
is for people working on the source code. See
[Self-hosted Docker](#self-hosted-docker) for the full self-hosted workflow and
[Development workflow](#development-workflow) for the dev stack.

---

## Self-hosted Docker

This is the recommended way to run the full DocMind application locally. It
requires **no host installs** — Python, Node.js, PostgreSQL, pgvector,
PyTorch and the ML models all live inside containers.

### 1. Requirements

- **Docker Desktop** (Windows/macOS) or Docker Engine + Compose v2 (Linux).
- **Memory:** at least **8 GB RAM** recommended. The BGE embedder (~400 MB)
  and the cross-encoder reranker are loaded into the backend process; on first
  PDF processing both are in memory. Do not run this stack on a 512 MB box.
- **Disk:** ~10 GB free for images, the Hugging Face model cache and uploaded
  documents.

### 2. First-time setup

```bash
git clone <repo-url> DocMind
cd DocMind

cp .env.example .env
```

### 3. Configure `.env`

Edit `.env` and set at minimum:

```bash
# Strong random password for PostgreSQL
POSTGRES_PASSWORD=change-me-strong-password

# JWT signing key (32+ random bytes)
SECRET_KEY=change-me-64-char-random-string

# Google AI Studio API key (https://aistudio.google.com/apikey)
GEMINI_API_KEY=AIza...
```

Optional overrides you may also want:

| Variable | Default | Notes |
|----------|---------|-------|
| `POSTGRES_USER` / `POSTGRES_DB` | `docmind` | Database credentials |
| `LLM_PROVIDER` | `gemini` | `gemini` (needs key) or `local` (offline dev only) |
| `CORS_ORIGINS` | `http://localhost:3000` | Frontend origin(s) allowed to call the API |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL baked into the frontend build |
| `STORAGE_DIR` | `/data/storage` | Uploaded-document root (persistent volume) |
| `HF_HOME` | `/data/huggingface` | Model cache (persistent volume) |

### 4. Gemini API key

Get a key from [Google AI Studio](https://aistudio.google.com/apikey) and put
it in `.env` as `GEMINI_API_KEY=AIza...`. The key is passed only to the
backend container; it is **never** baked into the frontend image and never
exposed to the browser.

If you do not set a key, the chat/search endpoints will return the grounded
fallback for Gemini (or you can set `LLM_PROVIDER=local` for an offline
answerer — not for production use).

### 5. Start DocMind

```bash
docker compose up -d --build
```

First run downloads the models from Hugging Face (BGE embedder +
cross-encoder), so it takes longer. Subsequent runs reuse the persisted cache.

### 6. Access the UI

Open **http://localhost:3000**:

- Register an account (always created as `STUDENT`), then log in.
- The backend API is available at **http://localhost:8000** (`/docs` for
  Swagger UI).
- PostgreSQL is **not** exposed to the host.

### 7. Stop DocMind

```bash
docker compose down
```

This stops the containers but **keeps all data** (database, uploaded
documents, model cache) in named volumes.

### 8. Restart DocMind

```bash
docker compose up -d
```

Reuses the existing volumes and the persisted model cache — no re-download,
no data loss.

### 9. Persistent data

All persistent state lives in named Docker volumes:

| Volume | Backs | Survives `docker compose down` |
|--------|-------|--------------------------------|
| `docmind_pgdata` | PostgreSQL data | Yes |
| `docmind_backend_storage` | Uploaded documents (`STORAGE_DIR`) | Yes |
| `docmind_hf_cache` | Hugging Face model cache (`HF_HOME`) | Yes |

Because the backend storage and model cache are volumes, uploaded PDFs and
the downloaded models survive container recreation and restarts.

### 10. Remove all data (completely reset)

```bash
docker compose down -v
```

`-v` deletes the named volumes (`pgdata`, `backend_storage`, `hf_cache`). This
erases the database, uploaded documents and the model cache (the models will
re-download on the next start).

To also remove the images:

```bash
docker compose down -v --rmi all
```

### 11. Model download / cache behavior

The first `POST /api/documents/{id}/process` triggers a download of
`BAAI/bge-base-en-v1.5`; the first chat/search request downloads
`cross-encoder/ms-marco-MiniLM-L-6-v2`. Both are cached in `/data/huggingface`
(the `hf_cache` volume). Models load lazily (on first use) and are shared as
in-process singletons, so a single backend worker avoids duplicate memory.

### 12. Docker architecture

```
Browser
   │
   ▼
frontend :3000  (production Next.js build, `npm start`)
   │  browser calls the API directly
   ▼
backend :8000   (FastAPI, single uvicorn worker, applies Alembic migrations)
   │
   ▼
PostgreSQL :5432  (internal only — not published to the host)
```

- **One backend worker** — the embedding and reranker models are process-local
  singletons; extra workers would duplicate their memory.
- **Automatic migrations** — the backend runs `alembic upgrade head` before
  uvicorn starts, so the schema is kept current on every startup.
- **Health checks** — the backend container is health-checked against
  `GET /api/health` (which verifies DB connectivity); the frontend waits for
  the backend to be healthy before serving, and the backend waits for the
  database healthcheck. No arbitrary sleeps.

### 13. Troubleshooting

- **"Connection refused" on `localhost:3000`** — wait for the first `--build`
  to finish; frontend containers are often still building.
- **First PDF process is very slow / appears hung** — the BGE model is
  downloading on first use; give it a minute (see `docker compose logs -f
  backend`).
- **Out-of-memory during processing** — the stack needs ~8 GB. Close other
  apps or increase Docker Desktop's memory limit (Settings → Resources).
- **Backend logs show `Could not connect to server` for the database** — the
  DB healthcheck may still be warming up; the backend waits on it. Check
  `docker compose logs db`.
- **Chat returns the grounded fallback even with documents** — either no
  evidence cleared the confidence gate (try a question with keywords from the
  document) or the Gemini key is missing/invalid (see `docker compose logs
  backend`).
- **Port 3000 or 8000 already in use** — stop the conflicting service or
  change the published ports in `docker-compose.yml`.

### 14. Production vs development workflow

| Aspect | Self-hosted (`docker-compose.yml`) | Development (`docker-compose.dev.yml`) |
|--------|-----------------------------------|----------------------------------------|
| Backend | Production image, single worker, no reload | `--reload`, bind-mounted `./backend` |
| Frontend | Production build (`npm start`) | `next dev`, bind-mounted `./frontend` |
| PostgreSQL port | Not exposed | Published on `5432` |
| Data | Named volumes (persistent) | Named volumes (persistent) |
| Command | `docker compose up -d --build` | `docker compose -f docker-compose.dev.yml up --build` |

The Docker package runs the **full** DocMind application — authentication, PDF
ingestion, embeddings, hybrid retrieval, reranking, Gemini answers, citations,
conversations, search, feedback, versioning and admin. It is not a demo or a
stripped-down build.

---

## Running locally

### Development workflow (Docker)

If you are developing DocMind, use the dev Compose stack which hot-reloads
both the backend and frontend:

```bash
# start the dev stack (db + backend + frontend)
docker compose -f docker-compose.dev.yml up --build

# watch logs
docker compose -f docker-compose.dev.yml logs -f

# stop (keeps the database volume)
docker compose -f docker-compose.dev.yml down
```

The dev stack bind-mounts `./backend` and `./frontend` for hot-reload, runs
`uvicorn --reload` and `next dev`, and publishes PostgreSQL on `5432` for
local tooling.

### Backend (host)

```bash
cd backend
python -m venv .venv                 # once
source .venv/bin/activate            # Linux/macOS  (Windows: .venv\Scripts\activate)
# Install CPU-only torch first so pip does not pull CUDA wheels:
pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.3,<3.0"
pip install -r requirements.txt

# ensure PostgreSQL is running (e.g. `docker compose up -d db` from the repo root)
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

On first `POST /api/documents/{id}/process` the embedding model
(`EMBEDDING_MODEL`) is downloaded from Hugging Face and cached locally; the
cross-encoder reranker (`RERANKER_MODEL`) is downloaded on the first chat or
search request. GPU is not required (CPU inference works).

> Development note: the dev frontend container shares `./frontend/.next` with
> the host via the bind mount. After running `npm run build` on the host and
> then starting `docker compose -f docker-compose.dev.yml up`, remove
> `frontend/.next` once so the container rebuilds its dev bundle cleanly.

### Frontend (host)

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
npm run typecheck      # tsc --noEmit
npm run build          # production build
```

### Health checks

- API: `GET http://localhost:8000/api/health`
  → `{"status":"ok","version":"0.1.0","environment":"development","database":"ok"}`
- Interactive docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000` (landing page renders live backend health)

### Tests

Backend tests use a dedicated database (default `docmind_test`) so they never
touch development data. The test suite creates the test database automatically
if it is missing.

```bash
cd backend
pip install -r requirements-dev.txt     # pytest + httpx
python -m pytest app/tests -q
```

Current suite: **252 tests** covering authentication, RBAC, document
validation/upload, extraction, chunking, embeddings, processing status
transitions, the full document API, the Phase 4 RAG pipeline (retrieval
ranking + permission filtering, context assembly, LLM provider, citations,
chat/search API), Phase 5 retrieval (BM25 ranking and permissions, score
normalization, hybrid fusion, reranker ordering/metadata, confidence gates),
Phase 6 product features (conversations, feedback, versioning, admin,
user-facing search) and the Phase 7 evaluation harness
(`test_evaluation_*.py`).

---

## API documentation

Interactive OpenAPI docs are available at `/docs` (and `/redoc`) on the
backend. Endpoints planned across the project:

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/health` | Health check *(implemented, Phase 1)* |
| POST | `/api/auth/register` | Create account *(implemented, Phase 2)* |
| POST | `/api/auth/login` | Issue JWT *(implemented, Phase 2)* |
| GET  | `/api/auth/me` | Current user *(implemented, Phase 2)* |
| GET  | `/api/admin/test` | RBAC check (ADMIN only) *(implemented, Phase 2)* |
| POST | `/api/documents` | Upload a PDF *(implemented, Phase 3)* |
| GET  | `/api/documents` | List documents *(implemented, Phase 3)* |
| GET  | `/api/documents/{id}` | Document detail *(implemented, Phase 3)* |
| PATCH | `/api/documents/{id}` | Edit metadata *(implemented, Phase 3)* |
| DELETE | `/api/documents/{id}` | Delete document *(implemented, Phase 3)* |
| POST | `/api/documents/{id}/process` | Trigger ingestion *(implemented, Phase 3)* |
| POST | `/api/chat` | Ask a grounded question (RAG) *(implemented, Phase 4/5; conversation-aware, Phase 6)* |
| POST | `/api/search` | Raw hybrid search, no LLM *(implemented, Phase 4/5)* |
| POST | `/api/search/results` | User-facing search, no raw internals *(implemented, Phase 6)* |
| GET  | `/api/conversations` | List conversations *(implemented, Phase 6)* |
| GET  | `/api/conversations/{id}` | Conversation detail *(implemented, Phase 6)* |
| DELETE | `/api/conversations/{id}` | Delete conversation *(implemented, Phase 6)* |
| POST | `/api/feedback` | Rate an answer *(implemented, Phase 6)* |
| GET  | `/api/documents/{id}/versions` | List document versions *(implemented, Phase 6)* |
| POST | `/api/documents/{id}/versions` | Upload a new version *(implemented, Phase 6)* |
| GET  | `/api/admin/users` | List users (ADMIN) *(implemented, Phase 6)* |
| GET  | `/api/admin/documents` | List documents (ADMIN) *(implemented, Phase 6)* |
| GET  | `/api/admin/stats` | System statistics (ADMIN) *(implemented, Phase 6)* |
| PATCH | `/api/admin/users/{id}/role` | Change a user's role (ADMIN) *(implemented, Phase 6)* |
| GET  | `/api/demo/info` | Public demo metadata + index readiness *(implemented, Phase 9; demo mode only)* |
| POST | `/api/demo/chat` | Grounded demo chat scoped to the pre-indexed PDF *(implemented, Phase 9; demo mode only)* |

### Authentication (Phase 2)

- `POST /api/auth/register` — body `{name, email, password}` (JSON). Always
  creates a `STUDENT`; any client-supplied role is rejected. Returns the new
  user (no token).
- `POST /api/auth/login` — `application/x-www-form-urlencoded`
  `username` + `password` (OAuth2 password form, so Swagger UI's "Authorize"
  button works). Returns `{access_token, token_type, user}`.
- `GET /api/auth/me` — requires `Authorization: Bearer <token>`. Returns the
  current user; the frontend calls this on load to restore a session.
- Roles are stored uppercase (`STUDENT`, `FACULTY`, `ADMIN`). Endpoints declare
  their required role via `require_role` dependencies; access is enforced
  server-side regardless of the UI.
- Tokens: HS256 signed with `SECRET_KEY`, expiry `ACCESS_TOKEN_EXPIRE_MINUTES`
  (default 30). On the frontend the token lives in `localStorage` under
  `docmind_token` (dev-tier persistence; passwords are never stored).

Errors use a consistent envelope — never raw stack traces:

```json
{
  "error": {
    "code": "DOCUMENT_PROCESSING_FAILED",
    "message": "The document could not be processed."
  }
}
```

Auth-specific codes: `AUTHENTICATION_REQUIRED`, `INVALID_CREDENTIALS`,
`INVALID_TOKEN`, `TOKEN_EXPIRED`, `EMAIL_ALREADY_REGISTERED`, `FORBIDDEN`.

### Documents (Phase 3)

All document endpoints require authentication. Upload takes
`multipart/form-data` (`file` + optional `title`, `description`, `department`,
`category`, `effective_date`). Immutable fields such as status, uploader and
storage paths cannot be changed via PATCH.

- **Validation** rejects non-PDF files by extension, MIME type or magic bytes
  (`INVALID_DOCUMENT_TYPE`), empty files (`EMPTY_DOCUMENT`) and oversized
  files (`DOCUMENT_TOO_LARGE`).
- **Lifecycle** `UPLOADED → PROCESSING → ACTIVE`; failures leave the document
  `FAILED` with a safe internal `processing_error` (never exposed via the API,
  never a stack trace). Reprocessing replaces old chunks, so retries are safe.
- **Authorization** is server-side. A document is *visible* when the user
  uploaded it or its `access_level` matches their role (`PUBLIC` is viewable
  by everyone). Only the uploader or an `ADMIN` may edit, process or delete.
- **Storage** is local and replaceable: `STORAGE_DIR` → `documents/<id>/`.
  Internal paths are never returned by the API.
- **Embeddings** use the configured `EMBEDDING_MODEL`
  (`BAAI/bge-base-en-v1.5` by default, 768 dims matching `EMBEDDING_DIM`). The
  model is loaded once per process and rejected if its dimension does not
  match the configured value.

Document error codes: `DOCUMENT_NOT_FOUND`, `FORBIDDEN`,
`INVALID_DOCUMENT_TYPE`, `EMPTY_DOCUMENT`, `DOCUMENT_TOO_LARGE`,
`DOCUMENT_PROCESSING_FAILED`.

### Chat & search (Phase 4/5)

Both endpoints require authentication and are permission-aware server-side.

- `POST /api/chat` — body `{"message": "<question>", "conversation_id": null | "<id>"}`.
  Runs the Phase 5 RAG pipeline over the documents the user can see and returns
  `{answer, citations, conversation_id, message_id}`. When no evidence meets the
  retrieval thresholds, evidence is below `CONFIDENCE_THRESHOLD`, or the LLM
  fails, the answer is the fixed grounded fallback: *"I couldn't find sufficient
  information in the available university documents."* Citations resolve the
  model's source tags to actual retrieved chunks; each citation includes
  `relevance_score` (the final reranker score, 0..1) plus `document_id`,
  `document_title` and `section` (`null` when the document does not provide
  one). With `conversation_id` omitted, a new conversation is created and the
  exchange is persisted (Phase 6).
- `POST /api/search` — body `{"query": "..."}`. Developer/debug endpoint that
  returns raw hybrid retrieval results (`{results: [...]}`) without calling an
  LLM. Each result exposes the per-stage scores — `dense_score` (pgvector
  cosine similarity), `bm25_score` (min-max normalized `ts_rank_cd`),
  `hybrid_score` (weighted fusion of the two), and `rerank_score` (sigmoid of
  the cross-encoder logit). `score` is a legacy alias equal to `dense_score`.
- `POST /api/search/results` — body `{"query": "..."}` (Phase 6). Same retrieval
  as `/api/search` but returns clean, user-facing results (`document_title`,
  `page_number`, `section`, `snippet`, `relevance_score`) with no raw scores or
  chunk ids.
- Chat error codes: `MESSAGE_EMPTY`, `MESSAGE_TOO_LONG`, `CONVERSATION_NOT_FOUND`.

The LLM provider is selected by `LLM_PROVIDER`:
`gemini` (default; requires `GEMINI_API_KEY`, model `LLM_MODEL`) or `local`
(offline development provider — answers verbatim from the top chunk, never for
production).

---

## RAG pipeline

Phase 5 implements **hybrid retrieval → fusion → cross-encoder reranking →
confidence gate → context → LLM → citations**. The pipeline runs entirely
server-side; permission filtering is part of every retrieval query, never
frontend filtering.

1. **Query processing** — the question is embedded with the same BGE model
   used for ingestion (`EMBEDDING_MODEL`).
2. **Permission filtering** — chunks are retrieved only from documents the
   user can see (uploader or access-level match). The filter is applied in the
   SQL `WHERE` clause of *both* retrievers, *before* ranking.
3. **Dense retrieval** — top `DENSE_CANDIDATE_K` chunks by cosine distance
   (`embedding <=> query`) via the HNSW index; chunks below
   `RETRIEVAL_MIN_SIMILARITY` are discarded.
4. **BM25 retrieval** — top `BM25_CANDIDATE_K` chunks ranked by PostgreSQL FTS
   `ts_rank_cd` over the generated `searchable_content` tsvector.
5. **Fusion** — the two pools are deduplicated by chunk id; dense and BM25
   scores are min-max normalized separately, then combined as
   `hybrid_score = HYBRID_DENSE_WEIGHT·norm(dense) + HYBRID_BM25_WEIGHT·norm(bm25)`.
6. **Reranking** — the top `RERANK_TOP_K` fused candidates are re-scored by a
   cross-encoder against the question; `rerank_score` (sigmoid of the logit)
   decides the final order.
7. **Confidence gate** — if the best evidence does not clear
   `CONFIDENCE_THRESHOLD`, the grounded fallback is returned and the LLM is
   never called.
8. **Context builder** — winning chunks are labelled `[1]…[n]` and assembled,
   truncating whole chunks to `MAX_CONTEXT_CHARS`.
9. **LLM generation** — a provider-agnostic client (Gemini default, `local`
   offline for development) answers strictly from the supplied context and is
   explicitly told to ignore any instructions embedded in the evidence
   (prompt-injection hardening). With insufficient evidence it returns the
   fixed grounded fallback.
10. **Citations** — source tags in the answer are resolved against the
    retrieved chunks into structured citations, each carrying the reranker
    `relevance_score`.

Failure handling degrades gracefully: a BM25 failure falls back to dense-only,
a dense failure to BM25-only, and a reranker outage returns the hybrid-fused
order.

Example citation payload returned by the API:

```json
{
  "answer": "The minimum attendance requirement is 75%.",
  "citations": [
    {
      "document_id": "…",
      "document_title": "Examination Ordinance 2026",
      "page_number": 14,
      "section": "Attendance",
      "relevance_score": 0.91
    }
  ]
}
```

---

## Evaluation methodology

Phase 7 adds a reproducible evaluation harness in `backend/evaluation/`. All
numbers below were actually measured on this machine (embedding
`BAAI/bge-base-en-v1.5`, reranker `cross-encoder/ms-marco-MiniLM-L-6-v2`,
2-document corpus). They are indicative of this corpus and setup, not a claim
about larger corpora.

**Dataset** — `evaluation/dataset.json` (version 1.0, 56 questions: 43
answerable + 13 unanswerable). Ground truth was hand-verified against the
extracted text of the two real corpus PDFs (`academic_regulations.pdf`,
`RAG_Test_Document_Edge_Cases.pdf`); it is never generated by the model under
test. Categories: semantic, keyword, entity, numeric, multi-fact, edge
(conflicting drafts, prompt injection), unanswerable. Each item records
`expected_answer`, `expected_answer_terms`, `relevant_documents`,
`relevant_pages` and `supporting_text` fragments used for relevance judgement.

**Modes** — the same 56 questions run through the real production services on
an isolated `docmind_eval` database:

- `baseline` (Phase 4): single dense pgvector lookup, no confidence gate.
- `phase5` (Phase 5): dense + BM25 candidate pools → weight fusion →
  cross-encoder rerank, with the confidence gate.

Both use an evaluation window of top-10 so Recall@10 is defined.

**Metrics** — retrieval: `Recall@1/3/5/10`, `MRR@10`, document-level recall;
end-to-end: answer accuracy, fallback rate, deterministic faithfulness rubric
(0/1/2), citation validity/support, per-stage latency (mean/median/P95);
phase5-only: confidence-gate 2×2 (accepted/rejected × answerable/unanswerable)
and failure classification (confidence rejection, retrieval miss, LLM refusal,
hallucination, wrong answer, LLM error).

**Reproducing** (run from `backend`, Postgres + models cached):

```bash
python -m evaluation.run_evaluation --mode baseline --llm-provider gemini
python -m evaluation.run_evaluation --mode phase5  --llm-provider gemini
python -m evaluation.run_evaluation --compare
```

Flags: `--limit N`, `--category NAME`, `--output PATH`, `--skip-generation`
(retrieval only), `--llm-provider local|gemini`,
`--llm-min-interval <seconds>` (rate-limit throttle for paid APIs). Results
land in `evaluation/results/` (`baseline.json`, `phase5.json`,
`comparison.json`, `report.md`). Unit tests for the harness live in
`app/tests/test_evaluation_*.py`.

**Latest measured results (2026-08-14, dataset 1.0, 56 questions):**

| Retrieval (answerable) | Baseline | phase5 | Δ |
| --- | --- | --- | --- |
| Recall@1 | 0.5814 | 0.8837 | +0.3023 |
| Recall@3 | 0.5814 | 0.8837 | +0.3023 |
| Recall@5 | 0.5814 | 0.8837 | +0.3023 |
| Recall@10 | 0.5814 | 0.8837 | +0.3023 |
| MRR@10 | 0.5814 | 0.8837 | +0.3023 |
| Doc recall@1 / @5 / @10 | 0.5814 | 0.8837 | +0.3023 |

> On this 2-document corpus a relevant chunk, when retrieved, always lands at
> rank 1 and is missed at every rank otherwise, so Recall@1/3/5/10 and MRR
> coincide; each metric is still computed independently per question.

| Confidence gate (phase5) | Count | Rate |
| --- | --- | --- |
| Answerable total | 43 | — |
| Answerable accepted | 38 | accuracy 0.4474 |
| Answerable rejected (all have corpus evidence) | 5 | false rejection rate 0.1163 |
| Unanswerable total | 13 | — |
| Unanswerable rejected (correct refusal) | 7 | correct rejection rate 0.5385 |
| Unanswerable accepted (false acceptance) | 6 | false acceptance rate 0.4615 |
| Abstention (all rejected / total) | 12 | 0.2143 |

> **False acceptance rate = accepted unanswerable / total unanswerable =
> 6/13 = 46.15%** (per the Phase 7 audit definition). An earlier report
> labelled the *correctness rate among accepted unanswerable* (0/6 = 0.0) as
> "false acceptance", which was wrong terminology; the corrected metric above
> is the honest figure. The 5 answerable rejections each have their evidence
> present in the corpus (retrieval failed to surface it: dense below the 0.65
> min-similarity cutoff and a BM25 AND-term mismatch), so they are false
> rejections caused by retrieval, not a dataset error.

| Latency (mean / median / p95 ms) | Baseline | phase5 |
| --- | --- | --- |
| Dense | 73.4 / 71.4 / 83.7 | 70.3 / 70.4 / 73.4 |
| BM25 | — | 2.3 / 2.2 / 3.1 |
| Rerank | — | 56.4 / 49.1 / 140.2 |
| End-to-end | 73.5 / 71.6 / 83.8 | 120.1 / 101.4 / 207.1 |

**Honest caveats.** Answer/faithfulness/citation columns in
`results/report.md` were produced with the **local deterministic provider**
(the offline test stub), because the Gemini free tier was quota-exhausted
(HTTP 429) during today's run. Those columns are an end-to-end harness check,
not a measure of the production LLM. Retrieval, confidence-gate and latency
numbers are real and provider-independent. The gate correctly refused all 7
unanswerable questions it rejected and blocked all 5 answerable questions
where retrieval surfaced no evidence, but it also **accepted 6 of 13
unanswerable questions (false acceptance rate 46.15%)**; with the local stub
each was answered incorrectly, though a real LLM would likely still refuse
some of them. No threshold was tuned and no dataset labels were changed to
improve any number.

---

## Development roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Foundation: repo, Docker, PostgreSQL+pgvector, FastAPI, Next.js, models, Alembic, health checks | ✅ Done |
| 2 | Authentication: register, login, JWT, password hashing, roles, protected routes | ✅ Done |
| 3 | Document ingestion: PDF upload, extraction, page tracking, chunking, embeddings, pgvector storage | ✅ Done |
| 4 | Basic RAG: semantic retrieval, context building, LLM integration, answers, citations | ✅ Done |
| 5 | Advanced retrieval: BM25, hybrid ranking, cross-encoder reranking, confidence threshold | ✅ Done |
| 6 | Product features: conversations, feedback, versioning, role-based access, admin, search | ✅ Done |
| 7 | Evaluation: dataset, retrieval metrics, RAG metrics, report | ✅ Done |
| 8 | Polish: error handling, tests, loading/empty states, responsive UI, docs | ✅ Done |
| 9 | Public demo mode: pre-indexed PDF, demo chat UI, example questions, RAM-light runtime | ✅ Done |

Each phase keeps the project runnable.

---

## Future improvements

- Background ingestion workers (Celery / arq / FastAPI BackgroundTasks) so
  large PDFs do not block the API.
- OCR pipeline integration for scanned documents (interface designed in the
  ingestion service).
- Streaming LLM responses with citation-aware rendering.
- Fine-grained analytics over feedback and failed-document errors.
- Deployment hardening: reverse proxy (TLS), secrets manager, read replicas,
  pgvector index tuning (ivfflat vs hnsw, `lists`/`m` parameters).

---

## Known limitations

These are intentional, documented trade-offs of the current implementation,
not undiscovered bugs.

- **Small evaluation corpus.** Measured retrieval/confidence numbers are from a
  2-document, 56-question evaluation set. Recall@1/3/5/10 and MRR coincide on
  this corpus (a relevant chunk either ranks #1 or is missed entirely), so they
  are indicative but not a claim about larger corpora.
- **Confidence gate is not a hallucination shield.** Phase 7 measured a **false
  acceptance rate of 46.15%** (6 of 13 unanswerable questions were accepted;
  the local evaluation stub then answered them incorrectly). A production LLM
  would likely refuse some of those, but the gate alone is insufficient — do
  not rely on it to refuse out-of-scope questions.
- **5 answerable questions are falsely rejected** (Q004, Q016, Q024, Q030,
  Q042): their evidence is in the corpus but retrieval misses it (dense cosine
  below the 0.65 cutoff and a BM25 AND-term mismatch). Tuning thresholds or the
  fusion weights could trade this off against more false acceptance; none was
  tuned for Phase 7.
- **`section` citations are often `null`.** Phase 3 chunking does not populate
  a section column, so citations surface `section=None` rather than fabricating
  one.
- **Gemini free-tier quota.** The Gemini-backed answer column in the Phase 7
  report was produced with the local deterministic provider because the free
  tier was quota-exhausted (HTTP 429). Retrieval, confidence-gate and latency
  numbers are provider-independent and real.
- **Single-server dev posture.** Local file storage, in-process (CPU)
  embedding/reranking and a synchronous ingestion request mean uploads block
  the API while processing. Designed for a demo/small-instance workload; see
  [Future improvements](#future-improvements).
- **JWT in `localStorage`.** Dev-tier session persistence; a hardened
  deployment should move to httpOnly cookies or a token store (see
  [Security](#security)).

---

## Security

- **Server-side authorization everywhere.** Every protected endpoint resolves
  the user from the JWT (`app/api/deps.py`) and enforces roles via
  `require_role`. Retrieval, documents, conversations and feedback all apply
  ownership / visibility rules in the backend — the frontend is never trusted.
  Non-owners of a conversation or document receive a 404 (existence hidden) or
  403 as appropriate; `STUDENT`/`FACULTY` cannot reach admin endpoints; the
  last `ADMIN` cannot be demoted.
- **Prompt-injection hardening.** The system prompt (`app/rag/prompts.py`)
  treats retrieval evidence as untrusted data and instructs the model to never
  follow instructions embedded in it. Evidence is delimited and labelled
  `[n]` before it reaches the LLM.
- **No secrets in version control.** A Phase 8 secrets scan (Google API key,
  `sk-`-style tokens, `SECRET_KEY`/password assignments) over all tracked
  files found only the documented dev placeholders. Real keys live only in
  untracked `.env` files (git-ignored).
- **Credential hygiene.** Passwords are bcrypt-hashed and never logged;
  registration rejects client-supplied roles; login returns the same error for
  an unknown email and a wrong password (no user enumeration); API responses
  never expose password hashes, storage paths or raw stack traces (structured
  `{error:{code,message}}` envelope).
- **Upload validation.** PDFs are rejected by extension, MIME type, `%PDF-`
  magic bytes, size and empty content before any extraction.
- **Production hardening checklist.** Replace `SECRET_KEY` and
  `POSTGRES_PASSWORD` with strong random values, set `CORS_ORIGINS` to the real
  frontend origin, set `DEBUG=false`, provide a real `GEMINI_API_KEY`, and move
  JWT storage to httpOnly cookies. See [Deployment](#deployment).

---

## Deployment

DocMind ships as a Docker Compose stack (database + backend + frontend) for
single-host deployments (see [Self-hosted Docker](#self-hosted-docker)). There
is no shared hosted instance.

**Production checklist**

1. Set strong, unique values for `SECRET_KEY` and `POSTGRES_PASSWORD` (root
   `.env`; both have non-production dev defaults in `docker-compose.yml`).
2. Set `CORS_ORIGINS` to your real frontend origin(s) and `DEBUG=false`.
3. Provide a real `GEMINI_API_KEY` (or set `LLM_PROVIDER=local` for a
   non-production offline answerer).
4. Put the app behind a reverse proxy (nginx / Caddy) that terminates TLS and
   proxies `/` to the frontend (:3000) and `/api` to the backend (:8000).
5. Back up the `pgdata`, `backend_storage` and `hf_cache` volumes (database,
   uploaded documents and model cache).
6. Verify migrations: the backend runs `alembic upgrade head` on startup and
   `python -m alembic check` reports no drift.

```bash
docker compose up -d --build
```

Then verify `GET http://<host>/api/health` → `{"status":"ok", ...}`.

**Scaling considerations** (not implemented): see
[Future improvements](#future-improvements) — background ingestion, read
replicas and managed storage would be the first steps for a larger deployment.

### Render (backend + database) + Vercel (frontend)

The frontend is a fully static Next.js build (all routes prerender), so it
deploys on Vercel with no Dockerfile, and the backend deploys on Render as a
Docker Web Service against Render's managed PostgreSQL (which ships the
`pgvector` extension).

**Render — managed PostgreSQL**

- Region close to the web service; note the **Internal Database URL**.
- Render's URL is `postgresql://…`; the app expects the psycopg driver
  explicitly, so set `DATABASE_URL` to the internal URL with the scheme
  rewritten to `postgresql+psycopg://`.

**Render — Web Service (Docker)**

- The Dockerfile installs CPU-only torch and runs migrations itself, so **no
  Start Command override is needed** — it already executes
  `alembic upgrade head && uvicorn app.main:app --port $PORT` (defaults to
  8000 for compose/local, `$PORT` on Render).
- Environment variables:

  | Variable | Value |
  |----------|-------|
  | `DATABASE_URL` | Internal URL, scheme rewritten to `postgresql+psycopg://` |
  | `SECRET_KEY` | Strong random string (32+ bytes) |
  | `CORS_ORIGINS` | `https://<your-app>.vercel.app` |
  | `GEMINI_API_KEY` | Real key (only needed with `LLM_PROVIDER=gemini`) |
  | `APP_ENV` | `production` |
  | `DEBUG` | `false` |
  | `EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` |
  | `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
  | `STORAGE_DIR` | `/data/storage` |
  | `HF_HOME` | `/data/huggingface` |

- **Persistent Disk** (required): mount a disk at `/data`. Without it the BGE
  embedding model (~400 MB) and cross-encoder re-download on every deploy and
  uploaded PDFs are lost on restart.
- **Health check path**: `/api/health` (unauthenticated; returns 503 when the
  database is unreachable).
- **Instance size**: at least 1 GB RAM (free tier 0.5 GB may OOM when both the
  BGE embedder and the reranker load). CPU-only inference, 1 worker — correct,
  because the models are in-process singletons.

**Vercel — frontend**

- Import the repo (framework auto-detected as Next.js). No build config needed.
- Environment variable: `NEXT_PUBLIC_API_URL=https://<your-backend>.onrender.com`
  (build-time; required — the default is localhost).
- Preview deployments call the same backend, so their preview URL must be added
  to the backend's `CORS_ORIGINS` (or the backend must allow the preview
  origin) before the frontend can reach the API from a preview.

---

## Demo checklist

A 5-minute walkthrough against the self-hosted stack (`docker compose up -d --build`):

1. **Landing page** — `http://localhost:3000` renders the live backend health
   card (API status `ok`, database `ok`).
2. **Registration** — "Create account"; a new user is always a `STUDENT`.
3. **Login** — sign in; the dashboard loads your empty conversations list and
   document list.
4. **Upload** — drop in `backend/evaluation/corpus/academic_regulations.pdf`;
   it appears as `UPLOADED`.
5. **Process** — "Process" → status becomes `ACTIVE` (first run downloads the
   BGE embedding model, so allow a minute).
6. **Ask a grounded question** — e.g. *"What is the minimum attendance
   requirement?"* → a sourced answer with a "Sources (n)" list carrying page
   numbers; rate it 👍/👎.
7. **Persistent conversations** — the conversation appears in the sidebar with
   a generated title; follow up with a second question; reload the page and
   reopen it.
8. **Chat failure behavior** — submit a question with the backend stopped: the
   input keeps your question and an error alert appears (Phase 8 fix).
9. **Search** — `/search` returns clean, permission-aware results with match
   percentages and no raw scores; an out-of-scope query shows the empty state.
10. **Mobile** — narrow the window below 640 px: the nav collapses into the
    hamburger menu, and Dashboard / Search / Admin all remain reachable.
11. **Admin (optional)** — login as an `ADMIN` user (promote one via the
    `PATCH /api/admin/users/{id}/role` endpoint) to see stats, the user list
    and role management; a non-admin is blocked server-side.
12. **Versioning** — on a document, "Versions" → "Upload new version" adds a
    v2 entry; reprocess to make it active.

**Public demo walkthrough** (with `DEMO_MODE=true`):

1. **Landing page** — `http://localhost:3000` renders the demo chat (no upload,
   no account): a "Demo Document / DocMind Public Demo Test Document" card with
   a "Public demo" badge.
2. **Example questions** — click any "Try asking" chip; it is sent automatically
   and appears as your own chat message.
3. **Grounded answers** — e.g. *"What were the retrieval recall and answer
   accuracy of Hybrid + Reranking?"* → 91% recall / 87% accuracy with a
   "Sources (n)" list pointing at the demo document.
4. **Refusal** — *"What is the capital of France?"* → *"I couldn't find that
   information in the demo document…"* (no hallucination from general
   knowledge).
5. **Loading state** — while the LLM answers, the thread shows
   *"Retrieving relevant sections…"*.
6. **Missing index** — if the index was never built, `/api/demo/info` reports
   `missing` and the page shows the build-script instruction.

---

## License

Academic project — internal use. See your institution's project guidelines.
