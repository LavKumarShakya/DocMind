"""Pydantic schemas for conversations, messages, citations and feedback."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import MessageRole


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class CitationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str | None
    document_id: str | None
    document_title: str | None
    page_number: int | None
    section: str | None
    relevance_score: float | None


class MessageDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime
    citations: list[CitationDetail] = Field(default_factory=list)


class ConversationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageDetail] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    message_id: uuid.UUID
    rating: int = Field(ge=1, le=5)
    reason: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    rating: int
    reason: str | None
    created_at: datetime