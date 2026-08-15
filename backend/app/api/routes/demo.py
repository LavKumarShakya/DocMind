"""Public demo endpoints (demo mode only).

These endpoints require no authentication: they serve the public demo page.
They are only active when ``DEMO_MODE=true``; otherwise they return a clear
``DEMO_MODE_DISABLED`` 404. The demo chat reuses the existing grounded RAG
pipeline but is scoped to the single pre-indexed demo document.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.db.database import get_db
from app.schemas.chat import CitationResponse
from app.schemas.demo import DemoChatRequest, DemoChatResponse, DemoInfoResponse
from app.services import demo_service

router = APIRouter(prefix="/demo", tags=["demo"])


def _require_demo_mode() -> None:
    if not settings.DEMO_MODE:
        raise ApiError(
            "DEMO_MODE_DISABLED",
            "Demo mode is not enabled on this deployment.",
            status_code=404,
        )


@router.get(
    "/info",
    response_model=DemoInfoResponse,
    summary="Public demo metadata and index readiness",
)
def demo_info(db: Session = Depends(get_db)) -> DemoInfoResponse:
    _require_demo_mode()
    ready = demo_service.demo_index_ready(db)
    return DemoInfoResponse(
        demo_mode=True,
        document_id=str(demo_service.DEMO_DOCUMENT_ID),
        document_title=settings.DEMO_DOCUMENT_TITLE,
        status="ready" if ready else "missing",
        chunk_count=demo_service.demo_chunk_count(db) if ready else None,
    )


@router.post(
    "/chat",
    response_model=DemoChatResponse,
    summary="Ask a grounded question about the demo document",
)
def demo_chat(
    payload: DemoChatRequest,
    db: Session = Depends(get_db),
) -> DemoChatResponse:
    _require_demo_mode()
    result = demo_service.answer_demo_question(db, question=payload.message)
    return DemoChatResponse(
        answer=result.answer,
        citations=[
            CitationResponse(**citation.__dict__) for citation in result.citations
        ],
    )