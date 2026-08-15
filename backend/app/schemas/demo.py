"""Pydantic schemas for the public demo endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.chat import CitationResponse


class DemoInfoResponse(BaseModel):
    demo_mode: bool
    document_id: str
    document_title: str
    # "ready" when the pre-indexed demo document exists, else "missing".
    status: str
    chunk_count: int | None = None


class DemoChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=settings.MAX_MESSAGE_LENGTH)


class DemoChatResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    demo_mode: bool = True