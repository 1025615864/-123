"""论坛服务层"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_, update, case, delete
from sqlalchemy.engine import CursorResult
from typing import cast
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.exc import IntegrityError

from ..models.forum import Post, Comment, PostLike, PostFavorite, PostReaction, CommentLike
from ..schemas.forum import PostCreate, PostUpdate, CommentCreate
from .cache_service import cache_service
from ..utils.content_filter import (
    AD_WORDS,
    DEFAULT_AD_WORDS_THRESHOLD,
    DEFAULT_CHECK_PHONE,
    DEFAULT_CHECK_URL,
    SENSITIVE_WORDS,
    apply_content_filter_config,
    needs_review,
)
import json
import math
from datetime import datetime


class ForumService:
    """论坛服务"""

    _CONTENT_FILTER_SENSITIVE_KEY = "forum.content_filter.sensitive_words"
    _CONTENT_FILTER_AD_KEY = "forum.content_filter.ad_words"
    _CONTENT_FILTER_AD_THRESHOLD_KEY = "forum.content_filter.ad_words_threshold"
    _CONTENT_FILTER_CHECK_URL_KEY = "forum.content_filter.check_url"
    _CONTENT_FILTER_CHECK_PHONE_KEY = "forum.content_filter.check_phone"

    _CONTENT_FILTER_CACHE_KEY = "forum:content_filter_config:v1"
    _CONTENT_FILTER_CACHE_EXPIRE_SECONDS = 60

    @staticmethod
    def _parse_bool_value(value: str | None, default: bool = True) -> bool:
        if value is None:
            return default
        v = value.strip().lower()
        if v in ("1", "true", "yes", "y", "on"):
            return True
        if v in ("0", "false", "no", "n", "off"):
            return False
        return default

    @staticmethod
    async def is_comment_review_enabled(db: AsyncSession) -> bool:
        from ..models.system import SystemConfig

        result = await db.execute(
            select(SystemConfig.value).where(SystemConfig.key == "forum.review.enabled")
        )
        value: str | None = result.scalar_one_or_none()
        return ForumService._parse_bool_value(value, default=True)

    @staticmethod
    async def is_post_review_enabled(db: AsyncSession) -> bool:
        from ..models.system import SystemConfig

        result = await db.execute(
            select(SystemConfig.value).where(SystemConfig.key == "forum.post_review.enabled")
        )
        value: str | None = result.scalar_one_or_none()
        return ForumService._parse_bool_value(value, default=False)

    @staticmethod
    async def get_post_review_mode(db: AsyncSession) -> str:
        from ..models.system import SystemConfig

        result = await db.execute(
            select(SystemConfig.value).where(SystemConfig.key == "forum.post_review.mode")
        )
        value: str | None = result.scalar_one_or_none()
        if not value:
            return "rule"
        mode = value.strip().lower()
        if mode in ("all", "rule"):
            return mode
        return "rule"

    @staticmethod
    def _parse_int_value(value: str | None, default: int) -> int:
        if value is None:
            return int(default)
        try:
            v = int(str(value).strip())
        except (TypeError, ValueError):
            return int(default)
        return v if v > 0 else int(default)

    @staticmethod
    def _parse_json_list(value: str | None) -> list[str] | None:
        if not value:
            return None
        try:
            loaded = json.loads(value)
        except Exception:
            return None
        if not isinstance(loaded, list):
            return None
        result: list[str] = []
        seen: set[str] = set()
        for item in loaded:
            s = str(item).strip()
            if not s:
                continue
            if s in seen:
                continue
            seen.add(s)
            result.append(s)
        return result

    @staticmethod
    async def _upsert_system_config(
        db: AsyncSession,
        *,
        key: str,
        value: str,
        description: str,
        updated_by: int | None,
        category: str = "forum",
    ) -> None:
        from ..models.system import SystemConfig

        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        config = result.scalar_one_or_none()
        if config:
            config.value = value
            config.updated_by = updated_by
            if not config.description:
                config.description = description
            if not config.category:
                config.category = category
        else:
            db.add(
                SystemConfig(
                    key=key,
                    value=value,
                    description=description,
                    category=category,
                    updated_by=updated_by,
                )
            )

    @staticmethod
    async def get_content_filter_config(db: AsyncSession) -> dict[str, object]:
        from ..models.system import SystemConfig

        cached = await cache_service.get_json(ForumService._CONTENT_FILTER_CACHE_KEY)
        if isinstance(cached, dict):
            if (
                "sensitive_words" in cached
                and "ad_words" in cached
                and "ad_words_threshold" in cached
                and "check_url" in cached
                and "check_phone" in cached
            ):
                return cast(dict[str, object], cached)

        keys = (
            ForumService._CONTENT_FILTER_SENSITIVE_KEY,
            ForumService._CONTENT_FILTER_AD_KEY,
            ForumService._CONTENT_FILTER_AD_THRESHOLD_KEY,
            ForumService._CONTENT_FILTER_CHECK_URL_KEY,
            ForumService._CONTENT_FILTER_CHECK_PHONE_KEY,
        )

        result = await db.execute(
            select(SystemConfig.key, SystemConfig.value).where(SystemConfig.key.in_(list(keys)))
        )
        pairs = list(result.all())
        kv: dict[str, str | None] = {str(k): (str(v) if v is not None else None) for k, v in pairs}

        sensitive_words = ForumService._parse_json_list(kv.get(ForumService._CONTENT_FILTER_SENSITIVE_KEY))
        ad_words = ForumService._parse_json_list(kv.get(ForumService._CONTENT_FILTER_AD_KEY))

        if sensitive_words is None:
            sensitive_words = list(SENSITIVE_WORDS)
        if ad_words is None:
            ad_words = list(AD_WORDS)

        ad_words_threshold = ForumService._parse_int_value(
            kv.get(ForumService._CONTENT_FILTER_AD_THRESHOLD_KEY),
            DEFAULT_AD_WORDS_THRESHOLD,
        )
        check_url = ForumService._parse_bool_value(
            kv.get(ForumService._CONTENT_FILTER_CHECK_URL_KEY),
            default=DEFAULT_CHECK_URL,
        )
        check_phone = ForumService._parse_bool_value(
            kv.get(ForumService._CONTENT_FILTER_CHECK_PHONE_KEY),
            default=DEFAULT_CHECK_PHONE,
        )

        config: dict[str, object] = {
            "sensitive_words": sensitive_words,
            "ad_words": ad_words,
            "ad_words_threshold": int(ad_words_threshold),
            "check_url": bool(check_url),
            "check_phone": bool(check_phone),
        }

        await cache_service.set_json(
            ForumService._CONTENT_FILTER_CACHE_KEY,
            config,
            expire=ForumService._CONTENT_FILTER_CACHE_EXPIRE_SECONDS,
        )

        return config

    @staticmethod
    async def invalidate_content_filter_config_cache() -> None:
        await cache_service.delete(ForumService._CONTENT_FILTER_CACHE_KEY)

    @staticmethod
    async def apply_content_filter_config_from_db(db: AsyncSession) -> dict[str, object]:
        config = await ForumService.get_content_filter_config(db)
        apply_content_filter_config(
            sensitive_words=cast(list[str], config.get("sensitive_words")),
            ad_words=cast(list[str], config.get("ad_words")),
            ad_words_threshold=cast(int, config.get("ad_words_threshold")),
            check_url=cast(bool, config.get("check_url")),
            check_phone=cast(bool, config.get("check_phone")),
        )
        return config

    @staticmethod
    async def update_content_filter_rules(
        db: AsyncSession,
        *,
        updated_by: int | None,
        ad_words_threshold: int | None = None,
        check_url: bool | None = None,
        check_phone: bool | None = None,
    ) -> dict[str, object]:
        await ForumService.invalidate_content_filter_config_cache()
        current = await ForumService.get_content_filter_config(db)

        # 确保词库也落库（这样首次保存规则时会把默认词库写入DB，后续可持久化）
        await ForumService._upsert_system_config(
            db,
            key=ForumService._CONTENT_FILTER_SENSITIVE_KEY,
            value=json.dumps(cast(list[str], current.get("sensitive_words") or []), ensure_ascii=False),
            description="论坛内容过滤：敏感词列表",
            updated_by=updated_by,
        )
        await ForumService._upsert_system_config(
            db,
            key=ForumService._CONTENT_FILTER_AD_KEY,
            value=json.dumps(cast(list[str], current.get("ad_words") or []), ensure_ascii=False),
            description="论坛内容过滤：广告词列表",
            updated_by=updated_by,
        )

        raw_threshold = current.get("ad_words_threshold")
        next_threshold = DEFAULT_AD_WORDS_THRESHOLD
        if isinstance(raw_threshold, (int, float, str)):
            try:
                next_threshold = int(raw_threshold)
            except (TypeError, ValueError):
                next_threshold = DEFAULT_AD_WORDS_THRESHOLD
        if ad_words_threshold is not None:
            next_threshold = ad_words_threshold if int(ad_words_threshold) > 0 else DEFAULT_AD_WORDS_THRESHOLD

        next_check_url = bool(current.get("check_url") if current.get("check_url") is not None else DEFAULT_CHECK_URL)
        if check_url is not None:
            next_check_url = bool(check_url)

        next_check_phone = bool(
            current.get("check_phone") if current.get("check_phone") is not None else DEFAULT_CHECK_PHONE
        )
        if check_phone is not None:
            next_check_phone = bool(check_phone)

        await ForumService._upsert_system_config(
            db,
            key=ForumService._CONTENT_FILTER_AD_THRESHOLD_KEY,
            value=str(int(next_threshold)),
            description="论坛内容过滤：广告词命中阈值",
            updated_by=updated_by,
        )
        await ForumService._upsert_system_config(
            db,
            key=ForumService._CONTENT_FILTER_CHECK_URL_KEY,
            value="true" if next_check_url else "false",
            description="论坛内容过滤：是否检查链接",
            updated_by=updated_by,
        )
        await ForumService._upsert_system_config(
            db,
            key=ForumService._CONTENT_FILTER_CHECK_PHONE_KEY,
            value="true" if next_check_phone else "false",
            description="论坛内容过滤：是否检查手机号",
            updated_by=updated_by,
        )

        await db.commit()

        await ForumService.invalidate_content_filter_config_cache()
        return await ForumService.apply_content_filter_config_from_db(db)

    @staticmethod
    async def add_sensitive_word(db: AsyncSession, *, word: str, updated_by: int | None) -> dict[str, object]:
        await ForumService.invalidate_content_filter_config_cache()
        w = str(word or "").strip()
        if not w:
            return await ForumService.apply_content_filter_config_from_db(db)

        current = await ForumService.get_content_filter_config(db)
        words = cast(list[str], current.get("sensitive_words"))
        if w not in words:
            words.append(w)

        await ForumService._upsert_system_config(
            db,
            key=ForumService._CONTENT_FILTER_SENSITIVE_KEY,
            value=json.dumps(words, ensure_ascii=False),
            description="论坛内容过滤：敏感词列表",
            updated_by=updated_by,
        )
        await db.commit()
        await ForumService.invalidate_content_filter_config_cache()
        return await ForumService.apply_content_filter_config_from_db(db)

    @staticmethod
    async def remove_sensitive_word(db: AsyncSession, *, word: str, updated_by: int | None) -> dict[str, object]:
        await ForumService.invalidate_content_filter_config_cache()
        w = str(word or "").strip()
        current = await ForumService.get_content_filter_config(db)
        words = [x for x in cast(list[str], current.get("sensitive_words")) if x != w]

        await ForumService._upsert_system_config(
            db,
            key=ForumService._CONTENT_FILTER_SENSITIVE_KEY,
            value=json.dumps(words, ensure_ascii=False),
            description="论坛内容过滤：敏感词列表",
            updated_by=updated_by,
        )
        await db.commit()
        await ForumService.invalidate_content_filter_config_cache()
        return await ForumService.apply_content_filter_config_from_db(db)

    @staticmethod
    async def add_ad_word(db: AsyncSession, *, word: str, updated_by: int | None) -> dict[str, object]:
        await ForumService.invalidate_content_filter_config_cache()
        w = str(word or "").strip()
        if not w:
            return await ForumService.apply_content_filter_config_from_db(db)

        current = await ForumService.get_content_filter_config(db)
        words = cast(list[str], current.get("ad_words"))
        if w not in words:
            words.append(w)

        await ForumService._upsert_system_config(
            db,
            key=ForumService._CONTENT_FILTER_AD_KEY,
            value=json.dumps(words, ensure_ascii=False),
            description="论坛内容过滤：广告词列表",
            updated_by=updated_by,
        )
        await db.commit()
        await ForumService.invalidate_content_filter_config_cache()
        return await ForumService.apply_content_filter_config_from_db(db)

    @staticmethod
    async def remove_ad_word(db: AsyncSession, *, word: str, updated_by: int | None) -> dict[str, object]:
        await ForumService.invalidate_content_filter_config_cache()
        w = str(word or "").strip()
        current = await ForumService.get_content_filter_config(db)
        words = [x for x in cast(list[str], current.get("ad_words")) if x != w]

        await ForumService._upsert_system_config(
            db,
            key=ForumService._CONTENT_FILTER_AD_KEY,
            value=json.dumps(words, ensure_ascii=False),
            description="论坛内容过滤：广告词列表",
            updated_by=updated_by,
        )
        await db.commit()
        await ForumService.invalidate_content_filter_config_cache()
        return await ForumService.apply_content_filter_config_from_db(db)
    
    # ============ 帖子相关 ============
    
    @staticmethod
    async def create_post(db: AsyncSession, user_id: int, post_data: PostCreate) -> Post:
        """创建帖子"""
        # 处理图片和附件
        images_json = json.dumps(post_data.images) if post_data.images else None
        attachments_json = json.dumps(post_data.attachments) if post_data.attachments else None

        _ = await ForumService.apply_content_filter_config_from_db(db)

        requires_review = False
        review_reason: str | None = None

        review_enabled = await ForumService.is_post_review_enabled(db)
        if not review_enabled:
            review_status = "approved"
        else:
            review_mode = await ForumService.get_post_review_mode(db)
            if review_mode == "all":
                requires_review = True
                review_reason = "全量审核"
                review_status = "pending"
            else:
                requires_review, review_reason = needs_review(f"{post_data.title}\n{post_data.content}")
                review_status = "pending" if requires_review else "approved"
        
        post = Post(
            title=post_data.title,
            content=post_data.content,
            category=post_data.category,
            user_id=user_id,
            cover_image=post_data.cover_image,
            images=images_json,
            attachments=attachments_json,
            review_status=review_status,
            review_reason=review_reason if requires_review else None,
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post
    
    @staticmethod
    async def get_post(db: AsyncSession, post_id: int) -> Post | None:
        """获取帖子详情"""
        approved_filter = or_(Post.review_status.is_(None), Post.review_status == "approved")
        result = await db.execute(
            select(Post)
            .options(selectinload(Post.author))
            .where(and_(Post.id == post_id, Post.is_deleted == False, approved_filter))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_post_any(db: AsyncSession, post_id: int) -> Post | None:
        """获取帖子详情（包含已删除）"""
        result = await db.execute(
            select(Post)
            .options(selectinload(Post.author))
            .where(Post.id == post_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_posts(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None,
        is_essence: bool | None = None,
        include_deleted: bool = False,
        deleted: bool | None = None,
        approved_only: bool = True,
    ) -> tuple[list[Post], int]:
        """获取帖子列表"""
        query = select(Post).options(selectinload(Post.author))
        count_query = select(func.count(Post.id))

        if deleted is True:
            query = query.where(Post.is_deleted == True)
            count_query = count_query.where(Post.is_deleted == True)
        elif deleted is False:
            query = query.where(Post.is_deleted == False)
            count_query = count_query.where(Post.is_deleted == False)
        else:
            if not include_deleted:
                query = query.where(Post.is_deleted == False)
                count_query = count_query.where(Post.is_deleted == False)

        if approved_only and deleted is not True:
            approved_filter = or_(Post.review_status.is_(None), Post.review_status == "approved")
            query = query.where(approved_filter)
            count_query = count_query.where(approved_filter)
        
        if category:
            query = query.where(Post.category == category)
            count_query = count_query.where(Post.category == category)
        
        if keyword:
            search_filter = Post.title.contains(keyword) | Post.content.contains(keyword)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        if is_essence is True:
            query = query.where(Post.is_essence == True)
            count_query = count_query.where(Post.is_essence == True)
        elif is_essence is False:
            query = query.where(Post.is_essence == False)
            count_query = count_query.where(Post.is_essence == False)
        
        # 置顶优先，然后按时间倒序
        query = query.order_by(desc(Post.is_pinned), desc(Post.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        posts = result.scalars().all()
        
        count_result = await db.execute(count_query)
        total = int(count_result.scalar() or 0)
        
        return list(posts), total

    @staticmethod
    async def get_user_deleted_posts(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        keyword: str | None = None,
    ) -> tuple[list[Post], int]:
        """获取用户删除的帖子列表（回收站）"""
        query = (
            select(Post)
            .options(selectinload(Post.author))
            .where(and_(Post.user_id == user_id, Post.is_deleted == True))
        )
        count_query = select(func.count(Post.id)).where(and_(Post.user_id == user_id, Post.is_deleted == True))

        if category:
            query = query.where(Post.category == category)
            count_query = count_query.where(Post.category == category)

        if keyword:
            search_filter = Post.title.contains(keyword) | Post.content.contains(keyword)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        query = query.order_by(desc(Post.updated_at))
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
        if "images" in update_data:
            update_data["images"] = json.dumps(update_data["images"]) if update_data.get("images") else None
        if "attachments" in update_data:
            update_data["attachments"] = (
                json.dumps(update_data["attachments"]) if update_data.get("attachments") else None
            )
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
    async def restore_post(db: AsyncSession, post: Post) -> Post:
        """恢复帖子（回收站 -> 正常）"""
        post.is_deleted = False
        await db.commit()
        await db.refresh(post)
        return post

    @staticmethod
    async def purge_post(db: AsyncSession, post: Post) -> None:
        """永久删除帖子（硬删除）"""
        # 删除评论点赞 -> 评论 -> 帖子点赞/收藏/反应 -> 帖子
        comment_ids_subq = select(Comment.id).where(Comment.post_id == post.id)

        _ = await db.execute(delete(CommentLike).where(CommentLike.comment_id.in_(comment_ids_subq)))
        _ = await db.execute(delete(Comment).where(Comment.post_id == post.id))

        _ = await db.execute(delete(PostLike).where(PostLike.post_id == post.id))
        _ = await db.execute(delete(PostFavorite).where(PostFavorite.post_id == post.id))
        _ = await db.execute(delete(PostReaction).where(PostReaction.post_id == post.id))

        await db.delete(post)
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
                        (
                            func.coalesce(Post.like_count, 0) > 0,
                            func.coalesce(Post.like_count, 0) - 1,
                        ),
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
            .values(like_count=func.coalesce(Post.like_count, 0) + 1)
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
        images_json = json.dumps(comment_data.images) if comment_data.images else None

        _ = await ForumService.apply_content_filter_config_from_db(db)

        requires_review = False
        review_reason: str | None = None

        review_enabled = await ForumService.is_comment_review_enabled(db)
        if not review_enabled:
            review_status = "approved"
        else:
            requires_review, review_reason = needs_review(comment_data.content)
            review_status = "pending" if requires_review else "approved"

        comment = Comment(
            content=comment_data.content,
            post_id=post_id,
            user_id=user_id,
            parent_id=comment_data.parent_id,
            images=images_json,
            review_status=review_status,
            review_reason=review_reason if requires_review else None,
        )
        db.add(comment)

        if review_status == "approved":
            _ = await db.execute(
                update(Post)
                .where(Post.id == post_id)
                .values(comment_count=func.coalesce(Post.comment_count, 0) + 1)
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
        approved_filter = or_(Comment.review_status.is_(None), Comment.review_status == "approved")
        result = await db.execute(
            select(Comment)
            .options(joinedload(Comment.author))
            .where(
                and_(
                    Comment.post_id == post_id,
                    approved_filter,
                    Comment.is_deleted == False,
                )
            )
            .order_by(desc(Comment.created_at))
        )

        all_comments = list(result.scalars().all())
        top_level = [c for c in all_comments if c.parent_id is None]
        total = len(top_level)

        start = max(0, (page - 1) * page_size)
        end = start + page_size
        page_top = top_level[start:end]

        children_by_parent: dict[int, list[Comment]] = {}
        for c in all_comments:
            if c.parent_id is None:
                continue
            children_by_parent.setdefault(int(c.parent_id), []).append(c)

        def _created_at_ts(value: Comment) -> float:
            created_at = getattr(value, "created_at", None)
            if isinstance(created_at, datetime):
                try:
                    return float(created_at.timestamp())
                except (OSError, ValueError, OverflowError):
                    return 0.0
            return 0.0

        for children in children_by_parent.values():
            children.sort(key=_created_at_ts)

        def attach_replies(node: Comment) -> None:
            replies = children_by_parent.get(int(node.id), [])
            set_committed_value(node, "replies", replies)
            for child in replies:
                attach_replies(child)

        for c in page_top:
            attach_replies(c)

        return list(page_top), int(total)

    @staticmethod
    async def get_comments_visible(
        db: AsyncSession,
        post_id: int,
        page: int = 1,
        page_size: int = 50,
        viewer_user_id: int | None = None,
        viewer_role: str | None = None,
        include_unapproved: bool = False,
    ) -> tuple[list[Comment], int]:
        if not include_unapproved or not viewer_user_id:
            return await ForumService.get_comments(db, post_id, page, page_size)

        is_admin = (viewer_role or "") in ("admin", "super_admin", "moderator")

        viewer_id = int(viewer_user_id)

        not_rejected_filter = or_(Comment.review_status.is_(None), Comment.review_status != "rejected")

        if is_admin:
            base_filter = and_(
                Comment.post_id == post_id,
                or_(
                    and_(Comment.is_deleted == False, not_rejected_filter),
                    and_(Comment.user_id == viewer_id, Comment.review_status == "rejected"),
                ),
            )
        else:
            approved_filter = or_(Comment.review_status.is_(None), Comment.review_status == "approved")
            base_filter = and_(
                Comment.post_id == post_id,
                or_(
                    and_(Comment.is_deleted == False, approved_filter),
                    and_(Comment.user_id == viewer_id, Comment.review_status == "pending", Comment.is_deleted == False),
                    and_(Comment.user_id == viewer_id, Comment.review_status == "rejected"),
                ),
            )

        result = await db.execute(
            select(Comment)
            .options(joinedload(Comment.author))
            .where(base_filter)
            .order_by(desc(Comment.created_at))
        )

        all_comments = list(result.scalars().all())
        top_level = [c for c in all_comments if c.parent_id is None]
        total = len(top_level)

        start = max(0, (page - 1) * page_size)
        end = start + page_size
        page_top = top_level[start:end]

        children_by_parent: dict[int, list[Comment]] = {}
        for c in all_comments:
            if c.parent_id is None:
                continue
            children_by_parent.setdefault(int(c.parent_id), []).append(c)

        def _created_at_ts(value: Comment) -> float:
            created_at = getattr(value, "created_at", None)
            if isinstance(created_at, datetime):
                try:
                    return float(created_at.timestamp())
                except (OSError, ValueError, OverflowError):
                    return 0.0
            return 0.0

        for children in children_by_parent.values():
            children.sort(key=_created_at_ts)

        def attach_replies(node: Comment) -> None:
            replies = children_by_parent.get(int(node.id), [])
            set_committed_value(node, "replies", replies)
            for child in replies:
                attach_replies(child)

        for c in page_top:
            attach_replies(c)

        return list(page_top), int(total)
    
    @staticmethod
    async def delete_comment(db: AsyncSession, comment: Comment) -> None:
        """删除评论（软删除）"""
        comment.is_deleted = True

        if comment.review_status in (None, "approved"):
            _ = await db.execute(
                update(Post)
                .where(Post.id == comment.post_id)
                .values(
                    comment_count=case(
                        (
                            func.coalesce(Post.comment_count, 0) > 0,
                            func.coalesce(Post.comment_count, 0) - 1,
                        ),
                        else_=0,
                    )
                )
            )

        await db.commit()

    @staticmethod
    async def restore_comment(db: AsyncSession, comment: Comment) -> Comment:
        """恢复评论（撤销删除）"""
        if not getattr(comment, "is_deleted", False):
            return comment

        comment.is_deleted = False

        if comment.review_status in (None, "approved"):
            _ = await db.execute(
                update(Post)
                .where(Post.id == comment.post_id)
                .values(comment_count=func.coalesce(Post.comment_count, 0) + 1)
            )

        await db.commit()
        await db.refresh(comment)
        return comment
    
    @staticmethod
    async def get_comment(db: AsyncSession, comment_id: int) -> Comment | None:
        """获取评论"""
        result = await db.execute(
            select(Comment).where(
                and_(Comment.id == comment_id, Comment.is_deleted == False)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_comment_any(db: AsyncSession, comment_id: int) -> Comment | None:
        """获取评论（包含已删除）"""
        result = await db.execute(select(Comment).where(Comment.id == comment_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def is_comment_liked(db: AsyncSession, comment_id: int, user_id: int) -> bool:
        result = await db.execute(
            select(CommentLike).where(
                and_(CommentLike.comment_id == comment_id, CommentLike.user_id == user_id)
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def toggle_comment_like(db: AsyncSession, comment_id: int, user_id: int) -> tuple[bool, int]:
        result = await db.execute(
            select(CommentLike).where(
                and_(CommentLike.comment_id == comment_id, CommentLike.user_id == user_id)
            )
        )
        existing_like = result.scalar_one_or_none()

        if existing_like:
            await db.delete(existing_like)
            _ = await db.execute(
                update(Comment)
                .where(Comment.id == comment_id)
                .values(
                    like_count=case(
                        (
                            func.coalesce(Comment.like_count, 0) > 0,
                            func.coalesce(Comment.like_count, 0) - 1,
                        ),
                        else_=0,
                    )
                )
            )
            await db.commit()
            like_count_result = await db.execute(select(Comment.like_count).where(Comment.id == comment_id))
            return False, int(like_count_result.scalar() or 0)

        like = CommentLike(comment_id=comment_id, user_id=user_id)
        db.add(like)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()

        _ = await db.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(like_count=func.coalesce(Comment.like_count, 0) + 1)
        )
        await db.commit()
        like_count_result = await db.execute(select(Comment.like_count).where(Comment.id == comment_id))
        return True, int(like_count_result.scalar() or 0)

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
                    Post.is_deleted == False,
                    or_(Post.review_status.is_(None), Post.review_status == "approved"),
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
                    Post.is_deleted == False,
                    or_(Post.review_status.is_(None), Post.review_status == "approved"),
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
            select(Post).where(
                and_(
                    Post.is_deleted == False,
                    or_(Post.review_status.is_(None), Post.review_status == "approved"),
                )
            )
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
            .where(
                and_(
                    Post.is_deleted == False,
                    or_(Post.review_status.is_(None), Post.review_status == "approved"),
                )
            )
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
        cursor = cast(CursorResult[tuple[object, ...]], result)
        rowcount = getattr(cursor, "rowcount", 0)
        return int(rowcount or 0) > 0
    
    @staticmethod
    async def set_post_essence(db: AsyncSession, post_id: int, is_essence: bool) -> bool:
        """设置帖子为精华"""
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(is_essence=is_essence)
        )
        await db.commit()
        cursor = cast(CursorResult[tuple[object, ...]], result)
        rowcount = getattr(cursor, "rowcount", 0)
        return int(rowcount or 0) > 0
    
    @staticmethod
    async def set_post_pinned(db: AsyncSession, post_id: int, is_pinned: bool) -> bool:
        """设置帖子置顶"""
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(is_pinned=is_pinned)
        )
        await db.commit()
        cursor = cast(CursorResult[tuple[object, ...]], result)
        rowcount = getattr(cursor, "rowcount", 0)
        return int(rowcount or 0) > 0

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
        approved_comments_result = await db.execute(
            select(func.count(Comment.id)).where(
                and_(
                    Comment.is_deleted == False,
                    or_(Comment.review_status.is_(None), Comment.review_status == "approved"),
                )
            )
        )
        approved_comments = approved_comments_result.scalar() or 0
        
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
            "total_comments": int(approved_comments),
            "hot_posts_count": int(hot_posts_count),
            "essence_posts_count": int(essence_posts_count),
            "category_stats": category_stats,
        }


forum_service = ForumService()
