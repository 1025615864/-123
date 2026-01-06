# 项目报告（百姓法律助手 / 百姓助手）

更新时间：2026-01-07

> 目的：为下一位接手工程师提供“一份文档就能上手”的项目报告。
>
> 范围：本仓库 `backend/`（FastAPI） + `frontend/`（React） + 部署交付（Docker Compose / Helm）。

---

## 1. 项目概览

**项目定位**：一站式法律服务平台，面向“AI 法律咨询 + 新闻资讯 + 论坛社区 + 律所/律师服务 + 支付订单 + 通知系统”等场景。

**关键特性**：

- **AI 法律咨询**
  - 支持同步与 SSE 流式输出。
  - 支持会话历史持久化（跨重启可续聊）。
  - 可选 RAG：使用 ChromaDB 向量库检索法律知识片段。
- **新闻模块 + News AI 内容加工**
  - 新闻列表/详情/订阅/收藏/评论。
  - News AI 生成摘要/要点/关键词/风险等级，并提供管理员运维状态接口。
  - 管理端支持版本历史/回滚、AI 工作台生成、链接检查。
- **论坛与内容治理**
  - 发帖/评论/点赞/收藏/表情反应。
  - 管理端支持审核、敏感词/过滤规则。
- **支付与订单**
  - 下单/支付/退款/回调验签。
  - 支付回调事件审计：回调事件落库、管理员回调统计/对账、后台审计页 `/admin/payment-callbacks`。
  - 微信支付回调（v3）：平台证书验签 + 回调资源解密（APIv3 key），并支持平台证书刷新/定时刷新。
- **运维交付**
  - Docker Compose 一键启动；生产示例 compose。
  - Helm Chart（K8s + Ingress，默认 `/api` -> backend）。
  - CI：后端测试、前端 build、Helm 校验。

---

## 2. 代码与目录结构

仓库根目录：

- `backend/`
  - `app/main.py`：FastAPI 入口，生命周期内启动周期任务（定时任务、RSS ingest、News AI pipeline 等）。
  - `app/routers/`：API 路由聚合（统一挂载到 `/api` 前缀）。
  - `app/services/`：业务服务层（如 `news_ai_pipeline_service.py`）。
  - `app/models/`：SQLAlchemy ORM 模型。
  - `alembic/`：数据库迁移骨架（Windows/中文路径请使用 `alembic_ascii.ini`）。
- `frontend/`
  - `src/`：React 页面与组件。
  - `src/pages/admin/SettingsPage.tsx`：后台系统设置（含 News AI 运维）。
  - `tests/e2e/`：Playwright 端到端测试。
- `docs/`：本文档与开发/运维说明。
- `helm/baixing-assistant/`：K8s Helm Chart。
- `scripts/`：运维/冒烟脚本（例如 News AI 一键冒烟）。

---

## 3. 技术栈

### 3.1 后端

- FastAPI
- SQLAlchemy 2.x（async）
- Pydantic / pydantic-settings
- JWT（python-jose）
- Redis（生产建议，用于周期任务分布式锁）
- AI：OpenAI-compatible HTTP API
- RAG：LangChain + ChromaDB

### 3.2 前端

- React 19 + TypeScript
- Vite
- TailwindCSS
- React Router
- React Query
- Axios
- Playwright（E2E）

---

## 4. 环境与配置（重要）

### 4.1 核心原则：Secrets 不入库

- `OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET`、Redis 密码等必须通过 **环境变量 / Secret Manager** 注入。
- **禁止**通过管理后台 SystemConfig 写入任何 API Key/secret（后端会返回 400）。

### 4.2 后端关键环境变量（生产）

- **必填**
  - `DEBUG=false`
  - `DATABASE_URL`
  - `JWT_SECRET_KEY` 或 `SECRET_KEY`
  - `PAYMENT_WEBHOOK_SECRET`
- **强烈推荐**
  - `REDIS_URL`（`DEBUG=false` 且 Redis 不可用时会禁用周期任务/News AI pipeline）
- **开发辅助**
  - `SQL_ECHO`：控制 SQLAlchemy SQL 日志（默认关闭；仅本地排障时建议开启）
- **AI 相关**
  - `OPENAI_API_KEY`
  - `OPENAI_BASE_URL`（可选）
  - `AI_MODEL`（可选）

### 4.3 前端关键环境变量

- `VITE_API_BASE_URL`
  - 本地开发通常为 `/api`（由 Vite proxy / Ingress / Nginx 转发到后端）。

### 4.4 配置来源与默认值（建议接手时先读）

- 后端设置定义：`backend/app/config.py`（Pydantic Settings）
  - **默认读取“当前工作目录下的 `.env`”**（测试运行 `pytest` 时不读 `.env`）
    - 通常在 `backend/` 目录启动，所以实际会读到 `backend/.env`
  - `DEBUG` 默认：测试环境自动为 `true`（因为 `pytest` 在 `sys.modules`）
  - `DATABASE_URL` 默认：`sqlite+aiosqlite:///./data/app.db`
  - 本仓库提供 `backend/env.example` 作为本地默认配置模板（当前默认已对齐 SQLite，开箱即用）
- 后端对生产配置有强制校验：
  - 当 `DEBUG=false` 时：
    - `SECRET_KEY/JWT_SECRET_KEY` 必须足够安全（长度 >= 32 且不能用默认值），否则启动直接报错
    - `PAYMENT_WEBHOOK_SECRET` 必须配置且长度 >= 16，否则启动直接报错

### 4.5 常用配置项速查（后端）

- **基础**
  - `DEBUG`：开发建议 `true`；生产必须 `false`
  - `DATABASE_URL`：支持 SQLite（默认）/ Postgres（生产推荐）
  - `SECRET_KEY` / `JWT_SECRET_KEY`：二选一（后端会读这两者之一）
  - `PAYMENT_WEBHOOK_SECRET`：生产必填（`DEBUG=false` 时强校验）
- **网络与代理**
  - `CORS_ALLOW_ORIGINS`：可用逗号分隔字符串（后端会自动拆分）
  - `FRONTEND_BASE_URL`：用于构造部分跳转链接/回调等（默认 `http://localhost:5173`）
  - `TRUSTED_PROXIES`：受信任代理列表（逗号分隔或 JSON 数组字符串）
- **AI**
  - `OPENAI_API_KEY`：必须通过环境变量/Secret 注入（禁止入库）
  - `OPENAI_BASE_URL`：OpenAI-compatible base（默认 `https://api.openai.com/v1`）
  - `AI_MODEL`：默认 `deepseek-chat`
  - `AI_FALLBACK_MODELS`：可选，逗号分隔
- **Redis 与周期任务（生产强烈建议）**
  - `REDIS_URL`：生产建议必配。`DEBUG=false` 且 Redis 不可用时，会禁用 RSS ingest / News AI 等周期任务
- **News AI（周期 pipeline）**
  - `NEWS_AI_ENABLED`：`true/1/on` 才启用
  - `NEWS_AI_INTERVAL_SECONDS`：默认 `120`
  - `NEWS_AI_BATCH_SIZE`：默认由服务端实现决定（E2E 会覆盖为较大值以减少等待）

---

## 5. 本地启动（开发）

### 5.0 常用端口（建议记住）

- **后端开发**：`8000`（FastAPI / Swagger：`/docs`）
- **前端开发**：`5173`（Vite）
- **Docker 前端**：`3000`
- **Postgres（compose）**：`5432`
- **Playwright E2E（隔离端口）**：后端默认 `8001`，前端默认 `5174`

### 5.1 后端

- 在 `backend/` 下复制示例：`backend/env.example` -> `backend/.env`
  - 当前 `env.example` 默认使用 SQLite：`sqlite+aiosqlite:///./data/app.db`，本地可直接启动
  - 如要切换 Postgres：将 `DATABASE_URL` 改为 `postgresql+asyncpg://...`
  - 如需查看 SQL（排障用）：设置 `SQL_ECHO=1`（默认不输出 SQL）
- 创建虚拟环境并安装依赖

说明：Windows 环境如果 `python` 指向 WindowsApps stub，建议使用 `py -m ...`。

启动：

- 推荐（在 `backend/` 目录执行，能直接读取 `backend/.env`）：
  - `py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- 或者（在仓库根目录执行）：
  - `py -m uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000`
  - 注意：此时 `Settings` 默认读取的是“根目录 `.env`”。如果你只配置了 `backend/.env`，需要复制/同步到根目录 `.env`，或在 shell 中注入对应环境变量。

验证：

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/api/health`（兼容前端 proxy 的别名）
- `GET http://localhost:8000/health/detailed`（包含 DB/AI 配置等详细检查）
- Swagger：`http://localhost:8000/docs`

### 5.2 前端

- `npm install`
- `npm run dev`

访问：`http://localhost:5173`

补充：前端 API / WebSocket 代理

- Vite proxy 配置：`frontend/vite.config.ts`
  - `/api` 默认转发到 `http://localhost:8000`（可用 `VITE_PROXY_TARGET` 覆盖）
  - `/ws` 默认转发到 `ws://localhost:8000`（可用 `VITE_WS_PROXY_TARGET` 覆盖）
- 前端请求基址：`frontend/src/api/client.ts`
  - `VITE_API_BASE_URL` 默认回落 `/api`（通常无需额外配置）

### 5.3 一键启动（Docker Compose）

- 开发：`docker compose up -d --build`
  - 前端：`http://localhost:3000`
  - 后端：`http://localhost:8000`
- 生产示例：`docker compose -f docker-compose.prod.yml up -d --build`
  - 依赖仓库根目录 `.env`（从 `env.example.txt` 复制并填写）

---

## 6. 部署交付

### 6.1 Docker Compose

- `docker-compose.yml`：本地/开发示例（包含 Postgres + backend + frontend）。
- `docker-compose.prod.yml`：生产示例（包含 Postgres + Redis + backend + frontend）。

### 6.2 Kubernetes / Helm

Chart：`helm/baixing-assistant`

- 默认 Ingress 规则：`/api` -> backend，`/` -> frontend。
- Secrets 推荐由 K8s Secret 或 ExternalSecrets 注入（参考 Chart README 与 values 示例）。

---

## 7. 关键业务模块说明（后端）

### 7.1 用户与权限

- 登录：`POST /api/user/login`
  - JWT 位于响应的 `token.access_token`（不是顶层 `access_token`）。
- 管理员能力：系统设置、审核、运营接口等。

### 7.2 AI 法律咨询（/api/ai）

- `POST /api/ai/chat`
- `POST /api/ai/chat/stream`（SSE）
- `GET /api/ai/consultations` / `GET /api/ai/consultations/{session_id}` / 导出 / 评价
- `GET /api/ai/consultations/{session_id}/report`（PDF 报告，需要登录）

要点：

- 会话消息落库（consultation/messages）。
- 当请求带 `session_id` 时，会从 DB 读取最近消息注入 assistant，实现跨重启续聊。

AI 咨询模块的实现细节与已知风险点已合并到本文档的「12.5 AI 咨询模块现状（要点）」章节。

### 7.3 新闻与 News AI（/api/news + /api/system/news-ai/status）

- 公共消费：`GET /api/news`、`GET /api/news/{news_id}`（详情包含 `ai_annotation`）。
- 管理端：创建/编辑/审核/版本回滚/链接检查。
- News AI：
  - 管理员手动重跑：`POST /api/news/admin/{news_id}/ai/rerun`
  - 运维状态：`GET /api/system/news-ai/status`（管理员）
  - E2E/调试接口（仅 DEBUG 可用）：`POST /api/news/admin/{news_id}/debug/set-view-count`（设置 `view_count` 并清 hot cache，用于热门新闻用例稳定化）

生产注意：

- 周期 pipeline 由 `NEWS_AI_ENABLED=true` 启用。
- `DEBUG=false` 且 Redis 不可用时，周期任务会被禁用（避免多副本重复执行）。

### 7.4 论坛与审核（/api/forum）

- 帖子/评论 CRUD
- 管理端审核与内容治理

### 7.5 支付与订单（/api/payment）

- 订单创建/支付/取消/退款
- 回调验签依赖 `PAYMENT_WEBHOOK_SECRET`

### 7.6 律师结算与商业化（/api/lawyer + /api/admin + /api/user/me/quotas）

- **律师结算/提现（律师侧）**：钱包、收入明细、收款账户管理、提现申请与记录。
  - 典型接口：`GET /api/lawyer/wallet`、`GET /api/lawyer/income-records`、`POST /api/lawyer/withdrawals`
- **管理员侧**：提现审核与结算统计、CSV 导出（接口响应含脱敏策略）。
  - 典型接口：`GET /api/admin/withdrawals`、`GET /api/admin/withdrawals/export`、`GET /api/admin/settlement-stats`
- **商业化配额**：VIP/次数包额度展示与消耗。
  - 典型接口：`GET /api/user/me/quotas`（配额查询）；支付购买走 `POST /api/payment/orders`（`order_type=vip|ai_pack`）

---

## 8. 测试与质量门禁

### 8.1 后端

- 单测：`py -m pytest -q`
- 类型检查：`py -m pyright`

### 8.2 前端

- build：`npm run build`
- E2E：`npm run test:e2e`
  - Playwright 默认会用隔离端口拉起后端/前端 dev server（避免与本地开发端口冲突）。
  - 默认端口：后端 `8001`、前端 `5174`（见 `frontend/playwright.config.ts`）
  - 如需复用你已经启动的服务：设置 `E2E_REUSE_EXISTING=1`（仅本地建议）
  - Windows 注意：命令行传 `tests/e2e/chat-*.spec.ts` 这类通配符可能匹配不到文件，建议显式列出文件或仅传目录/单文件。
  - 如需隔离 E2E 数据库：设置 `E2E_DATABASE_URL`（否则默认使用 `sqlite+aiosqlite:///../backend/data/app.db`）
  - 常见坑：
    - 前端 `AuthContext` 会校验 `localStorage.token` 必须为可解码且未过期的 JWT；纯前端 mock 场景建议使用 `frontend/tests/e2e/helpers.ts` 的 `makeE2eJwt()`
    - `/admin/settings` 默认 tab 为 `base`，部分运维卡片只在 `AI 咨询` / `新闻 AI` tab 渲染，E2E 断言前需先切 tab
    - 移动端底部导航与“更多”弹层入口可能随导航结构调整，MobileNav 用例以 `dialog` + `日历` 等工具入口为准

最新一次全量回归结果（2026-01-06）：后端 pytest 95 passed；Playwright E2E `76 passed, 0 failed`；pyright / basedpyright `0 errors/warnings`。

增量验证（2026-01-07，本次变更）：前端 `npm run build` OK；Playwright（admin UI feedback 冒烟）`frontend/tests/e2e/admin-ui-feedback.spec.ts` 7 passed。

---

## 9. 运维与冒烟（强烈建议）

### 9.1 冒烟脚本（News AI）

- Windows：`../scripts/smoke-news-ai.ps1`
- Linux/CI：`../scripts/smoke-news-ai.sh`

脚本逻辑：health -> status -> 创建新闻 -> AI rerun -> 轮询确认 -> 清理。

生产部署与冒烟 SOP 的关键要点已合并到本文档的「12.4 生产部署与冒烟（摘要）」章节。

### 9.2 CI 工作流

- `../.github/workflows/ci.yml`
  - Helm 校验、后端测试、前端构建。
- `../.github/workflows/post-deploy-smoke.yml`
  - 部署后手动触发冒烟（需要 Secrets：`BASE_URL`、`ADMIN_TOKEN`）。

### 9.3 GitHub PR 流程与分支策略（重要）

当前仓库已启用较严格的主干保护与合并策略，目标是：**禁止直推 main**、**所有改动走 PR**、**CI 通过后才能合并**、并保持 **线性提交历史**。

- **仓库合并策略（Settings -> General -> Pull Requests）**

  - **仅允许 Squash 合并**：`Allow squash merging = true`
  - 禁用其它合并方式：
    - `Allow merge commits = false`
    - `Allow rebase merging = false`
  - **合并后自动删除分支**：`Automatically delete head branches = true`

- **main 分支保护（Settings -> Branches -> Branch protection rules: main）**

  - `Require a pull request before merging = true`
  - `Require status checks to pass before merging = true`
    - Required checks：`required-checks`（由 `ci.yml` 的聚合 job 提供）
  - `Require branches to be up to date before merging = true`
  - `Do not allow bypassing the above settings = true`（管理员也不能绕过）
  - `Require linear history = true`（禁止 merge commit，保证线性历史）
  - `Require approvals = false`（避免因无人审核导致阻塞）

- **建议的日常 PR 流程**
  - 从 `main` 拉分支（如 `feat/...` / `fix/...` / `chore/...`）
  - Push 后创建 PR
  - 等待 CI 全绿（含 `required-checks` 与 `Type Check`）
  - 使用 **Squash and merge** 合并，合并后分支会自动删除

---

## 10. 常见问题（FAQ）

- **Windows 上 python/pip/uvicorn 启动异常**
  - 优先使用 `py -m pip ...` / `py -m uvicorn ...`。
- **生产环境 News AI 不跑**
  - `NEWS_AI_ENABLED=true` 才会启用周期任务。
  - `DEBUG=false` 且 Redis 不可用会禁用周期任务（检查 `REDIS_URL`）。
- **SystemConfig 写入被 400 拒绝**

  - 通常是触发了 secrets 拦截（例如 providers JSON 里写了 `api_key`）。

- **AI 咨询 PDF 报告接口返回 501**
  - 接口：`GET /api/ai/consultations/{session_id}/report`
  - 含义：当前运行的 Python 环境缺少 PDF 依赖（通常是 `reportlab`）。
  - 处理：确认你安装依赖的 Python 环境与运行后端的环境一致，并重新安装后端依赖（包含 `reportlab`）。

---

## 11. 接手 Checklist（建议照做）

- **先跑起来**
  - 本地 `backend + frontend` 启动，打开 Swagger 验证 `/health`。
- **跑测试**
  - 后端 `pytest`、前端 `npm run build`、必要时跑 E2E。
- **确认生产配置策略**
  - Secrets 注入方式（env / K8s Secret / ExternalSecrets）。
  - Redis 是否必须（生产建议必配）。
- **运维可观测性**
  - News AI：`/api/system/news-ai/status`。
  - AI 咨询（如有）：`/api/system/ai/status`（以 Swagger 为准）。

---

## 12. 文档与附录（已合并到本文）

本仓库的核心工程交接信息已收敛到 **本文件**。为减少文档分散、降低维护成本：

- 原 `docs/` 下的多份说明文档已统一归档到 `docs/_archive/`（默认保留用于追溯，必要时可清理）。
- 本节给出“合并后的摘要版附录”，覆盖接手工程师最常用的开发/运维/架构/API/变更信息。

---

### 12.1 开发指南（精简版）

- **后端启动**（Windows 建议优先用 `py -m ...`）：
  - 安装依赖：`py -m pip install -r backend/requirements.txt`
  - 启动：`py -m uvicorn app.main:app --reload --port 8000`（在 `backend/` 目录执行）
- **前端启动**：
  - 安装：`npm install`（在 `frontend/` 目录）
  - 启动：`npm run dev`（默认 `http://localhost:5173`）
- **Docker Compose**：
  - 开发：`docker compose up -d --build`
  - 生产示例：`docker compose -f docker-compose.prod.yml up -d --build`
- **测试**：
  - 后端：`py -m pytest -q`、类型：`py -m pyright`
  - 前端：`npm run build`、E2E：`npm run test:e2e`

---

### 12.2 架构与数据流（精简版）

- **整体**：`frontend(React)` -> `/api` -> `backend(FastAPI)` -> DB（SQLite/PG）/ Redis（生产推荐）/ ChromaDB（RAG）
- **路由聚合**：后端在 `app/main.py` 中挂载 `/api` 前缀；WebSocket 单独挂载。
- **生产关键约束**：
  - **Secrets 不入库**：`OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY` 等必须通过 env/Secret 注入。
  - **生产 News AI**：`DEBUG=false` 且 Redis 不可用时会禁用周期任务（避免多副本重复跑）。

---

### 12.3 常用 API 速查（精简版）

- **健康检查**：`GET /health`
- **登录**：`POST /api/user/login`（JWT 在 `token.access_token`）
- **AI 咨询**：`POST /api/ai/chat`、`POST /api/ai/chat/stream`
- **新闻消费**：`GET /api/news`、`GET /api/news/{id}`
- **News AI 运维**：`GET /api/system/news-ai/status`（管理员）
- **News AI 手动重跑**：`POST /api/news/admin/{news_id}/ai/rerun`（管理员）

---

### 12.4 生产部署与冒烟（摘要）

- **必须遵守**：Secrets（如 `OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET`）只能走环境变量/Secret Manager。
- **Redis（生产强烈建议）**：`DEBUG=false` 且 Redis 不可用会禁用定时任务/News AI pipeline。
- **冒烟脚本（News AI）**：
  - Windows：`../scripts/smoke-news-ai.ps1`
  - Linux/CI：`../scripts/smoke-news-ai.sh`
  - 逻辑：health -> status -> 创建新闻 -> AI rerun -> 轮询确认 -> 清理。

---

### 12.5 AI 咨询模块现状（要点）

- **核心能力**：同步与 SSE 流式聊天；会话与消息落库；支持 `session_id` 跨重启续聊（从 DB 注入最近历史）；权限校验（owner/admin）；游客配额（IP 维度）。
- **PDF 报告**：`GET /api/ai/consultations/{session_id}/report`；若缺少 PDF 依赖（如 `reportlab`）会返回 501。
- **运维接口**：`GET /api/system/ai/status`（管理员），用于查看 AI 模块就绪状态与最近错误趋势（以 Swagger 为准）。

---

### 12.6 更新记录（摘录）

- **2025-12-27**：落地“Secrets 不入库”、News AI 运维状态接口、`StaleDataError` 并发兜底、生产部署与冒烟 SOP。
- **2025-12-29**：News 模块发布（tag `news-module-20251229`）、补齐开发/架构/API 速查文档入口与测试结果记录。
- **2026-01-04**：Playwright E2E 全量回归全绿（73 passed）；新增/完善 E2E 稳定化手段（DEBUG 设置新闻 `view_count` 并清 hot cache、Settings tab 断言约定、ChatHistory 伪 JWT 工具 `makeE2eJwt()`）。
- **2026-01-06**：补齐律师结算/提现与商业化配额能力的交付口径；更新回归口径（pytest 95 passed、Playwright 76 passed、pyright/basedpyright 0）；并将部分已完成的过程文档归档到 `docs/_archive/`。

---

### 12.7 归档（历史文档）

为减少 `docs/` 根目录文件数、降低维护成本，下列文档已移到 `docs/_archive/` 目录保留：

- `_archive/ARCHITECTURE.md`
- `_archive/API_QUICK_REFERENCE.md`
- `_archive/PROD_DEPLOY_AND_SMOKE_SOP.md`
- `_archive/HANDOFF.md`
- `_archive/DEV_GUIDE.md`
- `_archive/AI_CONSULTATION_STATUS.md`
- `_archive/UPDATE_LOG.md`
- `_archive/反馈与建议.md`
- `_archive/律师结算功能需求说明书.md`
- `_archive/百姓法律助手商业化策略与定价方案.md`
- `_archive/甲方反馈.md`
- `_archive/甲方反馈回复.md`

---

### 12.8 前端布局与滚动约束（避免回归）

- **布局基线**：`frontend/src/components/Layout.tsx`
  - 根容器使用 `min-h-[100dvh] flex flex-col`（更适配移动端动态地址栏）
  - 内容区 `main` 必须是 `flex-1 min-h-0`，让子页面能在 flex 容器内正确滚动
- **Chat 页**：`frontend/src/pages/ChatPage.tsx`
  - 页面根容器应使用 `flex-1 min-h-0`，避免 `h-[calc(100vh-...)]` 这类“魔法高度”导致的双滚动/高度不准
  - 消息列表区域通过内部 `overflow-y-auto` 实现滚动
- **Modal 层级**：`frontend/src/components/ui/Modal.tsx`
  - 默认 `zIndexClass` 需要高于 sticky header / mobile nav（避免弹窗被遮挡）

---

## 13. 业务体验提升路线图（优先）

本节只关注“用户能感知到的体验提升”（增长/留存/转化/验收最直接），不把架构演进作为当前主线。

### 13.1 体验提升的优先级原则（建议）

- **先抓关键路径**：注册/登录 → 首页/搜索 → AI 咨询 → 下单/支付/订单 → 评价/分享/复用。
- **先降摩擦再加功能**：先把错误提示、加载状态、空状态、引导与可恢复操作做扎实。
- **先让用户“看得懂、信得过”**：结果结构化（要点/依据/风险提示）、引用来源、免责声明与“下一步建议”。

---

### 13.2 P0（1-2 周）：体验快速见效（建议做成一次冲刺）

#### 13.2.1 AI 咨询体验（用户侧最核心）

- **咨询结果结构化展示（不改变后端核心逻辑）**

  - 目标：让用户 10 秒内理解答复。
  - 建议前端约定统一渲染结构：
    - `结论` / `要点` / `建议操作` / `风险提示` / `可能依据（如有）`
  - **验收标准**：同一条回复在移动端不需要频繁滚动也能看到“结论+要点”。

- **生成过程的体验补齐**

  - 明确“正在生成/已完成/失败可重试”的状态。
  - 失败时给出可行动提示：网络问题、配额不足、服务繁忙（并提供重试按钮）。
  - **验收标准**：SSE 断流/超时时 UI 不会卡死；用户能一键重试或回到输入框继续。

- **咨询复用能力（提升留存）**
  - 对“复制/收藏/评价/分享”入口做统一工具条（当前有部分能力，但建议体验统一）。
  - 提供 3-5 个“常见追问”快捷按钮（例如：所需证据、时效、费用、下一步怎么做）。
  - **验收标准**：用户能在 3 秒内完成复制或继续追问。

#### 13.2.2 登录/注册与合规引导（降低新手流失）

- **登录/注册错误提示统一**

  - 表单校验提示尽量“就地显示”，避免用户不知道哪里错了。
  - **验收标准**：输入错误时页面不跳、不弹 500，提示清晰（密码格式/邮箱/验证码等）。

- **合规文本与 AI 免责声明体验**
  - 注册时“已阅读并同意”的勾选项与文案保持一致；提供“快速查看摘要 + 查看全文”。
  - **验收标准**：验收人员可以清晰复核“同意链路”与版本记录。

#### 13.2.3 新闻/论坛消费体验（内容侧留存）

- **阅读体验与弱网优化**

  - 列表/详情骨架屏、图片加载兜底、空状态文案统一。
  - **验收标准**：首屏加载有反馈（骨架/加载中），不会出现长时间白屏。

- **收藏/评论/订阅的“闭环反馈”**
  - 收藏/取消收藏、评论成功后给明确提示与可撤销。
  - **验收标准**：用户操作后能立即看到状态变化，不需要刷新。

#### 13.2.4 订单/支付链路体验（转化与验收关键）

- **订单状态解释与下一步指引**

  - 每个状态给出说明（待支付/已支付/已完成/已退款/已取消）+ 下一步按钮。
  - **验收标准**：验收人员不看接口文档也能理解订单当前处于哪个阶段、下一步怎么操作。

- **失败可恢复**
  - 支付失败/取消后能回到订单继续支付；退款状态有进度说明。
  - **验收标准**：不会出现“支付失败后不知道去哪里”的断点。

---

### 13.3 P1（1 个月）：体验增强与运营效率提升

#### 13.3.1 AI 咨询：质量感与信任感

- **“引用/依据”能力逐步上线（轻量版）**

  - 即便不做完整 RAG，也可以先在前端展示“可能依据/参考方向”（如法律条文标题、关键词），并明确“仅供参考”。
  - **验收标准**：用户能在回答中看到“为什么这么说/参考什么”。

- **咨询历史检索与整理**

  - 对话列表支持搜索（关键词/时间）；支持“一键生成本次咨询摘要”（可复用已有 AI 能力）。
  - **验收标准**：用户能快速找回历史咨询并复用结论。

#### 13.3.2 内容运营：News/RSS/AI 的体验化

- **新闻来源健康度展示（面向运营/管理员）**

  - 管理端能看到来源最近成功率/最近错误，便于及时处理。
  - **验收标准**：运营能在 1 分钟内定位“哪一个源在拖后腿”。

- **News AI 的“批量运营”**
  - 支持按专题/来源批量触发 AI 标注、批量回填。
  - **验收标准**：运营不用逐条点新闻也能完成一批内容的 AI 加工。

#### 13.3.3 商业化体验（不先做复杂架构）

- **配额/权益展示更直观**
  - 在咨询/文书入口显示：今日剩余、次数包剩余、VIP 到期时间与购买入口。
  - **验收标准**：用户不需要进入设置页也能理解自己还能用多少。

---

### 13.4 技术类建议（后置，不作为当前主线）

- **生产建议**：生产推荐使用 `Postgres + Redis`；SQLite 仅用于本地/演示。
- **可观测性**：后续可逐步补齐结构化日志、基础指标与任务运行状态，但不应挤占 P0 体验冲刺。

---

### 13.5 2 周体验冲刺：任务拆解模板（推荐直接照抄开任务）

#### 13.5.1 单个任务模板

- **目标用户**：游客 / 普通用户 / 律师 / 管理员
- **所在关键路径**：注册/登录 / AI 咨询 / 新闻/论坛 / 下单支付 / 订单售后
- **问题描述（现状）**：
- **期望体验（用户视角）**：
- **范围（页面）**：例如 `frontend/src/pages/ChatPage.tsx`
- **范围（接口）**：例如 `POST /api/ai/chat/stream`
- **交互细节**：加载/空/错误/重试/可撤销
- **验收标准（必须可点检）**：
  - 文案：是否清晰（能指导下一步）
  - 状态：是否可恢复（失败能重试）
  - 性能：首屏/关键操作是否有反馈（骨架/按钮 loading）
  - 移动端：是否可用（不遮挡、不抖动）
- **数据与埋点（可选）**：曝光/点击/转化/失败原因（先记日志也可）
- **回归用例**：对应 E2E/手工用例列表

#### 13.5.2 2 周冲刺建议拆法

- **第 1 周：先做“降摩擦”**

  - 目标：把关键路径上的“卡死/不知道怎么办/需要刷新”全部清掉。
  - 输出：统一的加载/空/错误/重试体验 + 关键按钮状态。

- **第 2 周：再做“增信任与复用”**
  - 目标：让结果更结构化、更可信、更容易复用（复制/收藏/分享/继续追问）。
  - 输出：AI 答复结构化卡片、常见追问、历史检索/摘要等。
