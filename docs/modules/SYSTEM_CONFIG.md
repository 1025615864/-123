# SystemConfig（系统配置）

本模块用于解释系统配置表 `system_configs` 与其 API，以及项目对“敏感配置”的治理策略。

## 1. 数据表

- Model：`backend/app/models/system.py:SystemConfig`
- 表：`system_configs`

字段：

- `key`（唯一）
- `value`（字符串，可为空）
- `category`
- `updated_by` -> `users.id`

## 2. 管理 API（/api/system）

实现：`backend/app/routers/system.py`

- `GET /api/system/configs`（admin）
- `GET /api/system/configs/{key}`（admin）
- `PUT /api/system/configs/{key}`（admin）
- `POST /api/system/configs/batch`（admin）

返回值会对敏感 key 做 mask（显示为 `***`）。

## 3. 敏感信息治理：禁止在 SystemConfig 存 secrets

关键实现：

- `_validate_system_config_no_secrets(key, value)`

规则：

- key 名包含 `secret/password/api_key/private_key` 等会被拒绝（HTTP 400）
- 例外：News AI providers 配置 key（见下节）

原因：

- SystemConfig 本质存 DB，通常更容易被误导出/备份/查看
- secret 必须通过 env/Secret Manager 注入

## 4. News AI providers 特殊规则

允许配置 providers，但 providers 内容里**禁止包含 `api_key` 字段**。

- 允许的 key：
  - `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON`
  - `NEWS_AI_SUMMARY_LLM_PROVIDERS_B64`
  - 以及 `_<ENV>` 后缀版本（例如 `_PROD`）

providers 允许描述：

- `base_url` / `model` / 权重
- 鉴权头结构（header name/prefix 等）

但真实密钥必须来自：

- `OPENAI_API_KEY`（env/Secret）

详见：`docs/guides/CONFIG_REFERENCE.md`。

## 5. 运维与观测相关 API

同一个 router 下还提供：

- `GET /api/system/news-ai/status`（admin）
- `GET /api/system/ai/status`（admin）
- `GET /api/system/public/ai/status`（public）
- `GET /api/system/metrics`（admin）
- `/dashboard/*`、`/analytics/*` 等运营统计接口

建议：

- 这些接口应在生产中置于管理员权限与网络边界内。
