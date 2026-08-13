"""Chat and semantic-search endpoints (Phase 4 RAG)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CitationResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a grounded question over your visible documents",
)
def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Run the RAG pipeline and return a grounded answer with citations.

    Answers are restricted to documents visible to ``current_user``. When no
    sufficient evidence is found, a fixed fallback answer is returned.
    """
    result = rag_service.answer_question(
        db, question=payload.message, user=current_user
    )
    return ChatResponse(
        answer=result.answer,
        citations=[
            CitationResponse(**citation.__dict__) for citation in result.citations
        ],
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic search (no LLM) - developer/debug endpoint",
)
def search(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Return raw retrieval results for a query without calling an LLM."""
    results = rag_service.search_documents(db, query=payload.query, user=current_user)
    return SearchResponse(
        results=[
            SearchResult(
                chunk_id=str(r.chunk_id),
                document_id=str(r.document_id),
                document_title=r.document_title,
                page_number=r.page_number,
                section=r.section,
                chunk_index=r.chunk_index,
                text=r.text,
                score=r.score,
            )
            for r in results
        ]
    )