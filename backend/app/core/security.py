"""Password hashing and JWT utilities.

Authentication logic lives here (not in route handlers) so it can be reused
by dependencies, services and tests. Secrets come from centralized settings.

Password hashing uses the maintained ``bcrypt`` library directly (``passlib``
is effectively unmaintained and breaks with current ``bcrypt`` releases).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings
from app.core.enums import Role
from app.core.errors import ApiError

# bcrypt only considers the first 72 bytes of a password; schema validation
# caps password length to 72 characters so this cannot silently truncate.
BCRYPT_PREFIX = "$2b$"


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt and return the encoded hash."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def create_access_token(
    user_id: str | uuid.UUID,
    role: Role,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT for the given user.

    Claims are intentionally minimal: subject (user id), role, issued-at and
    expiry. ``expires_delta`` defaults to ``ACCESS_TOKEN_EXPIRE_MINUTES`` from
    settings and can be overridden (used by tests to mint expired tokens).
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT, raising structured auth errors on failure.

    Distinguishes an expired token from other invalid-token conditions.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise ApiError(
            "TOKEN_EXPIRED",
            "Your session has expired. Please sign in again.",
            status_code=401,
        )
    except jwt.InvalidTokenError:
        raise ApiError(
            "INVALID_TOKEN",
            "Invalid authentication token.",
            status_code=401,
        )
