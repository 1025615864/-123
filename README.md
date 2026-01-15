# 百姓法律助手

百姓法律助手是一个**前后端一体**的法律服务产品仓库（`backend/` + `frontend/`），目标是把“AI 法律咨询 + 内容资讯 + 社区互动 + 律师服务 + 支付结算 + 通知实时触达”串成一套可落地、可运维、可持续迭代的系统。

如果你是：

- 想快速理解项目全貌并开始贡献的开发者
- 想部署并运营一套具备支付/结算/风控能力的法律类应用的团队

你应该从本 README 开始。

---

## Quick Links（先看这几个就够）

- 架构总览：`docs/ARCHITECTURE.md`
- 模块索引（开发者视角）：`docs/modules/INDEX.md`
- 数据模型：`docs/DATA_MODEL.md`
- 端到端数据流（请求 → DB → 通知/WS → 前端刷新）：`docs/modules/DATA_FLOWS.md`
- API 速查：`docs/guides/API_QUICK_REFERENCE.md`
- 开发指南：`docs/guides/DEV_GUIDE.md`
- 配置参考（env + SystemConfig）：`docs/guides/CONFIG_REFERENCE.md`
- 排障手册：`docs/guides/TROUBLESHOOTING.md`

---

## 核心能力（你会在系统里看到什么）

- AI 法律咨询与会话管理（含导出/分享等工具链）
- 新闻资讯（RSS 采集、热点缓存、News AI 标注/风控/去重）
- 社区论坛（帖子/评论、敏感词与审核、批量审核）
- 律所/律师信息、预约咨询、咨询消息
- 支付与结算（回调审计、对账诊断、提现审批与分摊）
- 通知中心 + WebSocket 实时消息
- 管理后台（统计、系统配置、导出与运维接口）

---

## 技术栈与边界

- 后端：FastAPI + async SQLAlchemy（见 `backend/`）
- 前端：Vite + React + React Query（见 `frontend/`）
- 部署：Helm Chart（`helm/baixing-assistant/`）+ Docker Compose 示例（根目录）

关键约定：

- REST API 前缀：`/api`
- WebSocket 入口：`/ws`（**不在** `/api` 下）

---

## 2 分钟 Quick Start（本地开发：推荐）

### 1) 前置要求

- Python 3.11（建议与 CI 对齐）
- Node.js 20（建议与 CI 对齐）
- Windows PowerShell（仓库自带 `start-dev.ps1`，推荐 Windows 开发直接用）

### 2) 一键启动（Windows / 推荐）

在仓库根目录执行：

- `./start-dev.ps1`

脚本会自动完成：

- 在 `backend/.venv` 创建虚拟环境并安装 `backend/requirements.txt`
- 在 `frontend/` 安装 npm 依赖（若 `node_modules` 不存在）
- 启动后端：`uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
- 启动前端：`vite dev --host 127.0.0.1 --port 5173`

启动后访问：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`
- OpenAPI：`http://127.0.0.1:8000/docs`
- WebSocket：`ws://127.0.0.1:8000/ws`

### 3) 环境变量（本地）

后端会自动尝试加载：

- `backend/.env`
- 或仓库根 `.env`

也可以用 `ENV_FILE` 指定 env 文件路径。

示例文件：

- `env.example.txt`（仓库根）
- `backend/env.example`（后端更完整）

本地开发一般只需要：

- `DEBUG=true`（默认测试/开发模式）

可选但推荐：

- `JWT_SECRET_KEY=<任意字符串>`

如需启用 AI / 语音转写：

- `OPENAI_API_KEY=...`

---

## API / WebSocket 关键约定

### Envelope 响应包装（前端默认开启）

前端请求默认携带：

- `X-Api-Envelope: 1`

后端会将 **2xx JSON** 响应包装为：

- `{"ok": true, "data": <原始响应>, "ts": <unix_ts>}`

浏览器端 axios 拦截器会自动把 `response.data` 解包为 `data`。

---

## 数据库与迁移

- 默认数据库：SQLite（`sqlite+aiosqlite:///./data/app.db`）
- 生产建议：PostgreSQL（见 `docker-compose.prod.yml` / Helm values）

迁移策略：

- 当 `DEBUG=false` 时，后端启动会要求数据库处于 Alembic head（否则启动失败）
- 可用 `python backend/scripts/alembic_cmd.py upgrade head` 执行迁移
  - 若 Windows 环境 `python` 不可用，可尝试用 `py` 执行
- 本地想临时跳过 Alembic 校验可设置 `DB_ALLOW_RUNTIME_DDL=1`（不建议在生产使用）

---

## Docker Compose

- 本地 compose：`docker-compose.yml`（含 Postgres、backend、frontend）
- 生产示例：`docker-compose.prod.yml`（含 Postgres、Redis、backend、frontend）

注意：生产模式（`DEBUG=false`）必须提供：

- `JWT_SECRET_KEY`（长度 >= 32，且不能使用默认值）
- `PAYMENT_WEBHOOK_SECRET`（长度 >= 16）
- `REDIS_URL`（且 Redis 可连通）

---

## 测试与质量门禁

- 后端：`pytest backend/tests/ -v`
- 前端：`npm --prefix frontend run build`
- E2E：`npm --prefix frontend run test:e2e`
- 预提交：`pre-commit install`（见 `.pre-commit-config.yaml`）

---

## 仓库结构（你应该从哪里开始读）

- `backend/`：FastAPI 应用与业务服务
- `frontend/`：React 应用
- `docs/`：文档中心（架构、数据模型、模块、运维、排障）
- `helm/baixing-assistant/`：Kubernetes Helm Chart（backend + frontend + ingress）
- `start-dev.ps1` / `start-dev.cmd`：本地开发启动脚本

---

## 文档入口（面向新开发者）

- 架构：`docs/ARCHITECTURE.md`
- 数据库：`docs/DATABASE.md`
- 数据模型：`docs/DATA_MODEL.md`
- 模块文档（开发者视角）：`docs/modules/INDEX.md`
- 开发指南：`docs/guides/DEV_GUIDE.md`
- API 速查：`docs/guides/API_QUICK_REFERENCE.md`
- 运维与发布：`docs/guides/OPERATIONS.md`
- 配置参考（env + SystemConfig）：`docs/guides/CONFIG_REFERENCE.md`
- 排障手册：`docs/guides/TROUBLESHOOTING.md`
- 贡献指南：`docs/CONTRIBUTING.md`
- 变更记录：`docs/CHANGELOG.md`

---

## 任务与迭代记录

- 入口索引：`TASKS.md`
- 当前迭代：`TASKS_NEXT.md`
- 历史快照：`docs/_archive/`
