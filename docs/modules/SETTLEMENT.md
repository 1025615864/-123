# 结算与提现（SETTLEMENT）

本模块描述律师钱包、收入记录、结算冻结期与提现流程。

## 1. 数据模型

- `lawyer_wallets`：律师钱包汇总
- `lawyer_income_records`：每笔收入记录（`pending/settled/withdrawn`）
- `lawyer_bank_accounts`：收款账户（账号字段会加密存储）
- `withdrawal_requests`：提现申请（`pending/approved/rejected/completed/failed`）

Model：`backend/app/models/settlement.py`

## 2. 加密策略（收款账号）

- 实现：`backend/app/services/settlement_service.py`
- 使用 `SECRET_KEY/JWT_SECRET_KEY` 经 SHA256 派生 Fernet key
- 加密字段以 `enc:` 前缀存储

实现细节：

- Fernet key：对 `get_settings().secret_key` 做 `sha256`，再 `base64.urlsafe_b64encode()` 作为 Fernet key。
- `decrypt_secret()` 对解密失败会返回空字符串（不会抛异常）。

目的：

- 降低 DB 泄露时的敏感信息暴露风险

## 3. 律师侧接口（/api/settlement/lawyer）

- `GET /api/settlement/lawyer/wallet`
- `GET /api/settlement/lawyer/income-records`
- `GET /api/settlement/lawyer/income-records/export`

- `GET /api/settlement/lawyer/bank-accounts`
- `POST /api/settlement/lawyer/bank-accounts`
- `PUT /api/settlement/lawyer/bank-accounts/{account_id}`
- `PUT /api/settlement/lawyer/bank-accounts/{account_id}/default`
- `DELETE /api/settlement/lawyer/bank-accounts/{account_id}`

- `GET /api/settlement/lawyer/withdrawals`
- `GET /api/settlement/lawyer/withdrawals/{withdrawal_id}`
- `POST /api/settlement/lawyer/withdrawals`

权限：`require_lawyer_verified`，且需要律师资料绑定、通过认证（在 service 内检查）。

## 3.2 平台抽成（platform fee rate）

结算侧会根据律师的“历史完成单数 + rating + 特殊合作名单”动态选择抽成比例：

- 默认：`SETTLEMENT_PLATFORM_FEE_RATE`（默认 0.15）
- 达标 verified：
  - `SETTLEMENT_VERIFIED_MIN_COMPLETED`（默认 10）
  - `SETTLEMENT_VERIFIED_MIN_RATING`（默认 4.5）
  - `SETTLEMENT_VERIFIED_PLATFORM_FEE_RATE`（默认 0.13）
- 达标 gold：
  - `SETTLEMENT_GOLD_MIN_COMPLETED`（默认 50）
  - `SETTLEMENT_GOLD_MIN_RATING`（默认 4.8）
  - `SETTLEMENT_GOLD_PLATFORM_FEE_RATE`（默认 0.10）
- 合作律师白名单：`SETTLEMENT_PARTNER_LAWYER_IDS`（逗号分隔 id 集合）
  - 抽成：`SETTLEMENT_PARTNER_PLATFORM_FEE_RATE`（默认 0.08）

## 3.1 钱包字段语义（必须理解）

Model：`backend/app/models/settlement.py:LawyerWallet`

- `total_income`：累计总收入（历史入账总和）
- `pending_amount`：冻结期内的“待结算收入”（未到 settle_time）
- `available_amount`：可提现金额
- `frozen_amount`：已发起提现、等待管理员处理的冻结金额
- `withdrawn_amount`：累计已提现金额

这些字段会在 `settlement_service` 内通过 `_recalc_wallet_fields()` 做一致性重算。

## 4. 管理员侧接口（/api/settlement/admin）

- 提现：

  - `GET /api/settlement/admin/withdrawals`
  - `GET /api/settlement/admin/withdrawals/export`
  - `GET /api/settlement/admin/withdrawals/{withdrawal_id}`
  - `POST /api/settlement/admin/withdrawals/{withdrawal_id}/approve`
  - `POST /api/settlement/admin/withdrawals/{withdrawal_id}/reject`
  - `POST /api/settlement/admin/withdrawals/{withdrawal_id}/complete`
  - `POST /api/settlement/admin/withdrawals/{withdrawal_id}/fail`

- 结算：
  - `POST /api/settlement/admin/settlement/run`
  - `GET /api/settlement/admin/settlement-stats`
  - `GET /api/settlement/admin/income-records/export`

## 5. 结算逻辑（冻结期）

- 环境变量：
  - `SETTLEMENT_FREEZE_DAYS`（默认 7）

流程：

- 订单支付成功 -> 创建 `lawyer_income_records`（status=pending，setttle_time=now+freeze_days）
- 周期任务/管理员触发 -> `settle_due_income_records()` 将到期记录从 pending -> settled

代码：`backend/app/services/settlement_service.py:settle_due_income_records()`。

关键点：

- 仅处理 `status == "pending"` 且 `settle_time <= now` 的记录
- 结算时会把对应金额从 `wallet.pending_amount` 扣减

收入记录创建触发点（来自业务 router）：

- 律师预约咨询完成：`/api/lawfirm/lawyer/consultations/{id}/complete` 调用
  - `settlement_service.ensure_income_record_for_completed_consultation(consultation, order)`
  - 唯一性：按 `(consultation_id, lawyer_id)` 查重，存在则直接返回。
- AI 咨询“律师复核”提交：`/api/reviews/lawyer/tasks/{task_id}/submit` 调用
  - `settlement_service.ensure_income_record_for_paid_review_order(lawyer_id, order)`
  - 仅当 `order.order_type == light_consult_review` 且 `order.status == paid`
  - 唯一性：按 `(lawyer_id, order_no)` 查重，存在则直接返回。

## 6. 提现逻辑

- 创建提现会（`create_withdrawal_request`）：

  - 校验最小/最大金额、可用余额
  - 将钱包可用金额转入冻结金额

金额边界（来自 service 常量）：

- `SETTLEMENT_WITHDRAW_MIN_AMOUNT`（默认 100）
- `SETTLEMENT_WITHDRAW_MAX_AMOUNT`（默认 50000）
- `SETTLEMENT_WITHDRAW_FEE`（默认 0，可按业务收取手续费）

收款账号落库格式（`withdrawal_requests.account_info`，JSON 字符串）：

- `account_no`：会写入加密后的字符串（`enc:<token>`）
- `masked.account_no`：仅保留后 4 位（展示用）

状态：`withdrawal_requests.status = "pending"`

- 管理员审核通过（approve）：

  - 仅 `pending` 可通过
  - 状态：`approved`

- 管理员驳回（reject）：

  - 仅 `pending` 可驳回
  - 状态：`rejected`
  - 钱包：`frozen_amount -= amount`，`available_amount += amount`（退回可提现）

- 管理员打款完成（complete）：

  - 仅 `approved` 可完成
  - 状态：`completed`
  - 钱包：`frozen_amount -= amount`，`withdrawn_amount += amount`
  - 审计：会尝试按时间顺序在 `lawyer_income_records(status in {settled, withdrawn})` 上分摊 `withdrawn_amount`
    - 分摊后若某条记录 `withdrawn_amount >= lawyer_income`，该记录变为 `withdrawn`

分摊规则实现说明：

- 排序：`coalesce(settle_time, created_at)` 升序，其次 `created_at` 升序（先结算先消耗）。
- 对每条记录：
  - `can_take = lawyer_income - withdrawn_amount`
  - `take = min(can_take, remaining)`
  - 更新 `withdrawn_amount/withdrawn_amount_cents`
  - 若 `new_withdrawn >= lawyer_income`：记录 `status=withdrawn`，否则保持 `settled`
- 该分摊逻辑被 `try/except` 包裹：即便分摊失败也不会阻止提现完成状态落库（属于“尽力而为”的审计）。

- 管理员打款失败（fail）：

  - 仅 `approved` 可标记失败
  - 状态：`failed`
  - 钱包：`frozen_amount -= amount`，`available_amount += amount`（退回可提现）

管理员状态机代码：`backend/app/services/settlement_service.py:admin_set_withdrawal_status()`。

## 7. 建议

- 生产环境应在管理侧对“打款完成”有双人复核流程（当前代码为单人动作）。
- 建议对提现完成动作增加外部支付流水号字段（当前以 remark/记录为主）。
