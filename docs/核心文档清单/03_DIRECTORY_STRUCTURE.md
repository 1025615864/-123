# 目录结构与模块说明（Directory Structure）

> 只列出核心目录与关键文件，忽略 `node_modules/`、构建产物、缓存等。

## 1. 仓库根目录（精简树）

```text
百姓助手/
├── backend/                         # 后端（FastAPI + SQLAlchemy）
│   ├── app/                         # 应用代码（router/service/model/schema）
│   ├── alembic/                     # Alembic 迁移（versions/）
│   ├── scripts/                     # 运维/联调/备份/冒烟脚本
│   ├── tests/                       # 后端测试
│   ├── Dockerfile                   # 后端镜像构建
│   ├── requirements.txt             # 运行依赖
│   ├── requirements-dev.txt         # 测试/开发依赖
│   └── env.example                  # 后端环境变量示例（默认 SQLite）
├── frontend/                        # 前端（React + TS + Vite）
│   ├── src/                         # 前端源码
│   ├── public/                      # 静态资源
│   ├── tests/                       # Playwright E2E
│   ├── Dockerfile                   # 前端镜像构建（Nginx）
│   ├── nginx.conf                   # 容器 Nginx 配置
│   ├── package.json                 # 前端依赖与脚本
│   └── vite.config.ts               # 本地代理与构建配置
├── docs/                            # 项目文档（PRD/TECH_SPEC/API/DATABASE 等）
│   └── 核心文档清单/                 # （本目录）对外评审材料
├── helm/baixing-assistant/           # Helm Chart（K8s 部署）
├── scripts/                         # 仓库级脚本（smoke/运维）
├── docker-compose.yml                # 本地演示：PG + backend + frontend
├── docker-compose.prod.yml           # 生产示例：PG + Redis + backend + frontend
├── env.example.txt                   # 根目录 .env 示例（供 prod compose）
├── TASKS.md                          # 迭代任务跟踪
└── README.md                          # 仓库总 README（开发/部署入口）
```

---

## 2. 后端目录（backend/app）

```text
backend/app/
├── main.py                   # FastAPI 入口；挂载 /api；启动周期任务；中间件
├── config.py                 # Pydantic Settings；env 文件解析；生产安全校验
├── database.py               # Async Engine/Session；init_db() 创建表+自修复
├── routers/                  # API 路由（按业务域拆分）
│   ├── __init__.py           # 聚合路由：include_router(...)；统一挂载 /api
│   ├── user.py               # 注册/登录/邮箱验证/短信绑定/管理员用户管理
│   ├── ai.py                 # AI 咨询（含流式/SSE、会话历史、导出等）
│   ├── documents.py          # 文书生成/保存/导出
│   ├── forum.py              # 论坛发帖/评论/审核/管理
│   ├── news.py               # 新闻/专题/订阅/评论/管理端工作台
│   ├── payment.py            # 订单创建/支付发起/回调验签/回调审计
│   ├── lawfirm.py            # 律所/律师/预约咨询（可生成支付订单）
│   ├── settlement.py         # 律师钱包/收入/提现/审核
│   ├── upload.py             # 头像/图片/附件上传与静态访问
│   ├── notification.py       # 通知列表/未读/批量
│   ├── search.py             # 全局搜索 + 搜索历史
│   └── system.py             # SystemConfig/运维状态/安全策略（secrets 不入库）
├── services/                 # 业务服务层（聚合 DB、缓存、外部接口）
├── models/                   # ORM 模型（表结构权威）
├── schemas/                  # Pydantic 请求/响应 DTO
├── middleware/               # 日志、限流、指标、响应 envelope 等
└── utils/                    # security/deps/permissions/rate_limiter 等通用能力
```

---

## 3. 前端目录（frontend/src）

```text
frontend/src/
├── main.tsx                  # 前端入口：QueryClient/Theme/Language/Auth Provider
├── App.tsx                   # 路由表：前台 + /admin
├── api/client.ts             # axios 实例：token 注入 + envelope 自动解包
├── components/               # 通用组件（Layout/AdminLayout/UI 组件等）
├── pages/                    # 页面
│   ├── ChatPage.tsx          # AI 对话
│   ├── DocumentGeneratorPage.tsx  # 文书生成
│   ├── ForumPage.tsx         # 论坛
│   ├── NewsPage.tsx          # 新闻
│   ├── OrdersPage.tsx        # 订单与支付入口
│   └── admin/*               # 管理后台页面
├── contexts/                 # Auth/Theme/Language
├── hooks/                    # Toast、Api Hook 等
├── queries/ / queryKeys.ts   # React Query 约定
└── types/                    # 前端类型
```

---

## 4. 基于目录结构的架构模式总结

- **系统级**：前后端分离架构

  - 前端：React SPA
  - 后端：单体服务（按业务域模块化拆分），统一 API 前缀 `/api`

- **后端内部**：典型 **分层架构（Layered Architecture）/“MVC-ish”**

  - Router（Controller）
  - Service（Domain Service / Application Service）
  - Model（ORM/Entity）
  - Schema（DTO）

- **部署形态**：

  - 单机：Docker Compose
  - 集群：Helm + Ingress（可选 ExternalSecrets）

- **数据层**：
  - 单 DB（SQLite/PG 二选一；默认 SQLite）
  - 无独立微服务拆分；更像“可演进的单体”。
