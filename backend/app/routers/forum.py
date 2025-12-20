"""论坛API路由"""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.models.user import User
from app.models.forum import Post, Comment
from app.schemas.forum import (
    PostCreate, PostUpdate, PostResponse, PostListResponse,
    CommentCreate, CommentResponse, CommentListResponse,
    LikeResponse, AuthorInfo, ReactionRequest, ReactionResponse, ReactionCount,
    HotPostRequest, EssencePostRequest, PinPostRequest
)
from app.services.forum_service import forum_service
from app.utils.deps import get_current_user, get_current_user_optional
from app.utils.content_filter import check_post_content, check_comment_content

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forum", tags=["社区论坛"])


# ============ 帖子相关 ============

@router.post("/posts", response_model=PostResponse, summary="发布帖子")
async def create_post(
    post_data: PostCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """发布新帖子（需登录）"""
    # 敏感词检测
    passed, error_msg = check_post_content(post_data.title, post_data.content)
    if not passed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    post = await forum_service.create_post(db, current_user.id, post_data)
    return await _build_post_response(db, post, current_user.id)


@router.get("/posts", response_model=PostListResponse, summary="获取帖子列表")
async def get_posts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    """获取帖子列表，支持分类筛选和关键词搜索"""
    posts, total = await forum_service.get_posts(db, page, page_size, category, keyword)
    
    user_id = current_user.id if current_user else None
    items = [await _build_post_response(db, post, user_id) for post in posts]
    
    return PostListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/me/posts", response_model=PostListResponse, summary="获取我发布的帖子")
async def get_my_posts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    """获取当前用户发布的帖子列表"""
    posts, total = await forum_service.get_user_posts(db, current_user.id, page, page_size, category, keyword)
    items = [await _build_post_response(db, post, current_user.id) for post in posts]
    return PostListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/posts/{post_id}", response_model=PostResponse, summary="获取帖子详情")
async def get_post(
    post_id: int,
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取帖子详情，自动增加浏览量"""
    try:
        post = await forum_service.get_post(db, post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

        await forum_service.increment_view(db, post)

        # 注意：increment_view 会提交事务，某些情况下会导致后续访问关系字段触发懒加载（async 下会抛 MissingGreenlet）。
        # 这里重新查询一次（带 author 预加载）保证构建响应不会触发隐式 IO。
        post = await forum_service.get_post(db, post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

        user_id = current_user.id if current_user else None
        return await _build_post_response(db, post, user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取帖子详情失败 post_id=%s", post_id)
        detail = str(e) if settings.debug else "服务器错误"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


@router.put("/posts/{post_id}", response_model=PostResponse, summary="更新帖子")
async def update_post(
    post_id: int,
    post_data: PostUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """更新帖子（仅作者或管理员可操作）"""
    from app.utils.permissions import is_owner_or_admin
    
    post = await forum_service.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    # 使用权限系统检查
    if not is_owner_or_admin(current_user, post.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有作者或管理员可以编辑帖子"
        )
    
    updated_post = await forum_service.update_post(db, post, post_data)
    return await _build_post_response(db, updated_post, current_user.id)


@router.delete("/posts/{post_id}", summary="删除帖子")
async def delete_post(
    post_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """删除帖子（仅作者、版主或管理员可操作）"""
    from app.utils.permissions import is_owner_or_admin
    
    post = await forum_service.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    # 使用权限系统检查
    if not is_owner_or_admin(current_user, post.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有作者、版主或管理员可以删除帖子"
        )
    
    await forum_service.delete_post(db, post)
    return {"message": "删除成功"}


@router.post("/posts/{post_id}/like", response_model=LikeResponse, summary="点赞/取消点赞帖子")
async def toggle_post_like(
    post_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """切换帖子点赞状态"""
    post = await forum_service.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

    try:
        liked, like_count = await forum_service.toggle_post_like(db, post_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    message = "点赞成功" if liked else "取消点赞"
    
    return LikeResponse(liked=liked, like_count=like_count, message=message)


# ============ 收藏相关 ============

@router.post("/posts/{post_id}/favorite", summary="收藏/取消收藏帖子")
async def toggle_post_favorite(
    post_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """切换帖子收藏状态"""
    post = await forum_service.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    favorited, favorite_count = await forum_service.toggle_post_favorite(db, post_id, current_user.id)
    message = "收藏成功" if favorited else "取消收藏"
    
    return {"favorited": favorited, "favorite_count": favorite_count, "message": message}


@router.get("/favorites", response_model=PostListResponse, summary="获取我的收藏")
async def get_my_favorites(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    """获取当前用户收藏的帖子列表"""
    posts, total = await forum_service.get_user_favorites(db, current_user.id, page, page_size, category, keyword)
    
    items = [await _build_post_response(db, post, current_user.id) for post in posts]
    
    return PostListResponse(items=items, total=total, page=page, page_size=page_size)


# ============ 评论相关 ============

@router.post("/posts/{post_id}/comments", response_model=CommentResponse, summary="发表评论")
async def create_comment(
    post_id: int,
    comment_data: CommentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """发表评论（需登录）"""
    # 敏感词检测
    passed, error_msg = check_comment_content(comment_data.content)
    if not passed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    post = await forum_service.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    comment = await forum_service.create_comment(db, post_id, current_user.id, comment_data)
    return await _build_comment_response(db, comment, current_user.id)


@router.get("/posts/{post_id}/comments", response_model=CommentListResponse, summary="获取评论列表")
async def get_comments(
    post_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    """获取帖子的评论列表"""
    post = await forum_service.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    comments, total = await forum_service.get_comments(db, post_id, page, page_size)
    
    user_id = current_user.id if current_user else None
    items = [await _build_comment_response(db, c, user_id) for c in comments]
    
    return CommentListResponse(items=items, total=total)


@router.delete("/comments/{comment_id}", summary="删除评论")
async def delete_comment(
    comment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """删除评论（仅作者、版主或管理员可操作）"""
    from app.utils.permissions import is_owner_or_admin
    
    comment = await forum_service.get_comment(db, comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")
    
    # 使用权限系统检查
    if not is_owner_or_admin(current_user, comment.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有作者、版主或管理员可以删除评论"
        )
    
    await forum_service.delete_comment(db, comment)
    return {"message": "删除成功"}


# ============ 辅助函数 ============

async def _build_post_response(db: AsyncSession, post: Post, user_id: int | None) -> PostResponse:
    """构建帖子响应"""
    is_liked = False
    if user_id:
        is_liked = await forum_service.is_post_liked(db, post.id, user_id)

    is_favorited = False
    if user_id:
        is_favorited = await forum_service.is_post_favorited(db, post.id, user_id)

    favorite_count = await forum_service.get_post_favorite_count(db, post.id)
    
    author_info = None
    if post.author:
        author_info = AuthorInfo(
            id=post.author.id,
            username=post.author.username,
            nickname=post.author.nickname,
            avatar=post.author.avatar
        )
    
    import json as json_module
    
    # 解析图片和附件
    images: list[str] = []
    if post.images:
        try:
            images = json_module.loads(post.images)
        except (json_module.JSONDecodeError, TypeError):
            images = []
    
    attachments: list[dict[str, str]] = []
    if post.attachments:
        try:
            attachments = json_module.loads(post.attachments)
        except (json_module.JSONDecodeError, TypeError):
            attachments = []
    
    # 获取表情反应统计
    reactions_data = await forum_service.get_post_reactions(db, post.id)
    reactions = [ReactionCount(emoji=str(r["emoji"]), count=int(r["count"])) for r in reactions_data]
    
    return PostResponse(
        id=post.id,
        title=post.title,
        content=post.content,
        category=post.category,
        user_id=post.user_id,
        view_count=int(post.view_count or 0),
        like_count=int(post.like_count or 0),
        comment_count=int(post.comment_count or 0),
        share_count=int(post.share_count or 0),
        favorite_count=favorite_count,
        is_pinned=bool(post.is_pinned),
        is_hot=bool(post.is_hot),
        is_essence=bool(post.is_essence),
        heat_score=float(post.heat_score or 0.0),
        cover_image=post.cover_image,
        images=images,
        attachments=attachments,
        reactions=reactions,
        created_at=post.created_at,
        updated_at=post.updated_at or post.created_at,
        author=author_info,
        is_liked=is_liked,
        is_favorited=is_favorited
    )


async def _build_comment_response(db: AsyncSession, comment: Comment, user_id: int | None) -> CommentResponse:
    """构建评论响应"""
    _ = db
    _ = user_id
    author_info = None
    if comment.author:
        author_info = AuthorInfo(
            id=comment.author.id,
            username=comment.author.username,
            nickname=comment.author.nickname,
            avatar=comment.author.avatar
        )
    
    return CommentResponse(
        id=comment.id,
        content=comment.content,
        post_id=comment.post_id,
        user_id=comment.user_id,
        parent_id=comment.parent_id,
        like_count=comment.like_count,
        created_at=comment.created_at,
        author=author_info,
        is_liked=False,
        replies=[]
    )


# ============ 表情反应 ============

@router.post("/posts/{post_id}/reaction", response_model=ReactionResponse, summary="添加/取消表情反应")
async def toggle_reaction(
    post_id: int,
    reaction_data: ReactionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """添加或取消帖子的表情反应"""
    post = await forum_service.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    reacted, reactions = await forum_service.toggle_reaction(db, post_id, current_user.id, reaction_data.emoji)
    
    return ReactionResponse(
        reacted=reacted,
        emoji=reaction_data.emoji,
        reactions=[ReactionCount(emoji=str(r["emoji"]), count=int(r["count"])) for r in reactions],
        message="已添加反应" if reacted else "已取消反应"
    )


# ============ 管理员接口 ============

@router.get("/stats", summary="获取论坛统计")
async def get_forum_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取论坛统计数据（管理员）"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    stats = await forum_service.get_forum_stats(db)
    return stats


@router.get("/admin/posts", response_model=PostListResponse, summary="管理员获取帖子列表")
async def admin_get_posts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    """管理员获取帖子列表，包含所有状态"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    posts, total = await forum_service.get_posts(db, page, page_size, category, keyword)
    items = [await _build_post_response(db, post, current_user.id) for post in posts]
    
    return PostListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/admin/posts/{post_id}/pin", summary="设置置顶")
async def admin_toggle_pin(
    post_id: int,
    pin_data: PinPostRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """设置帖子置顶状态"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    success = await forum_service.set_post_pinned(db, post_id, pin_data.is_pinned)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    return {"message": "置顶成功" if pin_data.is_pinned else "取消置顶成功"}


@router.post("/admin/posts/{post_id}/hot", summary="设置热门")
async def admin_toggle_hot(
    post_id: int,
    hot_data: HotPostRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """设置帖子热门状态"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    success = await forum_service.set_post_hot(db, post_id, hot_data.is_hot)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    return {"message": "设为热门成功" if hot_data.is_hot else "取消热门成功"}


@router.post("/admin/posts/{post_id}/essence", summary="设置精华")
async def admin_toggle_essence(
    post_id: int,
    essence_data: EssencePostRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """设置帖子精华状态"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    success = await forum_service.set_post_essence(db, post_id, essence_data.is_essence)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    return {"message": "设为精华成功" if essence_data.is_essence else "取消精华成功"}


@router.post("/admin/update-heat-scores", summary="更新所有帖子热度")
async def admin_update_heat_scores(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """批量更新所有帖子的热度分数"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    updated = await forum_service.update_heat_scores(db)
    return {"message": f"已更新 {updated} 个帖子的热度分数", "updated_count": updated}


# ============ 内容审核 ============

from sqlalchemy import select, func
from pydantic import BaseModel
from app.utils.content_filter import get_all_sensitive_words, add_sensitive_word, remove_sensitive_word, get_all_ad_words, add_ad_word, remove_ad_word


class ReviewAction(BaseModel):
    action: str  # approve / reject / delete
    reason: str | None = None


class SensitiveWordRequest(BaseModel):
    word: str


@router.get("/admin/pending-comments", summary="获取待审核评论")
async def get_pending_comments(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取待审核的评论列表"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    # 查询被标记需要审核的评论(通过status字段判断)
    query = select(Comment).where(
        Comment.is_deleted == False
    ).order_by(Comment.created_at.desc())
    
    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    comments = result.scalars().all()
    
    items = []
    for c in comments:
        # 获取用户信息
        user_result = await db.execute(select(User).where(User.id == c.user_id))
        user = user_result.scalar_one_or_none()
        
        # 获取帖子信息
        post_result = await db.execute(select(Post).where(Post.id == c.post_id))
        post = post_result.scalar_one_or_none()
        
        items.append({
            "id": c.id,
            "content": c.content,
            "user_id": c.user_id,
            "username": user.username if user else None,
            "post_id": c.post_id,
            "post_title": post.title if post else None,
            "created_at": c.created_at,
        })
    
    return {"items": items, "total": total}


@router.post("/admin/comments/{comment_id}/review", summary="审核评论")
async def review_comment(
    comment_id: int,
    data: ReviewAction,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """审核评论"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    
    if data.action == "delete":
        comment.is_deleted = True
        await db.commit()
        return {"message": "评论已删除"}
    elif data.action == "approve":
        # 评论审核通过，无需额外操作
        await db.commit()
        return {"message": "评论已通过审核"}
    elif data.action == "reject":
        comment.is_deleted = True
        await db.commit()
        return {"message": "评论已驳回并删除"}
    else:
        raise HTTPException(status_code=400, detail="无效操作")


@router.get("/admin/sensitive-words", summary="获取敏感词列表")
async def get_sensitive_words(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """获取所有敏感词"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    return {
        "sensitive_words": get_all_sensitive_words(),
        "ad_words": get_all_ad_words(),
    }


@router.post("/admin/sensitive-words", summary="添加敏感词")
async def add_word(
    data: SensitiveWordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """添加敏感词"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    add_sensitive_word(data.word)
    return {"message": f"已添加敏感词: {data.word}"}


@router.delete("/admin/sensitive-words/{word}", summary="删除敏感词")
async def delete_word(
    word: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """删除敏感词"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    remove_sensitive_word(word)
    return {"message": f"已删除敏感词: {word}"}


@router.post("/admin/ad-words", summary="添加广告词")
async def add_advertisement_word(
    data: SensitiveWordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """添加广告词"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    add_ad_word(data.word)
    return {"message": f"已添加广告词: {data.word}"}


@router.delete("/admin/ad-words/{word}", summary="删除广告词")
async def delete_advertisement_word(
    word: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """删除广告词"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")

    remove_ad_word(word)
    return {"message": f"已删除广告词: {word}"}


@router.get("/admin/content-stats", summary="内容审核统计")
async def get_content_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取内容审核统计数据"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    
    # 帖子统计
    total_posts = await db.scalar(select(func.count()).select_from(Post)) or 0
    deleted_posts = await db.scalar(
        select(func.count()).select_from(Post).where(Post.is_deleted == True)
    ) or 0
    
    # 评论统计
    total_comments = await db.scalar(select(func.count()).select_from(Comment)) or 0
    deleted_comments = await db.scalar(
        select(func.count()).select_from(Comment).where(Comment.is_deleted == True)
    ) or 0
    
    return {
        "posts": {
            "total": total_posts,
            "deleted": deleted_posts,
            "active": total_posts - deleted_posts,
        },
        "comments": {
            "total": total_comments,
            "deleted": deleted_comments,
            "active": total_comments - deleted_comments,
        },
        "sensitive_words_count": len(get_all_sensitive_words()),
        "ad_words_count": len(get_all_ad_words()),
    }
