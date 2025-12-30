"""知识库相关的Pydantic模式"""
from typing import ClassVar
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from enum import Enum


class KnowledgeType(str, Enum):
    """知识类型"""
    LAW = "law"
    CASE = "case"
    REGULATION = "regulation"
    INTERPRETATION = "interpretation"


class LegalKnowledgeBase(BaseModel):
    """法律知识基础模式"""
    knowledge_type: KnowledgeType = Field(..., description="知识类型")
    title: str = Field(..., min_length=1, max_length=200, description="标题")
    article_number: str | None = Field(None, max_length=50, description="条款编号")
    content: str = Field(..., min_length=1, description="内容")
    summary: str | None = Field(None, description="摘要/要点")
    category: str = Field(..., min_length=1, max_length=50, description="分类")
    keywords: str | None = Field(None, max_length=500, description="关键词，逗号分隔")
    source: str | None = Field(None, max_length=200, description="来源")
    effective_date: str | None = Field(None, max_length=20, description="生效日期")
    weight: float = Field(1.0, ge=0, le=10, description="权重")
    is_active: bool = Field(True, description="是否启用")


class LegalKnowledgeCreate(LegalKnowledgeBase):
    """创建法律知识"""
    pass


class LegalKnowledgeUpdate(BaseModel):
    """更新法律知识"""
    knowledge_type: KnowledgeType | None = None
    title: str | None = Field(None, min_length=1, max_length=200)
    article_number: str | None = None
    content: str | None = Field(None, min_length=1)
    summary: str | None = None
    category: str | None = Field(None, min_length=1, max_length=50)
    keywords: str | None = None
    source: str | None = None
    effective_date: str | None = None
    weight: float | None = Field(None, ge=0, le=10)
    is_active: bool | None = None


class LegalKnowledgeResponse(LegalKnowledgeBase):
    """法律知识响应"""
    id: int
    is_vectorized: bool
    created_at: datetime
    updated_at: datetime
    
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class LegalKnowledgeListResponse(BaseModel):
    """法律知识列表响应"""
    items: list[LegalKnowledgeResponse]
    total: int
    page: int
    page_size: int


# 咨询模板相关
class TemplateQuestionItem(BaseModel):
    """模板问题项"""
    question: str = Field(..., description="问题内容")
    hint: str | None = Field(None, description="提示信息")


class ConsultationTemplateBase(BaseModel):
    """咨询模板基础模式"""
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: str | None = Field(None, max_length=500, description="描述")
    category: str = Field(..., min_length=1, max_length=50, description="分类")
    icon: str = Field("MessageSquare", max_length=50, description="图标名称")
    questions: list[TemplateQuestionItem] = Field(..., min_length=1, description="问题列表")
    sort_order: int = Field(0, ge=0, description="排序顺序")
    is_active: bool = Field(True, description="是否启用")


class ConsultationTemplateCreate(ConsultationTemplateBase):
    """创建咨询模板"""
    pass


class ConsultationTemplateUpdate(BaseModel):
    """更新咨询模板"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    category: str | None = Field(None, min_length=1, max_length=50)
    icon: str | None = None
    questions: list[TemplateQuestionItem] | None = None
    sort_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class ConsultationTemplateResponse(BaseModel):
    """咨询模板响应"""
    id: int
    name: str
    description: str | None
    category: str
    icon: str
    questions: list[TemplateQuestionItem]
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


# 知识库统计
class KnowledgeCategoryCount(BaseModel):
    category: str = Field(..., description="分类")
    count: int = Field(..., description="数量")


class KnowledgeStats(BaseModel):
    """知识库统计"""
    total_laws: int = Field(..., description="法条总数")
    total_cases: int = Field(..., description="案例总数")
    total_regulations: int = Field(..., description="法规总数")
    total_interpretations: int = Field(..., description="司法解释总数")
    vectorized_count: int = Field(..., description="已向量化数量")
    categories: list[KnowledgeCategoryCount] = Field(..., description="分类统计")


# 批量操作
class BatchVectorizeRequest(BaseModel):
    """批量向量化请求"""
    ids: list[int] = Field(..., min_length=1, description="知识ID列表")


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    ids: list[int] = Field(..., min_length=1, description="知识ID列表")


class BatchOperationResponse(BaseModel):
    """批量操作响应"""
    success_count: int
    failed_count: int
    message: str
