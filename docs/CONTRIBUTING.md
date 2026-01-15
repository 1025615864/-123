# 贡献指南（CONTRIBUTING）

本指南面向仓库贡献者，聚焦“如何按现有项目约定新增功能且不破坏可交付性”。

## 1. 本地开发

推荐使用仓库根：

- `start-dev.ps1`

详见：`docs/guides/DEV_GUIDE.md`

## 2. 新增后端 API

- 路由文件：`backend/app/routers/<module>.py`
- 聚合入口：`backend/app/routers/__init__.py`
- 数据库写入：优先在 `backend/app/services/` 封装业务逻辑

鉴权：

- 需要登录：依赖 `get_current_user`
- 需要管理员：依赖 `require_admin`
- 敏感操作：可额外加 `require_user_verified` / `require_phone_verified` / `require_email_verified`

响应：

- 前端默认使用 Envelope（`X-Api-Envelope: 1`），后端 `EnvelopeMiddleware` 会自动包装

## 3. 新增数据模型与迁移

- Model：`backend/app/models/<name>.py`
- init_db 导入列表：`backend/app/database.py` 的 `init_db()` 会 import models

迁移：

- 生产（`DEBUG=false`）要求数据库在 Alembic head
- 使用 `python backend/scripts/alembic_cmd.py upgrade head`

详见：`docs/DATABASE.md`

## 4. SystemConfig 使用规范

- 仅用于业务开关/非敏感参数
- 禁止写入 secret（OPENAI_API_KEY 等）
- providers 配置中也禁止包含 api_key 字段

详见：`docs/guides/CONFIG_REFERENCE.md`

## 5. 前端开发规范

- API 统一走 `frontend/src/api/client.ts`
- WebSocket 统一走 `frontend/src/hooks/useWebSocket.ts`

## 6. 测试与门禁

- 后端：`pytest backend/tests/ -v`
- 前端：`npm --prefix frontend run build`
- E2E：`npm --prefix frontend run test:e2e`
- 预提交：`.pre-commit-config.yaml`
