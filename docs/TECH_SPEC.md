# 技术规范

## 一、技术栈

### 前端

- **框架**：React 19 + TypeScript
- **构建**：Vite 7
- **路由**：React Router DOM 7
- **状态/数据请求**：React Query 5
- **HTTP 请求**：Axios
- **样式**：TailwindCSS 4
- **Markdown 渲染**：react-markdown + remark-gfm
- **E2E 测试**：Playwright

### 后端

- **框架**：FastAPI
- **运行**：Uvicorn
- **数据库**：SQLite（默认，本地开箱即用）/ PostgreSQL（生产推荐）
- **ORM**：SQLAlchemy 2.x（async）
- **迁移**：Alembic
- **认证**：JWT（python-jose）
- **缓存/锁**：Redis（生产推荐，用于周期任务分布式锁）
- **AI**：OpenAI-compatible HTTP API（`OPENAI_API_KEY` + `OPENAI_BASE_URL`）
- **RAG/向量库**：LangChain + ChromaDB
- **文档处理**：pypdf、docx2txt、reportlab

### 部署

- **本地/演示**：Docker Compose（`docker-compose.yml`）
- **生产示例**：`docker-compose.prod.yml`（含 Redis）
- **K8s**：Helm Chart（`helm/baixing-assistant`）

---

## 二、项目结构

### 仓库根目录

```
.
├── backend/                 # FastAPI 后端
├── frontend/                # React 前端
├── docs/                    # 文档
├── scripts/                 # 冒烟/运维脚本
├── docker-compose.yml
├── docker-compose.prod.yml
└── helm/                    # Helm Chart
```

### 后端结构（backend/app）

```
backend/app/
├── main.py                  # FastAPI 入口；挂载 /api；周期任务
├── config.py                # Pydantic Settings；env 解析与生产校验
├── database.py              # Async SQLAlchemy engine/session；init_db
├── models/                  # SQLAlchemy ORM 模型
├── schemas/                 # Pydantic schema（请求/响应）
├── routers/                 # API 路由（按业务拆分）
├── services/                # 业务服务层
├── middleware/              # 中间件（日志/限流等）
└── utils/                   # 通用工具（鉴权、限流、权限等）
```

### 前端结构（frontend/src）

```
frontend/src/
├── App.tsx                  # 路由表（前台 + /admin）
├── components/              # 组件（含 AdminLayout/Layout 等）
├── pages/                   # 页面
├── contexts/                # Auth/Theme/Language 等
├── hooks/                   # useApi/useToast 等
├── api/                     # axios client
└── tests/e2e/               # Playwright 用例
```

---

## 三、命名规范

| 类型            | 规范                          | 示例                      |
| --------------- | ----------------------------- | ------------------------- |
| React 组件文件  | PascalCase                    | `NewsTopicsPage.tsx`      |
| hooks           | camelCase                     | `useApi.ts`               |
| 后端路由文件    | snake_case / 模块名           | `routers/news.py`         |
| SQLAlchemy 表名 | snake_case（复数）/按模型定义 | `users`、`payment_orders` |
| API 路径        | kebab-case/分层路径           | `/api/news/topics`        |

---

## 四、环境变量

> 后端配置定义见 `backend/app/config.py`；示例见 `backend/env.example`。

```env
# backend/.env 示例（开发）
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# JWT
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# 支付回调密钥（生产 DEBUG=false 必填）
PAYMENT_WEBHOOK_SECRET=your-payment-webhook-secret

# CORS
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000
FRONTEND_BASE_URL=http://localhost:5173
TRUSTED_PROXIES=[]

# Redis（生产推荐）
REDIS_URL=

# AI
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
AI_MODEL=deepseek-chat

# 调试
DEBUG=true
SQL_ECHO=
```

### 配置约束（生产）

- 当 `DEBUG=false`：
  - `JWT_SECRET_KEY/SECRET_KEY` 必须为安全值（且长度足够）
  - `PAYMENT_WEBHOOK_SECRET` 必须配置
  - Redis 不可用时会禁用部分周期任务（避免多副本重复执行）

### 生产环境变量清单（建议）

> 完整字段以 `backend/app/config.py` 为准；以下为生产部署建议最小集/常用集。

- 必填（生产）
  - `DATABASE_URL`（推荐 PostgreSQL）
  - `JWT_SECRET_KEY`（强随机；长度足够）
  - `PAYMENT_WEBHOOK_SECRET`（支付回调签名/鉴权）
  - `FRONTEND_BASE_URL`（用于生成支付回跳/链接）
  - `CORS_ALLOW_ORIGINS`（前端域名白名单）
- AI（如启用 AI 能力）
  - `OPENAI_API_KEY`
  - `OPENAI_BASE_URL`
  - `AI_MODEL`
- Redis（生产推荐，多副本时强烈建议）
  - `REDIS_URL`
- 支付渠道（按启用的渠道配置）
  - IKUNPAY：`IKUNPAY_PID` / `IKUNPAY_KEY` / `IKUNPAY_NOTIFY_URL`（可选 `IKUNPAY_RETURN_URL` / `IKUNPAY_GATEWAY_URL`）
  - ALIPAY：`ALIPAY_APP_ID` / `ALIPAY_PUBLIC_KEY` / `ALIPAY_PRIVATE_KEY` / `ALIPAY_NOTIFY_URL`（可选 `ALIPAY_RETURN_URL` / `ALIPAY_GATEWAY_URL`）
  - WECHATPAY：按后端配置项要求（如 `WECHATPAY_*` 系列；若仅保留回调链路也需确保 notify 可达）

### CI / E2E secrets 与生产 secrets 分离

- CI（GitHub Actions）中用于跑回归的密钥应使用 **测试专用 dummy 值**（例如 `JWT_SECRET_KEY=test-secret-key`），不得复用生产密钥。
- 需要访问线上环境的 smoke（例如 `.github/workflows/post-deploy-smoke.yml`）应通过 **GitHub Environments** 的 secrets 管理（如 `production` 环境），并做到：
  - 最小权限 token（只读或仅限 smoke 所需接口）
  - 与生产业务密钥（支付/AI/JWT）严格隔离

---

## 五、API 与鉴权约定

- **Base URL**：后端统一挂载在 `/api`（见 `backend/app/main.py`）。
- **认证方式**：JWT Bearer。

请求头示例：

```http
Authorization: Bearer <token>
```

- **游客与限流**：
  - AI/文书生成等接口对游客按 IP 做限制（并返回 429）。

---

## 六、开发与质量门禁

### 本地启动

- 后端（建议在 `backend/` 目录执行）：
  - `python -m uvicorn app.main:app --reload --port 8000`
- 前端：
  - `npm install`
  - `npm run dev`

### 测试

- 后端：
  - 安装（含测试依赖）：`py -m pip install -r backend/requirements-dev.txt`
  - 运行：`py -m pytest -q`
- 前端：
  - 安装：`npm --prefix frontend ci`
  - 构建：`npm --prefix frontend run build`
- E2E（Playwright，最小文书闭环）：
  - 安装浏览器：`npm --prefix frontend run test:e2e:install`
  - 运行（仅文书用例）：`npm --prefix frontend run test:e2e -- --grep "documents:"`
- CI：GitHub Actions workflow：`.github/workflows/ci.yml`

---

## 七、重要工程约束（必须遵守）

- **Secrets 不入库**：`OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET` 等必须通过环境变量/Secret Manager 注入；系统配置（SystemConfig）禁止写入敏感信息（后端会返回 400）。
- **生产周期任务**：生产多副本部署时建议配置 Redis，用于分布式锁，避免任务重复跑。

---

## 八、可观测性与排障（Stage 9）

### 8.1 request_id（端到端追踪）

- 前端会为当前会话生成稳定的 `X-Request-Id`，并在所有 API 请求中携带。
- 后端会优先使用请求头中的 `X-Request-Id`，并保证响应也带 `X-Request-Id`。
- 后端请求日志/错误日志会打印 `request_id`，用于从前端报错快速定位到具体请求。

常用排查路径：

- 浏览器 DevTools -> Network -> 任意失败请求：
  - 看 Response Headers 中的 `X-Request-Id`
  - 若为 AI 接口错误，响应体也可能包含 `request_id`
- 后端日志中按 `request_id=<id>` 搜索：
  - K8s：`kubectl -n <ns> logs deploy/<release>-baixing-assistant-backend | findstr request_id=<id>`
  - Docker：`docker logs <container> | grep request_id=<id>`

### 8.2 Prometheus 指标（/metrics）

后端暴露 Prometheus 指标：

- `GET /metrics`

关键指标（用于告警与 Grafana Dashboard）：

- HTTP：
  - `baixing_http_requests_total{method,route,status}`
  - `baixing_http_request_duration_seconds_bucket{method,route,status,le}`（用于 P95 等分位数）
- 周期任务：
  - `baixing_job_runs_total{job}` / `baixing_job_failure_total{job}`
  - `baixing_job_last_run_timestamp_seconds{job}` / `baixing_job_last_success{job}`

常用 PromQL：

- 5xx 比例：
  - `sum(rate(baixing_http_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(baixing_http_requests_total[5m])), 1)`
- P95 延迟（全局）：
  - `histogram_quantile(0.95, sum by (le) (rate(baixing_http_request_duration_seconds_bucket[5m])))`
- P95 延迟（按 route 拆分）：
  - `histogram_quantile(0.95, sum by (route, le) (rate(baixing_http_request_duration_seconds_bucket[5m])))`

### 8.3 关键异常上报（可选 webhook）

后端支持将关键异常以 webhook 方式异步上报（默认关闭；上报失败不影响主流程）。

环境变量：

```env
CRITICAL_EVENTS_ENABLED=false
CRITICAL_EVENTS_WEBHOOK_URL=
CRITICAL_EVENTS_WEBHOOK_BEARER=
CRITICAL_EVENTS_WEBHOOK_HEADER_NAME=
CRITICAL_EVENTS_WEBHOOK_HEADER_VALUE=
CRITICAL_EVENTS_MIN_INTERVAL_SECONDS=30
CRITICAL_EVENTS_TIMEOUT_SECONDS=3
```

说明：

- `CRITICAL_EVENTS_ENABLED=true` 且设置 `CRITICAL_EVENTS_WEBHOOK_URL` 后启用。
- 支持两种鉴权方式（二选一即可）：
  - `CRITICAL_EVENTS_WEBHOOK_BEARER`：发送 `Authorization: Bearer ...`
  - `CRITICAL_EVENTS_WEBHOOK_HEADER_NAME/CRITICAL_EVENTS_WEBHOOK_HEADER_VALUE`：自定义 header
- 内置简单去重/限频（`CRITICAL_EVENTS_MIN_INTERVAL_SECONDS`），避免异常风暴刷屏。
- 上报 payload 会包含：`event`、`severity`、`request_id`（如有）、`env`、`data` 等字段。
