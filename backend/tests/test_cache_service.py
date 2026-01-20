import builtins
import time
from types import SimpleNamespace

import pytest

import app.services.cache_service as cs


@pytest.fixture(autouse=True)
def _reset_cache_state():
    cs._memory_cache.clear()
    cs.cache_service._connected = False
    cs.cache_service._redis = None


def test_redis_property_returns_none_when_not_connected_and_obj_when_connected():
    svc = cs.CacheService()
    assert svc.redis is None

    obj = object()
    svc._redis = obj
    svc._connected = True
    assert svc.redis is obj


@pytest.mark.asyncio
async def test_get_set_delete_memory_and_expiry(monkeypatch):
    now = 1000.0

    def fake_time():
        return now

    monkeypatch.setattr(time, "time", fake_time, raising=True)

    assert cs._memory_cache == {}

    ok = await cs.cache_service.set("k", "v", expire=10)
    assert ok is True

    v = await cs.cache_service.get("k")
    assert v == "v"

    now = 1011.0
    v2 = await cs.cache_service.get("k")
    assert v2 is None
    assert "k" not in cs._memory_cache

    ok2 = await cs.cache_service.set("k2", "v2", expire=10)
    assert ok2 is True

    ok3 = await cs.cache_service.delete("k2")
    assert ok3 is True
    assert "k2" not in cs._memory_cache


@pytest.mark.asyncio
async def test_get_set_delete_falls_back_when_redis_errors(monkeypatch):
    now = 1500.0

    def fake_time():
        return now

    monkeypatch.setattr(time, "time", fake_time, raising=True)

    class DummyRedis:
        async def get(self, _key):
            raise RuntimeError("boom")

        async def setex(self, _key, _expire, _value):
            raise RuntimeError("boom")

        async def delete(self, _key):
            raise RuntimeError("boom")

    cs.cache_service._connected = True
    cs.cache_service._redis = DummyRedis()

    assert await cs.cache_service.set("k", "v", expire=10) is True
    assert await cs.cache_service.get("k") == "v"
    assert await cs.cache_service.delete("k") is True
    assert await cs.cache_service.get("k") is None


@pytest.mark.asyncio
async def test_get_json_and_set_json_and_invalid_json(monkeypatch):
    now = 2000.0

    def fake_time():
        return now

    monkeypatch.setattr(time, "time", fake_time, raising=True)

    ok = await cs.cache_service.set_json("d", {"a": 1}, expire=10)
    assert ok is True
    d = await cs.cache_service.get_json("d")
    assert d == {"a": 1}

    ok2 = await cs.cache_service.set_json("l", [1, 2], expire=10)
    assert ok2 is True
    l = await cs.cache_service.get_json("l")
    assert l == [1, 2]

    cs._memory_cache["bad"] = ("not-json", now + 10)
    assert await cs.cache_service.get_json("bad") is None

    cs._memory_cache["scalar"] = ("1", now + 10)
    assert await cs.cache_service.get_json("scalar") is None


@pytest.mark.asyncio
async def test_clear_pattern_memory():
    await cs.cache_service.set("a:1", "v", expire=10)
    await cs.cache_service.set("a:2", "v", expire=10)
    await cs.cache_service.set("b:1", "v", expire=10)

    n = await cs.cache_service.clear_pattern("a:*")
    assert n == 2
    assert await cs.cache_service.get("a:1") is None
    assert await cs.cache_service.get("a:2") is None
    assert await cs.cache_service.get("b:1") == "v"


@pytest.mark.asyncio
async def test_clear_pattern_redis_exception_branch():
    class DummyRedis:
        async def scan_iter(self, match):
            _ = match
            raise RuntimeError("boom")
            if False:  # pragma: no cover
                yield "x"

        async def delete(self, *_keys):
            return 0

    cs.cache_service._connected = True
    cs.cache_service._redis = DummyRedis()

    n = await cs.cache_service.clear_pattern("a:*")
    assert n == 0


@pytest.mark.asyncio
async def test_locks_memory_paths(monkeypatch):
    now = 3000.0

    def fake_time():
        return now

    monkeypatch.setattr(time, "time", fake_time, raising=True)

    assert await cs.cache_service.acquire_lock("lk", "v", expire=10) is True
    assert await cs.cache_service.acquire_lock("lk", "v", expire=10) is False

    now = 3011.0
    assert await cs.cache_service.acquire_lock("lk", "v", expire=10) is True

    assert await cs.cache_service.refresh_lock("missing", "v", expire=10) is False

    cs._memory_cache["rlk"] = ("v", now + 10)
    assert await cs.cache_service.refresh_lock("rlk", "wrong", expire=10) is False
    assert await cs.cache_service.refresh_lock("rlk", "v", expire=10) is True

    assert await cs.cache_service.release_lock("no", "v") is True
    cs._memory_cache["dlk"] = ("v", now + 10)
    assert await cs.cache_service.release_lock("dlk", "wrong") is False
    assert await cs.cache_service.release_lock("dlk", "v") is True


@pytest.mark.asyncio
async def test_locks_redis_exception_branches():
    class DummyRedis:
        async def set(self, *_a, **_k):
            raise RuntimeError("boom")

        async def eval(self, *_a, **_k):
            raise RuntimeError("boom")

    cs.cache_service._connected = True
    cs.cache_service._redis = DummyRedis()

    assert await cs.cache_service.acquire_lock("k", "v", expire=10) is False
    assert await cs.cache_service.refresh_lock("k", "v", expire=10) is False
    assert await cs.cache_service.release_lock("k", "v") is False


@pytest.mark.asyncio
async def test_cached_decorator_hit_and_skip_set_when_none(monkeypatch):
    store = {}

    async def fake_get_json(key):
        return store.get(key)

    async def fake_set_json(key, value, expire=300):
        _ = expire
        store[key] = value
        return True

    monkeypatch.setattr(cs.cache_service, "get_json", fake_get_json, raising=True)
    monkeypatch.setattr(cs.cache_service, "set_json", fake_set_json, raising=True)

    called = {"n": 0}

    @cs.cached("p", expire=10)
    async def f(x):
        called["n"] += 1
        return {"x": x}

    r1 = await f(1)
    r2 = await f(1)

    assert r1 == {"x": 1}
    assert r2 == {"x": 1}
    assert called["n"] == 1

    called2 = {"n": 0}

    @cs.cached("p2", expire=10)
    async def f2(x):
        called2["n"] += 1
        return None

    r3 = await f2(1)
    r4 = await f2(1)
    assert r3 is None
    assert r4 is None
    assert called2["n"] == 2


@pytest.mark.asyncio
async def test_disconnect_calls_close():
    svc = cs.CacheService()

    class DummyRedis:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    r = DummyRedis()
    svc._redis = r
    svc._connected = True

    await svc.disconnect()

    assert r.closed is True
    assert svc.is_connected is False


@pytest.mark.asyncio
async def test_connect_importerror_branch(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "redis.asyncio":
            raise ImportError("no redis")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    svc = cs.CacheService()
    ok = await svc.connect("redis://localhost:6379/0")
    assert ok is False


@pytest.mark.asyncio
async def test_connect_exception_branch(monkeypatch):
    class DummyClient:
        async def ping(self):
            raise RuntimeError("boom")

    dummy_module = SimpleNamespace(from_url=lambda *_a, **_k: DummyClient())

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "redis.asyncio":
            return dummy_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    svc = cs.CacheService()
    ok = await svc.connect("redis://localhost:6379/0")
    assert ok is False
