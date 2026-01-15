# 论坛模块（FORUM）

本模块描述社区论坛（帖子/评论/点赞/收藏/表情反应）、内容审核与内容过滤配置。

## 1. 入口与路由

- Router：`backend/app/routers/forum.py`
- Prefix：`/api/forum`

## 2. 核心数据模型

- `posts`（`backend/app/models/forum.py:Post`）

  - 软删除：`is_deleted`
  - 运营属性：`is_pinned/is_hot/is_essence`、`heat_score`
  - 审核字段：`review_status(pending/approved/rejected)`、`review_reason`、`reviewed_at`
  - 多媒体：`images`、`attachments`（JSON string）

- `comments`（`Comment`）

  - 支持楼中楼：`parent_id`
  - 审核字段：`review_status/review_reason/reviewed_at`
  - `is_deleted`

- `post_likes` / `comment_likes`：点赞
- `post_favorites`：收藏
- `post_reactions`：表情反应（unique: `post_id+user_id+emoji`）

## 3. 用户侧 API

### 3.1 帖子

- `GET /api/forum/posts`：列表（category/keyword/is_essence）
- `GET /api/forum/hot`：热门
- `GET /api/forum/posts/{post_id}`：详情（会递增 view_count）
- `POST /api/forum/posts`：发帖（登录）
- `PUT /api/forum/posts/{post_id}`：编辑（作者或管理员）
- `DELETE /api/forum/posts/{post_id}`：删除（作者/版主/管理员）

回收站能力：

- `GET /api/forum/me/posts/deleted`
- `GET /api/forum/posts/{post_id}/recycle`
- `POST /api/forum/posts/{post_id}/restore`
- `DELETE /api/forum/posts/{post_id}/purge`
- `POST /api/forum/posts/batch/restore`
- `POST /api/forum/posts/batch/purge`

### 3.2 评论

- `GET /api/forum/posts/{post_id}/comments`：评论列表
  - `include_unapproved=true` 需要配合角色/权限（service 内会按 viewer_role 控制可见性）
- `POST /api/forum/posts/{post_id}/comments`：发表评论（可回复 parent_id）
- `DELETE /api/forum/comments/{comment_id}`：删除
- `POST /api/forum/comments/{comment_id}/restore`：恢复

### 3.3 点赞/收藏/表情

- `POST /api/forum/posts/{post_id}/like`
- `POST /api/forum/comments/{comment_id}/like`

- `POST /api/forum/posts/{post_id}/favorite`
- `GET /api/forum/favorites`

- `POST /api/forum/posts/{post_id}/reaction`

## 4. 审核与内容过滤（SystemConfig）

论坛的“审核开关”和“内容过滤规则”来自 SystemConfig，并由 `forum_service` 读取 + 缓存。

### 4.1 审核开关

- 评论审核：`forum.review.enabled`（默认 true）
- 帖子审核：`forum.post_review.enabled`（默认 false）
- 帖子审核模式：`forum.post_review.mode`（`all` / `rule`，默认 rule）

管理员接口：

- `GET /api/forum/admin/review-config` / `PUT /api/forum/admin/review-config`
- `GET /api/forum/admin/post-review-config` / `PUT /api/forum/admin/post-review-config`

### 4.2 内容过滤规则

- `forum.content_filter.sensitive_words`（JSON list）
- `forum.content_filter.ad_words`（JSON list）
- `forum.content_filter.ad_words_threshold`（int）
- `forum.content_filter.check_url`（bool）
- `forum.content_filter.check_phone`（bool）

管理员接口：

- `GET /api/forum/admin/content-filter-config`
- `PUT /api/forum/admin/content-filter-config`

缓存：

- `forum_service` 使用 `cache_service` 缓存 `forum:content_filter_config:v1`，TTL=60s。

## 5. 内容审核（管理员）

- 待审核列表：

  - `GET /api/forum/admin/pending-posts`
  - `GET /api/forum/admin/pending-comments`

- 审核动作：
  - `POST /api/forum/admin/posts/{post_id}/review`（approve/reject/delete）
  - `POST /api/forum/admin/comments/{comment_id}/review`（approve/reject/delete）

审核副作用：

- 通过/驳回/删除会写 `AdminLog`（module=forum）
- 会给作者创建 `Notification(type=system)`，link 指向帖子/评论锚点
- 评论通过会更新 `posts.comment_count`（注意：reject/delete 会对 count 进行回滚/扣减）

## 6. 运营能力（管理员）

- `POST /api/forum/admin/posts/{post_id}/pin`
- `POST /api/forum/admin/posts/{post_id}/hot`
- `POST /api/forum/admin/posts/{post_id}/essence`
- `POST /api/forum/admin/update-heat-scores`
- `GET /api/forum/stats`

## 7. 真实踩坑点（来自实现细节）

- **MissingGreenlet**：`get_post` 中 `increment_view()` 会 commit，可能导致后续访问关系字段触发 async 懒加载；router 里通过“重新查询一次（带预加载）”规避。
- **通知类型**：forum 中给用户的“审核通知”使用 `NotificationType.SYSTEM`，这会影响前端筛选/统计，二次开发时注意一致性。
