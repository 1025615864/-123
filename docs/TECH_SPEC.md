# 技术规范

## 一、技术栈

### 前端

- **框架**：React 19 + TypeScript
- **构建**：Vite 7
- **路由**：React Router DOM 7
- **状态/数据请求**：React Query 5
- **HTTP 请求**：Axios
- **样式**：TailwindCSS 4
- **Markdown 渲染**：react-markdown + remark-gfm
- **E2E 测试**：Playwright

### 后端

- **框架**：FastAPI
- **运行**：Uvicorn
- **数据库**：SQLite（默认，本地开箱即用）/ PostgreSQL（生产推荐）
- **ORM**：SQLAlchemy 2.x（async）
- **迁移**：Alembic
- **认证**：JWT（python-jose）
- **缓存/锁**：Redis（生产推荐，用于周期任务分布式锁）
- **AI**：OpenAI-compatible HTTP API（`OPENAI_API_KEY` + `OPENAI_BASE_URL`）
- **RAG/向量库**：LangChain + ChromaDB
- **文档处理**：pypdf、docx2txt、reportlab

### 部署

- **本地/演示**：Docker Compose（`docker-compose.yml`）
- **生产示例**：`docker-compose.prod.yml`（含 Redis）
- **K8s**：Helm Chart（`helm/baixing-assistant`）

---

## 二、项目结构

### 仓库根目录

```
.
├── backend/                 # FastAPI 后端
├── frontend/                # React 前端
├── docs/                    # 文档
├── scripts/                 # 冒烟/运维脚本
├── docker-compose.yml
├── docker-compose.prod.yml
└── helm/                    # Helm Chart
```

### 后端结构（backend/app）

```
backend/app/
├── main.py                  # FastAPI 入口；挂载 /api；周期任务
├── config.py                # Pydantic Settings；env 解析与生产校验
├── database.py              # Async SQLAlchemy engine/session；init_db
├── models/                  # SQLAlchemy ORM 模型
├── schemas/                 # Pydantic schema（请求/响应）
├── routers/                 # API 路由（按业务拆分）
├── services/                # 业务服务层
├── middleware/              # 中间件（日志/限流等）
└── utils/                   # 通用工具（鉴权、限流、权限等）
```

### 前端结构（frontend/src）

```
frontend/src/
├── App.tsx                  # 路由表（前台 + /admin）
├── components/              # 组件（含 AdminLayout/Layout 等）
├── pages/                   # 页面
├── contexts/                # Auth/Theme/Language 等
├── hooks/                   # useApi/useToast 等
├── api/                     # axios client
└── tests/e2e/               # Playwright 用例
```

---

## 三、命名规范

| 类型            | 规范                          | 示例                      |
| --------------- | ----------------------------- | ------------------------- |
| React 组件文件  | PascalCase                    | `NewsTopicsPage.tsx`      |
| hooks           | camelCase                     | `useApi.ts`               |
| 后端路由文件    | snake_case / 模块名           | `routers/news.py`         |
| SQLAlchemy 表名 | snake_case（复数）/按模型定义 | `users`、`payment_orders` |
| API 路径        | kebab-case/分层路径           | `/api/news/topics`        |

---

## 四、环境变量

> 后端配置定义见 `backend/app/config.py`；示例见 `backend/env.example`。

```env
# backend/.env 示例（开发）
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# JWT
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# 支付回调密钥（生产 DEBUG=false 必填）
PAYMENT_WEBHOOK_SECRET=your-payment-webhook-secret

# CORS
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000
FRONTEND_BASE_URL=http://localhost:5173
TRUSTED_PROXIES=[]

# Redis（生产推荐）
REDIS_URL=

# AI
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
AI_MODEL=deepseek-chat

# 调试
DEBUG=true
SQL_ECHO=
```

### 配置约束（生产）

- 当 `DEBUG=false`：
  - `JWT_SECRET_KEY/SECRET_KEY` 必须为安全值（且长度足够）
  - `PAYMENT_WEBHOOK_SECRET` 必须配置
  - Redis 不可用时会禁用部分周期任务（避免多副本重复执行）

---

## 五、API 与鉴权约定

- **Base URL**：后端统一挂载在 `/api`（见 `backend/app/main.py`）。
- **认证方式**：JWT Bearer。

请求头示例：

```http
Authorization: Bearer <token>
```

- **游客与限流**：
  - AI/文书生成等接口对游客按 IP 做限制（并返回 429）。

---

## 六、开发与质量门禁

### 本地启动

- 后端（建议在 `backend/` 目录执行）：
  - `python -m uvicorn app.main:app --reload --port 8000`
- 前端：
  - `npm install`
  - `npm run dev`

### 测试

- 后端：
  - 安装（含测试依赖）：`py -m pip install -r backend/requirements-dev.txt`
  - 运行：`py -m pytest -q`
- 前端：
  - 安装：`npm --prefix frontend ci`
  - 构建：`npm --prefix frontend run build`
- E2E（Playwright，最小文书闭环）：
  - 安装浏览器：`npm --prefix frontend run test:e2e:install`
  - 运行（仅文书用例）：`npm --prefix frontend run test:e2e -- --grep "documents:"`
- CI：GitHub Actions workflow：`.github/workflows/ci.yml`

---

## 七、重要工程约束（必须遵守）

- **Secrets 不入库**：`OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET` 等必须通过环境变量/Secret Manager 注入；系统配置（SystemConfig）禁止写入敏感信息（后端会返回 400）。
- **生产周期任务**：生产多副本部署时建议配置 Redis，用于分布式锁，避免任务重复跑。
