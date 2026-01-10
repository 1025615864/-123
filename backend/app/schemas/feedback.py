from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class FeedbackTicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=20000)


class FeedbackTicketItem(BaseModel):
    id: int
    user_id: int
    subject: str
    content: str
    status: str
    admin_reply: str | None
    admin_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackTicketListResponse(BaseModel):
    items: list[FeedbackTicketItem]
    total: int
    page: int
    page_size: int


class AdminFeedbackTicketUpdate(BaseModel):
    status: str | None = None
    admin_reply: str | None = Field(default=None, max_length=20000)
    admin_id: int | None = None


class AdminFeedbackTicketStatsResponse(BaseModel):
    total: int
    open: int
    processing: int
    closed: int
    unassigned: int
