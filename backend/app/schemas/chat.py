"""Pydantic schemas for the chat and search endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=settings.MAX_MESSAGE_LENGTH)
    # When provided, the exchange is appended to the caller's conversation;
    # otherwise a new conversation is created and returned in the response.
    conversation_id: uuid.UUID | None = None


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    document_id: str
    document_title: str
    page_number: int | None
    section: str | None
    chunk_index: int
    # Final cross-encoder reranker relevance score (0..1), when available.
    relevance_score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    # Conversation persistence (Phase 6): the conversation the exchange was
    # stored in and the id of the persisted assistant message (for feedback).
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None


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
    # Legacy alias kept for Phase 4 compatibility; equals dense_score when the
    # candidate came from the dense stage, otherwise None.
    score: float | None = None
    # Phase 5 per-stage scores. Semantics:
    #   dense_score  - cosine similarity from pgvector (0..1).
    #   bm25_score   - normalized PostgreSQL FTS rank (0..1 after min-max).
    #   hybrid_score - weighted fusion of normalized scores (0..1).
    #   rerank_score - cross-encoder relevance, sigmoid of the logit (0..1).
    dense_score: float | None = None
    bm25_score: float | None = None
    hybrid_score: float | None = None
    rerank_score: float | None = None


class SearchResponse(BaseModel):
    results: list[SearchResult]


class UserSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=settings.MAX_MESSAGE_LENGTH)


class UserSearchResult(BaseModel):
    """User-facing search result: no raw scores, vector values or chunk ids.

    ``relevance_score`` is the final reranker relevance (0..1) so the UI can
    show a relative relevance indicator without exposing pipeline internals.
    """

    document_id: str
    document_title: str
    page_number: int | None
    section: str | None
    snippet: str
    relevance_score: float | None = None


class UserSearchResponse(BaseModel):
    results: list[UserSearchResult]