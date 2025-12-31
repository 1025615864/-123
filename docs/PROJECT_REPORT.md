# 项目报告（百姓法律助手 / 百姓助手）

更新时间：2025-12-31

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
- **AI 相关**
  - `OPENAI_API_KEY`
  - `OPENAI_BASE_URL`（可选）
  - `AI_MODEL`（可选）

### 4.3 前端关键环境变量

- `VITE_API_BASE_URL`
  - 本地开发通常为 `/api`（由 Vite proxy / Ingress / Nginx 转发到后端）。

---

## 5. 本地启动（开发）

### 5.1 后端

- 在 `backend/` 下复制示例：`backend/env.example` -> `backend/.env`
- 创建虚拟环境并安装依赖

说明：Windows 环境如果 `python` 指向 WindowsApps stub，建议使用 `py -m ...`。

启动：

- `python -m uvicorn app.main:app --reload --port 8000`

验证：

- `GET http://localhost:8000/health`
- Swagger：`http://localhost:8000/docs`

### 5.2 前端

- `npm install`
- `npm run dev`

访问：`http://localhost:5173`

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

生产注意：

- 周期 pipeline 由 `NEWS_AI_ENABLED=true` 启用。
- `DEBUG=false` 且 Redis 不可用时，周期任务会被禁用（避免多副本重复执行）。

### 7.4 论坛与审核（/api/forum）

- 帖子/评论 CRUD
- 管理端审核与内容治理

### 7.5 支付与订单（/api/payment）

- 订单创建/支付/取消/退款
- 回调验签依赖 `PAYMENT_WEBHOOK_SECRET`

---

## 8. 测试与质量门禁

### 8.1 后端

- 单测：`py -m pytest -q`
- 类型检查：`py -m pyright`

### 8.2 前端

- build：`npm run build`
- E2E：`npm run test:e2e`
  - Playwright 默认会用隔离端口拉起后端/前端 dev server（避免与本地开发端口冲突）。

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

---

## 10. 常见问题（FAQ）

- **Windows 上 python/pip/uvicorn 启动异常**
  - 优先使用 `py -m pip ...` / `py -m uvicorn ...`。
  - 中文路径下 `.venv\Scripts\uvicorn.exe` launcher 可能失败，使用 `python -m uvicorn ...` 规避。
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

- 原 `docs/` 下的多份说明文档已统一归档到 `docs/_archive/`（不删除，仅供追溯）。
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
