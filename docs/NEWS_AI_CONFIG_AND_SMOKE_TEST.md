# 新闻 AI 配置说明与线上冒烟验证清单

> 适用范围：新闻摘要/要点/关键词（`NewsAIPipelineService`）

## 1. 背景与目标

新闻 AI pipeline 会对新闻进行结构化标注：

- 摘要 `summary`
- 要点 `highlights`（列表）
- 关键词 `keywords`（列表）
- 风险等级 `risk_level`

为了便于线上运维与故障定位，系统支持：

- 多 LLM Provider（可配置多个 OpenAI-compat 服务）
- Provider 选择策略（priority/round_robin/random）
- `response_format`（支持 json_object/json_schema；不支持时 400/422 自动回退）
- 运行时动态配置（通过 `SystemConfig` 写入，无需重启）
- 运维状态接口：`GET /api/system/news-ai/status`

## 2. 配置入口

配置优先级：

1. **SystemConfig（运行时覆盖）**：通过管理后台“系统设置”写入，立即生效
2. **环境变量（env）**：服务启动时读取的默认值

说明：如果 SystemConfig 中存在同名 key 且 value 非空，则会覆盖 env。

## 3. 关键配置项（SystemConfig / env）

### 3.1 启用/禁用

- `NEWS_AI_SUMMARY_LLM_ENABLED`
  - `true/1/on/yes`：启用 LLM 摘要
  - `false/0/off/no`：禁用 LLM（使用本地兜底生成）

### 3.2 Provider 列表

- `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON`
  - JSON 字符串，内容为 provider 数组
- `NEWS_AI_SUMMARY_LLM_PROVIDERS_B64`
  - 将 providers JSON base64 后写入（Windows 复制粘贴更友好）

Provider JSON 示例：

```json
[
  {
    "name": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-xxx",
    "model": "gpt-4o-mini",
    "response_format": "json_object",
    "auth_type": "bearer",
    "chat_completions_path": "/chat/completions",
    "weight": 1
  },
  {
    "name": "vendor2",
    "base_url": "https://xxx.example.com/v1",
    "api_key": "k2",
    "model": "gpt-4o-mini",
    "response_format": "off",
    "auth_type": "header",
    "auth_header_name": "api-key",
    "auth_prefix": "",
    "chat_completions_path": "/chat/completions",
    "weight": 3
  }
]
```

字段说明：

- `name`：可选，展示/日志用
- `base_url`：必填，形如 `https://host/v1`
- `api_key`：必填
- `model`：可选，默认 `gpt-4o-mini`
- `response_format`：可选，provider 级覆盖（优先级高于全局）
- `auth_type`：可选，`bearer`（默认）/ `header`
- `auth_header_name`：`auth_type=header` 时可用，默认 `api-key`
- `auth_prefix`：`auth_type=header` 时可用（例如某些服务要求 `Token xxx`）
- `chat_completions_path`：可选，默认 `/chat/completions`
- `weight`：random 策略权重（正整数）

### 3.3 Provider 策略

- `NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY`
  - `priority`：按 providers 顺序依次尝试（失败自动切到下一个）
  - `round_robin`：轮询（每次调用从不同 provider 开始）
  - `random`：随机（支持 weight）

### 3.4 response_format（全局默认）

- `NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT`
  - `json_object`：结构化 JSON 输出（推荐）
  - `json_schema`：更严格结构（依赖供应商支持）
  - 关闭：`0/off/none/disable/disabled`

优先级：provider 内的 `response_format` > 全局 `NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT`。

### 3.5 运行参数（可按需）

- `NEWS_AI_BATCH_SIZE`：每次 pipeline 处理数量
- `NEWS_AI_LAST_ERROR_MAX_CHARS`：`last_error` 最大长度
- `NEWS_AI_SUMMARY_LLM_TIMEOUT_SECONDS`：LLM 请求超时
- `NEWS_AI_SUMMARY_LLM_HIGHLIGHTS_MAX` / `NEWS_AI_SUMMARY_LLM_KEYWORDS_MAX` / `NEWS_AI_SUMMARY_LLM_ITEM_MAX_CHARS`

## 4. 运维接口

### 4.1 状态接口

- `GET /api/system/news-ai/status`（管理员）

返回信息包含：

- 生效策略、response_format、providers（api_key 不回显，只返回 `api_key_configured`）
- 待处理积压 `pending_total`
- 错误总数 `errors_total`
- 近 24h 错误数 `errors_last_24h`
- 近 7d 错误数 `errors_last_7d`
- 近 7 天错误趋势 `errors_trend_7d`
- Top 错误 `top_errors`
- 最近错误列表 `recent_errors`（news_id、retry_count、last_error、last_error_at）
- `config_overrides`（SystemConfig 覆盖值会脱敏）

## 5. 线上冒烟验证清单（按风险从高到低）

### 5.1 配置是否生效（无需重启）

1. 管理后台 -> 系统设置
2. 填写/更新：
   - `NEWS_AI_SUMMARY_LLM_ENABLED=true`
   - `NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY=priority`
   - `NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT=json_object`
   - `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON`（填入至少 1 个 provider）
3. 保存
4. 打开 `GET /api/system/news-ai/status`（或看管理后台页面的运维卡片）
   - 推荐用管理员 token 直连验证（更准确）：

```bash
curl -sS \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  "<BASE_URL>/api/system/news-ai/status" | cat
```

5. 确认：
   - `providers` 数组长度正确
   - `api_key_configured=true`
   - `provider_strategy/response_format` 与配置一致
   - `config_overrides` 中能看到你刚写入的 key（值应被脱敏）

常见问题排查：

- SystemConfig 写入后仍未生效：确认写入 key 名是否完全一致（大小写敏感）
- providers 为空：优先检查 `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON` 是否为合法 JSON 数组

### 5.2 response_format 回退验证（供应商不支持时）

1. 选择一个已知不支持 `response_format` 的 provider（或临时设置为 `json_schema` 触发 400/422）
2. 确保 pipeline 仍能成功产出摘要（会自动重试一次不带 response_format）
3. 观察日志与 `recent_errors`：
   - 不应出现持续性错误堆积

期望结果：

- 最终 `summary/highlights/keywords` 仍能生成
- 若供应商返回 400/422：只应出现一次失败 + 一次自动回退重试（不带 response_format）

### 5.3 多 provider failover 验证

1. 配置 providers：第一个故意填错（base_url 或 api_key），第二个正确
2. 触发 pipeline（新增新闻或等待周期任务）
3. 验证：
   - 最终能产出 summary/highlights/keywords
   - 第一个 provider 失败不会阻断整体

推荐触发方式（更可控）：

- 在管理后台“新闻管理”新增一条新闻（内容写短一点）
- 或者后端已有周期任务时等待下一次跑批

### 5.4 处理积压与性能观察

1. 连续导入/创建多条新闻
2. 观察 `/system/news-ai/status`：
   - `pending_total` 随时间下降
   - `errors_total` 不应持续上升
3. 如积压大：
   - 适当上调 `NEWS_AI_BATCH_SIZE`
   - 检查 LLM timeout/供应商限流

补充建议：

- 若供应商有 QPS 限制，建议保持 `batch_size` 小一些并缩短 `NEWS_AI_INTERVAL_SECONDS`，避免瞬间并发
- 若经常超时，优先调大 `NEWS_AI_SUMMARY_LLM_TIMEOUT_SECONDS` 并检查供应商链路

### 5.5 错误可观测性验证

1. 故意让 LLM 请求失败（断网/错误 base_url）
2. 等待 pipeline 跑一次
3. 验证：
   - `news_ai_annotations.retry_count` 增加
   - `last_error/last_error_at` 被写入
   - `/system/news-ai/status` 的 `recent_errors` 可见

推荐验证 SQL（按你实际数据库调整）：

```sql
SELECT news_id, retry_count, last_error_at, last_error
FROM news_ai_annotations
WHERE last_error IS NOT NULL
ORDER BY last_error_at DESC
LIMIT 10;
```

### 5.6 鉴权与 Header 兼容性验证（provider 级 auth_type/header）

1. 配置一个 provider 使用默认 `bearer`
2. 再配置一个 provider 使用 `auth_type=header` + `auth_header_name`（例如 `api-key`）
3. 在 `priority` 策略下依次验证二者都能成功产出

期望结果：

- 两类鉴权方式都可用
- `GET /api/system/news-ai/status` 中能看到 provider 的 `auth_type/auth_header_name/auth_prefix`（但 api_key 不回显）

### 5.7（可选）管理员手动重跑单条新闻 AI 标注

当线上发现某条新闻标注结果异常、或 provider 切换后希望立即重算，可使用“手动重跑”。

- 接口（管理员）：`POST /api/news/admin/{news_id}/ai/rerun`
- UI：管理后台 -> 新闻管理 -> 操作列「重跑 AI 标注」按钮

推荐验证步骤（UI）：

1. 以管理员登录管理后台
2. 进入「新闻管理」页面
3. 找到目标新闻（可用搜索）
4. 点击操作列「重跑 AI 标注」并确认
5. 期望结果：
   - 页面 toast 提示“已触发重跑 AI 标注”
   - 该新闻的 AI 字段在短时间内刷新（或进入编辑弹窗查看）
   - 如失败：后端会累加 `retry_count` 并写入 `last_error/last_error_at`

推荐验证步骤（API）：

```bash
curl -sS -X POST \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  "<BASE_URL>/api/news/admin/<NEWS_ID>/ai/rerun" | cat
```

可选：验证 `processed_at/retry_count/last_error`（管理员接口）：

```bash
curl -sS \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  "<BASE_URL>/api/news/admin/<NEWS_ID>" | cat
```

期望结果：

- 成功时：`ai_annotation.processed_at` 更新为最新时间，且 `last_error/last_error_at` 为空、`retry_count=0`
- 失败时：`retry_count` 增加，`last_error/last_error_at` 写入；同时可在 `GET /api/system/news-ai/status` 的 `recent_errors/top_errors` 中看到异常聚合

## 6. 推荐默认值（可直接用）

- `NEWS_AI_SUMMARY_LLM_ENABLED=true`
- `NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY=priority`
- `NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT=json_object`
- `NEWS_AI_BATCH_SIZE=50`
- `NEWS_AI_LAST_ERROR_MAX_CHARS=800`
- `NEWS_AI_SUMMARY_LLM_TIMEOUT_SECONDS=20`
- `NEWS_AI_SUMMARY_LLM_HIGHLIGHTS_MAX=3`
- `NEWS_AI_SUMMARY_LLM_KEYWORDS_MAX=5`
- `NEWS_AI_SUMMARY_LLM_ITEM_MAX_CHARS=40`

## 7. CI / 主线验证（补充）

- **主线工作流**：
  - `CI/CD Pipeline` 与 `Type Check` 均支持 `workflow_dispatch`，可在 GitHub Actions 页面手动 Run workflow，并选择分支 `main`。
- **code-quality 行为**：
  - `code-quality` 为非阻塞项：ruff/eslint 失败不会阻断主流程。
  - 若前端未配置 `eslint`（无依赖/无配置文件），CI 会自动跳过 eslint 步骤，避免误报失败。
