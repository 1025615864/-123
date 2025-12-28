# 开发指南（Dev Guide）

> 目标：帮助你从零开始在本仓库把 **backend + frontend** 跑起来，并覆盖常见的 Windows/中文路径坑、基础联调与测试。

---

## 0. 前置要求

- Python：3.10+
- Node.js：18+
- npm：9+
- Docker（可选，用于一键拉起 PostgreSQL/Redis 等依赖）

---

## 1. 仓库结构与入口

- 后端：`backend/`
  - 入口：`backend/app/main.py`
  - 路由汇总：`backend/app/routers/__init__.py`（在 `main.py` 中以 `/api` 前缀挂载）
  - 配置：`backend/app/config.py`
  - 环境变量示例：`backend/env.example`
- 前端：`frontend/`
  - Vite dev server：默认 `http://localhost:5173`
  - API 代理：默认 `/api -> http://localhost:8000`

---

## 2. 后端（本地开发）

### 2.1 环境变量

在 `backend/` 下复制示例：

- 复制 `backend/env.example` -> `backend/.env`

> 注意：Secrets（例如 `OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET`）必须通过 env/Secret Manager 注入，**禁止**写入管理后台 SystemConfig（会返回 400）。

### 2.2 创建虚拟环境与安装依赖

在仓库根目录打开终端，执行：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

#### Windows 常见坑：WindowsApps stub / pip launcher

在某些 Windows 环境里：

- `where python` 指向 `WindowsApps\python.exe`（stub），可能导致执行“看似成功但实际没运行”。
- `.venv\Scripts\pip.exe` / `.venv\Scripts\uvicorn.exe` 在中文路径下可能触发 launcher 报错。

可用替代方式：

```powershell
# 用 py 选择真实 Python
py -m pip install -r requirements.txt

# 用 python -m 方式启动（避免 uvicorn.exe launcher）
py -m uvicorn app.main:app --reload --port 8000
```

### 2.3 启动后端

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

启动后验证：

- `GET http://localhost:8000/health`
- Swagger：`http://localhost:8000/docs`

---

## 3. 前端（本地开发）

### 3.1 配置

在 `frontend/` 下创建 `.env`（如果你使用默认 Vite 代理，最小配置通常即可）：

```env
VITE_API_BASE_URL=/api
```

### 3.2 安装依赖与启动

```bash
cd frontend
npm install
npm run dev
```

访问：`http://localhost:5173`

---

## 4. 一键启动（Docker Compose，可选）

### 4.1 开发 compose

```bash
docker compose up -d --build
```

### 4.2 生产示例 compose

> `docker-compose.prod.yml` 依赖仓库根目录的 `.env`。

- 复制 `env.example.txt` -> `.env`

然后：

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 5. 快速联调（建议路径）

### 5.1 登录与 JWT 结构

- 登录：`POST /api/user/login`
- 响应结构中 JWT 位于：`token.access_token`（不是顶层 `access_token`）

### 5.2 News AI 冒烟（管理员手动 rerun）

仓库提供了冒烟脚本：

- Windows：`scripts/smoke-news-ai.ps1`
- Linux/CI：`scripts/smoke-news-ai.sh`

详细说明：`scripts/README.md` 与 `docs/PROD_DEPLOY_AND_SMOKE_SOP.md`

---

## 6. 测试与质量门禁

### 6.1 后端（pytest）

```powershell
cd backend
py -m pytest -q
```

### 6.2 后端类型检查（Pyright）

```powershell
cd backend
py -m pyright
```

### 6.3 前端构建

```bash
cd frontend
npm run build
```

### 6.4 前端 E2E（Playwright）

```bash
cd frontend
npm run test:e2e
```

> Playwright 默认会启动隔离端口的后端/前端 dev server（见 `frontend/README.md` 的 E2E 环境变量说明）。

---

## 7. 常见问题（FAQ）

### 7.1 News AI pipeline 不自动跑

- `NEWS_AI_ENABLED=true` 才会启用周期任务。
- 当 `DEBUG=false` 且 Redis 未连接时，定时任务会被禁用（生产必须配置 `REDIS_URL`）。

### 7.2 SystemConfig 写入被 400 拒绝

通常是触发了 secrets 拦截：

- key 名包含 `secret/password/api_key/apikey/private_key` 且 value 非空
- 或 providers JSON/B64 内包含 `api_key/apikey`

正确做法：把 key 放到 `OPENAI_API_KEY`（env/Secret），providers JSON 不写 `api_key`。
