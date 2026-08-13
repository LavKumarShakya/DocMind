"""RAG orchestrator: question → evidence → grounded answer → citations.

Pipeline (all server-side, permission-aware):
  1. Embed the question with the same embedding model used for ingestion.
  2. Retrieve the top-K similar chunks from pgvector, restricted to documents
     the user can see.
  3. Assemble a labelled context block (bounded by MAX_CONTEXT_CHARS).
  4. Ask the LLM provider to answer strictly from that evidence.
  5. Map the answer's citation tags back to retrieved chunks (citation_service).

Failure handling is graceful: an empty retrieval or an LLM failure yields the
fixed grounded fallback answer rather than an error, so the chat API stays
useful even while an upstream provider is flaky.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.db.models import User
from app.rag.prompts import FALLBACK_ANSWER, build_system_prompt
from app.services import citation_service, context_service
from app.services.llm_service import LLMProviderError, get_llm_provider
from app.services.retrieval_service import RetrievedChunk, RetrievalService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RagResult:
    """The chat endpoint's response payload."""

    answer: str
    citations: list[citation_service.Citation] = field(default_factory=list)


def answer_question(
    db: Session,
    *,
    question: str,
    user: User,
    retrieval_service: RetrievalService | None = None,
    llm_provider=None,
) -> RagResult:
    """Answer ``question`` for ``user`` from their visible documents."""
    if len(question) > settings.MAX_MESSAGE_LENGTH:
        raise ApiError(
            "MESSAGE_TOO_LONG",
            f"Message exceeds the {settings.MAX_MESSAGE_LENGTH} character limit.",
            status_code=422,
        )
    if not question.strip():
        raise ApiError("MESSAGE_EMPTY", "Message must not be empty.", status_code=422)

    svc = retrieval_service or RetrievalService()
    query_embedding = svc.embed_query(question)
    results = svc.retrieve(
        db, query_embedding=query_embedding, user=user
    )

    if not results:
        logger.info("No evidence retrieved for question; returning grounded fallback")
        return RagResult(answer=FALLBACK_ANSWER)

    context = context_service.build_context(results)
    system_prompt = build_system_prompt(context)

    provider = llm_provider or get_llm_provider()
    try:
        answer = provider.answer(system_prompt=system_prompt, question=question)
    except LLMProviderError as exc:
        logger.warning("LLM provider failed; returning grounded fallback: %s", exc)
        return RagResult(answer=FALLBACK_ANSWER)

    answer = answer.strip() or FALLBACK_ANSWER
    citations = citation_service.build_citations(answer, results)
    return RagResult(answer=answer, citations=citations)


def search_documents(
    db: Session,
    *,
    query: str,
    user: User,
    retrieval_service: RetrievalService | None = None,
) -> list[RetrievedChunk]:
    """Developer-facing semantic search (no LLM); used by /api/search."""
    svc = retrieval_service or RetrievalService()
    query_embedding = svc.embed_query(query)
    return svc.retrieve(db, query_embedding=query_embedding, user=user)