# 百姓法律助手

一站式法律服务平台，提供 AI 法律咨询、论坛交流、新闻资讯、律所查询等功能。

## 快速启动

### 本地开发

后端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
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
docker-compose up -d --build
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

## 环境配置

### 后端配置

在 `backend/` 目录下创建 `.env` 文件（运行后端服务时会读取该文件）：

```env
# 应用配置
APP_NAME=百姓法律助手
DEBUG=true

# 数据库 (SQLite默认)
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# JWT密钥
JWT_SECRET_KEY=your-secret-key-here

# AI配置 (可选)
OPENAI_API_KEY=your-openai-key
OPENAI_BASE_URL=https://api.openai.com/v1
```

### 前端配置

创建 `frontend/.env` 文件：

```env
VITE_API_BASE_URL=/api
```

## 手动启动

### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python -m uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 生产部署

### 后端

```bash
# 使用gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 前端

```bash
# 构建生产版本
npm run build

# 使用nginx托管dist目录
```

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
