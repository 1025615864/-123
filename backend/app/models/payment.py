"""支付订单模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, Text, DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from ..database import Base
import enum

if TYPE_CHECKING:
    from .user import User


class PaymentStatus(str, enum.Enum):
    """支付状态"""
    PENDING = "pending"  # 待支付
    PAID = "paid"  # 已支付
    CANCELLED = "cancelled"  # 已取消
    REFUNDED = "refunded"  # 已退款
    FAILED = "failed"  # 支付失败


class PaymentMethod(str, enum.Enum):
    """支付方式"""
    ALIPAY = "alipay"  # 支付宝
    WECHAT = "wechat"  # 微信支付
    BALANCE = "balance"  # 余额支付


class OrderType(str, enum.Enum):
    """订单类型"""
    CONSULTATION = "consultation"  # 律师咨询
    SERVICE = "service"  # 法律服务
    VIP = "vip"  # VIP会员
    RECHARGE = "recharge"  # 余额充值


class PaymentOrder(Base):
    """支付订单表"""
    __tablename__: str = "payment_orders"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)  # 订单号
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 订单类型
    amount: Mapped[float] = mapped_column(Float, nullable=False)  # 订单金额
    actual_amount: Mapped[float] = mapped_column(Float, nullable=False)  # 实付金额
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # 关联信息
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 关联ID（如咨询ID）
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 关联类型
    
    # 支付信息
    trade_no: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 第三方交易号
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # 订单描述
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # 过期时间
    
    # 关系
    user: Mapped[User] = relationship("User", backref="orders")


class UserBalance(Base):
    """用户余额表"""
    __tablename__: str = "user_balances"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0)  # 可用余额
    frozen: Mapped[float] = mapped_column(Float, default=0.0)  # 冻结金额
    total_recharged: Mapped[float] = mapped_column(Float, default=0.0)  # 累计充值
    total_consumed: Mapped[float] = mapped_column(Float, default=0.0)  # 累计消费
    balance_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frozen_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_recharged_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_consumed_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    user: Mapped[User] = relationship("User", backref="balance_account")


class BalanceTransaction(Base):
    """余额交易记录表"""
    __tablename__: str = "balance_transactions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("payment_orders.id"), nullable=True)
    
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # recharge/consume/refund
    amount: Mapped[float] = mapped_column(Float, nullable=False)  # 正数为收入，负数为支出
    balance_before: Mapped[float] = mapped_column(Float, nullable=False)  # 交易前余额
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)  # 交易后余额
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    balance_before_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    balance_after_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user: Mapped[User] = relationship("User", backref="balance_transactions")
    order: Mapped[PaymentOrder | None] = relationship("PaymentOrder", backref="transactions")


class PaymentCallbackEvent(Base):
    __tablename__: str = "payment_callback_events"
    __table_args__: tuple[UniqueConstraint] = (
        UniqueConstraint("provider", "trade_no", name="uq_payment_cb_provider_trade_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    provider: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    order_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    trade_no: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(String(200), nullable=True)

    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
