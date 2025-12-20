"""全局搜索路由"""
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services.search_service import search_service, SearchResults, HotKeyword
from ..models.user import User
from ..utils.deps import get_current_user_optional
from ..utils.rate_limiter import get_client_ip

router = APIRouter(prefix="/search", tags=["全局搜索"])


@router.get("", summary="全局搜索")
async def global_search(
    request: Request,
    q: Annotated[str, Query(min_length=2, description="搜索关键词")],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> SearchResults:
    """
    全局搜索
    
    搜索新闻、帖子、律所、律师、法律知识
    """
    ip_address = get_client_ip(request)

    try:
        await search_service.record_search(
            db,
            keyword=q,
            user_id=current_user.id if current_user else None,
            ip_address=ip_address,
        )
    except Exception:
        # 记录搜索历史失败不影响搜索本身
        pass

    results = await search_service.global_search(db, q, limit)
    return results


@router.get("/suggestions", summary="搜索建议")
async def search_suggestions(
    q: Annotated[str, Query(min_length=1, description="搜索关键词")],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> dict[str, list[str]]:
    """获取搜索建议"""
    suggestions = await search_service.search_suggestions(db, q, limit)
    return {"suggestions": suggestions}


@router.get("/hot", summary="热门搜索")
async def hot_keywords(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> dict[str, list[HotKeyword]]:
    """获取热门搜索关键词"""
    keywords = await search_service.get_hot_keywords(db, limit)
    return {"keywords": keywords}


@router.get("/history", summary="用户搜索历史")
async def user_search_history(
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> dict[str, list[str]]:
    """获取当前用户的搜索历史"""
    if not current_user:
        return {"history": []}
    history = await search_service.get_user_search_history(db, current_user.id, limit)
    return {"history": history}


@router.delete("/history", summary="清除搜索历史")
async def clear_search_history(
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """清除当前用户的搜索历史"""
    if not current_user:
        return {"message": "未登录"}
    _ = await search_service.clear_user_search_history(db, current_user.id)
    return {"message": "搜索历史已清除"}
