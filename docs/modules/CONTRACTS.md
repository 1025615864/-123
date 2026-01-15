# 合同审查（CONTRACTS）

本模块提供“上传合同文件 -> 提取文本 -> AI 风险体检 -> 结构化 JSON + Markdown 报告”的能力。

Router：`backend/app/routers/contracts.py`（prefix：`/contracts`，实际对外：`/api/contracts/*`）

前端入口：

- 合同审查页：`frontend/src/pages/ContractReviewPage.tsx`

## 1. 核心 API

### 1.1 合同审查

- `POST /api/contracts/review`
  - Content-Type：`multipart/form-data`
  - form field：`file`

响应：`ContractReviewResponse`（见 `backend/app/schemas/contracts.py`）

- `report_json`：结构化体检报告
- `report_markdown`：可渲染报告（前端主要展示）
- `request_id`：服务端生成或从 request.state 取

## 2. 限流 / 配额 / 访客策略

后端同时叠加两类控制：

- 装饰器限流：`RateLimitConfig.AI_HEAVY`（按 IP）
- 游客试用：
  - env：`GUEST_CONTRACT_REVIEW_LIMIT`（默认 1）
  - env：`GUEST_CONTRACT_REVIEW_WINDOW_SECONDS`（默认 24h）
  - 超限会返回 429，并带 `X-RateLimit-*` / `Retry-After`
- 登录用户：复用 `quota_service.enforce_document_generate_quota()`（注意：当前实现与“文书生成”共用同一配额口径）

## 3. 文件处理与支持格式

文件大小：

- 非 E2E mock 时：最大 10MB，否则 400

提取策略：

- `.pdf`：`pypdf.PdfReader().pages[].extract_text()`
- `.docx`：`docx2txt`（临时文件落盘）
- 文本类：`txt/md/csv/json` 或 `text/*`：按 utf-8 解码（errors=replace）

不支持类型：返回 400（`CONTRACT_BAD_REQUEST`）

提取文本为空：返回 400（无法从文件中提取文本）

为了控制 token：

- 最长截断：`max_chars = 200_000`
- `text_preview`：前 4000 字符

## 4. AI 调用与可配置规则

AI 依赖：

- env：`OPENAI_API_KEY`（缺失会返回 503，error_code=`AI_NOT_CONFIGURED`）
- env：`OPENAI_BASE_URL`（可选）
- env：`AI_MODEL`（默认 fallback `gpt-4o-mini`）

隐私处理：

- 会对合同文本做脱敏：`backend/app/utils/pii.py:sanitize_pii()` 后再送入 AI

规则增强（SystemConfig）：

- key：`CONTRACT_REVIEW_RULES_JSON`
- 用途：为 AI 输出增加“必备条款/风险库关键字”等补充规则
- 生效方式：
  - prompt 会附加 rules JSON
  - 返回后通过 `apply_contract_review_rules()` 二次补全 missing_clauses/risks，并提升 overall_risk_level

实现：`backend/app/services/contract_review_service.py`

## 5. 错误响应与可观测性

错误响应会返回 JSON（而不是 Envelope），并带 header：

- `X-Request-Id`
- `X-Error-Code`

error_code 枚举（router 内）：

- `AI_NOT_CONFIGURED`
- `CONTRACT_BAD_REQUEST`
- `CONTRACT_INTERNAL_ERROR`

## 6. E2E Mock（仅 debug）

当满足：

- `DEBUG=true`（settings.debug）
- 且请求头：`X-E2E-Mock-AI: 1`

则不读取/解析真实文件，也不调用 OpenAI，直接返回固定结果（便于 E2E 自动化）。

## 7. 与 PDF 导出的复用

前端在合同审查结果页可“预览/下载 PDF”，实际调用的仍是文书模块：

- `POST /api/documents/export/pdf`（传入 `title/content`）

## 8. 常见问题

- **503 AI_NOT_CONFIGURED**：配置 `OPENAI_API_KEY`
- **400 不支持文件类型**：确保上传 pdf/docx/txt/md/csv/json
- **500 合同审查失败**：
  - 优先检查 OpenAI 网络/模型配置
  - 检查 rules JSON 是否非法（虽然代码做了 try/catch，但可能导致 prompt 异常）

## 9. 关联文档

- 文书生成（PDF 导出复用）：`docs/modules/DOCUMENTS.md`
- 配额/限流：`docs/modules/BACKEND_INFRA.md`
- SystemConfig：`docs/modules/SYSTEM_CONFIG.md`
