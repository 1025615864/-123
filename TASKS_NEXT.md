# TASKS_NEXT（下一阶段计划）

> 本文件：当前迭代任务主计划与验收口径。
> 历史归档：docs/_archive/TASKS_YYYY-MM-DD.md

## 0. 当前基线（已达成）

- 覆盖率：总覆盖率 **60.81%**（本地 `--cov-fail-under=60` 通过；CI 门禁已抬升到 `--cov-fail-under=60`）
- 关键模块：
  - app/services/review_task_sla_service.py：100%
  - app/middleware/envelope_middleware.py：100%
  - app/middleware/sentry_context_middleware.py：100%
  - app/middleware/metrics_middleware.py：100%
  - app/services/disclaimer.py：100%
  - app/services/content_safety.py：100%
  - app/services/ai_response_strategy.py：100%
  - app/schemas/document.py：100%
  - app/services/email_service.py：100%
  - app/services/voice_config_service.py：100%
  - app/services/ai_intent.py：92%
  - app/services/cache_service.py：95%
  - app/utils/rate_limiter.py：100%
  - app/utils/periodic_task_runner.py：99%
  - app/services/websocket_service.py：95%
  - app/routers/websocket.py：67%
  - app/services/user_service.py：95%
  - app/services/search_service.py：91%
  - app/routers/search.py：82%
  - app/routers/calendar.py：100%
  - app/services/quota_service.py：92%
  - app/services/sherpa_asr_service.py：48%

## 1. 下一阶段目标（建议 1-2 天内完成）

- 目标 1：总覆盖率稳定到 **>=60.8%**（建议留 **0.3%~0.8%** 安全余量）
- 目标 2：CI 覆盖率门禁抬升到 **60%**（先本地验证 `--cov-fail-under=60` 通过，再改 CI）
- 目标 3：触发 CI 跑一轮（含迁移+单测），确认 gate=60 在 CI 环境稳定通过
- 目标 4：持续推进到 **>=61%~62%**（按模块可测性分批推进，不引入 flaky）

## 2. 交付原则（强约束）

- 单测优先覆盖：纯逻辑函数 / 小型 middleware / 小型 service / utils
- 避免：依赖外部网络、真实第三方服务、随机时间/随机数导致的 flaky
- 每完成一个模块：
  - 先跑该模块测试 + ruff
  - 再跑全量 `pytest --cov` 确认门禁
  - 再更新本文件进展与验证命令
 - 覆盖率门禁抬升节奏（建议）：48 -> 50 -> 52 -> 55 -> 60（每次抬升前确保有安全余量且 CI 连续绿）

## 3. 工作项（按优先级）

### A. 快速涨覆盖（已完成：抬升到 48%）

- [x] A1：app/services/disclaimer.py（已补齐单测，覆盖率 100%）
- [x] A2：app/services/content_safety.py（已补齐单测，覆盖率 100%；修复 sanitize_output 在中文上下文无法匹配手机号/身份证的问题）
- [x] A3：app/services/ai_response_strategy.py（已补齐单测，覆盖率 100%）
- [x] A4：app/schemas/document.py（已补齐单测，覆盖率 100%）
- [x] A5：app/services/voice_config_service.py（已补齐单测，覆盖率 100%）
- [x] A6：app/services/ai_intent.py（已补齐主要分支单测，覆盖率 92%）
- [x] A7：app/services/sherpa_asr_service.py（新增 mock 单测，覆盖率提升到 48%，用于快速抬升总覆盖率到 >=48%）

### B. 冲刺到 50%（建议优先做 1-2 个中等体量模块）

- B1：app/services/report_generator.py
  - 关注点：`build_consultation_report_from_export_data` 的输入清洗、时间解析、消息过滤、引用法条去重；`generate_consultation_report_pdf` 的依赖缺失异常分支；`_escape_paragraph`
  - 测试策略：纯逻辑分支直接断言；PDF 生成依赖缺失用 import monkeypatch/隔离环境触发 `RuntimeError("PDF_DEPENDENCY_MISSING")`
- B2：app/services/contract_review_service.py
  - 关注点：`_extract_json`（json fenced block / 原始 JSON / 垃圾输入 / 代码块剥离 / 截取 `{...}`）；`apply_contract_review_rules`（required_clauses 与 risk_keywords 增补逻辑、风险等级聚合）
  - 测试策略：完全纯逻辑，不依赖外部服务；构造 extracted_text 命中/不命中 patterns 与 keyword
- B3：app/services/email_service.py
  - 关注点：token 生成/校验/失效，cache 正常分支与异常 fallback 分支，过期清理分支
  - 测试策略：monkeypatch `cache_service.get_json/set_json` 成功/抛异常两套路径；冻结时间或直接构造 expires_at

### C. 维稳与门禁抬升

- [x] B1：覆盖率稳定 >=48% 后，门禁抬升到 `--cov-fail-under=48`
- [x] C2：本地覆盖率 >=50% 且留余量后，将 CI 门禁抬升到 `--cov-fail-under=50`
- C3：补 1-2 个小模块“安全余量”，保证 CI 不因环境差异回落

### D. 工具链与脚本稳定性（不影响门禁前提下进行）

- D1：持续对话脚本 `xinghuo_continue_http.ps1` 稳定性回归
  - 核心：优先使用 `curl.exe --noproxy "*" --data-binary @jsonfile` 调用 JSON-RPC（规避系统代理/编码问题）
  - 验收：连续多次调用 tools/list + tools/call 成功，无 503/timeout

### C. 技术债（不影响门禁的前提下逐步清）

- C1：扫描并移除过期 TODO/FIXME（优先 backend/app）
- C2：移除注释掉的代码块
- C3：统一格式化（black/isort/ruff format）

## 4. 验证命令（标准）

- 单文件：`backend/.venv/Scripts/python.exe -m pytest -q tests/<file>.py`
- 备注：如本机 `python` 命令不可用，优先使用 venv 的 `backend/.venv/Scripts/python.exe` 或 `py -m pytest ...`
- 新增模块：
  - `backend/.venv/Scripts/python.exe -m pytest -q tests/test_disclaimer.py`
  - `backend/.venv/Scripts/python.exe -m pytest -q tests/test_content_safety.py`
  - `backend/.venv/Scripts/python.exe -m pytest -q tests/test_ai_response_strategy.py`
  - `backend/.venv/Scripts/python.exe -m pytest -q tests/test_document_schemas.py`
  - `backend/.venv/Scripts/python.exe -m pytest -q tests/test_voice_config_service.py`
  - `backend/.venv/Scripts/python.exe -m pytest -q tests/test_ai_intent.py`
  - `backend/.venv/Scripts/python.exe -m pytest -q tests/test_sherpa_asr_service.py`
- 冲刺模块：
  - `backend/.venv/Scripts/python.exe -m pytest -q tests/test_report_generator.py`
  - `backend/.venv/Scripts/python.exe -m pytest -q tests/test_contract_review_service.py`
  - `backend/.venv/Scripts/python.exe -m pytest -q tests/test_email_service.py`
- 全量覆盖率：
  - `backend/.venv/Scripts/python.exe -m pytest tests/ -q --tb=short --cov=app --cov-report=xml:coverage.xml --cov-report=json:coverage.json --cov-report=term:skip-covered --cov-fail-under=60`
  - （历史/回滚排查用）`backend/.venv/Scripts/python.exe -m pytest tests/ -q --tb=short --cov=app --cov-report=xml:coverage.xml --cov-report=json:coverage.json --cov-report=term:skip-covered --cov-fail-under=52`
  - （历史/回滚排查用）`backend/.venv/Scripts/python.exe -m pytest tests/ -q --tb=short --cov=app --cov-report=xml:coverage.xml --cov-report=json:coverage.json --cov-report=term:skip-covered --cov-fail-under=50`
  - （历史/回滚排查用）`backend/.venv/Scripts/python.exe -m pytest tests/ -q --tb=short --cov=app --cov-report=xml:coverage.xml --cov-report=json:coverage.json --cov-report=term:skip-covered --cov-fail-under=48`

## 5. 本轮执行记录（实时更新）

- 已完成 A1-A4：新增 4 个单测文件（disclaimer/content_safety/ai_response_strategy/document schemas），并修复 `ContentSafetyFilter.sanitize_output` 的手机号/身份证脱敏规则；总覆盖率提升到 **46.81%**。
- 已完成 A5-A7：新增 voice_config/ai_intent/sherpa_asr 的单测；总覆盖率提升到 **48.06%**，并将 CI 覆盖率门禁抬升到 `--cov-fail-under=48`。
- 已新增 report_generator 单测：`tests/test_report_generator.py`（含 PDF 依赖缺失分支与可选 smoke），模块覆盖率提升到 **91%**；全量回归通过，总覆盖率提升到 **48.33%**。
- 已新增 contract_review_service 单测：`tests/test_contract_review_service.py`（覆盖 `_extract_json`/rules 应用/Markdown 渲染/OpenAI 调用 mock）；模块覆盖率提升到 **94%**；全量回归通过，总覆盖率提升到 **49.20%**。
- 已新增 email_service 单测：`tests/test_email_service.py`（覆盖 token 生成/校验/失效、cache 正常/异常 fallback、邮件发送分支 mock）；模块覆盖率提升到 **87%**；全量回归通过，总覆盖率提升到 **49.70%**。
- 已补齐 cache_service/email_service 单测并达标 50%：`tests/test_cache_service.py` 补齐 redis 异常回落/锁异常/clear_pattern 异常等分支；`tests/test_email_service.py` 补齐 cache exception fallback + 邮箱验证 token invalidate + 邮件发送异常分支；本地全量 `--cov-fail-under=50` 通过（总覆盖率 **50.05%**），并将 CI 覆盖率门禁抬升到 `--cov-fail-under=50`。
- 已补安全余量模块：新增 `tests/test_rate_limiter.py` 并增强 `tests/test_periodic_task_runner.py`；本地全量 `--cov-fail-under=50` 通过（总覆盖率 **50.31%**），其中 `app/utils/rate_limiter.py` 覆盖率 **100%**、`app/utils/periodic_task_runner.py` 覆盖率 **99%**。
- 已补 WebSocket/UserService 模块单测：新增 `tests/test_websocket_service.py` / `tests/test_websocket_router.py` / `tests/test_user_service.py`；本地全量 `--cov-fail-under=50` 通过（总覆盖率 **50.82%**），其中 `app/services/websocket_service.py` 覆盖率 **95%**、`app/routers/websocket.py` 覆盖率 **67%**、`app/services/user_service.py` 覆盖率 **95%**。
- 已补 Search 模块单测：新增 `tests/test_search_service.py` / `tests/test_search_router.py`；本地全量 `--cov-fail-under=50` 通过（总覆盖率 **51.36%**），其中 `app/services/search_service.py` 覆盖率 **91%**、`app/routers/search.py` 覆盖率 **82%**。
- 已补 Calendar 路由单测：新增 `tests/test_calendar_router.py`；本地全量 `--cov-fail-under=50` 通过（总覆盖率 **51.36%**），其中 `app/routers/calendar.py` 覆盖率 **48%**。
- 已补 QuotaService 单测：新增 `tests/test_quota_service.py`；本地全量 `--cov-fail-under=50` 通过（总覆盖率 **51.94%**），其中 `app/services/quota_service.py` 覆盖率 **92%**。
- 已补支付后台与对账/反馈等路由单测：新增 `tests/test_payment_admin_reconcile.py` / `tests/test_feedback_router.py` / `tests/test_payment_admin_orders.py` / `tests/test_payment_admin_callback_events.py` / `tests/test_payment_admin_config_and_stats.py` / `tests/test_payment_admin_wechat_certs.py`；本地全量回归通过。
- 已补存储与微信支付工具单测：新增 `tests/test_storage_service.py` 并增强 `tests/test_wechatpay_v3.py`；`app/services/storage_service.py` 与 `app/utils/wechatpay_v3.py` 覆盖率均提升到 **100%**。
- 覆盖率冲刺与门禁抬升：新增 `backend/.coveragerc`（`concurrency=greenlet,thread` + `relative_files=true`）以修复 async/greenlet 场景的行覆盖率采集；补齐 `admin_orders` 回滚分支后，本地全量 `--cov-fail-under=55` 通过（总覆盖率 **60.06%**），并将 CI 覆盖率门禁抬升到 `--cov-fail-under=55`。
- 覆盖率安全余量继续提升：新增 `tests/test_payment_orders_create.py` 覆盖 `orders_create` 的 `ai_pack`/`light_consult_review` 参数解析与异常分支（含直调函数触发 Pydantic 难以触达的类型分支），`orders_create.py` 覆盖率提升到 **100%**；新增 `tests/test_news_topics_and_comments.py` 覆盖 `news/topics` 与 `news/comments` 的关键分支（含评论创建失败 500 分支），`news/comments.py` 覆盖率提升到 **100%**；新增 `tests/test_forum_favorites_reactions.py` 覆盖 `forum` 的收藏/表情路由的 404/成功分支；新增 `tests/test_auth_context_middleware.py` 覆盖 `AuthContextMiddleware` 的异常解析分支；补齐 `tests/test_search_router.py` 登录态搜索历史分支。最终本地全量 `--cov-fail-under=55` 通过，总覆盖率提升到 **60.51%**。
- 覆盖率再冲刺：新增 `tests/test_forum_comments_router.py` 覆盖论坛评论创建/列表权限/删除/恢复/点赞分支；增强 `tests/test_rate_limit_middleware.py`（LRU 淘汰、redis 回退、APIKeyRateLimiter 分支）、增强 `tests/test_pii.py`（空字符串与银行卡回调分支）、增强 `tests/test_report_generator.py`（PDF 生成包含引用法条分支）。本地全量 `--cov-fail-under=60` 通过，总覆盖率提升到 **60.81%**；并将 CI 覆盖率门禁抬升到 `--cov-fail-under=60`。
- 已补支付用户端路由单测：新增 `tests/test_payment_user_routes.py`（/payment/orders 列表与筛选、/orders/{order_no}/cancel 分支、/pricing 读取 SystemConfig、/balance 与交易记录分页）；本地全量 `--cov-fail-under=52` 通过（总覆盖率 **52.56%**）。

- 修复 CI/backend-test 导入失败：补齐 `app/routers/forum/`、`app/routers/news/`、`app/routers/payment/` 子包的 `__init__.py` 并导出 `router`（统一指向 `*_legacy.py`）；同时新增兼容 shim（`forum/comments.py`、`forum/favorites.py`、`forum/reactions.py`、`news/topics.py`、`news/comments.py`、`payment/orders_create.py`、`payment/orders_pay.py`、`payment/admin_stats.py`）以对齐现有单测的 import 路径，确保 pytest 进入执行阶段（本机依赖环境缺失时用 `compileall` 先做语法冒烟）。

- backend-test 用例对齐：将 `payment/orders_pay.py` 调整为调用 `payment_legacy.pay_order` 的轻量 wrapper，并按异常 `detail`/返回值映射 `prometheus_metrics.record_payment_pay(method, result)`，以满足 `tests/test_orders_pay.py` 对 metrics 语义的断言，同时尽量减少新增逻辑行数。

## 6. 验收口径（覆盖率提升相关）

- 覆盖率：本地全量执行 `--cov-fail-under=60` 通过，且建议留 0.3%~0.8% 余量
- 稳定性：新增用例不依赖外网/真实第三方；无随机/时间抖动导致的 flaky
- 回归：关键模块测试与全量覆盖率均绿；CI workflow 同步门禁阈值
