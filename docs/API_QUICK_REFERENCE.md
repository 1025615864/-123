# API 速查（核心模块）

> 目标：给接手同事一个“最常用接口”索引，便于联调、运维与排障。
>
> 说明：本文只列关键路径；完整 API 以 Swagger 为准：`/docs`。

---

## 0. 基础

- API 前缀：`/api`
- 健康检查：

  - `GET /health`
  - `GET /api/health`
  - `GET /health/detailed`

- WebSocket：

  - `WS /ws?token=<jwt>`
  - `GET /ws/status`

- 登录：
  - `POST /api/user/login`
  - 说明：JWT 位于响应的 `token.access_token`（不是顶层 `access_token`）。

---

## 1. User（用户/认证）

### 1.1 公共接口

- `POST /api/user/register`
- `POST /api/user/login`
- `POST /api/user/password-reset/request`
- `POST /api/user/password-reset/confirm`

### 1.2 登录用户接口

- `GET /api/user/me`
- `PUT /api/user/me`
- `PUT /api/user/me/password`
- `GET /api/user/me/stats`

### 1.3 管理员接口

- `GET /api/user/admin/list`
- `PUT /api/user/admin/{user_id}/toggle-active`
- `PUT /api/user/admin/{user_id}/role`
- `GET /api/user/{user_id}/stats`

---

## 2. AI 法律助手（咨询）

> 依赖 `OPENAI_API_KEY`（必须通过环境变量/Secret 注入）。

- `POST /api/ai/chat`
- `POST /api/ai/chat/stream`（SSE）
- `GET /api/ai/consultations`
- `GET /api/ai/consultations/{session_id}`
- `DELETE /api/ai/consultations/{session_id}`
- `GET /api/ai/consultations/{session_id}/export`
- `POST /api/ai/messages/rate`

---

## 3. Forum（论坛）

### 3.1 公共接口

- `GET /api/forum/posts`
- `GET /api/forum/hot`
- `GET /api/forum/posts/{post_id}`
- `GET /api/forum/posts/{post_id}/comments`

### 3.2 登录用户接口

- `POST /api/forum/posts`
- `PUT /api/forum/posts/{post_id}`
- `DELETE /api/forum/posts/{post_id}`
- `POST /api/forum/posts/{post_id}/restore`
- `DELETE /api/forum/posts/{post_id}/purge`
- `POST /api/forum/posts/{post_id}/like`
- `POST /api/forum/posts/{post_id}/favorite`
- `GET /api/forum/favorites`
- `POST /api/forum/posts/{post_id}/comments`
- `DELETE /api/forum/comments/{comment_id}`
- `POST /api/forum/comments/{comment_id}/like`
- `POST /api/forum/posts/{post_id}/reaction`

### 3.3 管理员审核/运营

- `GET /api/forum/admin/posts`
- `POST /api/forum/admin/posts/{post_id}/pin`
- `POST /api/forum/admin/posts/{post_id}/hot`
- `POST /api/forum/admin/posts/{post_id}/essence`
- `POST /api/forum/admin/posts/{post_id}/review`
- `POST /api/forum/admin/comments/{comment_id}/review`
- `POST /api/forum/admin/posts/review/batch`
- `POST /api/forum/admin/comments/review/batch`

---

## 4. Knowledge（知识库）

- `GET /api/knowledge/laws`
- `POST /api/knowledge/laws`
- `GET /api/knowledge/laws/{knowledge_id}`
- `PUT /api/knowledge/laws/{knowledge_id}`
- `DELETE /api/knowledge/laws/{knowledge_id}`
- `POST /api/knowledge/laws/batch-delete`

- `POST /api/knowledge/laws/{knowledge_id}/vectorize`
- `POST /api/knowledge/laws/batch-vectorize`
- `POST /api/knowledge/sync-vector-store`

- `GET /api/knowledge/stats`
- `GET /api/knowledge/categories`
- `POST /api/knowledge/categories`
- `PUT /api/knowledge/categories/{category_id}`
- `DELETE /api/knowledge/categories/{category_id}`

- `GET /api/knowledge/templates`
- `POST /api/knowledge/templates`
- `GET /api/knowledge/templates/{template_id}`
- `PUT /api/knowledge/templates/{template_id}`
- `DELETE /api/knowledge/templates/{template_id}`

- `POST /api/knowledge/laws/batch-import`
- `POST /api/knowledge/laws/import-csv`

---

## 5. LawFirm（律所/律师）

- `GET /api/lawfirm/firms`
- `GET /api/lawfirm/firms/{firm_id}`
- `GET /api/lawfirm/lawyers`
- `GET /api/lawfirm/lawyers/{lawyer_id}`
- `GET /api/lawfirm/lawyers/{lawyer_id}/reviews`

- `POST /api/lawfirm/consultations`（登录）
- `GET /api/lawfirm/consultations`（登录）
- `POST /api/lawfirm/reviews`（登录）

- `POST /api/lawfirm/verification/apply`（登录）
- `GET /api/lawfirm/verification/status`（登录）

管理员：

- `GET /api/lawfirm/admin/firms`
- `PUT /api/lawfirm/admin/firms/{firm_id}`
- `DELETE /api/lawfirm/admin/firms/{firm_id}`
- `GET /api/lawfirm/admin/verifications`
- `POST /api/lawfirm/admin/verifications/{verification_id}/review`

---

## 6. News（新闻）

### 6.1 公共接口（无需登录）

- `GET /api/news`
  - 新闻列表（分页、分类、keyword）
- `GET /api/news/{news_id}`
  - 新闻详情（包含 `ai_annotation`）
- `GET /api/news/{news_id}/related`
  - 相关新闻
- `GET /api/news/hot`
  - 热门新闻
- `GET /api/news/top`
  - 置顶新闻
- `GET /api/news/recent`
  - 最新新闻
- `GET /api/news/categories`
  - 分类统计
- `GET /api/news/topics`
  - 专题列表
- `GET /api/news/topics/{topic_id}`
  - 专题详情
- `GET /api/news/recommended`
  - 推荐新闻

### 6.2 登录用户接口（需要 JWT）

- `GET /api/news/favorites`
  - 我的收藏列表
- `POST /api/news/{news_id}/favorite`
  - 收藏/取消收藏
- `GET /api/news/history`
  - 最近浏览
- `GET /api/news/subscriptions`
  - 我的订阅
- `POST /api/news/subscriptions`
  - 创建订阅
- `DELETE /api/news/subscriptions/{sub_id}`
  - 删除订阅
- `GET /api/news/subscribed`

  - 我的订阅新闻列表

- `GET /api/news/{news_id}/comments`
  - 新闻评论列表
- `POST /api/news/{news_id}/comments`
  - 发表评论

### 6.3 管理员接口（需要管理员 JWT）

> 备注：具体列表/过滤项以 Swagger 为准。

- `POST /api/news`
  - 创建新闻
- `PUT /api/news/{news_id}`
  - 更新新闻
  - 并发兜底：若发生 `StaleDataError` 会 rollback 并重试一次；仍失败返回 409。
- `DELETE /api/news/{news_id}`

  - 删除新闻

- `GET /api/news/admin/{news_id}`
  - 管理员新闻详情

#### News AI 管理操作

- `POST /api/news/admin/{news_id}/ai/rerun`

  - 手动重跑单条新闻 AI 标注（管理员）

- `POST /api/news/admin/ai/generate`
  - 新闻 AI 工作台生成（管理员）

#### 新闻版本（管理员）

- `GET /api/news/admin/{news_id}/versions?limit=50`
- `POST /api/news/admin/{news_id}/rollback`

#### 链接提取/检查（管理员）

- `POST /api/news/admin/link_check`
- `GET /api/news/admin/link_check/{run_id}`

#### 专题（管理员）

- `GET /api/news/admin/topics`
- `POST /api/news/admin/topics`
- `PUT /api/news/admin/topics/{topic_id}`
- `DELETE /api/news/admin/topics/{topic_id}`
- `GET /api/news/admin/topics/{topic_id}`
- `POST /api/news/admin/topics/{topic_id}/items`
- `PUT /api/news/admin/topics/{topic_id}/items/{item_id}`
- `DELETE /api/news/admin/topics/{topic_id}/items/{item_id}`

#### RSS 采集（管理员）

- `GET /api/news/admin/sources`
  - 采集来源列表（DB 配置）
- `POST /api/news/admin/sources`
  - 创建采集来源
- `PUT /api/news/admin/sources/{source_id}`
  - 更新采集来源
- `DELETE /api/news/admin/sources/{source_id}`
  - 删除采集来源（同时清理该来源的 ingest runs）
- `POST /api/news/admin/sources/{source_id}/ingest/run-once`
  - 手动触发单个来源采集
- `GET /api/news/admin/ingest-runs`
  - 采集运行记录列表（可按 source_id/status 过滤；支持 `from/to` ISO 时间过滤 created_at）

---

## 7. Payment（支付）

### 7.1 登录用户接口

- `POST /api/payment/orders`
- `POST /api/payment/orders/{order_no}/pay`
- `POST /api/payment/orders/{order_no}/cancel`
- `GET /api/payment/orders`
- `GET /api/payment/orders/{order_no}`

- `GET /api/payment/balance`
- `GET /api/payment/balance/transactions`

### 7.2 回调

- `POST /api/payment/webhook`（验签）

### 7.3 管理员接口

- `GET /api/payment/admin/orders`
- `POST /api/payment/admin/refund/{order_no}`
- `POST /api/payment/admin/orders/{order_no}/mark-paid`
- `GET /api/payment/admin/stats`

---

## 8. Documents（文书生成）

- `POST /api/documents/generate`
- `GET /api/documents/types`

---

## 9. Upload（上传）

- `POST /api/upload/avatar`
- `GET /api/upload/avatars/{filename}`

- `POST /api/upload/image`
- `GET /api/upload/images/{filename}`

- `POST /api/upload/file`
- `GET /api/upload/files/{filename}`

---

## 10. Notifications（通知）

- `GET /api/notifications`
- `GET /api/notifications/unread-count`
- `PUT /api/notifications/{notification_id}/read`
- `PUT /api/notifications/read-all`
- `POST /api/notifications/batch-read`
- `POST /api/notifications/batch-delete`
- `GET /api/notifications/types`

管理员：

- `POST /api/notifications/admin/broadcast`
- `GET /api/notifications/admin/system`

---

## 11. Search（全局搜索）

- `GET /api/search?q=<keyword>`
- `GET /api/search/suggestions?q=<keyword>`
- `GET /api/search/hot`
- `GET /api/search/history`
- `DELETE /api/search/history`

---

## 12. Admin（统计/导出，管理员）

- `GET /api/admin/stats`
- `GET /api/admin/export/users`
- `GET /api/admin/export/posts`
- `GET /api/admin/export/news`
- `GET /api/admin/export/lawfirms`
- `GET /api/admin/export/knowledge`
- `GET /api/admin/export/consultations`

---

## 13. SystemConfig（系统配置，管理员）

- `GET /api/system/configs`
  - 获取全部配置（返回会对敏感值做脱敏）
- `GET /api/system/configs/{key}`
- `PUT /api/system/configs/{key}`
- `POST /api/system/configs/batch`

### 13.1 Secrets 拦截规则（非常重要）

- 任何写入 key/value 触发敏感字段校验会返回 400：
  - key 名包含：`secret/password/api_key/apikey/private_key` 等
  - 或写入 providers JSON/B64 且 JSON 内包含 `api_key/apikey`

---

## 14. News AI 运维（管理员）

- `GET /api/system/news-ai/status`
  - 查看：providers（脱敏）、策略、response_format、积压量、错误趋势、最近错误等

---

## 15. 调试建议

- 首选打开 Swagger：`GET /docs`
- 生产排障优先看：
  - `/api/system/news-ai/status`
  - `NewsAIAnnotation` 的 `retry_count/last_error/last_error_at`

---

## 16. 备注

- `/api/ai/*` 路由为可选模块，初始化失败时可能不会被加载（以 Swagger 为准）。
