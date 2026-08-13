"""Pydantic schemas for the chat and search endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=settings.MAX_MESSAGE_LENGTH)


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    document_id: str
    document_title: str
    page_number: int | None
    section: str | None
    chunk_index: int


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=settings.MAX_MESSAGE_LENGTH)


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    page_number: int | None
    section: str | None
    chunk_index: int
    text: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]