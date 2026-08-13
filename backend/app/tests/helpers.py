"""Shared helpers for tests."""

from app.core.enums import Role
from app.core.security import create_access_token


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_token(user_id, role: Role) -> str:
    return create_access_token(user_id, role)
