"""数据库配置"""
import importlib
import logging
import os
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from sqlalchemy.engine import Connection
from .config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

if settings.database_url.startswith("sqlite"):
    parts = settings.database_url.split("///", 1)
    if len(parts) == 2:
        db_path = parts[1]
        if db_path.startswith("./"):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

sql_echo_raw = os.getenv("SQL_ECHO", "").strip().lower()
engine_echo = sql_echo_raw in {"1", "true", "yes", "on"}

sql_level = logging.INFO if engine_echo else logging.WARNING
logging.getLogger("sqlalchemy").setLevel(sql_level)
logging.getLogger("sqlalchemy.engine").setLevel(sql_level)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(sql_level)
logging.getLogger("sqlalchemy.pool").setLevel(sql_level)

engine = create_async_engine(
    settings.database_url,
    echo=engine_echo,
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


def _env_truthy(name: str) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _get_backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _get_alembic_script_directory() -> ScriptDirectory:
    backend_dir = _get_backend_dir()
    ini_path = backend_dir / "alembic.ini"
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    return ScriptDirectory.from_config(config)


def _get_alembic_expected_heads() -> tuple[str, ...]:
    script = _get_alembic_script_directory()
    return tuple(script.get_heads())


def _get_alembic_current_heads(conn: Connection) -> tuple[str, ...]:
    ctx = MigrationContext.configure(conn)
    return tuple(ctx.get_current_heads())


def _assert_alembic_head(conn: Connection) -> None:
    expected = _get_alembic_expected_heads()
    current = _get_alembic_current_heads(conn)
    if set(current) != set(expected):
        raise RuntimeError(
            "Database schema is not at Alembic head. "
            f"current={list(current)} expected={list(expected)}. "
            "Run `py scripts/alembic_cmd.py upgrade head` (or `alembic upgrade head`). "
            "If the database already has the full schema and you only want to mark it, run `py scripts/alembic_cmd.py stamp head`. "
            "You may temporarily set DB_ALLOW_RUNTIME_DDL=1 to bypass this check."
        )


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
        "app.models.user_quota",
        "app.models.user_consent",
        "app.models.consultation",
        "app.models.consultation_review",
        "app.models.forum",
        "app.models.news",
        "app.models.news_ai",
        "app.models.news_workbench",
        "app.models.lawfirm",
        "app.models.settlement",
        "app.models.knowledge",
        "app.models.document",
        "app.models.document_template",
        "app.models.notification",
        "app.models.payment",
        "app.models.system",
        "app.models.calendar",
        "app.models.feedback",
    ):
        _ = importlib.import_module(module_name)

    allow_runtime_ddl = bool(settings.debug) or _env_truthy("DB_ALLOW_RUNTIME_DDL")
    if not allow_runtime_ddl:
        async with engine.connect() as conn:
            _ = await conn.execute(text("SELECT 1"))
            await conn.run_sync(_assert_alembic_head)
        return

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

                if "legal_knowledge" in tables:
                    lk_cols_result = await conn.execute(text("PRAGMA table_info(legal_knowledge)"))
                    lk_cols = {row[1] for row in lk_cols_result.fetchall()}
                    if "source_url" not in lk_cols:
                        _ = await conn.execute(text("ALTER TABLE legal_knowledge ADD COLUMN source_url VARCHAR(500)"))
                    if "source_version" not in lk_cols:
                        _ = await conn.execute(text("ALTER TABLE legal_knowledge ADD COLUMN source_version VARCHAR(50)"))
                    if "source_hash" not in lk_cols:
                        _ = await conn.execute(text("ALTER TABLE legal_knowledge ADD COLUMN source_hash VARCHAR(64)"))
                    if "ingest_batch_id" not in lk_cols:
                        _ = await conn.execute(text("ALTER TABLE legal_knowledge ADD COLUMN ingest_batch_id VARCHAR(36)"))
                    try:
                        _ = await conn.execute(
                            text("CREATE INDEX IF NOT EXISTS ix_legal_knowledge_source_hash ON legal_knowledge(source_hash)")
                        )
                        _ = await conn.execute(
                            text("CREATE INDEX IF NOT EXISTS ix_legal_knowledge_ingest_batch_id ON legal_knowledge(ingest_batch_id)")
                        )
                    except Exception:
                        logger.exception("创建 legal_knowledge 索引失败")

                if "generated_documents" in tables:
                    docs_cols_result = await conn.execute(text("PRAGMA table_info(generated_documents)"))
                    docs_cols = {row[1] for row in docs_cols_result.fetchall()}
                    if "template_key" not in docs_cols:
                        _ = await conn.execute(
                            text("ALTER TABLE generated_documents ADD COLUMN template_key VARCHAR(50)")
                        )
                    if "template_version" not in docs_cols:
                        _ = await conn.execute(
                            text("ALTER TABLE generated_documents ADD COLUMN template_version INTEGER")
                        )
                    try:
                        _ = await conn.execute(
                            text(
                                "CREATE INDEX IF NOT EXISTS ix_generated_documents_template_key ON generated_documents(template_key)"
                            )
                        )
                    except Exception:
                        logger.exception("创建generated_documents模板索引失败")

                if "payment_callback_events" not in tables:
                    _ = await conn.execute(
                        text(
                            "CREATE TABLE IF NOT EXISTS payment_callback_events (id INTEGER PRIMARY KEY AUTOINCREMENT, provider VARCHAR(20) NOT NULL, order_no VARCHAR(64), trade_no VARCHAR(100), amount FLOAT, amount_cents INTEGER, verified BOOLEAN DEFAULT 0, error_message VARCHAR(200), raw_payload TEXT, raw_payload_hash VARCHAR(64), source_ip VARCHAR(45), user_agent VARCHAR(512), created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                        )
                    )
                else:
                    cb_cols_result = await conn.execute(text("PRAGMA table_info(payment_callback_events)"))
                    cb_cols = {row[1] for row in cb_cols_result.fetchall()}
                    if "raw_payload_hash" not in cb_cols:
                        _ = await conn.execute(
                            text("ALTER TABLE payment_callback_events ADD COLUMN raw_payload_hash VARCHAR(64)")
                        )
                    if "source_ip" not in cb_cols:
                        _ = await conn.execute(
                            text("ALTER TABLE payment_callback_events ADD COLUMN source_ip VARCHAR(45)")
                        )
                    if "user_agent" not in cb_cols:
                        _ = await conn.execute(
                            text("ALTER TABLE payment_callback_events ADD COLUMN user_agent VARCHAR(512)")
                        )
                try:
                    _ = await conn.execute(
                        text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_cb_provider_trade_no ON payment_callback_events(provider, trade_no)"
                        )
                    )
                    _ = await conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_payment_callback_events_provider ON payment_callback_events(provider)"
                        )
                    )
                    _ = await conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_payment_callback_events_order_no ON payment_callback_events(order_no)"
                        )
                    )
                    _ = await conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_payment_callback_events_trade_no ON payment_callback_events(trade_no)"
                        )
                    )
                except Exception:
                    logger.exception("创建 payment_callback_events 索引失败")

                if "users" in tables:
                    users_cols_result = await conn.execute(text("PRAGMA table_info(users)"))
                    users_cols = {row[1] for row in users_cols_result.fetchall()}
                    if "vip_expires_at" not in users_cols:
                        _ = await conn.execute(text("ALTER TABLE users ADD COLUMN vip_expires_at DATETIME"))
                    if "email_verified" not in users_cols:
                        _ = await conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0"))
                    if "email_verified_at" not in users_cols:
                        _ = await conn.execute(text("ALTER TABLE users ADD COLUMN email_verified_at DATETIME"))
                    if "phone_verified" not in users_cols:
                        _ = await conn.execute(text("ALTER TABLE users ADD COLUMN phone_verified BOOLEAN DEFAULT 0"))
                    if "phone_verified_at" not in users_cols:
                        _ = await conn.execute(text("ALTER TABLE users ADD COLUMN phone_verified_at DATETIME"))

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

                _ = await conn.execute(
                    text("ALTER TABLE generated_documents ADD COLUMN IF NOT EXISTS template_key VARCHAR(50)")
                )
                _ = await conn.execute(
                    text("ALTER TABLE generated_documents ADD COLUMN IF NOT EXISTS template_version INTEGER")
                )
                try:
                    _ = await conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_generated_documents_template_key ON generated_documents(template_key)"
                        )
                    )
                except Exception:
                    logger.exception("创建generated_documents模板索引失败")

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

    try:
        from sqlalchemy import func, select

        from .models.document_template import DocumentTemplate, DocumentTemplateVersion
        from .services.document_templates_builtin import BUILTIN_DOCUMENT_TEMPLATES

        async with AsyncSessionLocal() as session:
            for key, meta in BUILTIN_DOCUMENT_TEMPLATES.items():
                k = str(key or "").strip()
                if not k:
                    continue

                tpl_res = await session.execute(
                    select(DocumentTemplate).where(DocumentTemplate.key == k)
                )
                tpl = tpl_res.scalar_one_or_none()
                if tpl is None:
                    tpl = DocumentTemplate(
                        key=k,
                        title=str(meta.get("title") or k).strip() or k,
                        description=str(meta.get("description") or "").strip() or None,
                        is_active=True,
                    )
                    session.add(tpl)
                    await session.flush()

                pub_res = await session.execute(
                    select(DocumentTemplateVersion)
                    .where(
                        DocumentTemplateVersion.template_id == int(tpl.id),
                        DocumentTemplateVersion.is_published.is_(True),
                    )
                    .order_by(DocumentTemplateVersion.version.desc())
                    .limit(1)
                )
                published = pub_res.scalar_one_or_none()
                if published is not None:
                    continue

                max_res = await session.execute(
                    select(func.max(DocumentTemplateVersion.version)).where(
                        DocumentTemplateVersion.template_id == int(tpl.id)
                    )
                )
                max_version = max_res.scalar_one_or_none()

                if max_version is None:
                    v = DocumentTemplateVersion(
                        template_id=int(tpl.id),
                        version=1,
                        content=str(meta.get("template") or "").strip(),
                        is_published=True,
                    )
                    if v.content:
                        session.add(v)
                    continue

                versions_res = await session.execute(
                    select(DocumentTemplateVersion).where(
                        DocumentTemplateVersion.template_id == int(tpl.id)
                    )
                )
                versions = versions_res.scalars().all()
                target: DocumentTemplateVersion | None = None
                for ver in versions:
                    ver.is_published = False
                    session.add(ver)
                    if int(ver.version) == int(max_version):
                        target = ver

                if target is not None:
                    target.is_published = True
                    session.add(target)

            await session.commit()
    except Exception:
        logger.exception("文书模板seed失败")
