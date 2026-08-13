"""Centralized application configuration.

All runtime settings are read from environment variables (and an optional
``.env`` file in the working directory). No setting is hardcoded in
business logic.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "CampusRAG"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+psycopg://campusrag:campusrag_dev_password@localhost:5432/campusrag"
    )

    # --- Auth (used from Phase 2 onward, defined here for centralization) ---
    SECRET_KEY: str = "dev-secret-key-change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- CORS ---
    # NoDecode keeps the raw environment string so the `before` validator
    # below can split a comma-separated value.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # --- Embeddings (Phase 3) ---
    # Must match the vector dimension of the embedding model used in Phase 3+.
    EMBEDDING_DIM: int = 768
    # Sentence-transformers model name. Default output dimension must equal
    # EMBEDDING_DIM (BAAI/bge-base-en-v1.5 → 768).
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"

    # --- Document ingestion (Phase 3) ---
    # Root directory for local document storage. Relative paths are resolved
    # against the backend working directory. This storage implementation is
    # replaceable (see app/services/storage_service.py).
    STORAGE_DIR: str = "storage"
    # Maximum accepted upload size in bytes (20 MiB default).
    MAX_UPLOAD_SIZE_BYTES: int = 20 * 1024 * 1024
    # Character-based chunking parameters used by the ingestion pipeline.
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150

    # --- Retrieval (Phase 4) ---
    # Number of semantically similar chunks to retrieve per question.
    RETRIEVAL_TOP_K: int = 5
    # Minimum cosine similarity for a chunk to be used as evidence. Cosine
    # similarity ranges from -1 to 1; 0.65 filters out weak matches.
    RETRIEVAL_MIN_SIMILARITY: float = 0.65
    # Maximum characters of evidence text assembled into a single LLM prompt.
    MAX_CONTEXT_CHARS: int = 8000
    # Maximum length of a user question accepted by the chat API.
    MAX_MESSAGE_LENGTH: int = 2000

    # --- Hybrid retrieval (Phase 5) ---
    # Dense (pgvector) and BM25 (PostgreSQL FTS) candidate pool sizes. Each
    # retriever returns only its own top-K; the pools are merged by chunk id,
    # so deduplication never feeds thousands of chunks into the reranker.
    DENSE_CANDIDATE_K: int = 20
    BM25_CANDIDATE_K: int = 20
    # Number of fused candidates handed to the cross-encoder reranker.
    RERANK_TOP_K: int = 8
    # Weights for the normalized score fusion. Must sum to ~1.
    HYBRID_DENSE_WEIGHT: float = 0.6
    HYBRID_BM25_WEIGHT: float = 0.4
    # Cross-encoder reranker model (sentence-transformers).
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Batch size for cross-encoder inference.
    RERANKER_BATCH_SIZE: int = 8
    # Retrieval confidence gate: a query is only answered when the top
    # reranker relevance score (sigmoid-transformed, 0..1) meets this
    # threshold. Development heuristic; tune after inspecting real scores.
    CONFIDENCE_THRESHOLD: float = 0.35

    # --- LLM (Phase 4) ---
    # Provider key: "gemini" (Google Gemini, requires GEMINI_API_KEY) or
    # "local" (offline development provider that answers from the top
    # retrieved chunk - never used in production).
    LLM_PROVIDER: str = "gemini"
    # Default model; overridable via LLM_MODEL for a specific provider.
    LLM_MODEL: str = "gemini-flash-latest"
    GEMINI_API_KEY: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string from environment variables."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
