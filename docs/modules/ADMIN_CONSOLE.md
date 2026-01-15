# 管理后台统计与导出（ADMIN_CONSOLE）

本模块提供管理后台的“统计看板 + CSV 数据导出”能力。

Router：`backend/app/routers/admin.py`（prefix：`/admin`，实际对外：`/api/admin/*`）

前端入口：

- 管理后台路由：`frontend/src/App.tsx`（`/admin/*`）
- 统计看板：`frontend/src/pages/admin/DashboardPage.tsx`

## 1. 权限

所有接口均需要管理员：`require_admin`。

## 2. 统计 API

- `GET /api/admin/stats`

统计项（当前实现）：

- 用户数：`users`
- 新闻数：`news`
- 帖子数：`posts`
- 评论数：`comments`
- AI 咨询数：`consultations`
- 律所数：`lawfirms`

## 3. CSV 导出 API

导出接口均返回：

- `Content-Type: text/csv; charset=utf-8-sig`
- `Content-Disposition: attachment; filename=<...>.csv`

并在 CSV 内容开头写入 BOM（`\ufeff`），以提升 Excel 兼容性。

### 3.1 用户

- `GET /api/admin/export/users?format=csv`

### 3.2 帖子

- `GET /api/admin/export/posts`

### 3.3 新闻

- `GET /api/admin/export/news`

### 3.4 律所

- `GET /api/admin/export/lawfirms`

### 3.5 知识库

- `GET /api/admin/export/knowledge`

注意：为了避免 CSV 过大，当前只导出 `content` 的前 200 字符作为 preview。

### 3.6 AI 咨询记录

- `GET /api/admin/export/consultations`

实现要点：

- 以 `Consultation` left join `User` + `ChatMessage` 聚合得到 `message_count`
- 采用 `generate_csv_stream()` 流式输出，避免一次性加载全量数据

## 4. 性能与一致性注意事项

- 多数导出采用 offset+limit 分批读取，适合中等数据量
- 超大数据量建议：
  - 改用 keyset pagination（按 id 游标）
  - 或走离线任务生成文件后再下载

## 5. 关联文档

- 知识库：`docs/modules/KNOWLEDGE.md`
- 论坛：`docs/modules/FORUM.md`
- 新闻：`docs/modules/NEWS_AI.md`
- 模块索引：`docs/modules/INDEX.md`
