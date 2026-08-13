"""Document CRUD, visibility and authorization logic.

Authorization is enforced here (server-side) — never by the frontend. A
document is **visible** to a user when they uploaded it or the document's
access level matches their role. Only the uploader or an ADMIN may **manage**
(edit / process / delete) a document.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import AccessLevel, DocumentStatus, Role
from app.core.errors import ApiError
from app.db.models import Document, DocumentChunk, User

# Higher value = more privileged.
_LEVEL_ORDER: dict[AccessLevel, int] = {
    AccessLevel.PUBLIC: 0,
    AccessLevel.STUDENT: 1,
    AccessLevel.FACULTY: 2,
    AccessLevel.ADMIN: 3,
}

_ALLOWED_UPDATE_FIELDS = frozenset(
    {"title", "description", "department", "category", "version", "effective_date", "access_level"}
)


def create_document(
    db: Session,
    *,
    document_id: uuid.UUID,
    uploader: User,
    original_filename: str,
    mime_type: str,
    file_size: int,
    file_path: str,
    title: str | None = None,
    description: str | None = None,
    department: str | None = None,
    category: str | None = None,
    effective_date: date | None = None,
    access_level: AccessLevel = AccessLevel.PUBLIC,
) -> Document:
    """Create an UPLOADED document owned by ``uploader``."""
    document = Document(
        id=document_id,
        title=title or _title_from_filename(original_filename),
        description=description,
        department=department,
        category=category,
        version="1",
        effective_date=effective_date,
        status=DocumentStatus.UPLOADED,
        access_level=access_level,
        file_path=file_path,
        original_filename=original_filename,
        mime_type=mime_type,
        file_size=file_size,
        uploaded_by=uploader.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def _title_from_filename(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return stem[:500] or "Untitled document"


def get_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise ApiError("DOCUMENT_NOT_FOUND", "Document not found.", status_code=404)
    return document


def _is_visible(user: User, document: Document) -> bool:
    if document.uploaded_by == user.id:
        return True
    if document.access_level == AccessLevel.PUBLIC:
        return True
    return _LEVEL_ORDER[user.role] >= _LEVEL_ORDER[document.access_level]


def get_visible_document(db: Session, document_id: uuid.UUID, user: User) -> Document:
    """Fetch a document the user is allowed to see (404 hides existence)."""
    document = get_document(db, document_id)
    if not _is_visible(user, document):
        raise ApiError("DOCUMENT_NOT_FOUND", "Document not found.", status_code=404)
    return document


def get_manageable_document(db: Session, document_id: uuid.UUID, user: User) -> Document:
    """Fetch a document the user may manage (uploader or ADMIN only)."""
    document = get_document(db, document_id)
    if document.uploaded_by != user.id and user.role != Role.ADMIN:
        raise ApiError(
            "FORBIDDEN",
            "You do not have permission to modify this document.",
            status_code=403,
        )
    return document


def list_documents(db: Session, user: User) -> list[Document]:
    """Return documents visible to ``user`` (uploaded by them or level-matched)."""
    return list(
        db.scalars(
            select(Document)
            .where(visible_condition(user))
            .order_by(Document.created_at.desc())
        ).all()
    )


def _level_filter(user: User, column) -> object:
    """Access levels a role may view — mirrors ``_is_visible`` exactly.

    A user sees a document when their role rank is >= the document's access
    level rank. PUBLIC (rank 0) is viewable by every role and is therefore
    always included in the allowed set.
    """
    max_level = _LEVEL_ORDER[user.role]
    allowed = [level for level, order in _LEVEL_ORDER.items() if order <= max_level]
    return column.in_(allowed)


def visible_condition(user: User) -> object:
    """SQLAlchemy predicate selecting documents visible to ``user``.

    Used by document listing and by semantic retrieval so permission filtering
    happens in the database, never in application code. Matches ``_is_visible``.
    """
    owned = Document.uploaded_by == user.id
    return owned | _level_filter(user, Document.access_level)


def update_document(db: Session, document: Document, payload: dict) -> Document:
    """Apply a whitelisted subset of fields.

    Uses ``model_dump(exclude_unset=True)`` semantics: explicitly provided
    values are set (including ``None``, which clears a field); the immutable
    fields (id, uploaded_by, status, storage paths) are never touched.
    """
    for field, value in payload.items():
        if field not in _ALLOWED_UPDATE_FIELDS:
            continue
        if field == "title" and (value is None or not str(value).strip()):
            continue
        setattr(document, field, value)
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def count_chunks(db: Session, document_id: uuid.UUID) -> int:
    from sqlalchemy import func

    return (
        db.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        )
        or 0
    )


def delete_document(
    db: Session,
    document: Document,
    *,
    delete_file: bool = True,
    file_deleter=None,
) -> None:
    """Delete chunks and the document record; storage cleanup runs after commit.

    ``document.file_path`` is captured before the record is removed so the
    stored file can be deleted even if a later step fails.
    """
    stored_path = document.file_path
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    db.delete(document)
    db.commit()

    if delete_file:
        if file_deleter is None:
            from app.services import storage_service

            file_deleter = storage_service.delete_document_file
        try:
            file_deleter(stored_path)
        except Exception:
            # DB state is already consistent; storage cleanup is best-effort so
            # a leftover file never breaks the API. Logged by the caller.
            pass