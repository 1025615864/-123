from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConsultationReviewVersionItem(BaseModel):
    id: int
    task_id: int
    editor_user_id: int
    editor_role: str
    content_markdown: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConsultationReviewTaskItem(BaseModel):
    id: int
    consultation_id: int
    user_id: int

    order_no: str
    status: str

    lawyer_id: int | None

    result_markdown: str | None

    claimed_at: datetime | None
    submitted_at: datetime | None

    created_at: datetime
    updated_at: datetime

    latest_version: ConsultationReviewVersionItem | None = None

    model_config = ConfigDict(from_attributes=True)


class ConsultationReviewTaskDetailResponse(BaseModel):
    task: ConsultationReviewTaskItem | None


class ConsultationReviewCreateOrderResponse(BaseModel):
    order_no: str
    amount: float
    expires_at: datetime | None


class LawyerReviewTaskListResponse(BaseModel):
    items: list[ConsultationReviewTaskItem]
    total: int
    page: int
    page_size: int


class LawyerReviewSubmitRequest(BaseModel):
    content_markdown: str = Field(..., min_length=1, max_length=20000)
