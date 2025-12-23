"""论坛模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..database import Base

if TYPE_CHECKING:
    from .user import User


class Post(Base):
    """帖子表"""

    __tablename__: str = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general")  # 分类：general/labor/marriage/contract/other
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)  # 分享次数
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)  # 置顶
    is_hot: Mapped[bool] = mapped_column(Boolean, default=False)  # 热门标记
    is_essence: Mapped[bool] = mapped_column(Boolean, default=False)  # 精华帖
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str | None] = mapped_column(String(20), default="approved", nullable=True)  # pending/approved/rejected
    review_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heat_score: Mapped[float] = mapped_column(Float, default=0.0)  # 热度分数
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 封面图
    images: Mapped[str | None] = mapped_column(Text, nullable=True)  # 图片列表JSON
    attachments: Mapped[str | None] = mapped_column(Text, nullable=True)  # 附件列表JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    author: Mapped[User] = relationship("User", backref="posts")
    comments: Mapped[list[Comment]] = relationship("Comment", back_populates="post")
    likes: Mapped[list[PostLike]] = relationship("PostLike", back_populates="post")
    favorites: Mapped[list[PostFavorite]] = relationship("PostFavorite", back_populates="post")


class Comment(Base):
    """评论表"""

    __tablename__: str = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("comments.id"), nullable=True)  # 回复评论
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    images: Mapped[str | None] = mapped_column(Text, nullable=True)  # 评论图片JSON
    review_status: Mapped[str | None] = mapped_column(String(20), default="approved", nullable=True)  # pending/approved/rejected
    review_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    post: Mapped[Post] = relationship("Post", back_populates="comments")
    author: Mapped[User] = relationship("User", backref="comments")
    parent: Mapped[Comment | None] = relationship(
        "Comment",
        remote_side="Comment.id",
        foreign_keys="Comment.parent_id",
        back_populates="replies",
        lazy="joined",
    )
    replies: Mapped[list[Comment]] = relationship(
        "Comment",
        foreign_keys="Comment.parent_id",
        back_populates="parent",
        lazy="selectin",
    )


class PostLike(Base):
    """帖子点赞表"""

    __tablename__: str = "post_likes"
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("post_id", "user_id", name="uq_post_like_post_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    post: Mapped[Post] = relationship("Post", back_populates="likes")
    user: Mapped[User] = relationship("User", backref="post_likes")


class CommentLike(Base):
    """评论点赞表"""

    __tablename__: str = "comment_likes"
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_like_comment_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(Integer, ForeignKey("comments.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    comment: Mapped[Comment] = relationship("Comment", backref="likes")
    user: Mapped[User] = relationship("User", backref="comment_likes")


class PostFavorite(Base):
    """帖子收藏表"""

    __tablename__: str = "post_favorites"
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("post_id", "user_id", name="uq_post_favorite_post_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    post: Mapped[Post] = relationship("Post", back_populates="favorites")
    user: Mapped[User] = relationship("User", backref="post_favorites")


class PostReaction(Base):
    """帖子表情反应表"""

    __tablename__: str = "post_reactions"
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("post_id", "user_id", "emoji", name="uq_post_reaction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    emoji: Mapped[str] = mapped_column(String(20), nullable=False)  # 表情符号或代码
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    post: Mapped[Post] = relationship("Post", backref="reactions")
    user: Mapped[User] = relationship("User", backref="post_reactions")
