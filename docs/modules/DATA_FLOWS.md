# 端到端数据流（DATA_FLOWS）

本文件面向开发者，按“请求 → 中间件/依赖 → DB/缓存/锁 → 通知/WS → 前端缓存刷新”的路径，解释项目中最关键的端到端数据流与关键表映射。

相关模块文档：

- `docs/modules/BACKEND_INFRA.md`
- `docs/modules/FRONTEND_ARCH.md`
- `docs/modules/PAYMENT.md`
- `docs/modules/SETTLEMENT.md`
- `docs/modules/REVIEWS_SLA.md`
- `docs/modules/FORUM.md`
- `docs/modules/NOTIFICATIONS.md`
- `docs/modules/UPLOAD_STORAGE.md`

## 1. 通用请求路径（绝大多数 REST API）

### 1.1 浏览器 → 前端 axios → 后端

- 前端：`frontend/src/api/client.ts`

  - 追加 `Authorization: Bearer <token>`（若已登录）
  - 追加 `X-Api-Envelope: 1`（启用 envelope）
  - 追加 `X-Request-Id`（链路 id）

- 后端：`backend/app/main.py`
  - 一系列 middleware（日志/RequestId/AuthContext/RateLimit/Envelope 等）
  - 路由 `APIRouter` 在 `/api` 下

### 1.2 关键中间件（调试/排障时最常用）

- `RequestIdMiddleware`：

  - 读取或生成 `request.state.request_id`
  - 写回响应 `X-Request-Id`

- `AuthContextMiddleware`：

  - 仅解码 JWT，写入 `request.state.user_id`
  - 主要给“按用户限流/日志”等横切能力使用

- `EnvelopeMiddleware`：

  - 请求带 `X-Api-Envelope: 1` 时，将 2xx JSON 响应包装为 `{ok,data,ts}`
  - 前端 axios 拦截器会自动解包

- `RateLimitMiddleware`（全局 IP 限流）：
  - 返回 429 + `Retry-After`

## 2. AI 法律咨询（/api/ai/chat）

### 2.1 流程

1. `POST /api/ai/chat`
2. `@rate_limit(*RateLimitConfig.AI_CHAT, by_ip=True)`（按 IP 装饰器限流）
3. 配额：
   - 登录用户：`QuotaService.enforce_ai_chat_quota()`（表：`user_quota_daily`）
   - 游客：`GUEST_AI_LIMIT/GUEST_AI_WINDOW_SECONDS`（窗口计数）
4. 调用 assistant（LLM/检索策略）
5. 落库：
   - `consultations`（如 session 首次出现）
   - `chat_messages`（user + assistant 两条）
   - assistant message 的 `references` 字段写入 JSON（references + meta）
6. 成功后对登录用户记录 quota 消耗：`QuotaService.record_ai_chat_usage()`

### 2.2 关键表/字段

- `consultations.session_id`（字符串）
- `chat_messages.role in {user, assistant}`
- `chat_messages.references`（JSON string，含 prompt_version/request_id 等 meta）
- `user_quota_daily.ai_chat_count`

## 3. 律师咨询预约（/api/lawfirm/consultations）

### 3.1 流程（用户预约 → 支付 → 律师接单 → 完成 → 结算）

1. 用户：`POST /api/lawfirm/consultations`
2. 创建 `lawyer_consultations` 记录
3. 若律师设置 `consultation_fee>0`：创建 `payment_orders`
   - `order_type="consultation"`
   - `related_type="lawyer_consultation"`
   - `related_id=<consultation.id>`
4. 用户完成支付（见支付回调链路）
5. 律师：`POST /api/lawfirm/lawyer/consultations/{id}/accept`
   - 若订单仍 pending：拒绝（"用户尚未完成支付"）
6. 律师：`POST /api/lawfirm/lawyer/consultations/{id}/complete`
7. 结算侧：`settlement_service.ensure_income_record_for_completed_consultation()`
   - 创建/补齐 `lawyer_income_records`（pending → freeze 到期后 settled）

### 3.2 关键表

- `lawyer_consultations` / `lawyer_consultation_messages`
- `payment_orders`
- `lawyer_income_records` / `lawyer_wallets`

### 3.3 结算与提现（冻结期 → 提现 → 分摊）

本段补齐“收入记录 pending → settled → withdrawn”以及“提现申请 pending → approved/rejected → completed/failed”的闭环。

1. 收入记录创建：

   - 律师预约咨询完成：`/api/lawfirm/lawyer/consultations/{id}/complete`
   - 复核任务提交：`/api/reviews/lawyer/tasks/{task_id}/submit`
   - 结算侧会创建 `lawyer_income_records(status=pending, settle_time=now+freeze_days)` 并把金额累计到 `lawyer_wallets.pending_amount/total_income`。

2. 冻结期到期结算（pending -> settled）：

   - 周期任务入口：`backend/app/main.py` 中 `PeriodicLockedRunner`
     - lock_key：`locks:settlement`
     - 开关：`SETTLEMENT_JOB_ENABLED`（或 DEBUG=true）
     - 扫描间隔：`SETTLEMENT_JOB_INTERVAL_SECONDS`（默认 3600）
   - 管理员手动触发：`POST /api/settlement/admin/settlement/run`
   - 逻辑：`settlement_service.settle_due_income_records()`
     - 扫描 `lawyer_income_records(status=pending && settle_time<=now)`
     - 将记录置为 `settled`
     - 从 `lawyer_wallets.pending_amount` 扣减对应金额（钱包字段最终由 `_recalc_wallet_fields()` 保持一致性）

3. 律师提交提现：`POST /api/settlement/lawyer/withdrawals`

   - 逻辑：`settlement_service.create_withdrawal_request()`
   - 校验：最小/最大金额、可用余额、收款账户存在且属于本人
   - 落库：`withdrawal_requests(status=pending)`
   - 钱包变化：`available_amount -= amount`，`frozen_amount += amount`

4. 管理员处理提现：

   - 通过：`POST /api/settlement/admin/withdrawals/{id}/approve`
     - `pending -> approved`（钱包金额不变，仅记录 admin_id/reviewed_at/remark）
   - 驳回：`POST /api/settlement/admin/withdrawals/{id}/reject`
     - `pending -> rejected`
     - 钱包：`frozen_amount -= amount`，`available_amount += amount`
   - 标记打款完成：`POST /api/settlement/admin/withdrawals/{id}/complete`
     - `approved -> completed`
     - 钱包：`frozen_amount -= amount`，`withdrawn_amount += amount`
     - 并尝试把提现金额“分摊”到 `lawyer_income_records`（按时间顺序），更新 `withdrawn_amount`，若单条记录被完全覆盖则置为 `withdrawn`
   - 标记失败：`POST /api/settlement/admin/withdrawals/{id}/fail`
     - `approved -> failed`
     - 钱包：`frozen_amount -= amount`，`available_amount += amount`

## 4. 支付回调（订单从 pending → paid）

### 4.1 流程

1. 第三方回调到：
   - `/api/payment/alipay/notify`（RSA2）
   - `/api/payment/wechat/notify`（平台证书验签）
   - `/api/payment/webhook`（HMAC，内部/简化渠道）
2. 验签/验密钥
3. 幂等与并发保护：
   - Redis 锁（`cache_service.acquire_lock()`）
   - DB unique：`payment_callback_events` 防止重复落库
4. 落库审计：`payment_callback_events`
5. 事务内更新：`payment_orders.status=paid` + 相关 side-effects

补充实现细节（来自 `payment.py`）：

- 回调幂等锁 key 形态：
  - `locks:payment_notify:alipay:{trade_no or order_no}`
  - `locks:payment_notify:wechat:{trade_no or order_no}`
  - `locks:payment_notify:ikunpay:{trade_no or order_no}`
- 回调审计的 trade_no 写入策略：仅当 `verified=true` 且 `error_message` 为空时才写 trade_no（否则写 NULL），用于避免失败回调触发唯一索引冲突。

### 4.2 关键表

- `payment_orders`：订单状态机
- `payment_callback_events`：回调审计（排障优先看这里）
- `user_balances` / `balance_transactions`：余额账本

### 4.3 用户发起支付（/api/payment/orders/{order_no}/pay）

该入口是“用户侧支付入口”，可能走余额支付或返回第三方 `pay_url`。

- 订单校验：
  - 必须属于当前用户（按 `order_no + user_id` 查）
  - `recharge` 订单禁止余额支付
  - 非 `pending`/已过期会直接返回错误（过期会落库为 cancelled）
- `wechat`：当前实现直接拒绝（"微信支付暂未开放"）
- `balance`：
  - 原子扣款（where 条件 `effective_balance_cents >= actual_amount_cents`）
  - 原子更新订单 `pending -> paid`
  - 记录 `balance_transactions(type=consume, amount 为负数)`
  - 同一事务执行副作用（VIP/次数包/咨询确认/复核任务创建）
- `alipay/ikunpay`：返回 `pay_url`，并会把 `order_no` 追加到 return_url query

## 5. 律师复核 SLA → 通知 → WebSocket → 前端刷新

### 5.1 流程

1. 律师端：`GET /api/reviews/lawyer/tasks`
2. 服务端根据 SystemConfig `CONSULT_REVIEW_SLA_JSON` 计算 `due_at/is_overdue`
3. 周期任务：`review_task_sla_service.scan_and_notify_review_task_sla()`
4. 插入通知：`notifications`
   - `type=system`
   - `dedupe_key=review_task:{task_id}:{kind}:{due_at.iso}`
5. 若插入成功：调用 `websocket_service.notify_user(... type=notification ...)`
6. 前端：`Layout.tsx` 收到 `msg.type === "notification"`
   - `react-query` invalidate notifications queries

补充：复核任务的创建与提交链路（与 payment/settlement 互相耦合）：

- 购买复核（创建订单）：`order_type=light_consult_review` + `related_type=ai_consultation` + `related_id=<consultation.id>`
- 支付成功后（回调或余额支付）：会尝试创建 `consultation_review_tasks(status=pending)`（按 `order_id` 查重）
- 律师提交复核：`POST /api/reviews/lawyer/tasks/{task_id}/submit`
  - 会校验关联订单必须为 `paid`
  - 提交成功后会触发结算入账：`settlement_service.ensure_income_record_for_paid_review_order()`

### 5.2 关键表

## 6. 论坛发帖/评论 → 审核 → 通知

### 6.1 流程（以发评论为例）

1. `POST /api/forum/posts/{post_id}/comments`
2. 内容过滤：`check_comment_content()` + `forum_service.apply_content_filter_config_from_db()`
3. `forum_service.create_comment()`
4. 若进入审核：`review_status=pending`（评论对外不可见，除非 include_unapproved 且为 owner/admin）
5. 给作者发通知：插入 `notifications(type=system)`，link 指向帖子的 comment 锚点
   - 当前实现**仅落库通知，不会通过 WebSocket 推送**（`forum.py` 内 `_create_notification()` 仅 `db.add()`）
6. 管理员审核：
   - `GET /api/forum/admin/pending-comments`
   - `POST /api/forum/admin/comments/{comment_id}/review`
7. 审核副作用：
   - 写 `AdminLog`
   - 调整 `posts.comment_count`（approve 增、reject/delete 扣）
   - 再次给用户发通知（通过/驳回/删除）

补充实现细节（来自 `forum.py` / `forum_service.py`）：

- 帖子审核：
  - `SystemConfig.forum.post_review.enabled` 控制是否开启
  - `SystemConfig.forum.post_review.mode in {all, rule}`
  - `rule` 模式下会对 `title+content` 做规则判定，命中才置 `review_status=pending`
- 评论审核：
  - `SystemConfig.forum.review.enabled` 控制是否开启
  - 命中规则时 `review_status=pending`，否则直接 `approved` 且会 `posts.comment_count + 1`
- 批量审核：
  - `POST /api/forum/admin/posts/review/batch`
  - `POST /api/forum/admin/comments/review/batch`
  - 对同一用户若数量较大，会合并成一条通知（title 带“（批量）”）

### 6.2 关键表

- `posts` / `comments`
- `notifications`
- `admin_logs`

## 7. 新闻定时发布/下架 → 订阅通知（scheduled_news）

### 7.1 流程

1. 周期任务：`backend/app/main.py` 中 `PeriodicLockedRunner`
   - lock_key：`locks:scheduled_news`
   - interval_seconds：固定 30s
2. 执行：`news_service.process_scheduled_news()`
   - publish：`News.is_published=false && scheduled_publish_at<=now && review_status==approved`
     - 置 `is_published=true`，`published_at=now`，`scheduled_publish_at=NULL`
   - unpublish：`News.is_published=true && scheduled_unpublish_at<=now`
     - 置 `is_published=false`，`scheduled_unpublish_at=NULL`
   - commit 后：`NewsService.invalidate_hot_cache()`
3. 对“发布成功”的新闻：调用 `notify_subscribers_on_publish()`
   - 插入 `notifications(type=news, dedupe_key=news:{news_id}, link=/news/{news_id})`
   - 采用 `on_conflict_do_nothing(user_id,type,dedupe_key)` 做去重
   - 当前实现**仅落库通知，不会通过 WebSocket 推送**

### 7.2 关键表

- `news`
- `news_subscriptions`
- `notifications`

## 8. 通知（API → WebSocket → 前端刷新）

### 8.1 API（REST）

- 用户侧：`/api/notifications`
  - `GET /api/notifications`：分页列表
  - `PUT /api/notifications/read-all`：全部已读
  - `PUT /api/notifications/{id}/read`：单条已读
- 管理员：
  - `POST /api/notifications/admin/broadcast`：给所有活跃用户创建系统通知

### 8.2 WebSocket（消息推送与前端刷新）

- WS server：`backend/app/services/websocket_service.py`
  - `MessageType.NOTIFICATION == "notification"`
  - `MessageType.SYSTEM == "system"`
- 前端刷新点：`frontend/src/components/Layout.tsx`
  - 仅当 `msg.type === "notification"` 时，会 `invalidateQueries`（notifications 列表/预览）

因此：

- `review_task_sla_service.scan_and_notify_review_task_sla()`：插入通知后会 `notify_user(... type=notification ...)`，前端会自动刷新。
- `notification.py` 的管理员广播：会 `broadcast_system_message(... type=system ...)`，**前端不会自动刷新通知列表**（因为不是 notification 消息）。
- 论坛审核通知、新闻订阅通知：目前仅写 `notifications` 表，**不会触发 WebSocket 推送**。

## 9. 上传（/api/upload）

1. `POST /api/upload/*`（avatar/image/file）
2. 后端做：类型/大小/文件名安全校验
3. `storage_service` 选择 provider：local / s3
4. 返回 URL：
   - local：`/api/upload/<category>/<filename>`
   - s3：public url + 307 redirect

关键：如果线上走 s3，反向代理需要允许 307 redirect 的访问路径。

## 10. 搜索（/api/search）

1. `GET /api/search?q=...`
2. 尝试 `record_search()` 写入 `SearchHistory`（失败不影响结果）
3. `SearchService.global_search()`：对 news/post/lawfirm/lawyer/knowledge 做 ilike 查询并返回聚合结构

## 11. News AI 流程

### 11.1 流程

1. `POST /api/news/ai`
2. 内容过滤：`check_news_content()` + `news_service.apply_content_filter_config_from_db()`
3. `news_service.create_news_ai_annotation()`
4. 若进入审核：`review_status=pending`
5. 给作者发通知：插入 `notifications(type=system)`，link 指向新闻的锚点
   - 当前实现**仅落库通知，不会通过 WebSocket 推送**（`news.py` 内 `_create_notification()` 仅 `db.add()`）
6. 管理员审核：
   - `GET /api/news/admin/pending-ai-annotations`
   - `POST /api/news/admin/ai-annotations/{ai_annotation_id}/review`
7. 审核副作用：
   - 写 `AdminLog`
   - 调整 `news.ai_annotation_count`（approve 增、reject/delete 扣）
   - 再次给用户发通知（通过/驳回/删除）

### 11.2 关键表

- `news`
- `news_ai_annotations`
- `notifications`

## 12. 关键表速查（按领域）

- 账号与权限：`users`
- 系统配置：`system_configs`、`admin_logs`
- 配额：`user_quota_daily`、`user_quota_pack_balances`
- AI 咨询：`consultations`、`chat_messages`
- 论坛：`posts`、`comments`、`post_likes`、`post_favorites`、`post_reactions`
- 新闻：`news`、`news_subscriptions`、`news_ai_annotations`
- 搜索：`search_history`（若 migration 已包含）
- 通知：`notifications`
- 支付：`payment_orders`、`payment_callback_events`、`user_balances`、`balance_transactions`
- 结算：`lawyer_wallets`、`lawyer_income_records`、`withdrawal_requests`、`lawyer_bank_accounts`
- 律师预约：`lawyer_consultations`、`lawyer_consultation_messages`
