from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class DocumentGenerateRequest(BaseModel):
    document_type: str = Field(..., min_length=1, max_length=50)
    case_type: str = Field(..., min_length=1, max_length=50)
    plaintiff_name: str = Field(..., min_length=1, max_length=100)
    defendant_name: str = Field(..., min_length=1, max_length=100)
    facts: str = Field(..., min_length=1, max_length=8000)
    claims: str = Field(..., min_length=1, max_length=4000)
    evidence: str | None = Field(default=None, max_length=4000)


class DocumentResponse(BaseModel):
    document_type: str
    title: str
    content: str
    created_at: datetime


class DocumentSaveRequest(BaseModel):
    document_type: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    payload: dict[str, object] | None = None


class DocumentItem(BaseModel):
    id: int
    document_type: str
    title: str
    created_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class DocumentDetail(BaseModel):
    id: int
    user_id: int
    document_type: str
    title: str
    content: str
    payload_json: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentItem]
    total: int
