from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..database import Base


class ConsultationReviewTask(Base):
    __tablename__: str = "consultation_review_tasks"
    __table_args__ = (UniqueConstraint("order_id", name="uq_consultation_review_tasks_order_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    consultation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("consultations.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("payment_orders.id"),
        nullable=False,
        index=True,
    )
    order_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    lawyer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lawyers.id"),
        nullable=True,
        index=True,
    )

    result_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)

    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    consultation = relationship("Consultation", foreign_keys=[consultation_id])
    user = relationship("User", foreign_keys=[user_id])
    lawyer = relationship("Lawyer", foreign_keys=[lawyer_id])
    order = relationship("PaymentOrder", foreign_keys=[order_id])

    versions = relationship(
        "ConsultationReviewVersion",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class ConsultationReviewVersion(Base):
    __tablename__: str = "consultation_review_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("consultation_review_tasks.id"),
        nullable=False,
        index=True,
    )

    editor_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    editor_role: Mapped[str] = mapped_column(String(20), nullable=False)

    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task = relationship("ConsultationReviewTask", back_populates="versions", foreign_keys=[task_id])
    editor = relationship("User", foreign_keys=[editor_user_id])
