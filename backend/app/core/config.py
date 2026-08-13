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
        env_file=".env",
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
