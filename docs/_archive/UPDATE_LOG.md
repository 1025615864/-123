# 更新记录（Update Log）

> 用途：记录关键功能变更、配置策略调整、测试结果与运维文档入口，便于后续追溯。

---

## 2025-12-27

### 1. 生产就绪：Secrets 管理（N2）

- **策略**：Secrets（尤其是 API Key）不允许通过 SystemConfig 入库；必须使用部署环境变量 / Secret Manager。
- **后端强制拦截**：SystemConfig 写入时若出现敏感字段（例如 `api_key/openai_api_key/password/secret/private_key` 等）会返回 400。
- **providers 配置（方案 A）**：
  - `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON/B64` 允许不包含 `api_key`。
  - 运行时鉴权统一使用 `OPENAI_API_KEY`（env/Secret）。
  - 若 providers JSON/B64 内出现 `api_key/apikey` 字段，会被拒绝写入（400）。

### 2. News AI：运行时配置与运维能力

- **运维状态接口（管理员）**：`GET /api/system/news-ai/status`
  - 返回当前生效 provider 配置（脱敏）、策略、response_format、积压量、错误趋势等。
- **管理员手动重跑**：`POST /api/news/admin/{news_id}/ai/rerun`

### 3. 并发/一致性兜底：处理 `StaleDataError`

- **问题**：Playwright E2E 日志中曾出现 `sqlalchemy.orm.exc.StaleDataError`（UPDATE 影响行数为 0）。
- **修复**：在 `PUT /api/news/{news_id}`（管理员更新新闻）接口中：
  - 捕获 `StaleDataError` -> `rollback` -> 重新加载最新新闻对象 -> **重试一次**。
  - 仍失败返回 `409 CONFLICT`；若记录已不存在返回 `404`。
  - 目的：避免线上出现 500 堆栈噪音，并对并发修改给出明确语义。

### 4. 运维文档

- 新增：`docs/PROD_DEPLOY_AND_SMOKE_SOP.md`
  - 生产部署参数清单（Backend/Frontend/DB/Redis/News AI）
  - 一键冒烟脚本（PowerShell + bash）：health/status/创建新闻/AI rerun/轮询校验/清理

### 5. README 更新

- 更新：`backend/README.md`
  - 与当前后端实际模块对齐（用户/论坛/新闻/系统/News AI）
  - 强调生产配置要点（Secrets 不入库、Redis 对周期任务/News AI 的要求）
  - 链接到 `../docs/PROD_DEPLOY_AND_SMOKE_SOP.md` 与 `../docs/UPDATE_LOG.md`

### 6. 测试结果（回归通过）

- **后端**：`py -m pytest -q` -> `42 passed`
- **前端 E2E**：`npm run test:e2e` -> `51 passed`

### 7. Kubernetes / Helm 交付

- 新增 Helm Chart：`../helm/baixing-assistant`
  - 支持 backend + frontend + ingress（`/api` -> backend，`/` -> frontend）
  - Secrets 通过 K8s Secret 注入，符合“Secrets 不入库”策略
- 新增 Helm 校验 CI：`.github/workflows/ci.yml` -> `helm-validate` job
  - `helm lint` + `helm template` 渲染验证（不依赖本机是否安装 helm）
  - 额外覆盖可选路径渲染：subcharts enabled（redis/postgresql）与 externalSecret enabled
- 新增合并门禁聚合 job：`.github/workflows/ci.yml` -> `required-checks` job
  - 依赖 `helm-validate/backend-test/frontend-build`
  - 可用于 GitHub Branch Protection 的 Required Status Check，让 `helm lint` 成为必需检查
- 提供 values 示例（不含 secrets，仅占位符）：
  - `../helm/baixing-assistant/values.prod.example.yaml`
  - `../helm/baixing-assistant/values.externalsecret.example.yaml`
  - `../helm/baixing-assistant/values.subcharts.example.yaml`

---

## 2025-12-29

### 1. News 模块发布

- Tag：`news-module-20251229`
- GitHub Release：`https://github.com/1025615864/-123/releases/tag/news-module-20251229`

### 2. 发布后冒烟验证

- 本地冒烟脚本：`scripts/smoke-news-ai.ps1` 通过（health/status/创建新闻/AI rerun/轮询校验/清理）。

### 3. 管理员登录 token 字段说明

- `POST /api/user/login` 返回的 JWT 位于：`token.access_token`（不是顶层 `access_token`）。

### 4. 文档整理与口径统一

- 根目录 `README.md`：精简重复内容，收敛为“文档入口 + 快速启动 + 配置与部署指引”，并链接到运维 SOP / Helm / env 示例。
- `backend/env.example`：补齐与实际配置项一致的示例（`PAYMENT_WEBHOOK_SECRET/REDIS_URL/FRONTEND_BASE_URL/TRUSTED_PROXIES/AI_MODEL` 等）。
- `backend/README.md`：修正 AI 咨询接口速查（补充 `chat/stream`，并将 consultations 路径参数对齐为 `session_id`）。

### 5. 文档完善：开发/架构/API 速查扩展

- `docs/API_QUICK_REFERENCE.md`：从 News/News AI/SystemConfig 扩展为“核心模块 API 速查”，覆盖用户/AI/论坛/知识库/律所/支付/文书/上传/通知/搜索/管理后台等。
- 新增：`docs/DEV_GUIDE.md`（从零本地启动、Windows 常见坑、测试/E2E 命令）
- 新增：`docs/ARCHITECTURE.md`（整体架构、路由结构、数据流与安全策略）
- `docs/HANDOFF.md` / 根目录 `README.md`：补充上述新文档索引入口。
