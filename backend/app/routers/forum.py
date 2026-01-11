"""论坛API路由"""
import json
import logging
from datetime import datetime, timezone
from typing import Annotated, TypedDict, cast
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, case, and_, or_, desc
from pydantic import BaseModel

from ..database import get_db
from ..config import get_settings
from ..models.user import User
from ..models.forum import Post, Comment
from ..models.system import AdminLog, LogAction, SystemConfig
from ..models.notification import Notification, NotificationType
from ..schemas.forum import (
    PostCreate,
    PostUpdate,
    PostResponse,
    PostListResponse,
    PostIdListRequest,
    CommentCreate,
    CommentResponse,
    CommentListResponse,
    LikeResponse,
    AuthorInfo,
    ReactionRequest, ReactionResponse, ReactionCount,
    HotPostRequest, EssencePostRequest, PinPostRequest
)
from ..services.forum_service import forum_service
from ..utils.deps import get_current_user, get_current_user_optional, require_admin
from ..utils.rate_limiter import get_client_ip
from ..utils.content_filter import (
    check_post_content,
    check_comment_content,
)

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forum", tags=["社区论坛"])


async def _log_forum_admin_action(
    db: AsyncSession,
    *,
    user_id: int,
    action: str,
    module: str,
    target_id: int | None = None,
    target_type: str | None = None,
    description: str | None = None,
    extra_data: dict[str, object] | None = None,
    request: Request | None = None,
) -> None:
    ip_address = None
    user_agent = None
    if request is not None:
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:500]

    log = AdminLog(
        user_id=int(user_id),
        action=str(action),
        module=str(module),
        target_id=(int(target_id) if target_id is not None else None),
        target_type=target_type,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data=json.dumps(extra_data, ensure_ascii=False) if extra_data else None,
    )
    db.add(log)


def _create_notification(
    db: AsyncSession,
    *,
    user_id: int,
    title: str,
    content: str | None = None,
    link: str | None = None,
    related_user_id: int | None = None,
    related_post_id: int | None = None,
    related_comment_id: int | None = None,
) -> None:
    notification = Notification(
        user_id=int(user_id),
        type=NotificationType.SYSTEM,
        title=str(title),
        content=content,
        link=link,
        is_read=False,
        related_user_id=(int(related_user_id) if related_user_id is not None else None),
        related_post_id=(int(related_post_id) if related_post_id is not None else None),
        related_comment_id=(int(related_comment_id) if related_comment_id is not None else None),
    )
    db.add(notification)


# ============ 帖子相关 ============

@router.post("/posts", response_model=PostResponse, summary="发布帖子")
async def create_post(
    post_data: PostCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """发布新帖子（需登录）"""
    _ = await forum_service.apply_content_filter_config_from_db(db)

    # 敏感词检测
    passed, error_msg = check_post_content(post_data.title, post_data.content)
    if not passed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    post = await forum_service.create_post(db, current_user.id, post_data)
    if getattr(post, "review_status", None) == "pending":
        content_lines: list[str] = [f"标题：{post.title}"]
        if getattr(post, "review_reason", None):
            content_lines.append(f"原因：{post.review_reason}")
        _create_notification(
            db,
            user_id=int(post.user_id),
            title="你的帖子已提交审核",
            content="\n".join(content_lines) if content_lines else None,
            link=f"/forum/post/{int(post.id)}",
            related_post_id=int(post.id),
        )
        await db.commit()
    return await _build_post_response(db, post, current_user.id)


class ForumReviewConfig(BaseModel):
    comment_review_enabled: bool


class ForumPostReviewConfig(BaseModel):
    post_review_enabled: bool
    post_review_mode: str  # all / rule


class ForumContentFilterRulesUpdate(BaseModel):
    ad_words_threshold: int | None = None
    check_url: bool | None = None
    check_phone: bool | None = None


class ForumContentFilterConfig(BaseModel):
    sensitive_words: list[str]
    ad_words: list[str]
    ad_words_threshold: int
    check_url: bool
    check_phone: bool


@router.get("/admin/review-config", summary="获取论坛审核配置")
async def get_forum_review_config(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    enabled = await forum_service.is_comment_review_enabled(db)
    return {"comment_review_enabled": bool(enabled)}


@router.put("/admin/review-config", summary="更新论坛审核配置")
async def update_forum_review_config(
    data: ForumReviewConfig,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    value = "true" if data.comment_review_enabled else "false"
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "forum.review.enabled")
    )
    config = result.scalar_one_or_none()

    if config:
        config.value = value
        config.updated_by = current_user.id
        if not config.description:
            config.description = "论坛评论审核开关"
    else:
        config = SystemConfig(
            key="forum.review.enabled",
            value=value,
            description="论坛评论审核开关",
            category="forum",
            updated_by=current_user.id,
        )
        db.add(config)

    await _log_forum_admin_action(
        db,
        user_id=current_user.id,
        action=LogAction.CONFIG,
        module="forum",
        description="更新论坛评论审核配置",
        extra_data={"comment_review_enabled": bool(data.comment_review_enabled)},
        request=request,
    )
    await db.commit()
    return {"message": "配置已更新", "comment_review_enabled": bool(data.comment_review_enabled)}


@router.get("/admin/post-review-config", summary="获取帖子审核配置")
async def get_forum_post_review_config(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    enabled = await forum_service.is_post_review_enabled(db)
    mode = await forum_service.get_post_review_mode(db)
    return {"post_review_enabled": bool(enabled), "post_review_mode": str(mode)}


@router.put("/admin/post-review-config", summary="更新帖子审核配置")
async def update_forum_post_review_config(
    data: ForumPostReviewConfig,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    enabled_value = "true" if data.post_review_enabled else "false"
    mode_value = (data.post_review_mode or "").strip().lower()
    if mode_value not in ("all", "rule"):
        raise HTTPException(status_code=400, detail="post_review_mode 仅支持 all 或 rule")

    for key, value, desc in (
        ("forum.post_review.enabled", enabled_value, "论坛帖子审核开关"),
        ("forum.post_review.mode", mode_value, "论坛帖子审核模式（all/rule）"),
    ):
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        config = result.scalar_one_or_none()
        if config:
            config.value = value
            config.updated_by = current_user.id
            if not config.description:
                config.description = desc
        else:
            config = SystemConfig(
                key=key,
                value=value,
                description=desc,
                category="forum",
                updated_by=current_user.id,
            )
            db.add(config)

    await _log_forum_admin_action(
        db,
        user_id=current_user.id,
        action=LogAction.CONFIG,
        module="forum",
        description="更新论坛帖子审核配置",
        extra_data={
            "post_review_enabled": bool(data.post_review_enabled),
            "post_review_mode": mode_value,
        },
        request=request,
    )
    await db.commit()

    return {
        "message": "配置已更新",
        "post_review_enabled": bool(data.post_review_enabled),
        "post_review_mode": mode_value,
    }


@router.get("/admin/content-filter-config", response_model=ForumContentFilterConfig, summary="获取内容过滤规则配置")
async def get_content_filter_config(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    config = await forum_service.apply_content_filter_config_from_db(db)
    return ForumContentFilterConfig.model_validate(config)


@router.put("/admin/content-filter-config", response_model=ForumContentFilterConfig, summary="更新内容过滤规则配置")
async def update_content_filter_config(
    data: ForumContentFilterRulesUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    config = await forum_service.update_content_filter_rules(
        db,
        updated_by=current_user.id,
        ad_words_threshold=data.ad_words_threshold,
        check_url=data.check_url,
        check_phone=data.check_phone,
    )

    await _log_forum_admin_action(
        db,
        user_id=current_user.id,
        action=LogAction.CONFIG,
        module="forum",
        description="更新论坛内容过滤规则配置",
        extra_data={
            "ad_words_threshold": data.ad_words_threshold,
            "check_url": data.check_url,
            "check_phone": data.check_phone,
        },
        request=request,
    )
    await db.commit()

    return ForumContentFilterConfig.model_validate(config)


@router.get("/posts", response_model=PostListResponse, summary="获取帖子列表")
async def get_posts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
    is_essence: Annotated[bool | None, Query(description="是否仅精华帖")] = None,
):
    """获取帖子列表，支持分类筛选和关键词搜索"""
    posts, total = await forum_service.get_posts(db, page, page_size, category, keyword, is_essence=is_essence)
    
    user_id = current_user.id if current_user else None
    items = [await _build_post_response(db, post, user_id) for post in posts]
    
    return PostListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/hot", response_model=PostListResponse, summary="获取热门帖子")
async def get_hot_posts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    category: str | None = None,
):
    posts = await forum_service.get_hot_posts(db, limit=limit, category=category)
    user_id = current_user.id if current_user else None
    items = [await _build_post_response(db, post, user_id) for post in posts]
    return PostListResponse(items=items, total=len(items), page=1, page_size=limit)


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


class MyCommentItem(BaseModel):
    id: int
    post_id: int
    post_title: str | None = None
    content: str
    created_at: datetime
    review_status: str | None = None
    review_reason: str | None = None


class MyCommentListResponse(BaseModel):
    items: list[MyCommentItem]
    total: int
    page: int
    page_size: int


@router.get("/me/comments", response_model=MyCommentListResponse, summary="获取我发布的评论")
async def get_my_comments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_param: Annotated[
        str | None,
        Query(alias="status", description="筛选状态：all/pending/approved/rejected"),
    ] = None,
):
    status_filter = (status_param or "all").strip().lower()
    if status_filter not in ("all", "pending", "approved", "rejected"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status 仅支持 all / pending / approved / rejected")

    base_filter = and_(Comment.user_id == current_user.id)
    if status_filter == "all":
        base_filter = and_(
            base_filter,
            or_(Comment.is_deleted == False, Comment.review_status == "rejected"),
        )
    elif status_filter == "pending":
        base_filter = and_(base_filter, Comment.review_status == "pending", Comment.is_deleted == False)
    elif status_filter == "approved":
        approved_filter = or_(Comment.review_status.is_(None), Comment.review_status == "approved")
        base_filter = and_(base_filter, approved_filter, Comment.is_deleted == False)
    elif status_filter == "rejected":
        base_filter = and_(base_filter, Comment.review_status == "rejected")

    total_result = await db.execute(select(func.count(Comment.id)).where(base_filter))
    total = int(total_result.scalar() or 0)

    query = (
        select(
            Comment.id,
            Comment.post_id,
            Post.title.label("post_title"),
            Comment.content,
            Comment.created_at,
            Comment.review_status,
            Comment.review_reason,
        )
        .select_from(Comment)
        .outerjoin(Post, Post.id == Comment.post_id)
        .where(base_filter)
        .order_by(desc(Comment.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    rows = result.all()

    items: list[MyCommentItem] = []
    for row in rows:
        items.append(
            MyCommentItem(
                id=int(cast(int, row.id)),
                post_id=int(cast(int, row.post_id)),
                post_title=cast(str | None, row.post_title),
                content=str(cast(str, row.content)),
                created_at=cast(datetime, row.created_at),
                review_status=cast(str | None, row.review_status),
                review_reason=cast(str | None, row.review_reason),
            )
        )

    return MyCommentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/posts/batch/restore", summary="批量恢复帖子")
async def batch_restore_posts(
    payload: PostIdListRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..utils.permissions import is_owner_or_admin

    success_ids: list[int] = []
    failed: list[dict[str, object]] = []

    for post_id in payload.ids:
        post = await forum_service.get_post_any(db, int(post_id))
        if not post:
            failed.append({"id": int(post_id), "reason": "帖子不存在"})
            continue
        if not is_owner_or_admin(current_user, post.user_id):
            failed.append({"id": int(post_id), "reason": "无权限"})
            continue
        if not post.is_deleted:
            failed.append({"id": int(post_id), "reason": "帖子未被删除"})
            continue
        _ = await forum_service.restore_post(db, post)
        success_ids.append(int(post_id))

    return {"success_ids": success_ids, "failed": failed}


@router.post("/posts/batch/purge", summary="批量永久删除帖子")
async def batch_purge_posts(
    payload: PostIdListRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..utils.permissions import is_owner_or_admin

    success_ids: list[int] = []
    failed: list[dict[str, object]] = []

    for post_id in payload.ids:
        post = await forum_service.get_post_any(db, int(post_id))
        if not post:
            failed.append({"id": int(post_id), "reason": "帖子不存在"})
            continue
        if not is_owner_or_admin(current_user, post.user_id):
            failed.append({"id": int(post_id), "reason": "无权限"})
            continue
        if not post.is_deleted:
            failed.append({"id": int(post_id), "reason": "请先删除帖子"})
            continue
        await forum_service.purge_post(db, post)
        success_ids.append(int(post_id))

    return {"success_ids": success_ids, "failed": failed}


@router.get("/posts/{post_id}/recycle", response_model=PostResponse, summary="查看回收站帖子详情")
async def get_deleted_post_detail(
    post_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..utils.permissions import is_owner_or_admin

    post = await forum_service.get_post_any(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    if not post.is_deleted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该帖子未被删除")
    if not is_owner_or_admin(current_user, post.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限查看")

    return await _build_post_response(db, post, current_user.id)


@router.get("/me/posts/deleted", response_model=PostListResponse, summary="获取我删除的帖子（回收站）")
async def get_my_deleted_posts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    posts, total = await forum_service.get_user_deleted_posts(db, current_user.id, page, page_size, category, keyword)
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
            if current_user is not None:
                post_any = await forum_service.get_post_any(db, post_id)
                if post_any and not post_any.is_deleted:
                    from ..utils.permissions import is_owner_or_admin

                    if is_owner_or_admin(current_user, post_any.user_id):
                        post = post_any
                    else:
                        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限查看")

        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

        await forum_service.increment_view(db, post)

        # 注意：increment_view 会提交事务，某些情况下会导致后续访问关系字段触发懒加载（async 下会抛 MissingGreenlet）。
        # 这里重新查询一次（带 author 预加载）保证构建响应不会触发隐式 IO。
        post_review_status = getattr(post, "review_status", None)
        if post_review_status in (None, "approved"):
            post = await forum_service.get_post(db, post_id)
        else:
            post = await forum_service.get_post_any(db, post_id)
            if post and post.is_deleted:
                post = None

            if post and current_user is not None:
                from ..utils.permissions import is_owner_or_admin

                if not is_owner_or_admin(current_user, post.user_id):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限查看")

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
    from ..utils.permissions import is_owner_or_admin
    
    post = await forum_service.get_post_any(db, post_id)
    if not post or post.is_deleted:
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
    from ..utils.permissions import is_owner_or_admin
    
    post = await forum_service.get_post_any(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

    if post.is_deleted:
        return {"message": "帖子已删除"}
    
    # 使用权限系统检查
    if not is_owner_or_admin(current_user, post.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有作者、版主或管理员可以删除帖子"
        )
    
    await forum_service.delete_post(db, post)
    return {"message": "删除成功"}


@router.post("/posts/{post_id}/restore", summary="恢复帖子")
async def restore_post(
    post_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..utils.permissions import is_owner_or_admin

    post = await forum_service.get_post_any(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

    if not is_owner_or_admin(current_user, post.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有作者、版主或管理员可以恢复帖子")

    if not post.is_deleted:
        return {"message": "帖子未被删除"}

    _ = await forum_service.restore_post(db, post)
    return {"message": "恢复成功"}


@router.delete("/posts/{post_id}/purge", summary="永久删除帖子")
async def purge_post(
    post_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..utils.permissions import is_owner_or_admin

    post = await forum_service.get_post_any(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

    if not is_owner_or_admin(current_user, post.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有作者、版主或管理员可以永久删除帖子")

    if not post.is_deleted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先删除帖子后再永久删除")

    await forum_service.purge_post(db, post)
    return {"message": "已永久删除"}


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
    _ = await forum_service.apply_content_filter_config_from_db(db)

    # 敏感词检测
    passed, error_msg = check_comment_content(comment_data.content)
    if not passed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    post = await forum_service.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

    if comment_data.parent_id is not None:
        parent = await forum_service.get_comment(db, comment_data.parent_id)
        if not parent or parent.post_id != post_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="父评论不存在")
    
    comment = await forum_service.create_comment(db, post_id, current_user.id, comment_data)
    if getattr(comment, "review_status", None) == "pending":
        content_lines: list[str] = [f"帖子ID：{int(post_id)}"]
        if getattr(comment, "review_reason", None):
            content_lines.append(f"原因：{comment.review_reason}")
        _create_notification(
            db,
            user_id=int(comment.user_id),
            title="你的评论已提交审核",
            content="\n".join(content_lines) if content_lines else None,
            link=f"/forum/post/{int(post_id)}?commentId={int(comment.id)}#comment-{int(comment.id)}",
            related_post_id=int(post_id),
            related_comment_id=int(comment.id),
        )
        await db.commit()
    return await _build_comment_response(db, comment, current_user.id)


@router.get("/posts/{post_id}/comments", response_model=CommentListResponse, summary="获取评论列表")
async def get_comments(
    post_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    include_unapproved: Annotated[bool, Query()] = False,
):
    """获取帖子的评论列表"""
    post = await forum_service.get_post(db, post_id)
    if not post and current_user is not None:
        post_any = await forum_service.get_post_any(db, post_id)
        if post_any and not post_any.is_deleted:
            from ..utils.permissions import is_owner_or_admin

            if is_owner_or_admin(current_user, post_any.user_id):
                post = post_any

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

    user_id = current_user.id if current_user else None
    viewer_role = current_user.role if current_user else None

    comments, total = await forum_service.get_comments_visible(
        db,
        post_id,
        page,
        page_size,
        viewer_user_id=user_id,
        viewer_role=viewer_role,
        include_unapproved=bool(include_unapproved),
    )

    items = [await _build_comment_response(db, c, user_id) for c in comments]
    
    return CommentListResponse(items=items, total=total)


@router.delete("/comments/{comment_id}", summary="删除评论")
async def delete_comment(
    comment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """删除评论（仅作者、版主或管理员可操作）"""
    from ..utils.permissions import is_owner_or_admin
    
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


@router.post("/comments/{comment_id}/restore", summary="恢复评论")
async def restore_comment(
    comment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """恢复评论（撤销删除，仅作者、版主或管理员可操作）"""
    from ..utils.permissions import is_owner_or_admin

    comment = await forum_service.get_comment_any(db, comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")

    if not is_owner_or_admin(current_user, comment.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有作者、版主或管理员可以恢复评论",
        )

    _ = await forum_service.restore_comment(db, comment)
    return {"message": "已恢复"}


@router.post("/comments/{comment_id}/like", response_model=LikeResponse, summary="点赞/取消点赞评论")
async def toggle_comment_like(
    comment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    comment = await forum_service.get_comment(db, comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")

    liked, like_count = await forum_service.toggle_comment_like(db, comment_id, current_user.id)
    message = "点赞成功" if liked else "取消点赞"
    return LikeResponse(liked=liked, like_count=like_count, message=message)


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
    
    # 解析图片和附件
    images: list[str] = []
    if post.images:
        try:
            raw_images: object = cast(object, json.loads(post.images))
            if isinstance(raw_images, list):
                images = []
                for elem in cast(list[object], raw_images):
                    if elem is None:
                        continue
                    if isinstance(elem, str):
                        if elem:
                            images.append(elem)
                        continue
                    images.append(str(elem))
            else:
                images = []
        except (json.JSONDecodeError, TypeError):
            images = []

    attachments: list[dict[str, str]] = []
    if post.attachments:
        try:
            raw_attachments: object = cast(object, json.loads(post.attachments))
            if isinstance(raw_attachments, list):
                normalized: list[dict[str, str]] = []
                for item in cast(list[object], raw_attachments):
                    if not isinstance(item, dict):
                        continue
                    item_dict = cast(dict[object, object], item)
                    name = item_dict.get("name")
                    url = item_dict.get("url")
                    if not isinstance(name, str) or not isinstance(url, str) or not name or not url:
                        continue
                    normalized.append({"name": name, "url": url})
                attachments = normalized
            else:
                attachments = []
        except (json.JSONDecodeError, TypeError):
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
        is_deleted=bool(getattr(post, "is_deleted", False)),
        heat_score=float(post.heat_score or 0.0),
        cover_image=post.cover_image,
        images=images,
        attachments=attachments,
        reactions=reactions,
        created_at=post.created_at,
        updated_at=post.updated_at or post.created_at,
        review_status=getattr(post, "review_status", None),
        review_reason=getattr(post, "review_reason", None),
        reviewed_at=getattr(post, "reviewed_at", None),
        author=author_info,
        is_liked=is_liked,
        is_favorited=is_favorited
    )


async def _build_comment_response(db: AsyncSession, comment: Comment, user_id: int | None) -> CommentResponse:
    """构建评论响应"""
    _ = db
    is_liked = False
    if user_id:
        is_liked = await forum_service.is_comment_liked(db, comment.id, user_id)
    author_info = None
    if comment.author:
        author_info = AuthorInfo(
            id=comment.author.id,
            username=comment.author.username,
            nickname=comment.author.nickname,
            avatar=comment.author.avatar
        )
    
    images: list[str] = []
    comment_images = comment.images
    if isinstance(comment_images, str) and comment_images:
        try:
            raw_comment_images: object = cast(object, json.loads(comment_images))
            if isinstance(raw_comment_images, list):
                images = [str(x) for x in cast(list[object], raw_comment_images) if x]
        except (json.JSONDecodeError, TypeError):
            images = []

    replies: list[CommentResponse] = []
    for child in comment.replies:
        if child.is_deleted:
            continue
        replies.append(await _build_comment_response(db, child, user_id))

    return CommentResponse(
        id=comment.id,
        content=comment.content,
        post_id=comment.post_id,
        user_id=comment.user_id,
        parent_id=comment.parent_id,
        like_count=int(comment.like_count or 0),
        images=images,
        created_at=comment.created_at,
        review_status=getattr(comment, "review_status", None),
        review_reason=getattr(comment, "review_reason", None),
        reviewed_at=getattr(comment, "reviewed_at", None),
        author=author_info,
        is_liked=is_liked,
        replies=replies,
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
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取论坛统计数据（管理员）"""
    stats = await forum_service.get_forum_stats(db)
    return stats


@router.get("/admin/posts", response_model=PostListResponse, summary="管理员获取帖子列表")
async def admin_get_posts(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
    deleted: bool = False,
    is_essence: Annotated[bool | None, Query(description="是否仅精华帖")] = None,
):
    """管理员获取帖子列表"""
    posts, total = await forum_service.get_posts(
        db,
        page,
        page_size,
        category,
        keyword,
        is_essence=is_essence,
        include_deleted=True,
        deleted=deleted,
        approved_only=False,
    )
    items = [await _build_post_response(db, post, current_user.id) for post in posts]
    
    return PostListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/posts/batch/delete", summary="批量删除帖子")
async def batch_delete_posts(
    payload: PostIdListRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..utils.permissions import is_owner_or_admin

    success_ids: list[int] = []
    failed: list[dict[str, object]] = []

    for post_id in payload.ids:
        post = await forum_service.get_post_any(db, int(post_id))
        if not post:
            failed.append({"id": int(post_id), "reason": "帖子不存在"})
            continue
        if not is_owner_or_admin(current_user, post.user_id):
            failed.append({"id": int(post_id), "reason": "无权限"})
            continue
        if post.is_deleted:
            failed.append({"id": int(post_id), "reason": "帖子已删除"})
            continue
        await forum_service.delete_post(db, post)
        success_ids.append(int(post_id))

    return {"success_ids": success_ids, "failed": failed}


@router.post("/admin/posts/{post_id}/pin", summary="设置置顶")
async def admin_toggle_pin(
    post_id: int,
    pin_data: PinPostRequest,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """设置帖子置顶状态"""
    success = await forum_service.set_post_pinned(db, post_id, pin_data.is_pinned)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    return {"message": "置顶成功" if pin_data.is_pinned else "取消置顶成功"}


@router.post("/admin/posts/{post_id}/hot", summary="设置热门")
async def admin_toggle_hot(
    post_id: int,
    hot_data: HotPostRequest,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """设置帖子热门状态"""
    success = await forum_service.set_post_hot(db, post_id, hot_data.is_hot)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    return {"message": "设为热门成功" if hot_data.is_hot else "取消热门成功"}


@router.post("/admin/posts/{post_id}/essence", summary="设置精华")
async def admin_toggle_essence(
    post_id: int,
    essence_data: EssencePostRequest,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """设置帖子精华状态"""
    success = await forum_service.set_post_essence(db, post_id, essence_data.is_essence)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
    
    return {"message": "设为精华成功" if essence_data.is_essence else "取消精华成功"}


@router.post("/admin/update-heat-scores", summary="更新所有帖子热度")
async def admin_update_heat_scores(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """批量更新所有帖子的热度分数"""
    updated = await forum_service.update_heat_scores(db)
    return {"message": f"已更新 {updated} 个帖子的热度分数", "updated_count": updated}


# ============ 内容审核 ============


class ReviewAction(BaseModel):
    action: str  # approve / reject / delete
    reason: str | None = None


class SensitiveWordRequest(BaseModel):
    word: str


class PendingCommentItem(TypedDict):
    id: int
    content: str
    user_id: int
    username: str | None
    post_id: int
    post_title: str | None
    created_at: datetime


class PendingPostItem(TypedDict):
    id: int
    title: str
    user_id: int
    username: str | None
    category: str | None
    created_at: datetime
    review_reason: str | None


@router.get("/admin/pending-comments", summary="获取待审核评论")
async def get_pending_comments(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """获取待审核的评论列表"""
    base_filter = and_(
        Comment.is_deleted == False,
        Comment.review_status == "pending",
    )

    total_result = await db.execute(select(func.count(Comment.id)).where(base_filter))
    total = total_result.scalar() or 0

    query = (
        select(
            Comment.id,
            Comment.content,
            Comment.user_id,
            User.username,
            Comment.post_id,
            Post.title.label("post_title"),
            Comment.created_at,
        )
        .select_from(Comment)
        .outerjoin(User, User.id == Comment.user_id)
        .outerjoin(Post, Post.id == Comment.post_id)
        .where(base_filter)
        .order_by(Comment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    rows = result.all()

    items: list[PendingCommentItem] = []
    for row in rows:
        row_id = cast(int, row.id)
        row_content = cast(str, row.content)
        row_user_id = cast(int, row.user_id)
        row_username = cast(str | None, row.username)
        row_post_id = cast(int, row.post_id)
        row_post_title = cast(str | None, row.post_title)
        row_created_at = cast(datetime, row.created_at)
        items.append(
            {
                "id": int(row_id),
                "content": str(row_content),
                "user_id": int(row_user_id),
                "username": row_username,
                "post_id": int(row_post_id),
                "post_title": row_post_title,
                "created_at": row_created_at,
            }
        )
    
    return {"items": items, "total": int(total)}


@router.get("/admin/pending-posts", summary="获取待审核帖子")
async def get_pending_posts(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    base_filter = and_(
        Post.is_deleted == False,
        Post.review_status == "pending",
    )

    total_result = await db.execute(select(func.count(Post.id)).where(base_filter))
    total = total_result.scalar() or 0

    query = (
        select(
            Post.id,
            Post.title,
            Post.user_id,
            User.username,
            Post.category,
            Post.created_at,
            Post.review_reason,
        )
        .select_from(Post)
        .outerjoin(User, User.id == Post.user_id)
        .where(base_filter)
        .order_by(Post.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    rows = result.all()

    items: list[PendingPostItem] = []
    for row in rows:
        row_id = cast(int, row.id)
        row_title = cast(str, row.title)
        row_user_id = cast(int, row.user_id)
        row_username = cast(str | None, row.username)
        row_category = cast(str | None, row.category)
        row_created_at = cast(datetime, row.created_at)
        row_reason = cast(str | None, row.review_reason)
        items.append(
            {
                "id": int(row_id),
                "title": str(row_title),
                "user_id": int(row_user_id),
                "username": row_username,
                "category": row_category,
                "created_at": row_created_at,
                "review_reason": row_reason,
            }
        )

    return {"items": items, "total": int(total)}


@router.post("/admin/posts/{post_id}/review", summary="审核帖子")
async def review_post(
    post_id: int,
    data: ReviewAction,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    result = await db.execute(
        select(Post).where(and_(Post.id == post_id, Post.is_deleted == False))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    now = datetime.now(timezone.utc)

    if data.action == "delete":
        post.is_deleted = True
        post.review_status = "rejected"
        post.review_reason = data.reason
        post.reviewed_at = now

        await _log_forum_admin_action(
            db,
            user_id=current_user.id,
            action=LogAction.DELETE,
            module="forum",
            target_id=post.id,
            target_type="post",
            description="审核删除帖子",
            extra_data={"action": "delete", "reason": data.reason},
            request=request,
        )

        content_lines = [f"标题：{post.title}"]
        if data.reason:
            content_lines.append(f"原因：{data.reason}")
        _create_notification(
            db,
            user_id=int(post.user_id),
            title="你的帖子已被删除",
            content="\n".join(content_lines) if content_lines else None,
            link=f"/forum/post/{int(post.id)}?deleted=1",
            related_post_id=int(post.id),
        )
        await db.commit()
        return {"message": "帖子已删除"}

    if data.action == "approve":
        post.review_status = "approved"
        post.review_reason = data.reason
        post.reviewed_at = now

        await _log_forum_admin_action(
            db,
            user_id=current_user.id,
            action=LogAction.UPDATE,
            module="forum",
            target_id=post.id,
            target_type="post",
            description="审核通过帖子",
            extra_data={"action": "approve", "reason": data.reason},
            request=request,
        )

        content_lines = [f"标题：{post.title}"]
        if data.reason:
            content_lines.append(f"原因：{data.reason}")
        _create_notification(
            db,
            user_id=int(post.user_id),
            title="你的帖子已通过审核",
            content="\n".join(content_lines) if content_lines else None,
            link=f"/forum/post/{int(post.id)}",
            related_post_id=int(post.id),
        )
        await db.commit()
        return {"message": "帖子已通过审核"}

    if data.action == "reject":
        post.review_status = "rejected"
        post.review_reason = data.reason
        post.reviewed_at = now

        await _log_forum_admin_action(
            db,
            user_id=current_user.id,
            action=LogAction.UPDATE,
            module="forum",
            target_id=post.id,
            target_type="post",
            description="审核驳回帖子",
            extra_data={"action": "reject", "reason": data.reason},
            request=request,
        )

        content_lines = [f"标题：{post.title}"]
        if data.reason:
            content_lines.append(f"原因：{data.reason}")
        _create_notification(
            db,
            user_id=int(post.user_id),
            title="你的帖子未通过审核",
            content="\n".join(content_lines) if content_lines else None,
            link=f"/forum/post/{int(post.id)}",
            related_post_id=int(post.id),
        )
        await db.commit()
        return {"message": "帖子已驳回"}

    raise HTTPException(status_code=400, detail="无效操作")


@router.post("/admin/comments/{comment_id}/review", summary="审核评论")
async def review_comment(
    comment_id: int,
    data: ReviewAction,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """审核评论"""
    result = await db.execute(
        select(Comment).where(and_(Comment.id == comment_id, Comment.is_deleted == False))
    )
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    
    if data.action == "delete":
        if comment.review_status in (None, "approved"):
            _ = await db.execute(
                update(Post)
                .where(Post.id == comment.post_id)
                .values(
                    comment_count=case(
                        (
                            func.coalesce(Post.comment_count, 0) > 0,
                            func.coalesce(Post.comment_count, 0) - 1,
                        ),
                        else_=0,
                    )
                )
            )

        comment.is_deleted = True
        comment.review_status = "rejected"
        comment.review_reason = data.reason
        comment.reviewed_at = datetime.now(timezone.utc)

        await _log_forum_admin_action(
            db,
            user_id=current_user.id,
            action=LogAction.DELETE,
            module="forum",
            target_id=comment.id,
            target_type="comment",
            description="审核删除评论",
            extra_data={"action": "delete", "reason": data.reason, "post_id": comment.post_id},
            request=request,
        )

        content_lines = [f"评论ID：{int(comment.id)}", f"帖子ID：{int(comment.post_id)}"]
        if data.reason:
            content_lines.append(f"原因：{data.reason}")
        _create_notification(
            db,
            user_id=int(comment.user_id),
            title="你的评论已被删除",
            content="\n".join(content_lines) if content_lines else None,
            link=f"/forum/post/{int(comment.post_id)}?commentId={int(comment.id)}#comment-{int(comment.id)}",
            related_post_id=int(comment.post_id),
            related_comment_id=int(comment.id),
        )
        await db.commit()
        return {"message": "评论已删除"}

    if data.action == "approve":
        if comment.review_status == "pending":
            _ = await db.execute(
                update(Post)
                .where(Post.id == comment.post_id)
                .values(comment_count=func.coalesce(Post.comment_count, 0) + 1)
            )

        comment.review_status = "approved"
        comment.review_reason = data.reason
        comment.reviewed_at = datetime.now(timezone.utc)

        await _log_forum_admin_action(
            db,
            user_id=current_user.id,
            action=LogAction.UPDATE,
            module="forum",
            target_id=comment.id,
            target_type="comment",
            description="审核通过评论",
            extra_data={"action": "approve", "reason": data.reason, "post_id": comment.post_id},
            request=request,
        )

        content_lines = [f"评论ID：{int(comment.id)}", f"帖子ID：{int(comment.post_id)}"]
        if data.reason:
            content_lines.append(f"原因：{data.reason}")
        _create_notification(
            db,
            user_id=int(comment.user_id),
            title="你的评论已通过审核",
            content="\n".join(content_lines) if content_lines else None,
            link=f"/forum/post/{int(comment.post_id)}?commentId={int(comment.id)}#comment-{int(comment.id)}",
            related_post_id=int(comment.post_id),
            related_comment_id=int(comment.id),
        )
        await db.commit()
        return {"message": "评论已通过审核"}

    if data.action == "reject":
        if comment.review_status in (None, "approved"):
            _ = await db.execute(
                update(Post)
                .where(Post.id == comment.post_id)
                .values(
                    comment_count=case(
                        (
                            func.coalesce(Post.comment_count, 0) > 0,
                            func.coalesce(Post.comment_count, 0) - 1,
                        ),
                        else_=0,
                    )
                )
            )

        comment.review_status = "rejected"
        comment.review_reason = data.reason
        comment.reviewed_at = datetime.now(timezone.utc)
        comment.is_deleted = True

        await _log_forum_admin_action(
            db,
            user_id=current_user.id,
            action=LogAction.UPDATE,
            module="forum",
            target_id=comment.id,
            target_type="comment",
            description="审核驳回评论",
            extra_data={"action": "reject", "reason": data.reason, "post_id": comment.post_id},
            request=request,
        )

        content_lines = [f"评论ID：{int(comment.id)}", f"帖子ID：{int(comment.post_id)}"]
        if data.reason:
            content_lines.append(f"原因：{data.reason}")
        _create_notification(
            db,
            user_id=int(comment.user_id),
            title="你的评论未通过审核",
            content="\n".join(content_lines) if content_lines else None,
            link=f"/forum/post/{int(comment.post_id)}?commentId={int(comment.id)}#comment-{int(comment.id)}",
            related_post_id=int(comment.post_id),
            related_comment_id=int(comment.id),
        )
        await db.commit()
        return {"message": "评论已驳回并删除"}
    else:
        raise HTTPException(status_code=400, detail="无效操作")


@router.get("/admin/sensitive-words", summary="获取敏感词列表")
async def get_sensitive_words(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取所有敏感词"""
    config = await forum_service.apply_content_filter_config_from_db(db)
    return {
        "sensitive_words": cast(list[str], config.get("sensitive_words") or []),
        "ad_words": cast(list[str], config.get("ad_words") or []),
    }


@router.post("/admin/sensitive-words", summary="添加敏感词")
async def add_word(
    data: SensitiveWordRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """添加敏感词"""
    _ = await forum_service.add_sensitive_word(db, word=data.word, updated_by=current_user.id)

    await _log_forum_admin_action(
        db,
        user_id=current_user.id,
        action=LogAction.CREATE,
        module="forum",
        description="添加敏感词",
        extra_data={"word": data.word},
        request=request,
    )
    await db.commit()
    return {"message": f"已添加敏感词: {data.word}"}


@router.delete("/admin/sensitive-words/{word}", summary="删除敏感词")
async def delete_word(
    word: str,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """删除敏感词"""
    _ = await forum_service.remove_sensitive_word(db, word=word, updated_by=current_user.id)

    await _log_forum_admin_action(
        db,
        user_id=current_user.id,
        action=LogAction.DELETE,
        module="forum",
        description="删除敏感词",
        extra_data={"word": word},
        request=request,
    )
    await db.commit()
    return {"message": f"已删除敏感词: {word}"}


@router.post("/admin/ad-words", summary="添加广告词")
async def add_advertisement_word(
    data: SensitiveWordRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """添加广告词"""
    _ = await forum_service.add_ad_word(db, word=data.word, updated_by=current_user.id)

    await _log_forum_admin_action(
        db,
        user_id=current_user.id,
        action=LogAction.CREATE,
        module="forum",
        description="添加广告词",
        extra_data={"word": data.word},
        request=request,
    )
    await db.commit()
    return {"message": f"已添加广告词: {data.word}"}


@router.delete("/admin/ad-words/{word}", summary="删除广告词")
async def delete_advertisement_word(
    word: str,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """删除广告词"""
    _ = await forum_service.remove_ad_word(db, word=word, updated_by=current_user.id)

    await _log_forum_admin_action(
        db,
        user_id=current_user.id,
        action=LogAction.DELETE,
        module="forum",
        description="删除广告词",
        extra_data={"word": word},
        request=request,
    )
    await db.commit()
    return {"message": f"已删除广告词: {word}"}


class BatchReviewAction(BaseModel):
    ids: list[int]
    action: str
    reason: str | None = None


@router.post("/admin/posts/review/batch", summary="批量审核帖子")
async def batch_review_posts(
    data: BatchReviewAction,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    ids = [int(x) for x in (data.ids or []) if int(x) > 0]
    if not ids:
        raise HTTPException(status_code=400, detail="ids 不能为空")

    action = (data.action or "").strip().lower()
    if action not in ("approve", "reject", "delete"):
        raise HTTPException(status_code=400, detail="action 仅支持 approve / reject / delete")

    result = await db.execute(
        select(Post).where(and_(Post.id.in_(ids), Post.is_deleted == False))
    )
    posts = list(result.scalars().all())
    found_ids = {int(p.id) for p in posts}
    missing_ids = [int(i) for i in ids if int(i) not in found_ids]

    now = datetime.now(timezone.utc)
    processed: list[int] = []
    for post in posts:
        if action == "delete":
            post.is_deleted = True
            post.review_status = "rejected"
            post.review_reason = data.reason
            post.reviewed_at = now
        elif action == "approve":
            post.review_status = "approved"
            post.review_reason = data.reason
            post.reviewed_at = now
        elif action == "reject":
            post.review_status = "rejected"
            post.review_reason = data.reason
            post.reviewed_at = now
        processed.append(int(post.id))

    max_individual = 10
    title_single = (
        "你的帖子已通过审核"
        if action == "approve"
        else "你的帖子未通过审核"
        if action == "reject"
        else "你的帖子已被删除"
    )
    by_user: dict[int, list[Post]] = {}
    for post in posts:
        by_user.setdefault(int(post.user_id), []).append(post)

    notifications_created = 0
    for user_id, user_posts in by_user.items():
        if len(user_posts) <= max_individual:
            for post in user_posts:
                content_lines = [f"标题：{post.title}"]
                if data.reason:
                    content_lines.append(f"原因：{data.reason}")
                link = (
                    f"/forum/post/{int(post.id)}?deleted=1"
                    if action == "delete"
                    else f"/forum/post/{int(post.id)}"
                )
                _create_notification(
                    db,
                    user_id=int(user_id),
                    title=f"{title_single}（批量）",
                    content="\n".join(content_lines) if content_lines else None,
                    link=link,
                    related_post_id=int(post.id),
                )
                notifications_created += 1
        else:
            post_ids = [int(p.id) for p in user_posts]
            content_lines = [f"帖子ID：{', '.join(str(i) for i in post_ids)}"]
            if data.reason:
                content_lines.append(f"原因：{data.reason}")
            first = user_posts[0]
            link = (
                f"/forum/post/{int(first.id)}?deleted=1"
                if action == "delete"
                else f"/forum/post/{int(first.id)}"
            )
            _create_notification(
                db,
                user_id=int(user_id),
                title=f"{title_single}（批量）",
                content="\n".join(content_lines) if content_lines else None,
                link=link,
                related_post_id=int(first.id),
            )
            notifications_created += 1

    await _log_forum_admin_action(
        db,
        user_id=current_user.id,
        action=LogAction.UPDATE if action in ("approve", "reject") else LogAction.DELETE,
        module="forum",
        target_type="post",
        description="批量审核帖子",
        extra_data={"action": action, "ids": ids, "processed": processed, "missing": missing_ids, "reason": data.reason},
        request=request,
    )

    await db.commit()
    counts = {
        "requested": len(ids),
        "processed": len(processed),
        "missing": len(missing_ids),
        "notifications_created": int(notifications_created),
    }
    message = f"已处理 {counts['processed']} 条，缺失 {counts['missing']} 条"
    return {
        "processed": processed,
        "missing": missing_ids,
        "action": action,
        "reason": data.reason,
        "requested": ids,
        "counts": counts,
        "message": message,
    }


@router.post("/admin/comments/review/batch", summary="批量审核评论")
async def batch_review_comments(
    data: BatchReviewAction,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    ids = [int(x) for x in (data.ids or []) if int(x) > 0]
    if not ids:
        raise HTTPException(status_code=400, detail="ids 不能为空")

    action = (data.action or "").strip().lower()
    if action not in ("approve", "reject", "delete"):
        raise HTTPException(status_code=400, detail="action 仅支持 approve / reject / delete")

    result = await db.execute(
        select(Comment).where(and_(Comment.id.in_(ids), Comment.is_deleted == False))
    )
    comments = list(result.scalars().all())
    found_ids = {int(c.id) for c in comments}
    missing_ids = [int(i) for i in ids if int(i) not in found_ids]

    processed: list[int] = []
    now = datetime.now(timezone.utc)

    for comment in comments:
        if action == "delete":
            if comment.review_status in (None, "approved"):
                _ = await db.execute(
                    update(Post)
                    .where(Post.id == comment.post_id)
                    .values(
                        comment_count=case(
                            (
                                func.coalesce(Post.comment_count, 0) > 0,
                                func.coalesce(Post.comment_count, 0) - 1,
                            ),
                            else_=0,
                        )
                    )
                )

            comment.is_deleted = True
            comment.review_status = "rejected"
            comment.review_reason = data.reason
            comment.reviewed_at = now

        elif action == "approve":
            if comment.review_status == "pending":
                _ = await db.execute(
                    update(Post)
                    .where(Post.id == comment.post_id)
                    .values(comment_count=func.coalesce(Post.comment_count, 0) + 1)
                )

            comment.review_status = "approved"
            comment.review_reason = data.reason
            comment.reviewed_at = now

        elif action == "reject":
            if comment.review_status in (None, "approved"):
                _ = await db.execute(
                    update(Post)
                    .where(Post.id == comment.post_id)
                    .values(
                        comment_count=case(
                            (
                                func.coalesce(Post.comment_count, 0) > 0,
                                func.coalesce(Post.comment_count, 0) - 1,
                            ),
                            else_=0,
                        )
                    )
                )

            comment.review_status = "rejected"
            comment.review_reason = data.reason
            comment.reviewed_at = now
            comment.is_deleted = True

        processed.append(int(comment.id))

    max_individual = 10
    title_single = (
        "你的评论已通过审核"
        if action == "approve"
        else "你的评论未通过审核"
        if action == "reject"
        else "你的评论已被删除"
    )
    by_user: dict[int, list[Comment]] = {}
    for comment in comments:
        by_user.setdefault(int(comment.user_id), []).append(comment)

    notifications_created = 0
    for user_id, items in by_user.items():
        if len(items) <= max_individual:
            for comment in items:
                content_lines = [f"评论ID：{int(comment.id)}", f"帖子ID：{int(comment.post_id)}"]
                if data.reason:
                    content_lines.append(f"原因：{data.reason}")
                link = f"/forum/post/{int(comment.post_id)}?commentId={int(comment.id)}#comment-{int(comment.id)}"
                _create_notification(
                    db,
                    user_id=int(user_id),
                    title=f"{title_single}（批量）",
                    content="\n".join(content_lines) if content_lines else None,
                    link=link,
                    related_post_id=int(comment.post_id),
                    related_comment_id=int(comment.id),
                )
                notifications_created += 1
        else:
            comment_ids = [int(c.id) for c in items]
            content_lines = [f"评论ID：{', '.join(str(i) for i in comment_ids)}"]
            if data.reason:
                content_lines.append(f"原因：{data.reason}")
            first = items[0]
            link = f"/forum/post/{int(first.post_id)}?commentId={int(first.id)}#comment-{int(first.id)}"
            _create_notification(
                db,
                user_id=int(user_id),
                title=f"{title_single}（批量）",
                content="\n".join(content_lines) if content_lines else None,
                link=link,
                related_post_id=int(first.post_id),
                related_comment_id=int(first.id),
            )
            notifications_created += 1

    await _log_forum_admin_action(
        db,
        user_id=current_user.id,
        action=LogAction.UPDATE if action in ("approve", "reject") else LogAction.DELETE,
        module="forum",
        target_type="comment",
        description="批量审核评论",
        extra_data={"action": action, "ids": ids, "processed": processed, "missing": missing_ids, "reason": data.reason},
        request=request,
    )

    await db.commit()
    counts = {
        "requested": len(ids),
        "processed": len(processed),
        "missing": len(missing_ids),
        "notifications_created": int(notifications_created),
    }
    message = f"已处理 {counts['processed']} 条，缺失 {counts['missing']} 条"
    return {
        "processed": processed,
        "missing": missing_ids,
        "action": action,
        "reason": data.reason,
        "requested": ids,
        "counts": counts,
        "message": message,
    }


@router.get("/admin/content-stats", summary="内容审核统计")
async def get_content_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取内容审核统计数据"""
    config = await forum_service.apply_content_filter_config_from_db(db)

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
        "sensitive_words_count": len(cast(list[str], config.get("sensitive_words") or [])),
        "ad_words_count": len(cast(list[str], config.get("ad_words") or [])),
    }
