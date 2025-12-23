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
                if "review_status" not in posts_cols:
                    posts_missing.append(
                        "ALTER TABLE posts ADD COLUMN review_status VARCHAR(20) DEFAULT 'approved'"
                    )
                if "review_reason" not in posts_cols:
                    posts_missing.append("ALTER TABLE posts ADD COLUMN review_reason VARCHAR(200)")
                if "reviewed_at" not in posts_cols:
                    posts_missing.append("ALTER TABLE posts ADD COLUMN reviewed_at DATETIME")

                for stmt in posts_missing:
                    _ = await conn.execute(text(stmt))

                comments_cols_result = await conn.execute(text("PRAGMA table_info(comments)"))
                comments_cols = {row[1] for row in comments_cols_result.fetchall()}
                if "images" not in comments_cols:
                    _ = await conn.execute(text("ALTER TABLE comments ADD COLUMN images TEXT"))
                if "review_status" not in comments_cols:
                    _ = await conn.execute(text("ALTER TABLE comments ADD COLUMN review_status VARCHAR(20)"))
                if "review_reason" not in comments_cols:
                    _ = await conn.execute(text("ALTER TABLE comments ADD COLUMN review_reason VARCHAR(200)"))
                if "reviewed_at" not in comments_cols:
                    _ = await conn.execute(text("ALTER TABLE comments ADD COLUMN reviewed_at DATETIME"))

                chat_cols_result = await conn.execute(text("PRAGMA table_info(chat_messages)"))
                chat_cols = {row[1] for row in chat_cols_result.fetchall()}
                if "rating" not in chat_cols:
                    _ = await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN rating INTEGER"))
                if "feedback" not in chat_cols:
                    _ = await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN feedback TEXT"))

                payment_orders_cols_result = await conn.execute(text("PRAGMA table_info(payment_orders)"))
                payment_orders_cols = {row[1] for row in payment_orders_cols_result.fetchall()}
                payment_orders_missing: list[str] = []
                if "amount_cents" not in payment_orders_cols:
                    payment_orders_missing.append("ALTER TABLE payment_orders ADD COLUMN amount_cents INTEGER")
                if "actual_amount_cents" not in payment_orders_cols:
                    payment_orders_missing.append("ALTER TABLE payment_orders ADD COLUMN actual_amount_cents INTEGER")
                for stmt in payment_orders_missing:
                    _ = await conn.execute(text(stmt))

                user_balances_cols_result = await conn.execute(text("PRAGMA table_info(user_balances)"))
                user_balances_cols = {row[1] for row in user_balances_cols_result.fetchall()}
                user_balances_missing: list[str] = []
                if "balance_cents" not in user_balances_cols:
                    user_balances_missing.append("ALTER TABLE user_balances ADD COLUMN balance_cents INTEGER")
                if "frozen_cents" not in user_balances_cols:
                    user_balances_missing.append("ALTER TABLE user_balances ADD COLUMN frozen_cents INTEGER")
                if "total_recharged_cents" not in user_balances_cols:
                    user_balances_missing.append("ALTER TABLE user_balances ADD COLUMN total_recharged_cents INTEGER")
                if "total_consumed_cents" not in user_balances_cols:
                    user_balances_missing.append("ALTER TABLE user_balances ADD COLUMN total_consumed_cents INTEGER")
                for stmt in user_balances_missing:
                    _ = await conn.execute(text(stmt))

                balance_tx_cols_result = await conn.execute(text("PRAGMA table_info(balance_transactions)"))
                balance_tx_cols = {row[1] for row in balance_tx_cols_result.fetchall()}
                balance_tx_missing: list[str] = []
                if "amount_cents" not in balance_tx_cols:
                    balance_tx_missing.append("ALTER TABLE balance_transactions ADD COLUMN amount_cents INTEGER")
                if "balance_before_cents" not in balance_tx_cols:
                    balance_tx_missing.append("ALTER TABLE balance_transactions ADD COLUMN balance_before_cents INTEGER")
                if "balance_after_cents" not in balance_tx_cols:
                    balance_tx_missing.append("ALTER TABLE balance_transactions ADD COLUMN balance_after_cents INTEGER")
                for stmt in balance_tx_missing:
                    _ = await conn.execute(text(stmt))

                _ = await conn.execute(
                    text(
                        "UPDATE payment_orders SET amount_cents = CAST(ROUND(amount * 100) AS INTEGER) WHERE amount_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE payment_orders SET actual_amount_cents = CAST(ROUND(actual_amount * 100) AS INTEGER) WHERE actual_amount_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE user_balances SET balance_cents = CAST(ROUND(balance * 100) AS INTEGER) WHERE balance_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE user_balances SET frozen_cents = CAST(ROUND(frozen * 100) AS INTEGER) WHERE frozen_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE user_balances SET total_recharged_cents = CAST(ROUND(total_recharged * 100) AS INTEGER) WHERE total_recharged_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE user_balances SET total_consumed_cents = CAST(ROUND(total_consumed * 100) AS INTEGER) WHERE total_consumed_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE balance_transactions SET amount_cents = CAST(ROUND(amount * 100) AS INTEGER) WHERE amount_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE balance_transactions SET balance_before_cents = CAST(ROUND(balance_before * 100) AS INTEGER) WHERE balance_before_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE balance_transactions SET balance_after_cents = CAST(ROUND(balance_after * 100) AS INTEGER) WHERE balance_after_cents IS NULL"
                    )
                )
            except Exception:
                logger.exception("SQLite表结构自修复失败")

        if engine.url.get_backend_name() == "postgresql":
            try:
                _ = await conn.execute(
                    text(
                        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS review_status VARCHAR(20)"
                    )
                )
                _ = await conn.execute(
                    text(
                        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS review_reason VARCHAR(200)"
                    )
                )
                _ = await conn.execute(
                    text(
                        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ"
                    )
                )

                _ = await conn.execute(
                    text(
                        "ALTER TABLE comments ADD COLUMN IF NOT EXISTS review_status VARCHAR(20)"
                    )
                )
                _ = await conn.execute(
                    text(
                        "ALTER TABLE comments ADD COLUMN IF NOT EXISTS review_reason VARCHAR(200)"
                    )
                )
                _ = await conn.execute(
                    text(
                        "ALTER TABLE comments ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ"
                    )
                )

                _ = await conn.execute(text("ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS amount_cents INTEGER"))
                _ = await conn.execute(text("ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS actual_amount_cents INTEGER"))
                _ = await conn.execute(text("ALTER TABLE user_balances ADD COLUMN IF NOT EXISTS balance_cents INTEGER"))
                _ = await conn.execute(text("ALTER TABLE user_balances ADD COLUMN IF NOT EXISTS frozen_cents INTEGER"))
                _ = await conn.execute(text("ALTER TABLE user_balances ADD COLUMN IF NOT EXISTS total_recharged_cents INTEGER"))
                _ = await conn.execute(text("ALTER TABLE user_balances ADD COLUMN IF NOT EXISTS total_consumed_cents INTEGER"))
                _ = await conn.execute(text("ALTER TABLE balance_transactions ADD COLUMN IF NOT EXISTS amount_cents INTEGER"))
                _ = await conn.execute(text("ALTER TABLE balance_transactions ADD COLUMN IF NOT EXISTS balance_before_cents INTEGER"))
                _ = await conn.execute(text("ALTER TABLE balance_transactions ADD COLUMN IF NOT EXISTS balance_after_cents INTEGER"))

                _ = await conn.execute(
                    text(
                        "UPDATE payment_orders SET amount_cents = CAST(ROUND(amount * 100) AS INTEGER) WHERE amount_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE payment_orders SET actual_amount_cents = CAST(ROUND(actual_amount * 100) AS INTEGER) WHERE actual_amount_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE user_balances SET balance_cents = CAST(ROUND(balance * 100) AS INTEGER) WHERE balance_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE user_balances SET frozen_cents = CAST(ROUND(frozen * 100) AS INTEGER) WHERE frozen_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE user_balances SET total_recharged_cents = CAST(ROUND(total_recharged * 100) AS INTEGER) WHERE total_recharged_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE user_balances SET total_consumed_cents = CAST(ROUND(total_consumed * 100) AS INTEGER) WHERE total_consumed_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE balance_transactions SET amount_cents = CAST(ROUND(amount * 100) AS INTEGER) WHERE amount_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE balance_transactions SET balance_before_cents = CAST(ROUND(balance_before * 100) AS INTEGER) WHERE balance_before_cents IS NULL"
                    )
                )
                _ = await conn.execute(
                    text(
                        "UPDATE balance_transactions SET balance_after_cents = CAST(ROUND(balance_after * 100) AS INTEGER) WHERE balance_after_cents IS NULL"
                    )
                )
            except Exception:
                logger.exception("PostgreSQL表结构自修复失败")

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
