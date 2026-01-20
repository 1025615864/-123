from __future__ import annotations

import types
from contextlib import contextmanager

import pytest
from starlette.requests import Request
from starlette.responses import Response

import app.middleware.sentry_context_middleware as mod
from app.middleware.sentry_context_middleware import SentryContextMiddleware


def _make_request(path: str = "/") -> Request:
    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.3", "version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [],
        "client": ("test", 12345),
        "server": ("test", 80),
        "root_path": "",
        "state": {},
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_sentry_context_no_sdk(monkeypatch) -> None:
    monkeypatch.setattr(mod, "sentry_sdk", None, raising=True)

    mw = SentryContextMiddleware(lambda scope, receive, send: None)
    called = {"n": 0}

    async def call_next(_request: Request) -> Response:
        called["n"] += 1
        return Response("ok")

    req = _make_request("/")
    resp = await mw.dispatch(req, call_next)
    assert resp.status_code == 200
    assert called["n"] == 1


@pytest.mark.asyncio
async def test_sentry_context_not_initialized(monkeypatch) -> None:
    dummy = types.SimpleNamespace(is_initialized=lambda: False)
    monkeypatch.setattr(mod, "sentry_sdk", dummy, raising=True)

    mw = SentryContextMiddleware(lambda scope, receive, send: None)
    called = {"n": 0}

    async def call_next(_request: Request) -> Response:
        called["n"] += 1
        return Response("ok")

    req = _make_request("/")
    resp = await mw.dispatch(req, call_next)
    assert resp.status_code == 200
    assert called["n"] == 1


@pytest.mark.asyncio
async def test_sentry_context_sets_tags_and_user(monkeypatch) -> None:
    class DummyScope:
        def __init__(self):
            self.tags: dict[str, str] = {}
            self.user: dict[str, str] | None = None

        def set_tag(self, key: str, value: str) -> None:
            self.tags[str(key)] = str(value)

        def set_user(self, user: dict[str, str]) -> None:
            self.user = user

    scope_obj = DummyScope()

    @contextmanager
    def configure_scope():
        yield scope_obj

    dummy = types.SimpleNamespace(is_initialized=lambda: True, configure_scope=configure_scope)
    monkeypatch.setattr(mod, "sentry_sdk", dummy, raising=True)

    mw = SentryContextMiddleware(lambda scope, receive, send: None)

    async def call_next(_request: Request) -> Response:
        return Response("ok")

    req = _make_request("/")
    req.state.request_id = "rid"
    req.state.user_id = 123

    resp = await mw.dispatch(req, call_next)
    assert resp.status_code == 200
    assert scope_obj.tags.get("request_id") == "rid"
    assert scope_obj.tags.get("user_id") == "123"
    assert scope_obj.user == {"id": "123"}
