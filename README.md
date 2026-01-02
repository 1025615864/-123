# 百姓法律助手

一站式法律服务平台（前后端全栈），面向 **法律咨询 + 内容资讯 + 社区互动 + 律所服务** 场景，内置 **AI 法律咨询（RAG）** 与 **News AI 内容加工** 能力，支持 Docker/Helm 快速部署。

## 核心亮点

- **AI 法律咨询（可流式）**

  - 支持对话咨询、流式输出（SSE）、会话历史、导出与评价。
  - 可结合知识库向量化（ChromaDB）实现检索增强（RAG）。

- **新闻模块 + News AI 自动加工**

  - 新闻列表/详情/订阅/收藏/评论。
  - News AI 支持摘要/要点/关键词/风险等级等标注，并提供运维状态与错误追踪。
  - 管理端支持版本历史与回滚、AI 工作台生成、链接检查等能力。

- **论坛与内容治理**

  - 发帖/评论/点赞/收藏/表情反应。
  - 管理端支持敏感词、内容过滤规则、帖子/评论审核与批量审核。

- **支付与订单**

  - 下单/支付/退款/订单管理。
  - Webhook 回调验签（生产建议通过 Secret 注入）。

- **通知系统 + WebSocket 在线能力**

  - 通知列表、未读计数、批量已读/删除。
  - WebSocket 在线状态与实时推送基础能力。

- **可运维、可交付**
  - 生产部署与一键冒烟 SOP。
  - Helm Chart（K8s + Ingress，默认 `/api` -> backend）。
  - CI 校验（backend test / frontend build / helm validate 等）。

## 适用场景

- **法律服务平台原型**：法律咨询 + 律所/律师查询 + 预约咨询 + 支付闭环。
- **内容平台**：新闻采集/运营/审核 + AI 摘要加工 + 专题聚合。
- **社区/论坛**：内容过滤 + 审核工作流 + 通知深链。

## 项目截图 / Demo（占位）

你可以在此处补充：

- 前台：AI 咨询、新闻列表/详情、论坛、律所/律师列表。
- 管理后台：News AI 运维状态、新闻编辑/版本回滚、审核工作台。

## 一分钟体验（本地）

如果你只想快速跑起来看看效果，推荐直接用 Docker：

```bash
docker compose up -d --build
```

启动后访问：

- 前端（Docker）：`http://localhost:3000`
- 后端 API：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`

---

## Release

- Tag：`news-module-20251229`
- GitHub Release：https://github.com/1025615864/-123/releases/tag/news-module-20251229

## 文档入口（建议先看）

- `docs/PROJECT_REPORT.md`：项目报告（面向接手工程师的一站式说明；开发/部署/运维/架构/API/FAQ 已收敛到此）
- `docs/_archive/`：历史文档归档（仅供追溯，不作为入口维护）
- `helm/baixing-assistant/README.md`：Helm Chart 部署说明（K8s + Ingress）

## 快速启动

### 本地开发

后端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# 推荐先复制一份本地配置（默认 SQLite，可直接跑）：
# cp env.example .env
# 如需查看 SQL（排障用）：设置 SQL_ECHO=1
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

- 生产配置要点 + 冒烟流程（News AI）：见 `docs/PROJECT_REPORT.md`
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
