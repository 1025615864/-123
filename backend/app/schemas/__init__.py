"""Pydantic模式"""
from app.schemas.ai import (
    ChatRequest, 
    ChatResponse, 
    ConsultationCreate,
    ConsultationResponse,
    MessageResponse
)

__all__ = [
    "ChatRequest", 
    "ChatResponse", 
    "ConsultationCreate",
    "ConsultationResponse",
    "MessageResponse"
]
