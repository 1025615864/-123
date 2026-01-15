# 文书模板管理（DOCUMENT_TEMPLATES）

本模块提供“后台可配置文书模板 + 多版本 + 发布切换”能力。

Router：`backend/app/routers/document_templates.py`

- prefix：`/admin/document-templates`
- 实际对外：`/api/admin/document-templates/*`

前端入口：

- 管理后台：`frontend/src/pages/admin/DocumentTemplatesManagePage.tsx`（路由：`/admin/document-templates`）

## 1. 权限与边界

鉴权：必须管理员

- `require_admin`：`role in {admin, super_admin}`

注意：这里的“文书模板管理”与“系统配置 SystemConfig”是两条独立的管理链路。

## 2. 数据模型

Model：`backend/app/models/document_template.py`

- `document_templates`

  - `key`：唯一（unique）
  - `is_active`：是否启用

- `document_template_versions`
  - unique：`(template_id, version)`
  - `is_published`：当前发布版本标记
  - `content`：模板正文

发布策略（后端实现）：

- 创建版本且 `publish=true` 时：会将同模板其他版本的 `is_published` 置为 `False`，保证同一模板最多一个发布版本
- 发布某个版本时：同样会取消其他版本的发布标记

## 3. 管理 API

### 3.1 模板 CRUD

- `GET /api/admin/document-templates`
- `POST /api/admin/document-templates`
- `PUT /api/admin/document-templates/{template_id}`

关键约束：

- 创建时 `key` 去重：重复会返回 409

### 3.2 版本管理

- `GET /api/admin/document-templates/{template_id}/versions`
- `POST /api/admin/document-templates/{template_id}/versions`

  - 入参：`{ content: string, publish: boolean }`
  - `version` 自动递增（`max(version)+1`）

- `POST /api/admin/document-templates/{template_id}/versions/{version_id}/publish`

## 4. 与文书生成的联动

文书生成接口 `POST /api/documents/generate` 会：

- 按 `template_key` 查找 `document_templates(key, is_active=true)`
- 读取最新的已发布版本（`is_published=true` 且 `version desc limit 1`）
- 若找不到发布版本，则 fallback 到内置模板

详见：`docs/modules/DOCUMENTS.md`。

## 5. 常见问题

- **模板创建成功但 types 列表不展示**

  - `GET /api/documents/types` 只会返回“存在发布版本”的模板
  - 需要创建并发布一个版本

- **发布版本切换后生成仍使用旧内容**
  - 生成逻辑每次查询最新发布版本，通常不会缓存；若出现异常，优先检查 DB 写入是否成功

## 6. 关联文档

- 文书生成：`docs/modules/DOCUMENTS.md`
- 模块索引：`docs/modules/INDEX.md`
