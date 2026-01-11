"""知识库模型 - 法律条文和案例"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Integer, String, DateTime, Text, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..database import Base


class KnowledgeType(str, Enum):
    """知识类型"""
    LAW = "law"           # 法律条文
    CASE = "case"         # 案例
    REGULATION = "regulation"  # 法规/规章
    INTERPRETATION = "interpretation"  # 司法解释


class LegalKnowledge(Base):
    """法律知识库表 - 存储法条和案例"""
    __tablename__: str = "legal_knowledge"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 知识类型
    knowledge_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    # 法律/案例名称
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    
    # 条款编号（如：第一百二十条）或案例编号
    article_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # 内容
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 摘要/要点
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 分类标签（如：民法、刑法、劳动法）
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # 关键词（逗号分隔）
    keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # 来源/出处
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)

    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    source_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    ingest_batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    
    # 生效日期
    effective_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # 是否已同步到向量库
    is_vectorized: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 向量库中的文档ID
    vector_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 是否启用
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 排序权重（权重越高越优先）
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KnowledgeCategory(Base):
    """知识库分类表"""
    __tablename__: str = "knowledge_categories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 支持二级分类
    icon: Mapped[str] = mapped_column(String(50), default="Folder")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsultationTemplate(Base):
    """咨询模板表 - 预设常见问题模板"""
    __tablename__: str = "consultation_templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 模板名称
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # 模板描述
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # 分类（如：劳动纠纷、婚姻家庭、合同纠纷）
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # 图标名称（Lucide图标）
    icon: Mapped[str] = mapped_column(String(50), default="MessageSquare")
    
    # 预设问题列表（JSON格式）
    questions: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 排序顺序
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # 是否启用
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
