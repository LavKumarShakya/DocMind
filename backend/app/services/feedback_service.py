"""Answer feedback (rate an assistant answer).

One rating per assistant message per user: submitting again updates the
existing entry (upsert), so a changed opinion does not create duplicates. The
user id always comes from the authenticated request, never the client.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import MessageRole
from app.core.errors import ApiError
from app.db.models import Feedback, Message, User

MIN_RATING = 1
MAX_RATING = 5


def submit_feedback(
    db: Session,
    *,
    user: User,
    message_id: uuid.UUID,
    rating: int,
    reason: str | None = None,
) -> Feedback:
    """Validate and persist (or update) a rating for an assistant answer."""
    message = db.get(Message, message_id)
    if message is None:
        raise ApiError(
            "MESSAGE_NOT_FOUND",
            "The message could not be found.",
            status_code=404,
        )

    if message.role != MessageRole.ASSISTANT:
        raise ApiError(
            "FEEDBACK_NOT_ALLOWED",
            "Feedback can only be given on assistant answers.",
            status_code=422,
        )

    if message.conversation.user_id != user.id:
        raise ApiError(
            "FORBIDDEN",
            "You do not have permission to rate this message.",
            status_code=403,
        )

    if not MIN_RATING <= rating <= MAX_RATING:
        raise ApiError(
            "INVALID_RATING",
            f"Rating must be between {MIN_RATING} and {MAX_RATING}.",
            status_code=422,
        )

    existing = db.scalar(
        select(Feedback).where(
            Feedback.user_id == user.id, Feedback.message_id == message_id
        )
    )
    if existing is not None:
        existing.rating = rating
        existing.reason = reason
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    feedback = Feedback(
        message_id=message_id, user_id=user.id, rating=rating, reason=reason
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback