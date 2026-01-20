import fnmatch

import pytest

from app.services import cache_service as cache_module


class _DummyRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.lock_kv: dict[str, str] = {}

    async def get(self, key: str):
        return self.kv.get(key)

    async def setex(self, key: str, _expire: int, value: str):
        self.kv[key] = str(value)
        return True

    async def delete(self, *keys: str):
        count = 0
        for key in keys:
            if key in self.kv:
                del self.kv[key]
                count += 1
            if key in self.lock_kv:
                del self.lock_kv[key]
                count += 1
        return count

    async def incr(self, key: str) -> int:
        current = int(self.kv.get(key, "0") or 0)
        current += 1
        self.kv[key] = str(current)
        return current

    async def expire(self, _key: str, _ttl: int) -> bool:
        return True

    async def scan_iter(self, match: str):
        for key in list(self.kv.keys()):
            if fnmatch.fnmatch(key, match):
                yield key

    async def set(self, key: str, value: str, ex: int, nx: bool):
        _ = ex
        if not nx:
            self.lock_kv[key] = value
            return True
        if key in self.lock_kv:
            return None
        self.lock_kv[key] = value
        return True

    async def eval(self, _script: str, _num_keys: int, key: str, value: str, expire: int | None = None):
        _ = (_script, _num_keys)
        if expire is None:
            if self.lock_kv.get(key) == value:
                del self.lock_kv[key]
                return 1
            return 0

        if self.lock_kv.get(key) == value:
            _ = expire
            return 1
        return 0


@pytest.mark.asyncio
async def test_cache_service_redis_set_get_delete_clear_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyRedis()
    monkeypatch.setattr(cache_module.cache_service, "_connected", True, raising=False)
    monkeypatch.setattr(cache_module.cache_service, "_redis", dummy, raising=False)
    cache_module._memory_cache.clear()

    ok = await cache_module.cache_service.set("k1", "v1", expire=10)
    assert ok is True
    assert await cache_module.cache_service.get("k1") == "v1"

    ok = await cache_module.cache_service.set("user:1", "u1", expire=10)
    assert ok is True
    ok = await cache_module.cache_service.set("user:2", "u2", expire=10)
    assert ok is True

    deleted = await cache_module.cache_service.delete("user:1")
    assert deleted is True
    assert await cache_module.cache_service.get("user:1") is None

    cleared = await cache_module.cache_service.clear_pattern("user:*")
    assert cleared == 1
    assert await cache_module.cache_service.get("user:2") is None


@pytest.mark.asyncio
async def test_cache_service_redis_lock_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyRedis()
    monkeypatch.setattr(cache_module.cache_service, "_connected", True, raising=False)
    monkeypatch.setattr(cache_module.cache_service, "_redis", dummy, raising=False)

    assert await cache_module.cache_service.acquire_lock("lock", "v", expire=60) is True
    assert await cache_module.cache_service.acquire_lock("lock", "v", expire=60) is False

    assert await cache_module.cache_service.refresh_lock("lock", "bad", expire=60) is False
    assert await cache_module.cache_service.refresh_lock("lock", "v", expire=60) is True

    assert await cache_module.cache_service.release_lock("lock", "bad") is False
    assert await cache_module.cache_service.release_lock("lock", "v") is True
