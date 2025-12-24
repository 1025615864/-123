"""新闻API路由"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from ..database import get_db
from ..models.news import News, NewsTopicItem
from ..models.user import User
from ..schemas.news import (
    NewsCreate, NewsUpdate, NewsResponse, NewsListResponse,
    NewsListItem, NewsCategoryCount, NewsFavoriteResponse,
    NewsAdminListResponse, NewsAdminListItem,
    NewsSubscriptionCreate, NewsSubscriptionResponse,
    NewsCommentCreate, NewsCommentResponse, NewsCommentListResponse,
    NewsTopicCreate, NewsTopicUpdate, NewsTopicResponse, NewsTopicListResponse,
    NewsTopicDetailResponse, NewsTopicItemCreate, NewsTopicItemBulkCreate, NewsTopicItemBulkResponse,
    NewsTopicItemBulkDelete, NewsTopicItemBulkDeleteResponse,
    NewsTopicItemsReindexResponse,
    NewsTopicItemsReorderRequest,
    NewsTopicAutoCacheRefreshResponse,
    NewsTopicImportRequest, NewsTopicImportResponse,
    NewsTopicReportResponse, NewsTopicReportItem,
    NewsTopicItemUpdate, NewsTopicItemBrief, NewsTopicAdminDetailResponse,
)
from ..services.news_service import news_service
from ..utils.deps import require_admin, get_current_user, get_current_user_optional
from ..utils.content_filter import check_comment_content

router = APIRouter(prefix="/news", tags=["新闻资讯"])


# ============ 公开接口 ============

@router.get("", response_model=NewsListResponse, summary="获取新闻列表")
async def get_news_list(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    """获取新闻列表，支持分类筛选和关键词搜索"""
    news_list, total = await news_service.get_list(
        db, page, page_size, category, keyword, published_only=True
    )

    ids = [int(n.id) for n in news_list]
    user_id = current_user.id if current_user else None
    fav_stats = await news_service.get_favorite_stats(db, ids, int(user_id) if user_id is not None else None)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        items.append(item)
    return NewsListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/topics", response_model=NewsTopicListResponse, summary="获取新闻专题列表")
async def list_news_topics(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topics = await news_service.list_topics(db, active_only=True)
    items = [NewsTopicResponse.model_validate(t) for t in topics]
    return NewsTopicListResponse(items=items)


@router.get("/topics/{topic_id}", response_model=NewsTopicDetailResponse, summary="获取专题详情")
async def get_news_topic_detail(
    topic_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic or not bool(getattr(topic, "is_active", True)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")

    news_list, total = await news_service.get_topic_news(db, topic_id, page=page, page_size=page_size, published_only=True)

    ids = [int(n.id) for n in news_list]
    user_id = current_user.id if current_user else None
    fav_stats = await news_service.get_favorite_stats(db, ids, int(user_id) if user_id is not None else None)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        items.append(item)

    return NewsTopicDetailResponse(
        topic=NewsTopicResponse.model_validate(topic),
        items=items,
        total=int(total),
        page=int(page),
        page_size=int(page_size),
    )


@router.get("/recommended", response_model=NewsListResponse, summary="获取推荐新闻")
async def get_recommended_news(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    user_id = current_user.id if current_user else None
    news_list, total = await news_service.get_recommended_news(
        db,
        user_id,
        page=page,
        page_size=page_size,
        category=category,
        keyword=keyword,
    )

    ids = [int(n.id) for n in news_list]
    fav_stats = await news_service.get_favorite_stats(db, ids, int(user_id) if user_id is not None else None)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        items.append(item)

    return NewsListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/subscriptions", response_model=list[NewsSubscriptionResponse], summary="获取我的新闻订阅")
async def get_my_news_subscriptions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    subs = await news_service.list_subscriptions(db, current_user.id)
    return [NewsSubscriptionResponse.model_validate(s) for s in subs]


@router.post("/subscriptions", response_model=NewsSubscriptionResponse, summary="创建新闻订阅")
async def create_news_subscription(
    data: NewsSubscriptionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sub_type = (data.sub_type or "").strip().lower()
    value = (data.value or "").strip()
    if sub_type not in {"category", "keyword"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的订阅类型")
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="订阅值不能为空")
    sub = await news_service.create_subscription(db, current_user.id, sub_type, value)
    return NewsSubscriptionResponse.model_validate(sub)


@router.delete("/subscriptions/{sub_id}", summary="删除新闻订阅")
async def delete_news_subscription(
    sub_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ok = await news_service.delete_subscription(db, current_user.id, sub_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订阅不存在")
    return {"message": "删除成功"}


@router.get("/subscribed", response_model=NewsListResponse, summary="获取我的订阅新闻")
async def get_my_subscribed_news(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    news_list, total = await news_service.get_subscribed_news(
        db, current_user.id, page, page_size, category, keyword
    )

    ids = [int(n.id) for n in news_list]
    fav_stats = await news_service.get_favorite_stats(db, ids, int(current_user.id))

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        items.append(item)

    return NewsListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/hot", response_model=list[NewsListItem], summary="获取热门新闻")
async def get_hot_news(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    days: Annotated[int, Query(ge=1, le=365)] = 7,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    category: str | None = None,
):
    news_list = await news_service.get_hot_news(db, days=days, limit=limit, category=category)

    ids = [int(n.id) for n in news_list]
    user_id = current_user.id if current_user else None
    fav_stats = await news_service.get_favorite_stats(db, ids, int(user_id) if user_id is not None else None)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        items.append(item)

    return items


@router.get("/history", response_model=NewsListResponse, summary="获取最近浏览新闻")
async def get_my_news_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    news_list, total = await news_service.get_user_history(db, current_user.id, page, page_size, category, keyword)

    ids = [int(n.id) for n in news_list]
    fav_stats = await news_service.get_favorite_stats(db, ids, int(current_user.id))

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        items.append(item)

    return NewsListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/top", response_model=list[NewsListItem], summary="获取置顶新闻")
async def get_top_news(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
):
    """获取置顶新闻"""
    news_list = await news_service.get_top_news(db, limit)

    ids = [int(n.id) for n in news_list]
    user_id = current_user.id if current_user else None
    fav_stats = await news_service.get_favorite_stats(db, ids, int(user_id) if user_id is not None else None)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        items.append(item)

    return items


@router.get("/recent", response_model=list[NewsListItem], summary="获取最新新闻")
async def get_recent_news(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    """获取最新新闻"""
    news_list = await news_service.get_recent_news(db, limit)

    ids = [int(n.id) for n in news_list]
    user_id = current_user.id if current_user else None
    fav_stats = await news_service.get_favorite_stats(db, ids, int(user_id) if user_id is not None else None)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        items.append(item)

    return items


@router.get("/categories", response_model=list[NewsCategoryCount], summary="获取分类列表")
async def get_categories(db: Annotated[AsyncSession, Depends(get_db)]):
    """获取新闻分类及数量"""
    categories = await news_service.get_categories(db)
    return [
        NewsCategoryCount(
            category=str(cat.get("category", "")),
            count=int(str(cat.get("count", 0) or 0)),
        )
        for cat in categories
    ]


@router.get("/admin/topics", response_model=NewsTopicListResponse, summary="管理员获取专题列表")
async def admin_list_news_topics(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topics = await news_service.list_topics(db, active_only=False)
    items = [NewsTopicResponse.model_validate(t) for t in topics]
    return NewsTopicListResponse(items=items)


@router.post("/admin/topics", response_model=NewsTopicResponse, summary="管理员创建专题")
async def admin_create_news_topic(
    data: NewsTopicCreate,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.create_topic(db, data.model_dump())
    return NewsTopicResponse.model_validate(topic)


@router.put("/admin/topics/{topic_id}", response_model=NewsTopicResponse, summary="管理员更新专题")
async def admin_update_news_topic(
    topic_id: int,
    data: NewsTopicUpdate,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")
    updated = await news_service.update_topic(db, topic, data.model_dump(exclude_unset=True))
    return NewsTopicResponse.model_validate(updated)


@router.delete("/admin/topics/{topic_id}", summary="管理员删除专题")
async def admin_delete_news_topic(
    topic_id: int,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")
    await news_service.delete_topic(db, topic_id)
    return {"message": "删除成功"}


@router.get("/admin/topics/{topic_id}", response_model=NewsTopicAdminDetailResponse, summary="管理员获取专题详情")
async def admin_get_news_topic(
    topic_id: int,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")
    rows = await news_service.list_topic_items_brief(db, topic_id)
    items: list[NewsTopicItemBrief] = []
    for item_id, news_id, position, title, category in rows:
        items.append(
            NewsTopicItemBrief(
                id=int(item_id),
                news_id=int(news_id),
                position=int(position),
                title=str(title or ""),
                category=str(category or ""),
            )
        )
    return NewsTopicAdminDetailResponse(topic=NewsTopicResponse.model_validate(topic), items=items)


@router.post("/admin/topics/{topic_id}/items", summary="管理员添加专题新闻")
async def admin_add_news_topic_item(
    topic_id: int,
    data: NewsTopicItemCreate,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")
    news = await news_service.get_by_id(db, int(data.news_id))
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")
    item = await news_service.add_topic_item(db, topic_id, int(data.news_id), data.position)
    return {"id": int(item.id), "message": "添加成功"}


@router.post(
    "/admin/topics/{topic_id}/items/bulk",
    response_model=NewsTopicItemBulkResponse,
    summary="管理员批量添加专题新闻",
)
async def admin_add_news_topic_items_bulk(
    topic_id: int,
    data: NewsTopicItemBulkCreate,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")

    ids = [int(i) for i in (data.news_ids or []) if int(i) > 0]
    if not ids:
        return NewsTopicItemBulkResponse(requested=0, added=0, skipped=0)

    exist_result = await db.execute(select(News.id).where(News.id.in_(ids)))
    exist_ids = {int(row[0]) for row in exist_result.all()}
    missing = [i for i in ids if i not in exist_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"新闻不存在: {','.join(str(i) for i in missing[:20])}",
        )

    requested, added, skipped = await news_service.add_topic_items_bulk(
        db, topic_id, ids, data.position_start
    )
    return NewsTopicItemBulkResponse(requested=requested, added=added, skipped=skipped)


@router.post(
    "/admin/topics/{topic_id}/items/bulk-delete",
    response_model=NewsTopicItemBulkDeleteResponse,
    summary="管理员批量移除专题新闻条目",
)
async def admin_delete_news_topic_items_bulk(
    topic_id: int,
    data: NewsTopicItemBulkDelete,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")

    ids = [int(i) for i in (data.item_ids or []) if int(i) > 0]
    if not ids:
        return NewsTopicItemBulkDeleteResponse(requested=0, deleted=0, skipped=0)

    requested, deleted, skipped = await news_service.remove_topic_items_bulk(db, topic_id, ids)
    return NewsTopicItemBulkDeleteResponse(requested=requested, deleted=deleted, skipped=skipped)


@router.post(
    "/admin/topics/{topic_id}/items/reindex",
    response_model=NewsTopicItemsReindexResponse,
    summary="管理员一键重排专题条目顺序",
)
async def admin_reindex_news_topic_items(
    topic_id: int,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")

    updated = await news_service.reindex_topic_items(db, topic_id)
    return NewsTopicItemsReindexResponse(updated=int(updated))


@router.post(
    "/admin/topics/{topic_id}/items/reorder",
    response_model=NewsTopicItemsReindexResponse,
    summary="管理员拖拽排序专题条目",
)
async def admin_reorder_news_topic_items(
    topic_id: int,
    data: NewsTopicItemsReorderRequest,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")

    updated = await news_service.reorder_topic_items(db, topic_id, data.item_ids)
    if not updated and (data.item_ids or []):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="条目列表不完整或不匹配")
    return NewsTopicItemsReindexResponse(updated=int(updated))


@router.post(
    "/admin/topics/{topic_id}/auto-cache/refresh",
    response_model=NewsTopicAutoCacheRefreshResponse,
    summary="管理员刷新专题自动收录缓存",
)
async def admin_refresh_topic_auto_cache(
    topic_id: int,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")
    cached = await news_service.refresh_topic_auto_cache(db, topic_id, published_only=True)
    return NewsTopicAutoCacheRefreshResponse(cached=int(cached))


@router.post(
    "/admin/topics/{topic_id}/import",
    response_model=NewsTopicImportResponse,
    summary="管理员按条件导入新闻到专题",
)
async def admin_import_news_to_topic(
    topic_id: int,
    data: NewsTopicImportRequest,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await news_service.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专题不存在")

    conditions = []

    existing_news_ids_subq = select(NewsTopicItem.news_id).where(NewsTopicItem.topic_id == int(topic_id))
    conditions.append(~News.id.in_(existing_news_ids_subq))
    if not bool(getattr(data, "include_unpublished", False)):
        conditions.append(News.is_published == True)

    if data.category:
        conditions.append(News.category == str(data.category))

    if data.keyword:
        pattern = f"%{str(data.keyword)}%"
        conditions.append(
            or_(
                News.title.ilike(pattern),
                News.summary.ilike(pattern),
                News.content.ilike(pattern),
                News.source.ilike(pattern),
                News.author.ilike(pattern),
            )
        )

    where_clause = and_(*conditions) if conditions else True
    limit = min(500, int(getattr(data, "limit", 50) or 50))
    q = (
        select(News.id)
        .where(where_clause)
        .order_by(desc(News.published_at), desc(News.created_at))
        .limit(int(limit))
    )
    res = await db.execute(q)
    ids = [int(r[0]) for r in res.all()]

    requested, added, skipped = await news_service.add_topic_items_bulk(
        db, topic_id, ids, getattr(data, "position_start", None)
    )
    return NewsTopicImportResponse(requested=requested, added=added, skipped=skipped)


@router.get(
    "/admin/topics/report",
    response_model=NewsTopicReportResponse,
    summary="管理员获取专题数据报表",
)
async def admin_get_topics_report(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = await news_service.get_topics_report(db)
    items: list[NewsTopicReportItem] = []
    for topic_id, title, is_active, sort_order, item_count, view_sum, fav_sum in rows:
        denom = int(view_sum or 0)
        conv = (float(fav_sum or 0) / float(denom)) if denom > 0 else 0.0
        items.append(
            NewsTopicReportItem(
                id=int(topic_id),
                title=str(title or ""),
                is_active=bool(is_active),
                sort_order=int(sort_order or 0),
                manual_item_count=int(item_count or 0),
                manual_view_count=int(view_sum or 0),
                manual_favorite_count=int(fav_sum or 0),
                manual_conversion_rate=float(conv),
            )
        )
    return NewsTopicReportResponse(items=items)


@router.put("/admin/topics/{topic_id}/items/{item_id}", summary="管理员更新专题新闻顺序")
async def admin_update_news_topic_item(
    topic_id: int,
    item_id: int,
    data: NewsTopicItemUpdate,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ok = await news_service.update_topic_item_position(db, topic_id, item_id, int(data.position))
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    return {"message": "更新成功"}


@router.delete("/admin/topics/{topic_id}/items/{item_id}", summary="管理员移除专题新闻")
async def admin_delete_news_topic_item(
    topic_id: int,
    item_id: int,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ok = await news_service.remove_topic_item(db, topic_id, item_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    return {"message": "移除成功"}


@router.get("/favorites", response_model=NewsListResponse, summary="获取我的新闻收藏")
async def get_my_news_favorites(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    news_list, total = await news_service.get_user_favorites(db, current_user.id, page, page_size, category, keyword)

    ids = [int(n.id) for n in news_list]
    fav_stats = await news_service.get_favorite_stats(db, ids, int(current_user.id))

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, _is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = True
        items.append(item)

    return NewsListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{news_id}/related", response_model=list[NewsListItem], summary="获取相关新闻")
async def get_related_news(
    news_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    limit: Annotated[int, Query(ge=1, le=20)] = 6,
):
    """获取相关新闻（同分类优先，不包含当前新闻）"""
    news_list = await news_service.get_related_news(db, news_id, limit)

    ids = [int(n.id) for n in news_list]
    user_id = current_user.id if current_user else None
    fav_stats = await news_service.get_favorite_stats(db, ids, int(user_id) if user_id is not None else None)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        items.append(item)

    return items


@router.get("/{news_id}", response_model=NewsResponse, summary="获取新闻详情")
async def get_news_detail(
    news_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
):
    """获取新闻详情，自动增加浏览量"""
    news = await news_service.get_published(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")
    
    await news_service.increment_view(db, news)
    await db.refresh(news)

    if current_user is not None:
        await news_service.record_view_history(db, news.id, current_user.id)

    user_id = current_user.id if current_user is not None else None
    fav_stats = await news_service.get_favorite_stats(db, [int(news.id)], int(user_id) if user_id is not None else None)
    fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
    resp = NewsResponse.model_validate(news)
    resp.favorite_count = int(fav_count)
    resp.is_favorited = bool(is_fav)
    return resp


@router.post("/{news_id}/favorite", response_model=NewsFavoriteResponse, summary="收藏/取消收藏新闻")
async def toggle_news_favorite(
    news_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    news = await news_service.get_published(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    favorited, favorite_count = await news_service.toggle_favorite(db, news_id, current_user.id)
    message = "收藏成功" if favorited else "取消收藏"
    return NewsFavoriteResponse(favorited=favorited, favorite_count=favorite_count, message=message)


@router.get("/{news_id}/comments", response_model=NewsCommentListResponse, summary="获取新闻评论")
async def get_news_comments(
    news_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    news = await news_service.get_published(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    comments, total = await news_service.get_comments(db, news_id, page, page_size)
    items = [NewsCommentResponse.model_validate(c) for c in comments]
    return NewsCommentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/{news_id}/comments", response_model=NewsCommentResponse, summary="发表评论")
async def create_news_comment(
    news_id: int,
    data: NewsCommentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    news = await news_service.get_published(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    passed, error_msg = check_comment_content(data.content)
    if not passed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    comment = await news_service.create_comment(db, news_id, current_user.id, data.content)
    comment = await news_service.get_comment(db, int(comment.id))
    if comment is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="评论创建失败")
    return NewsCommentResponse.model_validate(comment)


@router.delete("/comments/{comment_id}", summary="删除新闻评论")
async def delete_news_comment(
    comment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..utils.permissions import is_owner_or_admin

    comment = await news_service.get_comment(db, comment_id)
    if not comment or bool(getattr(comment, "is_deleted", False)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")

    if not is_owner_or_admin(current_user, int(comment.user_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有作者或管理员可以删除评论")

    await news_service.delete_comment(db, comment)
    return {"message": "删除成功"}


# ============ 管理接口（需要认证） ============

@router.post("", response_model=NewsResponse, summary="创建新闻")
async def create_news(
    news_data: NewsCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """创建新闻（需要管理员权限）"""
    _ = current_user
    news = await news_service.create(db, news_data)
    if news.is_published:
        _ = await news_service.notify_subscribers_on_publish(db, news)
    return NewsResponse.model_validate(news)


@router.put("/{news_id}", response_model=NewsResponse, summary="更新新闻")
async def update_news(
    news_id: int,
    news_data: NewsUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """更新新闻（需要管理员权限）"""
    _ = current_user
    news = await news_service.get_by_id(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    was_published = bool(news.is_published)
    updated_news = await news_service.update(db, news, news_data)
    if (not was_published) and bool(updated_news.is_published):
        _ = await news_service.notify_subscribers_on_publish(db, updated_news)
    return NewsResponse.model_validate(updated_news)


@router.delete("/{news_id}", summary="删除新闻")
async def delete_news(
    news_id: int,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """删除新闻（需要管理员权限）"""
    _ = current_user
    news = await news_service.get_by_id(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")
    
    await news_service.delete(db, news)
    return {"message": "删除成功"}


@router.get("/admin/all", response_model=NewsAdminListResponse, summary="获取所有新闻（含未发布）")
async def get_all_news(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
):
    """获取所有新闻，包括未发布的（需要管理员权限）"""
    _ = current_user
    news_list, total = await news_service.get_list(
        db, page, page_size, category, keyword, published_only=False
    )
    
    items = [NewsAdminListItem.model_validate(news) for news in news_list]
    return NewsAdminListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/admin/{news_id}", response_model=NewsResponse, summary="管理员获取新闻详情")
async def admin_get_news_detail(
    news_id: int,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """管理员获取新闻详情（包含未发布新闻，不增加浏览量）"""
    _ = current_user
    news = await news_service.get_by_id(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    return NewsResponse.model_validate(news)
