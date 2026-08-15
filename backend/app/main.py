"""FastAPI application entrypoint.

Phase 1 scope: application shell, CORS, structured error handling,
database connectivity and health checks. Feature routers are added in
their respective phases.
"""

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


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startup hook: in demo mode, surface index readiness without blocking."""
    if settings.DEMO_MODE:
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