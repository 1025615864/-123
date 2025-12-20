"""Redis缓存服务"""
import json
import logging
from typing import TypeVar, Callable
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 内存缓存作为Redis的备选方案
_memory_cache: dict[str, tuple[str, float]] = {}


class CacheService:
    """缓存服务类"""
    
    def __init__(self):
        self._redis = None
        self._connected = False
    
    async def connect(self, redis_url: str) -> bool:
        """连接Redis"""
        try:
            import redis.asyncio as redis
            self._redis = redis.from_url(redis_url, decode_responses=True)
            await self._redis.ping()
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
    
    async def get_json(self, key: str) -> dict | list | None:
        """获取JSON缓存"""
        data = await self.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None
    
    async def set_json(self, key: str, value: dict | list, expire: int = 300) -> bool:
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


# 单例实例
cache_service = CacheService()


def cached(key_prefix: str, expire: int = 300):
    """缓存装饰器"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
            
            # 尝试获取缓存
            cached_data = await cache_service.get_json(cache_key)
            if cached_data is not None:
                return cached_data
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 存储缓存
            if result is not None:
                await cache_service.set_json(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator
