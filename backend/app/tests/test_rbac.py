"""Tests for role-based access control (RBAC)."""

from app.core.enums import Role
from app.core.security import create_access_token
from app.tests.helpers import auth_header

ADMIN_PATH = "/api/admin/test"


class TestAdminOnlyEndpoint:
    def test_unauthenticated_returns_401(self, client):
        res = client.get(ADMIN_PATH)
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    def test_student_returns_403(self, client, user_factory):
        user = user_factory(role=Role.STUDENT)
        token = create_access_token(user.id, user.role)
        res = client.get(ADMIN_PATH, headers=auth_header(token))
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "FORBIDDEN"

    def test_faculty_returns_403(self, client, user_factory):
        user = user_factory(role=Role.FACULTY)
        token = create_access_token(user.id, user.role)
        res = client.get(ADMIN_PATH, headers=auth_header(token))
        assert res.status_code == 403

    def test_admin_returns_200(self, client, user_factory):
        user = user_factory(role=Role.ADMIN)
        token = create_access_token(user.id, user.role)
        res = client.get(ADMIN_PATH, headers=auth_header(token))
        assert res.status_code == 200
        assert res.json()["status"] == "admin_access_ok"


class TestRoleScopedAccess:
    def test_me_accessible_to_every_role(self, client, user_factory):
        for role in (Role.STUDENT, Role.FACULTY, Role.ADMIN):
            user = user_factory(role=role)
            token = create_access_token(user.id, user.role)
            res = client.get("/api/auth/me", headers=auth_header(token))
            assert res.status_code == 200
            assert res.json()["role"] == role.value
