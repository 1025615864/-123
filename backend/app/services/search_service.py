"""搜索服务 - 提供全局搜索功能"""
import logging
from typing import Literal, TypedDict, cast
from sqlalchemy import or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.news import News
from ..models.forum import Post
from ..models.lawfirm import LawFirm, Lawyer
from ..models.knowledge import LegalKnowledge

logger = logging.getLogger(__name__)


class NewsSearchItem(TypedDict):
    id: int
    title: str
    summary: str | None
    type: Literal["news"]


class PostSearchItem(TypedDict):
    id: int
    title: str
    content: str
    type: Literal["post"]


class LawFirmSearchItem(TypedDict):
    id: int
    name: str
    address: str | None
    type: Literal["lawfirm"]


class LawyerSearchItem(TypedDict):
    id: int
    name: str
    specialties: str | None
    type: Literal["lawyer"]


class KnowledgeSearchItem(TypedDict):
    id: int
    title: str
    category: str | None
    type: Literal["knowledge"]


class SearchResults(TypedDict):
    news: list[NewsSearchItem]
    posts: list[PostSearchItem]
    lawfirms: list[LawFirmSearchItem]
    lawyers: list[LawyerSearchItem]
    knowledge: list[KnowledgeSearchItem]


class HotKeyword(TypedDict):
    keyword: str
    count: int


class SearchService:
    """全局搜索服务"""
    
    async def global_search(
        self, 
        db: AsyncSession, 
        query: str, 
        limit: int = 10
    ) -> SearchResults:
        """
        全局搜索
        
        搜索新闻、帖子、律所、律师、法律知识
        """
        results: SearchResults = {
            "news": [],
            "posts": [],
            "lawfirms": [],
            "lawyers": [],
            "knowledge": []
        }
        
        if not query or len(query) < 2:
            return results
        
        search_term = f"%{query}%"
        
        # 搜索新闻
        news_query = select(News).where(
            or_(
                News.title.ilike(search_term),
                News.content.ilike(search_term),
                News.summary.ilike(search_term)
            ),
            News.is_published == True
        ).limit(limit)
        news_result = await db.execute(news_query)
        for news in news_result.scalars():
            results["news"].append({
                "id": news.id,
                "title": news.title,
                "summary": news.summary,
                "type": "news"
            })
        
        # 搜索帖子
        posts_query = select(Post).where(
            or_(
                Post.title.ilike(search_term),
                Post.content.ilike(search_term)
            ),
            Post.is_deleted == False
        ).limit(limit)
        posts_result = await db.execute(posts_query)
        for post in posts_result.scalars():
            results["posts"].append({
                "id": post.id,
                "title": post.title,
                "content": post.content[:100] if post.content else "",
                "type": "post"
            })
        
        # 搜索律所
        firms_query = select(LawFirm).where(
            or_(
                LawFirm.name.ilike(search_term),
                LawFirm.description.ilike(search_term),
                LawFirm.address.ilike(search_term),
                LawFirm.specialties.ilike(search_term)
            ),
            LawFirm.is_active == True
        ).limit(limit)
        firms_result = await db.execute(firms_query)
        for firm in firms_result.scalars():
            results["lawfirms"].append({
                "id": firm.id,
                "name": firm.name,
                "address": firm.address,
                "type": "lawfirm"
            })
        
        # 搜索律师
        lawyers_query = select(Lawyer).where(
            or_(
                Lawyer.name.ilike(search_term),
                Lawyer.specialties.ilike(search_term)
            ),
            Lawyer.is_active == True
        ).limit(limit)
        lawyers_result = await db.execute(lawyers_query)
        for lawyer in lawyers_result.scalars():
            results["lawyers"].append({
                "id": lawyer.id,
                "name": lawyer.name,
                "specialties": lawyer.specialties,
                "type": "lawyer"
            })
        
        # 搜索法律知识
        knowledge_query = select(LegalKnowledge).where(
            or_(
                LegalKnowledge.title.ilike(search_term),
                LegalKnowledge.content.ilike(search_term)
            ),
            LegalKnowledge.is_active == True
        ).limit(limit)
        knowledge_result = await db.execute(knowledge_query)
        for item in knowledge_result.scalars():
            results["knowledge"].append({
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "type": "knowledge"
            })
        
        return results
    
    async def search_suggestions(
        self, 
        db: AsyncSession, 
        query: str, 
        limit: int = 5
    ) -> list[str]:
        """获取搜索建议"""
        if not query or len(query) < 1:
            return []
        
        suggestions: list[str] = []
        search_term = f"{query}%"
        
        # 从新闻标题获取建议
        news_query = select(News.title).where(
            News.title.ilike(search_term),
            News.is_published == True
        ).limit(limit)
        news_result = await db.execute(news_query)
        suggestions.extend(cast(list[str], news_result.scalars().all()))
        
        # 从帖子标题获取建议
        posts_query = select(Post.title).where(
            Post.title.ilike(search_term),
            Post.is_deleted == False
        ).limit(limit)
        posts_result = await db.execute(posts_query)
        suggestions.extend(cast(list[str], posts_result.scalars().all()))
        
        # 去重并限制数量（保持顺序）
        seen: set[str] = set()
        unique: list[str] = []
        for s in suggestions:
            if s in seen:
                continue
            seen.add(s)
            unique.append(s)
            if len(unique) >= limit:
                break
 
        return unique


    async def get_hot_keywords(
        self,
        db: AsyncSession,
        limit: int = 10
    ) -> list[HotKeyword]:
        """获取热门搜索关键词"""
        # 从SearchHistory表获取热门搜索词
        try:
            from ..models.system import SearchHistory
            query = (
                select(SearchHistory.keyword, func.count(SearchHistory.id).label('count'))
                .group_by(SearchHistory.keyword)
                .order_by(func.count(SearchHistory.id).desc())
                .limit(limit)
            )
            result = await db.execute(query)
            items: list[HotKeyword] = []
            for row in result.all():
                items.append({
                    "keyword": cast(str, row[0]),
                    "count": cast(int, row[1]),
                })
            return items
        except Exception:
            # 如果表不存在，返回默认热词
            return [
                {"keyword": "劳动合同", "count": 100},
                {"keyword": "离婚财产", "count": 85},
                {"keyword": "交通事故", "count": 72},
                {"keyword": "借款纠纷", "count": 65},
                {"keyword": "房屋买卖", "count": 58},
            ]
    
    async def record_search(
        self,
        db: AsyncSession,
        keyword: str,
        user_id: int | None = None,
        ip_address: str | None = None
    ):
        """记录搜索历史"""
        try:
            from ..models.system import SearchHistory
            history = SearchHistory(
                keyword=keyword,
                user_id=user_id,
                ip_address=ip_address
            )
            db.add(history)
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to record search history: {e}")
    
    async def get_user_search_history(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> list[str]:
        """获取用户搜索历史"""
        try:
            from ..models.system import SearchHistory
            query = (
                select(SearchHistory.keyword)
                .where(SearchHistory.user_id == user_id)
                .order_by(SearchHistory.created_at.desc())
                .limit(limit * 2)  # 多查询一些用于去重
            )
            result = await db.execute(query)
            keywords = cast(list[str], result.scalars().all())
            # 去重保持顺序
            seen: set[str] = set()
            unique: list[str] = []
            for k in keywords:
                if k not in seen:
                    seen.add(k)
                    unique.append(k)
                    if len(unique) >= limit:
                        break
            return unique
        except Exception:
            return []
    
    async def clear_user_search_history(
        self,
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """清除用户搜索历史"""
        try:
            from ..models.system import SearchHistory
            from sqlalchemy import delete
            _ = await db.execute(
                delete(SearchHistory).where(SearchHistory.user_id == user_id)
            )
            await db.commit()
            return True
        except Exception:
            return False


# 单例实例
search_service = SearchService()
