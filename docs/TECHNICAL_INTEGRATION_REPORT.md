# 技术对接报告（给甲方工程师）

项目名称：百姓法律助手（百姓助手）

版本：v1.1

更新时间：2026-01-06

适用对象：甲方研发/运维/安全/测试工程师

---

## 1. 技术栈与总体架构

### 1.1 技术栈

- 后端

  - FastAPI（REST API）
  - SQLAlchemy 2.x Async（ORM）
  - Pydantic / pydantic-settings（配置与校验）
  - JWT（python-jose）
  - Redis（生产强烈建议，用于分布式锁/周期任务）
  - AI：OpenAI-compatible HTTP API（可替换供应商）
  - RAG：LangChain + ChromaDB（可选，用于知识检索增强）

- 前端

  - React + TypeScript + Vite
  - React Router
  - TailwindCSS
  - React Query + Axios
  - Playwright（E2E）

- 交付
  - Docker Compose（本地/生产示例）
  - Helm Chart（Kubernetes + Ingress）
  - GitHub Actions CI（测试/构建/Helm 校验/类型检查）

### 1.2 架构概览

- 前端（SPA）通过 `/api` 访问后端 REST API。
- 后端提供：
  - 业务 API（用户/AI/新闻/论坛/律所/支付/通知/工具等）
  - 运维接口（健康检查、News AI 状态等）
  - WebSocket（实时推送基础能力）
- 数据层：
  - DB：SQLite（默认/本地）或 Postgres（生产推荐）
  - Redis：生产建议必配（否则 `DEBUG=false` 时会禁用周期任务）
  - ChromaDB：可选（知识库向量化与检索增强）

---

## 2. 代码结构与模块边界

### 2.1 目录

- `backend/app/main.py`

  - FastAPI 应用入口
  - 注册路由（`/api` 前缀）与中间件
  - 应用生命周期（init_db、周期任务 runner 等）

- `backend/app/routers/`

  - API 路由聚合：`backend/app/routers/__init__.py`
  - 路由前缀（均在 `/api` 下）：
    - `/user`（用户管理）
    - `/ai`（AI 法律助手）
    - `/news`（新闻资讯 + 管理端子接口）
    - `/forum`（论坛 + 管理端审核/规则）
    - `/lawfirm`（律所/律师服务）
    - `/knowledge`（知识库/咨询模板/向量化）
    - `/documents`（文书生成）
    - `/search`（全局搜索）
    - `/notifications`（通知系统）
    - `/payment`（支付订单）
    - `/lawyer`（律师结算/提现：钱包、收入、收款账户、提现申请）
    - `/calendar`（法律日历）
    - `/system`（系统配置/运维状态/日志）
    - `/admin`（统计与导出等管理后台 API）
  - WebSocket：`/ws`（不在 `/api` 前缀下）

- `frontend/src/App.tsx`
  - 前台路由：
    - `/` 首页
    - `/chat` AI 咨询
    - `/news` 新闻列表与详情
    - `/forum` 论坛
    - `/lawfirm` 律所
    - `/orders` 我的订单 / 我的预约（统一入口，tab 切换）
    - `/lawfirm/consultations` 律师预约（兼容入口：会重定向到 `/orders?tab=consultations`）
    - `/lawyer/verification` 律师认证申请
    - `/lawyer` 律师工作台
    - `/documents` 文书生成
    - `/calendar` 法律日历
    - `/notifications` 通知
    - `/login` `/register` `/profile`
  - 管理后台路由：`/admin/*`（AdminLayout）

---

## 3. 环境变量与安全策略（必须遵守）

### 3.1 核心原则：Secrets 不入库

- `OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET`、Redis 密码等 **必须通过环境变量 / Secret Manager / K8s Secret 注入**。
- 后端的 SystemConfig 更新接口会阻止写入疑似 secret 的配置项，并对敏感 value 返回 `***`（脱敏）。

### 3.2 后端关键环境变量（生产建议）

- 必填（生产 `DEBUG=false`）

  - `DEBUG=false`
  - `DATABASE_URL`（建议 Postgres）
  - `JWT_SECRET_KEY` 或 `SECRET_KEY`（长度>=32 且不能用默认值）
  - `PAYMENT_WEBHOOK_SECRET`（长度>=16）

- 微信支付（WeChatPay v3，对接微信回调验签/解密时必需，Secrets 不入库）

  - `WECHATPAY_MCH_ID`
  - `WECHATPAY_MCH_SERIAL_NO`
  - `WECHATPAY_PRIVATE_KEY`（商户私钥 PEM；可包含换行）
  - `WECHATPAY_API_V3_KEY`（32 字节）
  - `WECHATPAY_CERTIFICATES_URL`（可选，默认 `https://api.mch.weixin.qq.com/v3/certificates`）

- 微信平台证书自动刷新（可选，生产建议开启；使用分布式锁避免多副本重复刷新）

  - `WECHATPAY_CERT_REFRESH_ENABLED`（`true/1/on` 才启用）
  - `WECHATPAY_CERT_REFRESH_INTERVAL_SECONDS`（可选，默认 `86400`，即 24h）

- 强烈推荐

  - `REDIS_URL`（生产强烈建议；`DEBUG=false` 且 Redis 不可用会禁用周期任务）

- AI（按需启用）

  - `OPENAI_API_KEY`
  - `OPENAI_BASE_URL`（可选，OpenAI-compatible）
  - `AI_MODEL`（可选）
  - `AI_FALLBACK_MODELS`（可选）

- CORS / 代理

  - `CORS_ALLOW_ORIGINS`（逗号分隔）
  - `TRUSTED_PROXIES`（可选）

- 周期任务与采集
  - `NEWS_AI_ENABLED`（启用 News AI pipeline）
  - `NEWS_AI_INTERVAL_SECONDS`（默认 120）
  - `RSS_FEEDS` / `RSS_INGEST_ENABLED` / `RSS_INGEST_INTERVAL_SECONDS`（按需启用）

### 3.3 前端关键环境变量

- `VITE_API_BASE_URL`
  - 本地开发通常为 `/api`（通过 Vite proxy 或 Ingress 转发到后端）。
- 可选：`VITE_PROXY_TARGET` / `VITE_WS_PROXY_TARGET`（见 `frontend/vite.config.ts`）

---

## 4. 部署方式

### 4.1 本地开发（推荐）

- 后端

  - 复制：`backend/env.example` -> `backend/.env`（默认 SQLite，可直接跑）
  - 启动：`py -m uvicorn app.main:app --reload --port 8000`（在 `backend/` 目录执行）
  - Swagger：`http://localhost:8000/docs`

- 前端
  - `npm install`
  - `npm run dev`（默认 `http://localhost:5173`）

### 4.2 Docker Compose

- 开发：`docker-compose.yml`

  - Postgres + backend + frontend
  - 前端：`http://localhost:3000`
  - 后端：`http://localhost:8000`

- 生产示例：`docker-compose.prod.yml`
  - Postgres + Redis + backend + frontend
  - 关键 secrets 通过宿主环境变量注入（`.env`）

### 4.3 Kubernetes / Helm

- Chart：`helm/baixing-assistant`
- Ingress：默认 `/api` -> backend，`/` -> frontend
- secrets 三种方式（选一）：
  - Chart 内置 Secret（values 中配置 `backend.secret.*`）
  - 复用已有 Secret（`backend.existingSecretName`）
  - ExternalSecrets（示例 values，需集群安装 external-secrets controller）

---

## 5. 关键后端接口（对接清单）

### 5.1 基础

- 健康检查

  - `GET /health`
  - `GET /api/health`（兼容前端代理）
  - `GET /health/detailed`

- API 文档
  - Swagger：`GET /docs`
  - OpenAPI：`GET /openapi.json`

### 5.2 认证与登录（JWT）

- 登录：`POST /api/user/login`

  - JWT 位于响应：`token.access_token`
  - 请求头：`Authorization: Bearer <token>`

- 获取当前用户：`GET /api/user/me`

### 5.3 AI 咨询（/api/ai）

- `POST /api/ai/chat`
- `POST /api/ai/chat/stream`（SSE）
- 会话历史：`GET /api/ai/consultations` / `GET /api/ai/consultations/{session_id}`

说明：AI 路由在启动时是“可选加载”，如果依赖缺失或配置异常会被禁用（见 `backend/app/main.py` 的 try-import）。

### 5.4 新闻（/api/news）与 News AI

- 用户侧

  - 新闻列表：`GET /api/news`
  - 新闻详情：`GET /api/news/{news_id}`（详情含 `ai_annotation`）

- 管理端（管理员）

  - News AI 手动重跑：`POST /api/news/admin/{news_id}/ai/rerun`
  - 链接检查：`POST /api/news/admin/link_check`
  - 版本历史：`GET /api/news/admin/{news_id}/versions?limit=...`

- News AI 运维状态（管理员）
  - `GET /api/system/news-ai/status`
    - 返回 providers 生效配置（脱敏）、积压、错误统计等

### 5.5 论坛（/api/forum）

- 发帖：`POST /api/forum/posts`（登录）
- 评论：`POST /api/forum/comments`（登录）
- 管理端审核/规则：`/api/forum/admin/...`

### 5.6 律所服务（/api/lawfirm）

- 律所列表：`GET /api/lawfirm/firms`
- 律所详情：`GET /api/lawfirm/firms/{firm_id}`
- 管理端：`/api/lawfirm/admin/...`

### 5.7 知识库（/api/knowledge，管理员）

- 法律知识 CRUD：`/api/knowledge/laws...`
- 向量化：`/api/knowledge/laws/{id}/vectorize`、`/api/knowledge/laws/batch-vectorize`、`/api/knowledge/sync-vector-store`
- 咨询模板：`/api/knowledge/templates...`

### 5.8 文书生成（/api/documents）

- `POST /api/documents/generate`
- `GET /api/documents/types`

### 5.9 全局搜索（/api/search）

- `GET /api/search?q=...`
- `GET /api/search/suggestions?q=...`
- `GET /api/search/hot`
- `GET /api/search/history` / `DELETE /api/search/history`

### 5.10 通知（/api/notifications）

- `GET /api/notifications`
- `GET /api/notifications/unread-count`
- 已读：`PUT /api/notifications/{id}/read` / `PUT /api/notifications/read-all`
- 删除：`DELETE /api/notifications/{id}`

### 5.11 支付（/api/payment）

- 创建订单：`POST /api/payment/orders`
- 支付订单：`POST /api/payment/orders/{order_no}/pay`
- Webhook（验签）：`POST /api/payment/webhook`（HMAC；依赖 `PAYMENT_WEBHOOK_SECRET`）
- 支付宝异步回调：`POST /api/payment/alipay/notify`（RSA2 验签）
- 微信支付回调（v3）：`POST /api/payment/wechat/notify`
  - 验签：平台证书 + `Wechatpay-*` 请求头
  - 解密：`resource` 使用 `WECHATPAY_API_V3_KEY` 解密

管理员审计/对账（/api/payment/admin）：

- 回调事件列表：`GET /api/payment/admin/callback-events?page=...&page_size=...&provider=...&order_no=...&trade_no=...&verified=...`
- 回调统计：`GET /api/payment/admin/callback-events/stats?minutes=...&provider=...`
- 订单对账：`GET /api/payment/admin/reconcile/{order_no}?limit=...`
- 微信平台证书：
  - `GET /api/payment/admin/wechat/platform-certs`
  - `POST /api/payment/admin/wechat/platform-certs/refresh`
  - `POST /api/payment/admin/wechat/platform-certs/import`

支付渠道配置状态（管理员）：

- `GET /api/payment/admin/channel-status`
  - 说明：出于安全策略（Secrets 不入库/不回显），此接口不会返回支付宝/微信的密钥明文，仅返回“是否已配置/是否就绪”、平台证书缓存数量与更新时间等运维信息。

说明：

- 生产联调时，甲方需提供：支付宝/微信商户参数、证书/密钥、回调白名单，以及沙箱/生产环境信息。
- 平台证书会缓存到 DB（SystemConfig）用于回调验签；商户私钥/APIv3 key 仍必须通过环境变量注入。

当“支付宝/微信信息展示无法获取”时的替代方案（推荐）：

1. 使用 `GET /api/payment/admin/channel-status` 查看渠道是否已配置与是否就绪（不回显 secrets）。
2. 当服务器无法访问微信证书接口（网络受限/无白名单/无联调环境）时：
   - 通过 `POST /api/payment/admin/wechat/platform-certs/import` 离线导入平台证书。
   - 支持两种方式：
     - `platform_certs_json`：粘贴平台证书 JSON（需为后端 `dump_platform_certs_json` 的输出格式）。
     - `cert_pem`：粘贴单个证书 PEM（可选传 `serial_no` / `expire_time`）。

### 5.12 律师结算与商业化（/api/lawyer + /api/admin + /api/user/me/quotas）

- 律师侧（需 `lawyer` 权限）

  - 钱包：`GET /api/lawyer/wallet`
  - 收入明细：`GET /api/lawyer/income-records`
  - 导出收入：`GET /api/lawyer/income-records/export`
  - 收款账户：`GET /api/lawyer/bank-accounts` / `POST /api/lawyer/bank-accounts` / `DELETE /api/lawyer/bank-accounts/{id}`
  - 提现：`GET /api/lawyer/withdrawals` / `POST /api/lawyer/withdrawals`

- 管理员侧（需 `admin` 权限）

  - 提现申请：`GET /api/admin/withdrawals` / `GET /api/admin/withdrawals/{id}`
  - 提现审核与打款状态：`POST /api/admin/withdrawals/{id}/approve|reject|complete|fail`
  - 结算统计：`GET /api/admin/settlement-stats`
  - CSV 导出：
    - 提现：`GET /api/admin/withdrawals/export`
    - 收入：`GET /api/admin/income-records/export`

- 商业化与配额
  - 配额查询：`GET /api/user/me/quotas`
  - 下单购买：`POST /api/payment/orders`（`order_type=vip|ai_pack`）
    - `vip`：购买会员（天数/价格由 SystemConfig 可配置）
    - `ai_pack`：购买次数包（AI 咨询/文书生成；价格/可选包由 SystemConfig 可配置）

### 5.13 法律日历（/api/calendar）

- 创建提醒：`POST /api/calendar/reminders`
- 列表：`GET /api/calendar/reminders`
- 更新：`PUT /api/calendar/reminders/{id}`
- 删除：`DELETE /api/calendar/reminders/{id}`

### 5.14 WebSocket

- 连接：`ws://<host>/ws?token=<jwt>`
- 状态：`GET /ws/status`

---

## 6. 后台运维与数据初始化

### 6.1 种子数据（仅本地/演示）

仓库提供了种子脚本：`backend/scripts/seed_data.py`

- 用于快速生成演示数据（用户、新闻、律所、论坛帖子等）。
- 账号与口令信息请以脚本内容为准（建议仅用于本地/演示环境）。

### 6.2 周期任务与分布式锁

在 `backend/app/main.py` 的 `lifespan` 中：

- 连接 Redis（若配置 `REDIS_URL`）
- 当 `DEBUG=false` 且 Redis 不可用时，会 **禁用**：
  - 定时新闻任务
  - RSS ingest
  - News AI pipeline

目的：避免生产多副本下重复执行周期任务。

---

## 7. CI / 分支策略（对接协作）

### 7.1 CI 工作流

- `.github/workflows/ci.yml`：

  - `helm-validate`（helm lint/template）
  - `backend-test`（pytest）
  - `frontend-build`（tsc + build）
  - `required-checks`（聚合门禁，依赖以上三项）

- `.github/workflows/type-check.yml`：
  - `pyright`（后端类型检查）

### 7.2 合并策略与主干保护

仓库采用严格 PR 流程：

- 仅允许 **Squash merge**
- 合并后自动删除分支
- `main` 分支保护：
  - 必须走 PR
  - 必须通过 `required-checks`
  - 分支必须 up-to-date
  - 启用 `Require linear history`（线性历史）
  - 管理员不可绕过

---

## 8. 联调建议（给甲方工程师的步骤）

1. 确认环境与依赖

- Python 3.10+、Node 18+、Postgres/Redis（生产）

2. 选择部署方式

- 本地开发：SQLite + 后端/前端 dev server
- 集成/生产：Docker Compose（prod）或 Helm（K8s）

3. 注入 secrets（生产必须）

- `JWT_SECRET_KEY/SECRET_KEY`
- `PAYMENT_WEBHOOK_SECRET`
- `OPENAI_API_KEY`（若启用 AI/News AI）
- `REDIS_URL`（生产建议）

4. 通过 Swagger 校验 API

- `GET /health` / `GET /health/detailed`
- `GET /docs`

5. 按模块联调

- 登录 -> 获取 token -> 带 Bearer 调用用户态接口
- 新闻/论坛/通知/搜索/日历/文书
- 管理端接口（需管理员账号与权限）

6. 跑自动化回归（建议在联调前/上线前至少跑一次）

- 前端 E2E：在 `frontend/` 目录执行：`npm run test:e2e`
  - Playwright 会自动拉起隔离端口的后端/前端 dev server（避免占用本地开发端口）。

E2E 注意事项（常见失败原因）：

- 前端 `AuthContext` 会校验 `localStorage.token` 必须为可解码且未过期的 JWT；否则会清理 token 并重定向到 `/login`。
  - 在纯前端 mock（`page.route`）类用例中，请使用测试工具函数生成伪 JWT：`frontend/tests/e2e/helpers.ts`：`makeE2eJwt()`。
- `/admin/settings` 默认 tab 为 `base`，部分运维卡片只在 `AI 咨询` / `新闻 AI` tab 渲染；E2E 断言前需先切 tab。
- 热门新闻榜单为排序 + limit 场景，E2E 通过 DEBUG 管理接口一次性准备数据：`POST /api/news/admin/{news_id}/debug/set-view-count`（仅 `debug=true` 可用）。
- 移动端底部导航与“更多”弹层入口随导航结构调整：论坛入口在底部导航，工具类（如日历）在“更多”弹层。

最新一次回归结果（2026-01-06）：后端 pytest 95 passed；Playwright E2E `76 passed, 0 failed`；pyright / basedpyright `0 errors/warnings`。

---

## 9. 常见问题

- **生产环境周期任务不跑**

  - 检查 `DEBUG=false` 时是否配置了可用 `REDIS_URL`。

- **AI/News AI 不生效**

  - 检查 `OPENAI_API_KEY` 是否通过环境变量注入。
  - News AI pipeline 需 `NEWS_AI_ENABLED=true`。

- **SystemConfig 写入被拒绝**
  - 触发 secrets 拦截（例如 providers JSON 中含 `api_key`）。

---

## 10. 附：前端路由速查（便于联调）

- 前台

  - `/` 首页
  - `/chat` AI 咨询
  - `/news` 新闻
  - `/forum` 论坛
  - `/lawfirm` 律所
  - `/orders` 我的订单 / 我的预约（统一入口，tab 切换）
  - `/lawfirm/consultations` 律师预约（用户侧，兼容入口：会重定向到 `/orders?tab=consultations`）
  - `/lawyer/verification` 律师认证申请（用户侧）
  - `/lawyer` 律师工作台（律师侧，仅律师可见入口）
  - `/documents` 文书生成
  - `/calendar` 法律日历
  - `/notifications` 通知
  - `/login` `/register` `/profile`

- 管理后台
  - `/admin` 仪表盘
  - `/admin/news` 新闻管理（含 RSS 来源/采集记录/专题/评论）
  - `/admin/forum` 论坛管理
  - `/admin/knowledge` 知识库
  - `/admin/templates` 咨询模板
  - `/admin/settings` 系统设置（含 News AI 运维）
  - `/admin/logs` 操作日志
  - `/admin/notifications` 通知管理
  - `/admin/lawyer-verifications` 律师认证审核
  - `/admin/payment-callbacks` 支付回调审计（列表/统计/微信证书刷新/订单对账）

---

## 11. 交付/使用说明：律师服务闭环（联调与验收）

本模块实现了「用户提交律师认证申请 → 管理员审核通过/驳回 → 审核通过后用户获得律师身份并进入律师工作台处理咨询」的闭环。

### 11.1 测试账号（种子数据）

如果你使用项目自带的种子数据脚本（`backend/scripts/seed_data.py`）初始化数据库，可使用以下账号：

- 管理员：`admin` / `admin123`
- 律师：`lawyer1` / `lawyer123`
- 普通用户：`user1` / `user123`

### 11.2 关键页面入口

- 用户侧律师认证申请：`/lawyer/verification`
- 用户侧我的订单/我的预约（统一入口）：`/orders`
- 律师工作台：`/lawyer`
  - 入口仅在用户角色为 `lawyer` 时展示（目前在个人中心页面中显示）。
- 管理端律师认证审核：`/admin/lawyer-verifications`

### 11.3 关键接口（后端）

- 用户提交认证申请：`POST /api/lawfirm/verification/apply`
- 用户查询认证状态：`GET /api/lawfirm/verification/status`
- 管理员查询认证列表：`GET /api/lawfirm/admin/verifications`
- 管理员审核认证：`POST /api/lawfirm/admin/verifications/{verification_id}/review`
- 律师侧咨询列表：`GET /api/lawfirm/lawyer/consultations`
- 律师接单/拒单/完成：
  - `POST /api/lawfirm/lawyer/consultations/{consultation_id}/accept`
  - `POST /api/lawfirm/lawyer/consultations/{consultation_id}/reject`
  - `POST /api/lawfirm/lawyer/consultations/{consultation_id}/complete`

### 11.4 状态机与验收要点（支付成功后自动确认）

- 用户支付律师咨询订单成功后：
  - 预约状态会从 `pending` 更新为 `confirmed`（支付回调/余额支付均可触发）。
  - 律师在工作台仍可点击“接单”，接口为幂等：当咨询已为 `confirmed` 时会直接返回（不再报错）。

### 11.5 冒烟测试清单（建议步骤）

- 普通用户：

  - 登录后访问 `/lawyer/verification` 可查看/提交认证申请。
  - 在律所详情页发起预约并完成支付后，在 `/orders?tab=consultations` 中看到状态为 `confirmed` 且支付状态为 `paid`。（兼容入口：`/lawfirm/consultations` 会重定向到该页面）

- 管理员：

  - 登录后进入 `/admin/lawyer-verifications` 可看到待审核记录，并可通过/驳回。
  - 审核通过后，用户角色会被更新为 `lawyer`（若用户不是 admin/super_admin）。

- 律师：
  - 登录后在个人中心可看到“律师工作台”入口。
  - 进入 `/lawyer` 能看到咨询列表：
    - 对 `pending` 咨询可执行“接单/拒单”。
    - 当咨询已因支付进入 `confirmed` 时，“接单”接口为幂等返回（不会报错）。
    - 对 `confirmed` 咨询可执行“标记完成”。

### 11.6 端到端冒烟路径（推荐，覆盖闭环）

目标：把「认证申请 → 审核 → 成为律师 → 预约支付 → 律师接单确认」按真实业务路径走通。

前置条件（本地开发）：

- 已启动后端与前端 dev server：
  - 后端：`py -m uvicorn app.main:app --reload --port 8000`
  - 前端：`npm run dev`（默认 `http://127.0.0.1:5173`）
- 建议先执行一次种子数据脚本：`py scripts/seed_data.py`
  - 会保证 `lawyer1` 账号已绑定 `Lawyer` 档案（否则律师工作台会提示“未绑定律师资料”）。
  - 会为 `user1` 预置余额（便于余额支付联调）。

步骤：

1. 使用普通用户（或新注册用户）提交律师认证申请

- 登录普通用户账号（例如：`user1/user123`）
- 进入 `/lawyer/verification` 提交认证信息
- 记录返回的认证状态为 `pending`

2. 管理员审核通过

- 登录管理员账号：`admin/admin123`
- 进入 `/admin/lawyer-verifications`
- 找到待审核记录，点击“通过”
- 审核通过后：
  - 认证状态变为 `approved`
  - 用户 `role` 会变为 `lawyer`
  - 系统会创建/更新 `Lawyer` 档案并绑定到该用户

3. 新晋律师确认可进入律师工作台

- 重新登录刚刚被审核通过的账号
- 进入 `/profile`，应能看到“律师工作台”入口
- 进入 `/lawyer`，应能看到“律师工作台”页面（首次可能显示“暂无预约”）

4. 用户预约并使用余额支付（支付后自动 confirmed）

- 使用任一“普通用户”账号进入某个律所详情页并预约律师（例如 `lawyer1`）
- 在弹窗内选择“余额支付”完成支付
- 进入 `/orders?tab=consultations`：
  - 应看到该预约 `payment_status=paid`
  - `status` 为 `confirmed`

5. 律师接单（幂等）

- 登录对应律师账号（例如 `lawyer1/lawyer123`）
- 进入 `/lawyer`
- 点击“接单”（若咨询已为 `confirmed`，接口会幂等返回，不会报错）
