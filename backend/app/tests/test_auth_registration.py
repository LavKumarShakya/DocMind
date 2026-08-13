"""Tests for user registration."""

from sqlalchemy import select

from app.core.enums import Role
from app.core.security import verify_password
from app.db.models import User

REGISTER_PATH = "/api/auth/register"


class TestRegistration:
    def test_successful_registration(self, client):
        res = client.post(
            REGISTER_PATH,
            json={
                "name": "Student One",
                "email": "student1@example.com",
                "password": "securepass123",
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["email"] == "student1@example.com"
        assert body["name"] == "Student One"
        assert body["role"] == Role.STUDENT.value
        assert body["id"]
        assert body["created_at"]
        # never expose the password or its hash
        assert "password" not in body
        assert "password_hash" not in body

    def test_email_is_normalized(self, client):
        res = client.post(
            REGISTER_PATH,
            json={
                "name": "Case User",
                "email": "  CASE@Example.COM ",
                "password": "securepass123",
            },
        )
        assert res.status_code == 201
        assert res.json()["email"] == "case@example.com"

    def test_duplicate_email_rejected(self, client, user_factory):
        user_factory(email="dup@example.com")
        res = client.post(
            REGISTER_PATH,
            json={"name": "Dup", "email": "dup@example.com", "password": "securepass123"},
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

    def test_duplicate_email_case_insensitive(self, client, user_factory):
        user_factory(email="dup@example.com")
        res = client.post(
            REGISTER_PATH,
            json={"name": "Dup", "email": "DUP@EXAMPLE.COM", "password": "securepass123"},
        )
        assert res.status_code == 409

    def test_invalid_email_rejected(self, client):
        res = client.post(
            REGISTER_PATH,
            json={"name": "Bad", "email": "not-an-email", "password": "securepass123"},
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_short_password_rejected(self, client):
        res = client.post(
            REGISTER_PATH,
            json={"name": "Bad", "email": "short@example.com", "password": "1234567"},
        )
        assert res.status_code == 422

    def test_missing_fields_rejected(self, client):
        res = client.post(REGISTER_PATH, json={"email": "x@example.com"})
        assert res.status_code == 422

    def test_password_is_hashed(self, client, db_session):
        client.post(
            REGISTER_PATH,
            json={"name": "Hash Check", "email": "hash@example.com", "password": "securepass123"},
        )
        user = db_session.scalar(select(User).where(User.email == "hash@example.com"))
        assert user is not None
        assert user.password_hash != "securepass123"
        assert user.password_hash.startswith("$2b$")
        assert verify_password("securepass123", user.password_hash) is True

    def test_admin_role_cannot_be_self_selected(self, client):
        # sending a role field is rejected outright (extra="forbid")
        res = client.post(
            REGISTER_PATH,
            json={
                "name": "Sneaky",
                "email": "sneaky@example.com",
                "password": "securepass123",
                "role": "ADMIN",
            },
        )
        assert res.status_code == 422
