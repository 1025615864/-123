# 咨询模块（CONSULTATION）

本模块描述两类“咨询”：

- **AI 法律咨询**：`/api/ai/*`（session_id 为字符串）
- **律师咨询预约**：`/api/lawfirm/consultations*`（consultation_id 为整数）

它们在数据模型、支付/结算、权限上是两套体系，但在前端体验上会被整合为“咨询/订单/评价”。

## 1. AI 法律咨询（/api/ai）

实现：`backend/app/routers/ai.py`

### 1.1 核心模型

- `consultations`：`backend/app/models/consultation.py:Consultation`

  - `session_id`：对外标识（字符串）
  - `user_id`：登录用户绑定（游客为 null）

- `chat_messages`：`ChatMessage`
  - `role`：`user/assistant`
  - `references`：JSON string（包含 `references[]` 与 `meta{prompt_version,duration_ms,request_id,...}`）
  - `rating/feedback`：用户对 assistant message 的评价

### 1.2 对话接口

- `POST /api/ai/chat`

  - 访客与登录用户都可用
  - 登录用户会执行 `QuotaService.enforce_ai_chat_quota()`（按天）
  - 访客使用 `GUEST_AI_LIMIT/GUEST_AI_WINDOW_SECONDS` 的窗口限额
  - 额外有 `RateLimitConfig.AI_CHAT` 的装饰器限流（按 IP）

- `POST /api/ai/chat/stream`
  - SSE（`text/event-stream`）流式输出
  - 支持 E2E mock：`X-E2E-Mock-AI: 1`

### 1.3 历史与分享

- `GET /api/ai/consultations`：我的会话列表（支持 `q` 在标题/消息内搜索）
- `GET /api/ai/consultations/{session_id}`：会话详情
- `DELETE /api/ai/consultations/{session_id}`：删除会话（并尝试清理 assistant session）

导出与报告：

- `GET /api/ai/consultations/{session_id}/export`：结构化导出（前端可据此生成报告）
- `GET /api/ai/consultations/{session_id}/report?format=pdf`：生成 PDF（依赖缺失会 501）

分享链接（基于 JWT token，不落库）：

- `POST /api/ai/consultations/{session_id}/share?expires_days=7`
  - token payload：`{"type":"consultation_share","session_id":"..."}`
- `GET /api/ai/share/{token}`：访问分享内容（无需登录）

### 1.4 语音转写 / 文件分析

- `POST /api/ai/transcribe`：语音转写（multipart file）

  - provider：openai / sherpa / auto
  - 支持从 DB 读取“语音配置强制覆盖”（`voice_config_service`）
  - 会输出诊断 header：`X-AI-Voice-*`、`X-Voice-Config-Forced`
  - 访客也会走 guest quota

- `POST /api/ai/files/analyze`：文件解析与摘要
  - 支持 pdf/docx/txt 等，最大 10MB
  - 文本会经过 `sanitize_pii()` 再送入 LLM

### 1.5 快捷追问 / 评价

- `POST /api/ai/quick-replies`：根据（用户输入 + AI 回复 + references）生成快捷追问（非 LLM，规则生成）
- `POST /api/ai/messages/rate`：对 AI 的 assistant message 评分（仅会话所有者可评）

## 2. 律师咨询预约（/api/lawfirm/consultations）

实现：`backend/app/routers/lawfirm.py`（"咨询预约相关" 段）

### 2.1 核心模型

- `lawyer_consultations`：`backend/app/models/lawfirm.py:LawyerConsultation`

  - status：`pending/confirmed/completed/cancelled`

- `lawyer_consultation_messages`：`LawyerConsultationMessage`
  - sender_role：`user/lawyer`

与支付的关联：

- `payment_orders`
  - `order_type="consultation"`
  - `related_type="lawyer_consultation"`
  - `related_id=<consultation.id>`

### 2.2 下单与支付

- `POST /api/lawfirm/consultations`
  - 创建预约
  - 若律师 `consultation_fee>0`：同步创建 `PaymentOrder(status=pending, expires_at=now+2h)`，并在响应中返回 `payment_order_no/payment_status/payment_amount`

### 2.3 双方操作与消息

用户侧：

- `GET /api/lawfirm/consultations`：我的咨询列表（聚合订单状态与是否可评价）
- `POST /api/lawfirm/consultations/{consultation_id}/cancel`
  - 退款规则：**仅支持余额支付自动退款**；其它支付方式提示联系管理员

律师侧：

- `GET /api/lawfirm/lawyer/consultations`
- `POST /api/lawfirm/lawyer/consultations/{consultation_id}/accept`
  - 若订单仍 `pending`：拒绝接单（"用户尚未完成支付"）
- `POST /api/lawfirm/lawyer/consultations/{consultation_id}/reject`
  - 若订单已 paid：拒绝拒单（"订单已支付，请走退款流程"）
- `POST /api/lawfirm/lawyer/consultations/{consultation_id}/complete`
  - 完成后会触发结算侧：`settlement_service.ensure_income_record_for_completed_consultation()`

消息线程：

- `GET /api/lawfirm/consultations/{consultation_id}/messages`
- `POST /api/lawfirm/consultations/{consultation_id}/messages`
  - 仅咨询双方可发（user/lawyer）

### 2.4 评价（律师服务评价）

- `POST /api/lawfirm/reviews`

  - 必须指定 consultation_id
  - 仅 completed 可评价
  - 同一 consultation 仅允许评价一次

- `GET /api/lawfirm/lawyers/{lawyer_id}/reviews`

## 3. 开发者常见坑

- **两套 consultation 的 ID 体系不同**：

  - AI：`session_id`（string）
  - 律师预约：`consultation_id`（int）
    前端/运营导出/日志排查时不要混用。

- **咨询取消退款限制**：律师预约的 cancel 目前仅支持余额支付自动退款，第三方支付需要走管理员退款流程。
