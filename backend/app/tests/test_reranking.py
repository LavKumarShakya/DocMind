"""Reranking service tests: sigmoid, ordering, metadata preservation, batching.

The real cross-encoder must never be downloaded in tests, so the underlying
model is stubbed and injected.
"""

import uuid

import pytest

from app.services.retrieval_types import RetrievalCandidate
from app.services.reranking_service import RerankingService


def _candidate(text, *, chunk_id=None, title="Regs", page=3):
    return RetrievalCandidate(
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title=title,
        page_number=page,
        section=None,
        chunk_index=1,
        text=text,
        dense_score=0.8,
    )


class StubModel:
    """Fake cross-encoder returning logits proportional to a keyword."""

    def __init__(self, keyword="answer"):
        self.keyword = keyword
        self.pairs = []
        self.batch_size = None

    def predict(self, pairs, batch_size=None, show_progress_bar=False):
        self.pairs = pairs
        self.batch_size = batch_size
        return [
            6.0 if self.keyword in candidate_text.lower() else -6.0
            for _query, candidate_text in pairs
        ]


def test_sigmoid_maps_logits_to_0_1():
    svc = RerankingService()
    assert svc._sigmoid(0.0) == pytest.approx(0.5, abs=1e-3)
    assert svc._sigmoid(6.0) > 0.99
    assert svc._sigmoid(-6.0) < 0.01


def test_rerank_scores_and_sorts_descending():
    svc = RerankingService()
    svc._model = StubModel(keyword="answer")
    candidates = [
        _candidate("this is the answer to the question"),
        _candidate("unrelated parking notice"),
    ]
    reranked = svc.rerank("what is the answer?", candidates)

    assert [c.rerank_score for c in reranked] == sorted(
        (c.rerank_score for c in reranked), reverse=True
    )
    assert reranked[0].text == "this is the answer to the question"
    assert reranked[0].rerank_score > 0.99
    assert reranked[1].rerank_score < 0.01


def test_rerank_preserves_provenance_verbatim():
    svc = RerankingService()
    svc._model = StubModel(keyword="answer")
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    candidate = RetrievalCandidate(
        chunk_id=chunk_id,
        document_id=doc_id,
        document_title="Academic Regulations",
        page_number=7,
        section="4.2",
        chunk_index=3,
        text="answer content here",
        dense_score=0.9,
        bm25_score=0.4,
        hybrid_score=0.7,
    )
    reranked = svc.rerank("answer", [candidate])

    assert len(reranked) == 1
    kept = reranked[0]
    assert kept.chunk_id == chunk_id
    assert kept.document_id == doc_id
    assert kept.document_title == "Academic Regulations"
    assert kept.page_number == 7
    assert kept.section == "4.2"
    assert kept.chunk_index == 3
    assert kept.text == "answer content here"
    assert kept.dense_score == 0.9
    assert kept.bm25_score == 0.4
    assert kept.hybrid_score == 0.7
    assert kept.rerank_score is not None


def test_rerank_empty_short_circuits_without_model():
    svc = RerankingService()

    class ExplodingModel:
        def predict(self, *args, **kwargs):
            raise AssertionError("must not load/run model for empty input")

    svc._model = ExplodingModel()
    assert svc.rerank("anything", []) == []


def test_rerank_uses_batch_size():
    svc = RerankingService()
    model = StubModel(keyword="answer")
    svc._model = model
    svc.rerank("answer", [_candidate("answer")])
    assert model.batch_size == svc.batch_size
    assert len(model.pairs) == 1
    assert model.pairs[0] == ("answer", "answer")


def test_singleton_holder_set_get_roundtrip():
    from app.services.reranking_service import get_reranking_service, set_reranking_service

    set_reranking_service(None)
    svc = get_reranking_service()
    assert isinstance(svc, RerankingService)
    set_reranking_service(svc)  # idempotent
    assert get_reranking_service() is svc