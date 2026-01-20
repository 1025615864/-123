import asyncio
import sys
import types

import pytest
from unittest.mock import AsyncMock

import app.database as database
from app import main as main_mod


def test_normalize_base_url() -> None:
    assert main_mod._normalize_base_url("") == ""
    assert main_mod._normalize_base_url(" http://example.com/ ") == "http://example.com"
    assert main_mod._normalize_base_url("http://example.com") == "http://example.com"


@pytest.mark.asyncio
async def test_robots_txt_uses_frontend_base_url(client, monkeypatch) -> None:
    monkeypatch.setattr(main_mod.settings, "frontend_base_url", "http://example.com/", raising=False)
    res = await client.get("/robots.txt")
    assert res.status_code == 200
    assert "Sitemap: http://example.com/sitemap.xml" in res.text


@pytest.mark.asyncio
async def test_sitemap_xml_includes_dynamic_news_urls(client, monkeypatch) -> None:
    monkeypatch.setattr(main_mod.settings, "frontend_base_url", "http://example.com/", raising=False)

    class DummyResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class DummySession:
        def __init__(self):
            self.calls = 0

        async def execute(self, _query):
            self.calls += 1
            if self.calls == 1:
                return DummyResult([(1,), (None,), ("2",), ("bad",), (1,)])
            return DummyResult([(10,), (None,), ("11",), ("bad",), (10,)])

    class DummySessionCtx:
        def __init__(self):
            self._session = DummySession()

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(main_mod, "AsyncSessionLocal", lambda: DummySessionCtx(), raising=True)

    res = await client.get("/sitemap.xml")
    assert res.status_code == 200
    text = res.text
    assert "<loc>http://example.com/news/topics/1</loc>" in text
    assert "<loc>http://example.com/news/topics/2</loc>" in text
    assert "<loc>http://example.com/news/10</loc>" in text
    assert "<loc>http://example.com/news/11</loc>" in text


@pytest.mark.asyncio
async def test_metrics_requires_auth_token_when_configured(client, monkeypatch) -> None:
    monkeypatch.setenv("METRICS_AUTH_TOKEN", "t")
    res = await client.get("/metrics")
    assert res.status_code == 401
    assert "unauthorized" in res.text


@pytest.mark.asyncio
async def test_metrics_authorized_renders_ai_metrics_lines(client, monkeypatch) -> None:
    monkeypatch.setenv("METRICS_AUTH_TOKEN", "t")

    mod = types.ModuleType("app.services.ai_metrics")

    class DummyAiMetrics:
        def snapshot(self):
            return {
                "started_at": 1.23,
                "chat_requests_total": 5,
                "chat_stream_requests_total": 2.0,
                "errors_total": True,
                "error_code_counts": {"E1": 2, "": 9, "E2": "3", "Ebad": "x", "Ebool": True},
                "endpoint_error_counts": {"/api/a": 1, " ": 2, "/api/b": "4", "/api/bad": "x"},
            }

    setattr(mod, "ai_metrics", DummyAiMetrics())
    monkeypatch.setitem(sys.modules, "app.services.ai_metrics", mod)

    def fake_render_prometheus(*, extra_lines=None):
        return "\n".join(extra_lines or []) + "\n"

    monkeypatch.setattr(main_mod.prometheus_metrics, "render_prometheus", fake_render_prometheus, raising=True)

    res = await client.get("/metrics", headers={"Authorization": "Bearer t"})
    assert res.status_code == 200
    assert "baixing_ai_started_at_seconds" in res.text
    assert "baixing_ai_chat_requests_total" in res.text
    assert "baixing_ai_chat_stream_requests_total" in res.text
    assert "baixing_ai_errors_total" in res.text
    assert "baixing_ai_error_code_total" in res.text
    assert "baixing_ai_endpoint_error_total" in res.text


@pytest.mark.asyncio
async def test_health_detailed_database_ok_and_memory_ok(client, monkeypatch) -> None:
    monkeypatch.setattr(main_mod.settings, "openai_api_key", "k", raising=False)

    class FakeConn:
        async def execute(self, _query):
            return None

    class FakeConnCtx:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def connect(self):
            return FakeConnCtx()

    monkeypatch.setattr(database, "engine", FakeEngine(), raising=False)

    psutil_mod = types.ModuleType("psutil")

    class _Mem:
        rss = 1024 * 1024

    class _Proc:
        def memory_info(self):
            return _Mem()

    setattr(psutil_mod, "Process", lambda: _Proc())
    monkeypatch.setitem(sys.modules, "psutil", psutil_mod)

    res = await client.get("/health/detailed")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "healthy"
    assert payload["checks"]["database"]["status"] == "ok"
    assert payload["checks"]["ai_service"]["status"] == "configured"
    assert payload["checks"]["memory"]["status"] == "ok"


@pytest.mark.asyncio
async def test_health_detailed_database_error_sets_degraded(client, monkeypatch) -> None:
    class BadEngine:
        def connect(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(database, "engine", BadEngine(), raising=False)

    res = await client.get("/health/detailed")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"]["status"] == "error"


@pytest.mark.asyncio
async def test_lifespan_requires_redis_when_debug_false(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "init_db", AsyncMock(return_value=None), raising=True)
    monkeypatch.setattr(main_mod.settings, "debug", False, raising=False)
    monkeypatch.setattr(main_mod.settings, "redis_url", "redis://localhost:6379/0", raising=False)

    connect = AsyncMock(return_value=False)
    monkeypatch.setattr(main_mod.cache_service, "connect", connect, raising=True)

    with pytest.raises(RuntimeError):
        async with main_mod.lifespan(main_mod.app):
            pass


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_background_tasks(monkeypatch) -> None:
    monkeypatch.setattr(main_mod, "init_db", AsyncMock(return_value=None), raising=True)
    monkeypatch.setattr(main_mod.settings, "debug", True, raising=False)
    monkeypatch.setattr(main_mod.settings, "redis_url", "", raising=False)

    disconnect = AsyncMock(return_value=None)
    monkeypatch.setattr(main_mod.cache_service, "disconnect", disconnect, raising=True)

    async def fake_run(self, *args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(main_mod.PeriodicLockedRunner, "run", fake_run, raising=True)

    async with main_mod.lifespan(main_mod.app):
        pass

    assert disconnect.await_count == 1
