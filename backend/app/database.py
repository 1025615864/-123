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


async def init_db() -> None:
    """初始化数据库表"""
    for module_name in (
        "app.models.user",
        "app.models.consultation",
        "app.models.forum",
        "app.models.news",
        "app.models.news_ai",
        "app.models.news_workbench",
        "app.models.lawfirm",
        "app.models.knowledge",
        "app.models.notification",
        "app.models.payment",
        "app.models.system",
        "app.models.calendar",
    ):
        _ = importlib.import_module(module_name)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        if engine.url.get_backend_name() == "sqlite":
            try:
                news_cols_result = await conn.execute(text("PRAGMA table_info(news)"))
                news_cols = {row[1] for row in news_cols_result.fetchall()}
                if "scheduled_publish_at" not in news_cols:
                    _ = await conn.execute(text("ALTER TABLE news ADD COLUMN scheduled_publish_at DATETIME"))
                if "scheduled_unpublish_at" not in news_cols:
                    _ = await conn.execute(text("ALTER TABLE news ADD COLUMN scheduled_unpublish_at DATETIME"))
                if "source_url" not in news_cols:
                    _ = await conn.execute(text("ALTER TABLE news ADD COLUMN source_url VARCHAR(500)"))
                if "dedupe_hash" not in news_cols:
                    _ = await conn.execute(text("ALTER TABLE news ADD COLUMN dedupe_hash VARCHAR(40)"))
                    try:
                        _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_dedupe_hash ON news(dedupe_hash)"))
                    except Exception:
                        logger.exception("创建news dedupe_hash索引失败")
                if "source_site" not in news_cols:
                    _ = await conn.execute(text("ALTER TABLE news ADD COLUMN source_site VARCHAR(100)"))
                if "review_status" not in news_cols:
                    _ = await conn.execute(text("ALTER TABLE news ADD COLUMN review_status VARCHAR(20) DEFAULT 'approved'"))
                if "review_reason" not in news_cols:
                    _ = await conn.execute(text("ALTER TABLE news ADD COLUMN review_reason VARCHAR(200)"))
                if "reviewed_at" not in news_cols:
                    _ = await conn.execute(text("ALTER TABLE news ADD COLUMN reviewed_at DATETIME"))

                tables_result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = {row[0] for row in tables_result.fetchall()}

                if "news_ai_annotations" in tables:
                    ann_cols_result = await conn.execute(text("PRAGMA table_info(news_ai_annotations)"))
                    ann_cols = {row[1] for row in ann_cols_result.fetchall()}
                    if "highlights" not in ann_cols:
                        _ = await conn.execute(text("ALTER TABLE news_ai_annotations ADD COLUMN highlights TEXT"))
                    if "keywords" not in ann_cols:
                        _ = await conn.execute(text("ALTER TABLE news_ai_annotations ADD COLUMN keywords TEXT"))
                    if "retry_count" not in ann_cols:
                        _ = await conn.execute(
                            text("ALTER TABLE news_ai_annotations ADD COLUMN retry_count INTEGER DEFAULT 0")
                        )
                    if "last_error" not in ann_cols:
                        _ = await conn.execute(text("ALTER TABLE news_ai_annotations ADD COLUMN last_error TEXT"))
                    if "last_error_at" not in ann_cols:
                        _ = await conn.execute(text("ALTER TABLE news_ai_annotations ADD COLUMN last_error_at DATETIME"))

                if "news_comments" not in tables:
                    _ = await conn.execute(
                        text(
                            "CREATE TABLE IF NOT EXISTS news_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, news_id INTEGER NOT NULL, user_id INTEGER NOT NULL, content TEXT NOT NULL, is_deleted BOOLEAN DEFAULT 0, review_status VARCHAR(20) DEFAULT 'approved', review_reason VARCHAR(200), reviewed_at DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                        )
                    )
                    _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_comments_news_id ON news_comments(news_id)"))
                    _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_comments_user_id ON news_comments(user_id)"))
                    _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_comments_created_at ON news_comments(created_at)"))
                else:
                    comments_cols_result = await conn.execute(text("PRAGMA table_info(news_comments)"))
                    comments_cols = {row[1] for row in comments_cols_result.fetchall()}
                    if "is_deleted" not in comments_cols:
                        _ = await conn.execute(text("ALTER TABLE news_comments ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                    if "review_status" not in comments_cols:
                        _ = await conn.execute(text("ALTER TABLE news_comments ADD COLUMN review_status VARCHAR(20) DEFAULT 'approved'"))
                    if "review_reason" not in comments_cols:
                        _ = await conn.execute(text("ALTER TABLE news_comments ADD COLUMN review_reason VARCHAR(200)"))
                    if "reviewed_at" not in comments_cols:
                        _ = await conn.execute(text("ALTER TABLE news_comments ADD COLUMN reviewed_at DATETIME"))

                if "news_topics" not in tables:
                    _ = await conn.execute(
                        text(
                            "CREATE TABLE IF NOT EXISTS news_topics (id INTEGER PRIMARY KEY AUTOINCREMENT, title VARCHAR(200) NOT NULL, description VARCHAR(500), cover_image VARCHAR(255), is_active BOOLEAN DEFAULT 1, sort_order INTEGER DEFAULT 0, auto_category VARCHAR(50), auto_keyword VARCHAR(100), auto_limit INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                        )
                    )
                    _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_topics_sort_order ON news_topics(sort_order)"))
                    _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_topics_is_active ON news_topics(is_active)"))
                else:
                    topics_cols_result = await conn.execute(text("PRAGMA table_info(news_topics)"))
                    topics_cols = {row[1] for row in topics_cols_result.fetchall()}
                    if "auto_category" not in topics_cols:
                        _ = await conn.execute(text("ALTER TABLE news_topics ADD COLUMN auto_category VARCHAR(50)"))
                    if "auto_keyword" not in topics_cols:
                        _ = await conn.execute(text("ALTER TABLE news_topics ADD COLUMN auto_keyword VARCHAR(100)"))
                    if "auto_limit" not in topics_cols:
                        _ = await conn.execute(text("ALTER TABLE news_topics ADD COLUMN auto_limit INTEGER DEFAULT 0"))

                if "news_topic_items" not in tables:
                    _ = await conn.execute(
                        text(
                            "CREATE TABLE IF NOT EXISTS news_topic_items (id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER NOT NULL, news_id INTEGER NOT NULL, position INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, UNIQUE(topic_id, news_id))"
                        )
                    )
                    _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_topic_items_topic ON news_topic_items(topic_id)"))
                    _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_topic_items_news ON news_topic_items(news_id)"))
                    _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_topic_items_position ON news_topic_items(position)"))

                if "notifications" in tables:
                    notifications_cols_result = await conn.execute(text("PRAGMA table_info(notifications)"))
                    notifications_cols = {row[1] for row in notifications_cols_result.fetchall()}
                    if "dedupe_key" not in notifications_cols:
                        _ = await conn.execute(text("ALTER TABLE notifications ADD COLUMN dedupe_key VARCHAR(200)"))
                    if "related_user_id" not in notifications_cols:
                        _ = await conn.execute(text("ALTER TABLE notifications ADD COLUMN related_user_id INTEGER"))
                    if "related_post_id" not in notifications_cols:
                        _ = await conn.execute(text("ALTER TABLE notifications ADD COLUMN related_post_id INTEGER"))
                    if "related_comment_id" not in notifications_cols:
                        _ = await conn.execute(text("ALTER TABLE notifications ADD COLUMN related_comment_id INTEGER"))
                    try:
                        _ = await conn.execute(
                            text(
                                "DELETE FROM notifications WHERE dedupe_key IS NOT NULL AND id NOT IN (SELECT MIN(id) FROM notifications WHERE dedupe_key IS NOT NULL GROUP BY user_id, type, dedupe_key)"
                            )
                        )
                    except Exception:
                        logger.exception("notifications去重失败")
                    try:
                        _ = await conn.execute(
                            text(
                                "CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_user_type_dedupe_key ON notifications (user_id, type, dedupe_key)"
                            )
                        )
                    except Exception:
                        logger.exception("创建notifications唯一索引失败（可能存在历史重复数据）")

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
                _ = await conn.execute(text("ALTER TABLE news ADD COLUMN IF NOT EXISTS scheduled_publish_at TIMESTAMPTZ"))
                _ = await conn.execute(text("ALTER TABLE news ADD COLUMN IF NOT EXISTS scheduled_unpublish_at TIMESTAMPTZ"))
                _ = await conn.execute(text("ALTER TABLE news ADD COLUMN IF NOT EXISTS source_url VARCHAR(500)"))
                _ = await conn.execute(text("ALTER TABLE news ADD COLUMN IF NOT EXISTS dedupe_hash VARCHAR(40)"))
                try:
                    _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_dedupe_hash ON news(dedupe_hash)"))
                except Exception:
                    logger.exception("创建news dedupe_hash索引失败")
                _ = await conn.execute(text("ALTER TABLE news ADD COLUMN IF NOT EXISTS source_site VARCHAR(100)"))
                _ = await conn.execute(text("ALTER TABLE news ADD COLUMN IF NOT EXISTS review_status VARCHAR(20) DEFAULT 'approved'"))
                _ = await conn.execute(text("ALTER TABLE news ADD COLUMN IF NOT EXISTS review_reason VARCHAR(200)"))
                _ = await conn.execute(text("ALTER TABLE news ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ"))

                _ = await conn.execute(text("ALTER TABLE news_ai_annotations ADD COLUMN IF NOT EXISTS highlights TEXT"))
                _ = await conn.execute(text("ALTER TABLE news_ai_annotations ADD COLUMN IF NOT EXISTS keywords TEXT"))
                _ = await conn.execute(
                    text("ALTER TABLE news_ai_annotations ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0")
                )
                _ = await conn.execute(text("ALTER TABLE news_ai_annotations ADD COLUMN IF NOT EXISTS last_error TEXT"))
                _ = await conn.execute(text("ALTER TABLE news_ai_annotations ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMPTZ"))

                _ = await conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS news_comments (id SERIAL PRIMARY KEY, news_id INTEGER NOT NULL, user_id INTEGER NOT NULL, content TEXT NOT NULL, is_deleted BOOLEAN DEFAULT FALSE, review_status VARCHAR(20) DEFAULT 'approved', review_reason VARCHAR(200), reviewed_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())"
                    )
                )
                _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_comments_news_id ON news_comments(news_id)"))
                _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_comments_user_id ON news_comments(user_id)"))
                _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_comments_created_at ON news_comments(created_at)"))

                _ = await conn.execute(text("ALTER TABLE news_comments ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE"))
                _ = await conn.execute(text("ALTER TABLE news_comments ADD COLUMN IF NOT EXISTS review_status VARCHAR(20)"))
                _ = await conn.execute(text("ALTER TABLE news_comments ADD COLUMN IF NOT EXISTS review_reason VARCHAR(200)"))
                _ = await conn.execute(text("ALTER TABLE news_comments ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ"))

                _ = await conn.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(200)"))
                _ = await conn.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS related_user_id INTEGER"))
                _ = await conn.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS related_post_id INTEGER"))
                _ = await conn.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS related_comment_id INTEGER"))
                try:
                    _ = await conn.execute(
                        text(
                            "DELETE FROM notifications WHERE dedupe_key IS NOT NULL AND id NOT IN (SELECT MIN(id) FROM notifications WHERE dedupe_key IS NOT NULL GROUP BY user_id, type, dedupe_key)"
                        )
                    )
                except Exception:
                    logger.exception("notifications去重失败")
                try:
                    _ = await conn.execute(
                        text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_user_type_dedupe_key ON notifications (user_id, type, dedupe_key)"
                        )
                    )
                except Exception:
                    logger.exception("创建notifications唯一索引失败（可能存在历史重复数据）")

                _ = await conn.execute(text("ALTER TABLE news_topics ADD COLUMN IF NOT EXISTS auto_category VARCHAR(50)"))
                _ = await conn.execute(text("ALTER TABLE news_topics ADD COLUMN IF NOT EXISTS auto_keyword VARCHAR(100)"))
                _ = await conn.execute(text("ALTER TABLE news_topics ADD COLUMN IF NOT EXISTS auto_limit INTEGER DEFAULT 0"))

                _ = await conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS news_topic_items (id SERIAL PRIMARY KEY, topic_id INTEGER NOT NULL, news_id INTEGER NOT NULL, position INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW(), CONSTRAINT uq_news_topic_items_topic_news UNIQUE(topic_id, news_id))"
                    )
                )
                _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_topic_items_topic ON news_topic_items(topic_id)"))
                _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_topic_items_news ON news_topic_items(news_id)"))
                _ = await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_news_topic_items_position ON news_topic_items(position)"))

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
