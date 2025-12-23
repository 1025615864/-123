"""新闻相关的Pydantic模式"""
from datetime import datetime
from typing import ClassVar
from pydantic import BaseModel, Field, ConfigDict


class NewsCreate(BaseModel):
    """创建新闻"""
    title: str = Field(..., min_length=1, max_length=200, description="标题")
    summary: str | None = Field(None, max_length=500, description="摘要")
    content: str = Field(..., min_length=1, description="内容")
    cover_image: str | None = Field(None, description="封面图URL")
    category: str = Field(default="general", description="分类")
    source: str | None = Field(None, max_length=100, description="来源")
    author: str | None = Field(None, max_length=50, description="作者")
    is_top: bool = Field(default=False, description="是否置顶")
    is_published: bool = Field(default=True, description="是否发布")


class NewsUpdate(BaseModel):
    """更新新闻"""
    title: str | None = Field(None, max_length=200)
    summary: str | None = Field(None, max_length=500)
    content: str | None = None
    cover_image: str | None = None
    category: str | None = None
    source: str | None = None
    author: str | None = None
    is_top: bool | None = None
    is_published: bool | None = None


class NewsResponse(BaseModel):
    """新闻响应"""
    id: int
    title: str
    summary: str | None = None
    content: str
    cover_image: str | None = None
    category: str
    source: str | None = None
    author: str | None = None
    view_count: int
    favorite_count: int = 0
    is_favorited: bool = False
    is_top: bool
    is_published: bool
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsListItem(BaseModel):
    """新闻列表项（不含详细内容）"""
    id: int
    title: str
    summary: str | None = None
    cover_image: str | None = None
    category: str
    source: str | None = None
    author: str | None = None
    view_count: int
    favorite_count: int = 0
    is_favorited: bool = False
    is_top: bool
    published_at: datetime | None = None
    created_at: datetime
    
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsListResponse(BaseModel):
    """新闻列表响应"""
    items: list[NewsListItem]
    total: int
    page: int
    page_size: int


class NewsAdminListItem(BaseModel):
    """管理员新闻列表项（包含发布状态等管理字段）"""

    id: int
    title: str
    summary: str | None = None
    cover_image: str | None = None
    category: str
    source: str | None = None
    author: str | None = None
    view_count: int
    is_top: bool
    is_published: bool
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsAdminListResponse(BaseModel):
    """管理员新闻列表响应"""

    items: list[NewsAdminListItem]
    total: int
    page: int
    page_size: int


class NewsCategoryCount(BaseModel):
    """分类统计"""
    category: str
    count: int


class NewsFavoriteResponse(BaseModel):
    """新闻收藏响应"""
    favorited: bool
    favorite_count: int
    message: str


class NewsSubscriptionCreate(BaseModel):
    sub_type: str = Field(..., description="订阅类型：category/keyword")
    value: str = Field(..., min_length=1, max_length=100, description="订阅值")


class NewsSubscriptionResponse(BaseModel):
    id: int
    sub_type: str
    value: str
    created_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
