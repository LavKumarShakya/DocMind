"""Authentication business logic.

Role assignment is always performed server-side. A newly registered user is
created with the ``STUDENT`` role; a role value sent by the client is never
trusted (the registration schema rejects unknown fields anyway).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import ApiError
from app.core.security import hash_password, verify_password
from app.db.models import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Session, *, name: str, email: str, password: str) -> User:
    """Create a new user, rejecting duplicate emails with a 409."""
    normalized_email = normalize_email(email)

    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise ApiError(
            "EMAIL_ALREADY_REGISTERED",
            "An account with this email already exists.",
            status_code=409,
        )

    user = User(
        name=name.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
        role=Role.STUDENT,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    """Verify credentials and return the matching user.

    The same error is raised for an unknown email and a wrong password so the
    API does not leak which emails are registered.
    """
    normalized_email = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized_email))

    if user is None or not verify_password(password, user.password_hash):
        raise ApiError(
            "INVALID_CREDENTIALS",
            "Invalid email or password.",
            status_code=401,
        )

    return user
