# Development Guide

How to set up a local development environment for DocMind.

---

## Prerequisites

### Docker Development (recommended)

- **Docker Desktop** (Windows/macOS) or Docker Engine + Compose v2 (Linux)
- **~8 GB RAM** (embedding and reranker models run in-process on CPU)
- **~10 GB disk** for images, model cache, and documents

### Host Development

- Python 3.13
- Node.js 20+
- Docker (for the PostgreSQL + pgvector database)
- Git

---

## Development Docker Stack

The dev Compose stack hot-reloads both backend and frontend:

```bash
# Start (db + backend + frontend with hot-reload)
docker compose -f docker-compose.dev.yml up --build

# Watch logs
docker compose -f docker-compose.dev.yml logs -f

# Stop (keeps database volume)
docker compose -f docker-compose.dev.yml down
```

The dev stack bind-mounts `./backend` and `./frontend` for hot-reload, runs `uvicorn --reload` and `next dev`, and publishes PostgreSQL on `5432` for local tooling.

### Production vs Development

| Aspect | Production (`docker-compose.yml`) | Development (`docker-compose.dev.yml`) |
|--------|-----------------------------------|----------------------------------------|
| Backend | Production image, single worker, no reload | `--reload`, bind-mounted `./backend` |
| Frontend | Production build (`npm start`) | `next dev`, bind-mounted `./frontend` |
| PostgreSQL port | Not exposed | Published on `5432` |
| Data | Named volumes (persistent) | Named volumes (persistent) |
| Command | `docker compose up -d --build` | `docker compose -f docker-compose.dev.yml up --build` |

---

## Host Development Setup

### Environment Files

```bash
# Backend
cp backend/.env.example backend/.env

# Frontend
cp frontend/.env.example frontend/.env.local
```

The defaults are safe for local development. To enable Gemini-backed answers, set `GEMINI_API_KEY` in `backend/.env`. Without it, set `LLM_PROVIDER=local` for an offline development answerer.

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                  # Windows
# source .venv/bin/activate             # Linux/macOS

# Install CPU-only PyTorch first (avoids CUDA wheels):
pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.3,<3.0"
pip install -r requirements.txt

# PostgreSQL must be running (e.g. `docker compose up -d db` from repo root)
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

On first `POST /api/documents/{id}/process`, the embedding model (`EMBEDDING_MODEL`) is downloaded from Hugging Face. The cross-encoder reranker (`RERANKER_MODEL`) is downloaded on the first chat or search request. GPU is not required.

### Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
npm run typecheck      # tsc --noEmit
npm run build          # production build
```

> **Note:** The dev frontend container shares `./frontend/.next` with the host via bind mount. After running `npm run build` on the host and then starting the dev Docker stack, remove `frontend/.next` once so the container rebuilds its dev bundle cleanly.

---

## Database Setup

The schema is managed with Alembic. The Docker backend runs `alembic upgrade head` automatically on startup.

### Manual Alembic Commands

```bash
cd backend

# Apply migrations
python -m alembic upgrade head

# Create a new migration from ORM models
python -m alembic revision --autogenerate -m "describe change"

# Verify schema matches models (should print "No new upgrade operations detected.")
python -m alembic check

# Show current revision
python -m alembic current
```

The initial migration creates the pgvector extension, all tables, indexes (including an HNSW index on `document_chunks.embedding`), and the `feedback.rating` CHECK constraint.

---

## Tests

Backend tests use a dedicated database (default `docmind_test`) so they never touch development data. The test suite creates the test database automatically if it is missing.

```bash
cd backend
pip install -r requirements-dev.txt     # pytest + httpx
python -m pytest app/tests -q
```

**Current suite: 252 tests** covering:

- Authentication, RBAC
- Document validation, upload, extraction, chunking, embeddings, processing status
- Phase 4 RAG pipeline (retrieval ranking, permission filtering, context assembly, LLM provider, citations, chat/search API)
- Phase 5 retrieval (BM25, score normalization, hybrid fusion, reranker ordering/metadata, confidence gates)
- Phase 6 product features (conversations, feedback, versioning, admin, user-facing search)
- Phase 7 evaluation harness
- Phase 9 demo (mode gating, index build/idempotency, scoped chat, upload blocking)

---

## Health Checks

| Check | URL | Notes |
|-------|-----|-------|
| API health | `GET http://localhost:8000/api/health` | Returns `{"status":"ok","version":"0.1.0","environment":"development","database":"ok"}` |
| Swagger docs | `http://localhost:8000/docs` | Interactive API documentation |
| Frontend | `http://localhost:3000` | Landing page renders live backend health |

---

## Demo Walkthrough (Self-hosted)

A 5-minute walkthrough against the Docker stack (`docker compose up -d --build`):

1. **Landing page** — `http://localhost:3000` renders the live backend health card.
2. **Registration** — "Create account"; a new user is always a `STUDENT`.
3. **Login** — sign in; the dashboard loads your empty conversations list.
4. **Upload** — drop in `backend/evaluation/corpus/academic_regulations.pdf`; it appears as `UPLOADED`.
5. **Process** — "Process" → status becomes `ACTIVE` (first run downloads the BGE model).
6. **Ask a question** — e.g. *"What is the minimum attendance requirement?"* → a sourced answer with page citations; rate it 👍/👎.
7. **Conversations** — the conversation appears in the sidebar; follow up with another question.
8. **Search** — `/search` returns clean, permission-aware results with match percentages.
9. **Mobile** — narrow the window below 640 px: the nav collapses into a hamburger menu.
10. **Admin** — promote a user to `ADMIN` via `PATCH /api/admin/users/{id}/role` to see stats and role management.
11. **Versioning** — on a document, "Versions" → "Upload new version" adds a v2 entry.
