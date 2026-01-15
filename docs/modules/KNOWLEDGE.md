# 知识库（KNOWLEDGE）

本模块提供：

- 法律知识条目管理（法条/案例/法规/司法解释）
- 批量导入、批量删除
- 向量化（写入向量库，用于 AI 检索增强）
- 咨询模板（常见问题模板）管理
- 分类（KnowledgeCategory）管理

Router：`backend/app/routers/knowledge.py`（prefix：`/knowledge`，实际对外：`/api/knowledge/*`）

前端入口：

- 管理后台知识库：`frontend/src/pages/admin/KnowledgeManagePage.tsx`（路由：`/admin/knowledge`）

## 1. 权限模型

- 绝大多数接口需要管理员：`require_admin`
- 咨询模板列表 `GET /api/knowledge/templates` 默认只返回 `is_active=true` 的模板
  - 若请求 `is_active != true`（例如 false 或空），则必须管理员（代码硬拦）

## 2. 数据模型

### 2.1 法律知识

表：`legal_knowledge`

Model：`backend/app/models/knowledge.py:LegalKnowledge`

关键字段：

- `knowledge_type`：`law/case/regulation/interpretation`
- `title/article_number/content/summary/category/keywords`
- `source/source_url/source_version/source_hash`
- `ingest_batch_id`：导入批次
- `weight`：排序权重（list 默认 `weight desc, created_at desc`）
- `is_active`：启用开关
- `is_vectorized`：是否已同步到向量库
- `vector_id`：向量库文档 ID（当前 service 主要用 `knowledge_id`，该字段可能未被写入）

source_hash 生成规则：

- `knowledge_type|title|article_number|content|source_url|source_version` 做 sha256

实现：`backend/app/services/knowledge_service.py:_compute_source_hash()`

### 2.2 分类

表：`knowledge_categories`

Model：`KnowledgeCategory`

说明：Router 提供 CRUD；service 的 `get_categories()` 仅用于从 `legal_knowledge` distinct 出 category（两套“分类来源”并存）。

### 2.3 咨询模板

表：`consultation_templates`

Model：`ConsultationTemplate`

- `questions`：JSON string（存储 `[{question,hint}]`）
- `sort_order/is_active`

## 3. 法律知识 API（管理员）

### 3.1 CRUD

- `POST /api/knowledge/laws`
- `GET /api/knowledge/laws?page=&page_size=&knowledge_type=&category=&keyword=&is_active=`
- `GET /api/knowledge/laws/{knowledge_id}`
- `PUT /api/knowledge/laws/{knowledge_id}`
- `DELETE /api/knowledge/laws/{knowledge_id}`

注意：

- `PUT` 若变更 `title/content`，会将 `is_vectorized` 重置为 `false`（需要重新向量化）

### 3.2 批量操作

- `POST /api/knowledge/laws/batch-delete`：`{ids: [...]}`
- `POST /api/knowledge/laws/batch-import`：`{items: [...], dry_run: bool}`
  - `dry_run=true`：仅校验，不写入

批量导入 upsert 规则（service 实现）：

- 以 `(knowledge_type, title, article_number)` 查重
- 若不存在：insert
- 若存在：update 内容并将 `is_vectorized=false`
- 对每条 item 单独 commit；失败会 rollback 且计数 failed

### 3.3 向量化

- `POST /api/knowledge/laws/{knowledge_id}/vectorize`
- `POST /api/knowledge/laws/batch-vectorize`：`{ids: [...]}`
- `POST /api/knowledge/sync-vector-store`：同步所有 `is_active=true && is_vectorized=false`

实现要点：

- 依赖 `ai_assistant.knowledge_base`，并要求 `vector_store` 已初始化
- 写入 doc 结构：
  - `law_name/article/content/source/knowledge_id/source_url/source_version/source_hash/ingest_batch_id`
- 成功后标记 `is_vectorized=true`

注意：

- 若 AI 助手不可用/向量库未初始化：vectorize 会返回失败（router 会转 400：向量化失败）

### 3.4 统计

- `GET /api/knowledge/stats`
- `GET /api/knowledge/laws/distinct-categories`

## 4. 咨询模板 API

- `POST /api/knowledge/templates`（管理员）
- `GET /api/knowledge/templates?category=&is_active=`（默认只给 active；取 inactive 需要管理员）
- `GET /api/knowledge/templates/{template_id}`（管理员）
- `PUT /api/knowledge/templates/{template_id}`（管理员）
- `DELETE /api/knowledge/templates/{template_id}`（管理员）

questions 字段存储：

- 写入时会 `json.dumps([q.model_dump() for q in data.questions])`
- 读取时用 `parse_template_questions()` 反序列化

## 5. 分类管理 API（管理员）

- `GET /api/knowledge/categories`
- `POST /api/knowledge/categories`
- `PUT /api/knowledge/categories/{category_id}`
- `DELETE /api/knowledge/categories/{category_id}`

## 6. 导入接口（legacy）

Router 额外提供：

- `POST /api/knowledge/laws/batch-import-legacy`（JSON）
- `POST /api/knowledge/laws/import-csv`（CSV）

这些接口更多用于历史迁移/快速导入。

## 7. 常见问题

- **知识已更新但检索结果不变**：检查该条目 `is_vectorized` 是否被重置为 false，并重新 vectorize
- **批量导入慢**：当前实现 per-item commit，适合中小批量；大批量建议后续改为批处理事务
- **分类来源不一致**：
  - `knowledge_categories` 是“管理配置分类”
  - `legal_knowledge.category` 是“条目实际分类字符串”

## 8. 关联文档

- AI 咨询与检索：`docs/modules/CONSULTATION.md`
- 搜索：`docs/modules/SEARCH.md`
- SystemConfig：`docs/modules/SYSTEM_CONFIG.md`
