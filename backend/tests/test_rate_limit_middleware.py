import inspect
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

import app.middleware.rate_limit as rl
from app.middleware.rate_limit import APIKeyRateLimiter, RateLimitMiddleware
from app.services.cache_service import cache_service


def _make_transport(app: FastAPI) -> ASGITransport:
    transport_kwargs: dict[str, Any] = {"app": app}
    if "lifespan" in inspect.signature(ASGITransport.__init__).parameters:
        transport_kwargs["lifespan"] = "off"
    return ASGITransport(**transport_kwargs)


@pytest.mark.asyncio
async def test_rate_limit_middleware_excluded_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_service, "_connected", False, raising=False)
    monkeypatch.setattr(cache_service, "_redis", None, raising=False)

    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=2,
        requests_per_second=1,
        excluded_paths=["/health"],
    )

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/ping")
        assert r1.status_code == 200

        r2 = await client.get("/ping")
        assert r2.status_code == 429

        for _ in range(5):
            r3 = await client.get("/health")
            assert r3.status_code == 200


def test_rate_limit_middleware_evict_if_needed_removes_oldest_ip() -> None:
    middleware = RateLimitMiddleware(FastAPI(), excluded_paths=[], max_tracked_ips=100)
    for i in range(100):
        ip = f"ip{i}"
        middleware.request_records[ip] = []
        middleware._ip_last_seen[ip] = float(i)

    middleware._evict_if_needed()

    assert len(middleware.request_records) == 99
    assert "ip0" not in middleware.request_records
    assert "ip0" not in middleware._ip_last_seen


@pytest.mark.asyncio
async def test_rate_limit_middleware_check_rate_limit_redis_falls_back_when_redis_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_service, "_connected", False, raising=False)
    monkeypatch.setattr(cache_service, "_redis", None, raising=False)

    middleware = RateLimitMiddleware(FastAPI(), excluded_paths=[])
    allowed, msg, remaining = await middleware._check_rate_limit_redis("1.2.3.4")
    assert allowed is True
    assert msg == ""
    assert isinstance(remaining, int)


def test_api_key_rate_limiter_allows_then_blocks_and_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl.time, "time", lambda: 1000.0)
    limiter = APIKeyRateLimiter(requests_per_minute=2)

    assert limiter.check("k") is True
    assert limiter.check("k") is True
    assert limiter.check("k") is False

    monkeypatch.setattr(rl.time, "time", lambda: 1061.0)
    assert limiter.check("k") is True


def test_rate_limit_middleware_blocks_by_minute() -> None:
    middleware = RateLimitMiddleware(
        FastAPI(),
        requests_per_minute=1,
        requests_per_second=100,
        excluded_paths=[],
    )

    allowed, _msg, remaining = middleware._check_rate_limit_memory("1.2.3.4")
    assert allowed is True
    assert remaining == 0

    allowed2, msg2, remaining2 = middleware._check_rate_limit_memory("1.2.3.4")
    assert allowed2 is False
    assert msg2
    assert remaining2 == 0


def test_rate_limit_middleware_trusted_proxy_uses_forwarded_for() -> None:
    app = FastAPI()
    middleware = RateLimitMiddleware(app, trusted_proxies=["1.1.1.1"])
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"9.9.9.9, 8.8.8.8")],
        "client": ("1.1.1.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)
    assert middleware._get_client_ip(request) == "9.9.9.9"


def test_rate_limit_middleware_trusted_proxy_uses_real_ip() -> None:
    app = FastAPI()
    middleware = RateLimitMiddleware(app, trusted_proxies=["1.1.1.1"])
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"x-real-ip", b"7.7.7.7")],
        "client": ("1.1.1.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)
    assert middleware._get_client_ip(request) == "7.7.7.7"


class _DummyRedis:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counts[key] = int(self._counts.get(key, 0)) + 1
        return int(self._counts[key])

    async def expire(self, _key: str, _ttl: int) -> bool:
        return True


@pytest.mark.asyncio
async def test_rate_limit_middleware_redis_blocks_per_second(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyRedis()
    monkeypatch.setattr(cache_service, "_connected", True, raising=False)
    monkeypatch.setattr(cache_service, "_redis", dummy, raising=False)

    monkeypatch.setattr(RateLimitMiddleware, "_get_client_ip", lambda *_args, **_kwargs: "1.2.3.4")

    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=100,
        requests_per_second=1,
        excluded_paths=["/health"],
    )

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/ping")
        assert r1.status_code == 200

        r2 = await client.get("/ping")
        assert r2.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_middleware_redis_blocks_per_minute(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyRedis()
    monkeypatch.setattr(cache_service, "_connected", True, raising=False)
    monkeypatch.setattr(cache_service, "_redis", dummy, raising=False)

    monkeypatch.setattr(RateLimitMiddleware, "_get_client_ip", lambda *_args, **_kwargs: "1.2.3.4")

    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=1,
        requests_per_second=100,
        excluded_paths=["/health"],
    )

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/ping")
        assert r1.status_code == 200

        r2 = await client.get("/ping")
        assert r2.status_code == 429
