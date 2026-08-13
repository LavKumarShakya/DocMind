"""BM25 (PostgreSQL FTS) retrieval tests: ranking, permissions, edge cases."""

from app.core.enums import AccessLevel, DocumentStatus, Role
from app.services.bm25_service import Bm25Service
from app.tests.test_retrieval import make_chunk, make_document, one_hot


def make_text_chunk(db, doc, text):
    """Chunk whose vector is a fixed one-hot; BM25 ignores embeddings."""
    return make_chunk(db, doc, text, one_hot(0))


def _search(db, query, user, top_k=10):
    return Bm25Service().search(db, query=query, user=user, top_k=top_k)


def test_bm25_returns_relevant_chunks_ranked(db_session, user_factory):
    user = user_factory()
    doc = make_document(db_session, user, access_level=AccessLevel.PUBLIC, title="Regs")
    make_text_chunk(db_session, doc, "Campus shuttle runs hourly between the library and hostel.")
    make_text_chunk(db_session, doc, "Shuttle schedule published every semester.")

    results = _search(db_session, "shuttle schedule", user)

    assert len(results) >= 1
    top = results[0]
    assert top.chunk_id is not None
    assert top.document_id == doc.id
    assert top.document_title == "Regs"
    assert top.bm25_score is not None
    assert "shuttle" in top.text.lower()
    # Ordering by ts_rank_cd: the chunk matching more tokens ranks first.
    scores = [r.bm25_score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_bm25_matches_course_codes(db_session, user_factory):
    user = user_factory()
    doc = make_document(db_session, user, access_level=AccessLevel.PUBLIC, title="Syllabus")
    make_text_chunk(db_session, doc, "Students taking BCS-501 must complete a data structures project.")
    make_text_chunk(db_session, doc, "Welcome week orientation is held in August.")

    results = _search(db_session, "BCS-501", user)

    assert len(results) == 1
    assert "BCS-501" in results[0].text


def test_bm25_permission_filter_in_sql(db_session, user_factory):
    student = user_factory(role=Role.STUDENT)
    admin = user_factory(role=Role.ADMIN)
    secret = make_document(db_session, student, access_level=AccessLevel.ADMIN, title="Secret")
    make_text_chunk(db_session, secret, "Confidential dean veto power over scholarships.")

    # Another student must not see the ADMIN-level doc through keywords.
    peer = user_factory(role=Role.STUDENT)
    peer_results = _search(db_session, "confidential dean veto", peer)
    assert peer_results == []

    admin_results = _search(db_session, "confidential dean veto", admin)
    assert len(admin_results) == 1


def test_bm25_only_active_documents(db_session, user_factory):
    user = user_factory()
    failed = make_document(db_session, user, access_level=AccessLevel.PUBLIC, title="Old")
    failed.status = DocumentStatus.FAILED
    db_session.add(failed)
    db_session.commit()

    active = make_document(db_session, user, access_level=AccessLevel.PUBLIC, title="Live")
    make_text_chunk(db_session, failed, "outdated parking policy details")
    make_text_chunk(db_session, active, "new parking policy details")

    results = _search(db_session, "parking policy", user)
    assert len(results) == 1
    assert results[0].document_title == "Live"


def test_bm25_empty_or_stopword_query_returns_nothing(db_session, user_factory):
    user = user_factory()
    doc = make_document(db_session, user, access_level=AccessLevel.PUBLIC)
    make_text_chunk(db_session, doc, "Interesting shuttle facts.")

    assert _search(db_session, "", user) == []
    assert _search(db_session, "the and or", user) == []


def test_bm25_honors_top_k(db_session, user_factory):
    user = user_factory()
    doc = make_document(db_session, user, access_level=AccessLevel.PUBLIC)
    for i in range(5):
        make_text_chunk(db_session, doc, f"annual campus transport policy update number {i}")

    results = _search(db_session, "campus transport policy", user, top_k=2)
    assert len(results) == 2


def test_bm25_no_embedding_required(db_session, user_factory):
    """BM25 works even when chunks have NULL embeddings."""
    user = user_factory()
    doc = make_document(db_session, user, access_level=AccessLevel.PUBLIC)
    make_chunk(db_session, doc, "Embeddingless chunk about fee reimbursement.", embedding=None)

    results = _search(db_session, "fee reimbursement", user)
    assert len(results) == 1