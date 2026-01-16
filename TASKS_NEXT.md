# TASKS_NEXT（当前迭代）

## 本迭代目标：文档体系补齐（基于现有代码与配置）

- [x] 建立根 `README.md`（项目简介、启动方式、关键约定、文档入口）
- [x] 建立 `docs/` 文档体系（架构 / 数据库 / 开发指南 / API 速查 / 运维）
- [x] 修正 Helm README 中的文档/脚本引用，确保互链不悬空
- [x] 补齐 `backend/README.md`、`frontend/README.md`
- [x] 补齐发布需要的 `docs/CHANGELOG.md`（用于 GitHub Release workflow）

## 建议后续迭代（待评估）

- [x] 生产反向代理补齐 WebSocket `/ws` 路径（Nginx / Ingress）并补运维说明
- [x] 补齐 post-deploy smoke 脚本与 Runbook（对齐 `.github/workflows/post-deploy-smoke.yml`）

## 当前工作：开发者视角文档深度化（进行中）

- [x] 补齐模块级文档（`docs/modules/*`）并在主文档互链（ARCHITECTURE/README）
- [x] 修正文档一致性（章节编号/模块顺序/互链）并做一次全局校验
- [x] 逐模块补齐数据流与关键表（forum/news/payment/settlement/notifications/reviews/consultation）
- [x] 补齐前端开发者文档（路由、React Query、WebSocket、鉴权与错误处理约定）
- [x] 补齐“开发者排障手册”与“配置参考”（env + SystemConfig + 生产约束）
- [x] 文档互链与目录检查（避免悬空链接）
- [x] 为核心链路补齐“端到端数据流”说明（请求->DB->通知/WS->前端缓存刷新）与关键表映射
- [x] 端到端数据流补强：补齐支付 pay_order 与复核提交->结算入账的耦合链路（DATA_FLOWS）
- [x] 继续扩写各业务模块的“关键表字段/状态机”与“边界条件”（尤其是 payment/settlement/reviews）
- [x] 深挖支付/结算/复核文档：补齐 pay_order 边界条件、余额扣款原子性、回调审计策略、对账诊断与提现分摊规则
- [x] 补齐补充模块文档（documents/document-templates/contracts/knowledge/calendar/feedback/admin-console）并接入导航
- [x] 补齐 API 速查（通知/结算提现关键接口）并对齐后端路由

## 2026-01-16 WIP（stash）拆分与回收进度

说明：在 `main` 已合并 docs 后，从本地 stash 中拆分出可合并的最小变更并单独提交，便于 review / 回滚。

- [x] `544f928` chore(dev): add start-dev scripts and ignore test-results
- [x] `186b820` feat(ai): add voice transcribe providers and sherpa support
- [x] `1514fd7` docs(config): document voice transcribe and sherpa env/systemconfig keys
- [x] `90796b0` test(e2e): add chat history sidebar draft retention spec
- [x] PR：https://github.com/1025615864/-123/pull/37

暂不回收：

- `stash@{2}`：前端大规模重写（包含 i18n/WS 行为变更与 E2E helpers 默认凭据硬编码），暂不合并，后续需要单独评审与拆分。

门禁结果：

- [x] backend：`py -m pytest -q`
- [x] frontend：`npm --prefix frontend run build`

## 自动执行计划（后续按顺序依次执行，不再逐步询问确认）

说明：以下为“可交付的文档增强”计划，每一项都包含：

- 交付物（会改哪些文档）
- 验收标准（完成到什么程度算过）
- 校验方式（互链校验/一致性检查）

### A. 数据模型补齐（以 `backend/app/models/*` 为准）

- [x] A1 扩写 `docs/DATA_MODEL.md`：支付域（Payment）

  - 交付物：补齐 `payment_orders/user_balances/balance_transactions/payment_callback_events` 的关键字段、唯一约束、金额正负语义、与订单/回调/余额的关系
  - 验收：开发者能仅凭 DATA_MODEL + PAYMENT 模块文档定位“订单/回调/余额流水”三者的落库点与主键/唯一键

- [x] A2 扩写 `docs/DATA_MODEL.md`：结算域（Settlement）

  - 交付物：补齐 `lawyer_wallets/lawyer_income_records/lawyer_bank_accounts/withdrawal_requests` 的关键字段、状态机、与 service 的一致性约束
  - 验收：开发者能从表字段推导出“pending/settled/withdrawn”与“pending/approved/rejected/completed/failed”的业务含义

- [x] A3 扩写 `docs/DATA_MODEL.md`：复核域（Reviews）

  - 交付物：补齐 `consultation_review_tasks/consultation_review_versions` 的关键字段、唯一约束、与 payment order 的绑定关系
  - 验收：开发者能定位“谁创建 task、谁提交 version、如何去重、如何和结算入账联动”

- [x] A4 扩写 `docs/DATA_MODEL.md`：通知域（Notifications）
  - 交付物：补齐 `notifications` 的字段语义、dedupe_key 语义、WebSocket 推送触发点
  - 验收：开发者能定位“为什么通知没插入/为什么重复/为什么 WS 没推送”

### B. 端到端数据流补齐（请求 →DB→ 通知/WS→ 前端刷新）

- [x] B1 扩写 `docs/modules/DATA_FLOWS.md`：论坛审核/通知链路（forum -> notifications）

  - 交付物：补齐“发帖/评论->审核->通知->WS->前端刷新”的关键表与状态
  - 验收：能明确指出哪些 API 写哪些表，哪些动作会触发通知/WS

- [x] B2 扩写 `docs/modules/DATA_FLOWS.md`：News / News AI 链路

  - 交付物：补齐“采集/发布/下架/News AI pipeline”主要任务与关键表落点（以代码为准）
  - 验收：能定位 pipeline 的 job、锁 key、写库点、常见失败点

- [x] B3 扩写 `docs/modules/DATA_FLOWS.md`：通知模块链路（broadcast/system/WS）
  - 交付物：补齐“插入通知->去重->WS 推送->前端 invalidate”的全链路
  - 验收：能明确 dedupe_key 设计与前端缓存刷新点

### C. 排障手册补齐（面向线上/联调常见故障）

- [x] C1 扩写 `docs/guides/TROUBLESHOOTING.md`：支付常见问题

  - 交付物：补齐“回调验签失败/回调重复/订单已 paid 但无成功回调/余额扣款失败/对账诊断”等
  - 验收：按文档步骤可复现定位到 `payment_callback_events` 或 reconcile diagnosis

- [x] C2 扩写 `docs/guides/TROUBLESHOOTING.md`：结算/提现常见问题
  - 交付物：补齐“结算 job 未跑/冻结期不结算/提现金额与 wallet 对不上/提现完成但 income_records 未分摊”等
  - 验收：按文档步骤可定位到 `withdrawal_requests`/`lawyer_wallets`/`lawyer_income_records`

### D. 文档一致性与自动校验

- [x] D1 对齐模块文档一致性（索引/章节/路由前缀/命名）

  - 交付物：确保 `ARCHITECTURE.md`、`modules/INDEX.md`、`API_QUICK_REFERENCE.md`、各模块文档互相一致
  - 验收：不存在“同一概念多种命名/同一接口多处不一致”

- [x] D2 全库互链校验（自动脚本）
  - 校验方式：执行仓库内的 Markdown link target 校验（py 脚本）

### E. 任务归档

- [x] E1 归档快照
  - 交付物：将当前迭代 `TASKS_NEXT.md` 快照归档到 `docs/_archive/TASKS_YYYY-MM-DD.md`
  - 验收：`TASKS.md` 仍为入口索引，历史可追溯

## 2026-01-16 收尾计划（一次性全部完成）

说明：本段为本轮继续推进的“收尾闭环”计划（以代码为准），完成后本迭代可视为文档深度化交付完毕。

### F. 模块文档再对齐（补齐关键不变量/边界条件清单）

- [x] F1 对齐 `docs/modules/PAYMENT.md`

  - 交付物：补齐“幂等/锁/回调审计唯一约束/运维入口”清单
  - 验收：开发者能回答“为何失败回调不写 trade_no”“为何 webhook 不加锁也可幂等”“env 热更新受哪些白名单约束”

- [x] F2 对齐 `docs/modules/SETTLEMENT.md`

  - 交付物：补齐“钱包字段不变量/分摊 best-effort/任务锁与开关”清单
  - 验收：开发者能回答“为何提现完成但分摊可能失败仍算完成”“钱包字段为何以重算为准”

- [x] F3 对齐 `docs/modules/REVIEWS_SLA.md`

  - 交付物：补齐“扫描范围边界/去重键与配置变更的影响/SQLite 推送语义差异”清单
  - 验收：开发者能回答“为何未领取任务不提醒”“为何 SLA 配置变更后可能产生新的提醒”

- [x] F4 对齐 `docs/modules/NOTIFICATIONS.md` + `docs/guides/API_QUICK_REFERENCE.md`
  - 交付物：补齐“WS message type 与前端刷新点”的注意事项
  - 验收：开发者能回答“为何 admin broadcast WS 发了但 bell 不刷新”

### G. 自动校验与归档

- [x] G1 全库互链校验（自动脚本）

  - 校验方式：执行仓库内的 Markdown link target 校验（py 脚本）
  - 验收：输出 `OK`

- [x] G2 归档快照（2026-01-16）
  - 交付物：`docs/_archive/TASKS_2026-01-16.md`
  - 验收：快照内容与当前 `TASKS_NEXT.md` 一致，可用于回溯
