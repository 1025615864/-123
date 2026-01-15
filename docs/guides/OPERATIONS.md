# 运维与发布（OPERATIONS）

## 1. 生产配置要点

当 `DEBUG=false` 时，后端会启用强校验：

- `JWT_SECRET_KEY`/`SECRET_KEY` 必须是安全值（长度 >= 32，且不能使用默认值）
- `PAYMENT_WEBHOOK_SECRET` 必须设置（长度 >= 16）
- `REDIS_URL` 必须设置且 Redis 可连接（否则后端拒绝启动）
- 数据库必须处于 Alembic head（否则后端拒绝启动）

## 2. Docker Compose（生产示例）

参考：`docker-compose.prod.yml`

组件：

- Postgres
- Redis
- backend（uvicorn workers=4）
- frontend（Nginx 静态站 + `/api`/`/ws` 反代）

建议：

- 将敏感变量通过 `.env` 或 Secret 管理注入（不要提交到仓库）

## 3. Kubernetes（Helm）

参考：`helm/baixing-assistant/`

默认 Ingress：

- `/api` -> backend
- `/` -> frontend

重要：

- 生产需要额外路由 `/ws` -> backend，保证 WebSocket 可用。

## 4. 周期任务（后台 Job）

后端在 lifespan 启动周期任务（需要 Redis 可用）：

- scheduled_news：定时发布/下架
- rss_ingest：RSS 采集
- news_ai_pipeline：News AI 标注/风控
- settlement：结算
- wechatpay_platform_certs_refresh：微信支付证书刷新
- review_task_sla：律师复核 SLA 催办

## 5. 监控与健康检查

- `GET /health`：基础健康
- `GET /health/detailed`：数据库/AI 配置/内存
- `GET /metrics`：Prometheus 指标
  - 若设置 `METRICS_AUTH_TOKEN`，需带 `Authorization: Bearer <token>`

## 6. 发布后冒烟（Post Deploy Smoke）

仓库提供 GitHub Actions 手动工作流：

- `.github/workflows/post-deploy-smoke.yml`

该 workflow 依赖：

- `scripts/smoke-news-ai.sh`

必需 secrets：

- `BASE_URL`：线上地址（例如 `https://yourdomain.com`）
- `ADMIN_TOKEN`：管理员 JWT token

可选：

- `STRICT=1`：要求新闻列表里至少有一条带 AI keywords

## 6.1 模块 Runbook（建议运维阅读）

- 支付与回调审计：`docs/modules/PAYMENT.md`
- 结算与提现：`docs/modules/SETTLEMENT.md`
- 律师复核与 SLA：`docs/modules/REVIEWS_SLA.md`
- News AI：`docs/modules/NEWS_AI.md`
- SystemConfig 规则：`docs/modules/SYSTEM_CONFIG.md`

## 7. SystemConfig 与 Secrets

系统配置（SystemConfig）用于可变业务开关与参数，但：

- **禁止存储敏感 secret（如 OPENAI_API_KEY）**
- 后端对敏感 key/结构做了硬拦截，并有单测覆盖

补充：

- News AI providers 配置允许写入，但 providers 内容里禁止包含 `api_key` 字段
- 微信支付平台证书缓存会写入 SystemConfig：`WECHATPAY_PLATFORM_CERTS_JSON`
