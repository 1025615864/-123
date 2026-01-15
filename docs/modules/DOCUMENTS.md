# 文书生成（DOCUMENTS）

本模块提供“法律文书生成 + PDF 导出 + 我的文书存档”能力。

Router：`backend/app/routers/document.py`（prefix：`/documents`，实际对外：`/api/documents/*`）

前端入口：

- 文书生成页：`frontend/src/pages/DocumentGeneratorPage.tsx`

## 1. 数据模型

### 1.1 生成记录

表：`generated_documents`

Model：`backend/app/models/document.py:GeneratedDocument`

- `user_id`：归属用户
- `document_type`：模板 key（例如 `complaint/defense/agreement/letter`）
- `title/content`：生成结果
- `template_key/template_version`：生成时使用的模板版本（可空）
- `payload_json`：保存时的表单输入（JSON string，可空）
- `created_at/updated_at`

### 1.2 文书模板（DB 可配置）

表：

- `document_templates`：模板元信息
- `document_template_versions`：模板内容版本

Model：`backend/app/models/document_template.py`

模板“生效版本”规则（生成时使用）：

- `DocumentTemplate.is_active == true`
- 选择 `DocumentTemplateVersion.is_published == true` 的最新 `version`（按 `version desc`）

当 DB 没有发布版本时，会 fallback 到内置模板：

- `backend/app/services/document_templates_builtin.py:BUILTIN_DOCUMENT_TEMPLATES`

## 2. 核心 API

### 2.1 生成文书（游客可用）

- `POST /api/documents/generate`

鉴权：可匿名（`get_current_user_optional`）

限流/配额：

- 装饰器限流：`RateLimitConfig.DOCUMENT_GENERATE`（按 IP）
- 游客额度：
  - env：`GUEST_DOCUMENT_GENERATE_LIMIT`（默认 0 表示不启用）
  - env：`GUEST_DOCUMENT_GENERATE_WINDOW_SECONDS`（默认 24h）
  - 逻辑：按 IP 计数，超过返回 429，且带 `X-RateLimit-*` / `Retry-After`
- 登录用户：`quota_service.enforce_document_generate_quota()`（文书额度，按天）

输入字段（简化）：

- `document_type`：模板 key
- `case_type/plaintiff_name/defendant_name/facts/claims/evidence`

边界条件：

- `facts > 8000` 或 `claims > 4000` 或 `evidence > 4000` 会 400
- `document_type` 必填；模板不存在/无发布版本/无内置模板会 400

输出字段：

- `title/content/created_at`
- 额外包含：`template_key/template_version`（便于存档）

### 2.2 获取可用模板列表

- `GET /api/documents/types`

行为：

- 优先读取 DB 中 `is_active=true` 且存在 `is_published=true` 版本的模板
- 若 DB 读取失败或无发布模板，会 fallback 返回内置模板列表

### 2.3 PDF 导出（无需登录）

- `POST /api/documents/export/pdf`

输入：`{title, content}`

输出：`application/pdf`（`Content-Disposition` 同时提供 ASCII filename + UTF-8 filename）

依赖：

- PDF 渲染依赖 `reportlab`（运行时 import）
- 若依赖缺失，返回 501：`PDF 生成依赖未安装`

前端使用：

- `DocumentGeneratorPage`、`ContractReviewPage` 都会复用此接口进行 PDF 预览/下载

### 2.4 保存为“我的文书”（需要登录）

- `POST /api/documents/save`

鉴权：`get_current_user`

行为：

- 将生成结果保存到 `generated_documents`
- `payload` 会被 `json.dumps` 存入 `payload_json`（若序列化失败则置空）
- `template_version`：
  - 若传入则尝试转 int
  - 否则尝试根据 `template_key` 自动解析当前发布版本

### 2.5 我的文书（需要登录）

- `GET /api/documents/my?page=&page_size=`：分页列表
- `GET /api/documents/my/{doc_id}`：详情
- `GET /api/documents/my/{doc_id}/export?format=pdf`：导出 PDF（仅支持 `pdf`）
- `DELETE /api/documents/my/{doc_id}`：删除

所有接口均做 owner 校验：`GeneratedDocument.user_id == current_user.id`。

## 3. 模板语法与扩展点

模板内容采用 Python `str.format()` 格式化，当前使用字段包括：

- `{plaintiff_name}` / `{defendant_name}`
- `{case_type}` / `{facts}` / `{claims}`
- `{evidence_section}` / `{evidence_count}`
- `{court_name}` / `{date}`

扩展点建议：

- 如需增加新字段：必须同时更新
  - 前端表单
  - `DocumentGenerateRequest`
  - 模板渲染 `format(...)` 入参
  - 内置模板与管理端模板编辑提示

## 4. 常见问题与排障

- **生成 429**

  - 游客：检查 `GUEST_DOCUMENT_GENERATE_LIMIT/WINDOW` 与 IP
  - 登录用户：检查 `quota_service` 的日配额与次数包（前端会从 `/user/me/quotas` 展示）

- **PDF 导出 501**

  - 安装 `reportlab` 依赖后重试

- **模板变更未生效**
  - 确认有 `is_published=true` 的版本
  - 确认模板 `is_active=true`

## 5. 关联文档

- 模块索引：`docs/modules/INDEX.md`
- 系统配置：`docs/modules/SYSTEM_CONFIG.md`
- 配额与限流：`docs/modules/BACKEND_INFRA.md`
