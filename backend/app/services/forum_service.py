"""论坛服务层"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, update, case
from sqlalchemy.engine import CursorResult
from typing import cast, Any
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.models.forum import Post, Comment, PostLike, PostFavorite, PostReaction
from app.schemas.forum import PostCreate, PostUpdate, CommentCreate
import json
import math
from datetime import datetime


class ForumService:
    """论坛服务"""
    
    # ============ 帖子相关 ============
    
    @staticmethod
    async def create_post(db: AsyncSession, user_id: int, post_data: PostCreate) -> Post:
        """创建帖子"""
        # 处理图片和附件
        images_json = json.dumps(post_data.images) if post_data.images else None
        attachments_json = json.dumps(post_data.attachments) if post_data.attachments else None
        
        post = Post(
            title=post_data.title,
            content=post_data.content,
            category=post_data.category,
            user_id=user_id,
            cover_image=post_data.cover_image,
            images=images_json,
            attachments=attachments_json,
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post
    
    @staticmethod
    async def get_post(db: AsyncSession, post_id: int) -> Post | None:
        """获取帖子详情"""
        result = await db.execute(
            select(Post)
            .options(selectinload(Post.author))
            .where(and_(Post.id == post_id, Post.is_deleted == False))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_posts(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None
    ) -> tuple[list[Post], int]:
        """获取帖子列表"""
        query = select(Post).options(selectinload(Post.author)).where(Post.is_deleted == False)
        count_query = select(func.count(Post.id)).where(Post.is_deleted == False)
        
        if category:
            query = query.where(Post.category == category)
            count_query = count_query.where(Post.category == category)
        
        if keyword:
            search_filter = Post.title.contains(keyword) | Post.content.contains(keyword)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # 置顶优先，然后按时间倒序
        query = query.order_by(desc(Post.is_pinned), desc(Post.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        posts = result.scalars().all()
        
        count_result = await db.execute(count_query)
        total = int(count_result.scalar() or 0)
        
        return list(posts), total

    @staticmethod
    async def get_user_posts(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None,
    ) -> tuple[list[Post], int]:
        """获取用户发布的帖子列表"""
        query = (
            select(Post)
            .options(selectinload(Post.author))
            .where(and_(Post.user_id == user_id, Post.is_deleted == False))
        )
        count_query = select(func.count(Post.id)).where(and_(Post.user_id == user_id, Post.is_deleted == False))

        if category:
            query = query.where(Post.category == category)
            count_query = count_query.where(Post.category == category)

        if keyword:
            search_filter = Post.title.contains(keyword) | Post.content.contains(keyword)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        query = query.order_by(desc(Post.is_pinned), desc(Post.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        posts = result.scalars().all()

        count_result = await db.execute(count_query)
        total = int(count_result.scalar() or 0)

        return list(posts), total
    
    @staticmethod
    async def update_post(db: AsyncSession, post: Post, post_data: PostUpdate) -> Post:
        """更新帖子"""
        update_data: dict[str, object] = post_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(post, field, value)
        await db.commit()
        await db.refresh(post)
        return post
    
    @staticmethod
    async def delete_post(db: AsyncSession, post: Post) -> None:
        """删除帖子（软删除）"""
        post.is_deleted = True
        await db.commit()
    
    @staticmethod
    async def increment_view(db: AsyncSession, post: Post) -> None:
        """增加浏览量"""
        try:
            _ = await db.execute(
                update(Post)
                .where(Post.id == post.id)
                .values(view_count=func.coalesce(Post.view_count, 0) + 1)
            )
            await db.commit()
        except Exception:
            await db.rollback()
    
    # ============ 点赞相关 ============
    
    @staticmethod
    async def toggle_post_like(db: AsyncSession, post_id: int, user_id: int) -> tuple[bool, int]:
        """切换帖子点赞状态"""
        # 检查是否已点赞
        result = await db.execute(
            select(PostLike).where(
                and_(PostLike.post_id == post_id, PostLike.user_id == user_id)
            )
        )
        existing_like = result.scalar_one_or_none()
        
        post_result = await db.execute(
            select(Post).where(and_(Post.id == post_id, Post.is_deleted == False))
        )
        post = post_result.scalar_one_or_none()
        if post is None:
            raise ValueError("帖子不存在")
        
        if existing_like:
            # 取消点赞
            await db.delete(existing_like)
            _ = await db.execute(
                update(Post)
                .where(Post.id == post_id)
                .values(
                    like_count=case(
                        (Post.like_count > 0, Post.like_count - 1),
                        else_=0,
                    )
                )
            )
            await db.commit()
            like_count_result = await db.execute(select(Post.like_count).where(Post.id == post_id))
            return False, int(like_count_result.scalar() or 0)

        # 添加点赞
        like = PostLike(post_id=post_id, user_id=user_id)
        db.add(like)
        _ = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count + 1)
        )
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            like_count_result = await db.execute(select(Post.like_count).where(Post.id == post_id))
            return True, int(like_count_result.scalar() or 0)

        like_count_result = await db.execute(select(Post.like_count).where(Post.id == post_id))
        return True, int(like_count_result.scalar() or 0)
    
    @staticmethod
    async def is_post_liked(db: AsyncSession, post_id: int, user_id: int) -> bool:
        """检查用户是否点赞帖子"""
        result = await db.execute(
            select(PostLike).where(
                and_(PostLike.post_id == post_id, PostLike.user_id == user_id)
            )
        )
        return result.scalar_one_or_none() is not None
    
    # ============ 评论相关 ============
    
    @staticmethod
    async def create_comment(
        db: AsyncSession,
        post_id: int,
        user_id: int,
        comment_data: CommentCreate
    ) -> Comment:
        """创建评论"""
        comment = Comment(
            content=comment_data.content,
            post_id=post_id,
            user_id=user_id,
            parent_id=comment_data.parent_id
        )
        db.add(comment)

        _ = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=Post.comment_count + 1)
        )

        await db.commit()
        await db.refresh(comment)
        return comment
    
    @staticmethod
    async def get_comments(
        db: AsyncSession,
        post_id: int,
        page: int = 1,
        page_size: int = 50
    ) -> tuple[list[Comment], int]:
        """获取帖子评论列表"""
        # 只获取顶级评论
        query = (
            select(Comment)
            .options(selectinload(Comment.author))
            .where(
                and_(
                    Comment.post_id == post_id,
                    Comment.parent_id == None,
                    Comment.is_deleted == False
                )
            )
            .order_by(desc(Comment.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        result = await db.execute(query)
        comments = result.scalars().all()
        
        count_result = await db.execute(
            select(func.count(Comment.id)).where(
                and_(
                    Comment.post_id == post_id,
                    Comment.parent_id == None,
                    Comment.is_deleted == False
                )
            )
        )
        total = int(count_result.scalar() or 0)
        
        return list(comments), total
    
    @staticmethod
    async def delete_comment(db: AsyncSession, comment: Comment) -> None:
        """删除评论（软删除）"""
        comment.is_deleted = True

        _ = await db.execute(
            update(Post)
            .where(Post.id == comment.post_id)
            .values(
                comment_count=case(
                    (Post.comment_count > 0, Post.comment_count - 1),
                    else_=0,
                )
            )
        )

        await db.commit()
    
    @staticmethod
    async def get_comment(db: AsyncSession, comment_id: int) -> Comment | None:
        """获取评论"""
        result = await db.execute(
            select(Comment).where(
                and_(Comment.id == comment_id, Comment.is_deleted == False)
            )
        )
        return result.scalar_one_or_none()

    # ============ 收藏相关 ============
    
    @staticmethod
    async def toggle_post_favorite(db: AsyncSession, post_id: int, user_id: int) -> tuple[bool, int]:
        """切换帖子收藏状态"""
        result = await db.execute(
            select(PostFavorite).where(
                and_(PostFavorite.post_id == post_id, PostFavorite.user_id == user_id)
            )
        )
        existing_favorite = result.scalar_one_or_none()
        
        if existing_favorite:
            # 取消收藏
            await db.delete(existing_favorite)
            await db.commit()
            
            # 获取收藏数
            count_result = await db.execute(
                select(func.count(PostFavorite.id)).where(PostFavorite.post_id == post_id)
            )
            return False, int(count_result.scalar() or 0)
        
        # 添加收藏
        favorite = PostFavorite(post_id=post_id, user_id=user_id)
        db.add(favorite)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
        
        count_result = await db.execute(
            select(func.count(PostFavorite.id)).where(PostFavorite.post_id == post_id)
        )
        return True, int(count_result.scalar() or 0)
    
    @staticmethod
    async def is_post_favorited(db: AsyncSession, post_id: int, user_id: int) -> bool:
        """检查用户是否收藏帖子"""
        result = await db.execute(
            select(PostFavorite).where(
                and_(PostFavorite.post_id == post_id, PostFavorite.user_id == user_id)
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_post_favorite_count(db: AsyncSession, post_id: int) -> int:
        """获取帖子收藏数"""
        result = await db.execute(
            select(func.count(PostFavorite.id)).where(PostFavorite.post_id == post_id)
        )
        return int(result.scalar() or 0)
    
    @staticmethod
    async def get_user_favorites(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None
    ) -> tuple[list[Post], int]:
        """获取用户收藏的帖子列表"""
        # 获取收藏的帖子 ID
        query = (
            select(Post)
            .join(PostFavorite, Post.id == PostFavorite.post_id)
            .options(selectinload(Post.author))
            .where(
                and_(
                    PostFavorite.user_id == user_id,
                    Post.is_deleted == False
                )
            )
        )

        if category:
            query = query.where(Post.category == category)

        if keyword:
            search_filter = Post.title.contains(keyword) | Post.content.contains(keyword)
            query = query.where(search_filter)

        query = (
            query
            .order_by(desc(PostFavorite.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        result = await db.execute(query)
        posts = result.scalars().all()
        
        # 获取总数
        count_query = (
            select(func.count(PostFavorite.id))
            .join(Post, Post.id == PostFavorite.post_id)
            .where(
                and_(
                    PostFavorite.user_id == user_id,
                    Post.is_deleted == False
                )
            )
        )

        if category:
            count_query = count_query.where(Post.category == category)

        if keyword:
            search_filter = Post.title.contains(keyword) | Post.content.contains(keyword)
            count_query = count_query.where(search_filter)

        count_result = await db.execute(count_query)
        total = int(count_result.scalar() or 0)
        
        return list(posts), int(total)
    
    @staticmethod
    async def get_user_stats(db: AsyncSession, user_id: int) -> dict[str, int]:
        """获取用户统计数据"""
        # 发布帖子数
        post_count_result = await db.execute(
            select(func.count(Post.id)).where(
                and_(Post.user_id == user_id, Post.is_deleted == False)
            )
        )
        post_count = post_count_result.scalar() or 0
        
        # 收藏数
        favorite_count_result = await db.execute(
            select(func.count(PostFavorite.id)).where(PostFavorite.user_id == user_id)
        )
        favorite_count = favorite_count_result.scalar() or 0
        
        # 评论数
        comment_count_result = await db.execute(
            select(func.count(Comment.id)).where(
                and_(Comment.user_id == user_id, Comment.is_deleted == False)
            )
        )
        comment_count = comment_count_result.scalar() or 0
        
        return {
            "post_count": int(post_count),
            "favorite_count": int(favorite_count),
            "comment_count": int(comment_count)
        }

    # ============ 热度计算 ============
    
    @staticmethod
    def calculate_heat_score(post: Post) -> float:
        """计算帖子热度分数
        
        热度算法：
        - 浏览量权重：0.1
        - 点赞数权重：1.0
        - 评论数权重：2.0
        - 分享数权重：3.0
        - 时间衰减：每24小时衰减10%
        """
        base_score = (
            post.view_count * 0.1 +
            post.like_count * 1.0 +
            post.comment_count * 2.0 +
            post.share_count * 3.0
        )
        
        # 时间衰减
        now = datetime.now(post.created_at.tzinfo) if post.created_at.tzinfo else datetime.now()
        age_hours = (now - post.created_at).total_seconds() / 3600
        decay = math.exp(-0.004 * age_hours)  # 约24小时衰减10%
        
        return round(base_score * decay, 2)
    
    @staticmethod
    async def update_heat_scores(db: AsyncSession) -> int:
        """批量更新所有帖子热度分数"""
        result = await db.execute(
            select(Post).where(Post.is_deleted == False)
        )
        posts = result.scalars().all()
        
        updated = 0
        for post in posts:
            new_score = ForumService.calculate_heat_score(post)
            if abs(post.heat_score - new_score) > 0.01:
                post.heat_score = new_score
                updated += 1
        
        await db.commit()
        return updated
    
    @staticmethod
    async def get_hot_posts(
        db: AsyncSession,
        limit: int = 10,
        category: str | None = None
    ) -> list[Post]:
        """获取热门帖子"""
        query = (
            select(Post)
            .options(selectinload(Post.author))
            .where(and_(Post.is_deleted == False))
            .order_by(desc(Post.heat_score), desc(Post.created_at))
            .limit(limit)
        )
        
        if category:
            query = query.where(Post.category == category)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def set_post_hot(db: AsyncSession, post_id: int, is_hot: bool) -> bool:
        """设置帖子为热门"""
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(is_hot=is_hot)
        )
        await db.commit()
        return cast(CursorResult[Any], result).rowcount > 0
    
    @staticmethod
    async def set_post_essence(db: AsyncSession, post_id: int, is_essence: bool) -> bool:
        """设置帖子为精华"""
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(is_essence=is_essence)
        )
        await db.commit()
        return cast(CursorResult[Any], result).rowcount > 0
    
    @staticmethod
    async def set_post_pinned(db: AsyncSession, post_id: int, is_pinned: bool) -> bool:
        """设置帖子置顶"""
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(is_pinned=is_pinned)
        )
        await db.commit()
        return cast(CursorResult[Any], result).rowcount > 0

    # ============ 表情反应 ============
    
    @staticmethod
    async def toggle_reaction(
        db: AsyncSession,
        post_id: int,
        user_id: int,
        emoji: str
    ) -> tuple[bool, list[dict[str, int | str]]]:
        """切换表情反应"""
        # 检查是否已存在该反应
        result = await db.execute(
            select(PostReaction).where(
                and_(
                    PostReaction.post_id == post_id,
                    PostReaction.user_id == user_id,
                    PostReaction.emoji == emoji
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # 取消反应
            await db.delete(existing)
            await db.commit()
            reacted = False
        else:
            # 添加反应
            reaction = PostReaction(post_id=post_id, user_id=user_id, emoji=emoji)
            db.add(reaction)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
            reacted = True
        
        # 获取当前所有反应统计
        reactions = await ForumService.get_post_reactions(db, post_id)
        return reacted, reactions
    
    @staticmethod
    async def get_post_reactions(db: AsyncSession, post_id: int) -> list[dict[str, int | str]]:
        """获取帖子的表情反应统计"""
        result = await db.execute(
            select(PostReaction.emoji, func.count(PostReaction.id).label("count"))
            .where(PostReaction.post_id == post_id)
            .group_by(PostReaction.emoji)
        )
        return [{"emoji": row[0], "count": row[1]} for row in result.all()]
    
    # ============ 统计相关 ============
    
    @staticmethod
    async def get_forum_stats(db: AsyncSession) -> dict[str, int | list[dict[str, int]]]:
        """获取论坛统计数据"""
        # 总帖子数
        total_posts_result = await db.execute(
            select(func.count(Post.id)).where(Post.is_deleted == False)
        )
        total_posts = total_posts_result.scalar() or 0
        
        # 总浏览量
        total_views_result = await db.execute(
            select(func.sum(Post.view_count)).where(Post.is_deleted == False)
        )
        total_views = total_views_result.scalar() or 0
        
        # 总点赞数
        total_likes_result = await db.execute(
            select(func.sum(Post.like_count)).where(Post.is_deleted == False)
        )
        total_likes = total_likes_result.scalar() or 0
        
        # 总评论数
        total_comments_result = await db.execute(
            select(func.count(Comment.id)).where(Comment.is_deleted == False)
        )
        total_comments = total_comments_result.scalar() or 0
        
        # 热门帖子数
        hot_posts_result = await db.execute(
            select(func.count(Post.id)).where(
                and_(Post.is_deleted == False, Post.is_hot == True)
            )
        )
        hot_posts_count = hot_posts_result.scalar() or 0
        
        # 精华帖数
        essence_posts_result = await db.execute(
            select(func.count(Post.id)).where(
                and_(Post.is_deleted == False, Post.is_essence == True)
            )
        )
        essence_posts_count = essence_posts_result.scalar() or 0
        
        # 分类统计
        category_result = await db.execute(
            select(Post.category, func.count(Post.id).label("count"))
            .where(Post.is_deleted == False)
            .group_by(Post.category)
        )
        category_stats = [
            {"category": row[0], "count": row[1]}
            for row in category_result.all()
        ]
        
        return {
            "total_posts": int(total_posts),
            "total_views": int(total_views),
            "total_likes": int(total_likes),
            "total_comments": int(total_comments),
            "hot_posts_count": int(hot_posts_count),
            "essence_posts_count": int(essence_posts_count),
            "category_stats": category_stats,
        }


forum_service = ForumService()
