"""Chat and semantic-search endpoints (Phase 4 RAG + Phase 5 hybrid retrieval)."""

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
    sufficient evidence is found (empty retrieval or evidence below the
    confidence threshold), a fixed fallback answer is returned.
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


def _search_result(candidate) -> SearchResult:
    """Map a retrieval candidate onto the debug payload, exposing stage scores."""
    return SearchResult(
        chunk_id=str(candidate.chunk_id),
        document_id=str(candidate.document_id),
        document_title=candidate.document_title,
        page_number=candidate.page_number,
        section=candidate.section,
        chunk_index=candidate.chunk_index,
        text=candidate.text,
        score=candidate.dense_score,
        dense_score=candidate.dense_score,
        bm25_score=candidate.bm25_score,
        hybrid_score=candidate.hybrid_score,
        rerank_score=candidate.rerank_score,
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Hybrid search (no LLM) - developer/debug endpoint",
)
def search(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Return raw hybrid retrieval results for a query without calling an LLM.

    Each result exposes the per-stage scores: dense_score, bm25_score,
    hybrid_score and rerank_score (see SearchResult for exact semantics).
    """
    results = rag_service.search_documents(db, query=payload.query, user=current_user)
    return SearchResponse(results=[_search_result(r) for r in results])