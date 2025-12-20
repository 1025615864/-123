"""论坛相关的Pydantic模式"""
from datetime import datetime
from pydantic import BaseModel, Field


# ============ 帖子相关 ============

class PostCreate(BaseModel):
    """创建帖子"""
    title: str = Field(..., min_length=1, max_length=200, description="标题")
    content: str = Field(..., min_length=1, description="内容")
    category: str = Field(default="general", description="分类")
    cover_image: str | None = Field(None, description="封面图URL")
    images: list[str] | None = Field(None, description="图片URL列表")
    attachments: list[dict[str, str]] | None = Field(None, description="附件列表[{name, url}]")


class PostUpdate(BaseModel):
    """更新帖子"""
    title: str | None = Field(None, max_length=200)
    content: str | None = None
    category: str | None = None
    cover_image: str | None = None
    images: list[str] | None = None
    attachments: list[dict[str, str]] | None = None
    is_pinned: bool | None = None
    is_hot: bool | None = None
    is_essence: bool | None = None


class AuthorInfo(BaseModel):
    """作者信息"""
    id: int
    username: str
    nickname: str | None = None
    avatar: str | None = None
    
    model_config = {"from_attributes": True}


class ReactionCount(BaseModel):
    """表情反应统计"""
    emoji: str
    count: int


class PostResponse(BaseModel):
    """帖子响应"""
    id: int
    title: str
    content: str
    category: str
    user_id: int
    view_count: int
    like_count: int
    comment_count: int
    favorite_count: int
    share_count: int = 0
    is_pinned: bool
    is_hot: bool = False
    is_essence: bool = False
    heat_score: float = 0.0
    cover_image: str | None = None
    images: list[str] = []
    attachments: list[dict[str, str]] = []
    created_at: datetime
    updated_at: datetime
    author: AuthorInfo | None = None
    is_liked: bool = False
    is_favorited: bool = False
    reactions: list[ReactionCount] = []  # 表情反应统计
    
    model_config = {"from_attributes": True}


class PostListResponse(BaseModel):
    """帖子列表响应"""
    items: list[PostResponse]
    total: int
    page: int
    page_size: int


# ============ 评论相关 ============

class CommentCreate(BaseModel):
    """创建评论"""
    content: str = Field(..., min_length=1, description="评论内容")
    parent_id: int | None = Field(None, description="父评论ID，回复时使用")
    images: list[str] | None = Field(None, description="评论图片URL列表")


class CommentResponse(BaseModel):
    """评论响应"""
    id: int
    content: str
    post_id: int
    user_id: int
    parent_id: int | None = None
    like_count: int
    images: list[str] = []
    created_at: datetime
    author: AuthorInfo | None = None
    is_liked: bool = False
    replies: list["CommentResponse"] = []
    
    model_config = {"from_attributes": True}


class CommentListResponse(BaseModel):
    """评论列表响应"""
    items: list[CommentResponse]
    total: int


# ============ 点赞相关 ============

class LikeResponse(BaseModel):
    """点赞响应"""
    liked: bool
    like_count: int
    message: str


# ============ 表情反应相关 ============

class ReactionRequest(BaseModel):
    """表情反应请求"""
    emoji: str = Field(..., min_length=1, max_length=20, description="表情符号")


class ReactionResponse(BaseModel):
    """表情反应响应"""
    reacted: bool
    emoji: str
    reactions: list[ReactionCount]
    message: str


# ============ 热门帖子相关 ============

class HotPostRequest(BaseModel):
    """设置热门帖子请求"""
    is_hot: bool = Field(..., description="是否设为热门")


class EssencePostRequest(BaseModel):
    """设置精华帖请求"""
    is_essence: bool = Field(..., description="是否设为精华")


class PinPostRequest(BaseModel):
    """设置置顶帖请求"""
    is_pinned: bool = Field(..., description="是否置顶")


class PostStatsResponse(BaseModel):
    """帖子统计响应"""
    total_posts: int
    total_views: int
    total_likes: int
    total_comments: int
    hot_posts_count: int
    essence_posts_count: int
    category_stats: list[dict[str, int]]
