"""数据库配置"""
import importlib
import logging
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from .config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

if settings.database_url.startswith("sqlite"):
    parts = settings.database_url.split("///", 1)
    if len(parts) == 2:
        db_path = parts[1]
        if db_path.startswith("./"):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    pass


async def get_db():
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库表"""
    for module_name in (
        "app.models.user",
        "app.models.consultation",
        "app.models.forum",
        "app.models.news",
        "app.models.lawfirm",
        "app.models.knowledge",
        "app.models.notification",
        "app.models.payment",
        "app.models.system",
    ):
        _ = importlib.import_module(module_name)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        if engine.url.get_backend_name() == "sqlite":
            try:
                posts_cols_result = await conn.execute(text("PRAGMA table_info(posts)"))
                posts_cols = {row[1] for row in posts_cols_result.fetchall()}
                posts_missing: list[str] = []

                if "share_count" not in posts_cols:
                    posts_missing.append("ALTER TABLE posts ADD COLUMN share_count INTEGER DEFAULT 0")
                if "is_hot" not in posts_cols:
                    posts_missing.append("ALTER TABLE posts ADD COLUMN is_hot BOOLEAN DEFAULT 0")
                if "is_essence" not in posts_cols:
                    posts_missing.append("ALTER TABLE posts ADD COLUMN is_essence BOOLEAN DEFAULT 0")
                if "heat_score" not in posts_cols:
                    posts_missing.append("ALTER TABLE posts ADD COLUMN heat_score REAL DEFAULT 0.0")
                if "cover_image" not in posts_cols:
                    posts_missing.append("ALTER TABLE posts ADD COLUMN cover_image VARCHAR(500)")
                if "images" not in posts_cols:
                    posts_missing.append("ALTER TABLE posts ADD COLUMN images TEXT")
                if "attachments" not in posts_cols:
                    posts_missing.append("ALTER TABLE posts ADD COLUMN attachments TEXT")
                if "updated_at" not in posts_cols:
                    posts_missing.append("ALTER TABLE posts ADD COLUMN updated_at DATETIME")

                for stmt in posts_missing:
                    _ = await conn.execute(text(stmt))

                comments_cols_result = await conn.execute(text("PRAGMA table_info(comments)"))
                comments_cols = {row[1] for row in comments_cols_result.fetchall()}
                if "images" not in comments_cols:
                    _ = await conn.execute(text("ALTER TABLE comments ADD COLUMN images TEXT"))

                chat_cols_result = await conn.execute(text("PRAGMA table_info(chat_messages)"))
                chat_cols = {row[1] for row in chat_cols_result.fetchall()}
                if "rating" not in chat_cols:
                    _ = await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN rating INTEGER"))
                if "feedback" not in chat_cols:
                    _ = await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN feedback TEXT"))
            except Exception:
                logger.exception("SQLite表结构自修复失败")

        try:
            post_dedup_result = await conn.execute(
                text(
                    "DELETE FROM post_likes WHERE id NOT IN (SELECT MIN(id) FROM post_likes GROUP BY post_id, user_id)"
                )
            )
            comment_dedup_result = await conn.execute(
                text(
                    "DELETE FROM comment_likes WHERE id NOT IN (SELECT MIN(id) FROM comment_likes GROUP BY comment_id, user_id)"
                )
            )
            logger.info(
                "重复点赞数据清理完成：post_likes=%s, comment_likes=%s",
                getattr(post_dedup_result, "rowcount", None),
                getattr(comment_dedup_result, "rowcount", None),
            )
        except Exception:
            logger.exception("清理重复点赞数据失败")

        try:
            _ = await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_post_like_post_user ON post_likes (post_id, user_id)"
                )
            )
            _ = await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_comment_like_comment_user ON comment_likes (comment_id, user_id)"
                )
            )
        except Exception:
            logger.exception("创建唯一索引失败（可能存在历史重复数据）")
