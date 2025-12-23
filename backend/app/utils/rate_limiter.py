"""
精细化API限流工具

支持:
- 按IP限流
- 按用户限流
- 按端点限流
- 滑动窗口算法
"""
import time
from collections import defaultdict
from typing import Optional, Callable
from fastapi import Request, HTTPException, status
from functools import wraps

from ..config import get_settings

settings = get_settings()


class RateLimiter:
    """滑动窗口限流器"""
    
    def __init__(self, max_tracked_keys: int = 20000):
        # 格式: {key: [(timestamp, count), ...]}
        self._requests: dict[str, list[tuple[float, int]]] = defaultdict(list)
        self._last_seen: dict[str, float] = {}
        self._max_tracked_keys = max(1000, int(max_tracked_keys))
    
    def _clean_old_requests(self, key: str, window_seconds: int):
        """清理过期的请求记录"""
        now = time.time()
        cutoff = now - window_seconds
        self._requests[key] = [
            (ts, count) for ts, count in self._requests[key]
            if ts > cutoff
        ]
        if not self._requests[key]:
            _ = self._requests.pop(key, None)
            _ = self._last_seen.pop(key, None)

    def _evict_if_needed(self) -> None:
        if len(self._requests) < self._max_tracked_keys:
            return

        oldest_key: str | None = None
        oldest_time = float("inf")
        for k, last_seen in self._last_seen.items():
            if last_seen < oldest_time:
                oldest_time = last_seen
                oldest_key = k

        if oldest_key is not None:
            _ = self._requests.pop(oldest_key, None)
            _ = self._last_seen.pop(oldest_key, None)
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """
        检查是否允许请求
        
        Returns:
            tuple[bool, int]: (是否允许, 剩余配额)
        """
        self._clean_old_requests(key, window_seconds)

        if key not in self._requests:
            self._evict_if_needed()
            if key not in self._requests:
                self._requests[key] = []
        
        total_requests = sum(count for _, count in self._requests[key])
        remaining = max(0, max_requests - total_requests)
        
        if total_requests >= max_requests:
            return False, 0
        
        now = time.time()
        self._requests[key].append((now, 1))
        self._last_seen[key] = now
        return True, remaining - 1
    
    def get_wait_time(self, key: str, window_seconds: int) -> float:
        """获取需要等待的时间（秒）"""
        if not self._requests[key]:
            return 0
        
        oldest = min(ts for ts, _ in self._requests[key])
        wait = oldest + window_seconds - time.time()
        return max(0, wait)


# 全局限流器实例
rate_limiter = RateLimiter()


# 预定义限流配置
class RateLimitConfig:
    """限流配置"""
    
    # 通用限流
    DEFAULT = (100, 60)  # 100次/分钟
    
    # AI接口限流
    AI_CHAT = (20, 60)  # 20次/分钟
    AI_HEAVY = (5, 60)  # 5次/分钟（重型操作）
    
    # 认证相关
    AUTH_LOGIN = (5, 300)  # 5次/5分钟
    AUTH_REGISTER = (3, 3600)  # 3次/小时
    AUTH_PASSWORD_RESET = (3, 3600)  # 3次/小时
    
    # 内容发布
    POST_CREATE = (10, 3600)  # 10篇/小时
    COMMENT_CREATE = (30, 3600)  # 30条/小时
    
    # 搜索
    SEARCH = (30, 60)  # 30次/分钟
    
    # 文件上传
    UPLOAD = (20, 3600)  # 20次/小时

    # 文书生成
    DOCUMENT_GENERATE = (10, 60)  # 10次/分钟

    # 埋点/行为统计
    ANALYTICS_TRACK = (200, 60)  # 200次/分钟
    
    # 管理员操作
    ADMIN = (200, 60)  # 200次/分钟


def get_client_ip(request: Request) -> str:
    """获取客户端真实IP"""
    remote = request.client.host if request.client else "unknown"
    if remote in set(settings.trusted_proxies):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

    return remote


def rate_limit(
    max_requests: int = 100,
    window_seconds: int = 60,
    key_func: Optional[Callable[[Request], str]] = None,
    by_user: bool = False,
    by_ip: bool = True,
):
    """
    限流装饰器
    
    Args:
        max_requests: 最大请求次数
        window_seconds: 时间窗口（秒）
        key_func: 自定义key生成函数
        by_user: 是否按用户ID限流
        by_ip: 是否按IP限流
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get('request')
            if not isinstance(request, Request):
                request = None

            if request is None:
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request = value
                        break

            if request is None:
                # 从args中查找Request对象
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                return await func(*args, **kwargs)
            
            # 生成限流key
            if key_func:
                key = key_func(request)
            else:
                parts = [request.url.path]
                
                if by_ip:
                    parts.append(get_client_ip(request))
                
                if by_user:
                    # 尝试从请求中获取用户ID
                    user_id = getattr(request.state, 'user_id', None)
                    if user_id:
                        parts.append(f"user:{user_id}")
                
                key = ":".join(parts)
            
            allowed, remaining = rate_limiter.is_allowed(key, max_requests, window_seconds)
            
            if not allowed:
                wait_time = rate_limiter.get_wait_time(key, window_seconds)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"请求过于频繁，请在 {int(wait_time)} 秒后重试",
                    headers={
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time() + wait_time)),
                        "Retry-After": str(int(wait_time)),
                    }
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# 便捷装饰器
def rate_limit_ai():
    """AI接口限流"""
    return rate_limit(*RateLimitConfig.AI_CHAT, by_user=True)


def rate_limit_auth():
    """认证接口限流"""
    return rate_limit(*RateLimitConfig.AUTH_LOGIN, by_ip=True)


def rate_limit_post():
    """发帖限流"""
    return rate_limit(*RateLimitConfig.POST_CREATE, by_user=True)


def rate_limit_comment():
    """评论限流"""
    return rate_limit(*RateLimitConfig.COMMENT_CREATE, by_user=True)


def rate_limit_search():
    """搜索限流"""
    return rate_limit(*RateLimitConfig.SEARCH, by_ip=True)


def rate_limit_upload():
    """上传限流"""
    return rate_limit(*RateLimitConfig.UPLOAD, by_user=True)
