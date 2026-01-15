# 数据库与迁移

## 1. 连接串（DATABASE_URL）

后端使用 SQLAlchemy 2.x async。

- 环境变量：`DATABASE_URL`
- Settings 别名：`DATABASE_URL` / `DB_URL` / `SQLALCHEMY_DATABASE_URL`

默认值（本地）：

- `sqlite+aiosqlite:///./data/app.db`

生产建议：

- PostgreSQL（示例）`postgresql+asyncpg://user:pass@host:5432/baixing_law`

## 2. 本地开发 vs 生产模式

### 2.1 DEBUG=true（开发模式）

当 `DEBUG=true`（或测试环境）时：

- 允许 `init_db()` 在启动时执行 `create_all`
- SQLite 模式下会进行“轻量自修复”（为缺失列/索引补 DDL）

适用场景：

- 本地快速跑起来
- E2E/联调

### 2.2 DEBUG=false（生产模式）

当 `DEBUG=false` 时：

- **必须提供 Redis**（`REDIS_URL` 且可连接，否则后端直接拒绝启动）
- **必须提供安全的 JWT Secret**（`JWT_SECRET_KEY`/`SECRET_KEY` 长度 >= 32 且不能使用默认值）
- **必须提供支付回调密钥**（`PAYMENT_WEBHOOK_SECRET` 长度 >= 16）
- **数据库必须在 Alembic head**（否则启动失败）

## 3. Alembic 迁移

仓库内提供命令包装：

- `backend/scripts/alembic_cmd.py`

示例：

- 升级到 head：`python backend/scripts/alembic_cmd.py upgrade head`
- 标记当前库为 head（谨慎使用）：`python backend/scripts/alembic_cmd.py stamp head`

注意：

- 当 `DEBUG=false` 且没有设置 `DB_ALLOW_RUNTIME_DDL=1` 时，后端会在启动阶段检查 `alembic heads` 与数据库当前 revision 是否一致。

## 4. DB_ALLOW_RUNTIME_DDL（临时绕过）

- 环境变量：`DB_ALLOW_RUNTIME_DDL=1`

作用：

- 临时允许 `init_db()` 执行运行时 DDL（包括 `create_all` 与部分自修复）

仅建议用于：

- 临时排障/开发环境

不建议用于：

- 生产环境（会掩盖迁移缺失、造成 schema 漂移）

## 5. 常用运维/数据脚本

位于：`backend/scripts/`

- `seed_data.py`：写入本地演示数据（含 admin/lawyer/user 等账号）
- `db_backup.py` / `db_restore.py`：数据库备份/恢复
- `db_drill.py`：数据库演练
- `cleanup_news_ai_data.py`：清理 News AI 数据
- `cleanup_e2e_data.py`：清理 E2E 数据

## 6. 数据目录与忽略规则

- SQLite 默认写入：`backend/data/app.db`（目录会自动创建）
- `.gitignore` 默认忽略：
  - `backend/data/`
  - `*.db` / `*.sqlite*`

因此：

- 本地数据库文件不会被提交到仓库。
