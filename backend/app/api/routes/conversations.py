"""Conversation endpoints: list, create, detail, delete.

Every endpoint is scoped to the authenticated user — another user's
conversation is indistinguishable from a missing one (404).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.conversation import (
    CitationDetail,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    MessageDetail,
)
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _summary(conversation) -> ConversationSummary:
    return ConversationSummary.model_validate(conversation)


def _detail(conversation) -> ConversationDetail:
    messages = [
        MessageDetail(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            citations=[
                CitationDetail(
                    chunk_id=str(citation.chunk_id) if citation.chunk_id else None,
                    document_id=(
                        str(citation.document_id) if citation.document_id else None
                    ),
                    document_title=citation.document_title,
                    page_number=citation.page_number,
                    section=citation.section,
                    relevance_score=citation.relevance_score,
                )
                for citation in message.citations
            ],
        )
        for message in conversation.messages
    ]
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=messages,
    )


@router.get(
    "",
    response_model=list[ConversationSummary],
    summary="List the current user's conversations",
)
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationSummary]:
    return [
        _summary(c)
        for c in conversation_service.list_conversations(db, user=current_user)
    ]


@router.post(
    "",
    response_model=ConversationSummary,
    status_code=201,
    summary="Create a conversation",
)
def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationSummary:
    return _summary(
        conversation_service.create_conversation(
            db, user=current_user, title=payload.title
        )
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    summary="Get a conversation with its messages and citations",
)
def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    conversation = conversation_service.get_owned_conversation(
        db, conversation_id=conversation_id, user=current_user, with_messages=True
    )
    conversation.messages.sort(key=lambda m: m.position)
    return _detail(conversation)


@router.delete(
    "/{conversation_id}",
    summary="Delete a conversation (messages and citations cascade)",
)
def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    conversation = conversation_service.get_owned_conversation(
        db, conversation_id=conversation_id, user=current_user
    )
    conversation_service.delete_conversation(db, conversation=conversation)
    return {"status": "deleted"}