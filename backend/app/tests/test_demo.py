"""Public demo mode tests: index build, readiness, demo chat, mode gating.

The demo chat endpoint is exercised end-to-end at the API level (with the RAG
orchestration stubbed so no model or network is needed), while index building
runs against the real demo PDF with the deterministic fake embedding service.
"""

import uuid

import pytest

from app.core.config import settings
from app.core.enums import AccessLevel, DocumentStatus
from app.db.models import Document, DocumentChunk, DocumentVersion
from app.rag.prompts import DEMO_FALLBACK_ANSWER, build_demo_system_prompt
from app.services import demo_service, rag_service
from app.services.llm_service import LLMProviderError
from app.tests.helpers import auth_headers, build_pdf, multipart_file

GUEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


@pytest.fixture()
def user(user_factory):
    return user_factory()


@pytest.fixture()
def demo_mode(monkeypatch, tmp_path):
    """Enable demo mode and keep file storage inside the test workspace."""
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    return settings


def _seed_demo_document(db) -> Document:
    """Insert an ACTIVE, PUBLIC demo document with a single chunk directly."""
    document = Document(
        id=demo_service.DEMO_DOCUMENT_ID,
        title=settings.DEMO_DOCUMENT_TITLE,
        description="Seeded demo document for tests.",
        status=DocumentStatus.ACTIVE,
        access_level=AccessLevel.PUBLIC,
        file_path="documents/demo/original.pdf",
        original_filename="demo.pdf",
        mime_type="application/pdf",
        file_size=1,
        uploaded_by=None,
    )
    db.add(document)
    db.flush()
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        status=DocumentStatus.ACTIVE,
        filename="demo.pdf",
        storage_path="documents/demo/original.pdf",
        file_size=1,
    )
    db.add(version)
    db.flush()
    document.current_version_id = version.id
    db.add(
        DocumentChunk(
            document_id=document.id,
            content="DocMind is a Retrieval-Augmented Generation document assistant.",
            embedding=[0.1] * settings.EMBEDDING_DIM,
            page_number=1,
            chunk_index=0,
            metadata_={},
        )
    )
    db.commit()
    return document


# ─── Mode gating ───


def test_demo_endpoints_disabled_when_mode_off(client):
    res = client.get("/api/demo/info")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "DEMO_MODE_DISABLED"

    res = client.post("/api/demo/chat", json={"message": "hello"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "DEMO_MODE_DISABLED"


def test_demo_info_reports_missing_index(client, demo_mode):
    res = client.get("/api/demo/info")
    assert res.status_code == 200
    body = res.json()
    assert body["demo_mode"] is True
    assert body["document_title"] == settings.DEMO_DOCUMENT_TITLE
    assert body["document_id"] == str(demo_service.DEMO_DOCUMENT_ID)
    assert body["status"] == "missing"
    assert body["chunk_count"] is None


def test_demo_chat_missing_index_returns_clear_error(client, demo_mode):
    res = client.post("/api/demo/chat", json={"message": "What is DocMind?"})
    assert res.status_code == 503
    error = res.json()["error"]
    assert error["code"] == "DEMO_INDEX_MISSING"
    assert "build_demo_index" in error["message"]


def test_demo_chat_empty_message_rejected(client, demo_mode, db_session):
    _seed_demo_document(db_session)
    res = client.post("/api/demo/chat", json={"message": ""})
    assert res.status_code == 422

    res = client.post(
        "/api/demo/chat",
        json={"message": "x" * (settings.MAX_MESSAGE_LENGTH + 1)},
    )
    assert res.status_code == 422


# ─── Demo chat pipeline wiring ───


def test_demo_chat_uses_demo_pipeline(db_session, demo_mode, monkeypatch):
    _seed_demo_document(db_session)
    captured: dict = {}

    def fake_answer_question(
        db,
        *,
        question,
        user,
        retrieval_service=None,
        llm_provider=None,
        document_ids=None,
        system_prompt_builder=None,
        fallback_answer=None,
    ):
        captured["question"] = question
        captured["user"] = user
        captured["document_ids"] = document_ids
        captured["system_prompt_builder"] = system_prompt_builder
        captured["fallback_answer"] = fallback_answer
        return rag_service.RagResult(answer="Demo answer", citations=[])

    monkeypatch.setattr(rag_service, "answer_question", fake_answer_question)

    result = demo_service.answer_demo_question(
        db_session, question="What is DocMind designed to do?"
    )

    assert result.answer == "Demo answer"
    assert captured["question"] == "What is DocMind designed to do?"
    assert captured["document_ids"] == [demo_service.DEMO_DOCUMENT_ID]
    assert captured["system_prompt_builder"] is build_demo_system_prompt
    assert captured["fallback_answer"] == DEMO_FALLBACK_ANSWER
    assert captured["user"].id == GUEST_USER_ID


def test_demo_chat_llm_failure_returns_demo_fallback(db_session, demo_mode, monkeypatch):
    _seed_demo_document(db_session)

    def boom(*args, **kwargs):
        raise LLMProviderError("no API key")

    monkeypatch.setattr(rag_service, "answer_question", boom)
    result = demo_service.answer_demo_question(db_session, question="hello")
    assert result.answer == DEMO_FALLBACK_ANSWER


def test_demo_chat_endpoint_returns_answer_and_citations(client, demo_mode, db_session, monkeypatch):
    _seed_demo_document(db_session)
    citation = {
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(demo_service.DEMO_DOCUMENT_ID),
        "document_title": settings.DEMO_DOCUMENT_TITLE,
        "page_number": 1,
        "section": None,
        "chunk_index": 0,
        "relevance_score": 0.91,
    }

    def fake_answer_question(
        db,
        *,
        question,
        user,
        retrieval_service=None,
        llm_provider=None,
        document_ids=None,
        system_prompt_builder=None,
        fallback_answer=None,
    ):
        return rag_service.RagResult(
            answer="Answer about: " + question,
            citations=[rag_service.citation_service.Citation(**citation)],
        )

    monkeypatch.setattr(rag_service, "answer_question", fake_answer_question)

    res = client.post(
        "/api/demo/chat",
        json={"message": "What were the three evaluation configurations?"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["demo_mode"] is True
    assert "Answer about:" in body["answer"]
    assert len(body["citations"]) == 1
    assert body["citations"][0]["document_id"] == str(demo_service.DEMO_DOCUMENT_ID)
    assert body["citations"][0]["document_title"] == settings.DEMO_DOCUMENT_TITLE


# ─── Index build (real demo PDF + deterministic embeddings) ───


def test_build_demo_index_creates_ready_document(db_session, demo_mode):
    document = demo_service.build_demo_index(db_session)

    assert document.id == demo_service.DEMO_DOCUMENT_ID
    assert document.status == DocumentStatus.ACTIVE
    assert document.access_level == AccessLevel.PUBLIC
    assert document.uploaded_by is None
    assert document.page_count == 2  # the real demo PDF has two pages

    chunk_count = demo_service.demo_chunk_count(db_session)
    assert chunk_count > 0
    assert demo_service.demo_index_ready(db_session)


def test_build_demo_index_is_idempotent(db_session, demo_mode):
    demo_service.build_demo_index(db_session)
    first = demo_service.demo_chunk_count(db_session)

    demo_service.build_demo_index(db_session)
    second = demo_service.demo_chunk_count(db_session)

    assert first == second
    assert demo_service.demo_index_ready(db_session)


def test_build_demo_index_missing_pdf(db_session, demo_mode, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_DOCUMENT_PATH", "does/not/exist.pdf")
    with pytest.raises(Exception) as excinfo:
        demo_service.build_demo_index(db_session)
    assert getattr(excinfo.value, "code", None) == "DEMO_DOCUMENT_MISSING"


# ─── Upload gating in demo mode ───


def test_upload_blocked_in_demo_mode(client, demo_mode, user):
    content = build_pdf(["DocMind demo", "Line two"])
    res = client.post(
        "/api/documents",
        headers=auth_headers(user),
        files=multipart_file(content, "visitor.pdf"),
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "DEMO_MODE"