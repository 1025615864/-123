"""新闻API路由"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user import User
from ..schemas.news import (
    NewsCreate, NewsUpdate, NewsResponse, NewsListResponse,
    NewsListItem, NewsCategoryCount, NewsFavoriteResponse,
    NewsAdminListResponse, NewsAdminListItem
)
from ..services.news_service import news_service
from ..utils.deps import require_admin, get_current_user, get_current_user_optional

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
    
    user_id = current_user.id if current_user else None
    items: list[NewsListItem] = []
    for news in news_list:
        fav_count = await news_service.get_favorite_count(db, news.id)
        is_fav = False
        if user_id is not None:
            is_fav = await news_service.is_favorited(db, news.id, user_id)
        item = NewsListItem.model_validate(news)
        item.favorite_count = fav_count
        item.is_favorited = is_fav
        items.append(item)
    return NewsListResponse(items=items, total=total, page=page, page_size=page_size)


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

    items: list[NewsListItem] = []
    for news in news_list:
        fav_count = await news_service.get_favorite_count(db, news.id)
        is_fav = await news_service.is_favorited(db, news.id, current_user.id)
        item = NewsListItem.model_validate(news)
        item.favorite_count = fav_count
        item.is_favorited = is_fav
        items.append(item)

    return NewsListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/top", response_model=list[NewsListItem], summary="获取置顶新闻")
async def get_top_news(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
):
    """获取置顶新闻"""
    news_list = await news_service.get_top_news(db, limit)
    return [NewsListItem.model_validate(news) for news in news_list]


@router.get("/recent", response_model=list[NewsListItem], summary="获取最新新闻")
async def get_recent_news(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    """获取最新新闻"""
    news_list = await news_service.get_recent_news(db, limit)
    return [NewsListItem.model_validate(news) for news in news_list]


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

    items: list[NewsListItem] = []
    for news in news_list:
        fav_count = await news_service.get_favorite_count(db, news.id)
        item = NewsListItem.model_validate(news)
        item.favorite_count = fav_count
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

    user_id = current_user.id if current_user else None
    items: list[NewsListItem] = []
    for news in news_list:
        fav_count = await news_service.get_favorite_count(db, news.id)
        is_fav = False
        if user_id is not None:
            is_fav = await news_service.is_favorited(db, news.id, user_id)
        item = NewsListItem.model_validate(news)
        item.favorite_count = fav_count
        item.is_favorited = is_fav
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

    fav_count = await news_service.get_favorite_count(db, news.id)
    is_fav = False
    if current_user is not None:
        is_fav = await news_service.is_favorited(db, news.id, current_user.id)
    resp = NewsResponse.model_validate(news)
    resp.favorite_count = fav_count
    resp.is_favorited = is_fav
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
    
    updated_news = await news_service.update(db, news, news_data)
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
