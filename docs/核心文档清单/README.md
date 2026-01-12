# 百姓法律助手（Baixing Legal Assistant）

一句话简介：一个面向 **法律咨询 + 内容资讯 + 社区互动 + 律所服务** 的全栈平台，后端提供统一 `/api`，前端为 React SPA，并内置 **AI 法律咨询** 与 **News AI 内容加工/运营** 能力，支持 Docker Compose 与 Helm 部署。

---

## 1. 项目解决什么问题

- 面向普通用户：
  - 通过 AI 法律咨询与模板化文书生成，降低法律服务的获取门槛。
  - 通过新闻/专题/订阅、论坛互动等，形成内容与社区生态。
- 面向律师/律所：
  - 提供律所/律师展示、用户预约咨询、（可扩展的）收费与结算闭环。
- 面向运营/管理员：
  - 管理后台支持新闻运营、News AI 管道运维、论坛内容治理、用户/订单/回调审计、结算与提现审核等。

---

## 2. 核心功能列表（已实现）

- **用户体系**

  - 注册/登录（JWT Bearer）
  - 邮箱验证（发送验证邮件 + token 验证）
  - 手机绑定/验证码校验（开发环境可回传 code）
  - 角色：user/lawyer/admin/super_admin

- **AI 法律咨询**（可选启用）

  - `/api/ai/chat` 同步对话
  - `/api/ai/chat/stream` SSE 流式对话
  - 会话与消息落库（consultations/chat_messages）
  - 游客试用配额 + 登录用户配额/VIP（Quota）

- **法律文书生成**

  - 生成：`POST /api/documents/generate`（游客/登录均可，配额与限流）
  - 保存：`POST /api/documents/save`（登录）
  - 我的文书：`GET /api/documents/my`、导出 PDF
  - 模板版本：`document_templates` + `document_template_versions`

- **新闻与 News AI**

  - 新闻列表/详情/分类/专题
  - 收藏、浏览历史、订阅
  - RSS 来源与采集记录
  - News AI 标注（摘要/风险/关键词/高亮），带重试与错误统计
  - 管理端：新闻编辑/版本历史/回滚、AI 工作台生成记录、链接检查
  - 周期任务：定时发布/取消发布、RSS ingest、News AI pipeline（生产建议 Redis 锁）

- **论坛与内容治理**

  - 发帖/评论/点赞/收藏/表情反应
  - 敏感词/广告规则检测与“需审核”工作流
  - 管理端：帖子/评论审核、批量操作、配置内容过滤规则

- **支付与订单（商业化）**

  - 创建订单：`POST /api/payment/orders`（VIP/充值/次数包/咨询等）
  - 发起支付：`POST /api/payment/orders/{order_no}/pay`（alipay/ikunpay/balance；wechat 暂未开放）
  - 回调与审计：`/api/payment/alipay/notify`、`/api/payment/ikunpay/notify`、`payment_callback_events`
  - 公共渠道状态：`GET /api/payment/channel-status`（对前端展示可用支付方式）

- **律所/律师与咨询预约**

  - 律所/律师列表与详情
  - 用户预约咨询（可能生成支付订单）
  - 律师工作台：接单/拒单/完成（与支付状态联动）

- **律师结算与提现**

  - 律师钱包、收入记录、收款账户
  - 提现申请、管理员审核/导出
  - 周期任务：结算（生产建议 Redis 锁）

- **通知系统**

  - 通知列表/未读计数/批量已读/批量删除
  - 论坛审核、系统广播等场景

- **全局搜索**
  - 搜索新闻、帖子、律所、律师、法律知识
  - 搜索历史记录（search_history）

---

## 3. 技术栈概览（关键版本以仓库文件为准）

### 3.1 后端

- 语言：Python 3.10+（CI 使用 3.11）
- 框架：FastAPI
- 运行：Uvicorn
- ORM：SQLAlchemy 2.x（async）
- 迁移：Alembic（仓库包含 baseline + 多个 migration；生产 `DEBUG=false` 默认启用 Alembic head 门禁）
- DB：SQLite（默认）/ PostgreSQL（生产推荐）
- 鉴权：JWT（python-jose + cryptography）
- 缓存/锁：Redis（生产强依赖；`DEBUG=false` 时 Redis 不可用会启动失败，用于限流/分布式锁/周期任务）
- AI：OpenAI-compatible（openai/httpx），LangChain + ChromaDB（RAG）

### 3.2 前端

- React 19 + TypeScript
- Vite 7
- React Router 7
- TanStack React Query 5
- Axios（统一加 `Authorization` 与 `X-Api-Envelope`）
- TailwindCSS 4

### 3.3 部署

- Docker Compose：`docker-compose.yml`（本地演示）
- Docker Compose（生产示例）：`docker-compose.prod.yml`（含 Redis）
- Helm：`helm/baixing-assistant`（K8s + Ingress，默认 `/api` -> backend）

---

## 4. 环境设置与启动

### 4.1 本地开发（推荐：前后端分开跑）

#### 后端

在仓库根目录的 `backend/` 下执行：

```bash
python -m venv .venv
.venv\Scripts\activate

# 仅运行：
py -m pip install -r requirements.txt

# 跑测试/CI 同步依赖（推荐开发机装）：
py -m pip install -r requirements-dev.txt

# 可选：复制环境变量示例（默认 SQLite，可直接跑）
# copy env.example .env

py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问：

- API：`http://localhost:8000/api`
- Swagger：`http://localhost:8000/docs`

#### 前端

在仓库根目录的 `frontend/` 下执行：

```bash
npm install
npm run dev
```

访问：

- 前端 Dev：`http://localhost:5173`

> 前端默认通过 Vite 代理把 `/api` 转发到后端（见 `frontend/vite.config.ts`；可用 `VITE_PROXY_TARGET` 覆盖）。

---

### 4.2 Docker Compose（最快体验）

仓库根目录执行：

```bash
docker compose up -d --build
```

- 前端（Docker）：`http://localhost:3000`
- 后端：`http://localhost:8000`

注意：

- `docker-compose.yml` 中包含演示用的弱口令/示例 JWT key（**仅本地演示**）。生产必须替换。

---

### 4.3 生产部署（Docker Compose 示例）

1. 复制 `env.example.txt` 到仓库根目录 `.env` 并填写真实值

2. 启动：

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

生产建议：

- 使用 PostgreSQL
- 使用 Redis（生产 `DEBUG=false` 时为强依赖：Redis 不可用会启动失败；用于限流/分布式锁/周期任务）
- 通过 Secret Manager 注入：
  - `JWT_SECRET_KEY/SECRET_KEY`
  - `PAYMENT_WEBHOOK_SECRET`
  - `OPENAI_API_KEY`
  - 支付渠道密钥（如 `IKUNPAY_KEY`/`ALIPAY_PRIVATE_KEY` 等）

---

### 4.4 Helm（Kubernetes）部署

- Chart：`helm/baixing-assistant`
- 说明：见 `helm/baixing-assistant/README.md`

---

## 5. 重要安全与运维约束（必须阅读）

- **Secrets 不入库**：管理后台 `SystemConfig` 禁止存储任何密钥/密码（服务端会返回 400），必须使用环境变量/Secret Manager 注入。
- **生产环境密钥强校验**：当 `DEBUG=false` 时，后端会校验 `SECRET_KEY` 长度与安全性、并要求 `PAYMENT_WEBHOOK_SECRET` 必填。
- **周期任务多副本**：生产多副本部署务必提供 Redis（用于分布式锁），避免重复跑任务（News 定时发布、RSS ingest、News AI pipeline、结算等）。

---

## 6. 常用命令（建议给专家快速验证）

- 后端单测：

```bash
cd backend
py -m pip install -r requirements-dev.txt
py -m pytest -q
```

- 前端构建：

```bash
cd frontend
npm ci
npm run build
```

- E2E（文书闭环最小集）：

```bash
npm --prefix frontend run test:e2e:install
npm --prefix frontend run test:e2e -- --grep "documents:"
```
