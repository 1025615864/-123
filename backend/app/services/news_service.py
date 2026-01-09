"""新闻服务层"""
import json
import logging
import math
from collections.abc import Sequence
from datetime import datetime, timedelta
import time
from typing import Any, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, delete, update, true, case
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.orm import joinedload

from ..models.news import (
    News,
    NewsFavorite,
    NewsViewHistory,
    NewsSubscription,
    NewsComment,
    NewsTopic,
    NewsTopicItem,
)
from ..models.news_ai import NewsAIAnnotation
from ..models.news_workbench import NewsVersion
from ..models.notification import Notification, NotificationType
from ..schemas.news import NewsCreate, NewsUpdate


logger = logging.getLogger(__name__)


class NewsService:
    """新闻服务"""

    @staticmethod
    def _escape_like(value: str, escape: str = "\\") -> str:
        s = str(value or "")
        if not escape:
            return s
        s = s.replace(escape, escape + escape)
        s = s.replace("%", escape + "%")
        s = s.replace("_", escape + "_")
        return s

    @staticmethod
    def _news_snapshot(news: News) -> dict[str, object]:
        def _dt(v: object) -> str | None:
            if isinstance(v, datetime):
                return v.isoformat()
            return None

        return {
            "id": int(getattr(news, "id", 0) or 0),
            "title": str(getattr(news, "title", "") or ""),
            "summary": getattr(news, "summary", None),
            "content": str(getattr(news, "content", "") or ""),
            "cover_image": getattr(news, "cover_image", None),
            "category": str(getattr(news, "category", "") or ""),
            "source": getattr(news, "source", None),
            "source_url": getattr(news, "source_url", None),
            "source_site": getattr(news, "source_site", None),
            "author": getattr(news, "author", None),
            "is_top": bool(getattr(news, "is_top", False)),
            "is_published": bool(getattr(news, "is_published", False)),
            "review_status": str(getattr(news, "review_status", "") or ""),
            "review_reason": getattr(news, "review_reason", None),
            "reviewed_at": _dt(getattr(news, "reviewed_at", None)),
            "published_at": _dt(getattr(news, "published_at", None)),
            "scheduled_publish_at": _dt(getattr(news, "scheduled_publish_at", None)),
            "scheduled_unpublish_at": _dt(getattr(news, "scheduled_unpublish_at", None)),
            "created_at": _dt(getattr(news, "created_at", None)),
            "updated_at": _dt(getattr(news, "updated_at", None)),
        }

    @staticmethod
    def _snapshot_json(news: News) -> str:
        return json.dumps(NewsService._news_snapshot(news), ensure_ascii=False)

    _hot_cache: dict[tuple[int, str | None, str | None], tuple[float, list[int]]] = {}
    _hot_cache_ttl_seconds: int = 60

    _topic_auto_cache: dict[tuple[int, bool], tuple[float, list[int]]] = {}
    _topic_auto_cache_ttl_seconds: int = 120

    _recommended_cache: dict[tuple[int | None, str | None, str | None], tuple[float, list[int]]] = {}
    _recommended_cache_ttl_seconds: int = 60

    @staticmethod
    def _prune_cache(
        cache: dict[object, tuple[float, list[int]]],
        ttl_seconds: int,
        now_ts: float,
        max_size: int = 2048,
    ) -> None:
        if len(cache) <= int(max_size):
            return

        keys = list(cache.keys())
        for k in keys:
            v = cache.get(k)
            if v is None:
                continue
            cached_at = float(v[0])
            if (now_ts - cached_at) > float(ttl_seconds):
                _ = cache.pop(k, None)

        if len(cache) > int(max_size):
            cache.clear()

    @staticmethod
    def invalidate_hot_cache() -> None:
        NewsService._hot_cache.clear()

    @staticmethod
    def invalidate_recommended_cache(user_id: int | None) -> None:
        keys = [k for k in NewsService._recommended_cache.keys() if k[0] == (int(user_id) if user_id is not None else None)]
        for k in keys:
            _ = NewsService._recommended_cache.pop(k, None)

    @staticmethod
    def invalidate_topic_auto_cache(topic_id: int) -> None:
        keys = [k for k in NewsService._topic_auto_cache.keys() if int(k[0]) == int(topic_id)]
        for k in keys:
            _ = NewsService._topic_auto_cache.pop(k, None)

    @staticmethod
    def _public_news_conditions() -> list[ColumnElement[bool]]:
        return [News.is_published == True, News.review_status == "approved"]

    @staticmethod
    async def _compute_topic_auto_ids(
        db: AsyncSession,
        topic: NewsTopic,
        published_only: bool,
    ) -> list[int]:
        auto_limit = int(getattr(topic, "auto_limit", 0) or 0)
        auto_category = str(getattr(topic, "auto_category", "") or "").strip()
        auto_keyword = str(getattr(topic, "auto_keyword", "") or "").strip()

        if auto_limit <= 0 or (not auto_category and not auto_keyword):
            return []

        auto_conditions: list[ColumnElement[bool]] = []
        if published_only:
            auto_conditions.extend(NewsService._public_news_conditions())
        if auto_category:
            auto_conditions.append(News.category == auto_category)
        if auto_keyword:
            pattern = f"%{auto_keyword}%"
            auto_conditions.append(
                or_(
                    News.title.ilike(pattern),
                    News.summary.ilike(pattern),
                    News.content.ilike(pattern),
                )
            )

        manual_ids_subq = select(NewsTopicItem.news_id).where(NewsTopicItem.topic_id == int(topic.id))
        auto_conditions.append(~News.id.in_(manual_ids_subq))

        effective_auto_limit = min(500, auto_limit)
        q = (
            select(News.id)
            .where(and_(*auto_conditions))
            .order_by(desc(News.published_at), desc(News.created_at))
            .limit(int(effective_auto_limit))
        )
        res = await db.execute(q)
        rows = cast(list[tuple[int]], res.all())
        return [int(nid) for (nid,) in rows]

    @staticmethod
    async def get_topic_auto_ids_cached(
        db: AsyncSession,
        topic: NewsTopic,
        published_only: bool,
        force_refresh: bool = False,
    ) -> list[int]:
        key = (int(topic.id), bool(published_only))
        now_ts = time.time()
        NewsService._prune_cache(
            cast(dict[object, tuple[float, list[int]]], NewsService._topic_auto_cache),
            int(NewsService._topic_auto_cache_ttl_seconds),
            float(now_ts),
        )
        if not force_refresh:
            cached = NewsService._topic_auto_cache.get(key)
            if cached is not None:
                cached_at, cached_ids = cached
                if (now_ts - float(cached_at)) <= float(NewsService._topic_auto_cache_ttl_seconds):
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            "news.topic_auto cache_hit topic_id=%s published_only=%s size=%s",
                            int(topic.id),
                            int(bool(published_only)),
                            len(cached_ids),
                        )
                    return list(cached_ids)

        ids = await NewsService._compute_topic_auto_ids(db, topic, bool(published_only))
        NewsService._topic_auto_cache[key] = (now_ts, list(ids))
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "news.topic_auto cache_miss topic_id=%s published_only=%s cached_size=%s",
                int(topic.id),
                int(bool(published_only)),
                len(ids),
            )
        return list(ids)

    @staticmethod
    async def refresh_topic_auto_cache(
        db: AsyncSession,
        topic_id: int,
        published_only: bool = True,
    ) -> int:
        topic = await NewsService.get_topic(db, int(topic_id))
        if not topic:
            return 0
        ids = await NewsService.get_topic_auto_ids_cached(db, topic, bool(published_only), force_refresh=True)
        return len(ids)
    
    @staticmethod
    async def create(db: AsyncSession, news_data: NewsCreate, *, admin_user_id: int | None = None) -> News:
        """创建新闻"""
        now = datetime.now()
        scheduled_publish_at = news_data.scheduled_publish_at
        scheduled_unpublish_at = news_data.scheduled_unpublish_at
        is_published = bool(news_data.is_published)
        published_at = now if is_published else None

        review_status_raw: object | None = getattr(news_data, "review_status", None)
        review_status = str(review_status_raw or "approved").strip().lower()
        review_reason_raw: object | None = getattr(news_data, "review_reason", None)
        review_reason = str(review_reason_raw).strip() if review_reason_raw is not None else None

        reviewed_at: datetime | None = None
        if review_status in {"approved", "rejected"}:
            reviewed_at = now

        if review_status != "approved":
            is_published = False
            published_at = None

        if scheduled_publish_at is not None:
            if scheduled_publish_at > now:
                is_published = False
                published_at = None
            else:
                if review_status == "approved":
                    is_published = True
                    published_at = now
                else:
                    is_published = False
                    published_at = None

        if scheduled_unpublish_at is not None and scheduled_unpublish_at <= now:
            is_published = False

        news = News(
            title=news_data.title,
            summary=news_data.summary,
            content=news_data.content,
            cover_image=news_data.cover_image,
            category=news_data.category,
            source=news_data.source,
            source_url=getattr(news_data, "source_url", None),
            source_site=getattr(news_data, "source_site", None),
            author=news_data.author,
            is_top=news_data.is_top,
            is_published=is_published,
            review_status=review_status,
            review_reason=review_reason,
            reviewed_at=reviewed_at,
            published_at=published_at,
            scheduled_publish_at=scheduled_publish_at,
            scheduled_unpublish_at=scheduled_unpublish_at,
        )
        db.add(news)

        if admin_user_id is not None and int(admin_user_id) > 0:
            await db.flush()
            db.add(
                NewsVersion(
                    news_id=int(news.id),
                    action="create",
                    reason=None,
                    snapshot_json=NewsService._snapshot_json(news),
                    created_by=int(admin_user_id),
                )
            )

        await db.commit()
        await db.refresh(news)
        return news
    
    @staticmethod
    async def get_by_id(db: AsyncSession, news_id: int) -> News | None:
        """根据ID获取新闻"""
        result = await db.execute(
            select(News).where(News.id == news_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_published(db: AsyncSession, news_id: int) -> News | None:
        """获取已发布的新闻"""
        result = await db.execute(
            select(News).where(
                and_(
                    News.id == news_id,
                    *NewsService._public_news_conditions(),
                )
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None,
        published_only: bool = True,
        review_status: str | None = None,
        ai_risk_level: str | None = None,
        source_site: str | None = None,
        source: str | None = None,
        topic_id: int | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> tuple[list[News], int]:
        """获取新闻列表"""
        query = select(News)
        count_query = select(func.count(News.id))
        
        if published_only:
            query = query.where(and_(*NewsService._public_news_conditions()))
            count_query = count_query.where(and_(*NewsService._public_news_conditions()))

        rs = str(review_status or "").strip().lower()
        if rs:
            query = query.where(News.review_status == rs)
            count_query = count_query.where(News.review_status == rs)
        
        if category:
            query = query.where(News.category == category)
            count_query = count_query.where(News.category == category)
        
        if keyword:
            kw = str(keyword or "").strip()
            pattern = f"%{NewsService._escape_like(kw)}%"
            search_filter = or_(
                News.title.ilike(pattern, escape="\\"),
                News.summary.ilike(pattern, escape="\\"),
                News.content.ilike(pattern, escape="\\"),
                News.source.ilike(pattern, escape="\\"),
                News.author.ilike(pattern, escape="\\"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        ss = str(source_site or "").strip()
        if ss:
            query = query.where(News.source_site == ss)
            count_query = count_query.where(News.source_site == ss)

        src = str(source or "").strip()
        if src:
            query = query.where(News.source == src)
            count_query = count_query.where(News.source == src)

        tid = int(topic_id) if topic_id is not None else 0
        if tid > 0:
            query = query.join(NewsTopicItem, NewsTopicItem.news_id == News.id).where(
                NewsTopicItem.topic_id == int(tid)
            )
            count_query = count_query.join(
                NewsTopicItem, NewsTopicItem.news_id == News.id
            ).where(NewsTopicItem.topic_id == int(tid))

        ts_expr = func.coalesce(News.published_at, News.created_at)
        if from_dt is not None:
            query = query.where(ts_expr >= from_dt)
            count_query = count_query.where(ts_expr >= from_dt)
        if to_dt is not None:
            query = query.where(ts_expr <= to_dt)
            count_query = count_query.where(ts_expr <= to_dt)

        rl = str(ai_risk_level or "").strip().lower()
        if rl and rl != "all":
            if rl == "unknown":
                query = query.outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    or_(NewsAIAnnotation.risk_level == "unknown", NewsAIAnnotation.id.is_(None))
                )
                count_query = count_query.outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    or_(NewsAIAnnotation.risk_level == "unknown", NewsAIAnnotation.id.is_(None))
                )
            else:
                query = query.join(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    NewsAIAnnotation.risk_level == rl
                )
                count_query = count_query.join(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    NewsAIAnnotation.risk_level == rl
                )
        
        # 置顶优先，然后按发布时间倒序
        query = query.order_by(desc(News.is_top), desc(News.published_at), desc(News.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        news_list = result.scalars().all()
        
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0
        
        return list(news_list), int(total)

    @staticmethod
    async def review_news_admin(
        db: AsyncSession,
        news_id: int,
        action: str,
        reason: str | None = None,
    ) -> News | None:
        news = await NewsService.get_by_id(db, int(news_id))
        if news is None:
            return None

        now = datetime.now()
        act = str(action or "").strip().lower()
        rsn = str(reason).strip() if reason is not None else None

        if act == "approve":
            news.review_status = "approved"
            news.review_reason = rsn
            news.reviewed_at = now

            sp = getattr(news, "scheduled_publish_at", None)
            su = getattr(news, "scheduled_unpublish_at", None)
            if isinstance(sp, datetime) and sp <= now and (su is None or (isinstance(su, datetime) and su > now)):
                news.is_published = True
                news.published_at = now

        elif act == "reject":
            news.review_status = "rejected"
            news.review_reason = rsn
            news.reviewed_at = now
            news.is_published = False
            news.published_at = None

        elif act == "pending":
            news.review_status = "pending"
            news.review_reason = rsn
            news.reviewed_at = None
            news.is_published = False
            news.published_at = None
        else:
            raise ValueError("invalid action")

        await db.commit()
        await db.refresh(news)
        return news
    
    @staticmethod
    async def update(
        db: AsyncSession,
        news: News,
        news_data: NewsUpdate,
        *,
        admin_user_id: int | None = None,
        version_action: str = "update",
        version_reason: str | None = None,
    ) -> News:
        """更新新闻"""
        update_data: dict[str, object] = news_data.model_dump(exclude_unset=True)

        now = datetime.now()

        review_status_value = update_data.get("review_status")
        if isinstance(review_status_value, str):
            rs = review_status_value.strip().lower()
            update_data["review_status"] = rs
            if rs in {"approved", "rejected"}:
                _ = update_data.setdefault("reviewed_at", now)

        review_status = str(update_data.get("review_status") or getattr(news, "review_status", "approved") or "approved").strip().lower()
        if review_status != "approved":
            update_data["is_published"] = False
            update_data["published_at"] = None

        scheduled_publish_at = update_data.get("scheduled_publish_at")
        if isinstance(scheduled_publish_at, datetime):
            if scheduled_publish_at > now:
                update_data["is_published"] = False
            else:
                if review_status == "approved":
                    update_data["is_published"] = True
                    _ = update_data.setdefault("published_at", now)
                else:
                    update_data["is_published"] = False
                    update_data["published_at"] = None

        scheduled_unpublish_at = update_data.get("scheduled_unpublish_at")
        if isinstance(scheduled_unpublish_at, datetime) and scheduled_unpublish_at <= now:
            update_data["is_published"] = False

        is_published_value = update_data.get("is_published")
        if isinstance(is_published_value, bool) and is_published_value and not news.is_published:
            _ = update_data.setdefault("published_at", now)
        
        for field, value in update_data.items():
            setattr(news, field, value)

        if admin_user_id is not None and int(admin_user_id) > 0:
            db.add(
                NewsVersion(
                    news_id=int(news.id),
                    action=str(version_action or "update").strip() or "update",
                    reason=str(version_reason).strip() if version_reason is not None else None,
                    snapshot_json=NewsService._snapshot_json(news),
                    created_by=int(admin_user_id),
                )
            )

        await db.commit()
        await db.refresh(news)
        return news

    @staticmethod
    async def list_versions(db: AsyncSession, news_id: int, *, limit: int = 50) -> list[NewsVersion]:
        q = (
            select(NewsVersion)
            .where(NewsVersion.news_id == int(news_id))
            .order_by(desc(NewsVersion.created_at), desc(NewsVersion.id))
            .limit(int(max(1, min(200, limit))))
        )
        res = await db.execute(q)
        return list(res.scalars().all())

    @staticmethod
    async def rollback_to_version(
        db: AsyncSession,
        news_id: int,
        version_id: int,
        *,
        admin_user_id: int,
        reason: str | None = None,
    ) -> News | None:
        news = await NewsService.get_by_id(db, int(news_id))
        if news is None:
            return None

        res = await db.execute(
            select(NewsVersion).where(
                and_(
                    NewsVersion.id == int(version_id),
                    NewsVersion.news_id == int(news_id),
                )
            )
        )
        ver = res.scalar_one_or_none()
        if ver is None:
            raise ValueError("version not found")

        raw = str(getattr(ver, "snapshot_json", "") or "").strip()
        if not raw:
            raise ValueError("empty snapshot")

        try:
            snap_obj: object = cast(object, json.loads(raw))
        except Exception as e:
            raise ValueError("invalid snapshot") from e
        if not isinstance(snap_obj, dict):
            raise ValueError("invalid snapshot")
        snap = cast(dict[str, object], snap_obj)

        def _dt(value: object) -> datetime | None:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                s = value.strip()
                if not s:
                    return None
                try:
                    return datetime.fromisoformat(s)
                except Exception:
                    return None
            return None

        update_payload: dict[str, Any] = {}
        for k in (
            "title",
            "summary",
            "content",
            "cover_image",
            "category",
            "source",
            "source_url",
            "source_site",
            "author",
            "is_top",
            "is_published",
            "review_status",
            "review_reason",
        ):
            if k in snap:
                update_payload[k] = snap.get(k)

        for k in (
            "reviewed_at",
            "published_at",
            "scheduled_publish_at",
            "scheduled_unpublish_at",
        ):
            if k in snap:
                update_payload[k] = _dt(snap.get(k))

        news_update = NewsUpdate(**update_payload)
        return await NewsService.update(
            db,
            news,
            news_update,
            admin_user_id=int(admin_user_id),
            version_action="rollback",
            version_reason=str(reason).strip() if reason is not None else f"rollback_to_{int(version_id)}",
        )

    @staticmethod
    async def process_scheduled_news(db: AsyncSession, batch_size: int = 50) -> tuple[int, int]:
        now = datetime.now()

        publish_result = await db.execute(
            select(News)
            .where(
                and_(
                    News.is_published == False,
                    News.scheduled_publish_at.is_not(None),
                    News.scheduled_publish_at <= now,
                    News.review_status == "approved",
                )
            )
            .order_by(News.scheduled_publish_at.asc())
            .limit(int(batch_size))
        )
        to_publish: list[News] = list(publish_result.scalars().all())

        unpublish_result = await db.execute(
            select(News)
            .where(
                and_(
                    News.is_published == True,
                    News.scheduled_unpublish_at.is_not(None),
                    News.scheduled_unpublish_at <= now,
                )
            )
            .order_by(News.scheduled_unpublish_at.asc())
            .limit(int(batch_size))
        )
        to_unpublish: list[News] = list(unpublish_result.scalars().all())

        for news in to_publish:
            news.is_published = True
            news.published_at = now
            news.scheduled_publish_at = None

        for news in to_unpublish:
            news.is_published = False
            news.scheduled_unpublish_at = None

        if to_publish or to_unpublish:
            await db.commit()
            NewsService.invalidate_hot_cache()

        for news in to_publish:
            _ = await NewsService.notify_subscribers_on_publish(db, news)

        return len(to_publish), len(to_unpublish)
    
    @staticmethod
    async def delete(db: AsyncSession, news: News) -> None:
        """删除新闻"""
        _ = await db.execute(
            delete(NewsAIAnnotation).where(
                or_(
                    NewsAIAnnotation.news_id == news.id,
                    NewsAIAnnotation.duplicate_of_news_id == news.id,
                )
            )
        )
        await db.delete(news)
        await db.commit()
        NewsService.invalidate_hot_cache()
    
    @staticmethod
    async def increment_view(db: AsyncSession, news: News) -> None:
        """增加浏览量"""
        _ = await db.execute(
            update(News)
            .where(News.id == news.id)
            .values(view_count=News.view_count + 1)
        )
        await db.commit()

    @staticmethod
    async def record_view_history(db: AsyncSession, news_id: int, user_id: int) -> None:
        result = await db.execute(
            select(NewsViewHistory).where(
                and_(NewsViewHistory.news_id == news_id, NewsViewHistory.user_id == user_id)
            )
        )
        existing: NewsViewHistory | None = result.scalar_one_or_none()
        if existing is not None:
            existing.viewed_at = datetime.now()
            await db.commit()
            return

        db.add(NewsViewHistory(news_id=news_id, user_id=user_id))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()

    @staticmethod
    async def get_user_history(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None,
        ai_risk_level: str | None = None,
        source_site: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> tuple[list[News], int]:
        query = (
            select(News)
            .join(NewsViewHistory, News.id == NewsViewHistory.news_id)
            .where(
                and_(
                    NewsViewHistory.user_id == user_id,
                    *NewsService._public_news_conditions(),
                )
            )
            .order_by(desc(NewsViewHistory.viewed_at))
        )

        count_query = (
            select(func.count(NewsViewHistory.id))
            .join(News, News.id == NewsViewHistory.news_id)
            .where(
                and_(
                    NewsViewHistory.user_id == user_id,
                    *NewsService._public_news_conditions(),
                )
            )
        )

        if category:
            query = query.where(News.category == category)
            count_query = count_query.where(News.category == category)

        if keyword:
            pattern = f"%{keyword}%"
            search_filter = or_(
                News.title.ilike(pattern),
                News.summary.ilike(pattern),
                News.content.ilike(pattern),
                News.source.ilike(pattern),
                News.author.ilike(pattern),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        ss = str(source_site or "").strip()
        if ss:
            query = query.where(News.source_site == ss)
            count_query = count_query.where(News.source_site == ss)

        ts_expr = func.coalesce(News.published_at, News.created_at)
        if from_dt is not None:
            query = query.where(ts_expr >= from_dt)
            count_query = count_query.where(ts_expr >= from_dt)
        if to_dt is not None:
            query = query.where(ts_expr <= to_dt)
            count_query = count_query.where(ts_expr <= to_dt)

        rl = str(ai_risk_level or "").strip().lower()
        if rl and rl != "all":
            if rl == "unknown":
                query = query.outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    or_(NewsAIAnnotation.risk_level == "unknown", NewsAIAnnotation.id.is_(None))
                )
                count_query = count_query.outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    or_(NewsAIAnnotation.risk_level == "unknown", NewsAIAnnotation.id.is_(None))
                )
            else:
                query = query.join(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    NewsAIAnnotation.risk_level == rl
                )
                count_query = count_query.join(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    NewsAIAnnotation.risk_level == rl
                )

        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        items = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = int(count_result.scalar() or 0)

        return items, total
    
    @staticmethod
    async def get_categories(db: AsyncSession) -> list[dict[str, object]]:
        """获取分类及其新闻数量"""
        result = await db.execute(
            select(News.category, func.count(News.id).label("count"))
            .where(and_(*NewsService._public_news_conditions()))
            .group_by(News.category)
        )
        rows = result.all()
        return [{"category": row[0], "count": row[1]} for row in rows]

    @staticmethod
    async def get_hot_news(
        db: AsyncSession,
        days: int = 7,
        limit: int = 10,
        category: str | None = None,
        keyword: str | None = None,
    ) -> list[News]:
        kw = str(keyword or "").strip()
        cache_key = (
            int(days),
            str(category) if category is not None else None,
            kw if kw else None,
        )
        now_ts = time.time()
        NewsService._prune_cache(
            cast(dict[object, tuple[float, list[int]]], NewsService._hot_cache),
            int(NewsService._hot_cache_ttl_seconds),
            float(now_ts),
        )
        cached = NewsService._hot_cache.get(cache_key)
        if cached is not None:
            cached_at, cached_ids = cached
            if (now_ts - float(cached_at)) <= float(NewsService._hot_cache_ttl_seconds) and len(cached_ids) >= int(limit):
                ids = list(cached_ids[: int(limit)])
                if not ids:
                    return []
                res = await db.execute(select(News).where(News.id.in_(ids)))
                rows = list(res.scalars().all())
                by_id = {int(n.id): n for n in rows}
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "news.hot cache_hit days=%s category=%s kw=%s limit=%s returned=%s",
                        int(days),
                        str(category) if category is not None else None,
                        kw if kw else None,
                        int(limit),
                        len(ids),
                    )
                return [by_id[i] for i in ids if i in by_id]

        since = datetime.now() - timedelta(days=days)

        conditions: list[ColumnElement[bool]] = [
            *NewsService._public_news_conditions(),
            or_(
                and_(News.published_at.is_not(None), News.published_at >= since),
                and_(News.published_at.is_(None), News.created_at >= since),
            ),
        ]

        if category:
            conditions.append(News.category == category)

        if kw:
            pattern = f"%{kw}%"
            conditions.append(
                or_(
                    News.title.ilike(pattern),
                    News.summary.ilike(pattern),
                    News.content.ilike(pattern),
                    News.source.ilike(pattern),
                    News.author.ilike(pattern),
                )
            )

        candidate_limit = min(500, max(int(limit) * 50, 200))
        candidate_ids = (
            select(News.id)
            .where(and_(*conditions))
            .order_by(desc(News.view_count), desc(News.published_at), desc(News.created_at))
            .limit(candidate_limit)
            .cte("hot_candidates")
        )

        fav_counts = (
            select(NewsFavorite.news_id, func.count(NewsFavorite.id).label("fav_count"))
            .where(NewsFavorite.news_id.in_(select(candidate_ids.c.id)))
            .group_by(NewsFavorite.news_id)
            .subquery("hot_fav_counts")
        )

        result = await db.execute(
            select(News, func.coalesce(fav_counts.c.fav_count, 0))
            .join(candidate_ids, candidate_ids.c.id == News.id)
            .outerjoin(fav_counts, fav_counts.c.news_id == News.id)
        )

        rows = cast(list[tuple[News, int]], result.all())
        candidates: list[News] = [row[0] for row in rows]
        if not candidates:
            return []

        fav_map = {int(news.id): int(count or 0) for news, count in rows}

        now = datetime.now()

        def age_hours(news: News) -> float:
            ts = news.published_at or news.created_at
            now_local = now
            if ts.tzinfo is not None and now_local.tzinfo is None:
                now_local = now_local.replace(tzinfo=ts.tzinfo)
            if ts.tzinfo is None and now_local.tzinfo is not None:
                now_local = now_local.replace(tzinfo=None)
            delta = now_local - ts
            return max(0.0, float(delta.total_seconds()) / 3600.0)

        def hot_score(news: News) -> float:
            fav = fav_map.get(int(news.id), 0)
            base = float(int(news.view_count or 0) + fav * 5)
            hours = age_hours(news)
            return float(base) / math.pow(hours + 2.0, 1.3)

        candidates.sort(
            key=lambda n: (
                hot_score(n),
                int(n.view_count or 0),
                -age_hours(n),
            ),
            reverse=True,
        )

        top = candidates[: int(limit)]
        NewsService._hot_cache[cache_key] = (now_ts, [int(n.id) for n in top])
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "news.hot cache_miss days=%s category=%s kw=%s limit=%s cached=%s",
                int(days),
                str(category) if category is not None else None,
                kw if kw else None,
                int(limit),
                len(top),
            )
        return top

    @staticmethod
    async def list_subscriptions(db: AsyncSession, user_id: int) -> list[NewsSubscription]:
        result = await db.execute(
            select(NewsSubscription)
            .where(NewsSubscription.user_id == user_id)
            .order_by(desc(NewsSubscription.created_at))
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_subscription(
        db: AsyncSession,
        user_id: int,
        sub_type: str,
        value: str,
    ) -> NewsSubscription:
        sub = NewsSubscription(user_id=int(user_id), sub_type=str(sub_type), value=str(value))
        db.add(sub)
        try:
            await db.commit()
            await db.refresh(sub)
            NewsService.invalidate_recommended_cache(int(user_id))
            return sub
        except IntegrityError:
            await db.rollback()

        result = await db.execute(
            select(NewsSubscription).where(
                and_(
                    NewsSubscription.user_id == user_id,
                    NewsSubscription.sub_type == sub_type,
                    NewsSubscription.value == value,
                )
            )
        )
        existing: NewsSubscription = result.scalar_one()
        NewsService.invalidate_recommended_cache(int(user_id))
        return existing

    @staticmethod
    async def delete_subscription(db: AsyncSession, user_id: int, sub_id: int) -> bool:
        result = await db.execute(
            select(NewsSubscription).where(
                and_(NewsSubscription.id == sub_id, NewsSubscription.user_id == user_id)
            )
        )
        sub: NewsSubscription | None = result.scalar_one_or_none()
        if sub is None:
            return False
        await db.delete(sub)
        await db.commit()
        NewsService.invalidate_recommended_cache(int(user_id))
        return True

    @staticmethod
    async def get_subscribed_news(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None,
        ai_risk_level: str | None = None,
        source_site: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> tuple[list[News], int]:
        subs = await NewsService.list_subscriptions(db, int(user_id))
        categories = [str(s.value) for s in subs if str(s.sub_type) == "category" and str(s.value).strip()]
        keywords = [str(s.value) for s in subs if str(s.sub_type) == "keyword" and str(s.value).strip()]

        if not categories and not keywords:
            return [], 0

        sub_conditions: list[ColumnElement[bool]] = []
        if categories:
            sub_conditions.append(News.category.in_(categories))

        if keywords:
            keyword_groups: list[ColumnElement[bool]] = []
            for kw in keywords:
                kw_clean = str(kw or "").strip()
                if not kw_clean:
                    continue
                pattern = f"%{NewsService._escape_like(kw_clean)}%"
                keyword_groups.append(
                    or_(
                        News.title.ilike(pattern, escape="\\"),
                        News.summary.ilike(pattern, escape="\\"),
                        News.content.ilike(pattern, escape="\\"),
                    )
                )
            if keyword_groups:
                sub_conditions.append(or_(*keyword_groups))

        if not sub_conditions:
            return [], 0

        conditions: list[ColumnElement[bool]] = [*NewsService._public_news_conditions(), or_(*sub_conditions)]

        if category:
            conditions.append(News.category == category)

        if keyword:
            kw = str(keyword or "").strip()
            pattern = f"%{NewsService._escape_like(kw)}%"
            search_filter = or_(
                News.title.ilike(pattern, escape="\\"),
                News.summary.ilike(pattern, escape="\\"),
                News.content.ilike(pattern, escape="\\"),
                News.source.ilike(pattern, escape="\\"),
                News.author.ilike(pattern, escape="\\"),
            )
            conditions.append(search_filter)

        ss = str(source_site or "").strip()
        if ss:
            conditions.append(News.source_site == ss)

        ts_expr = func.coalesce(News.published_at, News.created_at)
        if from_dt is not None:
            conditions.append(ts_expr >= from_dt)
        if to_dt is not None:
            conditions.append(ts_expr <= to_dt)

        where_clause = and_(*conditions)

        query = select(News).where(where_clause)
        count_query = select(func.count(News.id)).where(where_clause)

        rl = str(ai_risk_level or "").strip().lower()
        if rl and rl != "all":
            if rl == "unknown":
                query = query.outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    or_(NewsAIAnnotation.risk_level == "unknown", NewsAIAnnotation.id.is_(None))
                )
                count_query = count_query.outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    or_(NewsAIAnnotation.risk_level == "unknown", NewsAIAnnotation.id.is_(None))
                )
            else:
                query = query.join(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    NewsAIAnnotation.risk_level == rl
                )
                count_query = count_query.join(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    NewsAIAnnotation.risk_level == rl
                )

        query = (
            query.order_by(desc(News.is_top), desc(News.published_at), desc(News.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await db.execute(query)
        items = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = int(count_result.scalar() or 0)

        return items, total

    @staticmethod
    async def notify_subscribers_on_publish(db: AsyncSession, news: News) -> int:
        if not getattr(news, "is_published", False):
            return 0

        if str(getattr(news, "review_status", "approved") or "approved") != "approved":
            return 0

        link = f"/news/{int(news.id)}"
        dedupe_key = f"news:{int(news.id)}"

        reasons_by_user: dict[int, set[str]] = {}

        def add_reason(uid: int, reason: str) -> None:
            reasons_by_user.setdefault(int(uid), set()).add(str(reason))

        # category subscribers
        cat_result = await db.execute(
            select(NewsSubscription.user_id).where(
                and_(
                    NewsSubscription.sub_type == "category",
                    NewsSubscription.value == str(news.category),
                )
            )
        )
        cat_rows = cast(list[tuple[int]], cat_result.fetchall())
        for (uid,) in cat_rows:
            add_reason(int(uid), f"分类订阅：{str(news.category)}")

        # keyword subscribers (match in title/summary/content)
        keyword_result = await db.execute(
            select(NewsSubscription.user_id, NewsSubscription.value).where(
                NewsSubscription.sub_type == "keyword"
            )
        )

        haystack = " ".join(
            [
                str(getattr(news, "title", "") or ""),
                str(getattr(news, "summary", "") or ""),
                str(getattr(news, "content", "") or ""),
            ]
        ).lower()

        keyword_rows = cast(list[tuple[int, str | None]], keyword_result.fetchall())
        for uid, kw_value in keyword_rows:
            keyword = str(kw_value or "").strip().lower()
            if not keyword:
                continue
            if keyword in haystack:
                add_reason(int(uid), f"关键词订阅：{keyword}")

        user_ids: set[int] = set(reasons_by_user.keys())

        if not user_ids:
            return 0

        to_create = list(user_ids)

        title = f"订阅命中：{str(news.title)}"
        preview_source = str(getattr(news, "summary", None) or "").strip() or str(
            getattr(news, "content", "") or ""
        ).strip()
        preview = " ".join(preview_source.split())[:120]

        values: list[dict[str, object]] = []
        for uid in to_create:
            content_lines: list[str] = [f"分类：{str(news.category)}"]
            reasons = sorted(list(reasons_by_user.get(int(uid), set())))
            content_lines.extend(reasons)
            if preview:
                content_lines.append(f"摘要：{preview}")
            content = "\n".join(content_lines) if content_lines else None
            values.append(
                {
                    "user_id": int(uid),
                    "type": NotificationType.NEWS,
                    "title": title,
                    "content": content,
                    "link": link,
                    "dedupe_key": dedupe_key,
                    "is_read": False,
                }
            )

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

        result = await db.execute(stmt)
        await db.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    @staticmethod
    async def toggle_favorite(db: AsyncSession, news_id: int, user_id: int) -> tuple[bool, int]:
        result = await db.execute(
            select(NewsFavorite).where(
                and_(NewsFavorite.news_id == news_id, NewsFavorite.user_id == user_id)
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            await db.delete(existing)
            await db.commit()

            count_result = await db.execute(
                select(func.count(NewsFavorite.id)).where(NewsFavorite.news_id == news_id)
            )
            return False, int(count_result.scalar() or 0)

        favorite = NewsFavorite(news_id=news_id, user_id=user_id)
        db.add(favorite)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()

        count_result = await db.execute(
            select(func.count(NewsFavorite.id)).where(NewsFavorite.news_id == news_id)
        )
        return True, int(count_result.scalar() or 0)

    @staticmethod
    async def is_favorited(db: AsyncSession, news_id: int, user_id: int) -> bool:
        result = await db.execute(
            select(NewsFavorite).where(
                and_(NewsFavorite.news_id == news_id, NewsFavorite.user_id == user_id)
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_favorite_count(db: AsyncSession, news_id: int) -> int:
        result = await db.execute(
            select(func.count(NewsFavorite.id)).where(NewsFavorite.news_id == news_id)
        )
        return int(result.scalar() or 0)

    @staticmethod
    async def get_favorite_counts(db: AsyncSession, news_ids: Sequence[int]) -> dict[int, int]:
        ids = [int(i) for i in news_ids]
        if not ids:
            return {}

        result = await db.execute(
            select(NewsFavorite.news_id, func.count(NewsFavorite.id))
            .where(NewsFavorite.news_id.in_(ids))
            .group_by(NewsFavorite.news_id)
        )
        rows = cast(list[tuple[int, int]], result.all())
        return {int(news_id): int(count or 0) for news_id, count in rows}

    @staticmethod
    async def get_favorite_stats(
        db: AsyncSession,
        news_ids: Sequence[int],
        user_id: int | None = None,
    ) -> dict[int, tuple[int, bool]]:
        ids = [int(i) for i in news_ids]
        if not ids:
            return {}

        if user_id is None:
            result = await db.execute(
                select(NewsFavorite.news_id, func.count(NewsFavorite.id))
                .where(NewsFavorite.news_id.in_(ids))
                .group_by(NewsFavorite.news_id)
            )
            rows = cast(list[tuple[int, int]], result.all())
            return {int(news_id): (int(count or 0), False) for news_id, count in rows}

        is_fav_expr = func.max(
            case(
                (NewsFavorite.user_id == int(user_id), 1),
                else_=0,
            )
        )
        result2 = await db.execute(
            select(NewsFavorite.news_id, func.count(NewsFavorite.id), is_fav_expr)
            .where(NewsFavorite.news_id.in_(ids))
            .group_by(NewsFavorite.news_id)
        )
        rows2 = cast(list[tuple[int, int, int]], result2.all())
        return {int(news_id): (int(count or 0), bool(is_fav)) for news_id, count, is_fav in rows2}

    @staticmethod
    async def get_favorited_news_ids(
        db: AsyncSession,
        news_ids: Sequence[int],
        user_id: int,
    ) -> set[int]:
        ids = [int(i) for i in news_ids]
        if not ids:
            return set()

        result = await db.execute(
            select(NewsFavorite.news_id).where(
                and_(
                    NewsFavorite.news_id.in_(ids),
                    NewsFavorite.user_id == int(user_id),
                )
            )
        )
        rows = cast(list[tuple[int]], result.all())
        return {int(news_id) for (news_id,) in rows}

    @staticmethod
    async def get_user_favorites(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None,
        ai_risk_level: str | None = None,
        source_site: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> tuple[list[News], int]:
        query = (
            select(News)
            .join(NewsFavorite, News.id == NewsFavorite.news_id)
            .where(
                and_(
                    NewsFavorite.user_id == user_id,
                    *NewsService._public_news_conditions(),
                )
            )
            .order_by(desc(NewsFavorite.created_at))
        )

        if category:
            query = query.where(News.category == category)
        if keyword:
            search_filter = News.title.contains(keyword) | News.content.contains(keyword)
            query = query.where(search_filter)

        ss = str(source_site or "").strip()
        if ss:
            query = query.where(News.source_site == ss)

        ts_expr = func.coalesce(News.published_at, News.created_at)
        if from_dt is not None:
            query = query.where(ts_expr >= from_dt)
        if to_dt is not None:
            query = query.where(ts_expr <= to_dt)

        rl = str(ai_risk_level or "").strip().lower()
        if rl and rl != "all":
            if rl == "unknown":
                query = query.outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    or_(NewsAIAnnotation.risk_level == "unknown", NewsAIAnnotation.id.is_(None))
                )
            else:
                query = query.join(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    NewsAIAnnotation.risk_level == rl
                )

        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        items = list(result.scalars().all())

        count_query = (
            select(func.count(NewsFavorite.id))
            .join(News, News.id == NewsFavorite.news_id)
            .where(
                and_(
                    NewsFavorite.user_id == user_id,
                    *NewsService._public_news_conditions(),
                )
            )
        )

        if category:
            count_query = count_query.where(News.category == category)
        if keyword:
            search_filter = News.title.contains(keyword) | News.content.contains(keyword)
            count_query = count_query.where(search_filter)

        ss = str(source_site or "").strip()
        if ss:
            count_query = count_query.where(News.source_site == ss)

        ts_expr = func.coalesce(News.published_at, News.created_at)
        if from_dt is not None:
            count_query = count_query.where(ts_expr >= from_dt)
        if to_dt is not None:
            count_query = count_query.where(ts_expr <= to_dt)

        rl = str(ai_risk_level or "").strip().lower()
        if rl and rl != "all":
            if rl == "unknown":
                count_query = count_query.outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    or_(NewsAIAnnotation.risk_level == "unknown", NewsAIAnnotation.id.is_(None))
                )
            else:
                count_query = count_query.join(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                    NewsAIAnnotation.risk_level == rl
                )

        count_result = await db.execute(count_query)
        total = int(count_result.scalar() or 0)

        return items, total

    @staticmethod
    async def get_related_news(
        db: AsyncSession,
        news_id: int,
        limit: int = 6,
    ) -> list[News]:
        """获取相关新闻（同分类优先，不包含当前新闻）"""
        current = await NewsService.get_published(db, news_id)
        if not current:
            return []

        same_category_first = case((News.category == current.category, 0), else_=1)

        result = await db.execute(
            select(News)
            .where(
                and_(
                    *NewsService._public_news_conditions(),
                    News.id != news_id,
                )
            )
            .order_by(same_category_first, desc(News.published_at), desc(News.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_top_news(db: AsyncSession, limit: int = 5) -> list[News]:
        """获取置顶新闻"""
        result = await db.execute(
            select(News)
            .where(and_(*NewsService._public_news_conditions()), News.is_top == True)
            .order_by(desc(News.published_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_recent_news(db: AsyncSession, limit: int = 10) -> list[News]:
        """获取最新新闻"""
        result = await db.execute(
            select(News)
            .where(and_(*NewsService._public_news_conditions()))
            .order_by(desc(News.published_at), desc(News.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_recent_news_filtered(
        db: AsyncSession,
        limit: int = 10,
        category: str | None = None,
        keyword: str | None = None,
    ) -> list[News]:
        """获取最新新闻（支持分类/关键词过滤）"""
        conditions: list[ColumnElement[bool]] = [*NewsService._public_news_conditions()]
        if category:
            conditions.append(News.category == category)

        kw = str(keyword or "").strip()
        if kw:
            pattern = f"%{kw}%"
            conditions.append(
                or_(
                    News.title.ilike(pattern),
                    News.summary.ilike(pattern),
                    News.content.ilike(pattern),
                    News.source.ilike(pattern),
                    News.author.ilike(pattern),
                )
            )

        result = await db.execute(
            select(News)
            .where(and_(*conditions))
            .order_by(desc(News.published_at), desc(News.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_recommended_news(
        db: AsyncSession,
        user_id: int | None,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None,
        ai_risk_level: str | None = None,
        source_site: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> tuple[list[News], int]:
        desired = max(1, int(page)) * max(1, int(page_size))
        needed_fetch_limit = min(300, max(200, desired * 3))

        cat = str(category).strip() if category is not None else None
        kw = str(keyword or "").strip()
        kw_key = kw if kw else None
        cache_key = (
            int(user_id) if user_id is not None else None,
            cat,
            kw_key,
        )

        now_ts = time.time()
        NewsService._prune_cache(
            cast(dict[object, tuple[float, list[int]]], NewsService._recommended_cache),
            int(NewsService._recommended_cache_ttl_seconds),
            float(now_ts),
        )
        cached = NewsService._recommended_cache.get(cache_key)
        if cached is not None:
            cached_at, cached_ids = cached
            if (now_ts - float(cached_at)) <= float(NewsService._recommended_cache_ttl_seconds):
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "news.recommended cache_hit user_id=%s category=%s kw=%s total=%s",
                        int(user_id) if user_id is not None else None,
                        cat,
                        kw_key,
                        len(cached_ids),
                    )
                all_ids = list(cached_ids)
            else:
                all_ids = []
        else:
            all_ids = []

        if not all_ids:
            ordered_ids: list[int] = []
            seen: set[int] = set()

            def add_many_ids(items: Sequence[News]) -> None:
                for n in items:
                    nid = int(getattr(n, "id", 0) or 0)
                    if nid <= 0 or nid in seen:
                        continue
                    seen.add(nid)
                    ordered_ids.append(nid)
                    if len(ordered_ids) >= int(needed_fetch_limit):
                        return

            if user_id is not None:
                subscribed_items, _ = await NewsService.get_subscribed_news(
                    db,
                    int(user_id),
                    page=1,
                    page_size=min(200, needed_fetch_limit),
                    category=cat,
                    keyword=kw_key,
                )
                add_many_ids(subscribed_items)

            hot_items = await NewsService.get_hot_news(
                db,
                days=30,
                limit=min(200, needed_fetch_limit),
                category=cat,
                keyword=kw_key,
            )
            add_many_ids(hot_items)

            recent_items = await NewsService.get_recent_news_filtered(
                db,
                limit=min(200, needed_fetch_limit),
                category=cat,
                keyword=kw_key,
            )
            add_many_ids(recent_items)

            all_ids = list(ordered_ids)
            NewsService._recommended_cache[cache_key] = (now_ts, list(all_ids))
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "news.recommended cache_miss user_id=%s category=%s kw=%s total=%s",
                    int(user_id) if user_id is not None else None,
                    cat,
                    kw_key,
                    len(all_ids),
                )

        ss = str(source_site or "").strip()
        rl = str(ai_risk_level or "").strip().lower()

        if all_ids and (ss or (rl and rl != "all") or (from_dt is not None) or (to_dt is not None)):
            q = select(News.id).where(News.id.in_(all_ids))
            if ss:
                q = q.where(News.source_site == ss)

            ts_expr = func.coalesce(News.published_at, News.created_at)
            if from_dt is not None:
                q = q.where(ts_expr >= from_dt)
            if to_dt is not None:
                q = q.where(ts_expr <= to_dt)

            if rl and rl != "all":
                if rl == "unknown":
                    q = q.outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                        or_(NewsAIAnnotation.risk_level == "unknown", NewsAIAnnotation.id.is_(None))
                    )
                else:
                    q = q.join(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id).where(
                        NewsAIAnnotation.risk_level == rl
                    )

            allow_res = await db.execute(q)
            allowed = {int(x) for x in allow_res.scalars().all()}
            if allowed:
                all_ids = [i for i in all_ids if i in allowed]
            else:
                all_ids = []

        total = len(all_ids)
        start = max(0, (int(page) - 1) * int(page_size))
        end = start + int(page_size)
        page_ids = all_ids[start:end]
        if not page_ids:
            return [], int(total)

        res = await db.execute(select(News).where(News.id.in_(page_ids)))
        rows = list(res.scalars().all())
        by_id = {int(n.id): n for n in rows}
        page_items = [by_id[i] for i in page_ids if i in by_id]
        return page_items, int(total)

    @staticmethod
    async def list_topics(db: AsyncSession, active_only: bool = True) -> list[NewsTopic]:
        query = select(NewsTopic)
        if active_only:
            query = query.where(NewsTopic.is_active == True)
        query = query.order_by(desc(NewsTopic.sort_order), desc(NewsTopic.created_at))
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_topic(db: AsyncSession, topic_id: int) -> NewsTopic | None:
        result = await db.execute(select(NewsTopic).where(NewsTopic.id == int(topic_id)))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_topic(db: AsyncSession, data: dict[str, object]) -> NewsTopic:
        raw_sort_order = data.get("sort_order")
        sort_order = 0
        if isinstance(raw_sort_order, (int, float, str)):
            try:
                sort_order = int(raw_sort_order)
            except (TypeError, ValueError):
                sort_order = 0

        raw_auto_limit = data.get("auto_limit")
        auto_limit = 0
        if isinstance(raw_auto_limit, (int, float, str)):
            try:
                auto_limit = int(raw_auto_limit)
            except (TypeError, ValueError):
                auto_limit = 0

        topic = NewsTopic(
            title=str(data.get("title") or ""),
            description=(str(data.get("description")) if data.get("description") is not None else None),
            cover_image=(str(data.get("cover_image")) if data.get("cover_image") is not None else None),
            is_active=bool(data.get("is_active", True)),
            sort_order=int(sort_order),
            auto_category=(str(data.get("auto_category")) if data.get("auto_category") is not None else None),
            auto_keyword=(str(data.get("auto_keyword")) if data.get("auto_keyword") is not None else None),
            auto_limit=int(auto_limit),
        )
        db.add(topic)
        await db.commit()
        await db.refresh(topic)
        return topic

    @staticmethod
    async def update_topic(db: AsyncSession, topic: NewsTopic, data: dict[str, object]) -> NewsTopic:
        before_auto_category = str(getattr(topic, "auto_category", "") or "")
        before_auto_keyword = str(getattr(topic, "auto_keyword", "") or "")
        before_auto_limit = int(getattr(topic, "auto_limit", 0) or 0)
        for field in (
            "title",
            "description",
            "cover_image",
            "is_active",
            "sort_order",
            "auto_category",
            "auto_keyword",
            "auto_limit",
        ):
            if field not in data:
                continue
            setattr(topic, field, data[field])
        await db.commit()
        await db.refresh(topic)

        after_auto_category = str(getattr(topic, "auto_category", "") or "")
        after_auto_keyword = str(getattr(topic, "auto_keyword", "") or "")
        after_auto_limit = int(getattr(topic, "auto_limit", 0) or 0)
        if (
            before_auto_category != after_auto_category
            or before_auto_keyword != after_auto_keyword
            or before_auto_limit != after_auto_limit
        ):
            NewsService.invalidate_topic_auto_cache(int(topic.id))
        return topic

    @staticmethod
    async def delete_topic(db: AsyncSession, topic_id: int) -> None:
        _ = await db.execute(delete(NewsTopicItem).where(NewsTopicItem.topic_id == int(topic_id)))
        _ = await db.execute(delete(NewsTopic).where(NewsTopic.id == int(topic_id)))
        await db.commit()
        NewsService.invalidate_topic_auto_cache(int(topic_id))

    @staticmethod
    async def list_topic_items_brief(
        db: AsyncSession,
        topic_id: int,
    ) -> list[tuple[int, int, int, str, str]]:
        result = await db.execute(
            select(
                NewsTopicItem.id,
                NewsTopicItem.news_id,
                NewsTopicItem.position,
                News.title,
                News.category,
            )
            .join(News, News.id == NewsTopicItem.news_id)
            .where(NewsTopicItem.topic_id == int(topic_id))
            .order_by(NewsTopicItem.position.asc(), desc(News.published_at), desc(News.created_at))
        )
        return cast(list[tuple[int, int, int, str, str]], result.all())

    @staticmethod
    async def add_topic_item(
        db: AsyncSession,
        topic_id: int,
        news_id: int,
        position: int | None = None,
    ) -> NewsTopicItem:
        pos = position
        if pos is None:
            max_result = await db.execute(
                select(func.coalesce(func.max(NewsTopicItem.position), 0)).where(
                    NewsTopicItem.topic_id == int(topic_id)
                )
            )
            raw_max = max_result.scalar()
            max_pos = int(raw_max) if isinstance(raw_max, (int, float, str)) else 0
            pos = int(max_pos) + 1

        item = NewsTopicItem(topic_id=int(topic_id), news_id=int(news_id), position=int(pos))
        db.add(item)
        await db.commit()
        await db.refresh(item)
        NewsService.invalidate_topic_auto_cache(int(topic_id))
        return item

    @staticmethod
    async def add_topic_items_bulk(
        db: AsyncSession,
        topic_id: int,
        news_ids: Sequence[int],
        position_start: int | None = None,
    ) -> tuple[int, int, int]:
        ids_raw = [int(i) for i in news_ids]
        seen: set[int] = set()
        ids: list[int] = []
        for i in ids_raw:
            if i <= 0:
                continue
            if i in seen:
                continue
            seen.add(i)
            ids.append(i)

        requested = len(ids)
        if requested == 0:
            return 0, 0, 0

        existing_result = await db.execute(
            select(NewsTopicItem.news_id).where(
                and_(NewsTopicItem.topic_id == int(topic_id), NewsTopicItem.news_id.in_(ids))
            )
        )
        existing_rows = cast(list[tuple[int]], existing_result.all())
        existing_ids = {int(v) for (v,) in existing_rows}
        to_add = [i for i in ids if i not in existing_ids]

        if not to_add:
            return requested, 0, requested

        max_result = await db.execute(
            select(func.coalesce(func.max(NewsTopicItem.position), 0)).where(
                NewsTopicItem.topic_id == int(topic_id)
            )
        )
        raw_max = max_result.scalar()
        max_pos = int(raw_max) if isinstance(raw_max, (int, float, str)) else 0
        start_pos = int(position_start) if position_start is not None else max_pos + 1

        values = [
            {
                "topic_id": int(topic_id),
                "news_id": int(nid),
                "position": int(start_pos + idx),
            }
            for idx, nid in enumerate(to_add)
        ]

        bind = db.get_bind()
        dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "") or "")

        if dialect_name == "postgresql":
            stmt = pg_insert(NewsTopicItem).values(values).on_conflict_do_nothing(
                constraint="uq_news_topic_items_topic_news"
            )
        else:
            stmt = sqlite_insert(NewsTopicItem).values(values).on_conflict_do_nothing(
                index_elements=["topic_id", "news_id"]
            )

        result = await db.execute(stmt)
        await db.commit()

        NewsService.invalidate_topic_auto_cache(int(topic_id))

        added = int(getattr(result, "rowcount", 0) or 0)
        skipped = requested - added
        return requested, added, skipped

    @staticmethod
    async def update_topic_item_position(db: AsyncSession, topic_id: int, item_id: int, position: int) -> bool:
        result = await db.execute(
            update(NewsTopicItem)
            .where(and_(NewsTopicItem.id == int(item_id), NewsTopicItem.topic_id == int(topic_id)))
            .values(position=int(position))
        )
        await db.commit()
        if bool(getattr(result, "rowcount", 0) or 0):
            NewsService.invalidate_topic_auto_cache(int(topic_id))
        return bool(getattr(result, "rowcount", 0) or 0)

    @staticmethod
    async def remove_topic_item(db: AsyncSession, topic_id: int, item_id: int) -> bool:
        result = await db.execute(
            delete(NewsTopicItem).where(
                and_(NewsTopicItem.id == int(item_id), NewsTopicItem.topic_id == int(topic_id))
            )
        )
        await db.commit()
        return bool(getattr(result, "rowcount", 0) or 0)

    @staticmethod
    async def remove_topic_items_bulk(
        db: AsyncSession,
        topic_id: int,
        item_ids: Sequence[int],
    ) -> tuple[int, int, int]:
        ids_raw = [int(i) for i in item_ids]
        seen: set[int] = set()
        ids: list[int] = []
        for i in ids_raw:
            if i <= 0:
                continue
            if i in seen:
                continue
            seen.add(i)
            ids.append(i)

        requested = len(ids)
        if requested == 0:
            return 0, 0, 0

        result = await db.execute(
            delete(NewsTopicItem).where(
                and_(NewsTopicItem.topic_id == int(topic_id), NewsTopicItem.id.in_(ids))
            )
        )
        await db.commit()
        deleted_count = int(getattr(result, "rowcount", 0) or 0)
        if deleted_count:
            NewsService.invalidate_topic_auto_cache(int(topic_id))
        skipped = requested - deleted_count
        return requested, deleted_count, skipped

    @staticmethod
    async def reindex_topic_items(db: AsyncSession, topic_id: int) -> int:
        t_id = int(topic_id)
        res = await db.execute(
            select(NewsTopicItem.id)
            .where(NewsTopicItem.topic_id == t_id)
            .order_by(NewsTopicItem.position.asc(), NewsTopicItem.id.asc())
        )
        rows = cast(list[tuple[int]], res.all())
        ids = [int(v) for (v,) in rows]
        if not ids:
            return 0

        mapping = {int(item_id): int(idx + 1) for idx, item_id in enumerate(ids)}
        stmt = (
            update(NewsTopicItem)
            .where(and_(NewsTopicItem.topic_id == t_id, NewsTopicItem.id.in_(ids)))
            .values(position=case(mapping, value=NewsTopicItem.id))
        )
        upd = await db.execute(stmt)
        await db.commit()
        if int(getattr(upd, "rowcount", 0) or 0):
            NewsService.invalidate_topic_auto_cache(int(topic_id))
        return int(getattr(upd, "rowcount", 0) or 0)

    @staticmethod
    async def reorder_topic_items(db: AsyncSession, topic_id: int, item_ids: Sequence[int]) -> int:
        t_id = int(topic_id)
        ids_raw = [int(i) for i in item_ids]
        seen: set[int] = set()
        ids: list[int] = []
        for i in ids_raw:
            if i <= 0:
                continue
            if i in seen:
                continue
            seen.add(i)
            ids.append(i)

        if not ids:
            return 0

        exist_res = await db.execute(select(NewsTopicItem.id).where(NewsTopicItem.topic_id == t_id))
        exist_rows = cast(list[tuple[int]], exist_res.all())
        exist_ids = {int(v) for (v,) in exist_rows}
        if exist_ids and set(ids) != exist_ids:
            return 0

        mapping = {int(item_id): int(idx + 1) for idx, item_id in enumerate(ids)}
        stmt = (
            update(NewsTopicItem)
            .where(and_(NewsTopicItem.topic_id == t_id, NewsTopicItem.id.in_(ids)))
            .values(position=case(mapping, value=NewsTopicItem.id))
        )
        upd = await db.execute(stmt)
        await db.commit()
        updated = int(getattr(upd, "rowcount", 0) or 0)
        if updated:
            NewsService.invalidate_topic_auto_cache(int(topic_id))
        return updated

    @staticmethod
    async def get_topics_report(
        db: AsyncSession,
    ) -> list[tuple[int, str, bool, int, int, int, int]]:
        item_counts = (
            select(
                NewsTopicItem.topic_id.label("topic_id"),
                func.count(NewsTopicItem.id).label("item_count"),
            )
            .group_by(NewsTopicItem.topic_id)
            .subquery()
        )

        view_sums = (
            select(
                NewsTopicItem.topic_id.label("topic_id"),
                func.coalesce(func.sum(News.view_count), 0).label("view_sum"),
            )
            .join(News, News.id == NewsTopicItem.news_id)
            .group_by(NewsTopicItem.topic_id)
            .subquery()
        )

        fav_sums = (
            select(
                NewsTopicItem.topic_id.label("topic_id"),
                func.count(NewsFavorite.id).label("fav_sum"),
            )
            .join(NewsFavorite, NewsFavorite.news_id == NewsTopicItem.news_id)
            .group_by(NewsTopicItem.topic_id)
            .subquery()
        )

        q = (
            select(
                NewsTopic.id,
                NewsTopic.title,
                NewsTopic.is_active,
                NewsTopic.sort_order,
                func.coalesce(item_counts.c.item_count, 0),
                func.coalesce(view_sums.c.view_sum, 0),
                func.coalesce(fav_sums.c.fav_sum, 0),
            )
            .outerjoin(item_counts, item_counts.c.topic_id == NewsTopic.id)
            .outerjoin(view_sums, view_sums.c.topic_id == NewsTopic.id)
            .outerjoin(fav_sums, fav_sums.c.topic_id == NewsTopic.id)
            .order_by(desc(NewsTopic.is_active), desc(NewsTopic.sort_order), desc(NewsTopic.created_at))
        )

        result = await db.execute(q)
        return cast(list[tuple[int, str, bool, int, int, int, int]], result.all())

    @staticmethod
    async def get_topic_news(
        db: AsyncSession,
        topic_id: int,
        page: int = 1,
        page_size: int = 20,
        published_only: bool = True,
    ) -> tuple[list[News], int]:
        t_id = int(topic_id)
        p = max(1, int(page))
        ps = max(1, int(page_size))
        offset = (p - 1) * ps

        manual_conditions: list[ColumnElement[bool]] = [NewsTopicItem.topic_id == t_id]
        if published_only:
            manual_conditions.extend(NewsService._public_news_conditions())

        manual_where = and_(*manual_conditions)

        manual_count_result = await db.execute(
            select(func.count(NewsTopicItem.id))
            .select_from(NewsTopicItem)
            .join(News, News.id == NewsTopicItem.news_id)
            .where(manual_where)
        )
        manual_total = int(manual_count_result.scalar() or 0)

        manual_items: list[News] = []
        if offset < manual_total:
            manual_limit = min(ps, manual_total - offset)
            manual_query = (
                select(News)
                .join(NewsTopicItem, NewsTopicItem.news_id == News.id)
                .where(manual_where)
                .order_by(NewsTopicItem.position.asc(), desc(News.published_at), desc(News.created_at))
                .offset(int(offset))
                .limit(int(manual_limit))
            )
            manual_result = await db.execute(manual_query)
            manual_items = list(manual_result.scalars().all())

        remaining = ps - len(manual_items)

        topic = await NewsService.get_topic(db, t_id)
        auto_items: list[News] = []
        auto_total = 0

        if topic:
            auto_limit = int(getattr(topic, "auto_limit", 0) or 0)
            auto_category = str(getattr(topic, "auto_category", "") or "").strip()
            auto_keyword = str(getattr(topic, "auto_keyword", "") or "").strip()

            if remaining > 0 and auto_limit > 0 and (auto_category or auto_keyword):
                auto_ids = await NewsService.get_topic_auto_ids_cached(db, topic, bool(published_only))
                if auto_ids:
                    manual_ids_subq = select(NewsTopicItem.news_id).where(NewsTopicItem.topic_id == t_id)
                    auto_total_result = await db.execute(
                        select(func.count(News.id)).where(
                            and_(
                                News.id.in_(auto_ids),
                                ~News.id.in_(manual_ids_subq),
                            )
                        )
                    )
                    auto_total = int(auto_total_result.scalar() or 0)

                    auto_offset = max(0, int(offset) - manual_total)
                    if auto_offset < auto_total:
                        order_map = {int(nid): int(idx) for idx, nid in enumerate(auto_ids)}
                        auto_query = (
                            select(News)
                            .where(and_(News.id.in_(auto_ids), ~News.id.in_(manual_ids_subq)))
                            .order_by(case(order_map, value=News.id))
                            .offset(int(auto_offset))
                            .limit(int(remaining))
                        )
                        auto_result = await db.execute(auto_query)
                        auto_items = list(auto_result.scalars().all())

        total = manual_total + auto_total
        return manual_items + auto_items, int(total)

    @staticmethod
    async def create_comment(
        db: AsyncSession,
        news_id: int,
        user_id: int,
        content: str,
        review_status: str = "approved",
        review_reason: str | None = None,
    ) -> NewsComment:
        now = datetime.now()
        reviewed_at: datetime | None = None
        if str(review_status) in {"approved", "rejected"}:
            reviewed_at = now
        comment = NewsComment(
            news_id=int(news_id),
            user_id=int(user_id),
            content=str(content),
            review_status=str(review_status),
            review_reason=str(review_reason) if review_reason is not None else None,
            reviewed_at=reviewed_at,
        )
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        return comment

    @staticmethod
    async def get_comment(db: AsyncSession, comment_id: int) -> NewsComment | None:
        result = await db.execute(
            select(NewsComment)
            .options(joinedload(NewsComment.author), joinedload(NewsComment.news))
            .execution_options(populate_existing=True)
            .where(NewsComment.id == int(comment_id))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def delete_comment(db: AsyncSession, comment: NewsComment) -> None:
        comment.is_deleted = True
        await db.commit()

    @staticmethod
    async def get_comments(
        db: AsyncSession,
        news_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NewsComment], int]:
        base_filter = and_(
            NewsComment.news_id == int(news_id),
            NewsComment.is_deleted == False,
            NewsComment.review_status == "approved",
        )

        total_result = await db.execute(select(func.count(NewsComment.id)).where(base_filter))
        total = int(total_result.scalar() or 0)

        query = (
            select(NewsComment)
            .options(joinedload(NewsComment.author))
            .where(base_filter)
            .order_by(desc(NewsComment.created_at))
            .offset((int(page) - 1) * int(page_size))
            .limit(int(page_size))
        )

        result = await db.execute(query)
        items = list(result.scalars().all())
        return items, total

    @staticmethod
    async def list_comments_admin(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        review_status: str | None = None,
        news_id: int | None = None,
        user_id: int | None = None,
        keyword: str | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[NewsComment], int]:
        p = max(1, int(page))
        ps = max(1, int(page_size))

        conditions: list[ColumnElement[bool]] = []
        if not include_deleted:
            conditions.append(NewsComment.is_deleted == False)

        rs = str(review_status or "").strip().lower()
        if rs:
            conditions.append(NewsComment.review_status == rs)

        if news_id is not None:
            conditions.append(NewsComment.news_id == int(news_id))
        if user_id is not None:
            conditions.append(NewsComment.user_id == int(user_id))

        kw = str(keyword or "").strip()
        if kw:
            pattern = f"%{kw}%"
            conditions.append(NewsComment.content.ilike(pattern))

        where_clause: ColumnElement[bool]
        where_clause = and_(*conditions) if conditions else true()

        total_result = await db.execute(select(func.count(NewsComment.id)).where(where_clause))
        total = int(total_result.scalar() or 0)

        query = (
            select(NewsComment)
            .options(joinedload(NewsComment.author), joinedload(NewsComment.news))
            .where(where_clause)
            .order_by(desc(NewsComment.created_at), desc(NewsComment.id))
            .offset((p - 1) * ps)
            .limit(ps)
        )
        result = await db.execute(query)
        items = list(result.scalars().all())
        return items, total

    @staticmethod
    async def review_comment_admin(
        db: AsyncSession,
        comment_id: int,
        action: str,
        reason: str | None = None,
        admin_user_id: int | None = None,
    ) -> NewsComment | None:
        comment = await NewsService.get_comment(db, int(comment_id))
        if comment is None:
            return None

        act = str(action or "").strip().lower()
        rsn = str(reason).strip() if reason is not None else None
        now = datetime.now()

        if act == "approve":
            comment.is_deleted = False
            comment.review_status = "approved"
            comment.review_reason = rsn
            comment.reviewed_at = now
            title = "你的新闻评论已通过审核"
        elif act in {"reject", "delete"}:
            comment.is_deleted = True
            comment.review_status = "rejected"
            comment.review_reason = rsn
            comment.reviewed_at = now
            title = "你的新闻评论未通过审核" if act == "reject" else "你的新闻评论已被删除"
        else:
            raise ValueError("invalid action")

        await db.commit()
        await db.refresh(comment)

        content_lines: list[str] = [f"评论ID：{int(comment.id)}", f"新闻ID：{int(comment.news_id)}"]
        if rsn:
            content_lines.append(f"原因：{rsn}")
        link = f"/news/{int(comment.news_id)}"

        dedupe_key = f"news_comment:{int(comment.id)}:{act}"

        try:
            db.add(
                Notification(
                    user_id=int(comment.user_id),
                    type=NotificationType.SYSTEM,
                    title=title,
                    content="\n".join(content_lines) if content_lines else None,
                    link=link,
                    dedupe_key=dedupe_key,
                    related_user_id=int(admin_user_id) if admin_user_id is not None else None,
                    related_comment_id=int(comment.id),
                )
            )
            await db.commit()
        except Exception:
            await db.rollback()
        reloaded = await NewsService.get_comment(db, int(comment.id))
        return reloaded if reloaded is not None else comment


news_service = NewsService()
