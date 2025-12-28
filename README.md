# 百姓法律助手

一站式法律服务平台，提供 AI 法律咨询、论坛交流、新闻资讯、律所查询等功能。

## Release

- Tag：`news-module-20251229`
- GitHub Release：https://github.com/1025615864/-123/releases/tag/news-module-20251229

## 文档入口（建议先看）

- `docs/HANDOFF.md`：项目交接（架构/配置/关键入口/排障）
- `docs/PROD_DEPLOY_AND_SMOKE_SOP.md`：生产部署参数清单 + 冒烟 SOP
- `docs/API_QUICK_REFERENCE.md`：News/News AI/SystemConfig 常用 API 速查
- `docs/UPDATE_LOG.md`：更新记录（变更点与测试结果）
- `helm/baixing-assistant/README.md`：Helm Chart 部署说明（K8s + Ingress）

## 快速启动

### 本地开发

后端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# Windows 上如果 `pip`/`python` 指向 WindowsApps 的 stub，可改用：
# py -m pip install -r requirements.txt
# Windows 上如果 `python` 指向 WindowsApps 的 stub，可改用：
# py -m uvicorn app.main:app --reload --port 8000
python -m uvicorn app.main:app --reload --port 8000
```

前端（新终端）：

```bash
cd frontend
npm install
npm run dev
```

### Docker（可选）

```bash
docker compose up -d --build
```

生产（可选，使用独立 compose 文件）：

> `docker-compose.prod.yml` 依赖仓库根目录的 `.env` 环境变量；建议从 `env.example.txt` 复制一份到 `.env` 再执行。

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## 环境要求

- **Python**: 3.10+
- **Node.js**: 18+
- **npm**: 9+

## 项目结构

```
百姓助手/
├── backend/              # 后端 (FastAPI)
│   ├── app/
│   │   ├── models/       # 数据模型
│   │   ├── routers/      # API路由
│   │   ├── services/     # 业务逻辑
│   │   ├── schemas/      # Pydantic模型
│   │   ├── utils/        # 工具函数
│   │   └── main.py       # 应用入口
│   └── requirements.txt  # Python依赖
├── frontend/             # 前端 (React + TypeScript)
│   ├── src/
│   │   ├── components/   # 组件
│   │   ├── contexts/     # 上下文
│   │   ├── hooks/        # 自定义Hook
│   │   ├── i18n/         # 国际化
│   │   ├── pages/        # 页面
│   │   └── services/     # API服务
│   └── package.json      # Node依赖
└── README.md             # 本文件
```

## 服务地址

启动后访问：

| 服务             | 地址                        |
| ---------------- | --------------------------- |
| 前端（本地开发） | http://localhost:5173       |
| 前端（Docker）   | http://localhost:3000       |
| 后端 API         | http://localhost:8000       |
| API 文档         | http://localhost:8000/docs  |
| ReDoc            | http://localhost:8000/redoc |

## 功能模块

### 核心功能

- **AI 法律咨询** - 智能问答，快速获取法律建议
- **法律论坛** - 发帖讨论，互动交流
- **法律资讯** - 最新法律新闻动态
- **律所查询** - 律师、律所信息检索
- **知识库** - 法律知识百科

### 管理功能

- **数据统计大屏** - 可视化数据统计仪表板
- **用户行为分析** - 页面访问、功能使用统计
- **评论审核** - 敏感词过滤、人工审核
- **支付管理** - 订单管理、退款处理

### 系统特性

- **多语言支持** - 中文/英文切换
- **暗黑模式** - 亮色/暗黑/跟随系统
- **移动端适配** - 响应式设计
- **API 限流** - 精细化限流保护

## 配置与部署

### 本地开发配置

- 后端：在 `backend/` 下复制 `env.example` 为 `.env` 并按需修改。
- 前端：在 `frontend/` 下创建 `.env`，最小配置通常为 `VITE_API_BASE_URL=/api`。

### 生产配置与运维

- 生产部署参数清单 + 一键冒烟 SOP：`docs/PROD_DEPLOY_AND_SMOKE_SOP.md`
- Helm（Kubernetes）部署：`helm/baixing-assistant/README.md`
- Docker Compose 生产示例：`docker-compose.prod.yml` + 仓库根目录 `env.example.txt`

**重要**：Secrets（例如 `OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET` 等）必须通过环境变量/Secret Manager 注入，禁止写入管理后台 SystemConfig（后端会返回 400）。

## 技术栈

### 后端

- **FastAPI** - 高性能 Web 框架
- **SQLAlchemy** - ORM 数据库操作
- **Pydantic** - 数据验证
- **JWT** - 身份认证
- **SQLite/PostgreSQL** - 数据库

### 前端

- **React 19** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **TailwindCSS** - 样式框架
- **Lucide** - 图标库

## License

MIT License
