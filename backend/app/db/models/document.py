"""Document entity."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String, Text, Uuid, text
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
        default=DocumentStatus.PROCESSING,
        server_default=text("'PROCESSING'"),
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
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    processing_error: Mapped[str | None] = mapped_column(Text)

    uploader: Mapped[User | None] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
