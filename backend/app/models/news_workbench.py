from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..database import Base

if TYPE_CHECKING:
    from .news import News
    from .user import User


class NewsVersion(Base):
    __tablename__: str = "news_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(Integer, ForeignKey("news.id"), nullable=False, index=True)

    action: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    news: Mapped[News] = relationship("News", lazy="joined")
    creator: Mapped[User] = relationship("User", lazy="joined")

    __table_args__: tuple[object, ...] = (
        Index("ix_news_versions_news_created", "news_id", "created_at"),
    )


class NewsAIGeneration(Base):
    __tablename__: str = "news_ai_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    news_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("news.id"), nullable=True, index=True)

    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success")

    input_json: Mapped[str] = mapped_column(Text, nullable=False)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user: Mapped[User] = relationship("User", lazy="joined")
    news: Mapped[News | None] = relationship("News", foreign_keys=[news_id], lazy="joined")

    __table_args__: tuple[object, ...] = (
        Index("ix_news_ai_generations_user_created", "user_id", "created_at"),
        Index("ix_news_ai_generations_news_created", "news_id", "created_at"),
    )


class NewsLinkCheck(Base):
    __tablename__: str = "news_link_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    news_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("news.id"), nullable=True, index=True)

    url: Mapped[str] = mapped_column(String(800), nullable=False)
    final_url: Mapped[str | None] = mapped_column(String(800), nullable=True)

    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user: Mapped[User] = relationship("User", lazy="joined")
    news: Mapped[News | None] = relationship("News", foreign_keys=[news_id], lazy="joined")

    __table_args__: tuple[object, ...] = (
        Index("ix_news_link_checks_run_url", "run_id", "url"),
        Index("ix_news_link_checks_news_checked", "news_id", "checked_at"),
    )
