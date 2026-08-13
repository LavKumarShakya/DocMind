"""Chat and search API tests (POST /api/chat, POST /api/search)."""

import pytest

from app.core.enums import Role
from app.rag.prompts import FALLBACK_ANSWER
from app.services import rag_service
from app.tests.helpers import auth_headers


class StubRetrievalService:
    def __init__(self, results):
        self.results = results

    def embed_query(self, query):
        return [0.0] * 768

    def retrieve(self, db, *, query_embedding, user, top_k=None, min_similarity=None):
        return self.results


def _chunk(text: str):
    import uuid

    from app.services.retrieval_service import RetrievedChunk

    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Academic Regulations",
        page_number=1,
        section=None,
        chunk_index=0,
        text=text,
        score=0.9,
    )


@pytest.fixture()
def stub_retrieval(monkeypatch):
    """Point rag_service at a deterministic retrieval stub for API tests."""
    chunk = _chunk("80% attendance is required.")
    stub = StubRetrievalService([chunk])
    monkeypatch.setattr(rag_service, "RetrievalService", lambda: stub)
    return stub, chunk


def test_chat_requires_auth(client):
    res = client.post("/api/chat", json={"message": "hello"})
    assert res.status_code == 401


def test_chat_returns_grounded_answer_and_citation(client, user_factory, stub_retrieval):
    user = user_factory()
    stub, chunk = stub_retrieval
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


def test_chat_returns_fallback_when_no_evidence(client, user_factory, monkeypatch):
    user = user_factory()
    monkeypatch.setattr(rag_service, "RetrievalService", lambda: StubRetrievalService([]))
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


def test_search_returns_raw_results(client, user_factory, stub_retrieval):
    user = user_factory()
    stub, chunk = stub_retrieval
    res = client.post(
        "/api/search", headers=auth_headers(user), json={"query": "attendance"}
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["chunk_id"] == str(chunk.chunk_id)
    assert body["results"][0]["score"] == 0.9


def test_search_requires_auth(client):
    res = client.post("/api/search", json={"query": "x"})
    assert res.status_code == 401