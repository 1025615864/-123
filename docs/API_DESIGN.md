# API 设计文档

## 一、总览

- **后端框架**：FastAPI
- **统一前缀**：`/api`（见 `backend/app/main.py`）
- **在线文档**：
  - Swagger UI：`http://localhost:8000/docs`
  - ReDoc：`http://localhost:8000/redoc`

> 本文档作为“AI 编程友好”的 API 汇总口径：描述鉴权、模块边界与关键接口。**以 Swagger 为最终权威**。

---

## 二、认证与权限

### 2.1 JWT Bearer

- 登录成功后，token 位于响应 `token.access_token`。
- 请求需在 header 中携带：

```http
Authorization: Bearer <token>
```

### 2.2 角色

- 普通用户：`role=user`
- 律师：`role=lawyer`（部分接口还要求认证通过）
- 管理员：`role=admin/super_admin`

---

## 三、通用约定

### 3.1 错误码与错误结构

- 多数接口使用 FastAPI 默认错误结构：
  - `{"detail": "..."}`
- AI 相关接口会返回带 `error_code` 的结构（并附 `X-Request-Id`、`X-Error-Code`）：

```json
{
  "error_code": "AI_NOT_CONFIGURED",
  "message": "...",
  "detail": "...",
  "request_id": "..."
}
```

### 3.2 常用状态码

| 状态码 | 含义                         |
| ------ | ---------------------------- |
| 200    | 成功                         |
| 400    | 参数错误/业务校验失败        |
| 401    | 未登录                       |
| 403    | 无权限                       |
| 404    | 资源不存在                   |
| 409    | 冲突（如唯一键冲突）         |
| 422    | 校验失败（FastAPI/Pydantic） |
| 429    | 限流/配额不足                |
| 500    | 服务器异常                   |
| 503    | 服务不可用（如 AI 未配置）   |

### 3.3 可选响应 Envelope（兼容式）

为逐步降低前端适配成本，后端支持通过请求头开启统一响应 envelope：

- 请求头：`X-Api-Envelope: 1`
- 仅对 **2xx 且 JSON** 响应生效（非 JSON/非 2xx 不包装）
- 包装后结构：

```json
{
  "ok": true,
  "data": "<原始响应体>",
  "ts": 1730000000
}
```

兼容性说明：

- 不带该 header 的调用方不会受到影响（保持原始响应结构）。
- 前端 axios 默认带该 header，并在拦截器中自动解包回原始 `data`，因此业务代码通常无需修改。

### 3.4 Swagger 文档要求（强约束）

- **新增接口必须补齐 `tags` 与 `summary`**（FastAPI 装饰器参数），以便 Swagger/ReDoc 可检索、可读。
- 推荐同时补齐：
  - `response_model`（或明确返回结构）
  - 关键业务校验失败的 `HTTPException(status_code=400, detail=...)` 文案

### 3.5 Secrets 不入库（SystemConfig 约束）

- `SystemConfig` 仅用于保存**非敏感**的功能开关、展示文案、阈值等。
- 禁止保存：`api_key` / `secret` / `token` / `password` / `private_key` 等敏感信息。
- 敏感信息必须通过环境变量/Secret Manager 注入（例如 `OPENAI_API_KEY`）。
- 相关写接口在 `/api/system/configs` 已做服务端校验（保存敏感 key/value 会返回 400）。

---

## 四、模块接口

> 说明：这里只列“主干接口”。管理后台与 News 模块接口较多，建议结合 Swagger 查看完整参数。

### 4.1 健康检查

- `GET /health`
- `GET /api/health`
- `GET /health/detailed`

### 4.2 用户（/api/user）

- `POST /api/user/register`：注册
- `POST /api/user/login`：登录
- `GET /api/user/me`：当前用户
- `PUT /api/user/me`：更新资料（不允许直接改手机号）
- `PUT /api/user/me/password`：修改密码（要求邮箱验证）
- `GET /api/user/me/quotas`：配额
- `GET /api/user/me/quota-usage`：配额消耗记录（按天）
- `POST /api/user/email-verification/request`：请求验证邮件
- `GET /api/user/email-verification/verify`：验证邮箱
- `POST /api/user/sms/send`：发送短信验证码（开发环境回传 code）
- `POST /api/user/sms/verify`：校验验证码并绑定手机号

管理员：

- `GET /api/user/admin/list`
- `PUT /api/user/admin/{user_id}/toggle-active`
- `PUT /api/user/admin/{user_id}/role`

客服反馈（管理员）：

- `GET /api/feedback/admin/tickets`：工单列表
- `PUT /api/feedback/admin/tickets/{ticket_id}`：回复/状态/指派（目前仅支持指派给自己）
- `GET /api/feedback/admin/tickets/stats`：工单统计（按状态/未分配）

### 4.3 AI 法律助手（/api/ai）

- `POST /api/ai/chat`：同步聊天
- `POST /api/ai/chat/stream`：SSE 流式聊天

> 咨询历史、分享、导出、评价等接口以 Swagger 为准。

### 4.4 论坛（/api/forum）

- `GET /api/forum/posts`：帖子列表
- `POST /api/forum/posts`：发帖（登录）
- `GET /api/forum/posts/{post_id}`：帖子详情
- `PUT /api/forum/posts/{post_id}`：编辑（作者/管理员）
- `DELETE /api/forum/posts/{post_id}`：删除（软删）
- `POST /api/forum/posts/{post_id}/restore`：恢复
- `DELETE /api/forum/posts/{post_id}/purge`：永久删除
- `POST /api/forum/posts/{post_id}/like`：点赞/取消
- `POST /api/forum/posts/{post_id}/favorite`：收藏/取消
- `GET /api/forum/favorites`：我的收藏
- `POST /api/forum/posts/{post_id}/comments`：评论
- `GET /api/forum/posts/{post_id}/comments`：评论列表

管理员：

- `GET /api/forum/admin/review-config`、`PUT /api/forum/admin/review-config`
- `GET /api/forum/admin/post-review-config`、`PUT /api/forum/admin/post-review-config`
- `GET /api/forum/admin/content-filter-config`、`PUT /api/forum/admin/content-filter-config`

### 4.5 新闻（/api/news）

公开消费：

- `GET /api/news`
- `GET /api/news/recommended`
- `GET /api/news/hot`
- `GET /api/news/top`
- `GET /api/news/recent`
- `GET /api/news/categories`
- `GET /api/news/topics`、`GET /api/news/topics/{topic_id}`

用户：

- `POST /api/news/subscriptions`、`GET /api/news/subscriptions`、`DELETE /api/news/subscriptions/{sub_id}`
- `GET /api/news/subscribed`
- `GET /api/news/history`

管理员（节选）：

- `GET/POST/PUT/DELETE /api/news/admin/sources...`：RSS 来源管理
- `POST /api/news/admin/sources/{source_id}/ingest/run-once`：手动采集
- `GET /api/news/admin/ingest-runs`：采集记录
- `POST /api/news/admin/{news_id}/ai/rerun`：手动触发 News AI

### 4.6 律所服务（/api/lawfirm）

- `GET /api/lawfirm/firms`、`GET /api/lawfirm/firms/{firm_id}`
- `GET /api/lawfirm/lawyers`、`GET /api/lawfirm/lawyers/{lawyer_id}`
- `POST /api/lawfirm/consultations`：用户预约咨询（可能生成支付订单）
- `GET /api/lawfirm/consultations`：我的预约
- `GET /api/lawfirm/lawyer/consultations`：律师侧咨询列表
- `POST /api/lawfirm/lawyer/consultations/{id}/accept|reject|complete`

管理员：

- `GET/PUT/DELETE /api/lawfirm/admin/firms...`

### 4.7 支付（/api/payment）

- `GET /api/payment/pricing`：价格表（VIP/次数包）
- `POST /api/payment/orders`：创建订单
- `POST /api/payment/orders/{order_no}/pay`：发起支付

> 回调/验签/对账/回调事件审计等接口以 Swagger 为准。

### 4.8 通知（/api/notifications）

- `GET /api/notifications`：列表
- `GET /api/notifications/unread-count`
- `PUT /api/notifications/{id}/read`、`PUT /api/notifications/read-all`
- `POST /api/notifications/batch-read`、`POST /api/notifications/batch-delete`

管理员：

- `POST /api/notifications/admin/broadcast`
- `GET /api/notifications/admin/system`

### 4.9 系统（/api/system）

- `GET /api/system/configs`、`PUT /api/system/configs/{key}`、`POST /api/system/configs/batch`
- `GET /api/system/logs`
- `GET /api/system/metrics`
- `GET /api/system/news-ai/status`（管理员）
- `GET /api/system/ai/status`（管理员）

### 4.10 上传（/api/upload）

- `POST /api/upload/avatar`：上传头像
- `POST /api/upload/image`：上传图片
- `POST /api/upload/file`：上传附件
- `GET /api/upload/avatars/{filename}` / `images/{filename}` / `files/{filename}`

### 4.11 搜索（/api/search）

- `GET /api/search?q=...`
- `GET /api/search/suggestions?q=...`
- `GET /api/search/hot`
- `GET /api/search/history`
- `DELETE /api/search/history`

### 4.12 文书（/api/documents）

- `POST /api/documents/generate`：生成（游客/登录均可，按配额/限流）
- `GET /api/documents/types`
- `POST /api/documents/save`：保存（登录）
- `GET /api/documents/my`、`GET /api/documents/my/{doc_id}`、`DELETE /api/documents/my/{doc_id}`

说明：

- 文书生成支持模板版本追溯：生成/保存记录包含 `template_key` / `template_version`。

管理员：

- `GET /api/admin/document-templates`：模板列表
- `GET /api/admin/document-templates/{template_id}/versions`：版本列表
- `POST /api/admin/document-templates/{template_id}/versions`：新增版本
- `POST /api/admin/document-templates/{template_id}/versions/{version}/publish`：发布指定版本

### 4.13 日历（/api/calendar）

- `POST /api/calendar/reminders`
- `GET /api/calendar/reminders`
- `PUT /api/calendar/reminders/{id}`
- `DELETE /api/calendar/reminders/{id}`

### 4.14 反馈（/api/feedback）

- `POST /api/feedback`
- `GET /api/feedback`

管理员：

- `GET /api/feedback/admin/tickets`
- `PUT /api/feedback/admin/tickets/{ticket_id}`

### 4.15 律师结算（/api）

> 结算路由未统一 `prefix`，但整体仍挂载在 `/api` 下。

律师：

- `GET /api/lawyer/wallet`
- `GET /api/lawyer/income-records`
- `GET /api/lawyer/bank-accounts`、`POST/PUT/DELETE ...`
- `GET /api/lawyer/withdrawals`、`POST /api/lawyer/withdrawals`

管理员：

- `GET /api/admin/withdrawals`、`GET /api/admin/withdrawals/export`

### 4.16 管理后台（/api/admin）

- `GET /api/admin/stats`
- `GET /api/admin/export/*`：导出 users/posts/news/lawfirms/knowledge/consultations

### 4.17 WebSocket

- `WS /ws`：支持 `Authorization: Bearer` 或 `?token=`
- `GET /ws/status`

---

## 五、兼容性与演进建议

- 建议逐步统一接口响应 envelope（如 `{items,total,page,...}`）与错误结构，降低前端适配成本。
- 对外发布接口时建议增加版本前缀（如 `/api/v1`）并固定字段语义。
