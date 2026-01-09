"""新闻API路由"""
from datetime import datetime
import json
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, delete, update
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from ..config import get_settings
from ..models.news import News, NewsComment, NewsTopicItem, NewsSource, NewsIngestRun
from ..models.news_ai import NewsAIAnnotation
from ..models.notification import Notification, NotificationType
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
    NewsCommentAdminItem, NewsCommentAdminListResponse, NewsCommentReviewAction,
    NewsReviewAction,
    NewsAIAnnotationResponse,
    NewsVersionItem, NewsVersionListResponse, NewsRollbackRequest,
    NewsAIGenerateRequest, NewsAIGenerationItem, NewsAIGenerationListResponse,
    NewsLinkCheckRequest, NewsLinkCheckItem, NewsLinkCheckResponse,
    NewsBatchActionRequest, NewsBatchActionResponse, NewsBatchQueryRequest,
    ScheduledNewsItem, ScheduledNewsListResponse,
    NewsSourceCreate, NewsSourceUpdate, NewsSourceResponse, NewsSourceListResponse,
    NewsIngestRunResponse, NewsIngestRunListResponse,
    NewsSourceHealthItem, NewsSourceHealthListResponse,
)
from ..services.news_service import news_service
from ..services.news_workbench_service import news_workbench_service
from ..services.rss_ingest_service import rss_ingest_service
from ..utils.deps import require_admin, get_current_user, get_current_user_optional
from ..utils.content_filter import check_comment_content, needs_review

router = APIRouter(prefix="/news", tags=["新闻资讯"])


def _coerce_int(value: object) -> int | None:
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if s and s.lstrip("-").isdigit():
            return int(s)
    return None


def _parse_dt_param(raw: str | None, *, field: str, end_of_day: bool = False) -> datetime | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if (
            end_of_day
            and len(s) == 10
            and s[4:5] == "-"
            and s[7:8] == "-"
            and dt.hour == 0
            and dt.minute == 0
            and dt.second == 0
            and dt.microsecond == 0
        ):
            return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return dt
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"invalid {field}")


async def _get_ai_risk_levels(db: AsyncSession, news_ids: list[int]) -> dict[int, str]:
    ids = [int(i) for i in news_ids]
    if not ids:
        return {}

    res = await db.execute(
        select(NewsAIAnnotation.news_id, NewsAIAnnotation.risk_level).where(
            NewsAIAnnotation.news_id.in_(ids)
        )
    )
    rows = cast(list[tuple[object, object]], list(res.all()))
    out: dict[int, str] = {}
    for news_id_obj, risk_level_obj in rows:
        nid = 0
        if isinstance(news_id_obj, int):
            nid = int(news_id_obj)
        elif isinstance(news_id_obj, float):
            nid = int(news_id_obj)
        elif isinstance(news_id_obj, str):
            s = news_id_obj.strip()
            if s.isdigit():
                nid = int(s)
        if nid <= 0:
            continue
        out[int(nid)] = str(risk_level_obj or "unknown")
    return out


async def _get_ai_keywords(db: AsyncSession, news_ids: list[int]) -> dict[int, list[str]]:
    ids = [int(i) for i in news_ids]
    if not ids:
        return {}

    res = await db.execute(
        select(NewsAIAnnotation.news_id, NewsAIAnnotation.keywords).where(
            NewsAIAnnotation.news_id.in_(ids)
        )
    )
    rows = cast(list[tuple[object, object]], list(res.all()))
    out: dict[int, list[str]] = {}
    for news_id_obj, raw in rows:
        nid = 0
        if isinstance(news_id_obj, int):
            nid = int(news_id_obj)
        elif isinstance(news_id_obj, float):
            nid = int(news_id_obj)
        elif isinstance(news_id_obj, str):
            s = news_id_obj.strip()
            if s.isdigit():
                nid = int(s)
        if nid <= 0:
            continue

        kws: list[str] = []
        try:
            if isinstance(raw, str) and raw.strip():
                parsed: object = cast(object, json.loads(raw))
                if isinstance(parsed, list):
                    for x in cast(list[object], parsed):
                        s = str(x or "").strip()
                        if s:
                            kws.append(s)
        except Exception:
            kws = []
        out[int(nid)] = kws
    return out


# ============ 公开接口 ============

@router.get("", response_model=NewsListResponse, summary="获取新闻列表")
async def get_news_list(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    keyword: str | None = None,
    risk_level: str | None = None,
    source_site: str | None = None,
    from_dt: Annotated[str | None, Query(alias="from")] = None,
    to_dt: Annotated[str | None, Query(alias="to")] = None,
):
    """获取新闻列表，支持分类筛选和关键词搜索"""
    parsed_from = _parse_dt_param(from_dt, field="from")
    parsed_to = _parse_dt_param(to_dt, field="to", end_of_day=True)
    news_list, total = await news_service.get_list(
        db,
        page,
        page_size,
        category,
        keyword,
        published_only=True,
        ai_risk_level=risk_level,
        source_site=source_site,
        from_dt=parsed_from,
        to_dt=parsed_to,
    )

    ids = [int(n.id) for n in news_list]
    user_id = current_user.id if current_user else None
    fav_stats = await news_service.get_favorite_stats(db, ids, int(user_id) if user_id is not None else None)
    risk_levels = await _get_ai_risk_levels(db, ids)
    keywords_map = await _get_ai_keywords(db, ids)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        item.ai_risk_level = risk_levels.get(int(news.id))
        item.ai_keywords = keywords_map.get(int(news.id), [])
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
    risk_levels = await _get_ai_risk_levels(db, ids)
    keywords_map = await _get_ai_keywords(db, ids)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        item.ai_risk_level = risk_levels.get(int(news.id))
        item.ai_keywords = keywords_map.get(int(news.id), [])
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
    risk_level: str | None = None,
    source_site: str | None = None,
    from_dt: Annotated[str | None, Query(alias="from")] = None,
    to_dt: Annotated[str | None, Query(alias="to")] = None,
):
    user_id = current_user.id if current_user else None
    parsed_from = _parse_dt_param(from_dt, field="from")
    parsed_to = _parse_dt_param(to_dt, field="to", end_of_day=True)
    news_list, total = await news_service.get_recommended_news(
        db,
        user_id,
        page=page,
        page_size=page_size,
        category=category,
        keyword=keyword,
        ai_risk_level=risk_level,
        source_site=source_site,
        from_dt=parsed_from,
        to_dt=parsed_to,
    )

    ids = [int(n.id) for n in news_list]
    fav_stats = await news_service.get_favorite_stats(db, ids, int(user_id) if user_id is not None else None)
    risk_levels = await _get_ai_risk_levels(db, ids)
    keywords_map = await _get_ai_keywords(db, ids)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        item.ai_risk_level = risk_levels.get(int(news.id))
        item.ai_keywords = keywords_map.get(int(news.id), [])
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
    risk_level: str | None = None,
    source_site: str | None = None,
    from_dt: Annotated[str | None, Query(alias="from")] = None,
    to_dt: Annotated[str | None, Query(alias="to")] = None,
):
    parsed_from = _parse_dt_param(from_dt, field="from")
    parsed_to = _parse_dt_param(to_dt, field="to", end_of_day=True)
    news_list, total = await news_service.get_subscribed_news(
        db,
        current_user.id,
        page,
        page_size,
        category,
        keyword,
        ai_risk_level=risk_level,
        source_site=source_site,
        from_dt=parsed_from,
        to_dt=parsed_to,
    )

    ids = [int(n.id) for n in news_list]
    fav_stats = await news_service.get_favorite_stats(db, ids, int(current_user.id))
    risk_levels = await _get_ai_risk_levels(db, ids)
    keywords_map = await _get_ai_keywords(db, ids)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        item.ai_risk_level = risk_levels.get(int(news.id))
        item.ai_keywords = keywords_map.get(int(news.id), [])
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
    risk_levels = await _get_ai_risk_levels(db, ids)
    keywords_map = await _get_ai_keywords(db, ids)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        item.ai_risk_level = risk_levels.get(int(news.id))
        item.ai_keywords = keywords_map.get(int(news.id), [])
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
    risk_level: str | None = None,
    source_site: str | None = None,
    from_dt: Annotated[str | None, Query(alias="from")] = None,
    to_dt: Annotated[str | None, Query(alias="to")] = None,
):
    parsed_from = _parse_dt_param(from_dt, field="from")
    parsed_to = _parse_dt_param(to_dt, field="to", end_of_day=True)
    news_list, total = await news_service.get_user_history(
        db,
        current_user.id,
        page,
        page_size,
        category,
        keyword,
        ai_risk_level=risk_level,
        source_site=source_site,
        from_dt=parsed_from,
        to_dt=parsed_to,
    )

    ids = [int(n.id) for n in news_list]
    fav_stats = await news_service.get_favorite_stats(db, ids, int(current_user.id))
    risk_levels = await _get_ai_risk_levels(db, ids)
    keywords_map = await _get_ai_keywords(db, ids)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        item.ai_risk_level = risk_levels.get(int(news.id))
        item.ai_keywords = keywords_map.get(int(news.id), [])
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
    risk_levels = await _get_ai_risk_levels(db, ids)
    keywords_map = await _get_ai_keywords(db, ids)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        item.ai_risk_level = risk_levels.get(int(news.id))
        item.ai_keywords = keywords_map.get(int(news.id), [])
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
    risk_levels = await _get_ai_risk_levels(db, ids)
    keywords_map = await _get_ai_keywords(db, ids)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        item.ai_risk_level = risk_levels.get(int(news.id))
        item.ai_keywords = keywords_map.get(int(news.id), [])
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


@router.get("/admin/sources", response_model=NewsSourceListResponse, summary="管理员获取采集来源列表")
async def admin_list_news_sources(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    res = await db.execute(select(NewsSource).order_by(NewsSource.id.asc()))
    rows = list(res.scalars().all())
    return NewsSourceListResponse(items=[NewsSourceResponse.model_validate(s) for s in rows])


@router.get(
    "/admin/sources/health",
    response_model=NewsSourceHealthListResponse,
    summary="管理员获取采集来源健康度",
)
async def admin_list_news_sources_health(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit_per_source: Annotated[int, Query(ge=1, le=200)] = 20,
):
    limit = max(1, min(200, int(limit_per_source)))

    src_res = await db.execute(select(NewsSource).order_by(NewsSource.id.asc()))
    sources = list(src_res.scalars().all())
    source_ids = [int(s.id) for s in sources if _coerce_int(getattr(s, "id", None)) is not None]
    if not source_ids:
        return NewsSourceHealthListResponse(limit_per_source=int(limit), items=[])

    rn = func.row_number().over(
        partition_by=NewsIngestRun.source_id,
        order_by=(desc(NewsIngestRun.created_at), desc(NewsIngestRun.id)),
    ).label("rn")

    runs_subq = (
        select(
            NewsIngestRun.source_id.label("source_id"),
            NewsIngestRun.status.label("status"),
            rn,
        )
        .where(NewsIngestRun.source_id.in_(source_ids))
        .subquery()
    )

    runs_res = await db.execute(
        select(runs_subq.c.source_id, runs_subq.c.status, runs_subq.c.rn).where(
            runs_subq.c.rn <= int(limit)
        )
    )
    rows = list(runs_res.all())

    grouped: dict[int, list[tuple[int, str]]] = {}
    for sid_obj, status_obj, rn_obj in rows:
        sid = _coerce_int(sid_obj)
        rni = _coerce_int(rn_obj)
        if sid is None or sid <= 0 or rni is None or rni <= 0:
            continue
        st = str(status_obj or "").strip().lower()
        grouped.setdefault(int(sid), []).append((int(rni), st))

    items: list[NewsSourceHealthItem] = []
    for s in sources:
        sid2 = _coerce_int(getattr(s, "id", None))
        if sid2 is None or sid2 <= 0:
            continue
        pairs = grouped.get(int(sid2), [])
        pairs.sort(key=lambda x: x[0])
        statuses = [p[1] for p in pairs]
        recent_total = int(len(statuses))
        recent_failed = int(sum(1 for x in statuses if x == "failed"))
        failure_rate = float(recent_failed / recent_total) if recent_total > 0 else 0.0
        last_status = statuses[0] if statuses else None

        items.append(
            NewsSourceHealthItem(
                source_id=int(sid2),
                recent_total=recent_total,
                recent_failed=recent_failed,
                failure_rate=float(failure_rate),
                last_status=last_status,
                last_run_at=getattr(s, "last_run_at", None),
                last_success_at=getattr(s, "last_success_at", None),
                last_error=getattr(s, "last_error", None),
                last_error_at=getattr(s, "last_error_at", None),
            )
        )

    return NewsSourceHealthListResponse(limit_per_source=int(limit), items=items)


@router.post("/admin/sources", response_model=NewsSourceResponse, summary="管理员创建采集来源")
async def admin_create_news_source(
    data: NewsSourceCreate,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    feed_url = str(getattr(data, "feed_url", "") or "").strip()
    if not feed_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="feed_url不能为空")

    src = NewsSource(
        name=str(getattr(data, "name", "") or "").strip() or feed_url,
        source_type="rss",
        feed_url=feed_url,
        site=str(getattr(data, "site", None) or "").strip() or None,
        category=str(getattr(data, "category", None) or "").strip().lower() or None,
        is_enabled=bool(getattr(data, "is_enabled", True)),
        fetch_timeout_seconds=getattr(data, "fetch_timeout_seconds", None),
        max_items_per_feed=getattr(data, "max_items_per_feed", None),
    )
    db.add(src)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="feed_url已存在")
    await db.refresh(src)
    return NewsSourceResponse.model_validate(src)


@router.put("/admin/sources/{source_id}", response_model=NewsSourceResponse, summary="管理员更新采集来源")
async def admin_update_news_source(
    source_id: int,
    data: NewsSourceUpdate,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    res = await db.execute(select(NewsSource).where(NewsSource.id == int(source_id)))
    src = res.scalar_one_or_none()
    if src is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="来源不存在")

    payload = data.model_dump(exclude_unset=True)
    if "name" in payload:
        src.name = str(payload.get("name") or "").strip() or src.name
    if "feed_url" in payload:
        fu = str(payload.get("feed_url") or "").strip()
        if not fu:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="feed_url不能为空")
        src.feed_url = fu
    if "site" in payload:
        src.site = str(payload.get("site") or "").strip() or None
    if "category" in payload:
        src.category = str(payload.get("category") or "").strip().lower() or None
    if "is_enabled" in payload:
        src.is_enabled = bool(payload.get("is_enabled"))
    if "fetch_timeout_seconds" in payload:
        src.fetch_timeout_seconds = payload.get("fetch_timeout_seconds")
    if "max_items_per_feed" in payload:
        src.max_items_per_feed = payload.get("max_items_per_feed")

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="feed_url已存在")
    await db.refresh(src)
    return NewsSourceResponse.model_validate(src)


@router.delete("/admin/sources/{source_id}", summary="管理员删除采集来源")
async def admin_delete_news_source(
    source_id: int,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    res = await db.execute(select(NewsSource).where(NewsSource.id == int(source_id)))
    src = res.scalar_one_or_none()
    if src is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="来源不存在")

    _ = await db.execute(delete(NewsIngestRun).where(NewsIngestRun.source_id == int(source_id)))
    await db.delete(src)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/admin/sources/{source_id}/ingest/run-once", summary="管理员手动触发单个来源采集")
async def admin_run_ingest_once(
    source_id: int,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    res = await db.execute(select(NewsSource.id).where(NewsSource.id == int(source_id)))
    exists = res.scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="来源不存在")

    stats = await rss_ingest_service.run_once(db, source_id=int(source_id))
    return {"message": "ok", **{k: int(v) for k, v in stats.items()}}


@router.get("/admin/ingest-runs", response_model=NewsIngestRunListResponse, summary="管理员获取采集运行记录")
async def admin_list_ingest_runs(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    source_id: int | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    from_dt: Annotated[str | None, Query(alias="from")] = None,
    to_dt: Annotated[str | None, Query(alias="to")] = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))

    conditions: list[ColumnElement[bool]] = []
    if source_id is not None:
        conditions.append(NewsIngestRun.source_id == int(source_id))
    if status_filter is not None and str(status_filter).strip():
        conditions.append(NewsIngestRun.status == str(status_filter).strip())

    if from_dt is not None and str(from_dt).strip():
        raw = str(from_dt).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except Exception:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid from")
        conditions.append(NewsIngestRun.created_at >= parsed)

    if to_dt is not None and str(to_dt).strip():
        raw = str(to_dt).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except Exception:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid to")
        conditions.append(NewsIngestRun.created_at <= parsed)

    where_clause = and_(*conditions) if conditions else None

    base = select(NewsIngestRun)
    if where_clause is not None:
        base = base.where(where_clause)

    total_q = select(func.count(NewsIngestRun.id))
    if where_clause is not None:
        total_q = total_q.where(where_clause)
    total_res = await db.execute(total_q)
    total = int(total_res.scalar() or 0)

    q = (
        base.order_by(desc(NewsIngestRun.created_at), desc(NewsIngestRun.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    res = await db.execute(q)
    runs = list(res.scalars().all())
    return NewsIngestRunListResponse(
        items=[NewsIngestRunResponse.model_validate(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/admin/topics", response_model=NewsTopicListResponse, summary="管理员获取专题列表")
async def admin_list_news_topics(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topics = await news_service.list_topics(db, active_only=False)
    items = [NewsTopicResponse.model_validate(t) for t in topics]
    return NewsTopicListResponse(items=items)


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

    raw_ids = cast(list[object], list(getattr(data, "news_ids", []) or []))
    ids: list[int] = []
    for x in raw_ids:
        nid = _coerce_int(x)
        if nid is None:
            continue
        if int(nid) > 0:
            ids.append(int(nid))
    if not ids:
        return NewsTopicItemBulkResponse(requested=0, added=0, skipped=0)

    exist_result = await db.execute(select(News.id).where(News.id.in_(ids)))
    exist_rows = cast(list[tuple[object]], list(exist_result.all()))
    exist_ids: set[int] = set()
    for row in exist_rows:
        nid = _coerce_int(row[0])
        if nid is None:
            continue
        exist_ids.add(int(nid))
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

    raw_ids = cast(list[object], list(getattr(data, "item_ids", []) or []))
    ids: list[int] = []
    for x in raw_ids:
        nid = _coerce_int(x)
        if nid is None:
            continue
        if int(nid) > 0:
            ids.append(int(nid))
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

    conditions: list[ColumnElement[bool]] = []

    existing_news_ids_subq = select(NewsTopicItem.news_id).where(NewsTopicItem.topic_id == int(topic_id))
    conditions.append(~News.id.in_(existing_news_ids_subq))
    if not bool(getattr(data, "include_unpublished", False)):
        conditions.append(News.is_published.is_(True))

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

    limit = min(500, int(getattr(data, "limit", 50) or 50))
    q = select(News.id)
    if conditions:
        q = q.where(and_(*conditions))
    q = q.order_by(desc(News.published_at), desc(News.created_at)).limit(int(limit))
    res = await db.execute(q)
    id_rows = cast(list[tuple[object]], list(res.all()))
    ids: list[int] = []
    for r in id_rows:
        nid = _coerce_int(r[0])
        if nid is None:
            continue
        if int(nid) > 0:
            ids.append(int(nid))

    requested, added, skipped = await news_service.add_topic_items_bulk(
        db, topic_id, ids, getattr(data, "position_start", None)
    )
    return NewsTopicImportResponse(requested=requested, added=added, skipped=skipped)


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
    risk_level: str | None = None,
    source_site: str | None = None,
    from_dt: Annotated[str | None, Query(alias="from")] = None,
    to_dt: Annotated[str | None, Query(alias="to")] = None,
):
    parsed_from = _parse_dt_param(from_dt, field="from")
    parsed_to = _parse_dt_param(to_dt, field="to", end_of_day=True)
    news_list, total = await news_service.get_user_favorites(
        db,
        current_user.id,
        page,
        page_size,
        category,
        keyword,
        ai_risk_level=risk_level,
        source_site=source_site,
        from_dt=parsed_from,
        to_dt=parsed_to,
    )

    ids = [int(n.id) for n in news_list]
    fav_stats = await news_service.get_favorite_stats(db, ids, int(current_user.id))
    risk_levels = await _get_ai_risk_levels(db, ids)
    keywords_map = await _get_ai_keywords(db, ids)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, _is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = True
        item.ai_risk_level = risk_levels.get(int(news.id))
        item.ai_keywords = keywords_map.get(int(news.id), [])
        items.append(item)

    return NewsListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{news_id:int}/related", response_model=list[NewsListItem], summary="获取相关新闻")
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
    risk_levels = await _get_ai_risk_levels(db, ids)
    keywords_map = await _get_ai_keywords(db, ids)

    items: list[NewsListItem] = []
    for news in news_list:
        item = NewsListItem.model_validate(news)
        fav_count, is_fav = fav_stats.get(int(news.id), (0, False))
        item.favorite_count = int(fav_count)
        item.is_favorited = bool(is_fav)
        item.ai_risk_level = risk_levels.get(int(news.id))
        item.ai_keywords = keywords_map.get(int(news.id), [])
        items.append(item)

    return items


@router.get("/{news_id:int}", response_model=NewsResponse, summary="获取新闻详情")
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

    ann_res = await db.execute(select(NewsAIAnnotation).where(NewsAIAnnotation.news_id == int(news.id)))
    ann = ann_res.scalar_one_or_none()
    if ann is not None:
        raw_words = str(getattr(ann, "sensitive_words", "") or "").strip()
        words = [w.strip() for w in raw_words.split(",") if w.strip()] if raw_words else []

        highlights: list[str] = []
        try:
            raw_hl = getattr(ann, "highlights", None)
            parsed_hl: object = cast(object, json.loads(raw_hl)) if isinstance(raw_hl, str) and raw_hl.strip() else []
            if isinstance(parsed_hl, list):
                for x in cast(list[object], parsed_hl):
                    s = str(x or "").strip()
                    if s:
                        highlights.append(s)
        except Exception:
            highlights = []

        keywords: list[str] = []
        try:
            raw_kw = getattr(ann, "keywords", None)
            parsed_kw: object = cast(object, json.loads(raw_kw)) if isinstance(raw_kw, str) and raw_kw.strip() else []
            if isinstance(parsed_kw, list):
                for x in cast(list[object], parsed_kw):
                    s = str(x or "").strip()
                    if s:
                        keywords.append(s)
        except Exception:
            keywords = []
        resp.ai_annotation = NewsAIAnnotationResponse(
            summary=getattr(ann, "summary", None),
            risk_level=str(getattr(ann, "risk_level", "unknown") or "unknown"),
            sensitive_words=words,
            highlights=highlights,
            keywords=keywords,
            duplicate_of_news_id=getattr(ann, "duplicate_of_news_id", None),
            processed_at=getattr(ann, "processed_at", None),
        )
    return resp


@router.post("/{news_id:int}/favorite", response_model=NewsFavoriteResponse, summary="收藏/取消收藏新闻")
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


@router.get("/{news_id:int}/comments", response_model=NewsCommentListResponse, summary="获取新闻评论")
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


@router.post("/{news_id:int}/comments", response_model=NewsCommentResponse, summary="发表评论")
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

    need_review, review_reason = needs_review(data.content)
    review_status = "pending" if need_review else "approved"
    review_reason_value = review_reason if need_review else None

    comment = await news_service.create_comment(
        db,
        news_id,
        current_user.id,
        data.content,
        review_status=review_status,
        review_reason=review_reason_value,
    )
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

@router.get("/admin/comments", response_model=NewsCommentAdminListResponse, summary="管理员获取新闻评论列表")
async def admin_list_news_comments(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    review_status: str | None = None,
    news_id: int | None = None,
    user_id: int | None = None,
    keyword: str | None = None,
    include_deleted: bool = False,
):
    comments, total = await news_service.list_comments_admin(
        db,
        page=page,
        page_size=page_size,
        review_status=review_status,
        news_id=news_id,
        user_id=user_id,
        keyword=keyword,
        include_deleted=bool(include_deleted),
    )
    items = [NewsCommentAdminItem.model_validate(c) for c in comments]
    return NewsCommentAdminListResponse(items=items, total=int(total), page=int(page), page_size=int(page_size))


@router.post("/admin/comments/{comment_id}/review", response_model=NewsCommentAdminItem, summary="管理员审核新闻评论")
async def admin_review_news_comment(
    comment_id: int,
    data: NewsCommentReviewAction,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    action = str(getattr(data, "action", "") or "").strip().lower()
    if action not in {"approve", "reject", "delete"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="action 仅支持 approve / reject / delete")

    try:
        comment = await news_service.review_comment_admin(
            db,
            int(comment_id),
            action=action,
            reason=getattr(data, "reason", None),
            admin_user_id=int(current_user.id),
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效操作")

    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")

    return NewsCommentAdminItem.model_validate(comment)

class AdminDebugSetViewCountRequest(BaseModel):
    view_count: int

@router.post("/admin/{news_id}/debug/set-view-count", summary="DEBUG: 设置新闻浏览量")
async def admin_debug_set_view_count(
    news_id: int,
    data: AdminDebugSetViewCountRequest,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    settings = get_settings()
    if not bool(getattr(settings, "debug", False)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    vc = int(getattr(data, "view_count", 0) or 0)
    if vc < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="view_count must be >= 0")

    result = await db.execute(
        update(News).where(News.id == int(news_id)).values(view_count=int(vc))
    )
    await db.commit()
    if not int(getattr(result, "rowcount", 0) or 0):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    news_service.invalidate_hot_cache()
    return {"message": "ok", "news_id": int(news_id), "view_count": int(vc)}

@router.post("", response_model=NewsResponse, summary="创建新闻")
async def create_news(
    news_data: NewsCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """创建新闻（需要管理员权限）"""
    news = await news_service.create(db, news_data, admin_user_id=int(current_user.id))
    if news.is_published:
        _ = await news_service.notify_subscribers_on_publish(db, news)
    return NewsResponse.model_validate(news)


@router.post("/admin/{news_id}/review", response_model=NewsResponse, summary="管理员审核新闻")
async def admin_review_news(
    news_id: int,
    data: NewsReviewAction,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    action = str(getattr(data, "action", "") or "").strip().lower()
    if action not in {"approve", "reject", "pending"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="action 仅支持 approve / reject / pending")

    was_published = False
    existing = await news_service.get_by_id(db, int(news_id))
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")
    was_published = bool(getattr(existing, "is_published", False))

    try:
        updated = await news_service.review_news_admin(
            db,
            int(news_id),
            action=action,
            reason=getattr(data, "reason", None),
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效操作")

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    if (not was_published) and bool(getattr(updated, "is_published", False)):
        _ = await news_service.notify_subscribers_on_publish(db, updated)

    return NewsResponse.model_validate(updated)


@router.post("/admin/{news_id}/ai/rerun", summary="管理员重跑新闻AI标注")
async def admin_rerun_news_ai(
    news_id: int,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..services.news_ai_pipeline_service import news_ai_pipeline_service

    try:
        await news_ai_pipeline_service.rerun_news(db, int(news_id))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    return {"message": "ok"}


@router.post("/admin/ai/generate", response_model=NewsAIGenerationItem, summary="新闻AI工作台生成")
async def admin_news_ai_generate(
    data: NewsAIGenerateRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    from ..routers.system import log_admin_action

    nid = _coerce_int(data.news_id)

    title = getattr(data, "title", None)
    summary = getattr(data, "summary", None)
    content = getattr(data, "content", None)

    use_news_content = bool(data.use_news_content)
    if use_news_content and nid is not None and nid > 0:
        t0, s0, c0 = await news_workbench_service.get_news_content_for_task(db, int(nid))
        if title is None:
            title = t0
        if summary is None:
            summary = s0
        if content is None:
            content = c0

    if not str(content or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content 不能为空（可传 content 或传 news_id 并开启 use_news_content）")

    task_type = str(getattr(data, "task_type", "") or "").strip()
    if not task_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task_type 不能为空")

    wc_min = _coerce_int(data.word_count_min)
    wc_max = _coerce_int(data.word_count_max)
    if wc_min is not None and wc_max is not None and int(wc_min) > int(wc_max):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="word_count_min 不能大于 word_count_max")

    rec = await news_workbench_service.generate(
        db,
        user_id=int(current_user.id),
        news_id=nid,
        task_type=task_type,
        title=title,
        summary=summary,
        content=content,
        style=getattr(data, "style", None),
        word_count_min=getattr(data, "word_count_min", None),
        word_count_max=getattr(data, "word_count_max", None),
        append=bool(getattr(data, "append", False)),
    )

    await log_admin_action(
        db,
        int(current_user.id),
        "ai_generate",
        "news",
        target_id=int(nid) if nid is not None else None,
        description=f"task_type={str(getattr(data, 'task_type', '') or '').strip()} status={str(getattr(rec, 'status', '') or '')}",
        request=request,
    )
    return NewsAIGenerationItem.model_validate(rec)


@router.get("/admin/ai/generations", response_model=NewsAIGenerationListResponse, summary="获取新闻AI生成历史")
async def admin_list_news_ai_generations(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
    news_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    from ..routers.system import log_admin_action

    nid = int(news_id) if news_id is not None else None
    items = await news_workbench_service.list_generations(db, user_id=int(current_user.id), news_id=nid, limit=int(limit))

    await log_admin_action(
        db,
        int(current_user.id),
        "ai_generations_list",
        "news",
        target_id=int(nid) if nid is not None else None,
        description=f"news_id={int(nid) if nid is not None else ''} limit={int(limit)} items={len(items)}",
        request=request,
    )
    return NewsAIGenerationListResponse(items=[NewsAIGenerationItem.model_validate(x) for x in items])


@router.post("/admin/link_check", response_model=NewsLinkCheckResponse, summary="链接提取与检查")
async def admin_check_news_links(
    data: NewsLinkCheckRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    from ..routers.system import log_admin_action

    nid = _coerce_int(data.news_id)
    markdown = data.markdown

    use_news_content = bool(data.use_news_content)
    if (markdown is None) and use_news_content and nid is not None and nid > 0:
        _, _, c0 = await news_workbench_service.get_news_content_for_task(db, int(nid))
        markdown = c0
    md = str(markdown or "")

    if not md.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="markdown 不能为空")

    run_id, items = await news_workbench_service.check_links(
        db,
        user_id=int(current_user.id),
        news_id=nid,
        markdown=md,
        timeout_seconds=float(data.timeout_seconds or 6.0),
        max_urls=int(data.max_urls or 50),
    )

    await log_admin_action(
        db,
        int(current_user.id),
        "link_check",
        "news",
        target_id=int(nid) if nid is not None else None,
        description=f"run_id={str(run_id)} urls={len(items)}",
        request=request,
    )

    return NewsLinkCheckResponse(
        run_id=str(run_id),
        items=[NewsLinkCheckItem.model_validate(x) for x in items],
    )


@router.get("/admin/link_check/{run_id}", response_model=NewsLinkCheckResponse, summary="按run_id获取链接检查结果")
async def admin_get_link_check_result(
    run_id: str,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    from ..routers.system import log_admin_action

    rid = str(run_id or "").strip()
    if not rid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run_id 不能为空")

    items = await news_workbench_service.get_link_checks_by_run_id(db, run_id=rid, user_id=int(current_user.id))

    await log_admin_action(
        db,
        int(current_user.id),
        "link_check_get",
        "news",
        target_id=None,
        description=f"run_id={rid} items={len(items)}",
        request=request,
    )

    return NewsLinkCheckResponse(run_id=rid, items=[NewsLinkCheckItem.model_validate(x) for x in items])


@router.post("/admin/batch", response_model=NewsBatchActionResponse, summary="新闻批量操作")
async def admin_batch_action_news(
    data: NewsBatchActionRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    from ..routers.system import log_admin_action

    raw_ids = [int(x) for x in (data.ids or []) if int(x) > 0]
    seen: set[int] = set()
    ids: list[int] = []
    for i in raw_ids:
        if int(i) not in seen:
            ids.append(int(i))
            seen.add(int(i))
    if not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids 不能为空")

    action = str(getattr(data, "action", "") or "").strip().lower()
    reason = str(getattr(data, "reason", "") or "").strip() or None

    allowed = {"publish", "unpublish", "top", "untop", "rerun_ai"}
    if action not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="action 不支持")

    res = await db.execute(select(News).where(News.id.in_(ids)))
    items = list(res.scalars().all())
    found_ids = {int(n.id) for n in items}
    missing_ids = [int(i) for i in ids if int(i) not in found_ids]

    processed: list[int] = []
    skipped: list[int] = []

    if action == "rerun_ai":
        from ..services.news_ai_pipeline_service import news_ai_pipeline_service

        for n in items:
            try:
                await news_ai_pipeline_service.rerun_news(db, int(n.id))
                processed.append(int(n.id))
            except Exception:
                skipped.append(int(n.id))

        msg = f"已处理 {len(processed)} 条，跳过 {len(skipped)} 条，缺失 {len(missing_ids)} 条"
        await log_admin_action(
            db,
            int(current_user.id),
            "batch_rerun_ai",
            "news",
            target_id=None,
            description=msg,
            request=request,
        )
        return NewsBatchActionResponse(
            requested=ids,
            processed=processed,
            missing=missing_ids,
            skipped=skipped,
            action=action,
            reason=reason,
            message=msg,
        )

    updated_items: list[News] = []
    for n in items:
        if action == "publish":
            if str(getattr(n, "review_status", "approved") or "approved").strip().lower() != "approved":
                skipped.append(int(n.id))
                continue
            upd = NewsUpdate(is_published=True)
        elif action == "unpublish":
            upd = NewsUpdate(is_published=False)
        elif action == "top":
            upd = NewsUpdate(is_top=True)
        else:
            upd = NewsUpdate(is_top=False)

        try:
            updated = await news_service.update(
                db,
                n,
                upd,
                admin_user_id=int(current_user.id),
                version_action=f"batch_{action}",
                version_reason=reason,
            )
            updated_items.append(updated)
            processed.append(int(n.id))
        except Exception:
            skipped.append(int(n.id))

    published_new: list[News] = []
    if action == "publish":
        for n in updated_items:
            if int(n.id) in processed and bool(getattr(n, "is_published", False)):
                published_new.append(n)

    notifications_created = 0
    for n in published_new:
        try:
            notifications_created += int(await news_service.notify_subscribers_on_publish(db, n))
        except Exception:
            continue

    msg = f"已处理 {len(processed)} 条，跳过 {len(skipped)} 条，缺失 {len(missing_ids)} 条"
    if notifications_created:
        msg += f"，推送 {int(notifications_created)} 条"

    await log_admin_action(
        db,
        int(current_user.id),
        f"batch_{action}",
        "news",
        target_id=None,
        description=msg,
        request=request,
    )

    return NewsBatchActionResponse(
        requested=ids,
        processed=processed,
        missing=missing_ids,
        skipped=skipped,
        action=action,
        reason=reason,
        message=msg,
    )


@router.post("/admin/batch/query", response_model=NewsBatchActionResponse, summary="新闻按筛选批量操作")
async def admin_batch_action_news_by_query(
    data: NewsBatchQueryRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    from ..routers.system import log_admin_action

    action = str(data.action or "").strip().lower()
    if action != "rerun_ai":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="action 仅支持 rerun_ai")

    limit = int(data.limit or 200)
    limit = max(1, min(500, limit))

    topic_id = _coerce_int(data.topic_id)

    news_list, total = await news_service.get_list(
        db,
        page=1,
        page_size=limit,
        category=data.category,
        keyword=data.keyword,
        published_only=False,
        review_status=data.review_status,
        ai_risk_level=data.risk_level,
        source_site=data.source_site,
        source=data.source,
        topic_id=int(topic_id) if topic_id is not None else None,
    )

    ids = [int(n.id) for n in news_list]
    processed: list[int] = []
    skipped: list[int] = []

    from ..services.news_ai_pipeline_service import news_ai_pipeline_service

    for nid in ids:
        try:
            await news_ai_pipeline_service.rerun_news(db, int(nid))
            processed.append(int(nid))
        except Exception:
            skipped.append(int(nid))

    msg = (
        f"已处理 {len(processed)} 条，跳过 {len(skipped)} 条，"
        f"本次命中 {len(ids)} 条，筛选总数 {int(total)} 条"
    )
    await log_admin_action(
        db,
        int(current_user.id),
        "batch_query_rerun_ai",
        "news",
        target_id=None,
        description=msg,
        request=request,
    )

    return NewsBatchActionResponse(
        requested=ids,
        processed=processed,
        missing=[],
        skipped=skipped,
        action=action,
        reason=None,
        message=msg,
    )


@router.get("/admin/scheduled", response_model=ScheduledNewsListResponse, summary="获取定时发布/下线队列")
async def admin_list_scheduled_news(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    from ..routers.system import log_admin_action

    q = (
        select(News)
        .where(
            or_(
                News.scheduled_publish_at.is_not(None),
                News.scheduled_unpublish_at.is_not(None),
            )
        )
        .order_by(desc(News.scheduled_publish_at), desc(News.scheduled_unpublish_at), desc(News.id))
        .limit(int(limit))
    )
    res = await db.execute(q)
    items = list(res.scalars().all())

    await log_admin_action(
        db,
        int(current_user.id),
        "scheduled_list",
        "news",
        target_id=None,
        description=f"limit={int(limit)} items={len(items)}",
        request=request,
    )
    return ScheduledNewsListResponse(items=[ScheduledNewsItem.model_validate(x) for x in items])


class BatchReviewAction(BaseModel):
    ids: list[int]
    action: str
    reason: str | None = None


@router.post("/admin/review/batch", summary="批量审核新闻")
async def admin_batch_review_news(
    data: BatchReviewAction,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    from ..routers.system import log_admin_action

    ids = [int(x) for x in (data.ids or []) if int(x) > 0]
    if not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids 不能为空")

    action = (data.action or "").strip().lower()
    if action not in {"approve", "reject", "pending"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action 仅支持 approve / reject / pending",
        )

    result = await db.execute(select(News).where(News.id.in_(ids)))
    items = list(result.scalars().all())
    found_ids = {int(n.id) for n in items}
    missing_ids = [int(i) for i in ids if int(i) not in found_ids]

    now = datetime.now()
    rsn = str(data.reason).strip() if data.reason is not None else None

    became_published: list[News] = []
    processed: list[int] = []

    for news in items:
        prev_published = bool(getattr(news, "is_published", False))
        if action == "approve":
            news.review_status = "approved"
            news.review_reason = rsn
            news.reviewed_at = now

            sp = getattr(news, "scheduled_publish_at", None)
            su = getattr(news, "scheduled_unpublish_at", None)
            if isinstance(sp, datetime) and sp <= now and (
                su is None or (isinstance(su, datetime) and su > now)
            ):
                news.is_published = True
                news.published_at = now
        elif action == "reject":
            news.review_status = "rejected"
            news.review_reason = rsn
            news.reviewed_at = now
            news.is_published = False
            news.published_at = None
        else:
            news.review_status = "pending"
            news.review_reason = rsn
            news.reviewed_at = None
            news.is_published = False
            news.published_at = None

        if (not prev_published) and bool(getattr(news, "is_published", False)):
            became_published.append(news)

        processed.append(int(news.id))

    await db.commit()

    notifications_created = 0
    for news in became_published:
        notifications_created += int(await news_service.notify_subscribers_on_publish(db, news))

    counts = {
        "requested": len(ids),
        "processed": len(processed),
        "missing": len(missing_ids),
        "notifications_created": int(notifications_created),
    }
    message = f"已处理 {counts['processed']} 条，缺失 {counts['missing']} 条"

    await log_admin_action(
        db,
        int(current_user.id),
        f"review_batch_{action}",
        "news",
        target_id=None,
        description=message,
        request=request,
    )
    return {
        "processed": processed,
        "missing": missing_ids,
        "action": action,
        "reason": rsn,
        "requested": ids,
        "counts": counts,
        "message": message,
    }


@router.post("/admin/comments/review/batch", summary="批量审核新闻评论")
async def admin_batch_review_news_comments(
    data: BatchReviewAction,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    ids = [int(x) for x in (data.ids or []) if int(x) > 0]
    if not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids 不能为空")

    action = (data.action or "").strip().lower()
    if action not in {"approve", "reject", "delete"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action 仅支持 approve / reject / delete",
        )

    comment_result = await db.execute(select(NewsComment).where(NewsComment.id.in_(ids)))
    comments = list(comment_result.scalars().all())
    found_ids = {int(c.id) for c in comments}
    missing_ids = [int(i) for i in ids if int(i) not in found_ids]

    now = datetime.now()
    rsn = str(data.reason).strip() if data.reason is not None else None
    processed: list[int] = []

    title_single = (
        "你的新闻评论已通过审核"
        if action == "approve"
        else "你的新闻评论未通过审核"
        if action == "reject"
        else "你的新闻评论已被删除"
    )

    for comment in comments:
        if action == "approve":
            comment.is_deleted = False
            comment.review_status = "approved"
            comment.review_reason = rsn
            comment.reviewed_at = now
        else:
            comment.is_deleted = True
            comment.review_status = "rejected"
            comment.review_reason = rsn
            comment.reviewed_at = now
        processed.append(int(comment.id))

    await db.commit()

    by_user: dict[int, list[NewsComment]] = {}
    for comment in comments:
        by_user.setdefault(int(comment.user_id), []).append(comment)

    max_individual = 10
    values: list[dict[str, object]] = []
    for user_id, user_comments in by_user.items():
        user_comments = sorted(user_comments, key=lambda x: int(getattr(x, "id", 0) or 0))
        if len(user_comments) <= max_individual:
            for comment in user_comments:
                content_lines: list[str] = [
                    f"评论ID：{int(comment.id)}",
                    f"新闻ID：{int(comment.news_id)}",
                ]
                if rsn:
                    content_lines.append(f"原因：{rsn}")
                link = f"/news/{int(comment.news_id)}"
                values.append(
                    {
                        "user_id": int(user_id),
                        "type": NotificationType.SYSTEM,
                        "title": f"{title_single}（批量）",
                        "content": "\n".join(content_lines) if content_lines else None,
                        "link": link,
                        "dedupe_key": f"news_comment:{int(comment.id)}:{action}",
                        "is_read": False,
                        "related_user_id": int(current_user.id),
                        "related_comment_id": int(comment.id),
                    }
                )
        else:
            ids_str = ", ".join(str(int(c.id)) for c in user_comments)
            content_lines = [f"评论ID：{ids_str}"]
            if rsn:
                content_lines.append(f"原因：{rsn}")
            first = user_comments[0]
            link = f"/news/{int(first.news_id)}"
            values.append(
                {
                    "user_id": int(user_id),
                    "type": NotificationType.SYSTEM,
                    "title": f"{title_single}（批量）",
                    "content": "\n".join(content_lines) if content_lines else None,
                    "link": link,
                    "dedupe_key": f"news_comment_batch:{action}:{int(first.id)}:{len(user_comments)}",
                    "is_read": False,
                    "related_user_id": int(current_user.id),
                    "related_comment_id": int(first.id),
                }
            )

    notifications_created = 0
    if values:
        bind = db.get_bind()
        dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "") or "")
        if dialect_name == "postgresql":
            stmt = pg_insert(Notification).values(values).on_conflict_do_nothing(
                index_elements=["user_id", "type", "dedupe_key"]
            )
        else:
            stmt = sqlite_insert(Notification).values(values).on_conflict_do_nothing(
                index_elements=["user_id", "type", "dedupe_key"]
            )
        try:
            result = await db.execute(stmt)
            await db.commit()
            notifications_created = int(getattr(result, "rowcount", 0) or 0)
        except Exception:
            await db.rollback()

    counts: dict[str, int] = {
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
        "reason": rsn,
        "requested": ids,
        "counts": counts,
        "message": message,
    }


@router.put("/{news_id:int}", response_model=NewsResponse, summary="更新新闻")
async def update_news(
    news_id: int,
    news_data: NewsUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """更新新闻（需要管理员权限）"""
    news = await news_service.get_by_id(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    was_published = bool(news.is_published)
    updated_news = None
    target = news
    for attempt in range(2):
        try:
            updated_news = await news_service.update(db, target, news_data, admin_user_id=int(current_user.id))
            break
        except StaleDataError:
            await db.rollback()
            fresh = await news_service.get_by_id(db, news_id)
            if fresh is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")
            if attempt == 0:
                was_published = bool(fresh.is_published)
                target = fresh
                continue
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="新闻已被其他操作修改，请刷新后重试",
            )

    if updated_news is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="新闻已被其他操作修改，请刷新后重试",
        )
    if (not was_published) and bool(updated_news.is_published):
        _ = await news_service.notify_subscribers_on_publish(db, updated_news)
    return NewsResponse.model_validate(updated_news)


@router.get("/admin/{news_id:int}/versions", response_model=NewsVersionListResponse, summary="管理员查看新闻版本历史")
async def admin_list_news_versions(
    news_id: int,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    versions = await news_service.list_versions(db, int(news_id), limit=int(limit))
    items = [NewsVersionItem.model_validate(v) for v in versions]
    return NewsVersionListResponse(items=items)


@router.post("/admin/{news_id:int}/rollback", response_model=NewsResponse, summary="管理员回滚新闻到历史版本")
async def admin_rollback_news(
    news_id: int,
    data: NewsRollbackRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    from ..routers.system import log_admin_action

    try:
        updated = await news_service.rollback_to_version(
            db,
            int(news_id),
            int(data.version_id),
            admin_user_id=int(current_user.id),
            reason=getattr(data, "reason", None),
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="版本不存在或快照无效")

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    await log_admin_action(
        db,
        int(current_user.id),
        "rollback",
        "news",
        target_id=int(news_id),
        description=f"rollback to version {int(data.version_id)}",
        request=request,
    )

    return NewsResponse.model_validate(updated)


@router.delete("/{news_id:int}", summary="删除新闻")
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
    review_status: str | None = None,
    risk_level: str | None = None,
    source_site: str | None = None,
    source: str | None = None,
    topic_id: int | None = None,
):
    """获取所有新闻，包括未发布的（需要管理员权限）"""
    _ = current_user
    news_list, total = await news_service.get_list(
        db,
        page,
        page_size,
        category,
        keyword,
        published_only=False,
        review_status=review_status,
        ai_risk_level=risk_level,
        source_site=source_site,
        source=source,
        topic_id=int(topic_id) if topic_id is not None else None,
    )

    ids = [int(n.id) for n in news_list]
    risk_levels = await _get_ai_risk_levels(db, ids)

    items: list[NewsAdminListItem] = []
    for news in news_list:
        item = NewsAdminListItem.model_validate(news)
        item.ai_risk_level = risk_levels.get(int(news.id), "unknown")
        items.append(item)
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

    resp = NewsResponse.model_validate(news)

    ann_res = await db.execute(select(NewsAIAnnotation).where(NewsAIAnnotation.news_id == int(news.id)))
    ann = ann_res.scalar_one_or_none()
    if ann is not None:
        raw_words = str(getattr(ann, "sensitive_words", "") or "").strip()
        words = [w.strip() for w in raw_words.split(",") if w.strip()] if raw_words else []

        highlights: list[str] = []
        try:
            raw_hl = getattr(ann, "highlights", None)
            parsed_hl: object = cast(object, json.loads(raw_hl)) if isinstance(raw_hl, str) and raw_hl.strip() else []
            if isinstance(parsed_hl, list):
                for x in cast(list[object], parsed_hl):
                    s = str(x or "").strip()
                    if s:
                        highlights.append(s)
        except Exception:
            highlights = []

        keywords: list[str] = []
        try:
            raw_kw = getattr(ann, "keywords", None)
            parsed_kw: object = cast(object, json.loads(raw_kw)) if isinstance(raw_kw, str) and raw_kw.strip() else []
            if isinstance(parsed_kw, list):
                for x in cast(list[object], parsed_kw):
                    s = str(x or "").strip()
                    if s:
                        keywords.append(s)
        except Exception:
            keywords = []
        risk = str(getattr(ann, "risk_level", "unknown") or "unknown")
        resp.ai_risk_level = risk
        resp.ai_annotation = NewsAIAnnotationResponse(
            summary=getattr(ann, "summary", None),
            risk_level=risk,
            sensitive_words=words,
            highlights=highlights,
            keywords=keywords,
            duplicate_of_news_id=getattr(ann, "duplicate_of_news_id", None),
            processed_at=getattr(ann, "processed_at", None),
        )
    else:
        resp.ai_risk_level = "unknown"
    return resp
