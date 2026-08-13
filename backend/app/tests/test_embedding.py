"""Embedding service tests (using the deterministic fake encoder)."""

import pytest

from app.core.config import settings
from app.services.embedding_service import (
    EmbeddingService,
    get_embedding_service,
    set_embedding_service,
)


def test_dimension_matches_configured(fake_embedding_service):
    vectors = fake_embedding_service.embed(["college regulations"])
    assert len(vectors) == 1
    assert len(vectors[0]) == settings.EMBEDDING_DIM


def test_embedding_for_multiple_texts(fake_embedding_service):
    vectors = fake_embedding_service.embed(
        ["hostel rules", "exam ordinance", "scholarship criteria"]
    )
    assert len(vectors) == 3
    assert all(len(v) == settings.EMBEDDING_DIM for v in vectors)


def test_empty_input_returns_empty():
    svc = EmbeddingService(model_name="fake", expected_dim=settings.EMBEDDING_DIM)
    assert svc.embed([]) == []


def test_service_instance_is_reused(fake_embedding_service):
    first = get_embedding_service()
    second = get_embedding_service()
    assert first is second
    first.embed(["a"])
    first.embed(["b"])
    assert fake_embedding_service.calls >= 1


def test_real_service_rejected_dimension_mismatch():
    class WrongDimModel:
        def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
            return [[1.0, 2.0] for _ in texts]

    svc = EmbeddingService(model_name="fake", expected_dim=768)
    svc._model = WrongDimModel()
    with pytest.raises(RuntimeError, match="dimension mismatch"):
        svc.embed(["x"])


def test_set_embedding_service_allows_override():
    svc = EmbeddingService(model_name="fake", expected_dim=settings.EMBEDDING_DIM)
    set_embedding_service(svc)
    try:
        assert get_embedding_service() is svc
    finally:
        set_embedding_service(None)