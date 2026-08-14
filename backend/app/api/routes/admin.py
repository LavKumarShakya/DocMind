"""Admin-only endpoints.

All endpoints require the ADMIN role (server-side). Responses are minimal and
never include password hashes, tokens, secrets or internal filesystem paths.
Administrative document actions (delete, access-level change, process) reuse
the existing document endpoints, which already allow ADMIN management — nothing
is duplicated here.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_role
from app.core.enums import DocumentStatus, Role
from app.core.errors import ApiError
from app.db.database import get_db
from app.db.models import Conversation, Document, Feedback, User
from app.schemas.admin import (
    AdminDocumentResponse,
    AdminRoleUpdate,
    AdminStatsResponse,
    AdminUserResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/test",
    dependencies=[Depends(require_role(Role.ADMIN))],
    summary="Admin-only access check",
)
def admin_test() -> dict:
    """Return 200 only for ADMIN users; 401 unauthenticated / 403 otherwise."""
    return {"status": "admin_access_ok"}


@router.get(
    "/users",
    response_model=list[AdminUserResponse],
    summary="List all users",
)
def admin_users(
    current_user: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> list[AdminUserResponse]:
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [AdminUserResponse.model_validate(user) for user in users]


@router.patch(
    "/users/{user_id}/role",
    response_model=AdminUserResponse,
    summary="Change a user's role",
)
def admin_set_role(
    user_id: uuid.UUID,
    payload: AdminRoleUpdate,
    current_user: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    """Change a user's role, refusing to demote the last remaining ADMIN."""
    target = db.get(User, user_id)
    if target is None:
        raise ApiError("USER_NOT_FOUND", "User not found.", status_code=404)

    if target.role == Role.ADMIN and payload.role != Role.ADMIN:
        admin_count = db.scalar(
            select(func.count(User.id)).where(User.role == Role.ADMIN)
        )
        if (admin_count or 0) <= 1:
            raise ApiError(
                "LAST_ADMIN",
                "Cannot demote the last administrator.",
                status_code=422,
            )

    target.role = payload.role
    db.add(target)
    db.commit()
    db.refresh(target)
    return AdminUserResponse.model_validate(target)


@router.get(
    "/documents",
    response_model=list[AdminDocumentResponse],
    summary="List all documents with ownership and version metadata",
)
def admin_documents(
    current_user: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> list[AdminDocumentResponse]:
    documents = db.scalars(
        select(Document)
        .options(selectinload(Document.uploader))
        .order_by(Document.created_at.desc())
    ).all()
    responses = []
    for document in documents:
        response = AdminDocumentResponse.model_validate(document)
        response.owner_name = document.uploader.name if document.uploader else None
        from app.db.models import DocumentChunk

        response.chunk_count = db.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document.id
            )
        )
        responses.append(response)
    return responses


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="Database-backed system statistics",
)
def admin_stats(
    current_user: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> AdminStatsResponse:
    """Real counts from the database — never hardcoded."""
    users = db.scalar(select(func.count(User.id))) or 0
    documents = db.scalar(select(func.count(Document.id))) or 0
    active_documents = (
        db.scalar(
            select(func.count(Document.id)).where(Document.status == DocumentStatus.ACTIVE)
        )
        or 0
    )
    failed_documents = (
        db.scalar(
            select(func.count(Document.id)).where(Document.status == DocumentStatus.FAILED)
        )
        or 0
    )
    conversations = db.scalar(select(func.count(Conversation.id))) or 0
    feedback_entries = db.scalar(select(func.count(Feedback.id))) or 0
    return AdminStatsResponse(
        users=users,
        documents=documents,
        active_documents=active_documents,
        failed_documents=failed_documents,
        conversations=conversations,
        feedback_entries=feedback_entries,
    )