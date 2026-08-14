"""Phase 6 user-facing search tests (/api/search/results) + dev search regression."""

import uuid

import pytest

from app.core.config import settings
from app.core.enums import AccessLevel, DocumentStatus, Role
from app.services import rag_service
from app.services.retrieval_types import RetrievalCandidate
from app.tests.helpers import auth_headers
from app.tests.test_retrieval import make_chunk, make_document, one_hot


def _candidate(text: str, *, rerank_score: float = 0.9) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="BCS-501 Syllabus",
        page_number=4,
        section=None,
        chunk_index=0,
        text=text,
        dense_score=0.85,
        rerank_score=rerank_score,
    )


def _stub_pipeline(monkeypatch, results):
    monkeypatch.setattr(
        rag_service, "_retrieve", lambda db, q, user, rs=None: results
    )


def test_search_requires_auth(client):
    res = client.post("/api/search/results", json={"query": "syllabus"})
    assert res.status_code == 401


def test_search_returns_clean_results(client, user_factory, monkeypatch, fake_llm_provider):
    user = user_factory()
    _stub_pipeline(monkeypatch, [_candidate("BCS-501 data structures syllabus page content")])

    res = client.post(
        "/api/search/results", headers=auth_headers(user), json={"query": "BCS-501"}
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["document_title"] == "BCS-501 Syllabus"
    assert result["page_number"] == 4
    assert "syllabus" in result["snippet"].lower()
    assert result["relevance_score"] == 0.9
    # Clean payload: no raw scores, no chunk ids, no vector internals.
    assert "chunk_id" not in result
    assert "dense_score" not in result
    assert "bm25_score" not in result
    assert "hybrid_score" not in result


def test_search_does_not_invoke_llm(client, user_factory, monkeypatch, fake_llm_provider):
    user = user_factory()
    _stub_pipeline(monkeypatch, [_candidate("some evidence")])
    res = client.post(
        "/api/search/results", headers=auth_headers(user), json={"query": "evidence"}
    )
    assert res.status_code == 200
    assert fake_llm_provider.calls == 0


def test_search_no_results_returns_empty(client, user_factory, monkeypatch):
    user = user_factory()
    _stub_pipeline(monkeypatch, [])
    res = client.post(
        "/api/search/results", headers=auth_headers(user), json={"query": "zzz"}
    )
    assert res.status_code == 200
    assert res.json()["results"] == []


def test_search_relevant_results_real_pipeline(
    db_session, user_factory, fake_embedding_service
):
    """Real Phase 5 path (dense stage) returns the matching document."""
    user = user_factory()
    doc = make_document(db_session, user, access_level=AccessLevel.PUBLIC, title="BCS-501 Syllabus")
    make_chunk(
        db_session,
        doc,
        "BCS-501 data structures syllabus outline",
        one_hot(3),
        page_number=4,
    )

    from app.services.retrieval_service import RetrievalService

    results = rag_service.search_documents(
        db_session,
        query="BCS-501",
        user=user,
        retrieval_service=RetrievalService(),
    )
    assert results
    assert results[0].document_title == "BCS-501 Syllabus"
    assert results[0].page_number == 4


def test_search_respects_permissions_real_pipeline(
    db_session, user_factory, fake_embedding_service
):
    student = user_factory(role=Role.STUDENT)
    admin = user_factory(role=Role.ADMIN)
    secret_text = "confidential disciplinary committee minutes"
    secret = make_document(db_session, admin, access_level=AccessLevel.ADMIN, title="Committee Minutes")
    make_chunk(db_session, secret, secret_text, one_hot(5), page_number=2)

    public_doc = make_document(db_session, admin, access_level=AccessLevel.PUBLIC, title="Public Handbook")
    make_chunk(db_session, public_doc, "student handbook general rules", one_hot(1))

    from app.services.retrieval_service import RetrievalService

    service = RetrievalService()

    student_results = rag_service.search_documents(
        db_session, query="confidential disciplinary", user=student, retrieval_service=service
    )
    assert all(r.document_id != secret.id for r in student_results)

    admin_results = rag_service.search_documents(
        db_session, query="confidential disciplinary", user=admin, retrieval_service=service
    )
    assert any(r.document_id == secret.id for r in admin_results)


def test_developer_search_endpoint_unchanged(client, user_factory, monkeypatch):
    """/api/search (Phase 5 developer endpoint) still exposes per-stage scores."""
    user = user_factory()
    _stub_pipeline(monkeypatch, [_candidate("evidence", rerank_score=0.93)])

    res = client.post(
        "/api/search", headers=auth_headers(user), json={"query": "attendance"}
    )
    assert res.status_code == 200
    result = res.json()["results"][0]
    assert result["dense_score"] == 0.85
    assert result["rerank_score"] == 0.93
    assert result["chunk_id"]  # internal ids remain on the dev endpoint only