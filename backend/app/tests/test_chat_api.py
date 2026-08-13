"""Chat and search API tests (POST /api/chat, POST /api/search)."""

import uuid

import pytest

from app.rag.confidence import is_confident
from app.rag.prompts import FALLBACK_ANSWER
from app.services import rag_service
from app.services.retrieval_types import RetrievalCandidate
from app.tests.helpers import auth_headers


def _candidate(text: str, *, dense_score: float = 0.9) -> RetrievalCandidate:
    """Deterministic reranked candidate returned by the stubbed pipeline."""
    return RetrievalCandidate(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Academic Regulations",
        page_number=1,
        section=None,
        chunk_index=0,
        text=text,
        dense_score=dense_score,
        rerank_score=0.92,
    )


@pytest.fixture()
def stub_pipeline(monkeypatch):
    """Point rag_service at a deterministic retrieval stub for API tests."""
    chunk = _candidate("80% attendance is required.")
    monkeypatch.setattr(rag_service, "_retrieve", lambda db, q, user, rs=None: [chunk])
    return chunk


def test_chat_requires_auth(client):
    res = client.post("/api/chat", json={"message": "hello"})
    assert res.status_code == 401


def test_chat_returns_grounded_answer_and_citation(client, user_factory, stub_pipeline):
    user = user_factory()
    chunk = stub_pipeline
    res = client.post(
        "/api/chat", headers=auth_headers(user), json={"message": "What is the attendance policy?"}
    )
    assert res.status_code == 200
    body = res.json()
    assert "attendance" in body["answer"].lower()
    assert len(body["citations"]) == 1
    citation = body["citations"][0]
    assert citation["document_title"] == "Academic Regulations"
    assert citation["chunk_id"] == str(chunk.chunk_id)
    assert citation["page_number"] == 1
    assert citation["section"] is None
    assert citation["relevance_score"] == 0.92


def test_chat_returns_fallback_when_no_evidence(client, user_factory, monkeypatch):
    user = user_factory()
    monkeypatch.setattr(rag_service, "_retrieve", lambda db, q, user, rs=None: [])
    res = client.post(
        "/api/chat", headers=auth_headers(user), json={"message": "Tell me about the 1998 FIFA."}
    )
    assert res.status_code == 200
    assert res.json()["answer"] == FALLBACK_ANSWER
    assert res.json()["citations"] == []


def test_chat_rejects_empty_and_overlong_messages(client, user_factory):
    user = user_factory()
    res = client.post("/api/chat", headers=auth_headers(user), json={"message": ""})
    assert res.status_code == 422

    from app.core.config import settings

    res = client.post(
        "/api/chat",
        headers=auth_headers(user),
        json={"message": "x" * (settings.MAX_MESSAGE_LENGTH + 1)},
    )
    assert res.status_code == 422


def test_search_returns_raw_results(client, user_factory, stub_pipeline):
    user = user_factory()
    chunk = stub_pipeline
    res = client.post(
        "/api/search", headers=auth_headers(user), json={"query": "attendance"}
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["chunk_id"] == str(chunk.chunk_id)
    assert result["score"] == 0.9  # legacy alias == dense_score
    assert result["dense_score"] == 0.9
    assert result["rerank_score"] == 0.92


def test_search_requires_auth(client):
    res = client.post("/api/search", json={"query": "x"})
    assert res.status_code == 401


def test_confidence_gate_blocks_low_relevance_answer(client, user_factory, monkeypatch):
    """Weak evidence (low rerank score) must NOT invoke the LLM."""
    from app.services.llm_service import get_llm_provider

    weak = _candidate("thin snippet", dense_score=0.2)
    blocked = RetrievalCandidate(
        chunk_id=weak.chunk_id,
        document_id=weak.document_id,
        document_title=weak.document_title,
        page_number=weak.page_number,
        section=weak.section,
        chunk_index=weak.chunk_index,
        text=weak.text,
        dense_score=weak.dense_score,
        rerank_score=0.05,
    )
    monkeypatch.setattr(rag_service, "_retrieve", lambda db, q, user, rs=None: [blocked])
    user = user_factory()
    res = client.post(
        "/api/chat", headers=auth_headers(user), json={"message": "What is this?"}
    )
    assert res.status_code == 200
    assert res.json()["answer"] == FALLBACK_ANSWER
    assert get_llm_provider().calls == 0
    assert is_confident([blocked], threshold=0.1) is False