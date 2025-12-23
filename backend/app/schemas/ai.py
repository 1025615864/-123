"""AI助手相关的Pydantic模式"""
from typing import Annotated, ClassVar
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: str | None = Field(None, description="会话ID，为空则创建新会话")


class LawReference(BaseModel):
    """法律引用"""
    law_name: str = Field(..., description="法律名称")
    article: str = Field(..., description="条款编号")
    content: str = Field(..., description="条款内容")
    relevance: float = Field(..., description="相关度分数")


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str = Field(..., description="会话ID")
    answer: str = Field(..., description="AI回复内容")
    references: Annotated[list[LawReference], Field(default_factory=list, description="引用的法律条文")]
    assistant_message_id: int | None = Field(None, description="本次AI回复对应的消息ID（用于评价）")
    created_at: datetime = Field(default_factory=datetime.now)


class ConsultationCreate(BaseModel):
    """创建咨询会话"""
    title: str | None = Field(None, max_length=200, description="会话标题")


class MessageResponse(BaseModel):
    """消息响应"""
    id: int
    role: str
    content: str
    references: str | None = None
    created_at: datetime
    
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class ConsultationResponse(BaseModel):
    """咨询会话响应"""
    id: int
    session_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = []
    
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class ConsultationListItem(BaseModel):
    """咨询列表项"""
    id: int
    session_id: str
    title: str | None
    created_at: datetime
    message_count: int = 0
    
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class RatingRequest(BaseModel):
    """评价请求"""
    message_id: int = Field(..., description="消息ID")
    rating: int = Field(..., ge=1, le=3, description="评分：1=差评, 2=一般, 3=好评")
    feedback: str | None = Field(None, max_length=500, description="反馈内容")


class RatingResponse(BaseModel):
    """评价响应"""
    success: bool = True
    message: str = "评价成功"
