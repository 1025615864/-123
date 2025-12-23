"""新闻模型"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from ..database import Base


class News(Base):
    """新闻表"""
    __tablename__: str = "news"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 摘要
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cover_image: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 封面图
    category: Mapped[str] = mapped_column(String(50), default="general")  # 分类：general/policy/case/interpret
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 来源
    author: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 作者
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    is_top: Mapped[bool] = mapped_column(Boolean, default=False)  # 置顶
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否发布
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # 发布时间
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NewsFavorite(Base):
    """新闻收藏表"""

    __tablename__: str = "news_favorites"
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("news_id", "user_id", name="uq_news_favorite_news_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(Integer, ForeignKey("news.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    news: Mapped[News] = relationship("News")


class NewsViewHistory(Base):
    __tablename__: str = "news_view_history"
    __table_args__: tuple[object, ...] = (
        UniqueConstraint("news_id", "user_id", name="uq_news_view_history_news_user"),
        Index("ix_news_view_history_user_viewed_at", "user_id", "viewed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(Integer, ForeignKey("news.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    news: Mapped[News] = relationship("News")


class NewsSubscription(Base):
    __tablename__: str = "news_subscriptions"
    __table_args__: tuple[object, ...] = (
        UniqueConstraint("user_id", "sub_type", "value", name="uq_news_subscriptions_user_type_value"),
        Index("ix_news_subscriptions_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    sub_type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
