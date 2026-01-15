# 数据模型概览（DATA_MODEL）

本文件用于帮助开发者快速理解核心表与关系。内容以 `backend/app/models/*` 为准（不替代 Alembic 迁移）。

## 1. 用户与身份

- `users`
  - 关键字段：
    - `id`
    - `username` / `email`（均唯一）
    - `role`（字符串）：`user` / `lawyer` / `moderator` / `admin` / `super_admin`
    - `is_active`
    - `email_verified` / `phone_verified`
    - `vip_expires_at`

## 2. SystemConfig 与管理员日志

- `system_configs`

  - `key`（唯一）
  - `value`
  - `category`
  - `updated_by` -> `users.id`

- `admin_logs`
  - `user_id` -> `users.id`
  - `action` / `module` / `target_id` / `description` / `extra_data`

## 3. 配额（Quota）

- `user_quota_daily`

  - unique: `(user_id, day)`
  - `ai_chat_count`
  - `document_generate_count`

- `user_quota_pack_balances`
  - unique: `user_id`
  - `ai_chat_credits`
  - `document_generate_credits`

配额逻辑：见 `backend/app/services/quota_service.py`

## 4. 上传（Upload）

上传文件在 local 模式落地 `backend/uploads/<category>/...`，通过 API 访问：

- `/api/upload/avatars/{filename}`
- `/api/upload/images/{filename}`
- `/api/upload/files/{filename}`

S3 模式下为 307 重定向到 `STORAGE_PUBLIC_BASE_URL`。

## 5. 其他业务表

由于业务模块较多（news/forum/payment/settlement/consultation/reviews 等），建议结合以下方式理解：

- 从 `backend/app/routers/<module>.py` 找到写入/读取的模型
- 从 `backend/app/services/<module>_service.py` 找核心业务函数

后续会在模块文档里按“模块”补齐更细的表关系说明（例如 News AI annotations、支付回调审计等）。

### 5.1 支付（Payment）

- `payment_orders`

  - 唯一：`order_no`
  - 关键字段：
    - `order_no`：订单号（对外展示/对账主键）
    - `user_id`：下单用户
    - `order_type`：`consultation/service/vip/recharge/light_consult_review`（router 额外支持 `ai_pack`）
    - `related_type` / `related_id`：把订单绑定到业务对象（例如 `lawyer_consultation` 或 `ai_consultation`）
    - `status`：`pending/paid/cancelled/refunded/failed`
    - `payment_method`：`alipay/wechat/balance/ikunpay`
    - `trade_no`：第三方交易号（余额支付会生成 `BAL...`）
    - `expires_at`：过期后支付入口会把订单置为 `cancelled`

- `user_balances`

  - 唯一：`user_id`
  - 关键字段：`balance/frozen/total_recharged/total_consumed`（以及对应 cents 字段）
  - 语义：余额支付会在同一事务内扣减 `balance` 并增加 `total_consumed`

- `balance_transactions`

  - 关键字段：`type in {recharge, consume, refund}`
  - 语义：
    - `recharge` 为正数
    - `consume` 为负数（`amount/amount_cents` 都为负）
    - `refund` 为正数

- `payment_callback_events`
  - 唯一：`(provider, trade_no)`
  - 关键字段：`provider/order_no/trade_no/verified/error_message/raw_payload/raw_payload_hash/source_ip/user_agent`
  - 注意：成功回调才会写入 trade_no（失败回调 trade_no 可能为 NULL）

详见：`docs/modules/PAYMENT.md`。

### 5.2 结算与提现（Settlement）

- `lawyer_wallets`

  - 唯一：`lawyer_id`
  - 五个核心金额字段：`total_income/withdrawn_amount/pending_amount/frozen_amount/available_amount`
  - 一致性：服务端会通过 `_recalc_wallet_fields()` 反算 `available_amount`

- `lawyer_income_records`

  - 关键字段：
    - `lawyer_id`
    - `consultation_id`（律师预约完成入账）
    - `order_no`（复核订单入账）
    - `user_paid_amount/platform_fee/lawyer_income`
    - `withdrawn_amount`
    - `status in {pending, settled, withdrawn}`
    - `settle_time`（冻结期到期时间）

- `lawyer_bank_accounts`

  - 关键字段：`account_no` 在 DB 中以 `enc:` 前缀加密存储（展示时仅暴露后四位）

- `withdrawal_requests`
  - 唯一：`request_no`
  - 关键字段：
    - `status in {pending, approved, rejected, completed, failed}`
    - `account_info`：JSON（内部保存加密账号与 masked 信息）
    - `admin_id/reviewed_at/completed_at/reject_reason/remark`

详见：`docs/modules/SETTLEMENT.md`。

### 5.3 律师复核（Reviews）

- `consultation_review_tasks`

  - 唯一：`order_id`（同一笔复核订单只会产生一个 task）
  - 关键字段：
    - `consultation_id`：绑定 AI 咨询记录（自增 id）
    - `user_id`：咨询所属用户
    - `order_id/order_no`：绑定支付订单
    - `status in {pending, claimed, submitted}`
    - `lawyer_id`：领取后写入
    - `claimed_at/submitted_at`
    - `result_markdown`

- `consultation_review_versions`
  - 关键字段：`task_id/editor_user_id/editor_role/content_markdown/created_at`
  - 语义：每次提交会新增一条 version，用于审计与回溯

详见：`docs/modules/REVIEWS_SLA.md`。

### 5.4 通知（Notifications）

- `notifications`
  - 唯一：`(user_id, type, dedupe_key)`（用于“系统通知/催办”等去重）
  - 关键字段：`type/title/content/link/dedupe_key/is_read`
  - 关联字段：`related_user_id/related_post_id/related_comment_id`

详见：`docs/modules/NOTIFICATIONS.md` 与 `docs/guides/TROUBLESHOOTING.md`。
