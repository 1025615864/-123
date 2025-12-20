"""管理后台API路由"""
from collections.abc import AsyncIterator, Mapping
from typing import Annotated, cast
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User
from app.models.forum import Post, Comment
from app.models.news import News
from app.models.lawfirm import LawFirm
from app.models.consultation import Consultation, ChatMessage
from app.models.knowledge import LegalKnowledge
from app.utils.deps import require_admin

router = APIRouter(prefix="/admin", tags=["管理后台"])


@router.get("/stats", summary="获取统计数据")
async def get_stats(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取系统统计数据（需要管理员权限）"""
    _ = current_user
    # 用户统计
    user_count = await db.execute(select(func.count()).select_from(User))
    total_users = user_count.scalar() or 0
    
    # 新闻统计
    news_count = await db.execute(select(func.count()).select_from(News))
    total_news = news_count.scalar() or 0
    
    # 帖子统计
    post_count = await db.execute(select(func.count()).select_from(Post))
    total_posts = post_count.scalar() or 0

    # 评论统计
    comment_count = await db.execute(select(func.count()).select_from(Comment))
    total_comments = comment_count.scalar() or 0

    # AI咨询统计
    consultation_count = await db.execute(select(func.count()).select_from(Consultation))
    total_consultations = consultation_count.scalar() or 0
    
    # 律所统计
    firm_count = await db.execute(select(func.count()).select_from(LawFirm))
    total_firms = firm_count.scalar() or 0
    
    return {
        "users": total_users,
        "news": total_news,
        "posts": total_posts,
        "lawfirms": total_firms,
        "comments": total_comments,
        "consultations": total_consultations,
    }


# ============ 数据导出 API ============

def generate_csv(data: list[dict[str, object]], fieldnames: list[str]) -> io.StringIO:
    """生成CSV内容"""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for row in data:
        # 处理日期时间格式
        processed: dict[str, object] = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                processed[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            else:
                processed[k] = v
        writer.writerow(processed)
    _ = output.seek(0)
    return output


async def generate_csv_stream(fieldnames: list[str], rows_iter: AsyncIterator[Mapping[str, object]]):
    header_out = io.StringIO()
    _ = header_out.write("\ufeff")
    header_writer = csv.DictWriter(header_out, fieldnames=fieldnames, extrasaction='ignore', lineterminator="\n")
    header_writer.writeheader()
    yield header_out.getvalue()

    async for row in rows_iter:
        processed: dict[str, object] = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                processed[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            else:
                processed[k] = v

        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction='ignore', lineterminator="\n")
        writer.writerow(processed)
        yield out.getvalue()


@router.get("/export/users", summary="导出用户数据")
async def export_users(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = Query("csv", description="导出格式: csv"),
):
    """导出所有用户数据为CSV"""
    _ = current_user
    _ = format
    fieldnames = ["id", "username", "email", "nickname", "phone", "role", "is_active", "created_at"]

    async def row_generator():
        batch_size = 1000
        offset = 0
        while True:
            result = await db.execute(
                select(User).order_by(User.id).offset(offset).limit(batch_size)
            )
            users = result.scalars().all()
            if not users:
                break
            for u in users:
                yield {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "nickname": u.nickname or "",
                    "phone": u.phone or "",
                    "role": u.role,
                    "is_active": "是" if u.is_active else "否",
                    "created_at": u.created_at,
                }
            offset += batch_size

    filename = f"users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate_csv_stream(fieldnames, row_generator()),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/posts", summary="导出帖子数据")
async def export_posts(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """导出所有帖子数据为CSV"""
    _ = current_user
    fieldnames = ["id", "title", "author", "category", "view_count", "like_count", "comment_count", "is_pinned", "is_hot", "created_at"]

    async def row_generator():
        batch_size = 500
        offset = 0
        while True:
            result = await db.execute(
                select(Post, User.username)
                .join(User, Post.user_id == User.id)
                .order_by(Post.id.desc())
                .offset(offset)
                .limit(batch_size)
            )
            rows = cast(list[tuple[Post, str]], result.all())
            if not rows:
                break
            for post, username in rows:
                yield {
                    "id": post.id,
                    "title": post.title,
                    "author": username,
                    "category": post.category or "",
                    "view_count": post.view_count,
                    "like_count": post.like_count,
                    "comment_count": post.comment_count,
                    "is_pinned": "是" if post.is_pinned else "否",
                    "is_hot": "是" if post.is_hot else "否",
                    "created_at": post.created_at,
                }
            offset += batch_size

    filename = f"posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate_csv_stream(fieldnames, row_generator()),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/news", summary="导出新闻数据")
async def export_news(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """导出所有新闻数据为CSV"""
    _ = current_user
    fieldnames = ["id", "title", "category", "view_count", "is_published", "created_at"]

    async def row_generator():
        batch_size = 1000
        offset = 0
        while True:
            result = await db.execute(
                select(News).order_by(News.id.desc()).offset(offset).limit(batch_size)
            )
            news_list = result.scalars().all()
            if not news_list:
                break
            for n in news_list:
                yield {
                    "id": n.id,
                    "title": n.title,
                    "category": n.category or "",
                    "view_count": n.view_count,
                    "is_published": "是" if n.is_published else "否",
                    "created_at": n.created_at,
                }
            offset += batch_size

    filename = f"news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate_csv_stream(fieldnames, row_generator()),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/lawfirms", summary="导出律所数据")
async def export_lawfirms(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """导出所有律所数据为CSV"""
    _ = current_user
    fieldnames = ["id", "name", "city", "province", "address", "phone", "email", "rating", "review_count", "is_verified", "is_active", "created_at"]

    async def row_generator():
        batch_size = 1000
        offset = 0
        while True:
            result = await db.execute(
                select(LawFirm).order_by(LawFirm.id).offset(offset).limit(batch_size)
            )
            firms = result.scalars().all()
            if not firms:
                break
            for f in firms:
                yield {
                    "id": f.id,
                    "name": f.name,
                    "city": f.city or "",
                    "province": f.province or "",
                    "address": f.address or "",
                    "phone": f.phone or "",
                    "email": f.email or "",
                    "rating": f.rating,
                    "review_count": f.review_count,
                    "is_verified": "是" if f.is_verified else "否",
                    "is_active": "是" if f.is_active else "否",
                    "created_at": f.created_at,
                }
            offset += batch_size

    filename = f"lawfirms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate_csv_stream(fieldnames, row_generator()),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/knowledge", summary="导出知识库数据")
async def export_knowledge(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """导出所有法律知识数据为CSV"""
    _ = current_user
    fieldnames = ["id", "knowledge_type", "title", "article_number", "category", "content", "keywords", "source", "is_active", "is_vectorized", "created_at"]

    async def row_generator():
        batch_size = 500
        offset = 0
        while True:
            result = await db.execute(
                select(LegalKnowledge).order_by(LegalKnowledge.id).offset(offset).limit(batch_size)
            )
            knowledge_list = result.scalars().all()
            if not knowledge_list:
                break
            for k in knowledge_list:
                content_preview = k.content[:200] + "..." if len(k.content) > 200 else k.content
                yield {
                    "id": k.id,
                    "knowledge_type": k.knowledge_type,
                    "title": k.title,
                    "article_number": k.article_number or "",
                    "category": k.category,
                    "content": content_preview,
                    "keywords": k.keywords or "",
                    "source": k.source or "",
                    "is_active": "是" if k.is_active else "否",
                    "is_vectorized": "是" if k.is_vectorized else "否",
                    "created_at": k.created_at,
                }
            offset += batch_size

    filename = f"knowledge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate_csv_stream(fieldnames, row_generator()),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/consultations", summary="导出咨询记录")
async def export_consultations(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """导出所有咨询记录为CSV"""
    _ = current_user
    fieldnames = ["id", "session_id", "user", "title", "status", "message_count", "created_at", "updated_at"]

    async def row_generator() -> AsyncIterator[Mapping[str, object]]:
        batch_size = 500
        offset = 0
        while True:
            result = await db.execute(
                select(
                    Consultation.id,
                    Consultation.session_id,
                    Consultation.title,
                    Consultation.created_at,
                    Consultation.updated_at,
                    User.username,
                    func.count(ChatMessage.id).label("message_count"),
                )
                .select_from(Consultation)
                .outerjoin(User, Consultation.user_id == User.id)
                .outerjoin(ChatMessage, ChatMessage.consultation_id == Consultation.id)
                .group_by(
                    Consultation.id,
                    Consultation.session_id,
                    Consultation.title,
                    Consultation.created_at,
                    Consultation.updated_at,
                    User.username,
                )
                .order_by(Consultation.id.desc())
                .offset(offset)
                .limit(batch_size)
            )
            rows = cast(list[tuple[int, str, str | None, datetime, datetime, str | None, int]], result.all())
            if not rows:
                break
            for consultation_id, session_id, title, created_at, updated_at, username, message_count in rows:
                yield {
                    "id": consultation_id,
                    "session_id": session_id,
                    "user": username or "",
                    "title": title or "",
                    "status": "",
                    "message_count": int(message_count),
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            offset += batch_size

    filename = f"consultations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate_csv_stream(fieldnames, row_generator()),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
