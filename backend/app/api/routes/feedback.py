"""Answer feedback endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.conversation import FeedbackRequest, FeedbackResponse
from app.services import feedback_service

router = APIRouter(tags=["feedback"])


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Rate an assistant answer",
)
def submit_feedback(
    payload: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """Rate (or re-rate) an assistant message in one of the user's conversations."""
    feedback = feedback_service.submit_feedback(
        db,
        user=current_user,
        message_id=payload.message_id,
        rating=payload.rating,
        reason=payload.reason,
    )
    return FeedbackResponse.model_validate(feedback)