"""新闻服务层"""
import math
from collections.abc import Sequence
from datetime import datetime, timedelta
import time
from typing import cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update, and_, or_, case, delete
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
from ..models.notification import Notification, NotificationType
from ..schemas.news import NewsCreate, NewsUpdate


class NewsService:
    """新闻服务"""

    _hot_cache: dict[tuple[int, str | None, str | None], tuple[float, list[int]]] = {}
    _hot_cache_ttl_seconds: int = 60

    _topic_auto_cache: dict[tuple[int, bool], tuple[float, list[int]]] = {}
    _topic_auto_cache_ttl_seconds: int = 120

    _recommended_cache: dict[tuple[int | None, str | None, str | None], tuple[float, list[int]]] = {}
    _recommended_cache_ttl_seconds: int = 60

    @staticmethod
    def invalidate_hot_cache() -> None:
        NewsService._hot_cache.clear()

    @staticmethod
    def invalidate_recommended_cache(user_id: int | None) -> None:
        keys = [k for k in NewsService._recommended_cache.keys() if k[0] == (int(user_id) if user_id is not None else None)]
        for k in keys:
            NewsService._recommended_cache.pop(k, None)

    @staticmethod
    def invalidate_topic_auto_cache(topic_id: int) -> None:
        keys = [k for k in NewsService._topic_auto_cache.keys() if int(k[0]) == int(topic_id)]
        for k in keys:
            NewsService._topic_auto_cache.pop(k, None)

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
            auto_conditions.append(News.is_published == True)
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
        return [int(r[0]) for r in res.all()]

    @staticmethod
    async def get_topic_auto_ids_cached(
        db: AsyncSession,
        topic: NewsTopic,
        published_only: bool,
        force_refresh: bool = False,
    ) -> list[int]:
        key = (int(topic.id), bool(published_only))
        now_ts = time.time()
        if not force_refresh:
            cached = NewsService._topic_auto_cache.get(key)
            if cached is not None:
                cached_at, cached_ids = cached
                if (now_ts - float(cached_at)) <= float(NewsService._topic_auto_cache_ttl_seconds):
                    return list(cached_ids)

        ids = await NewsService._compute_topic_auto_ids(db, topic, bool(published_only))
        NewsService._topic_auto_cache[key] = (now_ts, list(ids))
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
    async def create(db: AsyncSession, news_data: NewsCreate) -> News:
        """创建新闻"""
        now = datetime.now()
        scheduled_publish_at = news_data.scheduled_publish_at
        scheduled_unpublish_at = news_data.scheduled_unpublish_at
        is_published = bool(news_data.is_published)
        published_at = now if is_published else None

        if scheduled_publish_at is not None:
            if scheduled_publish_at > now:
                is_published = False
                published_at = None
            else:
                is_published = True
                published_at = now

        if scheduled_unpublish_at is not None and scheduled_unpublish_at <= now:
            is_published = False

        news = News(
            title=news_data.title,
            summary=news_data.summary,
            content=news_data.content,
            cover_image=news_data.cover_image,
            category=news_data.category,
            source=news_data.source,
            author=news_data.author,
            is_top=news_data.is_top,
            is_published=is_published,
            published_at=published_at,
            scheduled_publish_at=scheduled_publish_at,
            scheduled_unpublish_at=scheduled_unpublish_at,
        )
        db.add(news)
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
            select(News).where(News.id == news_id, News.is_published == True)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None,
        published_only: bool = True
    ) -> tuple[list[News], int]:
        """获取新闻列表"""
        query = select(News)
        count_query = select(func.count(News.id))
        
        if published_only:
            query = query.where(News.is_published == True)
            count_query = count_query.where(News.is_published == True)
        
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
        
        # 置顶优先，然后按发布时间倒序
        query = query.order_by(desc(News.is_top), desc(News.published_at), desc(News.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        news_list = result.scalars().all()
        
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0
        
        return list(news_list), int(total)
    
    @staticmethod
    async def update(db: AsyncSession, news: News, news_data: NewsUpdate) -> News:
        """更新新闻"""
        update_data: dict[str, object] = news_data.model_dump(exclude_unset=True)

        now = datetime.now()

        scheduled_publish_at = update_data.get("scheduled_publish_at")
        if isinstance(scheduled_publish_at, datetime):
            if scheduled_publish_at > now:
                update_data["is_published"] = False
            else:
                update_data["is_published"] = True
                _ = update_data.setdefault("published_at", now)

        scheduled_unpublish_at = update_data.get("scheduled_unpublish_at")
        if isinstance(scheduled_unpublish_at, datetime) and scheduled_unpublish_at <= now:
            update_data["is_published"] = False

        is_published_value = update_data.get("is_published")
        if isinstance(is_published_value, bool) and is_published_value and not news.is_published:
            _ = update_data.setdefault("published_at", now)
        
        for field, value in update_data.items():
            setattr(news, field, value)
        
        await db.commit()
        await db.refresh(news)
        return news

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
    ) -> tuple[list[News], int]:
        query = (
            select(News)
            .join(NewsViewHistory, News.id == NewsViewHistory.news_id)
            .where(
                and_(
                    NewsViewHistory.user_id == user_id,
                    News.is_published == True,
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
                    News.is_published == True,
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
            .where(News.is_published == True)
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
                return [by_id[i] for i in ids if i in by_id]

        since = datetime.now() - timedelta(days=days)

        conditions: list[ColumnElement[bool]] = [
            News.is_published == True,
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

        result = await db.execute(
            select(News, func.count(NewsFavorite.id))
            .join(candidate_ids, candidate_ids.c.id == News.id)
            .outerjoin(NewsFavorite, NewsFavorite.news_id == News.id)
            .group_by(News.id)
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
                pattern = f"%{kw_clean}%"
                keyword_groups.append(
                    or_(
                        News.title.ilike(pattern),
                        News.summary.ilike(pattern),
                        News.content.ilike(pattern),
                    )
                )
            if keyword_groups:
                sub_conditions.append(or_(*keyword_groups))

        if not sub_conditions:
            return [], 0

        conditions: list[ColumnElement[bool]] = [News.is_published == True, or_(*sub_conditions)]

        if category:
            conditions.append(News.category == category)

        if keyword:
            pattern = f"%{keyword}%"
            search_filter = or_(
                News.title.ilike(pattern),
                News.summary.ilike(pattern),
                News.content.ilike(pattern),
                News.source.ilike(pattern),
                News.author.ilike(pattern),
            )
            conditions.append(search_filter)

        where_clause = and_(*conditions)

        query = (
            select(News)
            .where(where_clause)
            .order_by(desc(News.is_top), desc(News.published_at), desc(News.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_query = select(func.count(News.id)).where(where_clause)

        result = await db.execute(query)
        items = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = int(count_result.scalar() or 0)

        return items, total

    @staticmethod
    async def notify_subscribers_on_publish(db: AsyncSession, news: News) -> int:
        if not getattr(news, "is_published", False):
            return 0

        link = f"/news/{int(news.id)}"

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

        existing_result = await db.execute(
            select(Notification.user_id).where(
                and_(
                    Notification.type == NotificationType.NEWS,
                    Notification.link == link,
                    Notification.user_id.in_(list(user_ids)),
                )
            )
        )
        existing_rows = cast(list[tuple[int]], existing_result.fetchall())
        already_notified = {int(uid) for (uid,) in existing_rows}

        to_create = [uid for uid in user_ids if uid not in already_notified]
        if not to_create:
            return 0

        title = f"订阅命中：{str(news.title)}"
        preview_source = str(getattr(news, "summary", None) or "").strip() or str(
            getattr(news, "content", "") or ""
        ).strip()
        preview = " ".join(preview_source.split())[:120]

        notifications: list[Notification] = []
        for uid in to_create:
            content_lines: list[str] = [f"分类：{str(news.category)}"]
            reasons = sorted(list(reasons_by_user.get(int(uid), set())))
            content_lines.extend(reasons)
            if preview:
                content_lines.append(f"摘要：{preview}")
            content = "\n".join(content_lines) if content_lines else None
            notifications.append(
                Notification(
                    user_id=int(uid),
                    type=NotificationType.NEWS,
                    title=title,
                    content=content,
                    link=link,
                    is_read=False,
                )
            )

        db.add_all(notifications)
        await db.commit()
        return len(notifications)

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

        cols: list[object] = [
            NewsFavorite.news_id,
            func.count(NewsFavorite.id),
        ]
        if user_id is not None:
            cols.append(
                func.max(
                    case(
                        (NewsFavorite.user_id == int(user_id), 1),
                        else_=0,
                    )
                )
            )

        result = await db.execute(
            select(*cols)
            .where(NewsFavorite.news_id.in_(ids))
            .group_by(NewsFavorite.news_id)
        )

        if user_id is None:
            rows = cast(list[tuple[int, int]], result.all())
            return {int(news_id): (int(count or 0), False) for news_id, count in rows}

        rows2 = cast(list[tuple[int, int, int]], result.all())
        return {
            int(news_id): (int(count or 0), bool(is_fav))
            for news_id, count, is_fav in rows2
        }

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
    ) -> tuple[list[News], int]:
        query = (
            select(News)
            .join(NewsFavorite, News.id == NewsFavorite.news_id)
            .where(
                and_(
                    NewsFavorite.user_id == user_id,
                    News.is_published == True,
                )
            )
            .order_by(desc(NewsFavorite.created_at))
        )

        if category:
            query = query.where(News.category == category)
        if keyword:
            search_filter = News.title.contains(keyword) | News.content.contains(keyword)
            query = query.where(search_filter)

        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        items = list(result.scalars().all())

        count_query = (
            select(func.count(NewsFavorite.id))
            .join(News, News.id == NewsFavorite.news_id)
            .where(
                and_(
                    NewsFavorite.user_id == user_id,
                    News.is_published == True,
                )
            )
        )

        if category:
            count_query = count_query.where(News.category == category)
        if keyword:
            search_filter = News.title.contains(keyword) | News.content.contains(keyword)
            count_query = count_query.where(search_filter)

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
                    News.is_published == True,
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
            .where(News.is_published == True, News.is_top == True)
            .order_by(desc(News.published_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_recent_news(db: AsyncSession, limit: int = 10) -> list[News]:
        """获取最新新闻"""
        result = await db.execute(
            select(News)
            .where(News.is_published == True)
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
        conditions: list[ColumnElement[bool]] = [News.is_published == True]
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
        cached = NewsService._recommended_cache.get(cache_key)
        if cached is not None:
            cached_at, cached_ids = cached
            if (now_ts - float(cached_at)) <= float(NewsService._recommended_cache_ttl_seconds):
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
        topic = NewsTopic(
            title=str(data.get("title") or ""),
            description=(str(data.get("description")) if data.get("description") is not None else None),
            cover_image=(str(data.get("cover_image")) if data.get("cover_image") is not None else None),
            is_active=bool(data.get("is_active", True)),
            sort_order=int(data.get("sort_order", 0) or 0),
            auto_category=(str(data.get("auto_category")) if data.get("auto_category") is not None else None),
            auto_keyword=(str(data.get("auto_keyword")) if data.get("auto_keyword") is not None else None),
            auto_limit=int(data.get("auto_limit", 0) or 0),
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
            pos = int(max_result.scalar() or 0) + 1

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
        ids_raw = [int(i) for i in news_ids if i is not None]
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
        existing_ids = {int(row[0]) for row in existing_result.all()}
        to_add = [i for i in ids if i not in existing_ids]

        if not to_add:
            return requested, 0, requested

        max_result = await db.execute(
            select(func.coalesce(func.max(NewsTopicItem.position), 0)).where(
                NewsTopicItem.topic_id == int(topic_id)
            )
        )
        max_pos = int(max_result.scalar() or 0)
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
        ids_raw = [int(i) for i in item_ids if i is not None]
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
        ids = [int(r[0]) for r in res.all()]
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
        ids_raw = [int(i) for i in item_ids if i is not None]
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
        exist_ids = {int(r[0]) for r in exist_res.all()}
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
            manual_conditions.append(News.is_published == True)

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
    async def create_comment(db: AsyncSession, news_id: int, user_id: int, content: str) -> NewsComment:
        comment = NewsComment(news_id=int(news_id), user_id=int(user_id), content=str(content))
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        return comment

    @staticmethod
    async def get_comment(db: AsyncSession, comment_id: int) -> NewsComment | None:
        result = await db.execute(
            select(NewsComment)
            .options(joinedload(NewsComment.author))
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
        base_filter = and_(NewsComment.news_id == int(news_id), NewsComment.is_deleted == False)

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


news_service = NewsService()
