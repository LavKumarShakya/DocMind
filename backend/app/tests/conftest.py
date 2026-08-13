"""Shared pytest fixtures.

Tests run against a dedicated PostgreSQL database (``campusrag_test``), not
the development database. The schema is created with ``Base.metadata.create_all``
which is kept in sync with the ORM models by ``alembic check``.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.enums import Role
from app.core.security import hash_password
from app.db.database import Base, get_db
from app.db.models import User
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    settings.DATABASE_URL.rsplit("/", 1)[0] + "/campusrag_test",
)
def _ensure_test_database() -> None:
    """Create the test database if it does not exist."""
    base_url = settings.DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    engine = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'campusrag_test'")
        ).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE campusrag_test"))
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_before_each(engine):
    """Start every test from an empty database for isolation."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE feedback, citations, messages, conversations, "
                "document_chunks, documents, users RESTART IDENTITY CASCADE"
            )
        )
        conn.commit()
    yield


@pytest.fixture(scope="session")
def engine():
    _ensure_test_database()

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(engine):
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture()
def client(engine):
    TestSession = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def user_factory(engine):
    """Insert a user directly into the test database (password hashed)."""

    def _create(
        name: str = "Test User",
        email: str | None = None,
        password: str = "password123",
        role: Role = Role.STUDENT,
    ) -> User:
        TestSession = sessionmaker(bind=engine, expire_on_commit=False)
        session = TestSession()
        try:
            user = User(
                name=name,
                email=email or f"user-{uuid.uuid4().hex[:10]}@example.com",
                password_hash=hash_password(password),
                role=role,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
        finally:
            session.close()

    return _create


@pytest.fixture(autouse=True)
def fake_embedding_service():
    """Replace the shared embedding service with a deterministic fake.

    Guarantees the test suite never downloads a model and that vector
    dimension always matches settings.EMBEDDING_DIM.
    """
    from app.services.embedding_service import set_embedding_service

    class FakeEmbeddingService:
        model_name = "fake/test-model"

        def __init__(self):
            self.calls = 0

        def embed(self, texts: list[str]) -> list[list[float]]:
            self.calls += 1
            dim = settings.EMBEDDING_DIM
            return [
                [float((hash(text) + i) % 997) / 997.0 for i in range(dim)]
                for text in texts
            ]

    fake = FakeEmbeddingService()
    set_embedding_service(fake)
    yield fake
    set_embedding_service(None)


@pytest.fixture(autouse=True)
def fake_llm_provider():
    """Replace the shared LLM provider with a deterministic fake.

    Guarantees the test suite never calls a paid/network LLM. The fake answers
    with the question echoed plus a ``Sources: [1]`` citation so citation
    mapping is exercised end-to-end. Tests that need specific behaviour can
    call ``set_llm_provider`` themselves.
    """
    from app.services.llm_service import set_llm_provider

    class FakeLLMProvider:
        name = "fake"

        def __init__(self):
            self.calls = 0
            self.questions: list[str] = []

        def answer(self, *, system_prompt: str, question: str) -> str:
            self.calls += 1
            self.questions.append(question)
            return f"Answer about: {question}\n\nSources: [1]"

    fake = FakeLLMProvider()
    set_llm_provider(fake)
    yield fake
    set_llm_provider(None)
