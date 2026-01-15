# 律师复核与 SLA（REVIEWS_SLA）

本模块描述 AI 咨询的律师复核任务、SLA 计算与催办通知。

## 1. 复核任务 API（/api/reviews）

Router：`backend/app/routers/reviews.py`

- 用户：

  - `GET /api/reviews/consultations/{consultation_id}`：查询某次 AI 咨询的复核任务

- 律师：
  - `GET /api/reviews/lawyer/tasks`：复核任务列表（pending/claimed/submitted）
  - `POST /api/reviews/lawyer/tasks/{task_id}/claim`：领取任务（仅 pending 且未分配可领）
  - `POST /api/reviews/lawyer/tasks/{task_id}/submit`：提交复核结果（仅 claimed 可提交）

注意：提交时会校验关联订单必须为 `paid`。

## 1.1 数据模型与状态机

Model：`backend/app/models/consultation_review.py`

- `consultation_review_tasks`：`ConsultationReviewTask`

  - unique：`order_id`（同一笔订单只会对应一个复核任务）
  - `status`：
    - `pending`：待领取（`lawyer_id is NULL`）
    - `claimed`：已领取（`lawyer_id` 被某律师写入）
    - `submitted`：已提交复核

- `consultation_review_versions`：`ConsultationReviewVersion`
  - 每次提交会新增一个 version，便于审计与回溯

状态迁移（来自 router 实现）：

- `pending` -> `claimed`

  - 条件：`status==pending && lawyer_id is NULL`
  - 动作：写 `lawyer_id`、`claimed_at`、`status=claimed`

领取的并发/错误语义（来自原子 update）：

- 领取采用 `update ... where status==pending and lawyer_id is NULL` 的原子更新。
- 若领取失败：

  - 任务不存在：404
  - `lawyer_id` 已经有人写入：400（"任务已被领取"）
  - 其它状态：400（"任务不可领取: <cur_status>"）

- `claimed` -> `submitted`
  - 条件：`status==claimed && task.lawyer_id == current_lawyer` 且 `PaymentOrder.status == paid`
  - 动作：
    - 插入 `ConsultationReviewVersion`
    - 写 `task.result_markdown/submitted_at/status=submitted`
    - 触发结算侧入账：`settlement_service.ensure_income_record_for_paid_review_order()`

提交校验（来自 router）：

- 会校验 `task.lawyer_id == 当前律师`，否则 403。
- 会校验关联 `order_id` 能查到 `PaymentOrder`，否则 500（"订单信息缺失"）。
- 会校验 `PaymentOrder.status == paid`，否则 400（"订单未支付，无法提交"）。

## 1.2 任务创建触发点（来自支付模块）

复核任务不是人工创建，而是由支付模块在订单支付成功后自动创建：

- 订单：`payment_orders.order_type == "light_consult_review"`
- 且关联：`related_type == "ai_consultation"`、`related_id == <consultation.id>`

代码：`backend/app/routers/payment.py:_maybe_create_consultation_review_task_in_tx()`。

落库字段：

- `consultation_review_tasks.order_id` / `order_no` 绑定支付订单
- `consultation_review_tasks.consultation_id` 绑定 AI 咨询记录（注意这里是 Consultation 的 **自增 id**，不是 session_id）
- 默认 `status=pending`，等待律师领取

任务可见性（律师列表接口的查询条件）：

- 律师侧列表会返回：
  - `lawyer_id is NULL` 的任务（表示“可领取”）
  - 或 `lawyer_id == 当前律师` 的任务（表示“我已领取/已提交”）

## 2. SLA 配置

配置 key：

- `CONSULT_REVIEW_SLA_JSON`

来源优先级：

- SystemConfig（DB）
- env（同名）
- 默认值

默认结构：

- `pending_sla_minutes`：24h
- `claimed_sla_minutes`：12h
- `remind_before_minutes`：60min

## 3. SLA 计算

- 代码：`backend/app/services/review_task_sla_service.py`

规则：

- task.status == `pending`：以 `created_at` 为 base
- task.status == `claimed`：以 `claimed_at` 为 base
- task.status == `submitted`：无 due_at

API 返回字段：

- `due_at`
- `is_overdue`

## 4. 催办通知（Notification + WebSocket）

- Job：`scan_and_notify_review_task_sla()`
- gate：SystemConfig `enable_notifications` 若为 false 则跳过

通知写入：

- 表：`notifications`
- type：`system`
- link：`/lawyer?tab=reviews`
- dedupe_key：`review_task:{task_id}:{kind}:{due_at.iso}`（避免重复提醒）

实时推送：

- 若插入成功，会调用 `websocket_service.notify_user(... type=notification ...)`

实现要点（来自 `review_task_sla_service.py`）：

- 扫描范围：仅扫描 `status in {pending, claimed}` 且 **`lawyer_id is not NULL`** 的任务。
  - 含义：未领取（lawyer_id 为 NULL）的 `pending` 任务不会被 SLA job 催办。
- 通知插入：使用 `(user_id, type, dedupe_key)` 做去重（on_conflict_do_nothing）。
- 通知内容会包含：task id / consultation_id / order_no / status / due_at（以及 due_soon 场景的剩余分钟）。
- WebSocket 推送：
  - PostgreSQL：可通过 insert returning 拿到“实际插入”的行，再逐条推送。
  - SQLite：无法 returning，当前实现会在 `inserted>0` 时对候选 values 循环推送（属于近似行为）。

## 5. 生产建议

- 当 `DEBUG=false` 时 Redis 必须可用（周期任务依赖分布式锁/可用性）
- 建议对 SLA 扫描结果/插入数做监控告警
