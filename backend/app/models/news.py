"""新闻模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, Index, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from ..database import Base

if TYPE_CHECKING:
    from .user import User


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
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 来源链接
    dedupe_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_site: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 来源站点
    author: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 作者
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    is_top: Mapped[bool] = mapped_column(Boolean, default=False)  # 置顶
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否发布
    review_status: Mapped[str] = mapped_column(String(20), default="approved")
    review_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # 发布时间
    scheduled_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_unpublish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__: tuple[object, ...] = (
        Index("ix_news_published_review", "is_published", "review_status"),
        Index("ix_news_review_status", "review_status"),
        Index("ix_news_dedupe_hash", "dedupe_hash"),
    )


class NewsComment(Base):
    """新闻评论表"""

    __tablename__: str = "news_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(Integer, ForeignKey("news.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(20), default="approved")
    review_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    news: Mapped[News] = relationship("News")
    author: Mapped[User] = relationship("User", backref="news_comments")


class NewsTopic(Base):
    """新闻专题/合集"""

    __tablename__: str = "news_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    auto_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    auto_keyword: Mapped[str | None] = mapped_column(String(100), nullable=True)
    auto_limit: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items: Mapped[list["NewsTopicItem"]] = relationship(
        "NewsTopicItem",
        back_populates="topic",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class NewsTopicItem(Base):
    """专题-新闻关联"""

    __tablename__: str = "news_topic_items"
    __table_args__: tuple[object, ...] = (
        UniqueConstraint("topic_id", "news_id", name="uq_news_topic_items_topic_news"),
        Index("ix_news_topic_items_topic", "topic_id"),
        Index("ix_news_topic_items_news", "news_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(Integer, ForeignKey("news_topics.id"), nullable=False)
    news_id: Mapped[int] = mapped_column(Integer, ForeignKey("news.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    topic: Mapped[NewsTopic] = relationship("NewsTopic", back_populates="items")
    news: Mapped[News] = relationship("News")


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


class NewsSource(Base):
    __tablename__: str = "news_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), default="rss")

    feed_url: Mapped[str] = mapped_column(String(500), nullable=False)
    site: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    fetch_timeout_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_items_per_feed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__: tuple[object, ...] = (
        UniqueConstraint("feed_url", name="uq_news_sources_feed_url"),
        Index("ix_news_sources_enabled", "is_enabled"),
        Index("ix_news_sources_type", "source_type"),
    )


class NewsIngestRun(Base):
    __tablename__: str = "news_ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("news_sources.id"), nullable=True, index=True)
    source_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    feed_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="running")
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    source: Mapped[NewsSource | None] = relationship("NewsSource", lazy="joined")

    __table_args__: tuple[object, ...] = (
        Index("ix_news_ingest_runs_source_created", "source_id", "created_at"),
        Index("ix_news_ingest_runs_status_created", "status", "created_at"),
    )
