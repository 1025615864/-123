from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..database import Base
from .lawfirm import Lawyer
from .user import User


class LawyerWallet(Base):
    __tablename__: str = "lawyer_wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lawyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lawyers.id"), unique=True, nullable=False, index=True)

    total_income: Mapped[float] = mapped_column(Float, default=0.0)
    withdrawn_amount: Mapped[float] = mapped_column(Float, default=0.0)
    pending_amount: Mapped[float] = mapped_column(Float, default=0.0)
    frozen_amount: Mapped[float] = mapped_column(Float, default=0.0)
    available_amount: Mapped[float] = mapped_column(Float, default=0.0)

    total_income_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    withdrawn_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pending_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frozen_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lawyer: Mapped[Lawyer] = relationship("Lawyer", foreign_keys=[lawyer_id])


class LawyerIncomeRecord(Base):
    __tablename__: str = "lawyer_income_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lawyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lawyers.id"), nullable=False, index=True)

    consultation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("lawyer_consultations.id"), nullable=True, index=True)
    order_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    user_paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    platform_fee: Mapped[float] = mapped_column(Float, default=0.0)
    lawyer_income: Mapped[float] = mapped_column(Float, default=0.0)

    user_paid_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    platform_fee_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lawyer_income_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    withdrawn_amount: Mapped[float] = mapped_column(Float, default=0.0)
    withdrawn_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending/settled/withdrawn
    settle_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lawyer: Mapped[Lawyer] = relationship("Lawyer", foreign_keys=[lawyer_id])


class LawyerBankAccount(Base):
    __tablename__: str = "lawyer_bank_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lawyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lawyers.id"), nullable=False, index=True)

    account_type: Mapped[str] = mapped_column(String(20), default="bank_card")  # bank_card/alipay
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    account_no: Mapped[str] = mapped_column(String(100), nullable=False)
    account_holder: Mapped[str] = mapped_column(String(50), nullable=False)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lawyer: Mapped[Lawyer] = relationship("Lawyer", foreign_keys=[lawyer_id])


class WithdrawalRequest(Base):
    __tablename__: str = "withdrawal_requests"
    __table_args__ = (UniqueConstraint("request_no", name="uq_withdraw_request_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    lawyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lawyers.id"), nullable=False, index=True)

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    actual_amount: Mapped[float] = mapped_column(Float, nullable=False)

    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fee_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    withdraw_method: Mapped[str] = mapped_column(String(20), default="bank_card")
    account_info: Mapped[str] = mapped_column(Text, nullable=False)  # JSON

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending/approved/rejected/completed/failed
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    admin_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lawyer: Mapped[Lawyer] = relationship("Lawyer", foreign_keys=[lawyer_id])
    admin: Mapped[User | None] = relationship("User", foreign_keys=[admin_id])
