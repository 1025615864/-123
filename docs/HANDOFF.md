# 项目交接文档（百姓助手 / 新闻模块 + News AI）

> 目标：把当前项目的关键模块、运行方式、生产配置、News AI 工作机制、测试与运维手段一次性交接给下一位同事。
>
> 适用范围：本仓库（`backend/` + `frontend/`）。

---

## 1. 当前项目状态（结论）

- **新闻模块 + News AI 已完成并达到“可生产运行”的工程状态**。

发布信息：

- Tag：`news-module-20251229`
- GitHub Release：`https://github.com/1025615864/-123/releases/tag/news-module-20251229`
- 已落地的生产就绪工作包含：
  - **Secrets 不入库**（SystemConfig 拦截敏感字段；providers JSON/B64 禁止包含 `api_key`）。
  - **News AI provider 缺省 `api_key` 时可走 env 回退**（方案 A：统一使用 `OPENAI_API_KEY`）。
  - 前端管理后台设置页与后端策略对齐（不再写入/展示 API Key）。
  - 后端单测与前端 Playwright E2E 均通过。

---

## 2. 代码结构与关键入口

### 2.1 主要目录

- `backend/`
  - `app/main.py`：FastAPI 应用入口；生命周期 `lifespan` 内启动周期任务（定时新闻、RSS ingest、News AI pipeline）。
  - `app/config.py`：环境变量配置（Pydantic Settings）。
  - `app/routers/`：API 路由（含 `news.py`、`system.py` 等）。
  - `app/services/`：业务服务（含 `news_service.py`、`news_ai_pipeline_service.py` 等）。
  - `tests/`：pytest 单测。
- `frontend/`
  - `src/pages/admin/SettingsPage.tsx`：管理后台系统设置与 News AI 运维入口。
  - `tests/e2e/`：Playwright E2E。
- `docs/`
  - `PROD_DEPLOY_AND_SMOKE_SOP.md`：生产部署参数清单 + 一键冒烟。
  - `UPDATE_LOG.md`：更新记录。

### 2.2 关键后端模块

- **SystemConfig 与 Secrets 管理**：`backend/app/routers/system.py`
  - 更新 SystemConfig 时会对请求 payload 做“敏感信息拦截”。
  - 对 News AI providers 的 JSON/B64 配置做“包含 `api_key` 字段即拒绝”校验。
- **News AI pipeline**：`backend/app/services/news_ai_pipeline_service.py`
  - 周期任务：自动处理新闻并写入 AI 标注字段。
  - Provider 策略：priority/round_robin/random + failover。
  - `response_format`：`json_object/json_schema`，供应商不支持时 400/422 自动回退重试。
- **新闻服务**：`backend/app/services/news_service.py`
  - 管理后台操作（发布/置顶/审核/删除/专题等）。
  - 负责删除新闻时联动清理 AI 标注（避免 SQLite id 复用带来的旧标注污染）。
- **新闻更新并发兜底**：`backend/app/routers/news.py`
  - `PUT /api/news/{news_id}` 捕获 `StaleDataError`，回滚后刷新对象并重试一次；仍失败返回 409。

---

## 3. News AI 到底“有什么用”（业务价值）

News AI 的核心是：让新闻在进入系统后具备结构化“可运营、可检索、可风控”的标签与摘要。

- **用户体验**
  - 自动生成摘要（`summary`），帮助用户快速理解新闻。
  - 自动生成要点/关键词（`highlights` / `keywords`），提高可读性与信息获取效率。
- **运营与内容管理**
  - 关键词可用于推荐、专题聚合、标签展示。
  - 高风险新闻可通过风险等级（`risk_level`）做后台筛选与审核提醒。
- **工程与可观测性**
  - 有错误追踪字段（`retry_count/last_error/last_error_at`）
  - 有管理员状态接口与后台运维 UI（查看积压、错误趋势、配置是否生效）。

---

## 4. News AI 在项目里如何工作（数据流）

### 4.1 触发方式

- **周期任务自动跑批**（生产建议）：
  - `NEWS_AI_ENABLED=true` 开启。
  - `NEWS_AI_INTERVAL_SECONDS` 控制周期（默认 120s）。
- **管理员手动重跑**：
  - `POST /api/news/admin/{news_id}/ai/rerun`
  - 用于单条新闻 AI 结果异常、切换 provider 后立即重算等场景。

### 4.2 处理逻辑（简化版）

1. pipeline 找到需要处理的新闻（未处理/字段不完整/需要重算的情况）。
2. 根据 provider 列表 + 策略（priority/round_robin/random）选择 provider。
3. 调用 OpenAI-compat `/chat/completions`：
   - 支持 `response_format`（json_object/json_schema），不支持时自动回退。
4. 解析并写入 `NewsAIAnnotation`（以及新闻详情/列表接口会带上相应字段）。

补充：

- 当 LLM 被关闭或不可用时，后端会走本地兜底生成摘要/要点/关键词，尽量保证 `highlights/keywords` 不为空（提升可用性与 E2E 稳定性）。

### 4.3 关键接口（运维/排障必看）

- `GET /api/system/news-ai/status`（管理员）
  - 返回：providers（脱敏）、策略、response_format、积压量、错误趋势、最近错误等。

---

## 5. 配置方式（env + SystemConfig）

### 5.1 环境变量（env / Secret）

> 生产环境建议由 Secret Manager 注入。

- `DEBUG=false`
- `DATABASE_URL`
- `JWT_SECRET_KEY` 或 `SECRET_KEY`
- `PAYMENT_WEBHOOK_SECRET`
- `REDIS_URL`（生产强烈建议）
- `OPENAI_API_KEY`（**必须** env/Secret 注入）
- `OPENAI_BASE_URL`（可选；默认 `https://api.openai.com/v1`）
- `AI_MODEL`（可选；默认 `deepseek-chat`）

### 5.2 SystemConfig（运行时热更新）

> 适合做“开关、策略、非敏感参数”。

- 可写入（示例）：
  - `NEWS_AI_SUMMARY_LLM_ENABLED`
  - `NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY`
  - `NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT`
  - `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON` / `NEWS_AI_SUMMARY_LLM_PROVIDERS_B64`

### 5.3 Secrets 禁止写入 SystemConfig（N2）

- 禁止写入：
  - `openai_api_key` / `OPENAI_API_KEY`
  - 任意 key 名包含：`secret/password/api_key/apikey/private_key` 且 value 非空
  - providers JSON/B64 内出现 `api_key/apikey`

### 5.4 providers JSON（方案 A 推荐写法）

- providers JSON **不写** `api_key`：
  - 鉴权统一由 `OPENAI_API_KEY`（env/Secret）提供。

---

## 6. 生产环境运行关键点（非常重要）

### 6.1 Redis 与“只跑一次”问题

- 在 `DEBUG=false` 且 **Redis 不可用** 时：
  - 定时新闻任务、RSS ingest、News AI pipeline 会被禁用。
- 原因：避免多副本部署时无锁导致重复执行。

结论：**生产要用 News AI pipeline，必须配置可用 Redis（`REDIS_URL`）并保证连通。**

### 6.2 生产部署与冒烟

- 生产部署参数清单与一键冒烟脚本见：
  - `docs/PROD_DEPLOY_AND_SMOKE_SOP.md`

---

## 7. 测试与验证（当前已通过）

- **后端**：pytest
  - 命令：`py -m pytest -q`
  - 结果：`42 passed`
- **前端 E2E**：Playwright
  - 命令：`npm run test:e2e`
  - 结果：`51 passed`

E2E 关键点：

- Playwright 配置会自动拉起后端与前端 dev server（端口隔离，避免串线）。

E2E 历史不稳定问题（已修复）：

- SQLite 可能复用已删除新闻的 `id`，导致残留的 `NewsAIAnnotation` 被错误复用。
- 修复思路：
  - 删除新闻时联动删除 AI 标注。
  - pipeline 选取待处理条件增强：`highlights/keywords` 不完整也视为待处理。

---

## 8. 文档变更说明（给接手者）

- 已新增：
  - `docs/PROD_DEPLOY_AND_SMOKE_SOP.md`
  - `docs/UPDATE_LOG.md`

---

## 9. 常见问题排查（按频率）

- **News AI 不跑**
  - 检查 `DEBUG=false` 时 Redis 是否连接（`REDIS_URL`）
  - 检查 `NEWS_AI_ENABLED=true`
- **provider 不支持 `response_format`**
  - 已实现 400/422 自动回退重试；可把 `NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT` 设为 `off` 临时规避
- **SystemConfig 写入被拒绝**
  - 多半是触发了 secrets 拦截（例如 providers JSON 里写了 `api_key`）
  - 正确做法：把 key 放到 `OPENAI_API_KEY`（env/Secret）

---

## 10. 接手建议（下一步工作建议）

- **部署侧**：把 `docs/PROD_DEPLOY_AND_SMOKE_SOP.md` 的冒烟脚本落地到 CI（staging/post-deploy）。
- **产品侧**：确认生产 provider（base_url/model）以及 response_format 支持程度（已有自动回退，但仍建议在真实供应商冒烟）。
- **工程侧**（可选）：
  - 将数据库演进从“运行时补列”逐步迁移到 Alembic（尤其是生产 Postgres）。

---

## 11. 快速索引

- 生产部署与冒烟：`PROD_DEPLOY_AND_SMOKE_SOP.md`
- 更新记录：`UPDATE_LOG.md`
- 交接附录：API 速查：`API_QUICK_REFERENCE.md`
- GitHub Actions（CI 主流程）：`../.github/workflows/ci.yml`
- Branch Protection：Required Status Checks 里勾选 `required-checks`（使 `helm-validate`/`helm lint` 成为必需门禁）
- Helm Chart（K8s 部署）：`../helm/baixing-assistant`
- Helm Chart 说明：`../helm/baixing-assistant/README.md`
- GitHub Secrets（部署后冒烟所需）：`BASE_URL`、`ADMIN_TOKEN`
- docker-compose（开发）：`../docker-compose.yml`
- docker-compose（生产示例）：`../docker-compose.prod.yml`
- Helm values 示例（生产占位符）：`../helm/baixing-assistant/values.prod.example.yaml`
- Helm values 示例（ExternalSecrets 占位符）：`../helm/baixing-assistant/values.externalsecret.example.yaml`
- Helm values 示例（redis/postgresql 子 chart 占位符）：`../helm/baixing-assistant/values.subcharts.example.yaml`
- 一键冒烟脚本（Windows）：`../scripts/smoke-news-ai.ps1`
- 一键冒烟脚本（Linux/CI）：`../scripts/smoke-news-ai.sh`
- 冒烟脚本说明：`../scripts/README.md`
- 后端说明：`../backend/README.md`
