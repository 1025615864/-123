# DB 恢复演练报告（Drill Restore Report）

日期：2026-01-13

## 1. 目的

通过 drill 方式验证：

- 备份链路可用
- 恢复链路可用
- 恢复后的库能成功执行 `init_db()`（验证 schema/bootstrap）

> 约束：演练必须在独立 drill DB 上进行，禁止对主库执行“清库式恢复”。

---

## 2. 本次演练环境

- OS：Windows
- 演练数据库类型：SQLite（本地默认）
- 执行目录：`backend/`

## 3. 执行记录

### 3.1 直接使用 drill 脚本（推荐）

命令：

```powershell
cd backend
py scripts/db_drill.py
```

输出（脚本打印的备份文件路径）：

- `backend/backups/drill_sqlite_20260113_015703.db`

说明：

- `db_drill.py` 会自动：
  - 备份当前 DB（SQLite/PG 自动识别）
  - 恢复到一个临时 drill sqlite 文件（默认位于 `backend/backups/`，文件名 `drill_restore_*.db`）
  - 对 drill DB 执行：`asyncio.run(init_db())`
  - 若未传 `--keep`，会在成功后删除临时 drill restore 文件（避免误用）

### 3.2 单独执行一次备份（用于“保留策略/回归对照”验证）

命令：

```powershell
cd backend
py scripts/db_backup.py --output backups/drill_last_backup.db
```

输出：

- `backend/backups/drill_last_backup.db`

---

## 4. 结论

- 结果：**drill restore 成功**（脚本正常退出并打印备份文件路径）。
- 建议：生产环境至少做到：
  - 按固定周期执行备份
  - 至少每月执行一次 drill restore（在独立 drill DB/环境）
  - drill 通过后再进入迁移发布/大版本升级

---

## 5. 复现/扩展

### 5.1 SQLite drill 保留恢复文件（便于人工核查）

```powershell
cd backend
py scripts/db_drill.py --keep
```

### 5.2 PostgreSQL drill（必须提供独立 drill DB）

```powershell
cd backend
set DATABASE_URL=postgresql+asyncpg://prod_user:prod_pass@prod_host:5432/prod_db
py scripts/db_drill.py --drill-database-url postgresql+asyncpg://drill_user:drill_pass@drill_host:5432/drill_db --verify
```
