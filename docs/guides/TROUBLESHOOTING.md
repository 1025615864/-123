# 排障手册（TROUBLESHOOTING）

本手册聚焦开发者在本项目中最常遇到的问题（以现有代码行为为准）。

## 1. 后端启动直接报错：Redis must be available when DEBUG is False

现象：

- `RuntimeError: Redis must be available when DEBUG is False...`

原因：

- `backend/app/main.py` 在 lifespan 中要求：`DEBUG=false` 时 Redis 必须可用。

处理：

- 开发环境：设置 `DEBUG=true`
- 生产环境：正确设置 `REDIS_URL` 并确保 Redis 可连接

## 2. 后端启动报错：SECRET_KEY / PAYMENT_WEBHOOK_SECRET 校验失败

原因：

- `backend/app/config.py` 的 `model_validator` 在 `DEBUG=false` 时强制校验：
  - `SECRET_KEY/JWT_SECRET_KEY` 安全性（长度与默认值）
  - `PAYMENT_WEBHOOK_SECRET` 必填

处理：

- 生产通过 Secret/env 注入真实密钥。

## 3. SystemConfig 写入失败：Secret values must not be stored

原因：

- `backend/app/routers/system.py` 会拒绝把 `secret/password/api_key/private_key` 等敏感项写入 SystemConfig。

处理：

- 把敏感项移到 env/Secret
- SystemConfig 只存业务开关或非敏感参数

## 4. News AI providers 配置写入失败：must not include api_key

原因：

- providers JSON/B64 中包含 `api_key` 字段会被硬拦截。

处理：

- providers 只描述 base_url/model/鉴权头结构
- API key 统一用 `OPENAI_API_KEY`（env/Secret）

## 5. 401/403：未提供认证凭证 / 需要管理员权限

- 认证依赖：`backend/app/utils/deps.py`
  - `get_current_user`：读取 `Authorization: Bearer <jwt>`，并解析 `sub` 为 user_id
  - `require_admin`：要求 `role in {admin, super_admin}`

建议：

- 本地用 `backend/scripts/seed_data.py` 创建 admin 用户并登录获取 token

## 6. WebSocket 连接立即断开（1008）

原因：

- `backend/app/routers/websocket.py`：token 存在但无效/用户不可用，会 `close(code=1008)`。

处理：

- 确认前端拿到的 token 有效
- 确认用户 `is_active=true`

## 7. 429：请求过于频繁 / 每秒请求过多

项目存在两套限制：

- 全局 IP 限流中间件：`backend/app/middleware/rate_limit.py`
  - 优先 Redis 计数器（若 Redis 已连接），否则内存滑窗
- 业务配额（quota）：`backend/app/services/quota_service.py`
  - AI 聊天、文书生成按天消耗

处理：

- 确认是哪一种 429：
  - 限流中间件返回：`每秒请求过多` / `请求过于频繁`
  - quota 返回：`今日 AI 咨询次数已用尽` / `今日文书生成次数已用尽`

## 8. 上传文件 400/404

- 上传限制：

  - 头像/图片：2MB
  - 附件：10MB
  - 文件名有严格正则校验（防目录穿越）

- S3 模式：下载为 307 跳转

处理：

- 检查 content-type
- 检查文件大小
- 检查是否走了正确的 `/api/upload/<category>/...` 路径

## 9. 支付问题排障（回调/对账/余额）

### 9.1 订单已 paid 但用户仍提示未支付

排查路径：

- 先查 `payment_orders`：确认 `status/trade_no/paid_at/payment_method`
- 再查 `payment_callback_events`：
  - 若存在 `verified=true 且 error_message 为空` 的回调：说明回调链路已成功
  - 若只有 `verified=false` 或 `error_message`：按 error_message 继续定位（验签失败/解密失败/金额不一致等）

补充：

- 部分失败回调会看不到 `trade_no`（这是设计行为：只有成功回调会写入 trade_no 用于唯一索引去重），此时建议按 `order_no` 与 `raw_payload_hash` 排查。

### 9.2 余额支付提示“余额不足”但用户认为有余额

原因：

- 余额扣款使用原子条件更新（where 条件包含 `effective_balance_cents >= actual_amount_cents`），并发/缓存显示滞后时可能出现“看起来有余额但扣款失败”。

处理：

- 查 `user_balances.balance` 与 `balance_cents`
- 查 `balance_transactions` 是否已有同订单的 `consume` 记录

### 9.3 对账接口如何用（管理员）

- `GET /api/payment/admin/reconcile/{order_no}` 会返回 `diagnosis` 与 `details`，用于判断：
  - 是否无回调
  - 是否验签失败/解密失败/金额不一致
  - 是否“订单已 paid 但没有成功回调”或反过来

## 10. 结算/提现问题排障

### 10.1 冻结期到期但收入仍未变为 settled

排查路径：

- 查 `lawyer_income_records`：
  - `status` 是否仍为 `pending`
  - `settle_time` 是否已 <= now
- 若已到期仍不变：
  - 检查周期任务是否启用：`SETTLEMENT_JOB_ENABLED`（DEBUG=true 默认会跑）
  - 检查 Redis：生产 `DEBUG=false` 时 Redis 不可用会导致任务不跑
- 可用管理员接口手动触发：`POST /api/settlement/admin/settlement/run`

### 10.2 提现后钱包金额对不上（available/frozen/withdrawn）

排查路径：

- 查 `withdrawal_requests`：确认 `status/amount/fee/actual_amount/admin_id/reviewed_at/completed_at`
- 查 `lawyer_wallets`：
  - `pending_amount`（冻结期未结算）
  - `available_amount`（可提现）
  - `frozen_amount`（提现申请冻结）
  - `withdrawn_amount`（累计已提现）

原则：

- 提现创建：available -> frozen
- 驳回/失败：frozen -> available
- 完成：frozen -> withdrawn

### 10.3 提现已完成但收入记录未正确分摊（withdrawn_amount 未更新）

说明：

- `complete` 时会尝试把提现金额分摊到 `lawyer_income_records(status in {settled, withdrawn})`（按时间顺序），并更新 `withdrawn_amount`。
- 分摊逻辑是“尽力而为”：内部异常会被吞掉，不会阻止提现完成状态落库。

排查路径：

- 先确认 `withdrawal_requests.status == completed`
- 再查 `lawyer_income_records`：看 `withdrawn_amount/status` 是否匹配
