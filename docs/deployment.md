# Deployment Guide

How to deploy DocMind in production.

---

## Self-hosted Docker (Recommended)

This is the recommended way to run the full DocMind application. It requires **no host installs** — Python, Node.js, PostgreSQL, pgvector, PyTorch, and the ML models all live inside containers.

### Requirements

- **Docker Desktop** (Windows/macOS) or Docker Engine + Compose v2 (Linux)
- **Memory:** at least **8 GB RAM**. The BGE embedder (~400 MB) and the cross-encoder reranker are loaded into the backend process.
- **Disk:** ~10 GB free for images, the Hugging Face model cache, and uploaded documents.

### Setup

```bash
git clone <repo-url> DocMind
cd DocMind
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
# Strong random password for PostgreSQL
POSTGRES_PASSWORD=change-me-strong-password

# JWT signing key (32+ random bytes)
SECRET_KEY=change-me-64-char-random-string

# Google AI Studio API key (https://aistudio.google.com/apikey)
GEMINI_API_KEY=AIza...
```

### Optional Overrides

| Variable | Default | Notes |
|----------|---------|-------|
| `POSTGRES_USER` / `POSTGRES_DB` | `docmind` | Database credentials |
| `LLM_PROVIDER` | `gemini` | `gemini` (needs key) or `local` (offline dev only) |
| `CORS_ORIGINS` | `http://localhost:3000` | Frontend origin(s) allowed to call the API |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL baked into the frontend build |
| `STORAGE_DIR` | `/data/storage` | Uploaded-document root (persistent volume) |
| `HF_HOME` | `/data/huggingface` | Model cache (persistent volume) |

### Gemini API Key

Get a key from [Google AI Studio](https://aistudio.google.com/apikey) and put it in `.env` as `GEMINI_API_KEY=AIza...`. The key is passed only to the backend container; it is **never** baked into the frontend image and never exposed to the browser.

If you do not set a key, chat/search endpoints will return the grounded fallback. You can set `LLM_PROVIDER=local` for an offline answerer (not for production use).

### Start

```bash
docker compose up -d --build
```

First run downloads models from Hugging Face (~500 MB); subsequent runs reuse the persistent cache volume.

### Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |

Register an account (always created as `STUDENT`), then log in. PostgreSQL is **not** exposed to the host.

### Stop / Restart

```bash
# Stop (keeps all data in named volumes)
docker compose down

# Restart (reuses existing volumes, no re-download)
docker compose up -d
```

### Persistent Data

All persistent state lives in named Docker volumes:

| Volume | Backs | Survives `docker compose down` |
|--------|-------|--------------------------------|
| `docmind_pgdata` | PostgreSQL data | Yes |
| `docmind_backend_storage` | Uploaded documents (`STORAGE_DIR`) | Yes |
| `docmind_hf_cache` | Hugging Face model cache (`HF_HOME`) | Yes |

### Complete Reset

```bash
# Remove containers + volumes (database, documents, model cache)
docker compose down -v

# Also remove images
docker compose down -v --rmi all
```

### Model Download Behavior

The first `POST /api/documents/{id}/process` triggers download of `BAAI/bge-base-en-v1.5`; the first chat/search request downloads `cross-encoder/ms-marco-MiniLM-L-6-v2`. Both are cached in `/data/huggingface` (the `hf_cache` volume). Models load lazily and are shared as in-process singletons.

---

## Troubleshooting

- **"Connection refused" on `localhost:3000`** — wait for the first `--build` to finish; frontend containers are often still building.
- **First PDF process is very slow / appears hung** — the BGE model is downloading on first use; give it a minute (check `docker compose logs -f backend`).
- **Out-of-memory during processing** — the stack needs ~8 GB. Close other apps or increase Docker Desktop's memory limit (Settings → Resources).
- **Backend shows `Could not connect to server` for the database** — the DB healthcheck may still be warming up; the backend waits on it. Check `docker compose logs db`.
- **Chat returns the grounded fallback even with documents** — no evidence cleared the confidence gate (try a question with keywords from the document). Note that if the Gemini key is missing or quota is exhausted, you will see a 503 Service Unavailable / Rate Limited error instead of a fallback.
- **Port 3000 or 8000 already in use** — stop the conflicting service or change the published ports in `docker-compose.yml`.

---

## Render (Backend + Database) + Vercel (Frontend)

The frontend is a fully static Next.js build, so it deploys on Vercel with no Dockerfile. The backend deploys on Render as a Docker Web Service against Render's managed PostgreSQL (which ships the `pgvector` extension).

### Render — Managed PostgreSQL

- Region close to the web service; note the **Internal Database URL**.
- Render's URL is `postgresql://…`; the app expects `postgresql+psycopg://`, so rewrite the scheme in `DATABASE_URL`.

### Render — Web Service (Docker)

- The Dockerfile runs migrations and starts uvicorn automatically; **no Start Command override needed**.
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

- **Persistent Disk** (required): mount at `/data`. Without it the ML models re-download on every deploy and uploaded PDFs are lost.
- **Health check path**: `/api/health`
- **Instance size**: at least 1 GB RAM (free tier 0.5 GB may OOM when both models load). CPU-only inference, 1 worker.

### Vercel — Frontend

- Import the repo (framework auto-detected as Next.js). No build config needed.
- Environment variable: `NEXT_PUBLIC_API_URL=https://<your-backend>.onrender.com` (build-time).
- Preview deployments call the same backend, so their preview URL must be added to the backend's `CORS_ORIGINS`.

---

## Production Checklist

1. Set strong, unique values for `SECRET_KEY` and `POSTGRES_PASSWORD`.
2. Set `CORS_ORIGINS` to your real frontend origin(s) and `DEBUG=false`.
3. Provide a real `GEMINI_API_KEY` (or set `LLM_PROVIDER=local` for non-production use).
4. Put the app behind a reverse proxy (nginx / Caddy) that terminates TLS.
5. Back up the `pgdata`, `backend_storage`, and `hf_cache` volumes.
6. Verify migrations: the backend runs `alembic upgrade head` on startup; `python -m alembic check` should report no drift.

```bash
docker compose up -d --build
# Verify: GET http://<host>/api/health → {"status":"ok", ...}
```

**Scaling considerations** (not implemented): background ingestion, read replicas, and managed storage would be the first steps for a larger deployment.
