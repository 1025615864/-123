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
    source_url: str | None = Field(None, description="来源链接")
    source_site: str | None = Field(None, max_length=100, description="来源站点")
    author: str | None = Field(None, max_length=50, description="作者")
    is_top: bool = Field(default=False, description="是否置顶")
    is_published: bool = Field(default=True, description="是否发布")
    review_status: str | None = Field(None, description="审核状态：pending/approved/rejected")
    review_reason: str | None = Field(None, max_length=200, description="审核原因")
    scheduled_publish_at: datetime | None = Field(None, description="定时发布时间")
    scheduled_unpublish_at: datetime | None = Field(None, description="定时下线时间")


class NewsUpdate(BaseModel):
    """更新新闻"""
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    content: str | None = None
    cover_image: str | None = None
    category: str | None = None
    source: str | None = None
    source_url: str | None = None
    source_site: str | None = None
    author: str | None = None
    is_top: bool | None = None
    is_published: bool | None = None
    review_status: str | None = None
    review_reason: str | None = Field(default=None, max_length=200)
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    scheduled_publish_at: datetime | None = None
    scheduled_unpublish_at: datetime | None = None


class NewsAIAnnotationResponse(BaseModel):
    summary: str | None = None
    risk_level: str
    sensitive_words: list[str] = []
    highlights: list[str] = []
    keywords: list[str] = []
    duplicate_of_news_id: int | None = None
    processed_at: datetime | None = None


class NewsResponse(BaseModel):
    """新闻响应"""
    id: int
    title: str
    summary: str | None = None
    ai_annotation: NewsAIAnnotationResponse | None = None
    content: str
    cover_image: str | None = None
    category: str
    source: str | None = None
    source_url: str | None = None
    source_site: str | None = None
    author: str | None = None
    view_count: int
    favorite_count: int = 0
    is_favorited: bool = False
    ai_risk_level: str | None = None
    is_top: bool
    is_published: bool
    review_status: str | None = None
    review_reason: str | None = None
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    scheduled_publish_at: datetime | None = None
    scheduled_unpublish_at: datetime | None = None
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
    source_url: str | None = None
    source_site: str | None = None
    author: str | None = None
    view_count: int
    favorite_count: int = 0
    is_favorited: bool = False
    ai_risk_level: str | None = None
    ai_keywords: list[str] = []
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
    source_url: str | None = None
    source_site: str | None = None
    author: str | None = None
    view_count: int
    ai_risk_level: str | None = None
    is_top: bool
    is_published: bool
    review_status: str | None = None
    review_reason: str | None = None
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    scheduled_publish_at: datetime | None = None
    scheduled_unpublish_at: datetime | None = None
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


class NewsCommentAuthor(BaseModel):
    id: int
    username: str
    nickname: str | None = None
    avatar: str | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, description="评论内容")


class NewsCommentResponse(BaseModel):
    id: int
    news_id: int
    user_id: int
    content: str
    review_status: str | None = None
    review_reason: str | None = None
    created_at: datetime
    author: NewsCommentAuthor | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsCommentListResponse(BaseModel):
    items: list[NewsCommentResponse]
    total: int
    page: int
    page_size: int


class NewsCommentAdminNewsBrief(BaseModel):
    id: int
    title: str

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsCommentAdminItem(BaseModel):
    id: int
    news_id: int
    user_id: int
    content: str
    is_deleted: bool
    review_status: str | None = None
    review_reason: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    author: NewsCommentAuthor | None = None
    news: NewsCommentAdminNewsBrief | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsCommentAdminListResponse(BaseModel):
    items: list[NewsCommentAdminItem]
    total: int
    page: int
    page_size: int


class NewsCommentReviewAction(BaseModel):
    action: str = Field(..., description="approve/reject/delete")
    reason: str | None = Field(None, max_length=200)


class NewsReviewAction(BaseModel):
    action: str = Field(..., description="approve/reject/pending")
    reason: str | None = Field(None, max_length=200)


class NewsVersionItem(BaseModel):
    id: int
    news_id: int
    action: str
    reason: str | None = None
    snapshot_json: str
    created_by: int
    created_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsVersionListResponse(BaseModel):
    items: list[NewsVersionItem]


class NewsRollbackRequest(BaseModel):
    version_id: int
    reason: str | None = Field(None, max_length=200)


class NewsAIGenerationItem(BaseModel):
    id: int
    user_id: int
    news_id: int | None = None
    task_type: str
    status: str
    input_json: str
    output_json: str | None = None
    raw_output: str | None = None
    error: str | None = None
    created_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsAIGenerationListResponse(BaseModel):
    items: list[NewsAIGenerationItem]


class NewsAIGenerateRequest(BaseModel):
    news_id: int | None = None
    task_type: str = Field(..., min_length=1, max_length=50)
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    style: str | None = Field(None, max_length=50)
    word_count_min: int | None = Field(None, ge=0, le=20000)
    word_count_max: int | None = Field(None, ge=0, le=20000)
    append: bool = False
    use_news_content: bool = True


class NewsLinkCheckRequest(BaseModel):
    news_id: int | None = None
    markdown: str | None = None
    timeout_seconds: float = Field(6.0, ge=1.0, le=30.0)
    max_urls: int = Field(50, ge=1, le=200)
    use_news_content: bool = True


class NewsLinkCheckItem(BaseModel):
    id: int
    run_id: str
    user_id: int
    news_id: int | None = None
    url: str
    final_url: str | None = None
    ok: bool
    status_code: int | None = None
    error: str | None = None
    checked_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsLinkCheckListResponse(BaseModel):
    items: list[NewsLinkCheckItem]


class NewsLinkCheckResponse(BaseModel):
    run_id: str
    items: list[NewsLinkCheckItem]


class NewsBatchActionRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)
    action: str = Field(..., min_length=1, max_length=50)
    reason: str | None = Field(None, max_length=200)


class NewsBatchQueryRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=50)
    limit: int = Field(200, ge=1, le=500)
    category: str | None = None
    keyword: str | None = None
    review_status: str | None = None
    risk_level: str | None = None
    source_site: str | None = None
    source: str | None = None
    topic_id: int | None = Field(None, ge=1)


class NewsBatchActionResponse(BaseModel):
    requested: list[int]
    processed: list[int]
    missing: list[int]
    skipped: list[int]
    action: str
    reason: str | None = None
    message: str


class ScheduledNewsItem(BaseModel):
    id: int
    title: str
    category: str
    is_published: bool
    review_status: str | None = None
    scheduled_publish_at: datetime | None = None
    scheduled_unpublish_at: datetime | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class ScheduledNewsListResponse(BaseModel):
    items: list[ScheduledNewsItem]


class NewsTopicCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    cover_image: str | None = None
    is_active: bool = True
    sort_order: int = 0
    auto_category: str | None = Field(None, max_length=50)
    auto_keyword: str | None = Field(None, max_length=100)
    auto_limit: int = Field(0, ge=0, le=500)


class NewsTopicUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=500)
    cover_image: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    auto_category: str | None = Field(None, max_length=50)
    auto_keyword: str | None = Field(None, max_length=100)
    auto_limit: int | None = Field(None, ge=0, le=500)


class NewsTopicResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    cover_image: str | None = None
    is_active: bool
    sort_order: int
    auto_category: str | None = None
    auto_keyword: str | None = None
    auto_limit: int
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsTopicListResponse(BaseModel):
    items: list[NewsTopicResponse]


class NewsTopicDetailResponse(BaseModel):
    topic: NewsTopicResponse
    items: list[NewsListItem]
    total: int
    page: int
    page_size: int


class NewsTopicItemCreate(BaseModel):
    news_id: int
    position: int | None = None


class NewsTopicItemBulkCreate(BaseModel):
    news_ids: list[int]
    position_start: int | None = None


class NewsTopicItemBulkResponse(BaseModel):
    requested: int
    added: int
    skipped: int


class NewsTopicItemBulkDelete(BaseModel):
    item_ids: list[int]


class NewsTopicItemBulkDeleteResponse(BaseModel):
    requested: int
    deleted: int
    skipped: int


class NewsTopicItemsReindexResponse(BaseModel):
    updated: int


class NewsTopicItemsReorderRequest(BaseModel):
    item_ids: list[int]


class NewsTopicAutoCacheRefreshResponse(BaseModel):
    cached: int


class NewsTopicImportRequest(BaseModel):
    category: str | None = None
    keyword: str | None = None
    limit: int = Field(50, ge=1, le=500)
    include_unpublished: bool = False
    position_start: int | None = None


class NewsTopicImportResponse(BaseModel):
    requested: int
    added: int
    skipped: int


class NewsTopicItemUpdate(BaseModel):
    position: int


class NewsTopicItemBrief(BaseModel):
    id: int
    news_id: int
    position: int
    title: str
    category: str


class NewsTopicAdminDetailResponse(BaseModel):
    topic: NewsTopicResponse
    items: list[NewsTopicItemBrief]


class NewsTopicReportItem(BaseModel):
    id: int
    title: str
    is_active: bool
    sort_order: int
    manual_item_count: int
    manual_view_count: int
    manual_favorite_count: int
    manual_conversion_rate: float


class NewsTopicReportResponse(BaseModel):
    items: list[NewsTopicReportItem]


class NewsSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    feed_url: str = Field(..., min_length=1, max_length=500)
    site: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=50)
    is_enabled: bool = True
    fetch_timeout_seconds: float | None = None
    max_items_per_feed: int | None = Field(None, ge=1, le=200)


class NewsSourceUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    feed_url: str | None = Field(None, max_length=500)
    site: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=50)
    is_enabled: bool | None = None
    fetch_timeout_seconds: float | None = None
    max_items_per_feed: int | None = Field(None, ge=1, le=200)


class NewsSourceResponse(BaseModel):
    id: int
    name: str
    source_type: str
    feed_url: str
    site: str | None = None
    category: str | None = None
    is_enabled: bool
    fetch_timeout_seconds: float | None = None
    max_items_per_feed: int | None = None
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsSourceListResponse(BaseModel):
    items: list[NewsSourceResponse]


class NewsIngestRunResponse(BaseModel):
    id: int
    source_id: int | None = None
    source_name: str | None = None
    feed_url: str | None = None
    status: str
    fetched: int
    inserted: int
    skipped: int
    errors: int
    last_error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    created_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class NewsIngestRunListResponse(BaseModel):
    items: list[NewsIngestRunResponse]
    total: int
    page: int
    page_size: int


class NewsSourceHealthItem(BaseModel):
    source_id: int
    recent_total: int
    recent_failed: int
    failure_rate: float
    last_status: str | None = None
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None


class NewsSourceHealthListResponse(BaseModel):
    limit_per_source: int
    items: list[NewsSourceHealthItem]
