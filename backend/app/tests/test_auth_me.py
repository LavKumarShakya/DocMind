"""Tests for the current-user endpoint and token validation."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.enums import Role
from app.core.security import create_access_token
from app.tests.helpers import auth_header

ME_PATH = "/api/auth/me"


class TestCurrentUser:
    def test_valid_token(self, client, user_factory):
        user = user_factory()
        token = create_access_token(user.id, user.role)
        res = client.get(ME_PATH, headers=auth_header(token))
        assert res.status_code == 200
        body = res.json()
        assert body["id"] == str(user.id)
        assert body["email"] == user.email
        assert body["name"] == user.name
        assert "password" not in body

    def test_missing_token(self, client):
        res = client.get(ME_PATH)
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    def test_wrong_scheme(self, client):
        res = client.get(ME_PATH, headers={"Authorization": "Basic abc123"})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    def test_invalid_token(self, client):
        res = client.get(ME_PATH, headers=auth_header("garbage.token.value"))
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "INVALID_TOKEN"

    def test_malformed_token(self, client):
        res = client.get(ME_PATH, headers=auth_header("not-a-jwt"))
        assert res.status_code == 401

    def test_expired_token(self, client, user_factory):
        user = user_factory()
        token = create_access_token(user.id, user.role, expires_delta=timedelta(minutes=-5))
        res = client.get(ME_PATH, headers=auth_header(token))
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "TOKEN_EXPIRED"

    def test_token_signed_with_wrong_key(self, client, user_factory):
        user = user_factory()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "role": user.role.value,
            "iat": now,
            "exp": now + timedelta(minutes=30),
        }
        token = jwt.encode(payload, "totally-wrong-secret", algorithm=settings.ALGORITHM)
        res = client.get(ME_PATH, headers=auth_header(token))
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "INVALID_TOKEN"

    def test_token_for_deleted_user(self, client):
        token = create_access_token(uuid.uuid4(), Role.STUDENT)
        res = client.get(ME_PATH, headers=auth_header(token))
        assert res.status_code == 401

    def test_token_with_invalid_subject(self, client):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "not-a-uuid",
            "role": Role.STUDENT.value,
            "iat": now,
            "exp": now + timedelta(minutes=30),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        res = client.get(ME_PATH, headers=auth_header(token))
        assert res.status_code == 401
