"""Document CRUD, visibility and authorization logic.

Authorization is enforced here (server-side) — never by the frontend. A
document is **visible** to a user when they uploaded it or the document's
access level matches their role. Only the uploader or an ADMIN may **manage**
(edit / process / delete) a document.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.enums import AccessLevel, DocumentStatus, Role
from app.core.errors import ApiError
from app.db.models import Document, DocumentChunk, DocumentVersion, User

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
    db.flush()

    # The first upload is version 1 of the document.
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        status=DocumentStatus.UPLOADED,
        filename=original_filename,
        storage_path=file_path,
        file_size=file_size,
    )
    db.add(version)
    db.flush()
    document.current_version_id = version.id

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
    return (
        db.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        )
        or 0
    )


def next_version_number(db: Session, document_id: uuid.UUID) -> int:
    """Return ``max(version_number) + 1`` for a document (1 when none exist)."""
    current = db.scalar(
        select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
    )
    return (current or 0) + 1


def list_versions(db: Session, document: Document) -> list[DocumentVersion]:
    """Return a document's versions, newest first."""
    return list(
        db.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
        ).all()
    )


def get_version(
    db: Session, document: Document, version_id: uuid.UUID
) -> DocumentVersion:
    """Fetch a version belonging to ``document`` (404 otherwise)."""
    version = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document.id,
        )
    )
    if version is None:
        raise ApiError("VERSION_NOT_FOUND", "The version could not be found.", status_code=404)
    return version


def _snapshot_current_as_version(db: Session, document: Document) -> None:
    """Legacy documents (no version rows) get their current file snapshotted.

    Used so uploading a new version to a pre-Phase-6 document preserves the
    previous file instead of silently replacing it.
    """
    if document.current_version_id is not None:
        return
    db.add(
        DocumentVersion(
            document_id=document.id,
            version_number=1,
            status=DocumentStatus.ARCHIVED,
            filename=document.original_filename,
            storage_path=document.file_path,
            file_size=document.file_size,
            page_count=document.page_count,
            processed_at=document.processed_at,
        )
    )


def create_version(
    db: Session,
    document: Document,
    *,
    version_number: int,
    filename: str,
    storage_path: str,
    file_size: int,
    mime_type: str,
) -> DocumentVersion:
    """Register a new version and switch the document to it.

    The previous current version is archived (never deleted). The document's
    file pointers move to the new file and its status resets to UPLOADED so the
    new version must be processed before it is used by retrieval.
    """
    _snapshot_current_as_version(db, document)

    if document.current_version_id is not None:
        previous = db.get(DocumentVersion, document.current_version_id)
        if previous is not None and previous.status == DocumentStatus.ACTIVE:
            previous.status = DocumentStatus.ARCHIVED
            db.add(previous)

    version = DocumentVersion(
        document_id=document.id,
        version_number=version_number,
        status=DocumentStatus.UPLOADED,
        filename=filename,
        storage_path=storage_path,
        file_size=file_size,
    )
    db.add(version)
    db.flush()

    document.current_version_id = version.id
    document.file_path = storage_path
    document.original_filename = filename
    document.mime_type = mime_type
    document.file_size = file_size
    document.version = str(version_number)
    document.status = DocumentStatus.UPLOADED
    document.processing_error = None
    document.page_count = None
    document.processed_at = None

    db.add(document)
    db.commit()
    db.refresh(version)
    return version


def delete_document(
    db: Session,
    document: Document,
    *,
    delete_file: bool = True,
    file_deleter=None,
) -> None:
    """Delete chunks, versions and the document record; storage cleanup runs after commit.

    ``document.file_path`` and every version's storage path are captured before
    the record is removed so all stored files can be deleted even if a later
    step fails.
    """
    stored_paths = [document.file_path] + [
        version.storage_path for version in document.versions
    ]
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    db.delete(document)
    db.commit()

    if delete_file:
        if file_deleter is None:
            from app.services import storage_service

            file_deleter = storage_service.delete_document_files
        try:
            file_deleter(stored_paths)
        except Exception:
            # DB state is already consistent; storage cleanup is best-effort so
            # a leftover file never breaks the API. Logged by the caller.
            pass