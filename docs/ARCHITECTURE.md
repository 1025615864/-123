# 架构概览（百姓法律助手）

## 1. 总览

本项目为单仓库（monorepo）形态：

- `backend/`：FastAPI（异步）提供 REST API + WebSocket
- `frontend/`：Vite + React 前端 SPA
- `helm/baixing-assistant/`：K8s 部署（backend + frontend + ingress）

整体流量模型：

- 浏览器访问 `/`：由前端 SPA 处理路由
- 浏览器访问 `/api/*`：转发到后端 API
- 浏览器访问 `/ws`：连接后端 WebSocket（用于通知/实时事件）

## 2. 后端（backend/）

### 2.1 入口与路由

- 应用入口：`backend/app/main.py`
- API 路由聚合：`backend/app/routers/__init__.py`

关键约定：

- REST API 前缀：`/api`
- WebSocket：`/ws`（不在 `/api` 下）
- 健康检查：`/health`、`/health/detailed`、`/api/health`

主要 Router 前缀（以 `app.include_router(api_router, prefix="/api")` 为准）：

- `/api/user`：注册/登录/个人信息/配额
- `/api/forum`：帖子/评论/审核
- `/api/news`：新闻列表/详情/专题/采集/News AI
- `/api/lawfirm`：律所/律师/预约
- `/api/documents`：文书生成
- `/api/admin/document-templates`：文书模板管理
- `/api/contracts`：合同审查
- `/api/search`：全局搜索
- `/api/payment`：订单/支付/回调审计
- `/api/settlement`：律师钱包/收入记录/银行卡/提现申请
- `/api/notifications`：通知
- `/api/system`：系统配置/运维相关
- `/api/admin`：管理后台统计/导出
- `/api/knowledge`：知识库管理
- `/api/calendar`：法律日历
- `/api/feedback`：客服反馈
- `/api/reviews`：律师复核与 SLA 催办

### 2.2 中间件与横切能力

- 日志：`RequestLoggingMiddleware`、`ErrorLoggingMiddleware`
- 请求 ID：`RequestIdMiddleware`（前端会携带 `X-Request-Id`）
- 速率限制：`RateLimitMiddleware`（基于 IP，Redis 可选）
- 响应 Envelope：`EnvelopeMiddleware`
  - 当请求头 `X-Api-Envelope` 为真时，2xx JSON 会包装为 `{ok,data,ts}`

### 2.3 数据层

- ORM：SQLAlchemy 2.x async
- Session：`AsyncSessionLocal`
- 初始化：`init_db()`
  - `DEBUG=true` 或 `DB_ALLOW_RUNTIME_DDL=1` 时允许运行时 `create_all` + 轻量自修复
  - `DEBUG=false` 时要求 Alembic schema 在 head（否则启动失败）

详见：`docs/DATABASE.md`。

### 2.4 定时任务（PeriodicLockedRunner）

后端在 lifespan 中注册周期任务（依赖 Redis 进行分布式锁与可用性保障）：

- `scheduled_news`：处理定时发布/下架
- `rss_ingest`：RSS 采集
- `news_ai_pipeline`：News AI 标注流水线
- `settlement`：律师收入结算
- `wechatpay_platform_certs_refresh`：微信支付平台证书刷新
- `review_task_sla`：律师复核 SLA 扫描与通知

注意：

- 当 `DEBUG=false` 且 Redis 不可用时，后端会直接拒绝启动。

### 2.5 WebSocket

- 路由：`backend/app/routers/websocket.py`
- 连接地址：`ws(s)://<host>/ws?token=<jwt>`
- token 可通过 query 或 `Authorization: Bearer` header 提供
- 服务：`backend/app/services/websocket_service.py`

WebSocket 主要用于：

- 通知类消息实时推送（前端收到后会刷新通知列表缓存）

## 3. 前端（frontend/）

### 3.1 入口与路由

- 入口路由：`frontend/src/App.tsx`
- Layout：`frontend/src/components/Layout.tsx`

### 3.2 API Client 约定

- Axios client：`frontend/src/api/client.ts`
  - 自动注入 `Authorization: Bearer <token>`
  - 自动注入 `X-Api-Envelope: 1`（配合后端 Envelope）
  - 自动注入 `X-Request-Id`

### 3.3 WebSocket

- Hook：`frontend/src/hooks/useWebSocket.ts`
  - 默认连接：`ws(s)://<当前 host>/ws`
  - 若设置 `VITE_API_BASE_URL` / `VITE_API_URL`，会据此推导 WebSocket host

### 3.4 本地开发代理

- `frontend/vite.config.ts`：
  - `/api`、`/robots.txt`、`/sitemap.xml` -> 后端
  - `/ws` -> 后端（WebSocket）

## 4. 部署

### 4.1 Docker

- 后端镜像：`backend/Dockerfile`
- 前端镜像：`frontend/Dockerfile` + `frontend/nginx.conf`
- Compose：`docker-compose.yml` / `docker-compose.prod.yml`

### 4.2 Kubernetes（Helm）

- Chart：`helm/baixing-assistant`
- Ingress 默认：`/api` -> backend、`/` -> frontend
- 建议同时路由 `/ws` -> backend（保证实时能力可用）

## 5. 安全与配置治理

- Secrets 不入库（`.gitignore` 已忽略 `.env*`）
- 管理后台 SystemConfig 不允许写入敏感 secret（后端有硬拦截与单测覆盖）

## 6. 开发者文档（推荐阅读顺序）

- 模块文档索引：`docs/modules/INDEX.md`

基础设施：

- 后端基础设施（鉴权/权限/RequestId/限流/配额/缓存锁）：`docs/modules/BACKEND_INFRA.md`
- 端到端数据流（请求 →DB→ 通知/WS→ 前端缓存刷新）：`docs/modules/DATA_FLOWS.md`
- SystemConfig 规则（含 News AI providers 的特殊约束）：`docs/modules/SYSTEM_CONFIG.md`
- 上传与存储（local/S3）：`docs/modules/UPLOAD_STORAGE.md`
- 前端架构（路由/API client/React Query/WebSocket）：`docs/modules/FRONTEND_ARCH.md`

核心业务模块：

- News AI（pipeline + overrides + 运维接口）：`docs/modules/NEWS_AI.md`
- AI/律师咨询（AI session + 律师预约 + 消息/评价）：`docs/modules/CONSULTATION.md`
- 论坛（帖子/评论/审核/内容过滤）：`docs/modules/FORUM.md`
- 文书生成（生成/PDF/存档）：`docs/modules/DOCUMENTS.md`
- 文书模板管理（后台模板+版本+发布）：`docs/modules/DOCUMENT_TEMPLATES.md`
- 合同审查（文件解析+AI 体检+规则增强）：`docs/modules/CONTRACTS.md`
- 知识库（CRUD/导入/向量化/模板）：`docs/modules/KNOWLEDGE.md`
- 法律日历（提醒 CRUD）：`docs/modules/CALENDAR.md`
- 客服反馈与工单：`docs/modules/FEEDBACK.md`
- 通知（API + 广播 + WebSocket 联动）：`docs/modules/NOTIFICATIONS.md`
- 搜索（全局搜索/建议/热词/历史）：`docs/modules/SEARCH.md`
- 支付（订单/回调验签/回调审计/对账/管理员运维）：`docs/modules/PAYMENT.md`
- 结算与提现（律师钱包/冻结期/提现审批）：`docs/modules/SETTLEMENT.md`
- 律师复核与 SLA（任务/SLA/通知+WebSocket）：`docs/modules/REVIEWS_SLA.md`
- 管理后台统计与导出：`docs/modules/ADMIN_CONSOLE.md`

## 7. 关键实现约定（开发者必读）

### 7.1 鉴权与权限

- JWT：`backend/app/utils/security.py`，token payload 使用 `sub` 存放用户 id
- 依赖注入：`backend/app/utils/deps.py`
  - `get_current_user`：读取 `Authorization: Bearer <token>`
  - `require_admin`：`role in {admin, super_admin}`
  - `require_lawyer_verified`：律师 + 手机/邮箱验证（敏感操作兜底）

角色与静态权限映射：

- `backend/app/utils/permissions.py`

### 7.2 RequestId / 限流 / 配额

- RequestId：`backend/app/middleware/request_id_middleware.py`
  - 使用 `X-Request-Id` 贯穿链路

项目存在两套“限流/额度”机制（语义不同，排障时要区分）：

- 全局 IP 限流中间件：`backend/app/middleware/rate_limit.py`
  - 429 文案通常为“每秒请求过多/请求过于频繁”
- 业务配额（Quota，按天）：`backend/app/services/quota_service.py`
  - 429 文案通常为“今日 AI 咨询次数已用尽/今日文书生成次数已用尽”

此外还有装饰器限流：

- `backend/app/utils/rate_limiter.py:rate_limit`
  - 可按 IP/用户/端点组合 key
  - `by_user` 依赖 `AuthContextMiddleware` 读取 `request.state.user_id`

### 7.3 SystemConfig（DB 配置）与敏感信息治理

- SystemConfig API：`backend/app/routers/system.py`
- 关键安全策略：
  - **禁止**在 SystemConfig 存储 `secret/password/api_key/private_key` 等敏感项
  - News AI providers 配置允许写入，但 **providers JSON/B64 中禁止出现 `api_key` 字段**

详见：`docs/modules/SYSTEM_CONFIG.md`。

### 7.4 上传存储

- API：`/api/upload/*`
- provider：`backend/app/services/storage_service.py`
  - local：文件落地 `backend/uploads/<category>/...`
  - s3：GET 通过 307 重定向到 `STORAGE_PUBLIC_BASE_URL`

详见：`docs/modules/UPLOAD_STORAGE.md`。
