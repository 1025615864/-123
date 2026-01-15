# 法律日历（CALENDAR）

本模块提供“用户自定义法律事项提醒”的 CRUD 能力。

Router：`backend/app/routers/calendar.py`（prefix：`/calendar`，实际对外：`/api/calendar/*`）

前端入口：

- 日历页：`frontend/src/pages/CalendarPage.tsx`

## 1. 数据模型

表：`calendar_reminders`

Model：`backend/app/models/calendar.py:CalendarReminder`

- `user_id`：归属用户
- `title/note`
- `due_at`：到期时间（必填）
- `remind_at`：提醒时间（可选）
- `is_done/done_at`：完成状态
- `created_at/updated_at`

## 2. 权限与数据隔离

所有接口均要求登录：`get_current_user`。

并且对 reminder 做 owner 校验（服务端强制）：

- `CalendarReminder.user_id == current_user.id`

## 3. API

- `POST /api/calendar/reminders`

  - 创建提醒

- `GET /api/calendar/reminders?page=&page_size=&done=&from_at=&to_at=`

  - 列表
  - `done` 支持 true/false；为空表示不筛选
  - `from_at/to_at` 用于按 due_at 时间窗筛选

- `PUT /api/calendar/reminders/{reminder_id}`

  - 更新（局部更新）
  - 支持更新 `title/note/due_at/remind_at/is_done`

- `DELETE /api/calendar/reminders/{reminder_id}`

## 4. 状态机与边界条件

### 4.1 完成状态切换

当 `PUT` 传入 `is_done` 时：

- `is_done: true`：

  - 若 `done_at` 为空则写入当前时间（UTC）

- `is_done: false`：
  - `done_at` 会被清空

### 4.2 排序与分页

- 列表排序：`due_at asc, id asc`
- `page_size` 最大 100

## 5. 生产建议

- 如需“到点提醒通知”：当前后端仅存储 `remind_at`，未实现定时触发通知。
  - 可扩展 periodic job：扫描 `remind_at <= now && !is_done` 的记录，并写入 Notification。

## 6. 关联文档

- 通知：`docs/modules/NOTIFICATIONS.md`
- 后端基础设施：`docs/modules/BACKEND_INFRA.md`
