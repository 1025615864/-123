"""Pydantic模式"""
from .ai import (
    ChatRequest, 
    ChatResponse, 
    ConsultationCreate,
    ConsultationResponse,
    MessageResponse
)
from .calendar import (
    CalendarReminderCreate,
    CalendarReminderUpdate,
    CalendarReminderResponse,
    CalendarReminderListResponse,
)

__all__ = [
    "ChatRequest", 
    "ChatResponse", 
    "ConsultationCreate",
    "ConsultationResponse",
    "MessageResponse",
    "CalendarReminderCreate",
    "CalendarReminderUpdate",
    "CalendarReminderResponse",
    "CalendarReminderListResponse",
]
