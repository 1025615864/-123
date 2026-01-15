# 通知模块（NOTIFICATIONS）

本模块描述通知数据模型、用户通知 API、管理员广播，以及通知与 WebSocket 的联动。

## 1. 数据模型

- Model：`backend/app/models/notification.py:Notification`
- 表：`notifications`

关键字段：

- `user_id`
- `type`：`comment_reply/post_like/post_favorite/post_comment/system/consultation/news/...`
- `title/content/link`
- `dedupe_key`：用于去重
- `is_read`
- `related_user_id/related_post_id/related_comment_id`

去重约束：

- unique：`(user_id, type, dedupe_key)`（`uq_notifications_user_type_dedupe_key`）

## 2. 用户通知 API（/api/notifications）

实现：`backend/app/routers/notification.py`

- `GET /api/notifications`

  - 参数：`page/page_size/unread_only/notification_type`
  - 返回：`items/total/unread_count`

- `GET /api/notifications/unread-count`
- `PUT /api/notifications/{notification_id}/read`
- `PUT /api/notifications/read-all`
- `DELETE /api/notifications/{notification_id}`

批量操作：

- `POST /api/notifications/batch-read`
- `POST /api/notifications/batch-delete`

统计：

- `GET /api/notifications/types`

实现细节提示：

- `GET /api/notifications` 为了返回 `related_user_name`，会对每条记录额外查一次 `users`（N+1）。如果后续通知量大，可以在 service 层做 join 优化。

## 3. 管理员广播（系统通知）

- `POST /api/notifications/admin/broadcast`

  - 会对所有 `users.is_active=true` 批量插入 `Notification(type=system)`
  - 然后尝试通过 WebSocket 广播：`websocket_service.broadcast_system_message()`

- `GET /api/notifications/admin/system`
  - 返回系统通知发送记录（通过“title + 分钟级时间”做去重展示）

## 4. 通知来源（常见）

- 论坛审核：`backend/app/routers/forum.py`

  - 用户发帖/评论触发审核时，会插入 `Notification(type=system)`

- 律师复核 SLA：`review_task_sla_service`

  - 使用 `dedupe_key=review_task:{task_id}:{kind}:{due_at.iso}` 避免重复提醒

- 其它业务（咨询/新闻订阅/点赞/评论等）会在对应 service/router 中插入。

## 5. WebSocket 与前端联动

前端接入点：

- `frontend/src/components/Layout.tsx`
  - 登录后建立 `/ws` 连接
  - 收到 `msg.type === "notification"` 时：
    - `queryClient.invalidateQueries(queryKeys.notificationsPreview(10))`
    - 以及若干兼容 key 的 invalidate

Hook：

- `frontend/src/hooks/useWebSocket.ts`
  - URL 推导：优先 `VITE_API_BASE_URL`，否则用 `window.location.host`
  - 自动重连：最多 5 次，间隔 3s
  - 心跳：30s `ping`，服务端回 `pong`

## 6. 开发者建议

- 对于“可能重复触发”的通知（例如周期任务/回调），优先使用 `dedupe_key` + DB unique 约束去重。
- 对于“需要实时更新 UI”的通知，确保 WebSocket 推送的 `type` 与前端判断一致（当前前端只对 `notification` 类型做刷新）。
