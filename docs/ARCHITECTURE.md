# 架构说明（Architecture）

> 目标：从“整体架构 + 数据流 + 关键模块职责”的视角说明本项目，便于接手、排障与扩展。

---

## 1. 总体架构

- **前端**：React + TypeScript + Vite

  - 开发端口：`http://localhost:5173`
  - Docker/Nginx：`http://localhost:3000`
  - 默认通过 `/api` 访问后端（Vite proxy / Ingress / Nginx 转发）

- **后端**：FastAPI

  - 默认端口：`http://localhost:8000`
  - Swagger：`/docs`，ReDoc：`/redoc`
  - API 前缀：`/api`

- **存储**：

  - SQLite（本地默认）/ PostgreSQL（生产推荐）
  - ChromaDB（向量库，RAG 用；默认持久化目录 `./chroma_db`）

- **中间件/依赖**：

  - Redis（生产推荐；`DEBUG=false` 时用于周期任务/分布式锁）

- **AI**：
  - **AI 法律咨询（RAG）**：LangChain + ChromaDB + OpenAI-compatible LLM
  - **News AI**：新闻摘要/要点/关键词/风险等级（pipeline + 管理员手动 rerun）

---

## 2. 关键入口与路由结构

### 2.1 后端入口

- 应用入口：`backend/app/main.py`

  - 挂载 API：`app.include_router(api_router, prefix="/api")`
  - WebSocket：`app.include_router(websocket.router)`（不在 `/api` 前缀下）

- API 聚合：`backend/app/routers/__init__.py`
  - 统一 `api_router.include_router(x.router)`
  - AI 路由为可选模块：`ai` import 失败时不会注册 `/api/ai/*`

### 2.2 主要路由（prefix）

- `/user`：用户注册/登录/密码重置/管理员用户管理
- `/ai`：AI 法律咨询（可选模块）
- `/news`：新闻/专题/订阅/收藏/评论；以及 News AI 管理端接口
- `/forum`：论坛帖子/评论/互动；以及管理员审核与内容风控配置
- `/knowledge`：知识库条目/模板/分类；向量化与向量库同步
- `/lawfirm`：律所/律师/预约咨询/评价；律师认证与管理员审核
- `/payment`：订单/支付/余额/回调；管理员退款与统计
- `/documents`：文书模板生成
- `/upload`：头像/图片/附件上传与访问
- `/notifications`：通知列表/已读/批量操作；管理员广播
- `/search`：全局搜索/建议/热词/历史
- `/system`：SystemConfig/日志/看板/行为分析/News AI 运维状态
- `/admin`：统计与数据导出（CSV）

---

## 3. 安全与配置原则（必须遵守）

### 3.1 Secrets 不入库

- `OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET`、Redis 密码等必须通过环境变量/Secret Manager 注入。
- **禁止**在 SystemConfig 中写入任何 API Key/secret（后端会返回 400）。

相关实现位置：`backend/app/routers/system.py`。

### 3.2 生产与 Redis

- 当 `DEBUG=false` 且 Redis 未连接时：周期任务（定时新闻、RSS ingest、News AI pipeline）会被禁用。
- 因此生产建议配置可用 `REDIS_URL`。

---

## 4. 业务模块与数据流

### 4.1 用户与权限

- 登录：`POST /api/user/login`
  - JWT 位于 `token.access_token`
- 权限形态：
  - 未登录
  - 登录用户（普通用户/律师等）
  - 管理员（admin）

### 4.2 AI 法律咨询（RAG）

- 路由：`/api/ai/*`
  - `POST /api/ai/chat`（同步）
  - `POST /api/ai/chat/stream`（SSE 流式）
  - 历史/导出/评价等
- 依赖：
  - `OPENAI_API_KEY`（必需）
  - 向量库：ChromaDB（知识库向量化后供检索）

数据流（简化）：

1. 用户发起 `chat` 请求
2. 服务从 ChromaDB 检索相关知识片段（RAG）
3. 调用 OpenAI-compatible LLM 生成回答
4. 将会话与消息持久化到 DB（便于历史查询/导出/评价）

### 4.3 知识库与向量化

- 知识库条目：`/api/knowledge/laws*`
- 分类：`/api/knowledge/categories*`
- 模板：`/api/knowledge/templates*`
- 向量化：
  - 单条：`POST /api/knowledge/laws/{knowledge_id}/vectorize`
  - 批量：`POST /api/knowledge/laws/batch-vectorize`
  - 同步所有未向量化：`POST /api/knowledge/sync-vector-store`

### 4.4 新闻与 News AI

- 新闻对外消费：`GET /api/news`、`GET /api/news/{news_id}`
- 运营管理：管理员创建/编辑/审核、专题管理、RSS 采集
- News AI：
  - 周期 pipeline（env 开关）：`NEWS_AI_ENABLED=true`
  - 管理员手动重跑：`POST /api/news/admin/{news_id}/ai/rerun`
  - 运维状态：`GET /api/system/news-ai/status`

数据流（简化）：

1. 新闻进入系统（管理员创建或 RSS ingest）
2. News AI pipeline 选取待处理新闻
3. 根据 provider 策略调用 OpenAI-compatible `/chat/completions`
4. 解析并写入 AI 标注（摘要/要点/关键词/风险等级等）
5. 前端列表/详情联动展示 AI 信息；管理员可查看错误趋势/积压量

### 4.5 论坛与内容审核

- 帖子/评论：`/api/forum/posts*`、`/api/forum/comments*`
- 审核：`/api/forum/admin/*`
  - 贴子/评论审核
  - 批量审核
  - 内容过滤配置与敏感词管理

### 4.6 律所/律师与认证

- 律所/律师列表：`/api/lawfirm/firms*`、`/api/lawfirm/lawyers*`
- 预约咨询/评价：`/api/lawfirm/consultations`、`/api/lawfirm/reviews`
- 律师认证：
  - 申请：`POST /api/lawfirm/verification/apply`
  - 状态：`GET /api/lawfirm/verification/status`
  - 管理员审核：`POST /api/lawfirm/admin/verifications/{verification_id}/review`

### 4.7 支付与余额

- 下单/支付：`/api/payment/orders*`
- 回调：`POST /api/payment/webhook`（验签依赖 `PAYMENT_WEBHOOK_SECRET`）
- 余额：`/api/payment/balance*`
- 管理端：订单列表/退款/统计：`/api/payment/admin/*`

---

## 5. 运维与排障索引

- API 总览：`http://localhost:8000/docs`
- 生产部署与冒烟：`docs/PROD_DEPLOY_AND_SMOKE_SOP.md`
- News AI 一键冒烟脚本：`scripts/README.md`
- 核心 API 速查：`docs/API_QUICK_REFERENCE.md`
- 本地开发指南：`docs/DEV_GUIDE.md`
