# 支付模块（PAYMENT）

本模块描述支付订单、支付回调验签、回调审计、对账与管理员运维接口。

## 1. 数据模型

- `payment_orders`：订单

  - Model：`backend/app/models/payment.py:PaymentOrder`
  - `status`：`pending/paid/cancelled/refunded/failed`（见 `PaymentStatus`）
  - `payment_method`：`alipay/wechat/balance/ikunpay`（见 `PaymentMethod`）
  - `order_type`：
    - 代码枚举：`consultation/service/vip/recharge/light_consult_review`（见 `OrderType`）
    - 路由额外支持：`ai_pack`（次数包，router 里按字符串处理）

- `payment_callback_events`：支付回调审计

  - Model：`PaymentCallbackEvent`
  - unique：`(provider, trade_no)`（幂等）
  - 字段包含：raw_payload、hash、source_ip、user_agent

回调审计落库策略（非常关键，来自 `_record_callback_event()`）：

- **trade_no 并不总会写入**：只有在 `verified=true` 且 `error_message` 为空时，才会把 trade_no 写入 `payment_callback_events.trade_no`；否则会写 `NULL`。
  - 目的：避免“验签失败/业务失败”的回调因为 trade_no 重复触发唯一索引冲突。
- `raw_payload_hash`：对原始 payload 做 `sha256`，便于快速比对与排障。
- `user_agent` 最长 512、`source_ip` 最长 45（超长会截断）。
- 落库使用独立事务：内部会 `commit()`，遇到 `IntegrityError` 会 `rollback()` 并吞掉（即审计记录可能被去重）。

- `user_balances` + `balance_transactions`：余额账本

补充：

- `PaymentStatus` / `PaymentMethod` / `OrderType` 定义在：`backend/app/models/payment.py`

## 2. 用户接口（/api/payment）

- `POST /api/payment/orders`

  - 创建订单（vip/ai_pack/light_consult_review 等会根据配置自动定价）

- `GET /api/payment/pricing`

  - 获取 VIP/次数包/复核价格（来源：SystemConfig + env fallback）

- `POST /api/payment/orders/{order_no}/pay`

  - 生成支付跳转/发起支付（alipay/wechat/balance/ikunpay）

关键边界条件（来自 `pay_order()`）：

- 订单必须属于当前用户（按 `order_no + user_id` 查询），否则 404。
- 若 `order_type == recharge`，则 **不允许** `payment_method == balance`（400）。
- 若订单已 `paid`：直接返回 `{message:"支付成功", trade_no:<order.trade_no>}`。
- 若订单状态不是 `pending`：400（`订单状态异常: <status>`）。
- 若 `expires_at < now`：会把订单状态改为 `cancelled` 并提交，然后返回 400（"订单已过期"）。
- `wechat`：当前实现直接 400（"微信支付暂未开放"），即使后台渠道配置为 true。

### 2.1 余额支付（balance）

余额支付在 `pay_order()` 内完成“扣款 + 订单落库 + 余额流水 + 业务副作用”，并保证事务性：

- trade_no：`BAL<order_no_like>`（`BAL` + `generate_order_no()`）。
- 扣款为**原子条件更新**：
  - 使用 `effective_balance_cents >= actual_amount_cents` 作为 where 条件
  - 若 rowcount != 1，返回 400（"余额不足"）
- 扣款后会更新：
  - `user_balances.balance -= actual_amount`
  - `user_balances.total_consumed += actual_amount`
  - 同步更新 cents 字段
- 随后原子更新订单：`update payment_orders where status==pending -> paid`
- 写入 `balance_transactions`：
  - `type=consume`
  - `amount` 为负数（`-actual_amount`），`amount_cents` 也为负
  - `description`：`支付订单: <order.title>`
- 在同一事务内执行副作用：

  - VIP 延期、次数包入账、律师预约确认、复核任务创建（与 `_mark_order_paid_in_tx()` 保持一致）

- `GET /api/payment/orders` / `GET /api/payment/orders/{order_no}`
- `POST /api/payment/orders/{order_no}/cancel`

- `GET /api/payment/balance`
- `GET /api/payment/balance/transactions`

### 2.2 定价来源（VIP / 次数包 / 复核）

`POST /api/payment/orders` 会在创建某些订单类型时进行“后端定价”，定价来源优先级为：SystemConfig（DB）优先于 env 默认值。

- VIP：
  - days：SystemConfig `VIP_DEFAULT_DAYS`（默认 env `VIP_DEFAULT_DAYS`，再 fallback 常量）
  - price：SystemConfig `VIP_DEFAULT_PRICE`（默认 env `VIP_DEFAULT_PRICE`）
- 次数包：
  - AI：SystemConfig `AI_CHAT_PACK_OPTIONS_JSON`（fallback 常量 `AI_CHAT_PACK_OPTIONS`）
  - 文书：SystemConfig `DOCUMENT_GENERATE_PACK_OPTIONS_JSON`（fallback 常量 `DOCUMENT_GENERATE_PACK_OPTIONS`）
- 复核：SystemConfig `LIGHT_CONSULT_REVIEW_PRICE`（fallback env `LIGHT_CONSULT_REVIEW_DEFAULT_PRICE`）

### 2.3 第三方支付发起（pay_url）

`pay_order()` 在非 balance 场景会返回支付链接 `pay_url`：

- `ikunpay`：

  - 依赖：`IKUNPAY_PID` / `IKUNPAY_KEY` / `IKUNPAY_NOTIFY_URL` 必须设置，否则 400。
  - 若当前订单 `payment_method != ikunpay`，会先把订单 `payment_method` 更新为 `ikunpay`。
  - `return_url`：优先 `IKUNPAY_RETURN_URL`，否则使用 `FRONTEND_BASE_URL/payment/return`。
  - 会把 `order_no` 追加到 return_url query（`?order_no=...`）。
  - `gateway_url`：`IKUNPAY_GATEWAY_URL`，默认 `https://ikunpay.com/submit.php`。

- `alipay`：
  - 依赖：`ALIPAY_APP_ID` / `ALIPAY_PRIVATE_KEY` / `ALIPAY_NOTIFY_URL`。
  - 若当前订单 `payment_method != alipay`，会先把订单 `payment_method` 更新为 `alipay`。
  - `return_url`：优先 `ALIPAY_RETURN_URL`，否则使用 `FRONTEND_BASE_URL/payment/return`。
  - 会把 `order_no` 追加到 return_url query。

## 3. 回调入口与验签

### 3.1 通用 webhook（HMAC）

- `POST /api/payment/webhook`
- 签名：
  - payload：`{order_no}|{trade_no}|{payment_method}|{amount}`
  - HMAC-SHA256 key：`PAYMENT_WEBHOOK_SECRET`

用于：

- 内部/自建回调或简化渠道（alipay/wechat 的自定义 webhook）

实现要点：

- `payment_method` 仅允许 `alipay/wechat`（其它会记审计并 400）。
- 该入口 **不使用分布式锁**；主要依赖订单状态原子更新（`status==pending` 才会落库为 paid）实现幂等。

### 3.2 支付宝回调（RSA2）

- `POST /api/payment/alipay/notify`
- 验签：`ALIPAY_PUBLIC_KEY`
- 并发/幂等：
  - `cache_service.acquire_lock()` 以 `trade_no/order_no` 作为锁 key
  - `payment_callback_events` 记录审计

实现要点（来自 router）：

- 仅接受 `trade_status in {TRADE_SUCCESS, TRADE_FINISHED}`，其他状态会被记录为 `ignored_trade_status:*` 并直接返回 success（避免渠道重试）。
- 若回调 `sign_type` 非 `RSA2` 会记录 `unsupported_sign_type:*` 并返回 failure。
- 若设置了 `ALIPAY_APP_ID`，会校验回调 `app_id` 一致，否则记录 `app_id 不匹配` 并返回 failure。
- 幂等锁 key：`locks:payment_notify:alipay:{trade_no or order_no}`（expire=30s）。
- 返回体：`text/plain`，成功为 `success`，失败为 `failure`。

### 3.3 微信支付回调（平台证书验签）

- `POST /api/payment/wechat/notify`
- 依赖：`WECHATPAY_PLATFORM_CERTS_JSON`（存 SystemConfig）
- 验签头：`Wechatpay-Serial/Timestamp/Nonce/Signature/...`

平台证书来源：

- 管理接口导入或刷新（见下文）

实现要点（来自 router）：

- 会校验 `Wechatpay-Signature-Type == WECHATPAY2-SHA256-RSA2048`，否则记录并 400。
- 平台证书从 SystemConfig `WECHATPAY_PLATFORM_CERTS_JSON` 读取，并按 `Wechatpay-Serial` 取匹配证书；找不到会记录并 400。
- 解密依赖 `WECHATPAY_API_V3_KEY`：缺失会记录并 500。
- 订单状态/金额不满足预期时，多数情况下会**返回 SUCCESS**（`{"code":"SUCCESS","message":"OK"}`）来吞掉回调，避免渠道持续重试；但会留下 `payment_callback_events` 供对账。
- 幂等锁 key：`locks:payment_notify:wechat:{trade_no or order_no}`（expire=30s，未获取锁返回 `FAIL/BUSY`）。

### 3.4 Ikunpay 回调（MD5）

- `POST /api/payment/ikunpay/notify`（也支持 GET）
- 验签：`IKUNPAY_KEY`（MD5），可选校验 `IKUNPAY_PID`。
- 仅接受 `trade_status == TRADE_SUCCESS`，否则记录 `ignored_trade_status:*` 并返回 success。
- 幂等锁 key：`locks:payment_notify:ikunpay:{trade_no or order_no}`（expire=30s）。
- 返回体：`text/plain`，成功为 `success`，失败为 `fail`。

## 4. 订单落库与副作用

支付成功会调用 `_mark_order_paid_in_tx()`：

- 写订单 `paid_at/trade_no/status`
- 若订单为充值：增加 `user_balances` 并写 `balance_transactions`
- 若订单为 VIP/次数包/咨询确认/复核等：触发对应业务 side-effects

关键实现：`backend/app/routers/payment.py:_mark_order_paid_in_tx()`。

幂等与并发控制（来自 `_mark_order_paid_in_tx()`）：

- 通过 `update(PaymentOrder).where(id==..., status==pending)` 原子更新，确保同一订单不会被重复标记 paid。
- 若 `rowcount != 1`：直接 return（上层会当作“已处理/无需处理”）。

副作用包含：

- `vip`：延长 `users.vip_expires_at`（按 `VIP_DEFAULT_DAYS` / SystemConfig 同名 key 计算天数）
- `ai_pack`：写入 `user_quota_pack_balances`（`ai_chat_credits` 或 `document_generate_credits`）
  - `related_type` 允许：`ai_chat` / `document_generate`
  - `related_id` 使用 pack_count（次数）
- `consultation`（律师预约）：若 `related_type=lawyer_consultation`，会将 `lawyer_consultations.status` 从 `pending` 更新为 `confirmed`
- `light_consult_review`：若 `related_type=ai_consultation`，会创建 `consultation_review_tasks(status=pending)`

## 5. 管理员接口（/api/payment/admin）

- `GET /api/payment/admin/orders`
- `POST /api/payment/admin/orders/{order_no}/mark-paid`
- `POST /api/payment/admin/refund/{order_no}`

- 回调审计：

  - `GET /api/payment/admin/callback-events`
  - `GET /api/payment/admin/callback-events/stats`
  - `GET /api/payment/admin/callback-events/{event_id}`

- 微信平台证书：

  - `GET /api/payment/admin/wechat/platform-certs`
  - `POST /api/payment/admin/wechat/platform-certs/import`
  - `POST /api/payment/admin/wechat/platform-certs/refresh`

- 渠道状态：

  - `GET /api/payment/admin/channel-status`
  - `GET /api/payment/channel-status`（公开版）

- 对账：

  - `GET /api/payment/admin/reconcile/{order_no}`

对账诊断（来自 `admin_reconcile/{order_no}`）：

- 诊断字段 `diagnosis` 可能为：
  - `ok`
  - `no_callback`
  - `amount_mismatch`
  - `decrypt_failed`
  - `signature_failed`
  - `paid_without_success_callback`
  - `success_callback_but_order_not_paid`
- `details` 会包含 `expected_amount`、`last_event` 以及若干 `has_*` 标志位，用于定位回调失败原因。

- 运维（写入 env 文件并热加载）：
  - `POST /api/payment/admin/env`
  - 注意：只允许更新白名单内的支付相关 env key（代码内 allowed 列表）

env 白名单（来自 `_update_env_file()`，超出不会生效）：

- `PAYMENT_WEBHOOK_SECRET`
- `ALIPAY_APP_ID` / `ALIPAY_PRIVATE_KEY` / `ALIPAY_PUBLIC_KEY` / `ALIPAY_GATEWAY_URL` / `ALIPAY_NOTIFY_URL` / `ALIPAY_RETURN_URL`
- `IKUNPAY_PID` / `IKUNPAY_KEY` / `IKUNPAY_GATEWAY_URL` / `IKUNPAY_NOTIFY_URL` / `IKUNPAY_RETURN_URL` / `IKUNPAY_DEFAULT_TYPE`
- `WECHATPAY_MCH_ID` / `WECHATPAY_MCH_SERIAL_NO` / `WECHATPAY_PRIVATE_KEY` / `WECHATPAY_API_V3_KEY` / `WECHATPAY_CERTIFICATES_URL`
- `FRONTEND_BASE_URL`

补充：

- `POST /api/payment/admin/env` 在非测试环境会写入 `.env`（路径选择：优先 `backend/.env`，否则 repo 根 `.env`，可用 `ENV_FILE` 指定）。
- 会记录管理员操作日志（AdminLog），并 `get_settings.cache_clear()` 触发热加载。

## 6. 排障建议

- 回调验签失败：优先查看 `payment_callback_events` 的 `verified/error_message/raw_payload`
- 并发导致重复处理：检查 Redis/内存锁是否可用
- 生产必须配置：`PAYMENT_WEBHOOK_SECRET` + 对应渠道 key/cert

额外排障提示：

- 若你发现某些失败回调在 `payment_callback_events` 中看不到 `trade_no`，这是**设计行为**（见上文：仅成功回调写 trade_no）。排查时以 `order_no` + `raw_payload_hash` 为主。
- 公开渠道状态 `GET /api/payment/channel-status` 的 `available_methods` 默认始终包含 `balance`；第三方渠道根据配置追加。目前实现中会追加 `alipay/ikunpay`，不会把 `wechat` 放入 available_methods（即使 wechatpay_configured 为 true）。

常见业务边界条件（来自 router 实现）：

- 充值订单不支持余额支付（`order_type=recharge` 且 `payment_method=balance` 会被拒绝）
- `wechat` 在 `pay_order` 中直接返回“暂未开放”（目前实际不可用）
- 订单过期：若 `expires_at < now`，会被标记为 `cancelled` 并返回“订单已过期”

详见：`docs/guides/TROUBLESHOOTING.md`.
