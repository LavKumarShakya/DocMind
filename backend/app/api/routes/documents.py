"""Document endpoints: upload, list, detail, edit, process, delete, versions."""

from __future__ import annotations

import logging
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import Document, DocumentVersion, User
from app.schemas.document import (
    DocumentResponse,
    DocumentUpdate,
    DocumentVersionResponse,
)
from app.services import document_service, ingestion_service, pdf_service, storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_response(db: Session, document: Document, with_chunk_count: bool = False) -> DocumentResponse:
    response = DocumentResponse.model_validate(document)
    response.uploader_name = document.uploader.name if document.uploader else None
    if with_chunk_count:
        response.chunk_count = document_service.count_chunks(db, document.id)
    return response


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=201,
    summary="Upload a PDF document",
)
def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    department: str | None = Form(default=None),
    category: str | None = Form(default=None),
    effective_date: date | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Validate and store an uploaded PDF, creating an UPLOADED record."""
    content = file.file.read()
    pdf_service.check_mime_type(file.content_type)
    safe_name = pdf_service.validate_upload(filename=file.filename, content=content)

    document_id = uuid.uuid4()
    stored_path = storage_service.save_document_file(document_id, content)

    try:
        document = document_service.create_document(
            db,
            document_id=document_id,
            uploader=current_user,
            original_filename=safe_name,
            mime_type=file.content_type or "application/pdf",
            file_size=len(content),
            file_path=stored_path,
            title=title,
            description=description,
            department=department,
            category=category,
            effective_date=effective_date,
        )
    except Exception:
        logger.exception("Creating document record failed; removing stored file")
        storage_service.delete_document_file(stored_path)
        raise

    return _to_response(db, document)


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="List documents visible to the current user",
)
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    return [_to_response(db, doc) for doc in document_service.list_documents(db, current_user)]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Document detail",
)
def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    document = document_service.get_visible_document(db, document_id, current_user)
    return _to_response(db, document, with_chunk_count=True)


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Edit document metadata",
)
def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    document = document_service.get_manageable_document(db, document_id, current_user)
    updated = document_service.update_document(
        db, document, payload.model_dump(exclude_unset=True)
    )
    return _to_response(db, updated, with_chunk_count=True)


@router.post(
    "/{document_id}/process",
    response_model=DocumentResponse,
    summary="Run PDF ingestion for a document",
)
def process_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    processed = ingestion_service.process_document(db, document_id, current_user)
    return _to_response(db, processed, with_chunk_count=True)


@router.delete(
    "/{document_id}",
    summary="Delete a document and its stored file",
)
def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = document_service.get_manageable_document(db, document_id, current_user)
    document_service.delete_document(db, document)
    return {"status": "deleted"}


def _version_response(version: DocumentVersion) -> DocumentVersionResponse:
    return DocumentVersionResponse.model_validate(version)


@router.get(
    "/{document_id}/versions",
    response_model=list[DocumentVersionResponse],
    summary="List a document's versions (newest first)",
)
def list_versions(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentVersionResponse]:
    document = document_service.get_visible_document(db, document_id, current_user)
    return [
        _version_response(v)
        for v in document_service.list_versions(db, document)
    ]


@router.post(
    "/{document_id}/versions",
    response_model=DocumentVersionResponse,
    status_code=201,
    summary="Upload a new version of a document",
)
def upload_version(
    document_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentVersionResponse:
    """Upload a replacement PDF as a new version.

    The previous current version is archived (never deleted) and the document
    switches to the new file; the new version must be processed via
    ``POST /api/documents/{id}/process`` before retrieval uses it.
    """
    content = file.file.read()
    pdf_service.check_mime_type(file.content_type)
    safe_name = pdf_service.validate_upload(filename=file.filename, content=content)

    document = document_service.get_manageable_document(db, document_id, current_user)
    version_number = document_service.next_version_number(db, document.id)
    stored_path = storage_service.save_document_version_file(
        document.id, version_number, content
    )

    try:
        version = document_service.create_version(
            db,
            document,
            version_number=version_number,
            filename=safe_name,
            storage_path=stored_path,
            file_size=len(content),
            mime_type=file.content_type or "application/pdf",
        )
    except Exception:
        logger.exception("Creating document version failed; removing stored file")
        storage_service.delete_document_file(stored_path)
        raise

    return _version_response(version)


@router.get(
    "/{document_id}/versions/{version_id}",
    response_model=DocumentVersionResponse,
    summary="Get a document version",
)
def get_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentVersionResponse:
    document = document_service.get_visible_document(db, document_id, current_user)
    version = document_service.get_version(db, document, version_id)
    return _version_response(version)