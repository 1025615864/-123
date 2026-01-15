# 客服反馈与工单（FEEDBACK）

本模块提供“用户提交反馈工单 + 管理员处理/指派/统计”的能力。

Router：`backend/app/routers/feedback.py`（prefix：`/feedback`，实际对外：`/api/feedback/*`）

前端入口：

- 用户：`frontend/src/pages/FeedbackPage.tsx`（路由：`/feedback`）
- 管理后台：`frontend/src/pages/admin/FeedbackTicketsPage.tsx`（路由：`/admin/feedback`）

## 1. 数据模型

表：`feedback_tickets`

Model：`backend/app/models/feedback.py:FeedbackTicket`

- `user_id`：提交人
- `subject/content`
- `status`：字符串状态（见下文允许值）
- `admin_reply`：管理员回复（可空）
- `admin_id`：处理管理员（可空）
- `created_at/updated_at`

允许状态（router 常量）：

- `open`：待处理
- `processing`：处理中
- `closed`：已关闭

## 2. 用户侧 API（需要登录）

- `POST /api/feedback`

  - 提交工单
  - 初始状态固定为 `open`

- `GET /api/feedback?page=&page_size=`
  - 获取“我的工单”列表

## 3. 管理员侧 API（需要管理员）

### 3.1 统计

- `GET /api/feedback/admin/tickets/stats`

返回：

- `total/open/processing/closed/unassigned`
- `unassigned` 判定：`admin_id IS NULL`

### 3.2 列表

- `GET /api/feedback/admin/tickets?page=&page_size=&status=&keyword=`

筛选：

- `status`：精确匹配
- `keyword`：`subject/content/admin_reply` 上做 `ilike` 模糊查询

### 3.3 更新（回复/状态/指派）

- `PUT /api/feedback/admin/tickets/{ticket_id}`

支持字段：

- `status`：必须在 `{open, processing, closed}`
- `admin_reply`：写入回复
- `admin_id`：指派管理员

重要约束（避免“互相甩锅”）：

- 当前实现仅允许“指派给自己”
  - `admin_id` 若传非自己 id，会返回 400：`目前仅支持指派给自己`
- 当写入 `admin_reply` 且非空，会自动写 `admin_id=current_user.id`

## 4. 典型处理流程（建议）

- 用户创建工单：`status=open, admin_id=NULL`
- 管理员点击“指派给我”：写 `admin_id=me`
- 管理员回复并将状态改为 `processing`
- 处理完成后将状态改为 `closed`

## 5. 常见问题

- **工单一直显示未分配**：管理员未写 `admin_id`；或仅写了空回复
- **无法指派给其他管理员**：当前后端硬限制，仅支持指派给自己（产品策略）

## 6. 关联文档

- 管理后台统计/导出：`docs/modules/ADMIN_CONSOLE.md`
- 权限与角色：`docs/modules/BACKEND_INFRA.md`
