from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..database import Base


class DocumentTemplate(Base):
    __tablename__: str = "document_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DocumentTemplateVersion(Base):
    __tablename__: str = "document_template_versions"
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("template_id", "version", name="uq_document_template_versions_template_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("document_templates.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
