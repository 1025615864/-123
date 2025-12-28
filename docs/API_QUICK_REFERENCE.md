# API 速查（News / News AI / SystemConfig）

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

---

## 1. News（新闻）

### 1.1 公共接口（无需登录）

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

### 1.2 登录用户接口（需要 JWT）

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

### 1.3 管理员接口（需要管理员 JWT）

> 备注：具体列表/过滤项以 Swagger 为准。

- `POST /api/news`
  - 创建新闻
- `PUT /api/news/{news_id}`
  - 更新新闻
  - 并发兜底：若发生 `StaleDataError` 会 rollback 并重试一次；仍失败返回 409。
- `DELETE /api/news/{news_id}`
  - 删除新闻

#### News AI 管理操作

- `POST /api/news/admin/{news_id}/ai/rerun`
  - 手动重跑单条新闻 AI 标注（管理员）

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

## 2. SystemConfig（系统配置，管理员）

- `GET /api/system/configs`
  - 获取全部配置（返回会对敏感值做脱敏）
- `GET /api/system/configs/{key}`
- `PUT /api/system/configs/{key}`
- `POST /api/system/configs/batch`

### 2.1 Secrets 拦截规则（非常重要）

- 任何写入 key/value 触发敏感字段校验会返回 400：
  - key 名包含：`secret/password/api_key/apikey/private_key` 等
  - 或写入 providers JSON/B64 且 JSON 内包含 `api_key/apikey`

---

## 3. News AI 运维（管理员）

- `GET /api/system/news-ai/status`
  - 查看：providers（脱敏）、策略、response_format、积压量、错误趋势、最近错误等

---

## 4. 调试建议

- 首选打开 Swagger：`GET /docs`
- 生产排障优先看：
  - `/api/system/news-ai/status`
  - `NewsAIAnnotation` 的 `retry_count/last_error/last_error_at`
