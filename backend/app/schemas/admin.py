"""Pydantic schemas for admin-only endpoints.

Admin responses are deliberately minimal and never include password hashes,
tokens, secrets or internal filesystem paths.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import AccessLevel, DocumentStatus, Role


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Role
    created_at: datetime


class AdminRoleUpdate(BaseModel):
    role: Role


class AdminDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    owner_name: str | None = None
    access_level: AccessLevel
    status: DocumentStatus
    version: str
    current_version_id: uuid.UUID | None
    page_count: int | None
    chunk_count: int | None = None
    created_at: datetime
    updated_at: datetime


class AdminStatsResponse(BaseModel):
    users: int
    documents: int
    active_documents: int
    failed_documents: int
    conversations: int
    feedback_entries: int