"""系统配置和日志模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from ..database import Base

if TYPE_CHECKING:
    from .user import User


class SystemConfig(Base):
    """系统配置表"""
    __tablename__: str = "system_configs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="general")  # general, ai, notification, security
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


class AdminLog(Base):
    """管理员操作日志表"""
    __tablename__: str = "admin_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create, update, delete, login, etc.
    module: Mapped[str] = mapped_column(String(50), nullable=False)  # user, post, news, lawfirm, system, etc.
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 操作对象ID
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 操作对象类型
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # 操作描述
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extra_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON格式额外数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # 关系
    user: Mapped[User] = relationship("User", backref="admin_logs")


# 日志动作类型
class LogAction:
    CREATE: str = "create"
    UPDATE: str = "update"
    DELETE: str = "delete"
    LOGIN: str = "login"
    LOGOUT: str = "logout"
    ENABLE: str = "enable"
    DISABLE: str = "disable"
    EXPORT: str = "export"
    IMPORT: str = "import"
    CONFIG: str = "config"


# 日志模块类型
class LogModule:
    USER: str = "user"
    POST: str = "post"
    COMMENT: str = "comment"
    NEWS: str = "news"
    LAWFIRM: str = "lawfirm"
    LAWYER: str = "lawyer"
    KNOWLEDGE: str = "knowledge"
    TEMPLATE: str = "template"
    SYSTEM: str = "system"
    AUTH: str = "auth"


class SearchHistory(Base):
    """搜索历史表"""
    __tablename__: str = "search_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # 关系
    user: Mapped[User | None] = relationship("User", backref="search_history")


class UserActivity(Base):
    """用户行为追踪表"""
    __tablename__: str = "user_activities"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # page_view, click, search, etc.
    page: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 页面路径
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 操作目标
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 目标ID
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 来源页面
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # desktop/mobile/tablet
    extra_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON格式额外数据
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 停留时长(秒)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # 关系
    user: Mapped[User | None] = relationship("User", backref="activities")


class PageView(Base):
    """页面访问统计表(聚合)"""
    __tablename__: str = "page_views"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    page: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_visitors: Mapped[int] = mapped_column(Integer, default=0)
    avg_duration: Mapped[int] = mapped_column(Integer, default=0)  # 平均停留时长(秒)
