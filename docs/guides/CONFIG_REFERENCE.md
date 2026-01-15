# 配置参考（CONFIG_REFERENCE）

本文件从**现有代码**（`backend/app/config.py`、`backend/app/routers/system.py`、各 service/router）抽取“开发者需要关心”的配置项。

## 1. env 文件加载规则

后端 `Settings` 会按顺序加载 env：

- 若设置 `ENV_FILE`：只加载该文件
- 否则自动尝试（存在即加载）：
  - `backend/.env`
  - 仓库根 `.env`

## 2. 后端环境变量（ENV）

### 2.1 必要项（生产 `DEBUG=false`）

- `DEBUG=false`
- `DATABASE_URL`：建议 `postgresql+asyncpg://...`
- `JWT_SECRET_KEY` 或 `SECRET_KEY`：
  - **长度 >= 32** 且不能是默认占位符
- `PAYMENT_WEBHOOK_SECRET`：
  - **长度 >= 16**
- `REDIS_URL`：
  - Redis 必须可用，否则后端拒绝启动（`backend/app/main.py`）

### 2.2 常用项（开发/测试/联调）

- `DEBUG=true|false`
- `SQL_ECHO=1`：SQLAlchemy 打印 SQL
- `CORS_ALLOW_ORIGINS`：逗号分隔字符串或列表字符串
- `FRONTEND_BASE_URL`：用于 robots/sitemap/邮件链接等生成
- `TRUSTED_PROXIES`：用于限流中间件在反向代理下取真实 IP（`X-Forwarded-For`/`X-Real-IP`）

### 2.3 存储（上传）

- `STORAGE_PROVIDER=local|s3`

当 `STORAGE_PROVIDER=s3` 时需要：

- `STORAGE_S3_BUCKET`
- `STORAGE_PUBLIC_BASE_URL`

可选：

- `STORAGE_S3_ENDPOINT_URL`
- `STORAGE_S3_REGION`
- `STORAGE_S3_ACCESS_KEY_ID`
- `STORAGE_S3_SECRET_ACCESS_KEY`
- `STORAGE_S3_PREFIX`（默认 `uploads`）

### 2.4 额度/配额（Quota）

环境变量默认值（会被 SystemConfig 覆盖，见下文）：

- `FREE_AI_CHAT_DAILY_LIMIT`（默认 5）
- `VIP_AI_CHAT_DAILY_LIMIT`（默认 1e9）
- `FREE_DOCUMENT_GENERATE_DAILY_LIMIT`（默认 10）
- `VIP_DOCUMENT_GENERATE_DAILY_LIMIT`（默认 50）

### 2.5 周期任务（后台 Job）

由 `backend/app/main.py` 注册（通常依赖 Redis）：

- RSS 采集
  - `RSS_FEEDS` / `RSS_INGEST_ENABLED`
  - `RSS_INGEST_INTERVAL_SECONDS`
- News AI
  - `NEWS_AI_ENABLED`
  - `NEWS_AI_INTERVAL_SECONDS`
- 结算
  - `SETTLEMENT_JOB_ENABLED`
  - `SETTLEMENT_JOB_INTERVAL_SECONDS`
- 微信支付证书刷新
  - `WECHATPAY_CERT_REFRESH_ENABLED`
  - `WECHATPAY_CERT_REFRESH_INTERVAL_SECONDS`
- 律师复核 SLA
  - `REVIEW_TASK_SLA_JOB_ENABLED`
  - `REVIEW_TASK_SLA_SCAN_INTERVAL_SECONDS`

### 2.6 监控

- `METRICS_AUTH_TOKEN`
  - 设置后访问 `/metrics` 需要 `Authorization: Bearer <token>`

### 2.7 AI（能力开关与密钥）

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `AI_MODEL`
- `AI_FALLBACK_MODELS`

注意：

- **敏感密钥必须走 env/Secret 注入**，禁止写入 SystemConfig（代码硬拦截）。

## 3. SystemConfig（数据库配置项）

SystemConfig 表：`system_configs`

API：`/api/system/configs`（管理员）

### 3.1 通用规则：禁止存储 secrets

`backend/app/routers/system.py` 中 `_validate_system_config_no_secrets()` 会阻止以下情况：

- key 名包含 `secret`/`password`/`api_key`/`private_key` 等（会直接 400）

### 3.2 特殊：News AI providers 配置

允许配置 providers（用于多供应商/多 base_url 策略），但**providers JSON/B64 中禁止出现 `api_key` 字段**：

- `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON`
- `NEWS_AI_SUMMARY_LLM_PROVIDERS_B64`
- 以及其 `_PROD` 等后缀版本

原则：

- providers 只描述 `base_url`/`model`/权重/鉴权头结构等
- 实际 `OPENAI_API_KEY` 必须来自 env/Secret

### 3.3 Quota（配额）相关 key

`backend/app/services/quota_service.py` 会优先从 SystemConfig 读取（找不到才用 env 默认）：

- `FREE_AI_CHAT_DAILY_LIMIT`
- `VIP_AI_CHAT_DAILY_LIMIT`
- `FREE_DOCUMENT_GENERATE_DAILY_LIMIT`
- `VIP_DOCUMENT_GENERATE_DAILY_LIMIT`

### 3.4 论坛审核（脚本/测试中使用）

例如种子脚本/测试会写入：

- `forum.review.enabled`
- `forum.post_review.enabled`
- `forum.post_review.mode`

### 3.5 律师复核 SLA

- `CONSULT_REVIEW_SLA_JSON`（用于 SLA 计算/通知策略）

## 4. 建议

- **开发阶段**：优先用 `backend/env.example` 作为可运行配置模板
- **生产阶段**：env/Secret 管理敏感项，SystemConfig 只放业务开关与非敏感参数
