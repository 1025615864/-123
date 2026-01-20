import pytest

import app.database as db


def test_env_truthy(monkeypatch) -> None:
    monkeypatch.delenv("X", raising=False)
    assert db._env_truthy("X") is False
    monkeypatch.setenv("X", "1")
    assert db._env_truthy("X") is True
    monkeypatch.setenv("X", "true")
    assert db._env_truthy("X") is True
    monkeypatch.setenv("X", "0")
    assert db._env_truthy("X") is False


def test_assert_alembic_head_raises_on_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(db, "_get_alembic_expected_heads", lambda: ("a",), raising=True)
    monkeypatch.setattr(db, "_get_alembic_current_heads", lambda _conn: ("b",), raising=True)

    with pytest.raises(RuntimeError) as e:
        db._assert_alembic_head(object())
    assert "current" in str(e.value)
    assert "expected" in str(e.value)


@pytest.mark.asyncio
async def test_init_db_no_runtime_ddl_checks_alembic_head(monkeypatch) -> None:
    monkeypatch.setattr(db.settings, "debug", False, raising=False)
    monkeypatch.delenv("DB_ALLOW_RUNTIME_DDL", raising=False)

    called = {"exec": 0, "run_sync": 0}

    class Conn:
        async def execute(self, _q):
            called["exec"] += 1
            return None

        async def run_sync(self, fn):
            called["run_sync"] += 1
            fn(object())

    class ConnCtx:
        async def __aenter__(self):
            return Conn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class Engine:
        def connect(self):
            return ConnCtx()

    monkeypatch.setattr(db, "engine", Engine(), raising=True)
    monkeypatch.setattr(db, "_assert_alembic_head", lambda _c: None, raising=True)

    await db.init_db()
    assert called["exec"] == 1
    assert called["run_sync"] == 1
