# 百姓法律助手 - 后端服务

基于 FastAPI + LangChain 的 AI 法律咨询服务后端。

## 功能特性

- 🤖 **AI 法律咨询**: 基于法律知识库的智能问答
- 📚 **法律知识库**: 向量化存储，支持语义搜索
- 💬 **多轮对话**: 支持上下文连续对话
- 📝 **咨询记录**: 保存和管理咨询历史

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `env.example` 为 `.env` 并修改配置：

```bash
cp env.example .env
```

**重要配置项：**

- `OPENAI_API_KEY`: OpenAI API 密钥
- `OPENAI_BASE_URL`: API 地址（可使用国内代理）
- `DATABASE_URL`: 数据库连接地址

### 3. 初始化法律知识库

```bash
python scripts/init_knowledge_base.py
```

### 4. 启动服务

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或直接运行
python -m app.main
```

### 5. 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 接口

### AI 咨询

| 方法   | 路径                         | 说明         |
| ------ | ---------------------------- | ------------ |
| POST   | `/api/ai/chat`               | 发送咨询消息 |
| GET    | `/api/ai/consultations`      | 获取咨询列表 |
| GET    | `/api/ai/consultations/{id}` | 获取咨询详情 |
| DELETE | `/api/ai/consultations/{id}` | 删除咨询记录 |

### 请求示例

```bash
# 发送咨询
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "劳动合同未签书面合同，我能获得什么赔偿？"}'
```

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
- **AI 框架**: LangChain
- **向量数据库**: ChromaDB
- **LLM**: OpenAI GPT
