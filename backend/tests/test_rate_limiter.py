import asyncio
import time

import pytest
from starlette.requests import Request

import app.utils.rate_limiter as rl


def _make_request(
    *,
    path: str = "/x",
    client_host: str = "1.1.1.1",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.3", "version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "root_path": "",
        "headers": headers or [],
        "client": (client_host, 12345),
        "server": ("testserver", 80),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def test_get_client_ip_uses_forwarded_for_when_trusted_proxy(monkeypatch):
    req = _make_request(
        client_host="9.9.9.9",
        headers=[(b"x-forwarded-for", b"2.2.2.2, 3.3.3.3")],
    )
    monkeypatch.setattr(rl.settings, "trusted_proxies", ["9.9.9.9"], raising=False)
    assert rl.get_client_ip(req) == "2.2.2.2"


def test_get_client_ip_uses_x_real_ip_when_trusted_proxy(monkeypatch):
    req = _make_request(
        client_host="9.9.9.9",
        headers=[(b"x-real-ip", b"4.4.4.4")],
    )
    monkeypatch.setattr(rl.settings, "trusted_proxies", ["9.9.9.9"], raising=False)
    assert rl.get_client_ip(req) == "4.4.4.4"


def test_rate_limiter_memory_path_allows_then_blocks(monkeypatch):
    limiter = rl.RateLimiter()

    now = 1000.0

    def fake_time():
        return now

    monkeypatch.setattr(time, "time", fake_time, raising=True)

    ok1, remaining1 = limiter._memory_is_allowed("k", 2, 60)
    assert ok1 is True
    assert remaining1 == 1

    ok2, remaining2 = limiter._memory_is_allowed("k", 2, 60)
    assert ok2 is True
    assert remaining2 == 0

    ok3, remaining3 = limiter._memory_is_allowed("k", 2, 60)
    assert ok3 is False
    assert remaining3 == 0


def test_rate_limiter_memory_get_wait_time_empty_list_returns_zero():
    limiter = rl.RateLimiter()
    limiter._requests["k"] = []
    assert limiter._memory_get_wait_time("k", window_seconds=60) == 0


def test_rate_limiter_evicts_oldest_key(monkeypatch):
    limiter = rl.RateLimiter(max_tracked_keys=1)
    limiter._max_tracked_keys = 1

    now = 1000.0

    def fake_time():
        return now

    monkeypatch.setattr(time, "time", fake_time, raising=True)

    ok1, _ = limiter._memory_is_allowed("k1", 100, 60)
    assert ok1 is True

    now = 1001.0
    ok2, _ = limiter._memory_is_allowed("k2", 100, 60)
    assert ok2 is True

    assert "k2" in limiter._requests
    assert "k1" not in limiter._requests


@pytest.mark.asyncio
async def test_rate_limiter_check_redis_allows_and_blocks(monkeypatch):
    class DummyRedis:
        def __init__(self):
            self.counts = {}
            self._ttl = {}

        async def incr(self, key):
            self.counts[key] = int(self.counts.get(key, 0)) + 1
            return self.counts[key]

        async def expire(self, key, window):
            self._ttl[key] = int(window)
            return True

        async def ttl(self, key):
            return int(self._ttl.get(key, 5))

    dummy = DummyRedis()
    monkeypatch.setattr(rl.cache_service, "_connected", True, raising=False)
    monkeypatch.setattr(rl.cache_service, "_redis", dummy, raising=False)

    limiter = rl.RateLimiter()

    ok, remaining, wait = await limiter.check("k", max_requests=2, window_seconds=60)
    assert ok is True
    assert remaining == 1
    assert wait == 0

    ok, remaining, wait = await limiter.check("k", max_requests=2, window_seconds=60)
    assert ok is True
    assert remaining == 0
    assert wait == 0

    ok, remaining, wait = await limiter.check("k", max_requests=2, window_seconds=60)
    assert ok is False
    assert remaining == 0
    assert wait == 60


@pytest.mark.asyncio
async def test_rate_limit_decorator_no_request_pass_through(monkeypatch):
    called = {"n": 0}

    async def handler(*_args, **_kwargs):
        called["n"] += 1
        return "ok"

    async def check_should_not_be_called(*_args, **_kwargs):
        raise AssertionError("check should not be called")

    monkeypatch.setattr(rl.rate_limiter, "check", check_should_not_be_called, raising=True)

    wrapped = rl.rate_limit()(handler)
    assert await wrapped() == "ok"
    assert called["n"] == 1


@pytest.mark.asyncio
async def test_rate_limit_decorator_allowed_records_metrics_and_returns(monkeypatch):
    req = _make_request(path="/p", client_host="1.1.1.1")

    calls = {}

    async def fake_check(key, max_requests, window_seconds):
        calls["key"] = key
        calls["max"] = max_requests
        calls["window"] = window_seconds
        return True, 9, 0

    def fake_record_rate_limit(*, endpoint, allowed):
        calls["endpoint"] = endpoint
        calls["allowed"] = allowed

    monkeypatch.setattr(rl, "rate_limiter", rl.RateLimiter(), raising=True)
    monkeypatch.setattr(rl.rate_limiter, "check", fake_check, raising=True)
    monkeypatch.setattr(rl.prometheus_metrics, "record_rate_limit", fake_record_rate_limit, raising=True)

    async def handler(request: Request):
        _ = request
        return "ok"

    wrapped = rl.rate_limit(max_requests=10, window_seconds=60, by_ip=False)(handler)
    assert await wrapped(request=req) == "ok"
    assert calls["endpoint"] == "/p"
    assert calls["allowed"] is True


@pytest.mark.asyncio
async def test_rate_limit_decorator_finds_request_in_kwargs_values(monkeypatch):
    req = _make_request(path="/p", client_host="1.1.1.1")

    async def fake_check(_key, _max_requests, _window_seconds):
        return True, 1, 0

    def fake_record_rate_limit(*, endpoint, allowed):
        _ = (endpoint, allowed)

    monkeypatch.setattr(rl, "rate_limiter", rl.RateLimiter(), raising=True)
    monkeypatch.setattr(rl.rate_limiter, "check", fake_check, raising=True)
    monkeypatch.setattr(rl.prometheus_metrics, "record_rate_limit", fake_record_rate_limit, raising=True)

    async def handler(foo: Request):
        _ = foo
        return "ok"

    wrapped = rl.rate_limit(max_requests=2, window_seconds=60, by_ip=False)(handler)
    assert await wrapped(foo=req) == "ok"


@pytest.mark.asyncio
async def test_rate_limit_decorator_finds_request_in_args(monkeypatch):
    req = _make_request(path="/p", client_host="1.1.1.1")

    async def fake_check(_key, _max_requests, _window_seconds):
        return True, 1, 0

    def fake_record_rate_limit(*, endpoint, allowed):
        _ = (endpoint, allowed)

    monkeypatch.setattr(rl, "rate_limiter", rl.RateLimiter(), raising=True)
    monkeypatch.setattr(rl.rate_limiter, "check", fake_check, raising=True)
    monkeypatch.setattr(rl.prometheus_metrics, "record_rate_limit", fake_record_rate_limit, raising=True)

    async def handler(request: Request):
        _ = request
        return "ok"

    wrapped = rl.rate_limit(max_requests=2, window_seconds=60, by_ip=False)(handler)
    assert await wrapped(req) == "ok"


@pytest.mark.asyncio
async def test_rate_limit_decorator_denied_raises_http_exception_with_headers(monkeypatch):
    req = _make_request(path="/p", client_host="1.1.1.1")

    async def fake_check(_key, _max_requests, _window_seconds):
        return False, 0, 7

    def fake_record_rate_limit(*, endpoint, allowed):
        _ = (endpoint, allowed)

    monkeypatch.setattr(rl, "rate_limiter", rl.RateLimiter(), raising=True)
    monkeypatch.setattr(rl.rate_limiter, "check", fake_check, raising=True)
    monkeypatch.setattr(rl.prometheus_metrics, "record_rate_limit", fake_record_rate_limit, raising=True)

    async def handler(request: Request):
        _ = request
        return "ok"

    wrapped = rl.rate_limit(max_requests=10, window_seconds=60, by_ip=False)(handler)

    with pytest.raises(rl.HTTPException) as ei:
        await wrapped(request=req)

    err = ei.value
    assert err.status_code == rl.status.HTTP_429_TOO_MANY_REQUESTS
    assert err.headers is not None
    assert err.headers["X-RateLimit-Limit"] == "10"
    assert err.headers["X-RateLimit-Remaining"] == "0"
    assert err.headers["Retry-After"] == "7"


@pytest.mark.asyncio
async def test_rate_limit_decorator_by_user_adds_user_id(monkeypatch):
    req = _make_request(path="/p", client_host="1.1.1.1")
    req.state.user_id = 123

    async def fake_check(key, _max_requests, _window_seconds):
        assert "user:123" in key
        return True, 1, 0

    def fake_record_rate_limit(*, endpoint, allowed):
        _ = (endpoint, allowed)

    monkeypatch.setattr(rl, "rate_limiter", rl.RateLimiter(), raising=True)
    monkeypatch.setattr(rl.rate_limiter, "check", fake_check, raising=True)
    monkeypatch.setattr(rl.prometheus_metrics, "record_rate_limit", fake_record_rate_limit, raising=True)

    async def handler(request: Request):
        _ = request
        return "ok"

    wrapped = rl.rate_limit(max_requests=2, window_seconds=60, by_user=True, by_ip=False)(handler)
    assert await wrapped(request=req) == "ok"


@pytest.mark.asyncio
async def test_rate_limit_decorator_key_func_override(monkeypatch):
    req = _make_request(path="/p", client_host="1.1.1.1")

    async def fake_check(key, _max_requests, _window_seconds):
        assert key == "custom"
        return True, 1, 0

    def fake_record_rate_limit(*, endpoint, allowed):
        _ = (endpoint, allowed)

    monkeypatch.setattr(rl, "rate_limiter", rl.RateLimiter(), raising=True)
    monkeypatch.setattr(rl.rate_limiter, "check", fake_check, raising=True)
    monkeypatch.setattr(rl.prometheus_metrics, "record_rate_limit", fake_record_rate_limit, raising=True)

    async def handler(request: Request):
        _ = request
        return "ok"

    wrapped = rl.rate_limit(
        max_requests=2,
        window_seconds=60,
        key_func=lambda _r: "custom",
        by_user=True,
        by_ip=True,
    )(handler)
    assert await wrapped(request=req) == "ok"


def test_convenience_decorators_call_rate_limit(monkeypatch):
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_rate_limit(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(rl, "rate_limit", fake_rate_limit, raising=True)

    _ = rl.rate_limit_ai()
    _ = rl.rate_limit_auth()
    _ = rl.rate_limit_post()
    _ = rl.rate_limit_comment()
    _ = rl.rate_limit_search()
    _ = rl.rate_limit_upload()

    assert len(calls) == 6
