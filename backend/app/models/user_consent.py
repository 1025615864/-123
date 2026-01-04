from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import enum

from sqlalchemy import Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..database import Base

if TYPE_CHECKING:
    from .user import User


class ConsentDocType(str, enum.Enum):
    TERMS = "terms"
    PRIVACY = "privacy"
    AI_DISCLAIMER = "ai_disclaimer"


class UserConsent(Base):
    __tablename__: str = "user_consents"
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("user_id", "doc_type", "doc_version", name="uq_user_consents_user_doc_ver"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_version: Mapped[str] = mapped_column(String(50), nullable=False)

    agreed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped[User] = relationship("User", backref="consents")
