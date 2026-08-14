"""Document entity."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AccessLevel, DocumentStatus
from app.db.database import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.types import enum_type


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(String(255), index=True)
    category: Mapped[str | None] = mapped_column(String(255), index=True)
    version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="1", server_default=text("'1'")
    )
    effective_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[DocumentStatus] = mapped_column(
        enum_type(DocumentStatus, "document_status"),
        nullable=False,
        default=DocumentStatus.UPLOADED,
        server_default=text("'UPLOADED'"),
        index=True,
    )
    access_level: Mapped[AccessLevel] = mapped_column(
        enum_type(AccessLevel, "access_level"),
        nullable=False,
        default=AccessLevel.PUBLIC,
        server_default=text("'PUBLIC'"),
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    # The version currently used by retrieval; historical versions remain on
    # ``versions`` and are never deleted automatically. ``use_alter`` breaks
    # the documents <-> document_versions FK cycle for create/drop_all.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "document_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_documents_current_version_id_document_versions",
        ),
        nullable=True,
        index=True,
    )

    uploader: Mapped[User | None] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        primaryjoin="Document.id == DocumentVersion.document_id",
        foreign_keys="[DocumentVersion.document_id]",
    )
