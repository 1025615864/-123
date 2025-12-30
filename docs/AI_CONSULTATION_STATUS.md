# AI 咨询模块开发进度与现状说明

更新时间：2025-12-29

本文件用于记录「百姓助手」项目中 **AI 法律咨询模块** 的当前实现情况、已完成的增强点、接口与数据流细节、测试覆盖与已知风险点。后续规划可在此基础上继续扩展。

## 1. 模块入口与范围

- 后端 API 路由：`backend/app/routers/ai.py`
- 运维/状态接口：`backend/app/routers/system.py`（admin）
- 核心服务：`backend/app/services/ai_assistant.py`
- 请求/响应 Schema：`backend/app/schemas/ai.py`
- 数据模型：`backend/app/models/consultation.py`
- 前端页面（流式 SSE 客户端）：`frontend/src/pages/ChatPage.tsx`
- 前端管理后台（运维状态卡片）：`frontend/src/pages/admin/SettingsPage.tsx`

API 基础前缀为 `/api`（由主应用挂载决定），AI 路由前缀为 `/ai`，因此对外完整路径为：

- `/api/ai/chat`
- `/api/ai/chat/stream`
- `/api/ai/consultations`
- `/api/ai/consultations/{session_id}`
- `/api/ai/consultations/{session_id}` (DELETE)
- `/api/ai/consultations/{session_id}/export`
- `/api/ai/messages/rate`
- `/api/system/ai/status`（admin 运维状态）

## 2. 当前实现架构（后端）

### 2.1 主要组件

- **FastAPI Router**：负责鉴权、游客限流、参数校验、落库、SSE 组装等。
- **AILegalAssistant**：负责 RAG 检索、提示词拼装、与大模型交互（同步/流式）、会话内存管理。
- **LegalKnowledgeBase**：负责向量检索（Chroma）与（可选）写入向量库。

### 2.2 模型与表结构（持久化）

文件：`backend/app/models/consultation.py`

#### Consultation（consultations）

- `id`: int 主键
- `user_id`: int | null（允许为空，表示游客会话）
- `session_id`: string(50) 唯一索引
- `title`: string(200) | null
- `created_at`, `updated_at`
- `messages`: 与 `ChatMessage` 关系，`cascade="all, delete-orphan"`

#### ChatMessage（chat_messages）

- `id`: int 主键
- `consultation_id`: 外键 -> consultations.id
- `role`: string(20)（`user` / `assistant`）
- `content`: Text
- `references`: Text | null（JSON 字符串，存储法条引用数组）
- `rating`: int | null（1=差评, 2=一般, 3=好评）
- `feedback`: Text | null
- `created_at`

## 3. AI 助手服务实现细节（backend/app/services/ai_assistant.py）

### 3.1 LLM 调用

- 使用 LangChain 的 `ChatOpenAI`
- 主要参数：
  - `model = settings.ai_model`（默认在项目设置中通常为 `deepseek-chat`）
  - `api_key = SecretStr(settings.openai_api_key)`
  - `base_url = settings.openai_base_url`
  - `temperature = 0.7`
  - `model_kwargs = {"max_completion_tokens": 2000}`（用于限制回复长度）

说明：当前代码为了兼容静态检查，将 `max_completion_tokens` 放在 `model_kwargs`，实际是否生效取决于所使用的 OpenAI 兼容服务端。

### 3.2 RAG / 向量检索（Chroma）

`LegalKnowledgeBase.initialize()`：

- Embeddings：`OpenAIEmbeddings(api_key=..., base_url=...)`
- VectorStore：`Chroma(persist_directory=settings.chroma_persist_dir, collection_name="legal_knowledge")`

`LegalKnowledgeBase.search(query, k=5)`：

- 调用 `similarity_search_with_score`
- 返回 `[(content, metadata, score)]`

`AILegalAssistant.chat(...)` 与 `chat_stream(...)`：

- 固定 `k=5` 进行检索
- `context` = `_build_context(references)`
- 生成法条引用结构：`parsed_refs = _parse_references(references)`

### 3.3 系统提示词（SYSTEM_PROMPT）

`SYSTEM_PROMPT` 约束了输出格式：

- 问题理解 / 法律分析（要求引用条文）/ 风险评估 / 行动建议 / 追问确认
- 并在末尾拼接 `相关法律参考：{context}`

注意：当前“引用法条”的强约束主要依赖提示词约束与 RAG 提供的 `context`。如果检索为空，会退化为“基于法律知识回答”。

### 3.4 会话内存（in-memory conversation_histories）

- `conversation_histories: dict[str, list[{role, content}]]`
- `_max_sessions = 5000`：超过后基于 `_last_seen` 做简单淘汰
- `_max_messages_per_session = 50`：每个 session 最多保留 50 条（role/content）

在生成 prompt 时，仅取最近 `history[-10:]` 作为对话上下文拼入 messages。

## 4. 本次已完成的关键增强（开发进度）

本次增强目标是：

- **会话上下文跨服务重启可续**（不再只依赖内存缓存）
- **SSE 流式无论落库成败都能结束**（前端不会卡住）
- **严格权限与最小测试覆盖**

相关 commit：`d3ddd49`（已推送到 `origin/main`）

### 4.1 会话历史从 DB 注入 assistant（跨重启续聊）

#### 4.1.1 机制

- 新增 `SEED_HISTORY_MAX_MESSAGES = 20`
- 新增 `_load_seed_history(db, session_id, current_user)`：
  - 查 `Consultation.session_id`
  - 若存在且 `consultation.user_id != null`：要求 `current_user.id == consultation.user_id`，否则 `403`
  - 查出该 consultation 下所有 `ChatMessage`，按 `created_at` 排序
  - 转为 `[{role, content}]`，并截断到最近 20 条

#### 4.1.2 注入位置

- `/api/ai/chat`：

  - 若 `payload.session_id` 存在，则先 `_load_seed_history` 得到 `seed_history`
  - 调用 `assistant.chat(..., initial_history=seed_history)`

- `/api/ai/chat/stream`：
  - 若 `payload.session_id` 存在，则先 `_load_seed_history` 得到 `seed_history`
  - 调用 `assistant.chat_stream(..., initial_history=seed_history)`

#### 4.1.3 assistant 侧行为

`AILegalAssistant.get_or_create_session(session_id, initial_history=...)`：

- 若该 session 已在内存缓存：直接复用
- 若不在缓存：
  - 会创建 `conversation_histories[session_id] = []`
  - 若 `initial_history` 非空且当前缓存为空，则进行一次性“补种”
  - `initial_history` 会通过 `_normalize_history` 过滤/清洗（仅允许 user/assistant，content 不能为空）并截断到 `_max_messages_per_session`

### 4.2 SSE 流式“done 事件”可靠发送

前端流式消费逻辑依赖 `event: done` 来：

- flush 文本
- 设置 `assistant_message_id`
- 结束 streaming 状态

#### 4.2.1 事件类型（assistant -> router -> frontend）

`assistant.chat_stream` 产出事件：

- `session`：`{"session_id": "..."}`
- `references`：`{"references": [LawReference...]}`
- `content`：`{"text": "..."}`（片段）
- `done`：`{"session_id": "..."}`（assistant 内部会发）

router 的 SSE 格式：

- 每条事件写为：
  - `event: <type>`
  - `data: <json>`
  - 空行分隔

#### 4.2.2 router 保底 done

在 `/api/ai/chat/stream` 的 `event_generator()` 中：

- streaming 阶段无论是否捕获到 assistant 的 `done`，最终都会构造并 `yield` 一个 `event: done`
- `final_done` 字段：
  - `session_id`: 一定包含
  - `assistant_message_id`: 若成功落库 AI 消息
  - `persist_error`: 若发生异常
    - `stream_failed`：流式生成阶段异常
    - `persist_failed`：落库阶段异常

并设置了 SSE 响应头：

- `Cache-Control: no-cache`
- `Connection: keep-alive`
- `X-Accel-Buffering: no`
- `Content-Encoding: identity`

### 4.3 权限控制与游客配额

#### 4.3.1 登录用户会话权限

- 若会话属于某个 `user_id`：
  - `/api/ai/chat` 和 `_load_seed_history` 会在调用 assistant 前抛 `403`
  - `/api/ai/consultations/*`、`/export`、`/delete`、`/messages/rate` 都要求 owner

#### 4.3.2 游客配额（IP 维度）

- 常量：
  - `GUEST_AI_LIMIT = 5`
  - `GUEST_AI_WINDOW_SECONDS = 24h`
- 生效点：
  - `/api/ai/chat`、`/api/ai/chat/stream` 在 `current_user is None` 时执行 `_enforce_guest_ai_quota(request)`
- 返回：`429` + headers
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining`
  - `X-RateLimit-Reset`
  - `Retry-After`

注意：前端本地也有一套 localStorage 计数，但后端以自己的限流为准。

### 4.4 落库策略（chat vs stream）

#### 4.4.1 `/api/ai/chat`（同步）

- 调用 assistant 得到：`session_id, answer, references`
- 确认/创建 Consultation：
  - 若不存在则创建
  - 已登录用户遇到 `consultation.user_id is None` 会补绑到当前用户
- 创建两条 ChatMessage：
  - user message（role=`user`）
  - assistant message（role=`assistant`，带 `references` JSON）
- 返回：`ChatResponse`，包含 `assistant_message_id`

#### 4.4.2 `/api/ai/chat/stream`（流式）

- streaming 阶段收集：
  - `session_id`
  - `references_payload`
  - `answer_parts`（拼接为最终全文）
- streaming 结束后统一落库：
  - 创建/更新 Consultation
  - 创建 user message
  - 创建 assistant message（全文 + references JSON）
  - commit
- 最终保证发送 `event: done`

### 4.5 测试覆盖（backend/tests/test_api.py）

新增用例：`TestAIConsultationAPI.test_ai_chat_seeds_history_and_enforces_permission`

验证点：

- 创建 u1/u2 两个用户，构造 u1 的 Consultation + 2 条历史消息
- monkeypatch `ai_router.settings.openai_api_key = "test"` 使接口可用
- monkeypatch `_try_get_ai_assistant()`：
  - 用 FakeAssistant 断言 `initial_history` 真实传入且包含历史
- u1 请求 `/api/ai/chat`：返回 200
- u2 请求同一个 session：返回 403，且确保不会调用 assistant

测试结果：后端 pytest 已验证通过（`51 passed`）。

### 4.6 统一错误码 / request_id / 审计日志 / 运维 metrics（可观测性增强）

已对 AI 相关接口补齐统一的可观测性能力，用于快速关联线上问题与定位失败原因：

- `/api/ai/chat` 与 `/api/ai/chat/stream`：
  - 每个请求生成 `request_id`，并通过响应头 `X-Request-Id` 返回
  - 错误响应统一返回 `error_code`（同时放在响应体与 `X-Error-Code` 头）
  - 关键路径写入结构化 audit 日志（包含 endpoint/session_id/user_id/request_id 等）
- in-process metrics：
  - 记录 `chat`/`chat_stream` 请求计数
  - 记录错误计数与 recent errors 环形缓冲
  - 聚合错误分布：按 `error_code` 与 `endpoint` 统计 Top N
- 新增运维接口：`GET /api/system/ai/status`（admin），用于前端管理后台展示概览与最近错误

## 5. 前端对接现状（frontend/src/pages/ChatPage.tsx）

### 5.1 会话载入

- URL query `?session=<sid>` 存在时：
  - GET `/api/ai/consultations/{sid}`
  - 将返回的 `messages[].references`（字符串）JSON.parse 成数组供 UI 展示

### 5.2 流式发送与解析

- POST `/api/ai/chat/stream`，body：`{ message, session_id }`
- SSE 解析事件：
  - `session`：更新 `currentSessionId`
  - `references`：更新 assistant message 的 `references`
  - `content`：按帧累积文本（requestAnimationFrame 进行节流刷新）
  - `done`：flush 文本 + 写入 `assistant_message_id`

### 5.3 错误处理

- `401`：清 token，提示重新登录
- `429`：游客模式同步本地配额（并尝试读取 `X-RateLimit-Reset`）
- 其他错误：
  - 先在 UI 中写入错误提示
  - 再 fallback 调用非流式 `/api/ai/chat`

## 6. 配置依赖与运行条件

AI 咨询服务可用的关键条件：

- `OPENAI_API_KEY` 必须配置（后端在 `/ai/chat` 与 `/ai/chat/stream` 会检查，否则 503）
- 可选：`OPENAI_BASE_URL`（使用 OpenAI 兼容 API 时常用）
- 向量库目录：`settings.chroma_persist_dir`（例如 `./chroma_db`）
- 模型：`settings.ai_model`（例如 `deepseek-chat`）

## 7. 已知限制 / 风险点（当前现状）

### 7.1 RAG 可信度与可控性

- 当前只做了 `k=5` 的相似度检索 + 拼接 context
- 缺少：
  - 检索结果质量打分阈值/拒答策略
  - 引用法条的“可验证引用”（现在主要靠提示词约束）
  - 对“引用来源/条款编号”更强的结构化保障

### 7.2 SSE 语义

- 后端保证最终 `done`，但当前 `done` 中的 `persist_error` 前端未显式展示/处理（仅用于不挂起）。

### 7.3 可观测性

- 已具备：
  - request_id（`X-Request-Id` + 日志关联）
  - 统一错误码（`error_code` / `X-Error-Code`）
  - in-process metrics + admin 运维状态接口（`/api/system/ai/status`）
- 仍可继续增强：
  - 模型调用耗时细分、token 估算/成本统计
  - 检索命中数/score 分布与“拒答阈值”指标
  - 失败原因分层（上游超时、模型返回异常、落库失败等）与重试/熔断策略

### 7.4 多实例一致性

- assistant 仍有内存缓存（`conversation_histories`）。
- 在多实例部署下：
  - 同一 session 可能落到不同实例，需要依赖“DB 注入”来恢复上下文
  - 仍建议后续把 “会话记忆” 完全以 DB 为准（或引入共享缓存）

## 8. 附：接口行为摘要

### 8.1 POST /api/ai/chat

- 入参：`{ message: string, session_id?: string }`
- 登录：绑定到用户；游客：允许但受配额限制
- 出参：`{ session_id, answer, references, assistant_message_id, created_at }`

### 8.2 POST /api/ai/chat/stream

- SSE 事件：`session` / `references` / `content` / `done`
- 保底：最终必出 `done`

### 8.3 GET /api/ai/consultations

- 登录必需
- 返回咨询列表（含消息数）

### 8.4 GET /api/ai/consultations/{session_id}

- 登录必需 + owner 校验
- 返回消息列表（`references` 为 JSON 字符串）

### 8.5 DELETE /api/ai/consultations/{session_id}

- 登录必需 + owner 校验
- 删除 DB 记录，并尝试调用 `assistant.clear_session(session_id)` 清理内存

### 8.6 GET /api/ai/consultations/{session_id}/export

- 登录必需 + owner 校验
- 返回结构化数据（供前端生成 PDF 等）

### 8.7 POST /api/ai/messages/rate

- 登录必需 + owner 校验
- 仅允许对 role=assistant 的消息评价

### 8.8 GET /api/system/ai/status（admin）

- 用途：管理后台展示 AI 咨询运维状态（配置是否就绪、请求量、错误分布、最近错误）。
- 鉴权：仅管理员可访问。
- 主要字段（示意）：
  - `ai_router_enabled: bool`
  - `openai_api_key_configured: bool`
  - `chat_requests_total: int`
  - `chat_stream_requests_total: int`
  - `errors_total: int`
  - `recent_errors: [{ at, request_id, endpoint, error_code, status_code?, message? }]`
  - `top_error_codes: [{ error_code, count }]`
  - `top_endpoints: [{ endpoint, count }]`

## 9. 后续计划（待补充）

请在你确定下一阶段目标后，将计划追加到本节，例如：

- RAG 可控性：引用校验、阈值拒答、来源可追溯
- 观测：统一日志字段、metrics、慢请求与错误聚合
- 成本：token 预算、缓存、模型路由
- 稳定：重试、超时、取消、SSE keepalive
- 测试：补充 stream 测试、权限/限流边界测试
