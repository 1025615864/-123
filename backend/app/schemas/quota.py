from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class UserQuotaDailyResponse(BaseModel):
    day: date

    ai_chat_limit: int = Field(..., ge=0)
    ai_chat_used: int = Field(..., ge=0)
    ai_chat_remaining: int = Field(..., ge=0)

    document_generate_limit: int = Field(..., ge=0)
    document_generate_used: int = Field(..., ge=0)
    document_generate_remaining: int = Field(..., ge=0)

    ai_chat_pack_remaining: int = Field(0, ge=0)
    document_generate_pack_remaining: int = Field(0, ge=0)

    is_vip_active: bool
