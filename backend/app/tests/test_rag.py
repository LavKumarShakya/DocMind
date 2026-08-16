"""RAG pipeline tests: grounded answer, fallback on empty/LLM failure, validation, permissions."""

import uuid

import pytest

from app.core.config import settings
from app.core.enums import AccessLevel, DocumentStatus, Role
from app.core.errors import ApiError
from app.db.models import Document
from app.rag.prompts import FALLBACK_ANSWER
from app.services import rag_service
from app.services.llm_service import LLMProviderError, set_llm_provider
from app.services.retrieval_service import RetrievedChunk, RetrievalService


class StubRetrievalService:
    """Deterministic retrieval whose results are set by the test."""

    def __init__(self, results):
        self.results = results
        self.embed_query_calls = 0

    def embed_query(self, query):
        self.embed_query_calls += 1
        return [0.0] * settings.EMBEDDING_DIM

    def retrieve(self, db, *, query_embedding, user, top_k=None, min_similarity=None):
        return self.results


def _chunk(text: str, *, title: str = "Academic Regulations") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title=title,
        page_number=1,
        section=None,
        chunk_index=0,
        text=text,
        score=0.9,
    )


def test_grounded_answer_returns_answer_and_citations(db_session, user_factory, fake_llm_provider):
    user = user_factory()
    result = rag_service.answer_question(
        db_session,
        question="What is the attendance policy?",
        user=user,
        retrieval_service=StubRetrievalService([_chunk("80% attendance required.")]),
    )
    assert "attendance" in result.answer.lower()
    assert len(result.citations) == 1
    assert result.citations[0].section is None


def test_empty_retrieval_returns_grounded_fallback(db_session, user_factory, fake_llm_provider):
    user = user_factory()
    result = rag_service.answer_question(
        db_session,
        question="Tell me about 1998 FIFA.",
        user=user,
        retrieval_service=StubRetrievalService([]),
    )
    assert result.answer == FALLBACK_ANSWER
    assert result.citations == []
    assert fake_llm_provider.calls == 0  # LLM is not invoked without evidence


def test_llm_failure_returns_grounded_fallback(db_session, user_factory, fake_llm_provider):
    user = user_factory()

    class FailingProvider:
        name = "failing"

        def answer(self, *, system_prompt, question):
            raise LLMProviderError("simulated outage")

    set_llm_provider(FailingProvider())
    try:
        with pytest.raises(LLMProviderError):
            rag_service.answer_question(
                db_session,
                question="Any question at all?",
                user=user,
                retrieval_service=StubRetrievalService([_chunk("some evidence")]),
            )
    finally:
        set_llm_provider(None)


def test_message_too_long_rejected(db_session, user_factory):
    user = user_factory()
    with pytest.raises(ApiError) as exc:
        rag_service.answer_question(
            db_session,
            question="x" * (settings.MAX_MESSAGE_LENGTH + 1),
            user=user,
            retrieval_service=StubRetrievalService([]),
        )
    assert exc.value.code == "MESSAGE_TOO_LONG"


def test_empty_message_rejected(db_session, user_factory):
    user = user_factory()
    with pytest.raises(ApiError) as exc:
        rag_service.answer_question(
            db_session,
            question="   ",
            user=user,
            retrieval_service=StubRetrievalService([]),
        )
    assert exc.value.code == "MESSAGE_EMPTY"


def test_search_documents_returns_raw_results(db_session, user_factory):
    user = user_factory()
    results = rag_service.search_documents(
        db_session,
        query="shuttle schedule",
        user=user,
        retrieval_service=StubRetrievalService([_chunk("Shuttle runs hourly")]),
    )
    assert len(results) == 1
    assert "Shuttle" in results[0].text


def test_real_retrieval_respects_permissions(db_session, user_factory, fake_embedding_service):
    """End-to-end retrieval path (SQL-level permission filter) through rag_service."""
    from app.tests.test_retrieval import make_document

    student = user_factory(role=Role.STUDENT)
    admin = user_factory(role=Role.ADMIN)
    secret_text = "confidential academic integrity report"
    secret = make_document(db_session, admin, access_level=AccessLevel.ADMIN)
    # Embed the chunk with the SAME fake embedding service the query uses, so a
    # student querying the exact text yields cosine similarity 1.0. If the
    # permission filter leaked, the student would retrieve it; it must be
    # blocked in SQL.
    secret_embedding = fake_embedding_service.embed([secret_text])[0]
    from app.tests.test_retrieval import make_chunk

    make_chunk(db_session, secret, secret_text, secret_embedding)

    service = RetrievalService()
    student_results = rag_service.search_documents(
        db_session, query=secret_text, user=student, retrieval_service=service
    )
    assert all(r.document_id != secret.id for r in student_results)

    admin_results = rag_service.search_documents(
        db_session, query=secret_text, user=admin, retrieval_service=service
    )
    assert any(r.document_id == secret.id for r in admin_results)