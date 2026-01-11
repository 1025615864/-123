"""Redis缓存服务"""
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeAlias, TypeVar, cast
from functools import wraps

logger = logging.getLogger(__name__)

JsonDict: TypeAlias = dict[str, Any]
JsonList: TypeAlias = list[Any]
JsonValue: TypeAlias = JsonDict | JsonList

TJson = TypeVar("TJson", bound=JsonValue)
P = ParamSpec("P")

# 内存缓存作为Redis的备选方案
_memory_cache: dict[str, tuple[str, float]] = {}


class CacheService:
    """缓存服务类"""
    
    def __init__(self):
        self._redis: Any | None = None
        self._connected: bool = False
    
    async def connect(self, redis_url: str) -> bool:
        """连接Redis"""
        try:
            import redis.asyncio as redis
            client = cast(Any, redis.from_url(redis_url, decode_responses=True))
            await client.ping()
            self._redis = client
            self._connected = True
            logger.info("Redis connected successfully")
            return True
        except ImportError:
            logger.warning("redis package not installed, using memory cache")
            return False
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using memory cache")
            return False
    
    async def disconnect(self) -> None:
        """断开Redis连接"""
        if self._redis:
            await self._redis.close()
            self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected

    @property
    def redis(self) -> Any | None:
        if self._connected and self._redis:
            return self._redis
        return None
    
    async def get(self, key: str) -> str | None:
        """获取缓存"""
        if self._connected and self._redis:
            try:
                return await self._redis.get(key)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        # 内存缓存备选
        import time
        if key in _memory_cache:
            value, expires_at = _memory_cache[key]
            if time.time() < expires_at:
                return value
            del _memory_cache[key]
        return None
    
    async def set(self, key: str, value: str, expire: int = 300) -> bool:
        """设置缓存"""
        if self._connected and self._redis:
            try:
                await self._redis.setex(key, expire, value)
                return True
            except Exception as e:
                logger.error(f"Redis set error: {e}")
        
        # 内存缓存备选
        import time
        _memory_cache[key] = (value, time.time() + expire)
        return True
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if self._connected and self._redis:
            try:
                await self._redis.delete(key)
                return True
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
        
        if key in _memory_cache:
            del _memory_cache[key]
        return True
    
    async def get_json(self, key: str) -> JsonValue | None:
        """获取JSON缓存"""
        data = await self.get(key)
        if data:
            try:
                raw = json.loads(data)
                if isinstance(raw, dict):
                    return cast(JsonDict, raw)
                if isinstance(raw, list):
                    return cast(JsonList, raw)
                return None
            except json.JSONDecodeError:
                return None
        return None
    
    async def set_json(self, key: str, value: JsonValue, expire: int = 300) -> bool:
        """设置JSON缓存"""
        return await self.set(key, json.dumps(value, ensure_ascii=False), expire)
    
    async def clear_pattern(self, pattern: str) -> int:
        """清除匹配模式的缓存"""
        count = 0
        if self._connected and self._redis:
            try:
                keys = []
                async for key in self._redis.scan_iter(match=pattern):
                    keys.append(key)
                if keys:
                    count = await self._redis.delete(*keys)
            except Exception as e:
                logger.error(f"Redis clear pattern error: {e}")
        else:
            # 内存缓存
            import fnmatch
            keys_to_delete = [k for k in _memory_cache if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_delete:
                del _memory_cache[key]
                count += 1
        return count

    async def acquire_lock(self, key: str, value: str, expire: int = 60) -> bool:
        if self._connected and self._redis:
            try:
                result = await self._redis.set(key, value, ex=int(expire), nx=True)
                return bool(result)
            except Exception as e:
                logger.error(f"Redis acquire_lock error: {e}")
                return False

        import time
        now = time.time()
        existing = _memory_cache.get(key)
        if existing is not None:
            _v, expires_at = existing
            if now < expires_at:
                return False
        _memory_cache[key] = (value, now + float(expire))
        return True

    async def refresh_lock(self, key: str, value: str, expire: int = 60) -> bool:
        if self._connected and self._redis:
            try:
                script = """
                if redis.call('get', KEYS[1]) == ARGV[1] then
                  return redis.call('expire', KEYS[1], ARGV[2])
                else
                  return 0
                end
                """
                result = await self._redis.eval(script, 1, key, value, int(expire))
                return int(result or 0) > 0
            except Exception as e:
                logger.error(f"Redis refresh_lock error: {e}")
                return False

        import time
        existing = _memory_cache.get(key)
        if existing is None:
            return False
        existing_value, _expires_at = existing
        if existing_value != value:
            return False
        _memory_cache[key] = (value, time.time() + float(expire))
        return True

    async def release_lock(self, key: str, value: str) -> bool:
        if self._connected and self._redis:
            try:
                script = """
                if redis.call('get', KEYS[1]) == ARGV[1] then
                  return redis.call('del', KEYS[1])
                else
                  return 0
                end
                """
                result = await self._redis.eval(script, 1, key, value)
                return int(result or 0) > 0
            except Exception as e:
                logger.error(f"Redis release_lock error: {e}")
                return False

        existing = _memory_cache.get(key)
        if existing is None:
            return True
        existing_value, _expires_at = existing
        if existing_value != value:
            return False
        del _memory_cache[key]
        return True


# 单例实例
cache_service = CacheService()


def cached(key_prefix: str, expire: int = 300):
    """缓存装饰器"""
    def decorator(func: Callable[P, Awaitable[TJson | None]]) -> Callable[P, Awaitable[TJson | None]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> TJson | None:
            # 生成缓存键
            cache_key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
            
            # 尝试获取缓存
            cached_data = await cache_service.get_json(cache_key)
            if cached_data is not None:
                return cast(TJson, cached_data)
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 存储缓存
            if result is not None:
                _ = await cache_service.set_json(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator
