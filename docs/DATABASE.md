# 数据库设计

> 数据库通过 SQLAlchemy 模型定义（`backend/app/models`），默认 SQLite（`sqlite+aiosqlite:///./data/app.db`），生产推荐 PostgreSQL。

## 迁移规范（Alembic，SQLite/PG 双模式）

本项目同时支持：

- **开发/轻量部署**：SQLite（默认）
- **生产/多实例**：PostgreSQL（推荐）

为保证两种数据库下的结构一致，建议统一采用 Alembic 做“正式迁移”。当前代码在生产环境默认启用 **Alembic head 门禁**：当 `DEBUG=false` 且未设置 `DB_ALLOW_RUNTIME_DDL=1` 时，启动阶段会校验 DB 是否已升级到 `head`，否则启动失败并给出迁移命令指引。

同时，代码也保留了运行时 DDL 的兜底路径（仅用于本地开发/应急）：当 `DEBUG=true` 或显式设置 `DB_ALLOW_RUNTIME_DDL=1` 时，`init_db()` 允许执行 `create_all` 与少量补列/补索引逻辑。

> 注意：从第十二阶段（P0.1）开始，生产环境（`DEBUG=false`）将逐步收敛为 **Alembic Only**：
>
> - 生产环境默认 **禁止运行时 DDL**（建表/补列/补索引）。
> - 启动时会校验 DB 是否已升级到 Alembic `head`，否则启动失败并提示迁移命令。
> - 如需临时放行（不建议长期使用），可设置 `DB_ALLOW_RUNTIME_DDL=1`。

### 1) 基本约定

- **模型是权威**：以 `backend/app/models` 的 SQLAlchemy 模型为最终结构来源。
- **迁移是可追溯变更**：凡是新增表/字段/索引/约束，优先走 Alembic migration。
- **SQLite 自修复仅兜底**：只用于历史数据库补列、补索引等“低风险增量”，避免复杂变更（如重命名列/改类型/拆表）。

### 2) Alembic 配置与模型发现

- Alembic 配置位于：`backend/alembic.ini`、`backend/alembic/env.py`。
- `env.py` 通过 `from app.models import *` 加载模型，因此需确保 `backend/app/models/__init__.py` 导出所有 ORM 模型，避免 autogenerate 漏表。

### 3) 常用命令（建议在 backend 目录执行）

说明：若环境中未将 `alembic` 安装为可执行命令（或未加入 PATH），可使用封装脚本：

- `py scripts/alembic_cmd.py <cmd> ...`

#### 3.1 查看当前版本

- `alembic current`
- 或：`py scripts/alembic_cmd.py current`

#### 3.2 生成迁移（autogenerate）

- `alembic revision --autogenerate -m "add_xxx"`
- 或：`py scripts/alembic_cmd.py revision --autogenerate -m "add_xxx"`

建议：

- 生成后务必检查脚本，确认仅包含预期变更。
- 对 SQLite 不友好的操作（如 ALTER COLUMN）需要在迁移脚本中做兼容处理或采用“新表+拷贝+rename”的方式。

#### 3.3 执行迁移

- `alembic upgrade head`
- 或：`py scripts/alembic_cmd.py upgrade head`

#### 3.5 生产启动前的“门禁”说明

当 `DEBUG=false` 时，后端启动会检查当前 DB 的 Alembic 版本是否为 `head`：

- 若不是 `head`：启动失败，并提示你运行 `py scripts/alembic_cmd.py upgrade head`
- 若 DB 已经是“正确结构”但没有 alembic 版本记录：可以执行 `py scripts/alembic_cmd.py stamp head`

临时兜底开关（不建议长期使用）：

- `DB_ALLOW_RUNTIME_DDL=1`：允许 `init_db()` 执行运行时 DDL（仅用于应急/临时兼容）

#### 3.4 回滚迁移

- `alembic downgrade -1`
- 或：`py scripts/alembic_cmd.py downgrade -1`

### 4) SQLite 与 PostgreSQL 的注意事项

- **SQLite 的 ALTER TABLE 能力有限**：改列类型/删除列/复杂约束调整通常需要“重建表”。
- **生产推荐 PG**：需要更强一致性与并发能力的场景请使用 PostgreSQL，并在 CI/预发布环境验证迁移脚本。

---

## 运维 Runbook（DB 备份/恢复/演练/迁移发布/回滚）

> 本 Runbook 复用仓库内脚本：`backend/scripts/db_backup.py`、`db_restore.py`、`db_drill.py`。

### 0) 前置检查

- DB 连接以 `DATABASE_URL` 为准（默认 SQLite：`sqlite+aiosqlite:///./data/app.db`）。
- PostgreSQL 备份/恢复依赖：
  - `pg_dump` / `pg_restore` 在 PATH 中可用（脚本会检查）。
- 建议在 `backend/` 目录执行。

---

### 1) 备份（Backup）

#### 1.1 SQLite 备份

```bash
cd backend
py scripts/db_backup.py
```

默认输出到：

- `backend/backups/sqlite_YYYYMMDD_HHMMSS.db`

#### 1.2 PostgreSQL 备份（建议带连通性校验）

```bash
cd backend
set DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
py scripts/db_backup.py --verify
```

默认输出到：

- `backend/backups/postgres_YYYYMMDD_HHMMSS.dump`（pg_dump custom format）

保留策略（可选）：

```bash
cd backend
py scripts/db_backup.py --retention-count 20
py scripts/db_backup.py --retention-days 7
```

建议默认保留策略（可作为生产基线）：

- 日常备份：`--retention-days 7`（保留最近 7 天）
- 关键节点（发布前/大迁移前）额外保留：`--retention-count 20`（保留最近 20 份）

恢复演练周期建议（强烈推荐）：

- 至少每月执行 1 次 drill restore（在独立 drill DB/临时 sqlite 文件上），确保备份文件与恢复链路有效。
- 演练通过后再进行“迁移发布/大版本升级”。

本仓库示例（已执行一次 drill 并归档）：

- `docs/_archive/DB_DRILL_REPORT_2026-01-13.md`

---

### 2) 恢复（Restore）

#### 2.1 SQLite 恢复（覆盖目标 DB）

```bash
cd backend
py scripts/db_restore.py backups/sqlite_YYYYMMDD_HHMMSS.db --force
```

说明：

- 不加 `--force` 时，如果目标 DB 已存在会拒绝覆盖。

#### 2.2 PostgreSQL 恢复（高风险操作：会清理目标库对象）

```bash
cd backend
set DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
py scripts/db_restore.py backups/postgres_YYYYMMDD_HHMMSS.dump --verify
```

说明：

- 内部使用 `pg_restore --clean --if-exists`，会清理目标库对象。
- 强烈建议只对“明确的目标环境库”操作，避免误伤生产主库。

---

### 3) 恢复演练（Drill Restore）

目标：不要在主库上做恢复，通过 drill 验证：

- 备份文件可用
- 恢复链路可用
- `init_db()` 能在恢复后的库上正常运行（验证 schema/bootstrap）

#### 3.1 SQLite drill（默认恢复到临时 sqlite 文件）

```bash
cd backend
py scripts/db_drill.py
```

#### 3.2 PostgreSQL drill（必须提供独立 drill DB）

```bash
cd backend
set DATABASE_URL=postgresql+asyncpg://prod_user:prod_pass@prod_host:5432/prod_db
py scripts/db_drill.py --drill-database-url postgresql+asyncpg://drill_user:drill_pass@drill_host:5432/drill_db --verify
```

---

### 4) 迁移发布（Deploy with migrations）

建议发布流程：

1. 备份（生产必做）
2. 执行迁移：`alembic upgrade head`
3. 再滚动发布 backend（K8s/Compose）

命令：

```bash
cd backend
py scripts/alembic_cmd.py upgrade head
```

生产门禁补充：

- `DEBUG=false` 时后端启动会检查 DB 是否在 Alembic `head`：
  - 不在 head：启动失败并提示 upgrade 命令
  - 若 DB 结构正确但没有 alembic 版本记录：可 `stamp head`（谨慎）

```bash
cd backend
py scripts/alembic_cmd.py stamp head
```

---

### 5) 回滚策略（Rollback）

优先级（推荐从上到下）：

1. 应用回滚（推荐）

- 回滚到上一版本 tag/镜像
- DB 不回滚（长期建议迁移尽量向前兼容）

2. 数据回滚（通过备份恢复）

- SQLite：`db_restore.py` + `--force`
- PostgreSQL：`db_restore.py`（会 clean；务必对准目标库）

3. Schema 回滚（谨慎使用）

```bash
cd backend
py scripts/alembic_cmd.py downgrade -1
```

说明：

- downgrade 未必可逆（尤其涉及数据迁移/字段语义变化），只作为最后手段。

## ER 图

- 建议后续补充（可由 SQLAlchemy model 自动生成）。
- 当前以“表结构 + 关键关系/约束”作为交接口径。

---

## 数据表结构（按模块）

### 1) 用户与合规模块

#### users 用户表

| 字段              | 类型         | 说明              | 约束                          |
| ----------------- | ------------ | ----------------- | ----------------------------- |
| id                | int          | 主键              | PK                            |
| username          | varchar(50)  | 用户名            | UNIQUE, NOT NULL, index       |
| email             | varchar(100) | 邮箱              | UNIQUE, NOT NULL, index       |
| nickname          | varchar(50)  | 昵称              |                               |
| phone             | varchar(20)  | 手机号            |                               |
| email_verified    | bool         | 邮箱是否已验证    | default false                 |
| email_verified_at | datetime     | 邮箱验证时间      |                               |
| phone_verified    | bool         | 手机是否已验证    | default false                 |
| phone_verified_at | datetime     | 手机验证时间      |                               |
| hashed_password   | varchar(255) | 密码哈希          | NOT NULL                      |
| avatar            | varchar(255) | 头像 URL          |                               |
| role              | varchar(20)  | user/lawyer/admin | default user                  |
| is_active         | bool         | 是否启用          | default true                  |
| vip_expires_at    | datetime     | VIP 到期          |                               |
| created_at        | datetime     | 创建时间          | server_default now            |
| updated_at        | datetime     | 更新时间          | server_default now + onupdate |

#### user_consents 用户协议同意记录

| 字段        | 类型         | 说明                        | 约束                  |
| ----------- | ------------ | --------------------------- | --------------------- |
| id          | int          | 主键                        | PK                    |
| user_id     | int          | 用户                        | FK -> users.id, index |
| doc_type    | varchar(50)  | terms/privacy/ai_disclaimer | NOT NULL              |
| doc_version | varchar(50)  | 版本号                      | NOT NULL              |
| agreed_at   | datetime     | 同意时间                    | server_default now    |
| ip          | varchar(64)  | IP                          |                       |
| user_agent  | varchar(500) | UA                          |                       |

唯一约束：`(user_id, doc_type, doc_version)`。

#### user_quota_daily 用户每日用量

- 表：`user_quota_daily`
- 唯一：`(user_id, day)`
- 字段：`ai_chat_count`、`document_generate_count`

#### user_quota_pack_balances 次数包余额

- 表：`user_quota_pack_balances`
- 唯一：`(user_id)`
- 字段：`ai_chat_credits`、`document_generate_credits`

---

### 2) AI 咨询模块

#### consultations 会话表

| 字段                  | 类型         | 说明                         |
| --------------------- | ------------ | ---------------------------- |
| id                    | int          | PK                           |
| user_id               | int          | FK -> users.id，可空（游客） |
| session_id            | varchar(50)  | 会话标识，唯一               |
| title                 | varchar(200) | 会话标题                     |
| created_at/updated_at | datetime     | 时间戳                       |

#### chat_messages 消息表

| 字段            | 类型        | 说明                   |
| --------------- | ----------- | ---------------------- |
| id              | int         | PK                     |
| consultation_id | int         | FK -> consultations.id |
| role            | varchar(20) | user/assistant         |
| content         | text        | 内容                   |
| references      | text        | JSON（引用信息）       |
| rating          | int         | 评价（1-3）            |
| feedback        | text        | 用户反馈               |
| created_at      | datetime    | 创建时间               |

---

#### consultation_review_tasks 律师复核任务

- 表：`consultation_review_tasks`
- 说明：用户为某次 AI 咨询购买“律师复核”后生成的任务，律师可领取并提交复核稿。
- 唯一约束：`order_id` 唯一（防重复发放/重复建任务）。
- 关键字段：
  - `consultation_id`：FK -> `consultations.id`
  - `user_id`：FK -> `users.id`
  - `order_id` / `order_no`：FK -> `payment_orders.id`；`order_no` 冗余便于检索
  - `status`：`pending/claimed/submitted`
  - `lawyer_id`：FK -> `lawyers.id`（可空，未领取）
  - `result_markdown`：最终复核稿（Markdown）
  - `claimed_at/submitted_at/created_at/updated_at`

#### consultation_review_versions 复核版本

- 表：`consultation_review_versions`
- 说明：每次提交/更新复核稿时写入一条版本记录用于审计与追溯。
- 关键字段：
  - `task_id`：FK -> `consultation_review_tasks.id`
  - `editor_user_id`：FK -> `users.id`
  - `editor_role`：例如 `lawyer`
  - `content_markdown`：提交内容
  - `created_at`

---

### 3) 论坛模块

#### posts 帖子表

包含：标题、正文、分类、封面/图片/附件 JSON、浏览/点赞/评论计数、审核字段、软删字段、热度字段等。

#### comments 评论表

包含：内容、父评论、审核字段、软删字段、图片 JSON。

#### post_likes / comment_likes / post_favorites / post_reactions

- 点赞/收藏/表情反应表
- 多数具备 `(post_id, user_id)` 或 `(comment_id, user_id)` 等唯一约束。

---

### 4) 新闻与 News AI

#### news 新闻表

| 字段                                                     | 类型        | 说明           |
| -------------------------------------------------------- | ----------- | -------------- |
| id                                                       | int         | PK             |
| title/summary/content                                    | string/text | 标题/摘要/正文 |
| cover_image                                              | varchar     | 封面           |
| category                                                 | varchar(50) | 分类           |
| source/source_url/source_site                            | varchar     | 来源信息       |
| dedupe_hash                                              | varchar(40) | 去重哈希       |
| view_count                                               | int         | 阅读量         |
| is_top/is_published                                      | bool        | 置顶/发布      |
| review_status/review_reason/reviewed_at                  |             | 审核           |
| published_at/scheduled_publish_at/scheduled_unpublish_at | datetime    | 发布时间与定时 |
| created_at/updated_at                                    | datetime    |                |

#### news_comments 新闻评论

| 字段                        | 类型     | 说明           |
| --------------------------- | -------- | -------------- |
| id                          | int      | PK             |
| news_id                     | int      | FK -> news.id  |
| user_id                     | int      | FK -> users.id |
| content                     | text     | 评论内容       |
| review_status/review_reason |          | 审核           |
| is_deleted                  | bool     | 软删           |
| created_at                  | datetime |                |

#### news_topics / news_topic_items

- 专题表与专题-新闻关联表（`(topic_id, news_id)` 唯一）。

#### news_favorites 新闻收藏

- `(news_id, user_id)` 唯一。

#### news_view_history 浏览历史

- `(news_id, user_id)` 唯一。

#### news_subscriptions 订阅

- `(user_id, sub_type, value)` 唯一。

#### news_sources RSS 来源

- `feed_url` 唯一。

#### news_ingest_runs 采集运行记录

- 记录来源、状态、计数、错误、开始/结束时间等。

#### news_ai_annotations News AI 标注

- `(news_id)` 唯一。
- 字段：summary、risk_level、highlights、keywords、错误与重试、processed_at 等。

#### news_versions / news_ai_generations / news_link_checks

- 新闻版本快照、AI 工作台生成记录、链接检查记录。

---

### 5) 律所/律师/咨询预约

#### law_firms 律师事务所

- 基础信息、评分/认证/启用、专长字段。

#### lawyers 律师

- 关联用户、所属律所、执业信息、评分、咨询费用等。

#### lawyer_verifications 律师认证

- 认证材料与审核状态/审核人。

#### lawyer_consultations 律师咨询预约

- user_id、lawyer_id、subject、description、status、preferred_time 等。

#### lawyer_consultation_messages 咨询留言

- consultation_id、sender_user_id、sender_role、content。

#### lawyer_reviews 律师评价

- lawyer_id、user_id、rating、content。

---

### 6) 支付与余额

#### payment_orders 订单

- order_no 唯一；支持关联 `related_type/related_id`（如 lawyer_consultation）。

#### user_balances 用户余额

- user_id 唯一；记录余额、冻结、累计充值/消费及 cents 字段。

#### balance_transactions 余额流水

- 记录充值/消费/退款等。

#### payment_callback_events 支付回调事件

- `(provider, trade_no)` 唯一；用于回调审计。

---

### 7) 通知与系统

#### notifications 用户通知

- `(user_id, type, dedupe_key)` 唯一。

#### system_configs 系统配置

- key 唯一；后端对敏感字段有拦截（secrets 禁止入库）。

#### admin_logs 管理员操作日志

- user_id + action + module + 描述 + 额外数据。

#### search_history / user_activities / page_views

- 搜索历史与行为追踪/聚合统计。

---

### 8) 文书、日历、反馈

#### generated_documents 生成文书

- user_id、document_type、title、content、payload_json。

#### calendar_reminders 日历提醒

- user_id、title、due_at、remind_at、is_done。

#### feedback_tickets 反馈工单

- user_id、subject、content、status、admin_reply。

---

### 9) 律师结算

#### lawyer_wallets 律师钱包

- lawyer_id 唯一；记录总收入/可用/冻结等。

#### lawyer_income_records 律师收入记录

- 与 consultation/order 关联（字段中保留 consultation_id/order_no）。

#### lawyer_bank_accounts 律师收款账户

- 保存收款信息（部分字段会加密/脱敏处理）。

#### withdrawal_requests 提现申请

- request_no 唯一；包含金额、手续费、状态、审核字段。

---

## 索引与约束（摘录）

- **用户**：`users.username`、`users.email` 唯一
- **新闻**：`news` 多个 index（发布/审核/去重 hash）
- **订阅/收藏**：多处联合唯一约束
- **支付回调**：`(provider, trade_no)` 唯一

> 如需完整索引信息，建议直接查看各模型 `__table_args__`。
