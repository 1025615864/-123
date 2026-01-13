# 生产部署演练记录（Deploy Drill）

日期：2026-01-13

## 0. 目标

以“可复现、可追溯”的方式走通一次发布链路：

- 备份（Backup）
- 迁移（`alembic upgrade head`）
- 滚动发布（Compose 或 Helm）
- 发布后冒烟（Smoke）

并将：命令、输出、截图/日志、结论归档。

---

## 1. 本次演练选择的口径

- 首选：`docker-compose.prod.yml`（本地模拟生产：PG + Redis + backend + frontend）

原因：

- 演练成本低，可在单机快速复现
- 能覆盖生产关键门禁：`DEBUG=false` + Redis 强依赖 + DB head 门禁

---

## 2. 前置检查（本次阻塞点，已解决）

### 2.1 Docker Engine 状态

- 本次演练开始时：Docker CLI 可用，但 Docker Engine/daemon 未启动，`docker version` 报 `docker_engine` pipe 不存在。
- 本次演练中：已恢复 Docker Engine（`docker.exe`/`docker compose` 可正常工作）。

验证命令：

```powershell
docker version
docker compose version
```

---

## 3. 演练步骤

### 3.1 准备生产 .env（不要提交到仓库）

参考：`env.example.txt`。

建议：创建 `.env.prod`（不要提交到仓库），并在所有 compose 命令中显式指定 `--env-file .env.prod`。

至少需要：

- `POSTGRES_PASSWORD`
- `JWT_SECRET_KEY`
- `PAYMENT_WEBHOOK_SECRET`
- `REDIS_PASSWORD`
- `CORS_ALLOW_ORIGINS`

可选：

- `OPENAI_API_KEY`

建议的 `.env.prod` 示例（仅示例，务必替换为真实安全值）：

```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change_me
POSTGRES_DB=baixing_law

JWT_SECRET_KEY=change_me_long_random
PAYMENT_WEBHOOK_SECRET=change_me_long_random

REDIS_PASSWORD=change_me
CORS_ALLOW_ORIGINS=["http://localhost"]

VITE_API_BASE_URL=/api

OPENAI_API_KEY=
```

关键门禁说明：

- `docker-compose.prod.yml` 中 `backend` 会以 `DEBUG=false` 启动。
- 后端在 `DEBUG=false` 时 **必须**连通 Redis（否则启动阶段直接抛错退出）。本 compose 已内置 `REDIS_URL=redis://:...@redis:6379/0`，因此只要 redis 服务健康即可。

### 3.2 启动生产 compose

```powershell
docker compose -p baixing_prod -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

说明：在部分 PowerShell 环境里可能存在 `docker` 的别名/函数干扰，建议在 Windows 下明确使用 `docker.exe`：

```powershell
docker.exe compose -p baixing_prod -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

注意：本仓库目录名包含中文字符时，`docker compose` 的默认 project name 可能被归一化为空，导致报错：`project name must not be empty`。

- 解决：如上命令显式指定 `-p baixing_prod`（或等价地设置 `COMPOSE_PROJECT_NAME=baixing_prod`）。

注意：`docker-compose.prod.yml` 默认将前端映射到宿主机 `80` 端口（`80:3000`）。

- 如果宿主机 `80` 端口被占用，请先释放占用或临时改成 `8080:3000` 再演练。

建议额外检查：

```powershell
docker compose -p baixing_prod -f docker-compose.prod.yml --env-file .env.prod ps
```

### 3.3 DB 备份（生产必做）

`docker-compose.prod.yml` 口径是 Postgres。

推荐备份方式（避免 Windows / PowerShell 对二进制重定向的坑）：在 Postgres 容器内生成二进制 dump，然后 `docker cp` 拷到宿主机归档。

```powershell
# 1) 在 db 容器内生成二进制 dump
docker exec baixing_db_prod sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump --no-owner --no-privileges -Fc -U "$POSTGRES_USER" -f /tmp/baixing.dump "$POSTGRES_DB"'

# 2) 拷贝到宿主机（仓库内归档目录）
mkdir backend\backups -Force | Out-Null
docker cp baixing_db_prod:/tmp/baixing.dump backend/backups/postgres_deploy_drill_<YYYYMMDD_HHMMSS>.dump

# 3) 清理容器内临时文件
docker exec baixing_db_prod sh -lc "rm -f /tmp/baixing.dump"
```

可选：如果你已在宿主机安装 `pg_dump`（Postgres client），也可用脚本（会要求 `pg_dump` 在 PATH 中）：

```powershell
py backend\scripts\db_backup.py --verify
```

预期：

- 输出备份文件到 `backend/backups/postgres_*.dump`

### 3.4 DB 迁移（upgrade head）

推荐：在 backend 容器内执行（使用同一套环境变量与依赖），执行完后重启 backend。

```powershell
docker exec baixing_backend_prod python scripts/alembic_cmd.py upgrade head
```

预期：

- Alembic 输出 `Running upgrade ...`
- 无报错退出

### 3.5 滚动发布（本地用 restart 模拟）

```powershell
docker compose -p baixing_prod -f docker-compose.prod.yml --env-file .env.prod restart backend
```

### 3.6 发布后冒烟（Smoke）

- Health：

```powershell
curl http://localhost/api/health
```

说明：

- `frontend/nginx.conf` 仅代理 `/api` 到后端，因此从 `http://localhost/` 访问健康检查应使用 `/api/health`。
- 后端也提供 `/health`，但在本 prod compose 中 backend 不对外暴露端口，默认只能经由前端网关访问。

- 关键页面：

  - `http://localhost/`
  - `http://localhost/admin`

- 可选：News AI 冒烟（如果你开启并具备管理员 token）：
  - 参考 `scripts/smoke-news-ai.ps1` 与 `docs/_archive/PROD_DEPLOY_AND_SMOKE_SOP.md`

---

## 4. 预期产出（演练完成后补齐）

- 命令清单（含输出摘要）
- 服务健康检查结果
- 迁移结果与 Alembic 版本验证
- Postgres dump 备份文件（含文件名与存放位置）
- 关键页面截图（可选）
- 结论：是否可复现成功，失败点与修复建议

---

## 4.1 回滚与清理（演练建议项）

```powershell
# 仅重启 backend（快速回滚到“重启前镜像/配置”的情形）
docker compose -p baixing_prod -f docker-compose.prod.yml --env-file .env.prod restart backend

# 完整停止（保留数据卷）
docker compose -p baixing_prod -f docker-compose.prod.yml --env-file .env.prod down

# 完整停止并删除数据卷（仅演练环境/可接受清空数据时）
docker compose -p baixing_prod -f docker-compose.prod.yml --env-file .env.prod down -v
```

---

## 5. 下一步

本次演练已完成，实际输出摘要见下。

---

## 6. 本次演练实际执行记录（摘要）

### 6.1 Compose 启动与服务状态

```powershell
docker.exe compose -p baixing_prod -f docker-compose.prod.yml --env-file .env.prod ps
```

关键结果（节选）：

- `baixing_db_prod`：`healthy`
- `baixing_redis_prod`：`healthy`
- `baixing_backend_prod`：`Up`
- `baixing_frontend_prod`：`0.0.0.0:80->3000/tcp`

### 6.2 发布后冒烟（Health）

```powershell
curl http://localhost/api/health
```

结果：`200 OK`（返回 `{"status":"healthy"}`）。

### 6.3 DB 迁移（Alembic upgrade head）

说明：backend 启动阶段会校验“schema 在 alembic head”，未迁移会导致 upstream 不可用从而前端网关返回 `502`。

```powershell
docker exec baixing_backend_prod python scripts/alembic_cmd.py upgrade head
docker exec baixing_backend_prod python scripts/alembic_cmd.py current
docker exec baixing_backend_prod python scripts/alembic_cmd.py heads
```

结果（节选）：

- `current`：`d4f2c9a31b10 (head)`
- `heads`：`d4f2c9a31b10 (head)`

### 6.4 DB 备份（pg_dump + docker cp）

```powershell
docker exec baixing_db_prod sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump --no-owner --no-privileges -Fc -U "$POSTGRES_USER" -f /tmp/baixing.dump "$POSTGRES_DB"'
docker cp baixing_db_prod:/tmp/baixing.dump backend/backups/postgres_deploy_drill_20260113_042822.dump
docker exec baixing_db_prod sh -lc 'rm -f /tmp/baixing.dump'
```

产物：

- `backend/backups/postgres_deploy_drill_20260113_042822.dump`（`208280` bytes）

### 6.5 本次踩坑与修复

- `docker compose`：中文路径下默认 project name 可能为空，报 `project name must not be empty`。
  - 解决：显式 `-p baixing_prod`。
- `/api/health` 返回 `502`：backend 实际未成功启动（upstream 端口拒绝连接）。
  - 原因 A：`CORS_ALLOW_ORIGINS` 是 list 类型，env 值需为 JSON array；否则 Pydantic settings 解析失败。
    - 解决：`.env.prod` 使用 `CORS_ALLOW_ORIGINS=["http://localhost"]`；同时修正 compose/env example 默认值。
  - 原因 B：DB schema 不在 alembic head，backend 启动阶段硬校验失败。
    - 解决：容器内执行 `alembic upgrade head` 后重启 backend。
- 镜像构建网络不稳定：`apt-get`/`pip install` 有超时/失败风险。
  - 解决：`backend/Dockerfile` 增加 apt 镜像替换、重试/超时；pip 增加重试/超时与镜像源；并补充 `backend/.dockerignore`、`frontend/.dockerignore` 降低 build context。
