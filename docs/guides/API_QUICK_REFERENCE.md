# API 速查（API_QUICK_REFERENCE）

## 1. Base URL

- 本地后端：`http://127.0.0.1:8000`
- API 前缀：`/api`

示例：

- `GET /api/health`

## 2. 认证

使用 JWT Bearer Token：

- `Authorization: Bearer <token>`

获取 token：

- `POST /api/user/login`

## 3. 响应 Envelope（可选）

如果请求带：

- `X-Api-Envelope: 1`

则 2xx JSON 响应会被包装为：

- `{ "ok": true, "data": <payload>, "ts": <unix_ts> }`

前端 axios client 默认会携带该 header，并自动解包。

## 4. WebSocket

- 路径：`/ws`
- 连接：`ws(s)://<host>/ws?token=<jwt>`

前端默认连接：

- `ws(s)://<当前页面 host>/ws`

## 4.1 Request-Id

- 请求可携带：`X-Request-Id`
- 响应会回传：`X-Request-Id`

后端实现：`backend/app/middleware/request_id_middleware.py`

## 5. 常用接口（按模块）

### 5.1 用户

- `POST /api/user/register`
- `POST /api/user/login`
- `GET /api/user/me`（需要登录）

### 5.2 新闻

- `GET /api/news`（列表）
- `GET /api/news/{id}`（详情）
- `GET /api/news/topics` / `GET /api/news/topics/{topic_id}`

管理员：

- `GET /api/news/admin/sources`
- `POST /api/news/admin/sources`
- `POST /api/news/admin/sources/{source_id}/ingest/run-once`
- `GET /api/news/admin/ingest-runs`

### 5.3 论坛

- `GET /api/forum/posts`
- `POST /api/forum/posts`（需要登录）
- `POST /api/forum/posts/{post_id}/comments`（需要登录；可能触发审核）

### 5.4 律所/律师

- `GET /api/lawfirm/firms`
- `GET /api/lawfirm/firms/{id}`

律师咨询预约（部分常用）：

- `POST /api/lawfirm/consultations`（需要登录；可能返回 `payment_order_no`）
- `GET /api/lawfirm/consultations`（需要登录）
- `POST /api/lawfirm/consultations/{consultation_id}/cancel`（需要登录；仅余额支付可自动退款）
- `GET /api/lawfirm/consultations/{consultation_id}/messages`（需要登录）
- `POST /api/lawfirm/consultations/{consultation_id}/messages`（需要登录）

律师侧：

- `GET /api/lawfirm/lawyer/consultations`（需要登录）
- `POST /api/lawfirm/lawyer/consultations/{consultation_id}/accept`
- `POST /api/lawfirm/lawyer/consultations/{consultation_id}/reject`
- `POST /api/lawfirm/lawyer/consultations/{consultation_id}/complete`

### 5.5 AI 法律咨询（AI）

- `POST /api/ai/chat`（对话）
- `POST /api/ai/chat/stream`（SSE 流式）
- `GET /api/ai/consultations`（我的会话列表）
- `GET /api/ai/consultations/{session_id}`（会话详情）
- `POST /api/ai/consultations/{session_id}/share`
- `GET /api/ai/share/{token}`（分享访问）
- `GET /api/ai/consultations/{session_id}/export`
- `GET /api/ai/consultations/{session_id}/report?format=pdf`
- `POST /api/ai/transcribe`（语音转写）
- `POST /api/ai/files/analyze`（文件分析）
- `POST /api/ai/quick-replies`（快捷追问）
- `POST /api/ai/messages/rate`（评价 AI 回复）

### 5.6 搜索

- `GET /api/search?q=<keyword>`
- `GET /api/search/suggestions?q=<keyword>`
- `GET /api/search/hot`
- `GET /api/search/history` / `DELETE /api/search/history`

### 5.7 支付

- `POST /api/payment/orders`（创建订单）
- `POST /api/payment/orders/{order_no}/pay`（发起支付）
- `POST /api/payment/webhook`（支付回调）

补充：

- `POST /api/payment/alipay/notify`（支付宝异步通知，RSA2 验签）
- `POST /api/payment/wechat/notify`（微信支付回调，平台证书验签）
- `GET /api/payment/channel-status`（公开：可用支付方式）

管理员：

- `GET /api/payment/admin/channel-status`
- `GET /api/payment/admin/callback-events`
- `GET /api/payment/admin/reconcile/{order_no}`
- `POST /api/payment/admin/env`（写入 env 文件并热加载；仅允许白名单 key）

### 5.8 结算与提现

- 律师：
  - `GET /api/settlement/lawyer/wallet`
  - `GET /api/settlement/lawyer/income-records`
  - `GET /api/settlement/lawyer/withdrawals`
  - `GET /api/settlement/lawyer/withdrawals/{withdrawal_id}`
  - `POST /api/settlement/lawyer/withdrawals`
- 管理员：
  - `GET /api/settlement/admin/withdrawals`
  - `GET /api/settlement/admin/withdrawals/export`
  - `GET /api/settlement/admin/withdrawals/{withdrawal_id}`
  - `POST /api/settlement/admin/withdrawals/{withdrawal_id}/approve`
  - `POST /api/settlement/admin/withdrawals/{withdrawal_id}/reject`
  - `POST /api/settlement/admin/withdrawals/{withdrawal_id}/complete`
  - `POST /api/settlement/admin/withdrawals/{withdrawal_id}/fail`
  - `POST /api/settlement/admin/settlement/run`

### 5.9 律师复核（Reviews）

- 用户：`GET /api/reviews/consultations/{consultation_id}`
- 律师：
  - `GET /api/reviews/lawyer/tasks`
  - `POST /api/reviews/lawyer/tasks/{task_id}/claim`
  - `POST /api/reviews/lawyer/tasks/{task_id}/submit`

### 5.10 通知

- `GET /api/notifications`（需要登录）
- `GET /api/notifications/unread-count`
- `PUT /api/notifications/read-all`
- `PUT /api/notifications/{notification_id}/read`
- `DELETE /api/notifications/{notification_id}`

- `POST /api/notifications/batch-read`
- `POST /api/notifications/batch-delete`

- `GET /api/notifications/types`

管理员：

- `POST /api/notifications/admin/broadcast`
- `GET /api/notifications/admin/system`

### 5.11 上传

- `POST /api/upload/avatar`
- `POST /api/upload/image`
- `POST /api/upload/file`

- `GET /api/upload/avatars/{filename}`
- `GET /api/upload/images/{filename}`
- `GET /api/upload/files/{filename}`

### 5.12 系统配置与运维（管理员）

- `GET /api/system/configs`
- `PUT /api/system/configs/{key}`
- `POST /api/system/configs/batch`

- `GET /api/system/news-ai/status`
- `GET /api/system/ai/status`
- `GET /api/system/metrics`

### 5.13 管理后台

- `GET /api/admin/stats`（管理员）
- `GET /api/admin/export/*`（管理员导出 CSV）

### 5.14 文书生成

- `POST /api/documents/generate`（生成；游客可用但有 IP 限制）
- `GET /api/documents/types`（获取支持类型）
- `POST /api/documents/export/pdf`（PDF 导出；reportlab 缺失会 501）

需要登录：

- `POST /api/documents/save`
- `GET /api/documents/my`
- `GET /api/documents/my/{doc_id}`
- `GET /api/documents/my/{doc_id}/export?format=pdf`
- `DELETE /api/documents/my/{doc_id}`

### 5.15 文书模板管理（管理员）

- `GET /api/admin/document-templates`
- `POST /api/admin/document-templates`
- `PUT /api/admin/document-templates/{template_id}`
- `GET /api/admin/document-templates/{template_id}/versions`
- `POST /api/admin/document-templates/{template_id}/versions`
- `POST /api/admin/document-templates/{template_id}/versions/{version_id}/publish`

### 5.16 合同审查

- `POST /api/contracts/review`（上传合同文件，返回 JSON+Markdown 报告）

### 5.17 知识库（管理员）

- `GET /api/knowledge/stats`
- `GET /api/knowledge/laws`
- `POST /api/knowledge/laws`
- `PUT /api/knowledge/laws/{knowledge_id}`
- `DELETE /api/knowledge/laws/{knowledge_id}`

- `POST /api/knowledge/laws/batch-import`（支持 dry_run）
- `POST /api/knowledge/laws/batch-delete`
- `POST /api/knowledge/laws/batch-vectorize`
- `POST /api/knowledge/sync-vector-store`

### 5.18 法律日历

- `POST /api/calendar/reminders`
- `GET /api/calendar/reminders`
- `PUT /api/calendar/reminders/{reminder_id}`
- `DELETE /api/calendar/reminders/{reminder_id}`

### 5.19 客服反馈与工单

用户（需要登录）：

- `POST /api/feedback`
- `GET /api/feedback`

管理员：

- `GET /api/feedback/admin/tickets/stats`
- `GET /api/feedback/admin/tickets`
- `PUT /api/feedback/admin/tickets/{ticket_id}`

## 6. 重要环境变量（与 API 行为相关）

- `DEBUG`：生产模式为 false，会启用安全校验与强依赖（Redis、密钥长度、Alembic head）
- `REDIS_URL`：生产必需；也影响限流与周期任务
- `REVIEW_TASK_SLA_JOB_ENABLED` / `REVIEW_TASK_SLA_SCAN_INTERVAL_SECONDS`：律师复核 SLA 扫描

## 7. 429 的两种来源（排障提示）

- 全局 IP 限流（中间件）：通常提示“每秒请求过多/请求过于频繁”
- 业务配额（Quota）：通常提示“今日 AI 咨询次数已用尽/今日文书生成次数已用尽”
