import pytest
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_init_db_requires_alembic_head_when_debug_false(monkeypatch):
    from app import database as db

    orig_engine = db.engine
    orig_debug = db.settings.debug
    new_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    try:
        db.settings.debug = False
        monkeypatch.delenv("DB_ALLOW_RUNTIME_DDL", raising=False)
        db.engine = new_engine

        with pytest.raises(RuntimeError) as exc:
            await db.init_db()

        assert "upgrade head" in str(exc.value)
    finally:
        await new_engine.dispose()
        db.engine = orig_engine
        db.settings.debug = orig_debug


@pytest.mark.asyncio
async def test_init_db_allows_runtime_ddl_when_env_enabled(monkeypatch):
    from app import database as db

    orig_engine = db.engine
    orig_debug = db.settings.debug
    new_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    try:
        db.settings.debug = False
        monkeypatch.setenv("DB_ALLOW_RUNTIME_DDL", "1")
        db.engine = new_engine

        await db.init_db()
    finally:
        await new_engine.dispose()
        db.engine = orig_engine
        db.settings.debug = orig_debug
        monkeypatch.delenv("DB_ALLOW_RUNTIME_DDL", raising=False)
