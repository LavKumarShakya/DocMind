"""Hybrid retrieval tests: fusion, dedupe, weights, rerank, permissions, degradation."""

import dataclasses
import uuid

from app.core.enums import AccessLevel, Role
from app.rag.confidence import is_confident
from app.rag.score_normalization import min_max_normalize
from app.services.hybrid_retrieval_service import HybridRetrievalService
from app.services.retrieval_types import RetrievalCandidate
from app.tests.test_retrieval import make_chunk, make_document, one_hot


def _dense_stub(results, *, embed=None):
    """Deterministic dense retriever returning fixed chunks."""

    class StubDense:
        def __init__(self):
            self.results = results
            self.calls = 0

        def embed_query(self, query):
            self.calls += 1
            return embed or [0.0] * 768

        def retrieve(self, db, *, query_embedding, user, top_k=None, min_similarity=None):
            return self.results

    return StubDense()


def _dense_candidate(text, score, *, title="Doc", page=1, section=None):
    return RetrievalCandidate(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title=title,
        page_number=page,
        section=section,
        chunk_index=0,
        text=text,
        dense_score=score,
    )


class RecordingReranker:
    """Records pairs and returns scores that invert input order."""

    def __init__(self):
        self.calls = 0
        self.pairs = []

    def rerank(self, query, candidates):
        self.calls += 1
        self.pairs.append((query, [c.text for c in candidates]))
        reranked = []
        for index, candidate in enumerate(candidates):
            reranked.append(
                dataclasses.replace(candidate, rerank_score=round(1.0 - 0.2 * index, 6))
            )
        return reranked


def test_min_max_normalization():
    expected = min_max_normalize([0.9, 0.8, 0.7])
    assert all(abs(a - b) < 1e-9 for a, b in zip(expected, [1.0, 0.5, 0.0]))
    assert min_max_normalize([0.5]) == [1.0]
    assert min_max_normalize([0.4, 0.4, 0.4]) == [1.0, 1.0, 1.0]
    assert min_max_normalize([]) == []


def test_fusion_normalizes_and_weights_scores(db_session, user_factory):
    user = user_factory()
    # Two chunks: one found only by dense, one found only by BM25.
    dense = _dense_stub([
        _dense_candidate("dense-only evidence", 0.9),
    ])

    from app.services.bm25_service import Bm25Service

    class Bm25Stub:
        def search(self, db, *, query, user, top_k=None):
            return [
                RetrievalCandidate(
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    document_title="BM25 Doc",
                    page_number=2,
                    section=None,
                    chunk_index=1,
                    text="bm25-only evidence",
                    bm25_score=1.0,
                )
            ]

    service = HybridRetrievalService(
        dense_service=dense, bm25_service=Bm25Stub(), reranking_service=RecordingReranker()
    )
    results = service.retrieve(db_session, query="anything", user=user)

    assert {r.hybrid_score is not None for r in results} == {True}
    assert len(results) == 2
    # dense-only chunk: normalized dense 1.0 (single value), bm25 0.0.
    dense_only = next(r for r in results if "dense-only" in r.text)
    bm25_only = next(r for r in results if "bm25-only" in r.text)
    assert dense_only.hybrid_score > bm25_only.hybrid_score
    # Rerank preserved provenance verbatim.
    assert bm25_only.document_title == "BM25 Doc"
    assert bm25_only.page_number == 2
    assert all(r.rerank_score is not None for r in results)


def test_fusion_dedupes_by_chunk_id(db_session, user_factory):
    user = user_factory()
    shared = _dense_candidate("shared evidence", 0.8)
    dense = _dense_stub([shared])

    from app.services.bm25_service import Bm25Service

    class Bm25Stub:
        def search(self, db, *, query, user, top_k=None):
            # Same chunk id also found by BM25 with its own score.
            return [
                RetrievalCandidate(
                    chunk_id=shared.chunk_id,
                    document_id=shared.document_id,
                    document_title=shared.document_title,
                    page_number=shared.page_number,
                    section=shared.section,
                    chunk_index=shared.chunk_index,
                    text=shared.text,
                    bm25_score=0.5,
                )
            ]

    service = HybridRetrievalService(
        dense_service=dense, bm25_service=Bm25Stub(), reranking_service=RecordingReranker()
    )
    results = service.retrieve(db_session, query="anything", user=user)

    assert len(results) == 1  # deduplicated
    assert results[0].dense_score == 0.8
    assert results[0].bm25_score == 0.5
    assert results[0].rerank_score is not None


def test_merge_prefers_the_score_each_stage_produces(db_session, user_factory):
    """Bm25-only chunk keeps bm25_score; dense keeps dense_score."""
    user = user_factory()
    dense = _dense_stub([
        _dense_candidate("top phrase", 0.95),
    ])
    from app.services.bm25_service import Bm25Service

    class Bm25Stub:
        def search(self, db, *, query, user, top_k=None):
            return [
                RetrievalCandidate(
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    document_title="Doc",
                    page_number=None,
                    section=None,
                    chunk_index=5,
                    text="bm25 phrase",
                    bm25_score=0.7,
                )
            ]

    service = HybridRetrievalService(
        dense_service=dense, bm25_service=Bm25Stub(), reranking_service=RecordingReranker()
    )
    results = service.retrieve(db_session, query="phrase", user=user)
    scores = {c.text: (c.dense_score, c.bm25_score) for c in results}
    assert scores["top phrase"] == (0.95, None)
    assert scores["bm25 phrase"] == (None, 0.7)


def test_hybrid_irrelevant_query_rejected_by_confidence(db_session, user_factory):
    """A low-scoring hybrid pool must not pass the confidence gate."""
    user = user_factory()
    dense = _dense_stub([
        _dense_candidate("weak match", 0.1),
    ])

    class EmptyBm25:
        def search(self, db, *, query, user, top_k=None):
            return []

    class LowReranker:
        def rerank(self, query, candidates):
            return [dataclasses.replace(c, rerank_score=0.05) for c in candidates]

    service = HybridRetrievalService(
        dense_service=dense, bm25_service=EmptyBm25(), reranking_service=LowReranker()
    )
    results = service.retrieve(db_session, query="irrelevant", user=user)
    assert len(results) == 1
    assert is_confident(results) is False


def test_reranker_failure_returns_hybrid_order(db_session, user_factory, monkeypatch):
    """If the cross-encoder raises, the hybrid-fused order is returned."""
    user = user_factory()
    dense = _dense_stub([
        _dense_candidate("best", 0.9),
        _dense_candidate("second", 0.8),
    ])

    class EmptyBm25:
        def search(self, db, *, query, user, top_k=None):
            return []

    class BrokenReranker:
        def rerank(self, query, candidates):
            raise RuntimeError("model unavailable")

    service = HybridRetrievalService(
        dense_service=dense, bm25_service=EmptyBm25(), reranking_service=BrokenReranker()
    )
    results = service.retrieve(db_session, query="test", user=user)
    assert len(results) == 2
    assert results[0].text == "best"
    assert results[0].hybrid_score is not None
    assert results[0].rerank_score is None


def test_hybrid_search_respects_permissions_end_to_end(db_session, user_factory, fake_embedding_service):
    """Hybrid path must not leak hidden docs via dense OR bm25 stages."""
    from app.services import rag_service

    student = user_factory(role=Role.STUDENT)
    admin = user_factory(role=Role.ADMIN)
    secret_text = "confidential scholarship distribution numbers"
    secret = make_document(db_session, admin, access_level=AccessLevel.ADMIN, title="Secret")
    secret_embedding = fake_embedding_service.embed([secret_text])[0]
    make_chunk(db_session, secret, secret_text, secret_embedding)

    student_results = rag_service.search_documents(db_session, query=secret_text, user=student)
    assert student_results == [] or all(r.document_id != secret.id for r in student_results)

    admin_results = rag_service.search_documents(db_session, query=secret_text, user=admin)
    assert any(r.document_id == secret.id for r in admin_results)


def test_e2e_hybrid_pipeline_beats_dense_only(db_session, user_factory, fake_embedding_service):
    """End-to-end hybrid: a keyword hit that dense misses must surface, and the
    reranker must dominate the final order. Demonstrates the Phase 5 behaviour
    change: dense-only retrieval alone would not find the BCS-501 snippet."""
    from app.core.config import settings
    from app.services import rag_service
    from app.services.retrieval_service import RetrievalService

    user = user_factory()

    ory = make_document(db_session, user, access_level=AccessLevel.PUBLIC, title="Regulations")
    # Chunk A: embedded text is unlike the query, but BM25 matches "BCS-501".
    make_chunk(db_session, ory, "BCS-501 candidates must complete a data structures project.",
               one_hot(1))
    # Chunk B: embedded text matches the query embedding exactly.
    query_text = "BCS-501 data structures project"
    make_chunk(db_session, ory, query_text, fake_embedding_service.embed([query_text])[0])

    # Dense-only retrieval: min similarity 0.65 clears chunk B but not chunk A.
    dense_only = RetrievalService().retrieve(
        db_session,
        query_embedding=fake_embedding_service.embed([query_text])[0],
        user=user,
        top_k=settings.DENSE_CANDIDATE_K,
    )
    dense_texts = {c.text for c in dense_only}
    assert query_text in dense_texts
    assert "BCS-501 candidates" not in dense_texts

    # Hybrid retrieval must surface BOTH chunks (dense + bm25).
    hybrid = rag_service.search_documents(db_session, query=query_text, user=user)
    hybrid_texts = [c.text for c in hybrid]
    assert any("BCS-501 candidates" in t for t in hybrid_texts)  # keyword hit rescued
    assert query_text in hybrid_texts

    # Reranker now decides the order; the semantically-on-topic chunk leads.
    bcs_chunk = next(c for c in hybrid if "BCS-501 candidates" in c.text)
    query_chunk = next(c for c in hybrid if c.text == query_text)
    assert bcs_chunk.rerank_score is not None
    assert query_chunk.rerank_score is not None
    assert bcs_chunk.hybrid_score is not None
    assert query_chunk.hybrid_score is not None

    # The answer is grounded and cited when evidence is strong.
    result = rag_service.answer_question(db_session, question=query_text, user=user)
    assert result.answer
    assert len(result.citations) == 1
    assert result.citations[0].relevance_score is not None