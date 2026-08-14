"""Chat, search and user-facing search endpoints.

The chat endpoint runs the Phase 5 RAG pipeline unchanged and, on top of it,
persists the exchange (user message → answer → citations) in a conversation
(Phase 6). The RAG service itself is never modified by persistence logic.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.enums import MessageRole
from app.db.database import get_db
from app.db.models import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CitationResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    UserSearchRequest,
    UserSearchResponse,
    UserSearchResult,
)
from app.services import conversation_service, rag_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])


def _citations(result) -> list[CitationResponse]:
    return [CitationResponse(**citation.__dict__) for citation in result.citations]


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

    The exchange is persisted in a conversation: a new one is created (with a
    deterministic title from the question) when ``conversation_id`` is omitted,
    otherwise the exchange is appended to the caller's conversation.
    """
    if payload.conversation_id is None:
        conversation = conversation_service.create_conversation(
            db,
            user=current_user,
            title=conversation_service.generate_title(payload.message),
        )
    else:
        conversation = conversation_service.get_owned_conversation(
            db, conversation_id=payload.conversation_id, user=current_user
        )

    conversation_service.add_message(
        db, conversation=conversation, role=MessageRole.USER, content=payload.message
    )

    result = rag_service.answer_question(
        db, question=payload.message, user=current_user
    )

    assistant = conversation_service.add_message(
        db, conversation=conversation, role=MessageRole.ASSISTANT, content=result.answer
    )
    conversation_service.persist_citations(
        db, message=assistant, citations=result.citations
    )

    return ChatResponse(
        answer=result.answer,
        citations=_citations(result),
        conversation_id=conversation.id,
        message_id=assistant.id,
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


@router.post(
    "/search/results",
    response_model=UserSearchResponse,
    summary="User-facing search (no LLM, no raw pipeline internals)",
)
def user_search(
    payload: UserSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSearchResponse:
    """Run Phase 5 retrieval and return clean, user-facing results.

    Results carry document title, page, a text snippet and a relevance
    indicator only — raw scores, vector values and chunk ids are never exposed
    here (they remain available on the developer endpoint above).
    """
    results = rag_service.search_documents(db, query=payload.query, user=current_user)
    return UserSearchResponse(
        results=[
            UserSearchResult(
                document_id=str(r.document_id),
                document_title=r.document_title,
                page_number=r.page_number,
                section=r.section,
                snippet=r.text,
                relevance_score=r.rerank_score,
            )
            for r in results
        ]
    )