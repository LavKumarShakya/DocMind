"""FastAPI application entrypoint.

Phase 1 scope: application shell, CORS, structured error handling,
database connectivity and health checks. Feature routers are added in
their respective phases.
"""

import os
from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    admin,
    auth,
    chat,
    conversations,
    demo,
    documents,
    feedback,
    health,
)
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.db.database import SessionLocal
from app.services import demo_service

setup_logging()

logger = logging.getLogger(__name__)


def _build_identifier() -> str:
    """A short deployment/build identifier for confirming which code is running.

    Prefers an explicit ``GIT_COMMIT``/``SOURCE_VERSION`` env var (Render sets
    ``SOURCE_VERSION``), then falls back to the local git HEAD, else ``unknown``.
    """
    for key in ("GIT_COMMIT", "SOURCE_VERSION", "RENDER_GIT_COMMIT"):
        value = os.environ.get(key)
        if value:
            return value[:12]
    try:
        import subprocess

        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if head.returncode == 0 and head.stdout.strip():
            return head.stdout.strip()[:12]
    except Exception:  # pragma: no cover - best-effort only
        pass
    return "unknown"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startup hook: log runtime diagnostics, then surface demo index readiness."""
    logger.info(
        "DocMind build=%s app_version=%s",
        _build_identifier(),
        settings.APP_VERSION,
    )
    logger.info(
        "DEMO_MODE=%s (public model-free demo active=%s)",
        settings.DEMO_MODE,
        bool(settings.DEMO_MODE),
    )
    if settings.DEMO_MODE:
        logger.info("DEMO_DOCUMENT_ID=%s", settings.DEMO_DOCUMENT_ID)
        logger.info("DEMO retrieval mode=lightweight TF-IDF (no embedding model, no reranker)")
        logger.info("DEMO_MODE enabled: public demo is active (document=%r)", settings.DEMO_DOCUMENT_TITLE)
        logger.info("Embedding model initialization skipped in DEMO_MODE")
        try:
            with SessionLocal() as db:
                if demo_service.demo_index_ready(db):
                    logger.info(
                        "Demo mode active: pre-indexed demo document is ready "
                        "(title=%r, chunks=%d)",
                        settings.DEMO_DOCUMENT_TITLE,
                        demo_service.demo_chunk_count(db),
                    )
                else:
                    logger.warning(
                        "Demo mode active but the demo index is MISSING. "
                        "Run `python -m scripts.build_demo_index` from the "
                        "backend directory before serving visitors."
                    )
        except Exception:  # pragma: no cover - startup must not crash the app
            logger.exception("Could not inspect demo index during startup")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="DocMind - university knowledge retrieval and question-answering platform.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(demo.router, prefix="/api")

register_exception_handlers(app)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }