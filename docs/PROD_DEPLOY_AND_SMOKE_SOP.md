# 生产部署参数清单 + 一键冒烟 SOP

> 目的：把“News / News AI 的配置与线上冒烟清单”落到“可部署、可验证、可复用”的运维流程。
>
> 适用范围：百姓法律助手（backend + frontend）生产发布；重点覆盖 News / News AI。

---

## 0. 关键原则（务必遵守）

### 0.1 Secrets 不入库（N2）

- `OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET`、Redis 密码等 **必须** 用环境变量/Secret Manager 注入。
- **禁止**把任何 API Key/secret 写入 SystemConfig（管理后台“系统设置”）。
- 后端已实现硬拦截：
  - 若写入 key 包含 `secret/password/api_key/apikey/private_key` 等敏感 token，会直接返回 400。
  - 若写入 `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON/B64` 且 JSON 内出现 `api_key/apikey` 字段，会直接返回 400。

### 0.2 News AI 在生产的“分布式锁”要求

- 在 `DEBUG=false` 且 **Redis 未连接** 时：
  - 定时新闻任务（scheduled news）会被禁用
  - RSS ingest 会被禁用
  - News AI pipeline 会被禁用

因此：**生产想启用 News AI 定时 pipeline，必须配置可用的 `REDIS_URL` 并保证连通。**

---

## 1. 生产部署参数清单（Backend）

> 来源依据：`backend/app/config.py`、`backend/app/main.py`、`backend/env.example`、`env.example.txt`

### 1.1 必填（生产）

- `DEBUG=false`

  - 生产必须关闭 debug。

- `DATABASE_URL`

  - 示例（Postgres）：
    - `postgresql+asyncpg://<user>:<pass>@<host>:5432/<db>`
  - 注意：默认值是 sqlite，本地可用；生产建议 Postgres。

- `JWT_SECRET_KEY` 或 `SECRET_KEY`

  - 二者等价（后端用 `AliasChoices("SECRET_KEY", "JWT_SECRET_KEY")` 读取）。
  - 要求：`DEBUG=false` 时必须安全（长度>=32 且不可用默认值）。

- `PAYMENT_WEBHOOK_SECRET`
  - `DEBUG=false` 时强制要求设置（长度>=16）。

### 1.2 强烈推荐（生产）

- `REDIS_URL`

  - 不填会导致生产禁用定时任务/News AI pipeline。
  - 示例：
    - `redis://:<password>@<host>:6379/0`

- `CORS_ALLOW_ORIGINS`

  - 逗号分隔。
  - 示例：`https://yourdomain.com,https://admin.yourdomain.com`

- `FRONTEND_BASE_URL`

  - 用于生成前端链接/通知 deep link（如你项目里有相关逻辑）。

- `TRUSTED_PROXIES`
  - 反代/网关部署（如 Nginx/Ingress）时建议配置。

### 1.3 AI（生产）

- `OPENAI_API_KEY`（Secret）

  - **必须**通过 Secret/env 注入。

- `OPENAI_BASE_URL`

  - 默认：`https://api.openai.com/v1`
  - 可切换为兼容 OpenAI 的供应商（例如 DeepSeek 等）。

- `AI_MODEL`
  - 默认：`deepseek-chat`（见 `backend/app/config.py`）。

### 1.4 News AI pipeline 调度（env）

- `NEWS_AI_ENABLED`

  - `true/1/on/yes`：启用周期任务
  - 生产注意：`DEBUG=false` 且 Redis 未连接会被强制关闭。

- `NEWS_AI_INTERVAL_SECONDS`

  - 默认 `120`

- （可选）RSS ingest：
  - `RSS_FEEDS`（非空即启用）
  - `RSS_INGEST_INTERVAL_SECONDS`（默认 `300`）

---

## 2. 生产部署参数清单（Frontend）

### 2.1 必填

- `VITE_API_BASE_URL`
  - 通常为 `/api`（由 Nginx/网关转发到后端）。

### 2.2 推荐

- 建议部署时由网关统一处理：
  - `/api` -> backend
  - `/ws`（若有 websocket）-> backend

---

## 3. News AI 运行时配置（SystemConfig，可热更新）

> 配置入口：管理后台 -> 系统设置

### 3.1 可写入 SystemConfig（推荐用 SystemConfig 做运维开关/调参）

- `NEWS_AI_SUMMARY_LLM_ENABLED`

  - `true/1/on/yes` 启用 LLM 摘要
  - `false/0/off/no` 禁用（走本地兜底生成）

- `NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY`

  - `priority` / `round_robin` / `random`

- `NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT`

  - `json_object` / `json_schema`
  - 关闭：`0/off/none/disable/disabled`

- `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON` 或 `NEWS_AI_SUMMARY_LLM_PROVIDERS_B64`

  - **允许写入，但有硬约束**：JSON 内不得包含 `api_key/apikey`。
  - 方案 A：鉴权统一用 `OPENAI_API_KEY`（env/Secret）。

- 运行参数（按需）：
  - `NEWS_AI_BATCH_SIZE`
  - `NEWS_AI_SUMMARY_LLM_TIMEOUT_SECONDS`
  - `NEWS_AI_LAST_ERROR_MAX_CHARS`
  - `NEWS_AI_SUMMARY_LLM_HIGHLIGHTS_MAX` / `NEWS_AI_SUMMARY_LLM_KEYWORDS_MAX` / `NEWS_AI_SUMMARY_LLM_ITEM_MAX_CHARS`

### 3.2 禁止写入 SystemConfig（会被 400 拒绝）

- `openai_api_key` / `OPENAI_API_KEY`
- 任意 key 名包含：`secret/password/api_key/apikey/private_key`（且 value 非空）
- providers JSON/B64 中包含 `api_key/apikey` 字段

---

## 4. CI/CD 运维 SOP（发布流程建议）

> 你可以把本节直接落到 GitHub Actions / Jenkins / ArgoCD 的“发布前检查”。

### 4.1 发布前（Preflight）

- 确认 Secret/环境变量已在生产环境配置：

  - `DATABASE_URL`
  - `JWT_SECRET_KEY` 或 `SECRET_KEY`
  - `PAYMENT_WEBHOOK_SECRET`
  - `REDIS_URL`
  - `OPENAI_API_KEY`
  - （可选）`OPENAI_BASE_URL`、`AI_MODEL`

- 确认后端启动参数：

  - `DEBUG=false`

- 确认数据库迁移/自动补列策略：
  - 项目对 SQLite 有自动补列逻辑；生产 Postgres 建议仍采用显式迁移（如果你后续引入 Alembic）。

### 4.2 发布后（Post-deploy）

- 运行“一键冒烟”脚本（见第 5 节）
- 管理后台检查：
  - Settings -> 新闻 AI 运维卡片是否正常显示
  - `/api/system/news-ai/status` 中 pending/errors 指标是否正常

---

## 5. 一键冒烟（Smoke Test）

### 5.1 准备

你需要：

- `BASE_URL`：例如 `https://yourdomain.com`
- `ADMIN_TOKEN`：管理员 JWT

> 获取管理员 token 的方式：登录管理后台或调用登录接口 `/api/user/login`。

推荐：使用仓库内的可执行脚本（比复制粘贴更稳定、也更适合 CI）：

- Windows：`../scripts/smoke-news-ai.ps1`
- Linux/CI：`../scripts/smoke-news-ai.sh`
- 参数说明：`../scripts/README.md`

#### 5.1.1 关键接口

- 健康检查：`GET {BASE_URL}/health`
- News AI 状态：`GET {BASE_URL}/api/system/news-ai/status`
- 创建新闻：`POST {BASE_URL}/api/news`（管理员）
- 管理员详情：`GET {BASE_URL}/api/news/admin/{id}`（管理员）
- 手动重跑 AI：`POST {BASE_URL}/api/news/admin/{id}/ai/rerun`（管理员）
- 删除新闻：`DELETE {BASE_URL}/api/news/{id}`（管理员）

### 5.2 推荐：直接运行仓库脚本（Windows / PowerShell）

```powershell
./scripts/smoke-news-ai.ps1 -BaseUrl "https://yourdomain.com" -AdminToken "<ADMIN_TOKEN>"
```

### 5.3 推荐：直接运行仓库脚本（Linux / CI）

```bash
chmod +x ./scripts/smoke-news-ai.sh

BASE_URL="https://yourdomain.com" \
ADMIN_TOKEN="<ADMIN_TOKEN>" \
./scripts/smoke-news-ai.sh
```

脚本参数说明与常见排障见：`../scripts/README.md`

（提示：本文位于 `docs/` 目录，脚本实际路径在仓库根目录 `scripts/` 下。）

---

## 6. 常见失败与处理（运维视角）

- **`/api/system/news-ai/status` 访问 403**

  - 需要管理员 token。

- **生产环境 News AI 不跑**

  - 检查 `DEBUG=false` 时 Redis 是否连接成功（必须配置 `REDIS_URL`）。
  - 检查 `NEWS_AI_ENABLED` 是否开启。

- **provider 不支持 response_format**

  - 已实现 400/422 自动回退重试（不带 response_format）。

- **误把 api_key 写进 SystemConfig**
  - 后端会返回 400；正确做法是把 key 放到 `OPENAI_API_KEY`（env/Secret）。

---

## 7. 建议你在 CI/CD 里落地的最小检查项

- 后端：`py -m pytest`
- 前端：`npm run build`
- E2E（可选但推荐 pre-prod/staging）：`npm run test:e2e`
- 部署后：跑本 SOP 的“一键冒烟”脚本（PowerShell 或 bash）
