# AI 编程助手规则（本仓库）

## 项目背景

- 项目名称：百姓法律助手
- 形态：前后端一体仓库（`backend/` + `frontend/`）
- 核心业务：AI 法律咨询、新闻资讯（含 News AI）、论坛社区、律所/律师服务、支付与结算、通知与运维后台。

## 核心开发原则

1. **不破坏可交付性**
   - 优先保持现有功能与 E2E 回归稳定。
   - 修改核心接口/数据结构时，需要同步更新前端调用与测试（如 Playwright 用例）。

2. **Secrets 永不入库**（强约束）
   - 任何 API key/secret（`OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET` 等）只能走环境变量/Secret Manager。
   - 严禁通过 SystemConfig（管理后台配置）写入 secrets；后端已做硬拦截。

3. **后端优先 async/typed**
   - 新增后端代码使用 async SQLAlchemy（`AsyncSession`）与明确的类型标注。
   - 路由层只做参数校验/权限校验；业务逻辑放 `services/`。

4. **前端保持一致的请求与错误处理**
   - API 调用尽量集中在 `frontend/src/hooks/useApi.ts` 或 `frontend/src/api/client.ts` 的统一封装。
   - 用户可见的错误必须可理解，并尽量可重试。

## 项目关键入口（必须知道）

- 后端入口：`backend/app/main.py`
  - 路由挂载：`/api`
  - 健康检查：`/health`、`/health/detailed`
- 后端配置：`backend/app/config.py`（Pydantic Settings）
- 路由聚合：`backend/app/routers/__init__.py`
- 前端路由：`frontend/src/App.tsx`

## 约定与建议

- 新增 API：
  - 放在 `backend/app/routers/<module>.py`
  - 需要登录时使用依赖 `get_current_user` / `require_admin` 等
  - 需要写数据库时优先保证事务完整、异常回滚清晰

- 新增表：
  - 放在 `backend/app/models/`
  - 同步更新 `init_db()` 模块导入列表（`backend/app/database.py`）
  - 如生产使用 Alembic，建议补迁移；但本仓库本地默认 SQLite 会自动 create_all

- 关键测试：
  - 后端：`pytest`
  - 前端：`npm run build`、`npm run test:e2e`

## 你应避免

- 不要把密钥写入 `.env` 并提交。
- 不要在组件内随意 `fetch`，统一走 axios client/hooks。
- 不要修改接口返回结构而不更新前端与测试。

## 当前主线（建议）

- 保持“咨询-内容-社区-支付-结算”的闭环可用。
- 优先做用户体验可感知的提升（加载/错误/空状态/重试），其次再做架构演进。
