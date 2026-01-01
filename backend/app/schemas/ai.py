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


class SearchQualityInfo(BaseModel):
    total_candidates: int = Field(0, description="检索候选数量")
    qualified_count: int = Field(0, description="通过阈值过滤的引用数量")
    avg_similarity: float = Field(0.0, description="通过过滤结果的平均相似度")
    confidence: str = Field("low", description="检索置信度等级")
    fallback_used: bool = Field(False, description="是否使用了 DB 关键词检索作为降级")


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str = Field(..., description="会话ID")
    answer: str = Field(..., description="AI回复内容")
    references: Annotated[list[LawReference], Field(default_factory=list, description="引用的法律条文")]
    assistant_message_id: int | None = Field(None, description="本次AI回复对应的消息ID（用于评价）")
    strategy_used: str | None = Field(None, description="回答策略")
    strategy_reason: str | None = Field(None, description="策略选择原因")
    confidence: str | None = Field(None, description="置信度")
    risk_level: str | None = Field(None, description="风险等级")
    search_quality: SearchQualityInfo | None = Field(None, description="检索质量信息")
    disclaimer: str | None = Field(None, description="免责声明")
    model_used: str | None = Field(None, description="实际使用的模型")
    fallback_used: bool | None = Field(None, description="是否发生模型降级")
    model_attempts: list[str] | None = Field(None, description="尝试过的模型列表")
    intent: str | None = Field(None, description="识别到的意图类别")
    needs_clarification: bool | None = Field(None, description="是否需要追问补充信息")
    clarifying_questions: list[str] | None = Field(None, description="建议追问的问题列表")
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


class ShareLinkResponse(BaseModel):
    token: str
    share_path: str
    expires_at: datetime


class SharedMessageResponse(BaseModel):
    role: str
    content: str
    references: str | None = None
    created_at: datetime


class SharedConsultationResponse(BaseModel):
    session_id: str
    title: str | None
    created_at: datetime
    messages: list[SharedMessageResponse] = []


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
    is_favorite: bool = False
    
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class FavoriteToggleResponse(BaseModel):
    is_favorite: bool


class RatingRequest(BaseModel):
    """评价请求"""
    message_id: int = Field(..., description="消息ID")
    rating: int = Field(..., ge=1, le=3, description="评分：1=差评, 2=一般, 3=好评")
    feedback: str | None = Field(None, max_length=500, description="反馈内容")


class RatingResponse(BaseModel):
    """评价响应"""
    success: bool = True
    message: str = "评价成功"


class QuickRepliesRequest(BaseModel):
    user_message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    assistant_answer: str = Field(..., min_length=1, max_length=8000, description="AI回复")
    references: Annotated[list[LawReference], Field(default_factory=list, description="引用的法律条文")]


class QuickRepliesResponse(BaseModel):
    replies: Annotated[list[str], Field(default_factory=list, description="快捷回复候选")]


class TranscribeResponse(BaseModel):
    text: str = Field(..., description="语音转写文本")


class FileAnalyzeResponse(BaseModel):
    filename: str = Field(..., description="文件名")
    content_type: str | None = Field(None, description="文件类型")
    text_chars: int = Field(..., description="提取文本长度")
    text_preview: str = Field(..., description="提取文本预览")
    summary: str = Field(..., description="分析摘要")
