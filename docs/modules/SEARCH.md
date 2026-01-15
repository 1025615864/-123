# 搜索模块（SEARCH）

本模块描述全局搜索、搜索建议、热门词、搜索历史的实现。

## 1. 路由

- Router：`backend/app/routers/search.py`
- Prefix：`/api/search`

## 2. API

- `GET /api/search?q=<keyword>&limit=10`

  - `q` 最小长度 2
  - 未登录也可以用（`get_current_user_optional`）
  - 会尝试记录搜索历史（失败不影响搜索结果）

- `GET /api/search/suggestions?q=<keyword>&limit=5`

- `GET /api/search/hot?limit=10`

- `GET /api/search/history?limit=10`

  - 未登录返回空列表

- `DELETE /api/search/history`
  - 未登录返回 `{"message":"未登录"}`

## 3. SearchService 实现要点

实现：`backend/app/services/search_service.py`

- 关键词匹配：使用 `ilike` + escape（防止 `%/_` 造成模糊匹配异常）
- 返回的结果集结构：
  - `news/posts/lawfirms/lawyers/knowledge`

排序策略（news）：

- title 命中优先级最高，其次 summary，其次 content
- 然后按 `is_top/published_at/view_count/created_at` 综合排序

snippet：

- `SearchService._make_snippet()` 会截取包含关键词附近的上下文（最多 120 chars）

## 4. 搜索历史与热门词

- `record_search()`：尝试写入 `SearchHistory`（来自 `backend/app/models/system.py`）
- `get_hot_keywords()`：
  - 若 `SearchHistory` 表存在，按 count 聚合
  - 若异常（表不存在等），返回内置默认热词（保证线上不崩）

## 5. 生产注意

- 如果你希望 hot/history 真正生效，需要确保 DB migration 已包含 `search_history` 表。
- 当前 search 没有额外 rate limit 装饰器，若遇到爬虫压力建议在 router 上加 `rate_limit` 或在中间件层做路径级限流。
