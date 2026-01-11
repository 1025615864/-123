"""接口限流中间件"""
import time
from collections import defaultdict
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from ..services.cache_service import cache_service


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于IP的请求速率限制中间件"""
    
    def __init__(
        self, 
        app: ASGIApp,
        requests_per_minute: int = 60,
        requests_per_second: int = 10,
        excluded_paths: list[str] | None = None,
        trusted_proxies: list[str] | None = None,
        max_tracked_ips: int = 10000
    ):
        super().__init__(app)
        self.requests_per_minute: int = requests_per_minute
        self.requests_per_second: int = requests_per_second
        self.excluded_paths: list[str] = excluded_paths or ["/docs", "/redoc", "/openapi.json", "/health", "/"]
        self.trusted_proxies: set[str] = set(trusted_proxies or [])
        self.max_tracked_ips: int = max(100, int(max_tracked_ips))
        
        # 存储请求记录: {ip: [(timestamp, count), ...]}
        self.request_records: dict[str, list[float]] = defaultdict(list)
        self._ip_last_seen: dict[str, float] = {}
        
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        remote = request.client.host if request.client else "unknown"

        if remote in self.trusted_proxies:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()

        return remote

    def _evict_if_needed(self) -> None:
        if len(self.request_records) < self.max_tracked_ips:
            return

        oldest_ip: str | None = None
        oldest_time = float("inf")
        for ip, last_seen in self._ip_last_seen.items():
            if last_seen < oldest_time:
                oldest_time = last_seen
                oldest_ip = ip

        if oldest_ip is not None:
            _ = self.request_records.pop(oldest_ip, None)
            _ = self._ip_last_seen.pop(oldest_ip, None)
    
    def _clean_old_records(self, ip: str, current_time: float):
        """清理过期的请求记录"""
        # 只保留最近1分钟的记录
        cutoff = current_time - 60
        self.request_records[ip] = [
            t for t in self.request_records[ip] if t > cutoff
        ]
        if not self.request_records[ip]:
            _ = self.request_records.pop(ip, None)
            _ = self._ip_last_seen.pop(ip, None)
    
    def _check_rate_limit_memory(self, ip: str) -> tuple[bool, str, int]:
        current_time = time.time()
        self._clean_old_records(ip, current_time)

        if ip not in self.request_records:
            self._evict_if_needed()
            if ip not in self.request_records:
                self.request_records[ip] = []

        records = self.request_records[ip]

        one_second_ago = current_time - 1
        requests_last_second = sum(1 for t in records if t > one_second_ago)
        if requests_last_second >= self.requests_per_second:
            return False, "每秒请求过多，请稍后再试", 0

        if len(records) >= self.requests_per_minute:
            return False, "请求过于频繁，请稍后再试", 0

        self.request_records[ip].append(current_time)
        self._ip_last_seen[ip] = current_time
        remaining = self.requests_per_minute - len(self.request_records[ip])
        return True, "", max(0, int(remaining))

    async def _check_rate_limit_redis(self, ip: str) -> tuple[bool, str, int]:
        redis = cache_service.redis
        if redis is None:
            return self._check_rate_limit_memory(ip)

        key_sec = f"rl:ip:{ip}:sec"
        key_min = f"rl:ip:{ip}:min"

        sec_count = int(await redis.incr(key_sec))
        if sec_count == 1:
            _ = await redis.expire(key_sec, 1)
        if sec_count > int(self.requests_per_second):
            return False, "每秒请求过多，请稍后再试", 0

        min_count = int(await redis.incr(key_min))
        if min_count == 1:
            _ = await redis.expire(key_min, 60)
        if min_count > int(self.requests_per_minute):
            return False, "请求过于频繁，请稍后再试", 0

        remaining = int(self.requests_per_minute) - int(min_count)
        return True, "", max(0, remaining)
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """处理请求"""
        # 排除特定路径
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            return await call_next(request)
        
        # 获取客户端IP
        client_ip = self._get_client_ip(request)
        
        # 检查速率限制
        if cache_service.redis is not None:
            allowed, message, remaining = await self._check_rate_limit_redis(client_ip)
        else:
            allowed, message, remaining = self._check_rate_limit_memory(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": message},
                headers={"Retry-After": "60"},
            )
        
        # 继续处理请求
        response = await call_next(request)
        
        # 添加速率限制头信息
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        
        return response


class APIKeyRateLimiter:
    """基于API Key的速率限制器（用于特定接口）"""
    
    def __init__(self, requests_per_minute: int = 20):
        self.requests_per_minute: int = requests_per_minute
        self.request_records: dict[str, list[float]] = defaultdict(list)
    
    def check(self, key: str) -> bool:
        """检查是否允许请求"""
        current_time = time.time()
        cutoff = current_time - 60
        
        # 清理过期记录
        self.request_records[key] = [
            t for t in self.request_records[key] if t > cutoff
        ]
        
        # 检查限制
        if len(self.request_records[key]) >= self.requests_per_minute:
            return False
        
        self.request_records[key].append(current_time)
        return True


# AI聊天接口限流器（更严格）
ai_chat_limiter = APIKeyRateLimiter(requests_per_minute=30)

# 文书生成接口限流器
document_limiter = APIKeyRateLimiter(requests_per_minute=10)
