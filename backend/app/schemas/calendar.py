from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class CalendarReminderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=8000)
    due_at: datetime
    remind_at: datetime | None = None


class CalendarReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=8000)
    due_at: datetime | None = None
    remind_at: datetime | None = None
    is_done: bool | None = None


class CalendarReminderResponse(BaseModel):
    id: int
    user_id: int
    title: str
    note: str | None = None
    due_at: datetime
    remind_at: datetime | None = None
    is_done: bool
    done_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class CalendarReminderListResponse(BaseModel):
    items: list[CalendarReminderResponse]
    total: int
