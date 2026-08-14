"""Pydantic schemas for document endpoints.

``file_path`` and ``processing_error`` are intentionally absent: internal
storage paths and diagnostics are never exposed to clients.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import AccessLevel, DocumentStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    department: str | None
    category: str | None
    version: str
    effective_date: date | None
    status: DocumentStatus
    access_level: AccessLevel
    original_filename: str
    mime_type: str
    file_size: int
    page_count: int | None
    uploader_name: str | None = None
    chunk_count: int | None = None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    department: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=255)
    version: str | None = Field(default=None, max_length=50)
    effective_date: date | None = None
    access_level: AccessLevel | None = None


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    status: DocumentStatus
    filename: str
    file_size: int
    page_count: int | None
    created_at: datetime
    processed_at: datetime | None