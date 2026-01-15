# 后端基础设施（BACKEND_INFRA）

本文件面向后端开发者，描述项目的鉴权、权限、RequestId、限流、配额、缓存/锁等基础设施约定。

## 1. 认证（JWT）

- 实现：`backend/app/utils/security.py`
- token payload：使用 `sub` 存放 `user_id`

调用方：

- `backend/app/utils/deps.py:get_current_user()`
  - 从 `Authorization: Bearer <token>` 读取 token
  - `decode_token()` 失败 / `sub` 不合法 / 用户不存在 -> 401
  - 用户 `is_active=false` -> 403

## 2. AuthContextMiddleware（用于 by_user 限流等横切能力）

- `backend/app/middleware/auth_context_middleware.py`
- 作用：从请求 header 解出 `user_id` 写入 `request.state.user_id`

注意：

- 它不做 DB 查询，只从 JWT 解码，因此属于“弱认证上下文”，用于限流/日志等。

## 3. RequestIdMiddleware（链路追踪）

- `backend/app/middleware/request_id_middleware.py`

规则：

- 若请求带 `X-Request-Id`，沿用；否则生成 `uuid4().hex`
- 会写入：
  - `request.state.request_id`
  - `response.headers["X-Request-Id"]`

前端 axios client 默认会携带 `X-Request-Id`。

## 4. 角色与权限

### 4.1 Role 常量

- `backend/app/utils/permissions.py:Role`
  - `user` / `lawyer` / `moderator` / `admin` / `super_admin`

### 4.2 路由依赖（强约束）

- `require_admin`：允许 `admin/super_admin`
- `require_lawyer`：要求 `lawyer`
- `require_lawyer_verified`：律师 + 手机/邮箱已验证（并在部分业务里要求律师资料已绑定/已认证）

实现位置：`backend/app/utils/deps.py`

### 4.3 Permission 映射（可选，用于装饰器式鉴权）

- `backend/app/utils/permissions.py`
  - `ROLE_PERMISSIONS` 为静态映射
  - `require_permission()` / `require_role()` 等为装饰器

## 5. 限流（两套机制）

项目同时存在：

### 5.1 全局 IP 限流中间件（RateLimitMiddleware）

- 文件：`backend/app/middleware/rate_limit.py`
- 默认策略：
  - `requests_per_second` / `requests_per_minute`
  - 排除路径（默认包含 `/docs`、`/health`、`/` 等）
  - 支持 `trusted_proxies` 下从 `X-Forwarded-For`/`X-Real-IP` 取真实 IP
- 存储：
  - Redis 可用时使用 Redis 计数器
  - 否则 fallback 为内存

### 5.2 装饰器限流（rate_limit）

- 文件：`backend/app/utils/rate_limiter.py`
- 用法：`@rate_limit(*RateLimitConfig.X, by_ip=True, by_user=False)`

实现要点：

- key 默认由 `path + ip + user_id(optional)` 拼成
- `by_user` 依赖 `AuthContextMiddleware` 提供 `request.state.user_id`
- 存储：Redis 或内存
- 超限返回 429，带 `Retry-After`、`X-RateLimit-Reset` 等 header

## 6. 业务配额（Quota，按天消耗）

- 文件：`backend/app/services/quota_service.py`
- 表：
  - `user_quota_daily`
  - `user_quota_pack_balances`

策略：

- AI 咨询次数：`consume_ai_chat()`
- 文书生成次数：`consume_document_generate()`

配额来源优先级：

- SystemConfig（同名 key）
- env 默认值

管理员与 super_admin：近似无限（1e9）。

## 7. 缓存与分布式锁（cache_service）

- 文件：`backend/app/services/cache_service.py`

能力：

- `get/set/delete` + JSON 版本
- `clear_pattern`
- `acquire_lock/refresh_lock/release_lock`

存储：

- Redis 可用时使用 Redis
- Redis 不可用时 fallback 为进程内存（仅适合开发）

支付回调、周期任务等会使用锁进行幂等与并发保护。
