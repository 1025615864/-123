from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import Response

import app.middleware.metrics_middleware as mod
from app.middleware.metrics_middleware import MetricsMiddleware


def _make_request(path: str = "/x", *, route_path: str | None = None) -> Request:
    route_obj = None
    if route_path is not None:
        class _R:
            path = route_path
        route_obj = _R()

    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.3", "version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [],
        "client": ("test", 12345),
        "server": ("test", 80),
        "root_path": "",
        "state": {},
        "route": route_obj,
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_metrics_records_on_success(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def record_http(**kw):
        calls.append(dict(kw))

    monkeypatch.setattr(mod.prometheus_metrics, "record_http", record_http, raising=True)

    mw = MetricsMiddleware(lambda scope, receive, send: None)

    async def call_next(_request: Request) -> Response:
        return Response("ok", status_code=201)

    req = _make_request("/api/x", route_path="/api/x")
    resp = await mw.dispatch(req, call_next)
    assert resp.status_code == 201
    assert len(calls) == 1
    assert calls[0]["status_code"] == 201


@pytest.mark.asyncio
async def test_metrics_skips_excluded_paths(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def record_http(**kw):
        calls.append(dict(kw))

    monkeypatch.setattr(mod.prometheus_metrics, "record_http", record_http, raising=True)

    mw = MetricsMiddleware(lambda scope, receive, send: None)

    async def call_next(_request: Request) -> Response:
        return Response("ok")

    req = _make_request("/health")
    resp = await mw.dispatch(req, call_next)
    assert resp.status_code == 200
    assert calls == []


@pytest.mark.asyncio
async def test_metrics_records_on_exception(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def record_http(**kw):
        calls.append(dict(kw))

    monkeypatch.setattr(mod.prometheus_metrics, "record_http", record_http, raising=True)

    mw = MetricsMiddleware(lambda scope, receive, send: None)

    async def call_next(_request: Request) -> Response:
        raise RuntimeError("boom")

    req = _make_request("/api/err", route_path="/api/err")
    with pytest.raises(RuntimeError):
        await mw.dispatch(req, call_next)

    assert len(calls) == 1
    assert calls[0]["status_code"] == 500


@pytest.mark.asyncio
async def test_metrics_exception_skips_excluded_path(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def record_http(**kw):
        calls.append(dict(kw))

    monkeypatch.setattr(mod.prometheus_metrics, "record_http", record_http, raising=True)

    mw = MetricsMiddleware(lambda scope, receive, send: None)

    async def call_next(_request: Request) -> Response:
        raise RuntimeError("boom")

    req = _make_request("/metrics")
    with pytest.raises(RuntimeError):
        await mw.dispatch(req, call_next)

    assert calls == []


@pytest.mark.asyncio
async def test_metrics_missing_response_raises(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def record_http(**kw):
        calls.append(dict(kw))

    monkeypatch.setattr(mod.prometheus_metrics, "record_http", record_http, raising=True)

    mw = MetricsMiddleware(lambda scope, receive, send: None)

    async def call_next(_request: Request):
        return None

    req = _make_request("/api/none")
    with pytest.raises(RuntimeError) as e:
        await mw.dispatch(req, call_next)  # type: ignore[arg-type]
    assert "metrics_middleware_missing_response" in str(e.value)
    assert calls == []
