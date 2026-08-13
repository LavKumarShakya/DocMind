"""Retrieval service tests: pgvector ranking, similarity threshold, permission filtering."""

import uuid

from app.core.config import settings
from app.core.enums import AccessLevel, DocumentStatus, Role
from app.db.models import Document, DocumentChunk
from app.services.retrieval_service import RetrievalService


def one_hot(dimension: int, *, dims: int | None = None) -> list[float]:
    dims = dims or settings.EMBEDDING_DIM
    vector = [0.0] * dims
    if dimension < dims:
        vector[dimension] = 1.0
    return vector


def make_document(db, user, *, access_level: AccessLevel, title: str = "Doc") -> Document:
    doc = Document(
        id=uuid.uuid4(),
        title=title,
        status=DocumentStatus.ACTIVE,
        access_level=access_level,
        original_filename=f"{title}.pdf",
        mime_type="application/pdf",
        file_size=100,
        file_path=f"storage/{uuid.uuid4().hex}.pdf",
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def make_chunk(db, doc: Document, text: str, embedding: list[float], *, page_number: int = 1) -> DocumentChunk:
    chunk = DocumentChunk(
        document_id=doc.id,
        content=text,
        embedding=embedding,
        page_number=page_number,
        chunk_index=0,
        metadata_={"document_id": str(doc.id)},
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


def test_retrieval_returns_chunks_ordered_by_similarity(
    db_session, user_factory, fake_embedding_service
):
    user = user_factory()
    doc = make_document(db_session, user, access_level=AccessLevel.PUBLIC)
    make_chunk(db_session, doc, "campus shuttle schedule", one_hot(0))
    make_chunk(db_session, doc, "football tryouts", one_hot(1))

    service = RetrievalService()
    results = service.retrieve(
        db_session,
        query_embedding=one_hot(0),
        user=user,
        top_k=10,
        min_similarity=0.5,
    )

    assert len(results) == 1
    assert results[0].document_id == doc.id
    assert results[0].document_title == "Doc"
    assert "campus shuttle" in results[0].text
    assert results[0].score == 1.0


def test_retrieval_respects_top_k(db_session, user_factory):
    user = user_factory()
    doc = make_document(db_session, user, access_level=AccessLevel.PUBLIC)
    for i in range(5):
        make_chunk(db_session, doc, f"chunk {i}", one_hot(0))

    results = RetrievalService().retrieve(
        db_session, query_embedding=one_hot(0), user=user, top_k=3, min_similarity=0.1
    )
    assert len(results) == 3


def test_retrieval_filters_out_below_threshold(db_session, user_factory):
    user = user_factory()
    doc = make_document(db_session, user, access_level=AccessLevel.PUBLIC)
    make_chunk(db_session, doc, "campus shuttle", one_hot(2))

    results = RetrievalService().retrieve(
        db_session, query_embedding=one_hot(0), user=user, top_k=10, min_similarity=0.9
    )
    assert results == []


def test_retrieval_hides_admin_level_documents_from_student(
    db_session, user_factory
):
    student = user_factory(role=Role.STUDENT)
    admin = user_factory(role=Role.ADMIN)
    doc = make_document(db_session, admin, access_level=AccessLevel.ADMIN)
    make_chunk(db_session, doc, "dean's confidential memo", one_hot(0))

    student_results = RetrievalService().retrieve(
        db_session, query_embedding=one_hot(0), user=student, top_k=10, min_similarity=0.5
    )
    assert student_results == []

    admin_results = RetrievalService().retrieve(
        db_session, query_embedding=one_hot(0), user=admin, top_k=10, min_similarity=0.5
    )
    assert len(admin_results) == 1


def test_retrieval_shows_uploader_even_for_elevated_level(db_session, user_factory):
    student = user_factory(role=Role.STUDENT)
    peer = user_factory(role=Role.STUDENT)
    doc = make_document(db_session, student, access_level=AccessLevel.FACULTY)
    make_chunk(db_session, doc, "faculty-only results", one_hot(0))

    uploader_results = RetrievalService().retrieve(
        db_session, query_embedding=one_hot(0), user=student, top_k=10, min_similarity=0.5
    )
    assert len(uploader_results) == 1  # the uploader sees their own document

    peer_results = RetrievalService().retrieve(
        db_session, query_embedding=one_hot(0), user=peer, top_k=10, min_similarity=0.5
    )
    assert peer_results == []  # a different student does not


def test_retrieval_only_considers_active_documents(db_session, user_factory):
    user = user_factory()
    failed = make_document(db_session, user, access_level=AccessLevel.PUBLIC, title="Failed")
    failed.status = DocumentStatus.FAILED
    db_session.add(failed)
    db_session.commit()

    active = make_document(db_session, user, access_level=AccessLevel.PUBLIC, title="Active")
    make_chunk(db_session, failed, "old content", one_hot(0))
    make_chunk(db_session, active, "new content", one_hot(0))

    results = RetrievalService().retrieve(
        db_session, query_embedding=one_hot(0), user=user, top_k=10, min_similarity=0.5
    )
    assert len(results) == 1
    assert results[0].document_title == "Active"