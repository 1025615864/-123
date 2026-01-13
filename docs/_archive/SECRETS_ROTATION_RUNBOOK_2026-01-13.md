# Secrets 轮换与最小权限 Runbook

日期：2026-01-13

## 0. 目标

- 明确本项目哪些 secrets 需要/可以轮换
- 给出“轮换步骤 + 验证 + 回滚”标准流程
- 落地最小权限与分层管理（dev/staging/prod 分离；CI secrets 与生产 secrets 分离）

> 红线：任何 secret 不允许写入 SystemConfig（管理后台系统设置）。

---

## 1. Secrets 清单（建议按“影响范围”分级）

### 1.1 高危（轮换需严格演练）

- `DATABASE_URL`（包含 DB 用户名/密码）
- `POSTGRES_PASSWORD`（Compose 口径）
- `REDIS_PASSWORD` / `REDIS_URL`
- `PAYMENT_WEBHOOK_SECRET`

### 1.2 中危（可较频繁轮换）

- `JWT_SECRET_KEY` / `SECRET_KEY`
  - 注意：轮换会影响现有登录态（旧 token 失效）
- `OPENAI_API_KEY`

### 1.3 低危/配置类（不属于 secrets）

- `OPENAI_BASE_URL` / `AI_MODEL`
- `CORS_ALLOW_ORIGINS`
- `FRONTEND_BASE_URL`

---

## 2. 最小权限原则

- **环境隔离**：
  - CI 用 dummy key/测试 key，不得复用生产 key。
  - Staging/Prod 分离（建议 GitHub Environments）。
- **按用途分权**：
  - 支付回调 secret 与 AI key 分离，不要复用同一 secret。
  - DB 用户分离：应用只拿 DML 权限；迁移使用单独 migrator 用户（如采用）。
- **可审计**：
  - 轮换必须留下：时间、操作者、变更范围、验证证据、回滚证据。

---

## 3. 轮换通用流程（推荐标准）

### 3.1 Preflight（轮换前）

- 备份（生产必做）：
  - `py backend/scripts/db_backup.py --verify`（PG）
  - 或 `py backend/scripts/db_backup.py`（SQLite）
- 确认可回滚：
  - 旧 secret 的安全存储位置（Secret Manager / K8s Secret 历史版本 / 受控密码库）
- 确认发布窗口：
  - 明确是否允许用户短时掉线（例如 JWT 轮换会导致用户需要重新登录）

### 3.2 Rotate（轮换执行）

- Kubernetes（Helm/Secret/ExternalSecrets）：
  - 更新 Secret（或 ExternalSecret remote ref 指向的新版本）
  - `helm upgrade` 或触发 rollout（确保 Pod 重建读取新 env）
- Docker Compose：
  - 更新 `.env`（不入库）
  - `docker compose up -d` 或 `restart backend`

### 3.3 Verify（轮换后验证）

最小验证集：

- `GET /health`（backend）
- 登录/鉴权：
  - 新 token 可用（JWT_SECRET_KEY 轮换后必须验证）
- 支付回调：
  - 走一条 sandbox/mock 回调或调用渠道状态接口 `GET /api/payment/channel-status`
- AI（如启用）：
  - 发起一次最小请求（或在后台进行 dry-run）
- Redis：
  - 启动日志无 Redis 连接失败（生产 `DEBUG=false` 强依赖）

### 3.4 Rollback（失败回滚）

优先级：

1. **回滚 secret**（回到旧值）
2. **回滚应用版本**（回到上一镜像/tag）
3. **数据恢复**（仅当确实造成数据破坏；谨慎）

---

## 4. 关键项专项注意

### 4.1 JWT_SECRET_KEY / SECRET_KEY

- 轮换影响：
  - 旧 token 全部失效（用户需要重新登录）
- 建议：
  - 在低峰窗口执行
  - 轮换后公告（或在前端提示“登录已失效，请重新登录”）

### 4.2 PAYMENT_WEBHOOK_SECRET

- 轮换影响：
  - 第三方回调验签/鉴权可能失败
- 建议：
  - 若支付渠道支持“灰度/双密钥”，可短期支持新旧并行（若代码/渠道允许）
  - 否则必须确保渠道后台同步更新后再切换生产 secret

### 4.3 OPENAI_API_KEY

- 建议：
  - 使用子账号/子 key（可按环境分配）
  - 有额度与速率限制的监控告警

### 4.4 DATABASE_URL / DB 密码

- 轮换影响：
  - 应用无法连接数据库导致启动失败
- 建议：
  - DB 侧先创建新用户/新密码并授权
  - 应用切换连接串
  - 验证后再撤销旧用户/旧密码

---

## 5. 归档要求

每次轮换至少归档：

- 轮换目标与范围
- 执行命令/变更摘要
- 验证结果截图/日志
- 回滚路径是否验证
