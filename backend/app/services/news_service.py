"""新闻服务层"""
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update, and_, or_, case
from sqlalchemy.exc import IntegrityError

from ..models.news import News, NewsFavorite, NewsViewHistory, NewsSubscription
from ..models.notification import Notification, NotificationType
from ..schemas.news import NewsCreate, NewsUpdate


class NewsService:
    """新闻服务"""
    
    @staticmethod
    async def create(db: AsyncSession, news_data: NewsCreate) -> News:
        """创建新闻"""
        news = News(
            title=news_data.title,
            summary=news_data.summary,
            content=news_data.content,
            cover_image=news_data.cover_image,
            category=news_data.category,
            source=news_data.source,
            author=news_data.author,
            is_top=news_data.is_top,
            is_published=news_data.is_published,
            published_at=datetime.now() if news_data.is_published else None
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
        
        # 如果从未发布变为发布，设置发布时间
        is_published_value = update_data.get("is_published")
        if isinstance(is_published_value, bool) and is_published_value and not news.is_published:
            update_data["published_at"] = datetime.now()
        
        for field, value in update_data.items():
            setattr(news, field, value)
        
        await db.commit()
        await db.refresh(news)
        return news
    
    @staticmethod
    async def delete(db: AsyncSession, news: News) -> None:
        """删除新闻"""
        await db.delete(news)
        await db.commit()
    
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
        existing = result.scalar_one_or_none()
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
    ) -> list[News]:
        since = datetime.now() - timedelta(days=days)

        query = select(News).where(
            and_(
                News.is_published == True,
                or_(
                    and_(News.published_at.is_not(None), News.published_at >= since),
                    and_(News.published_at.is_(None), News.created_at >= since),
                ),
            )
        )

        if category:
            query = query.where(News.category == category)

        candidate_limit = min(500, max(int(limit) * 50, 200))
        query = query.order_by(desc(News.view_count), desc(News.published_at), desc(News.created_at)).limit(candidate_limit)

        result = await db.execute(query)
        candidates = list(result.scalars().all())
        if not candidates:
            return []

        ids = [int(n.id) for n in candidates]
        fav_result = await db.execute(
            select(NewsFavorite.news_id, func.count(NewsFavorite.id))
            .where(NewsFavorite.news_id.in_(ids))
            .group_by(NewsFavorite.news_id)
        )
        fav_map = {int(row[0]): int(row[1] or 0) for row in fav_result.all()}

        now = datetime.now()

        def age_hours(news: News) -> float:
            ts = getattr(news, "published_at", None) or getattr(news, "created_at", None)
            if ts is None:
                return 0.0
            try:
                delta = now - ts
            except TypeError:
                delta = now.replace(tzinfo=getattr(ts, "tzinfo", None)) - ts
            return max(0.0, float(delta.total_seconds()) / 3600.0)

        def hot_score(news: News) -> float:
            fav = fav_map.get(int(news.id), 0)
            base = float(int(getattr(news, "view_count", 0) or 0) + fav * 5)
            hours = age_hours(news)
            return base / pow(hours + 2.0, 1.3)

        candidates.sort(
            key=lambda n: (
                hot_score(n),
                int(getattr(n, "view_count", 0) or 0),
                -age_hours(n),
            ),
            reverse=True,
        )
        return candidates[: int(limit)]

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
        existing = result.scalar_one()
        return existing

    @staticmethod
    async def delete_subscription(db: AsyncSession, user_id: int, sub_id: int) -> bool:
        result = await db.execute(
            select(NewsSubscription).where(
                and_(NewsSubscription.id == sub_id, NewsSubscription.user_id == user_id)
            )
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            return False
        await db.delete(sub)
        await db.commit()
        return True

    @staticmethod
    async def notify_subscribers_on_publish(db: AsyncSession, news: News) -> int:
        if not getattr(news, "is_published", False):
            return 0

        link = f"/news/{int(news.id)}"

        user_ids: set[int] = set()

        # category subscribers
        cat_result = await db.execute(
            select(NewsSubscription.user_id).where(
                and_(
                    NewsSubscription.sub_type == "category",
                    NewsSubscription.value == str(news.category),
                )
            )
        )
        user_ids.update([int(row[0]) for row in cat_result.fetchall()])

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

        for row in keyword_result.fetchall():
            uid = int(row[0])
            keyword = str(row[1] or "").strip().lower()
            if not keyword:
                continue
            if keyword in haystack:
                user_ids.add(uid)

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
        already_notified = {int(row[0]) for row in existing_result.fetchall()}

        to_create = [uid for uid in user_ids if uid not in already_notified]
        if not to_create:
            return 0

        title = f"你订阅的新闻已发布：{str(news.title)}"
        content_lines: list[str] = [f"分类：{str(news.category)}"]
        content = "\n".join(content_lines) if content_lines else None

        notifications: list[Notification] = []
        for uid in to_create:
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


news_service = NewsService()
