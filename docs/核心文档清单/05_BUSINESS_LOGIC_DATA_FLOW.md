# 核心业务逻辑与数据流（Business Logic & Data Flow）

本文件以“**从 API 入口 → 服务层 → 数据库交互**”的方式，描述本项目最核心的业务流程调用链路，并指出关键的业务校验与状态机。

---

## 1. 认证与用户生命周期

### 1.1 注册

- **入口**：`POST /api/user/register`
  - 文件：`backend/app/routers/user.py::register`
- **关键校验**：
  - 必须同意：用户协议/隐私政策/AI 免责声明
  - username/email 唯一性检查
- **核心调用**：
  - Router → `user_service.create()`（`backend/app/services/user_service.py`）
  - 写 DB：`users`
  - 写合规记录：`user_consents`（terms/privacy/ai_disclaimer）
  - 发送邮箱验证（若未验证）：`email_service.generate_email_verification_token()` + `send_email_verification_email()`

### 1.2 登录

- **入口**：`POST /api/user/login`
  - 文件：`backend/app/routers/user.py::login`
- **核心调用**：
  - Router → `user_service.authenticate()`
  - `verify_password()`（PBKDF2-SHA256）
  - `create_access_token({sub:user_id})`（`backend/app/utils/security.py`）
- **返回**：JWT token + user

### 1.3 鉴权中间流程

- **依赖**：`backend/app/utils/deps.py::get_current_user`
  - 解析 `Authorization: Bearer <token>`
  - `decode_token()` → `sub` → 查询 `users`
  - 校验 `is_active`

### 1.4 邮箱验证 / 手机绑定

- 邮箱：
  - 请求：`POST /api/user/email-verification/request`
  - 验证：`GET /api/user/email-verification/verify?token=...`
- 短信：
  - 发送：`POST /api/user/sms/send`（写入 Redis/Cache；开发环境返回 code）
  - 校验绑定：`POST /api/user/sms/verify`（更新 `users.phone_verified`）

---

## 2. AI 法律咨询（AI Chat）

### 2.1 同步/流式聊天

- **入口**：
  - `POST /api/ai/chat`
  - `POST /api/ai/chat/stream`
  - 文件：`backend/app/routers/ai.py`
- **限流/配额**：
  - 游客：`_enforce_guest_ai_quota()`（按 IP，内存滑窗）
  - 登录用户：`quota_service.consume_ai_chat()`（按日配额 + 次数包）
- **数据落库**：
  - `consultations`：会话
  - `chat_messages`：消息
- **外部依赖**：
  - 通过 `services/ai_assistant.py` 抽象 AI Provider（OpenAI-compatible）。

---

## 3. 文书生成（Documents）

### 3.1 生成

- **入口**：`POST /api/documents/generate`
  - 文件：`backend/app/routers/document.py::generate_document`
- **关键校验**：
  - 游客生成次数（可通过 env 配置）
  - 登录用户：`quota_service.enforce_document_generate_quota()`
  - 输入长度限制（facts/claims/evidence）
- **模板选择**：
  - 优先：DB 已发布模板
    - `document_templates` + `document_template_versions(is_published=true)`
  - 否则：内置模板 `services/document_templates_builtin.py`
- **生成结果**：返回 `DocumentResponse`（不自动保存）

### 3.2 保存与查询

- 保存：`POST /api/documents/save` → 写 `generated_documents`
- 我的列表：`GET /api/documents/my`（分页）
- 导出 PDF：`GET /api/documents/my/{doc_id}/export?format=pdf`

---

## 4. 论坛（Forum）与内容审核

### 4.1 发帖

- **入口**：`POST /api/forum/posts`
  - 文件：`backend/app/routers/forum.py::create_post`
- **关键链路**：
  - Router → `forum_service.apply_content_filter_config_from_db()`：加载/缓存内容过滤规则
  - `check_post_content(title, content)`：敏感词/广告/URL/电话等
  - Router → `forum_service.create_post()`：写 `posts`
  - 若 `review_status=pending`：写 `notifications` 通知用户“已提交审核”

### 4.2 评论

- **入口**：`POST /api/forum/posts/{post_id}/comments`
  - 文件：`backend/app/routers/forum.py::create_comment`
- **关键点**：
  - 类似敏感词检测
  - 评论支持 `parent_id` 自关联

### 4.3 运营配置

- 审核开关与规则存储在 `system_configs`：
  - `forum.review.enabled`
  - `forum.post_review.enabled`
  - `forum.content_filter.*`

---

## 5. 新闻（News）与 News AI Pipeline

### 5.1 新闻列表消费

- **入口**：`GET /api/news`
  - 文件：`backend/app/routers/news.py::get_news_list`
- **核心调用**：
  - Router → `news_service.get_list(...)`（`backend/app/services/news_service.py`）
  - 仅公开内容：`is_published=true` 且 `review_status=approved`
  - 额外聚合：收藏状态、AI 风险等级、AI 关键词

### 5.2 RSS 采集与运行记录

- 表：`news_sources`、`news_ingest_runs`
- 周期任务：`backend/app/main.py`（Redis 可用时启用分布式锁，避免多副本重复跑）

### 5.3 News AI 标注

- 表：`news_ai_annotations`
- 服务：`backend/app/services/news_ai_pipeline_service.py::run_once`
  - 选取待处理新闻
  - 先做本地内容过滤与风险判断
  - 可调用 LLM 生成摘要/关键词/高亮
  - 错误记录与重试
- 管理端运维：`GET /api/system/news-ai/status`（脱敏 providers 配置）

### 5.4 新闻工作台（版本/回滚/链接检查）

- 表：`news_versions`、`news_ai_generations`、`news_link_checks`
- 迁移：Alembic `b9c7a0f3d2a1_add_news_workbench_tables.py`

---

## 6. 支付与订单（Payment）

### 6.1 创建订单

- **入口**：`POST /api/payment/orders`
  - 文件：`backend/app/routers/payment.py::create_order`
- **关键分支**：
  - `order_type=vip`：读取 VIP 方案（天数/价格）
  - `order_type=ai_pack`：按次数包定价（AI 咨询/文书生成）
  - 其他：直接使用传入金额（并做 >0 校验）
- **写库**：`payment_orders`（状态 `pending`，2h 过期）

### 6.2 发起支付

- **入口**：`POST /api/payment/orders/{order_no}/pay`
  - 文件：`backend/app/routers/payment.py::pay_order`
- **支持方式**：
  - `balance`：余额扣减 + 订单置为 paid + 写流水 + 触发权益
  - `alipay`：生成支付跳转 URL
  - `ikunpay`：生成支付跳转 URL
  - `wechat`：明确返回 400（暂未开放）

### 6.3 支付回调与审计

- 支付宝：`POST /api/payment/alipay/notify`
  - RSA2 验签、校验金额与订单状态
  - 成功：`_mark_order_paid_in_tx()` + `payment_callback_events` 记录
- Ikunpay：`GET/POST /api/payment/ikunpay/notify`
  - MD5 验签、校验金额与订单状态
  - 成功：同上

### 6.4 支付后权益发放（VIP/次数包/咨询确认）

- 在 `pay_order(balance)` 或回调 `mark_paid` 中执行：
  - `_maybe_apply_vip_membership_in_tx(db, order)`：更新 `users.vip_expires_at`
  - `_maybe_apply_ai_pack_in_tx(db, order)`：更新 `user_quota_pack_balances`
  - `_maybe_confirm_lawyer_consultation_in_tx(db, order)`：联动律师咨询状态

---

## 7. 律所咨询预约与结算

### 7.1 用户预约咨询

- **入口**：`POST /api/lawfirm/consultations`
  - 文件：`backend/app/routers/lawfirm.py::create_consultation`
- **关键点**：
  - 若律师 `consultation_fee>0`：创建 `payment_orders`（related_type=`lawyer_consultation`）

### 7.2 律师侧接单

- **入口**：`POST /api/lawfirm/lawyer/consultations/{id}/accept`
- **关键校验**：
  - 若存在未支付订单：拒绝接单（提示用户先支付）

### 7.3 结算与提现

- **入口**：`backend/app/routers/settlement.py`
  - 律师：钱包、收入记录、提现
  - 管理员：提现审核与导出
- **周期任务**：`backend/app/main.py` 中 `settlement_service.settle_due_income_records()`（生产建议 Redis 锁）

---

## 8. 典型请求链路示例（支付-回调闭环）

1. 前端下单：`POST /api/payment/orders`
2. 前端发起支付：`POST /api/payment/orders/{order_no}/pay` → 得到 `pay_url`
3. 用户在第三方完成支付
4. 第三方回调：`/api/payment/{provider}/notify`
5. 后端：
   - 验签
   - 校验订单、金额
   - `payment_orders.status = paid` + `payment_callback_events` 审计
   - 发放权益（VIP/次数包/咨询确认）
6. 前端：用户回跳 `#/payment/return?order_no=...` 轮询/查询订单状态
