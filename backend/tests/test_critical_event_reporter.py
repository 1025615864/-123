import asyncio
from collections.abc import Coroutine
from typing import Any, cast

import pytest

from app.services.critical_event_reporter import CriticalEventReporter


class _DummyAsyncClient:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.posts: list[dict[str, object]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, headers=None):
        self.posts.append({"url": url, "json": json, "headers": headers})
        return object()


@pytest.mark.asyncio
async def test_report_disabled_does_not_send(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CRITICAL_EVENTS_ENABLED", raising=False)
    monkeypatch.setenv("CRITICAL_EVENTS_WEBHOOK_URL", "http://example.invalid")

    import app.services.critical_event_reporter as mod

    created: list[_DummyAsyncClient] = []

    def _factory(*a, **k):
        inst = _DummyAsyncClient(*a, **k)
        created.append(inst)
        return inst

    monkeypatch.setattr(mod.httpx, "AsyncClient", _factory)

    reporter = CriticalEventReporter()
    await reporter.report(event="e", severity="error")

    assert created == []


@pytest.mark.asyncio
async def test_report_missing_url_does_not_send(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRITICAL_EVENTS_ENABLED", "1")
    monkeypatch.delenv("CRITICAL_EVENTS_WEBHOOK_URL", raising=False)

    reporter = CriticalEventReporter()
    await reporter.report(event="e", severity="error")


@pytest.mark.asyncio
async def test_report_sends_once_and_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRITICAL_EVENTS_ENABLED", "1")
    monkeypatch.setenv("CRITICAL_EVENTS_WEBHOOK_URL", "http://example.invalid/webhook")
    monkeypatch.setenv("CRITICAL_EVENTS_MIN_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("CRITICAL_EVENTS_WEBHOOK_BEARER", "token")
    monkeypatch.setenv("CRITICAL_EVENTS_WEBHOOK_HEADER_NAME", "X-Test")
    monkeypatch.setenv("CRITICAL_EVENTS_WEBHOOK_HEADER_VALUE", "1")
    monkeypatch.setenv("CRITICAL_EVENTS_TIMEOUT_SECONDS", "bad")

    import app.services.critical_event_reporter as mod

    created: list[_DummyAsyncClient] = []

    def _factory(*a, **k):
        inst = _DummyAsyncClient(*a, **k)
        created.append(inst)
        return inst

    monkeypatch.setattr(mod.httpx, "AsyncClient", _factory)

    reporter = CriticalEventReporter()

    await reporter.report(
        event="pay_failed",
        severity="error",
        request_id="rid",
        title="t",
        message="m",
        data={None: "x", "": "y", "ok": 1},
        dedup_key="k",
    )
    await reporter.report(event="pay_failed", severity="error", title="t", message="m", dedup_key="k")

    assert len(created) == 1
    inst = created[0]
    assert inst.kwargs.get("timeout") == 3.0

    assert len(inst.posts) == 1
    posted = inst.posts[0]

    assert str(posted["url"]).endswith("/webhook")
    headers = posted["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer token"
    assert headers["X-Test"] == "1"

    payload = posted["json"]
    assert isinstance(payload, dict)
    assert payload["event"] == "pay_failed"
    assert payload["request_id"] == "rid"
    data = payload["data"]
    assert isinstance(data, dict)
    assert data.get("ok") == 1
    assert "" not in data


def test_fire_and_forget_invalid_event_is_noop() -> None:
    reporter = CriticalEventReporter()
    reporter.fire_and_forget(event="")
    reporter.fire_and_forget(event=None)


def test_fire_and_forget_schedules_task(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter = CriticalEventReporter()

    tasks: list[Coroutine[Any, Any, Any]] = []

    def _capture_task(coro: Coroutine[Any, Any, Any]) -> object:
        tasks.append(coro)
        return object()

    monkeypatch.setattr(asyncio, "create_task", _capture_task)
    reporter.fire_and_forget(event="e", severity="warning")

    assert len(tasks) == 1
    cast(Any, tasks[0]).close()
