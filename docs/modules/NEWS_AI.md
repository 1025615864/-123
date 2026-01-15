# News AI（NEWS_AI）

本模块描述新闻 AI 标注流水线、SystemConfig overrides 机制与运维接口。

## 1. Pipeline

- Service：`backend/app/services/news_ai_pipeline_service.py`
- 处理目标：为新闻生成
  - 摘要
  - highlights
  - keywords
  - risk_level（基于内容安全过滤/策略）

落库：

- `news_ai_annotations`（Model：`backend/app/models/news_ai.py:NewsAIAnnotation`）

## 2. SystemConfig overrides（按环境优先）

函数：`load_system_config_overrides(db)`

核心点：

- 基础 key：

  - `NEWS_AI_SUMMARY_LLM_ENABLED`
  - `NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT`
  - `NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY`
  - `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON`
  - `NEWS_AI_SUMMARY_LLM_PROVIDERS_B64`
  - `NEWS_REVIEW_POLICY_ENABLED`
  - `NEWS_REVIEW_POLICY_JSON`

- 环境 token：由 env `APP_ENV/ENV/ENVIRONMENT` 推导（prod->PROD，staging->STAGING 等）
- 若存在 `_PROD/_STAGING/...` 后缀版本，会优先使用后缀版本

安全规则：

- providers 配置禁止包含 `api_key` 字段（详见 `docs/modules/SYSTEM_CONFIG.md`）

## 3. 运维接口（/api/system/news-ai）

- `GET /api/system/news-ai/status`（admin）

提供：

- providers（脱敏后）
- pending/错误统计
- overrides 生效情况

## 4. 常见问题

- keywords 空：

  - pipeline 未运行或 annotation.processed_at 为 null
  - NEWS_AI_ENABLED 未开启或 Redis/job 不可用

- providers 不生效：
  - SystemConfig key 写错
  - 写入被 secret 拦截（包含 api_key）

详见：

- 配置参考：`docs/guides/CONFIG_REFERENCE.md`
- 排障：`docs/guides/TROUBLESHOOTING.md`
