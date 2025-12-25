from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..database import Base

if TYPE_CHECKING:
    from .news import News


class NewsAIAnnotation(Base):
    __tablename__: str = "news_ai_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(Integer, ForeignKey("news.id"), nullable=False)

    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown")
    sensitive_words: Mapped[str | None] = mapped_column(Text, nullable=True)

    highlights: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    duplicate_of_news_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("news.id"), nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    news: Mapped[News] = relationship("News", foreign_keys=[news_id], lazy="joined")

    __table_args__: tuple[object, ...] = (
        UniqueConstraint("news_id", name="uq_news_ai_annotations_news"),
        Index("ix_news_ai_annotations_processed_at", "processed_at"),
        Index("ix_news_ai_annotations_risk_level", "risk_level"),
    )
