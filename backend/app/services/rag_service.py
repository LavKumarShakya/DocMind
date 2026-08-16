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
    document_ids: list | None = None,
    system_prompt_builder=None,
    fallback_answer: str | None = None,
    retrieval_pipeline=None,
    confidence_threshold: float | None = None,
) -> RagResult:
    """Answer ``question`` for ``user`` from their visible documents.

    ``document_ids`` optionally restricts retrieval to specific documents
    (demo mode); ``system_prompt_builder`` and ``fallback_answer`` let demo
    mode reuse this exact pipeline with demo-flavoured grounding.

    ``retrieval_pipeline`` bypasses the hybrid (dense + BM25 + reranker) path
    entirely: when provided, it is called as ``retrieval_pipeline(db, question,
    user)`` and its results are used directly. This is how demo mode runs a
    lightweight lexical retriever over the prebuilt index without ever loading
    the embedding model or the cross-encoder reranker.

    ``confidence_threshold`` overrides the shared CONFIDENCE_THRESHOLD gate
    (used by demo mode, whose scores are not reranker sigmoids). Defaults
    preserve the original behaviour exactly.
    """
    if len(question) > settings.MAX_MESSAGE_LENGTH:
        raise ApiError(
            "MESSAGE_TOO_LONG",
            f"Message exceeds the {settings.MAX_MESSAGE_LENGTH} character limit.",
            status_code=422,
        )
    if not question.strip():
        raise ApiError("MESSAGE_EMPTY", "Message must not be empty.", status_code=422)

    fallback = fallback_answer or FALLBACK_ANSWER
    prompt_builder = system_prompt_builder or build_system_prompt

    if retrieval_pipeline is not None:
        results = retrieval_pipeline(db, question, user)
    elif document_ids:
        results = _retrieve(
            db, question, user, retrieval_service, document_ids=document_ids
        )
    else:
        results = _retrieve(db, question, user, retrieval_service)

    if not results or not is_confident(results, threshold=confidence_threshold):
        reason = "no evidence" if not results else "evidence below confidence threshold"
        logger.info("Not answering question (%s); returning grounded fallback", reason)
        return RagResult(answer=fallback)

    context = context_service.build_context(results)
    system_prompt = prompt_builder(context)

    provider = llm_provider or get_llm_provider()
    try:
        answer = provider.answer(system_prompt=system_prompt, question=question)
    except LLMProviderError as exc:
        logger.warning("LLM provider failed; returning grounded fallback: %s", exc)
        return RagResult(answer=fallback)

    answer = answer.strip() or fallback
    citations = citation_service.build_citations(answer, results)
    return RagResult(answer=answer, citations=citations)


def _retrieve(
    db: Session,
    question: str,
    user: User,
    retrieval_service=None,
    *,
    document_ids: list | None = None,
) -> list[RetrievalCandidate]:
    """Run hybrid retrieval; ``retrieval_service`` fills the dense stage.

    ``document_ids`` is keyword-only so existing test stubs that patch
    ``_retrieve`` with a 4-argument signature keep working unchanged.
    """
    dense = retrieval_service
    pipeline = HybridRetrievalService(dense_service=dense)
    return pipeline.retrieve(
        db, query=question, user=user, document_ids=document_ids
    )


def search_documents(
    db: Session,
    *,
    query: str,
    user: User,
    retrieval_service=None,
) -> list[RetrievalCandidate]:
    """Developer-facing hybrid search (no LLM); used by /api/search."""
    return _retrieve(db, query, user, retrieval_service)