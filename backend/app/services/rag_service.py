"""RAG orchestrator: question → evidence → grounded answer → citations.

Pipeline (all server-side, permission-aware):
  1. Hybrid retrieval (Phase 5): dense pgvector + BM25 keyword candidates are
     merged, normalized, fused and re-ranked by a cross-encoder; all filtering
     happens in SQL so only documents visible to the user are considered.
  2. Confidence gate: if the strongest evidence does not clear
     CONFIDENCE_THRESHOLD, the fixed fallback answer is returned and the LLM
     is never called.
  3. Assemble a labelled context block (bounded by MAX_CONTEXT_CHARS).
  4. Ask the LLM provider to answer strictly from that evidence.
  5. Map the answer's citation tags back to retrieved chunks (citation_service).

Failure handling is graceful: an empty retrieval, weak evidence or an LLM
failure yields the fixed grounded fallback answer rather than an error, so the
chat API stays useful even while an upstream provider is flaky.

The ``retrieval_service`` argument is preserved for compatibility: it is used
as the *dense* stage inside the hybrid pipeline, so tests can inject a
deterministic fake while BM25 still runs against the real database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.db.models import User
from app.rag.confidence import is_confident
from app.rag.prompts import FALLBACK_ANSWER, build_system_prompt
from app.services import citation_service, context_service
from app.services.hybrid_retrieval_service import HybridRetrievalService
from app.services.llm_service import LLMProviderError, get_llm_provider
from app.services.retrieval_types import RetrievalCandidate

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
    retrieval_service=None,
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

    results = _retrieve(db, question, user, retrieval_service)

    if not results or not is_confident(results):
        reason = "no evidence" if not results else "evidence below confidence threshold"
        logger.info("Not answering question (%s); returning grounded fallback", reason)
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


def _retrieve(db: Session, question: str, user: User, retrieval_service=None) -> list[RetrievalCandidate]:
    """Run hybrid retrieval; ``retrieval_service`` fills the dense stage."""
    dense = retrieval_service
    pipeline = HybridRetrievalService(dense_service=dense)
    return pipeline.retrieve(db, query=question, user=user)


def search_documents(
    db: Session,
    *,
    query: str,
    user: User,
    retrieval_service=None,
) -> list[RetrievalCandidate]:
    """Developer-facing hybrid search (no LLM); used by /api/search."""
    return _retrieve(db, query, user, retrieval_service)