"""Reusable authentication and authorization dependencies.

These enforce access control server-side. The frontend is never treated as an
authorization boundary.
"""

import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import ApiError
from app.core.security import decode_access_token
from app.db.database import get_db
from app.db.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the `Authorization: Bearer` token.

    Raises ``AUTHENTICATION_REQUIRED`` (401) when credentials are missing or
    use the wrong scheme, and ``INVALID_TOKEN``/``TOKEN_EXPIRED`` (401) when
    the token is malformed, invalid or expired.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            "AUTHENTICATION_REQUIRED",
            "Authentication is required.",
            status_code=401,
        )

    payload = decode_access_token(credentials.credentials)

    subject = payload.get("sub")
    if not subject:
        raise ApiError("INVALID_TOKEN", "Invalid authentication token.", status_code=401)
    try:
        user_id = uuid.UUID(str(subject))
    except (ValueError, TypeError):
        raise ApiError("INVALID_TOKEN", "Invalid authentication token.", status_code=401)

    user = db.get(User, user_id)
    if user is None:
        raise ApiError("INVALID_TOKEN", "Invalid authentication token.", status_code=401)

    return user


# Convenience alias: any authenticated user.
require_authenticated_user = get_current_user


def require_role(*allowed_roles: Role):
    """Factory returning a dependency that restricts access to given roles.

    Usage: ``Depends(require_role(Role.ADMIN))`` or, for several roles,
    ``Depends(require_role(Role.FACULTY, Role.ADMIN))``.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ApiError(
                "FORBIDDEN",
                "You do not have permission to access this resource.",
                status_code=403,
            )
        return current_user

    return dependency
