"""法律咨询所模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, DynamicMapped
from sqlalchemy.sql import func
from ..database import Base

if TYPE_CHECKING:
    from .user import User


class LawFirm(Base):
    """律师事务所表"""
    __tablename__: str = "law_firms"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(50), nullable=True)
    province: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    license_no: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 执业许可证号
    specialties: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 专业领域，逗号分隔
    rating: Mapped[float] = mapped_column(Float, default=0.0)  # 评分
    review_count: Mapped[int] = mapped_column(Integer, default=0)  # 评价数
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否认证
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    lawyers: DynamicMapped[Lawyer] = relationship("Lawyer", back_populates="firm", lazy="dynamic")


class Lawyer(Base):
    """律师表"""
    __tablename__: str = "lawyers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)  # 关联用户
    firm_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("law_firms.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 职称：律师/合伙人/主任
    license_no: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 执业证号
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)  # 个人简介
    specialties: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 擅长领域
    experience_years: Mapped[int] = mapped_column(Integer, default=0)  # 从业年限
    case_count: Mapped[int] = mapped_column(Integer, default=0)  # 案件数
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    consultation_fee: Mapped[float] = mapped_column(Float, default=0.0)  # 咨询费用
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    firm: Mapped[LawFirm | None] = relationship("LawFirm", back_populates="lawyers")
    user: Mapped[User | None] = relationship("User", backref="lawyer_profile")


class LawyerVerification(Base):
    """律师认证申请表"""
    __tablename__: str = "lawyer_verifications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    real_name: Mapped[str] = mapped_column(String(50), nullable=False)  # 真实姓名
    id_card_no: Mapped[str] = mapped_column(String(20), nullable=False)  # 身份证号
    license_no: Mapped[str] = mapped_column(String(100), nullable=False)  # 律师执业证号
    firm_name: Mapped[str] = mapped_column(String(200), nullable=False)  # 执业律所名称
    id_card_front: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 身份证正面照
    id_card_back: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 身份证背面照
    license_photo: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 执业证照片
    specialties: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 擅长领域
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)  # 个人简介
    experience_years: Mapped[int] = mapped_column(Integer, default=0)  # 从业年限
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/approved/rejected
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # 驳回原因
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    user: Mapped[User] = relationship("User", foreign_keys=[user_id], backref="lawyer_verifications")
    reviewer: Mapped[User | None] = relationship("User", foreign_keys=[reviewed_by])


class LawyerConsultation(Base):
    """律师咨询预约表"""
    __tablename__: str = "lawyer_consultations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    lawyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lawyers.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)  # 咨询主题
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # 问题描述
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 案件类型
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # 期望时间
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/confirmed/completed/cancelled
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # 管理备注
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    user: Mapped[User] = relationship("User", backref="consultations")
    lawyer: Mapped[Lawyer] = relationship("Lawyer", backref="consultations")


class LawyerReview(Base):
    """律师评价表"""
    __tablename__: str = "lawyer_reviews"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lawyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lawyers.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    consultation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("lawyer_consultations.id"), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5星
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    lawyer: Mapped[Lawyer] = relationship("Lawyer", backref="reviews")
    user: Mapped[User] = relationship("User", backref="lawyer_reviews")
