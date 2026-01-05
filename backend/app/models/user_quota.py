from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..database import Base
from .user import User


class UserQuotaDaily(Base):
    __tablename__: str = "user_quota_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_user_quota_daily_user_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    ai_chat_count: Mapped[int] = mapped_column(Integer, default=0)
    document_generate_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])


class UserQuotaPackBalance(Base):
    __tablename__: str = "user_quota_pack_balances"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_quota_pack_balances_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    ai_chat_credits: Mapped[int] = mapped_column(Integer, default=0)
    document_generate_credits: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
