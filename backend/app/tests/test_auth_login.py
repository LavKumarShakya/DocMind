"""Tests for login and JWT issuance."""

import jwt

from app.core.config import settings
from app.core.enums import Role

LOGIN_PATH = "/api/auth/login"


def _login(client, email: str, password: str):
    return client.post(
        LOGIN_PATH, data={"username": email, "password": password}
    )


class TestLogin:
    def test_correct_credentials(self, client, user_factory):
        user = user_factory(email="login@example.com", password="secret123")
        res = _login(client, "login@example.com", "secret123")
        assert res.status_code == 200
        body = res.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"]["id"] == str(user.id)
        assert body["user"]["role"] == Role.STUDENT.value
        assert "password" not in body and "password_hash" not in body

    def test_incorrect_password(self, client, user_factory):
        user_factory(email="wrong@example.com", password="correct123")
        res = _login(client, "wrong@example.com", "wrongpass")
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_unknown_user_same_error_as_wrong_password(self, client, user_factory):
        user_factory(email="known@example.com", password="correct123")
        unknown = _login(client, "unknown@example.com", "correct123").json()
        wrong = _login(client, "known@example.com", "wrongpass").json()
        assert unknown == wrong
        assert wrong["error"]["code"] == "INVALID_CREDENTIALS"

    def test_email_is_case_insensitive(self, client, user_factory):
        user_factory(email="mixed@example.com", password="secret123")
        res = _login(client, "MIXED@EXAMPLE.COM", "secret123")
        assert res.status_code == 200

    def test_token_contains_expected_claims(self, client, user_factory):
        user = user_factory(email="claims@example.com", password="secret123")
        res = _login(client, "claims@example.com", "secret123")
        token = res.json()["access_token"]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == str(user.id)
        assert payload["role"] == Role.STUDENT.value
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]
