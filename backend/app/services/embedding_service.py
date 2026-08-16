"""Embedding generation using sentence-transformers / BGE.

The model is loaded exactly once per process and reused for every chunk, so
ingestion never re-loads weights per request. On CPU the pipeline simply runs
slower — no GPU is required.

A single module-level instance is shared across the application. Tests may
replace it (``set_embedding_service``) with a deterministic fake so the suite
never downloads models.
"""

from __future__ import annotations

import logging
import threading

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Wraps a sentence-transformers model and enforces the configured dimension."""

    def __init__(self, model_name: str | None = None, expected_dim: int | None = None) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._expected_dim = expected_dim if expected_dim is not None else settings.EMBEDDING_DIM
        self._model = None
        self._lock = threading.Lock()

    @property
    def model(self):
        """Lazily load the underlying model (thread-safe, once per process)."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    if settings.DEMO_MODE:
                        import traceback

                        logger.error(
                            "[DEMO_GUARD] DEMO_MODE=%s — embedding model initialization "
                            "requested and BLOCKED. Caller:\n%s",
                            settings.DEMO_MODE,
                            "".join(traceback.format_stack()[:-1]),
                        )
                        raise RuntimeError(
                            "Embedding model initialization is forbidden in DEMO_MODE. "
                            "The public demo is model-free by design; do not call the "
                            "embedding service while DEMO_MODE=true."
                        )
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ImportError as exc:  # pragma: no cover - dependency is required
                        raise RuntimeError("sentence-transformers is not installed.") from exc
                    self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dimension(self) -> int:
        """Output dimension of the configured model, validated against settings."""
        probe = self.embed(["dimension probe"])
        return len(probe[0])

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning a list of float vectors."""
        if not texts:
            return []
        model = self.model
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        result = [list(map(float, row)) for row in vectors]
        for vector in result:
            if len(vector) != self._expected_dim:
                raise RuntimeError(
                    f"Embedding dimension mismatch: model '{self.model_name}' "
                    f"produces {len(vector)} dimensions but EMBEDDING_DIM is "
                    f"{self._expected_dim}. Update EMBEDDING_DIM to match the model."
                )
        return result


_instance: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Return the shared embedding service, creating it on first use."""
    global _instance
    if _instance is None:
        _instance = EmbeddingService()
    return _instance


def set_embedding_service(service: EmbeddingService | None) -> None:
    """Override the shared service (used by tests to avoid model downloads)."""
    global _instance
    _instance = service
