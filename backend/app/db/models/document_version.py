"""Document version entity: historical snapshots of a logical document.

A ``Document`` is the logical identity (title, access rules, current file);
each ``DocumentVersion`` captures one uploaded file for that document
(version_number, storage path, processing status). The current version is the
one the RAG pipeline ingests and answers from; older versions are preserved
for authorized users and are never silently mixed into retrieval.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DocumentStatus
from app.db.database import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.types import enum_type


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        enum_type(DocumentStatus, "document_status"),
        nullable=False,
        default=DocumentStatus.UPLOADED,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_error: Mapped[str | None] = mapped_column(Text)

    document: Mapped[Document] = relationship(
        back_populates="versions",
        primaryjoin="Document.id == DocumentVersion.document_id",
        foreign_keys="[DocumentVersion.document_id]",
    )
