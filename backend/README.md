# 百姓法律助手 - 后端服务

基于 FastAPI 的后端服务，提供用户、论坛、新闻、系统管理等 API；并包含新闻 AI 标注（摘要/要点/关键词/风险）能力与运维接口。

## 功能特性

- 👤 **用户系统**: 注册、登录、权限与管理员能力
- 💬 **论坛社区**: 发帖、评论、审核、通知
- 📰 **新闻资讯**: 新闻 CRUD/审核/发布/置顶、专题/合集、订阅与通知
- 🧠 **新闻 AI 标注**: 摘要/要点/关键词/风险等级；支持多 Provider、策略与失败切换
- ⚙️ **系统管理**: SystemConfig 配置、运维状态接口

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt

# Windows 提示：若 `python` 指向 WindowsApps stub，优先使用 `py -m pip ...` / `py -m uvicorn ...`
```

### 2. 配置环境变量

复制 `env.example` 为 `.env` 并修改配置：

```bash
cp env.example .env
```

**重要配置项：**

- `DATABASE_URL`: 数据库连接地址
- `JWT_SECRET_KEY` / `SECRET_KEY`: JWT 密钥（生产必填且必须足够安全）
- `PAYMENT_WEBHOOK_SECRET`: 支付回调密钥（生产 `DEBUG=false` 必填）
- `REDIS_URL`: Redis 连接串（生产推荐；`DEBUG=false` 时未连接会禁用定时任务与 News AI pipeline）
- `OPENAI_API_KEY`: LLM API Key（**必须走环境变量/Secret**，禁止写入 SystemConfig 入库）
- `OPENAI_BASE_URL`: LLM API Base URL（可切换 OpenAI-compat 供应商）
- `SQL_ECHO`: （可选）输出 SQLAlchemy SQL 日志（默认关闭；仅本地排障建议开启）

说明：`env.example` 当前默认使用 SQLite（`sqlite+aiosqlite:///./data/app.db`），本地可直接跑；生产建议按需切换 Postgres。

#### 2.1 生产配置要点（建议先读）

- Secrets（例如 `OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET`）必须通过部署环境变量/Secret Manager 注入。
- 管理后台 SystemConfig **禁止保存** API Key/secret（后端会硬拦截）。
- 生产启用 News AI 周期任务时，务必配置可用的 `REDIS_URL`（用于分布式锁，避免多副本重复跑）。

详见：`../docs/PROJECT_REPORT.md`

### 3. 初始化法律知识库

```bash
python scripts/init_knowledge_base.py
```

### 4. 启动服务

```bash
# 开发模式
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或直接运行
python -m app.main
```

### 5. 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 数据库备份 / 恢复 / 演练（运维）

本仓库提供了可直接运行的脚本：

- `scripts/db_backup.py`：备份（SQLite / Postgres）
- `scripts/db_restore.py`：从备份恢复（SQLite / Postgres）
- `scripts/db_drill.py`：灾备演练（当前支持 SQLite）

数据库连接串的来源优先级：

- `--database-url`
- 环境变量 `DATABASE_URL`
- `.env` / 默认配置（默认：`sqlite+aiosqlite:///./data/app.db`）

### 备份

SQLite（默认配置直接执行即可，会在 `backend/backups/` 下生成文件并输出路径）：

```bash
python scripts/db_backup.py
```

备份保留策略（仅对默认 `backend/backups/` 目录生效）：

```bash
# 仅保留最近 14 份（更旧的会被自动清理）
python scripts/db_backup.py --retention-count 14

# 仅保留最近 7 天
python scripts/db_backup.py --retention-days 7
```

Postgres（需要本机安装并可执行 `pg_dump`）：

```bash
python scripts/db_backup.py --database-url "postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB" --verify
```

### 恢复

SQLite（恢复会覆盖目标 DB，必须显式 `--force`）：

```bash
python scripts/db_restore.py ./backups/sqlite_YYYYMMDD_HHMMSS.db --force
```

Postgres（需要本机安装并可执行 `pg_restore`；**请务必指向独立的恢复库/演练库，避免误覆盖生产库**）：

```bash
python scripts/db_restore.py ./backups/postgres_YYYYMMDD_HHMMSS.dump \
  --database-url "postgresql+asyncpg://USER:PASSWORD@HOST:5432/RESTORE_DB" --verify
```

### 灾备演练（Drill）

SQLite：会创建备份，然后恢复到一个单独的 `drill_restore_*.db` 并执行一次 `init_db()` 校验；默认会清理演练恢复库文件。

```bash
python scripts/db_drill.py

# 保留演练恢复库文件（便于人工检查）
python scripts/db_drill.py --keep
```

Postgres：必须显式指定独立的演练库（`--drill-database-url`），脚本会先备份源库，再用 `pg_restore --clean --if-exists` 恢复到演练库，然后执行一次 `init_db()` 校验。

```bash
python scripts/db_drill.py \
  --database-url "postgresql+asyncpg://USER:PASSWORD@HOST:5432/PROD_DB" \
  --drill-database-url "postgresql+asyncpg://USER:PASSWORD@HOST:5432/DRILL_DB" \
  --verify
```

### 定时备份（示例）

Linux cron（每天 03:10 备份一次，并保留最近 14 份）：

```bash
10 3 * * * cd /path/to/backend && /usr/bin/python3 scripts/db_backup.py --retention-count 14 >> backups/cron.log 2>&1
```

Windows 计划任务（示例思路）：

- 通过“任务计划程序”创建任务
- 操作选择启动程序：`python`
- 参数：`scripts\db_backup.py --retention-count 14`
- 起始于：`<你的 backend 目录>`

## API 接口

### AI 咨询

| 方法   | 路径                                        | 说明                       |
| ------ | ------------------------------------------- | -------------------------- |
| POST   | `/api/ai/chat`                              | 发送咨询消息               |
| POST   | `/api/ai/chat/stream`                       | 流式对话（SSE）            |
| GET    | `/api/ai/consultations`                     | 获取咨询列表               |
| GET    | `/api/ai/consultations/{session_id}`        | 获取咨询详情               |
| DELETE | `/api/ai/consultations/{session_id}`        | 删除咨询记录               |
| GET    | `/api/ai/consultations/{session_id}/export` | 导出咨询记录（结构化数据） |
| POST   | `/api/ai/messages/rate`                     | 评价 AI 回复               |

### 请求示例

```bash
# 发送咨询
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "劳动合同未签书面合同，我能获得什么赔偿？"}'
```

### News AI 运维（管理员）

- `GET /api/system/news-ai/status`
  - 查看当前生效 providers（脱敏）、策略、response_format、积压与错误趋势。
- `POST /api/news/admin/{news_id}/ai/rerun`
  - 手动触发单条新闻 AI 重跑。

## 项目结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI入口
│   ├── config.py         # 配置管理
│   ├── database.py       # 数据库连接
│   ├── models/           # ORM模型
│   ├── schemas/          # Pydantic模式
│   ├── routers/          # API路由
│   └── services/         # 业务服务
├── knowledge_base/       # 法律知识库
│   └── laws/            # 法律条文JSON
├── scripts/             # 脚本工具
├── requirements.txt
└── .env
```

## 技术栈

- **Web 框架**: FastAPI
- **ORM**: SQLAlchemy (async)
- **AI**: OpenAI-compatible HTTP API（可选；相关能力可通过 env + SystemConfig 配置）
- **向量数据库**: ChromaDB
- **LLM**: OpenAI / OpenAI-compat 服务

## 相关文档

- `../docs/PROJECT_REPORT.md`：项目报告（面向接手工程师的一站式说明）
