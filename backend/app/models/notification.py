"""通知消息模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from ..database import Base

if TYPE_CHECKING:
    from .user import User


class Notification(Base):
    """用户通知表"""
    __tablename__: str = "notifications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # comment_reply, post_like, system, etc.
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 跳转链接
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 关联信息
    related_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)  # 触发通知的用户
    related_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 关联帖子
    related_comment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 关联评论
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user: Mapped[User] = relationship("User", foreign_keys=[user_id], backref="notifications")
    related_user: Mapped[User | None] = relationship("User", foreign_keys=[related_user_id])


# 通知类型常量
class NotificationType:
    COMMENT_REPLY = "comment_reply"  # 评论回复
    POST_LIKE = "post_like"  # 帖子被点赞
    POST_FAVORITE = "post_favorite"  # 帖子被收藏
    POST_COMMENT = "post_comment"  # 帖子被评论
    SYSTEM = "system"  # 系统通知
    CONSULTATION = "consultation"  # 咨询相关
