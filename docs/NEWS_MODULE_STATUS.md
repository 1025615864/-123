# 新闻模块开发进度（截至 2025-12-26）

> 目的：给你在新对话中继续推进提供一份“可直接接力”的状态说明。

## 1. 当前完成情况（已落地且已验证）

### 1.1 新闻 AI 标注（摘要/要点/关键词/风险）链路已打通

- **后端**：`NewsAIPipelineService` 能产出并入库
  - `summary`
  - `highlights`（列表）
  - `keywords`（列表）
  - `risk_level`（safe/warn/danger 等）
- **接口返回**：新闻详情接口会返回 `ai_annotation`，包含 `highlights/keywords/risk_level` 等字段；新闻列表会返回用于卡片展示的 `ai_keywords`。
- **前端展示**：
  - 新闻详情页可见 AI highlights、keywords。
  - 新闻列表卡片可展示 keywords badge。

### 1.2 E2E 不稳定问题已定位并修复（核心成果）

此前 Playwright E2E 中 `waitForNewsAiAnnotationReady` 超时（highlights/keywords 不出现）已修复，根因与修复点如下：

- **根因（重要）**：

  - E2E 使用的 SQLite 会复用已删除新闻的 `id`；
  - 但 `NewsAIAnnotation` 可能残留（删除新闻时未级联清理）；
  - 新建新闻复用同一个 `news_id` 时，会读到旧的 annotation（可能只有 risk，没有 highlights/keywords），且 pipeline 可能因为 `processed_at` 已存在而不再处理，导致 highlights/keywords 永远空。

- **修复（已合入）**：
  1. **Pipeline 选取待处理条件增强**：
     - `run_once()` 现在会把以下情况也视为“需要处理”：
       - `highlights is NULL` 或 `keywords is NULL`
     - 这样即便存在旧 annotation，也会被重新补齐结构化字段。
  2. **删除新闻联动删除 AI 标注**：
     - `NewsService.delete()` 会同步删除 `NewsAIAnnotation`：
       - `news_id == news.id` 或 `duplicate_of_news_id == news.id`

### 1.3 Mock/无 LLM 情况下也能稳定产出 highlights/keywords

- 后端加入了本地兜底生成逻辑：当 LLM/mock 不可用时也会从 title/content 生成基本的 highlights/keywords。
- 同时增强：即便 LLM 返回了 summary，但 highlights 或 keywords 为空，也会用本地结果补齐（避免 E2E 等待空数组）。

### 1.4 Playwright 环境稳定策略已完成

- **端口隔离**：E2E 前端 dev server 默认端口固定为 `5174`（避免复用 5173 的旧进程导致 proxy 指向错后端）。
- **后端端口**：默认 `8001`。
- **复用策略**：只有设置 `E2E_REUSE_EXISTING=1` 才会复用现存服务，默认不复用（CI/本地均更确定性）。
- **Mock LLM 输出**：通过 Base64 环境变量注入（Windows 友好）：
  - `NEWS_AI_SUMMARY_LLM_MOCK_RESPONSE_B64`。

### 1.5 OpenAI 兼容接口 response_format 支持（已完成）

- `NewsAIPipelineService._llm_summarize()` 支持 `response_format`：
  - `json_object`
  - `json_schema`
- **默认启用**：现在默认使用 `json_object`（更强结构化，减少解析风险）。
- **显式关闭**：环境变量 `NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT` 设为以下任意值会关闭：
  - `0/off/none/disable/disabled`
- **自动回退**：供应商不支持 `response_format` 时（HTTP 400/422）自动重试一次，不携带 `response_format`。

### 1.6 可观测性与运维能力增强（已完成）

- **错误可追踪（入库）**：`NewsAIAnnotation` 新增字段
  - `retry_count`
  - `last_error`
  - `last_error_at`
- **数据库自修复**：SQLite/PostgreSQL 初始化会自动补齐新增列。
- **Pipeline 统计日志**：`run_once()` 会记录处理耗时与积压量，并在失败时写入 last_error 信息。
- **运维接口（管理员）**：
  - `GET /api/system/news-ai/status`
  - 返回：当前生效 provider 配置（脱敏）、策略、response_format、积压量、最近错误。
- **管理后台页面增强**：管理后台“系统设置”新增“新闻 AI 配置/运维状态”区块，用于查看与配置。

## 2. 测试覆盖现状（已通过）

### 2.1 后端 pytest

- 已新增/已有的后端单测覆盖：
  - 结构化输出解析与限长（`_extract_structured_output`）。
  - `run_once()` 写入 highlights/keywords。
  - `response_format` 不支持时自动回退重试。
- 最新状态：`py -m pytest` 全绿（36 passed）。

### 2.2 前端 Playwright E2E

- 新闻相关 E2E 已覆盖：
  - 新闻详情：AI 要点/关键词可见；列表卡片展示 AI keywords badge。
  - 管理后台：AI 风险筛选可用且列表展示 badge。
- 最新状态：`npm run test:e2e` 全绿（50 passed）。

### 2.3 GitHub Actions（主线 main）

- **工作流**：
  - `CI/CD Pipeline`：backend-test / frontend-build / docker-build / code-quality / security-scan
  - `Type Check`：pyright
- **触发方式**：
  - push 到 `main`（以及 `develop`）
  - PR 指向 `main`
  - Actions 页面手动触发（`workflow_dispatch` -> Run workflow）
- **备注**：
  - `code-quality` 为非阻塞项：ruff/eslint 失败不会阻断主流程
  - 若前端未配置 `eslint`（无依赖/无配置文件），CI 会自动跳过 eslint 步骤

## 3. 当前新闻模块“功能清单”视角（你可以用来汇报/对齐）

### 3.1 已具备的能力

- 新闻 CRUD/审核/发布/置顶
- 新闻列表：关键词搜索、热门、推荐、最近浏览
- 订阅：订阅分类 -> 发布后通知
- AI：
  - 风险识别（risk_level + badge）
  - 摘要（summary）
  - highlights/keywords 结构化字段

### 3.2 已解决的工程质量问题

- E2E 的确定性与可重复性（端口隔离、mock 注入、pipeline 可再处理）
- SQLite id 复用导致的历史 annotation 污染

## 4. 未完成/待确认事项（建议在新对话中优先推进）

> 下面是“功能/质量/上线”维度仍建议继续做的点（不代表现在有 bug，而是为了产品化/可运营）。

### 4.1 配置与上线策略（已决策并落地）

- **生产 provider：区分环境（是）**
  - 后端已支持按环境读取 SystemConfig（优先读取带后缀的 key），并回退到 default key。
  - 环境 token 解析来源：`APP_ENV` / `ENV` / `ENVIRONMENT`。
    - `prod|production` -> `PROD`
    - `staging` -> `STAGING`
    - `dev|development` -> `DEV`
- **多 provider：启用（是，按 priority 兜底）**
  - `NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY=priority`
  - Providers JSON 示例（不写 api_key，api_key 走环境变量/Secret）：
    - `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON_PROD`：
      - `[{"name":"openai","priority":1},{"name":"azure-openai","priority":2},{"name":"claude","priority":3}]`
  - 对应环境变量约定：
    - `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `AI_MODEL`
    - `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_BASE_URL` / `AZURE_OPENAI_MODEL`
    - `CLAUDE_API_KEY` / `CLAUDE_BASE_URL` / `CLAUDE_MODEL`
- **response_format：默认启用 json_object（是）**
  - 生产建议设置：`NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT=json_object`
  - 后端已实现 400/422 自动回退（不携带 response_format 再重试一次）。

### 4.2 数据一致性/清理策略

- 现已在删除新闻时清理 annotation，但：
  - 生产环境历史脏数据清理脚本：**已提供（是）**
    - `backend/scripts/cleanup_news_ai_data.py`
    - 默认 dry-run；加 `--apply` 才会落库。
  - `duplicate_of_news_id` 的业务语义：**仅提示（不合并/不隐藏）**
    - 前台新闻详情页会显示“疑似重复 -> 查看 #id”。
    - 管理后台编辑弹窗也会显示同样提示，方便运营跳转核对。

### 4.3 可观测性（建议）

（已完成）

### 4.4 API/前端体验（可选增强）

- 列表页/详情页的 AI 字段加载体验：
  - 是否需要 skeleton/“AI 生成中”占位
  - 是否需要手动触发“重新生成”按钮（管理员）

### 4.5 性能与并发（可选）

- 当前 pipeline 通过周期任务 + 锁运行：
  - 生产是否强依赖 Redis（用于分布式锁）：**是**
  - batch_size/interval：继续以 env 为主（必要时再开放到 SystemConfig）。

---

## 4.x 已确认的决策（最终）

1. 生产 provider：是否区分环境：**是**
2. 多 provider 策略：**priority**（按 `priority` 兜底）
3. response_format 默认：**json_object**
4. 是否需要历史数据清理脚本：**是**（已提供 `backend/scripts/cleanup_news_ai_data.py`)
5. duplicate_of_news_id：**仅提示**（不做合并/隐藏产品化）
6. 生产 Redis 是否可用：**是**

## 5. 对“上一计划（n12）完成进度”的汇总

- n12-1：定位 E2E highlights/keywords 不出现根因 —— **完成**
- n12-2：修复后端确保 E2E pipeline 可靠产出并写入 —— **完成**
- n12-3：修复/稳定 Playwright E2E（等待条件、mock、端口）—— **完成**
- n12-4：跑通并确认后端单测 + 前端 E2E 全部通过 —— **完成**

## 6. 新对话建议你直接这样开局（复制即可）

> “基于 docs/NEWS_MODULE_STATUS.md：我想先推进 4.1 配置与上线策略。我们当前使用的 LLM provider 是 XXX，base_url 是 XXX，生产环境是否支持 response_format？请你给出上线前冒烟验证清单，并按风险排序。”
