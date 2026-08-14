"""Conversation, message and citation persistence.

Phase 6 product layer: conversations persist across requests, assistant
messages keep their citations, and feedback references messages. The RAG
pipeline itself is untouched — this service only stores what the chat API
already produces.

Authorization is enforced here: every conversation access goes through
``get_owned_conversation`` which returns 404 for other users' conversations
(existence is never leaked).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import MessageRole
from app.core.errors import ApiError
from app.db.models import Citation, Conversation, DocumentChunk, Message, User
from app.services.citation_service import Citation as CitationData

MAX_TITLE_LENGTH = 60

# Leading words stripped when deriving a short title from the first question.
_TITLE_STOP_PREFIXES = frozenset(
    {
        "a", "an", "the", "what", "why", "how", "when", "where", "who", "whom",
        "whose", "which", "is", "are", "was", "were", "do", "does", "did",
        "can", "could", "would", "should", "will", "shall", "may", "might",
        "must", "i", "we", "tell", "explain", "give", "show", "need", "know",
    }
)
_TRAILING_PUNCTUATION = " ?!.,;:"


def generate_title(question: str) -> str:
    """Deterministic, short title derived from a user question (no LLM).

    ``"What is the minimum attendance requirement?"`` →
    ``"Minimum attendance requirement"``
    """
    words = question.strip().split()
    while words and words[0].lower().strip(_TRAILING_PUNCTUATION) in _TITLE_STOP_PREFIXES:
        words = words[1:]
    title = " ".join(words).strip(_TRAILING_PUNCTUATION)
    if not title:
        return "New conversation"
    if len(title) > MAX_TITLE_LENGTH:
        title = title[: MAX_TITLE_LENGTH - 1].rstrip()
    return title[0].upper() + title[1:]


def create_conversation(
    db: Session, *, user: User, title: str | None = None
) -> Conversation:
    """Create a conversation owned by ``user``."""
    conversation = Conversation(user_id=user.id, title=title or "New conversation")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, *, user: User) -> list[Conversation]:
    """Return only ``user``'s conversations, most recently active first."""
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
        ).all()
    )


def get_owned_conversation(
    db: Session, *, conversation_id: uuid.UUID, user: User, with_messages: bool = False
) -> Conversation:
    """Fetch ``user``'s conversation (404 hides other users' conversations)."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == user.id
    )
    if with_messages:
        stmt = stmt.options(
            selectinload(Conversation.messages).selectinload(Message.citations),
        )
    conversation = db.scalar(stmt)
    if conversation is None:
        raise ApiError(
            "CONVERSATION_NOT_FOUND",
            "The conversation could not be found.",
            status_code=404,
        )
    return conversation


def delete_conversation(db: Session, *, conversation: Conversation) -> None:
    """Delete a conversation; messages and citations cascade in the database."""
    db.delete(conversation)
    db.commit()


def _next_position(db: Session, *, conversation_id: uuid.UUID) -> int:
    current = db.scalar(
        select(func.max(Message.position)).where(
            Message.conversation_id == conversation_id
        )
    )
    return (current or 0) + 1


def add_message(
    db: Session,
    *,
    conversation: Conversation,
    role: MessageRole,
    content: str,
) -> Message:
    """Persist a message, bump conversation ordering and return it."""
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        position=_next_position(db, conversation_id=conversation.id),
    )
    db.add(message)
    # Touch the conversation so the list is ordered by recent activity even
    # when multiple messages arrive in the same transaction.
    conversation.updated_at = datetime.now(timezone.utc)
    db.add(conversation)
    db.commit()
    db.refresh(message)
    return message


def persist_citations(
    db: Session, *, message: Message, citations: list[CitationData]
) -> None:
    """Persist a message's citations, resolving chunk references.

    ``chunk_id`` is only stored when the chunk row actually exists (citations
    produced against a stubbed/removed pipeline never violate the FK). Document
    provenance (title, page, section, relevance) is always stored so the
    citation survives later chunk/document deletion.
    """
    chunk_ids = [c.chunk_id for c in citations if c.chunk_id]
    existing_chunks: set[uuid.UUID] = set()
    if chunk_ids:
        existing_chunks = set(
            db.scalars(
                select(DocumentChunk.id).where(DocumentChunk.id.in_(chunk_ids))
            ).all()
        )

    document_ids = [c.document_id for c in citations if c.document_id]
    existing_documents: set[uuid.UUID] = set()
    if document_ids:
        from app.db.models import Document

        existing_documents = set(
            db.scalars(
                select(Document.id).where(Document.id.in_(document_ids))
            ).all()
        )

    rows = []
    for citation in citations:
        chunk_id = None
        if citation.chunk_id:
            try:
                chunk_uuid = uuid.UUID(citation.chunk_id)
            except ValueError:
                chunk_uuid = None
            if chunk_uuid is not None and chunk_uuid in existing_chunks:
                chunk_id = chunk_uuid
        document_id = _coerce_uuid(citation.document_id)
        if document_id is not None and document_id not in existing_documents:
            document_id = None
        rows.append(
            Citation(
                message_id=message.id,
                chunk_id=chunk_id,
                document_id=document_id,
                document_title=citation.document_title,
                page_number=citation.page_number,
                section=citation.section,
                relevance_score=citation.relevance_score,
            )
        )
    if rows:
        db.add_all(rows)
        db.commit()


def _coerce_uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
