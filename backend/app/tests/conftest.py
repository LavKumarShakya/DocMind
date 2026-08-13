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
