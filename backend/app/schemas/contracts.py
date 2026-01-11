from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ContractReviewResponse(BaseModel):
    filename: str = Field(..., description="文件名")
    content_type: str | None = Field(None, description="文件类型")
    text_chars: int = Field(..., description="提取文本长度")
    text_preview: str = Field(..., description="提取文本预览")
    report_json: dict[str, Any] = Field(default_factory=dict, description="结构化风险体检报告")
    report_markdown: str = Field("", description="可渲染的 Markdown 报告")
    request_id: str = Field("", description="请求ID")


class ContractReviewErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str
