# 开发任务（NEXT）

> 说明：这是当前进行中的任务清单（滚动迭代）。历史任务快照见：`docs/_archive/TASKS_2026-01-13.md`。

## 0. 当前里程碑（P0/P1）

- [x] 生产部署演练（按 Helm/Compose 任一口径走通一次）

  - [x] 演练：备份 -> 迁移（`alembic upgrade head`）-> 滚动发布 -> post-deploy smoke
  - [x] 验收：完整演练记录写入 `docs/_archive/`（含命令、日志、结论）

  - 已做：演练归档：`docs/_archive/PROD_DEPLOY_DRILL_2026-01-13.md`
  - 已做：冒烟：`GET http://localhost/api/health` -> `200 OK`
  - 已做：迁移：`alembic current/heads` -> `d4f2c9a31b10 (head)`
  - 已做：备份产物：`backend/backups/postgres_deploy_drill_20260113_042822.dump`

- [x] 文档体系“权威入口”再对齐一次（避免口径漂移）

  - [x] 验收：`README.md` / `docs/README.md` / `docs/核心文档清单/*` / `docs/TECH_SPEC.md` / `docs/DATABASE.md` 互链无断链

  - 已做：互链审计归档：`docs/_archive/DOC_LINK_AUDIT_2026-01-13.md`（排除 `node_modules/.venv` 后 0 断链）

## 1. 稳定性与质量（P1）

- [x] Playwright E2E 扩展：覆盖 1 条“支付失败/取消”路径（mock 或沙箱）

  - [x] 已做：扩展 `frontend/tests/e2e/payment-return.spec.ts`
    - 失败状态（mock）：`支付回跳页：失败状态展示与引导（mock）`
    - 取消路径（真实后端）：`payment: 创建订单后取消-回跳页展示 cancelled（E2E）`
  - [x] 验证：本地 `npm --prefix frontend run test:e2e -- --grep "payment:|支付回跳页"` 通过（4 passed）

- [x] 后端性能基线（最小版）

  - [x] 指标：关键接口 P95（chat、documents、payment callback、news ingest admin）
  - [x] 已做：归档报告：`docs/_archive/PERF_BASELINE_2026-01-13.md`
  - [x] 已做：原始采样 JSON：`docs/_archive/PERF_BASELINE_2026-01-13.json`
  - [x] 已做：基线脚本：`backend/scripts/perf_baseline.py`

- [x] 协作规范：补齐项目角色划分与 Windsurf Workflows 入口

  - [x] 已做：新增 `docs/ROLES.md`（RACI/职责/交付物/质量门禁/Workflows）
  - [x] 已做：新增 `.windsurf/workflows/*`（`/project-roles`、`/role-backend` 等）
  - [x] 已做：更新入口互链：`README.md`、`docs/README.md`

- [x] 前端质量与交互：依赖安全基线 + Layout 菜单可用性修复

  - [x] 已做：`npm --prefix frontend audit` 清零（升级 `react-router-dom@7.12.0`）
  - [x] 已做：Layout 增强：`Esc` 关闭、点击空白处关闭、移动端菜单打开锁定背景滚动
  - [x] 已做：Hotfix i18n：缺失 key 回落中文；关键路径接入 `t()`（login/register/chat）
  - [x] 已做：i18n 覆盖扩展：`/`（Home）、`/forgot-password`、`/reset-password`、`/verify-email` 接入 `t()` 并补齐 `zh/en` key
  - [x] 已做：i18n 覆盖扩展：Layout footer 文案（简介/地址/版权）接入 `t()`，英文模式不再夹杂中文
  - [x] 已做：i18n 覆盖扩展：`/search`（SearchPage）、`/news`（NewsPage）、`/forum`（ForumPage）接入 `t()`
  - [x] 已做：i18n 词条补齐：补齐 `searchPage.*` / `newsPage.*` / `forumPage.*` 的 `zh/en` key（保持结构一致）
  - [x] 已做：i18n 覆盖扩展：`/news/:newsId`（NewsDetailPage）、`/forum/post/:postId`（PostDetailPage）接入 `t()`
  - [x] 已做：i18n 词条补齐：新增 `newsDetailPage.*` / `postDetailPage.*` 的 `zh/en` key（保持结构一致）
  - [x] 已做：i18n 覆盖扩展：`/news/topics`（NewsTopicsPage）、`/news/topics/:topicId`（NewsTopicDetailPage）接入 `t()`
  - [x] 已做：i18n 词条补齐：新增 `newsTopicsPage.*` / `newsTopicDetailPage.*` 的 `zh/en` key（保持结构一致）
  - [x] 已做：i18n 覆盖扩展：`/share/:token`（SharePage）接入 `t()`（含复制提示/空态/按钮/错误 fallback）
  - [x] 已做：i18n 词条补齐：新增 `sharePage.*` 的 `zh/en` key（保持结构一致）
  - [x] 已做：i18n 覆盖扩展：`/chat/history`（ChatHistoryPage）接入 `t()`（含导出/分享/删除/复核购买/空态/筛选）
  - [x] 已做：i18n 词条补齐：新增 `chatHistoryPage.*` 的 `zh/en` key（保持结构一致）
  - [x] 已做：i18n 覆盖扩展：`/documents`（DocumentGeneratorPage）接入 `t()`（含配额/步骤/表单/历史弹窗/复制下载/PDF 预览）
  - [x] 已做：i18n 覆盖扩展：`/contracts`（ContractReviewPage）接入 `t()`（含上传/配额/VIP 提示/复制下载/PDF 预览）
  - [x] 已做：i18n 词条补齐：新增 `documentGeneratorPage.*` / `contractReviewPage.*` 的 `zh/en` key（含 `common.unlimited/vip/nonVip/refresh/refreshing/view`）
  - [x] 已做：Hotfix 语音输入：MediaRecorder mimeType 兼容、stop 前 requestData、更清晰错误提示
  - [x] 已做：Hotfix 语音可用性检测：新增 `/system/public/ai/status`（不需管理员权限），ChatPage 根据状态禁用语音按钮并提示；E2E mock 覆盖
  - [x] 已做：E2E：Playwright 默认 `locale: zh-CN`，避免 i18n 导致文案漂移
  - [x] 已做：UI 一致性：`PageHeader` 防溢出与色系统一；Layout 全局 padding/留白节奏优化
  - [x] 已做：UI 一致性：全局 Loading（Suspense fallback）接入 i18n；Modal close aria-label 统一；Button 图标尺寸随 size 自适配
  - [x] 已做：UI 一致性：`/documents`（DocumentGeneratorPage）步骤指示器可换行、配额展示分隔符统一、结果区/详情按钮组可换行并统一 icon 用法
  - [x] 已做：UI 一致性：`/contracts`（ContractReviewPage）文件操作按钮组可换行，提升小屏可用性
  - [x] 已做：计划文档：`docs/PLAN_FRONTEND_2026-01-13.md`
  - [x] 验证：`npm --prefix frontend run build` 通过
  - [x] 验证：`npm --prefix frontend run test:e2e -- --grep chat-voice-input` 通过

## 2. 运维与安全（P1）

- [x] 数据库运维：制定“备份保留策略”与“恢复演练周期”并固化（计划/责任人/频率）

  - [x] 已做：更新 `docs/DATABASE.md`（补充保留策略建议 + drill 周期建议）
  - [x] 已做：归档 drill 报告：`docs/_archive/DB_DRILL_REPORT_2026-01-13.md`

- [x] Secrets 轮换与最小权限
  - [x] 已做：归档 runbook：`docs/_archive/SECRETS_ROTATION_RUNBOOK_2026-01-13.md`

## 3. 产品迭代（P2，候选池）

- [x] 运营增长：专题页 SEO 加强（结构化数据/更多 OG/更完善 sitemap）
  - [x] 已做：`/news/topics`（NewsTopicsPage）补齐 canonical / Twitter card / OG image，并添加 JSON-LD（CollectionPage + BreadcrumbList）
  - [x] 已做：`/news/topics/:topicId`（NewsTopicDetailPage）补齐 canonical / Twitter card / OG image，并添加 JSON-LD（CollectionPage + BreadcrumbList）
  - [x] 已做：后端 `/sitemap.xml` 动态追加 `/news/topics/:id` 与 `/news/:id`（限量），失败自动降级为静态 sitemap
- [x] 合同审查：条款库/风险库可配置化（SystemConfig 非敏感项）
  - [x] 已做：新增 SystemConfig `CONTRACT_REVIEW_RULES_JSON`（后台 Settings -> AI 可编辑，JSON 校验）
  - [x] 已做：合同审查 `/contracts/review` 读取规则 JSON 注入 prompt
  - [x] 已做：对 AI 输出做确定性合并（required_clauses / risk_keywords），保证配置立即生效且可控
- [x] 律师复核：工单 SLA / 超时策略 / 自动催办

  - [x] 已做：复核任务接口动态计算 `due_at/is_overdue`（不改数据库结构）
  - [x] 已做：后台 Settings 增加 `CONSULT_REVIEW_SLA_JSON`（JSON 校验）
  - [x] 已做：后端周期任务扫描待处理/处理中任务并发送去重系统通知（Notification `dedupe_key`）
    - 通知跳转：`/lawyer?tab=reviews`
    - env 开关：`REVIEW_TASK_SLA_JOB_ENABLED=1`
    - env 间隔：`REVIEW_TASK_SLA_SCAN_INTERVAL_SECONDS=60`
    - 实时推送：写库后通过 WebSocket 推送 `notification`（在线用户即时刷新铃铛/列表）
  - [x] 已做：律师工作台支持 `tab=reviews` URL 参数，便于通知直达“复核任务”Tab

---

## 变更记录

- 2026-01-13：创建 `TASKS_NEXT.md`，用于承接后续迭代任务（上一版快照见 `docs/_archive/TASKS_2026-01-13.md`）。
- 2026-01-13：补齐项目角色划分与 Windsurf Workflows（`docs/ROLES.md` + `.windsurf/workflows/*`），并更新文档入口互链。
- 2026-01-13：前端质量与布局优化：修复 npm audit（升级 `react-router-dom@7.12.0`）+ Layout 菜单交互增强；计划归档 `docs/PLAN_FRONTEND_2026-01-13.md`。
- 2026-01-13：Hotfix：翻译系统（i18n 关键路径接入 + fallback）与语音输入（MediaRecorder 兼容增强）；E2E locale 固定。
- 2026-01-13：i18n 覆盖扩展（Home/Forgot/Reset/Verify + footer），以及 PageHeader/Layout 全局视觉节奏一致性优化；build 回归通过。
- 2026-01-13：Hotfix：语音可用性检测（public AI status + ChatPage 禁用/提示 + E2E mock），build 与语音用例回归通过。
- 2026-01-13：i18n 覆盖扩展（Search/News/Forum）接入 `t()` 并补齐 `zh/en` 词条；build 回归通过。
- 2026-01-13：i18n 覆盖扩展（NewsDetail/PostDetail）接入 `t()` 并补齐 `zh/en` 词条；build 回归通过。
- 2026-01-13：i18n 覆盖扩展（NewsTopics/NewsTopicDetail）接入 `t()` 并补齐 `zh/en` 词条；build 回归通过。
- 2026-01-13：i18n 覆盖扩展（SharePage）接入 `t()` 并补齐 `zh/en` 词条；build 回归通过。
- 2026-01-13：i18n 覆盖扩展（ChatHistoryPage）接入 `t()` 并补齐 `zh/en` 词条；build 回归通过。
- 2026-01-13：i18n 覆盖扩展（DocumentGeneratorPage/ContractReviewPage）接入 `t()` 并补齐 `zh/en` 词条；build 回归通过。
- 2026-01-13：UI 一致性补强：Layout/Modal/Button/PageHeader 与 `/documents`、`/contracts` 关键交互的密度/按钮组/可换行策略统一；build 回归通过。
- 2026-01-13：专题页 SEO 加强：`/news/topics` & `/news/topics/:id` 增强 OG/Twitter/canonical/JSON-LD；后端 sitemap 动态追加 topics/news。
- 2026-01-13：合同审查可配置化：SystemConfig `CONTRACT_REVIEW_RULES_JSON` 管理条款库/风险库（prompt 注入 + 规则确定性合并）。
- 2026-01-13：律师复核 SLA：API 动态输出 `due_at/is_overdue` + 后台可配置 `CONSULT_REVIEW_SLA_JSON` + 周期任务自动催办（去重通知跳转 `/lawyer?tab=reviews`）。
