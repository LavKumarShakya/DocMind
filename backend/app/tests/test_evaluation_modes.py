"""Unit tests for the retrieval mode drivers (baseline vs phase5) with fakes.

The drivers only exercise wiring and score propagation; the database and
models are replaced by injected fakes so no network/model/DB access happens.
"""

import uuid

from app.services.retrieval_service import RetrievedChunk
from app.services.retrieval_types import RetrievalCandidate
from evaluation.modes import BaselineRetriever, EVAL_TOP_K, Phase5Retriever


def _chunk(text: str, title: str = "academic_regulations") -> RetrievedChunk:
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


class FakeDense:
    """Deterministic dense service: embeds trivially, returns its chunk pool."""

    def __init__(self, chunks, top_k_ignore=False):
        self.chunks = chunks
        self.embed_calls = 0
        self.top_k_ignore = top_k_ignore

    def embed_query(self, query):
        self.embed_calls += 1
        return [0.5] * 8

    def retrieve(self, db, *, query_embedding, user, top_k):
        if self.top_k_ignore:
            return list(self.chunks)
        return list(self.chunks[:top_k])


class FakeBm25:
    def __init__(self, candidates):
        self.candidates = candidates

    def search(self, db, *, query, user, top_k):
        return list(self.candidates[:top_k])


class FakeRerank:
    def rerank(self, query, candidates):
        reranked = []
        for index, candidate in enumerate(candidates):
            reranked.append(
                RetrievalCandidate(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    document_title=candidate.document_title,
                    page_number=candidate.page_number,
                    section=candidate.section,
                    chunk_index=candidate.chunk_index,
                    text=candidate.text,
                    dense_score=candidate.dense_score,
                    bm25_score=candidate.bm25_score,
                    hybrid_score=candidate.hybrid_score,
                    rerank_score=round(1.0 - 0.1 * index, 6),
                )
            )
        reranked.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)
        return reranked


def test_baseline_retriever_returns_dense_results():
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    dense = FakeDense(chunks)
    driver = BaselineRetriever(dense_service=dense)

    outcome = driver.retrieve(None, query="q", user=None, top_k=EVAL_TOP_K)

    assert len(outcome.candidates) == 3
    assert outcome.candidates[0].document_title == "academic_regulations"
    assert outcome.candidates[0].dense_score == 0.9
    assert "dense" in outcome.times
    assert dense.embed_calls == 1


def test_phase5_retriever_fuses_and_reranks():
    dense_chunks = [_chunk("dense one"), _chunk("dense two")]
    bm25 = [
        RetrievalCandidate(
            chunk_id=uuid.uuid4(), document_id=uuid.uuid4(),
            document_title="academic_regulations", page_number=1, section=None,
            chunk_index=1, text="bm25 one", bm25_score=0.7,
        )
    ]
    driver = Phase5Retriever(
        dense_service=FakeDense(dense_chunks, top_k_ignore=True),
        bm25_service=FakeBm25(bm25),
        reranking_service=FakeRerank(),
    )

    outcome = driver.retrieve(None, query="q", user=None, top_k=EVAL_TOP_K)

    assert len(outcome.candidates) == 3
    assert all(c.rerank_score is not None for c in outcome.candidates)
    assert outcome.candidates[0].rerank_score >= outcome.candidates[-1].rerank_score
    for stage in ("dense", "bm25", "fuse", "rerank"):
        assert stage in outcome.times


def test_phase5_empty_pool_returns_empty():
    driver = Phase5Retriever(
        dense_service=FakeDense([], top_k_ignore=True),
        bm25_service=FakeBm25([]),
        reranking_service=FakeRerank(),
    )
    outcome = driver.retrieve(None, query="q", user=None, top_k=EVAL_TOP_K)
    assert outcome.candidates == []
    assert "fuse" in outcome.times