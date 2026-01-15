# 开发指南（DEV_GUIDE）

## 1. 推荐开发方式（Windows）

仓库根目录提供：

- `start-dev.ps1`（推荐）
- `start-dev.cmd`（调用 ps1）

执行：

- `./start-dev.ps1`

它会：

- 创建 `backend/.venv` 并安装 `backend/requirements.txt`
- 安装前端依赖（若 `frontend/node_modules` 不存在）
- 启动后端 `uvicorn`（reload）与前端 `vite dev`

默认端口：

- 后端：`127.0.0.1:8000`
- 前端：`127.0.0.1:5173`

前端代理：

- `/api` -> 后端
- `/ws` -> 后端 WebSocket
- `/sitemap.xml`、`/robots.txt` -> 后端

## 2. 环境变量与配置

### 2.1 env 文件加载规则（后端）

后端会按顺序尝试读取 env 文件：

- `ENV_FILE`（若显式设置）
- `backend/.env`
- 仓库根 `.env`

参考：

- `backend/env.example`
- `env.example.txt`

### 2.2 生产模式强约束

当 `DEBUG=false` 时：

- 必须设置 `JWT_SECRET_KEY`/`SECRET_KEY`（>=32 且不是默认值）
- 必须设置 `PAYMENT_WEBHOOK_SECRET`（>=16）
- 必须设置 `REDIS_URL` 且 Redis 可连接

否则后端会直接报错拒绝启动。

## 3. 数据库与迁移

- 默认 SQLite：`sqlite+aiosqlite:///./data/app.db`
- 生产建议 PostgreSQL：`postgresql+asyncpg://...`

迁移：

- `python backend/scripts/alembic_cmd.py upgrade head`

详见：`docs/DATABASE.md`。

## 4. 常用脚本

- 初始化/演示数据：`python backend/scripts/seed_data.py`
- 初始化知识库：`python backend/scripts/init_knowledge_base.py`
- mock OpenAI：`python backend/scripts/mock_openai_server.py`

### 4.1 演示账号与登录

`seed_data.py` 会创建/更新演示账号（可重复执行），常用于本地联调：

- `admin`（管理员）
- `lawyer1`（律师）
- `user1`（普通用户）

拿 token 的方式：

- `POST /api/user/login`（username/password）

## 5. 开发者文档入口（推荐）

- 模块文档索引：`docs/modules/INDEX.md`
- 配置参考（env + SystemConfig）：`docs/guides/CONFIG_REFERENCE.md`
- 数据模型概览：`docs/DATA_MODEL.md`
- 排障手册：`docs/guides/TROUBLESHOOTING.md`

## 6. 鉴权、权限与常见限制

### 6.1 角色与依赖

- `get_current_user`：需要 `Authorization: Bearer <jwt>`
- `require_admin`：`role in {admin, super_admin}`
- `require_lawyer_verified`：律师 + 手机/邮箱验证

实现位置：`backend/app/utils/deps.py`

### 6.2 限流 vs 配额（容易混淆）

项目存在两套“429”来源：

- 全局 IP 限流中间件：`backend/app/middleware/rate_limit.py`
  - 文案多为“每秒请求过多/请求过于频繁”
- 业务配额（Quota）：`backend/app/services/quota_service.py`
  - 文案多为“今日 AI 咨询次数已用尽/今日文书生成次数已用尽”

### 6.3 SystemConfig 不允许存 secrets

SystemConfig API（管理员）：`/api/system/configs*`

规则：

- key 名含 `secret/password/api_key/private_key` 等会被拒绝写入（HTTP 400）
- News AI providers 配置是例外 key，但 providers 内容里同样禁止包含 `api_key` 字段

详见：`docs/modules/SYSTEM_CONFIG.md`。

## 7. 测试

### 7.1 后端

- `pytest backend/tests/ -v --tb=short`

CI 中会：

- 启动 Postgres service
- 执行 `python backend/scripts/alembic_cmd.py upgrade head`
- 运行 `pytest`

### 7.2 前端

- 构建：`npm --prefix frontend run build`

### 7.3 E2E（Playwright）

- 安装浏览器：`npm --prefix frontend run test:e2e:install`
- 运行：`npm --prefix frontend run test:e2e`

## 8. 代码质量

仓库提供 `pre-commit` 配置：`.pre-commit-config.yaml`

建议：

- `pre-commit install`

包含：

- basic hooks（末尾空格、YAML 校验等）
- `ruff` + `ruff-format`
- `pyright`（指向 `backend/pyrightconfig.json`）
