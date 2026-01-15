# 模块文档索引（modules/）

本目录用于存放“开发者视角”的模块级文档。

每个模块文档通常会回答这些问题：

- 模块边界：负责什么、不负责什么
- 关键 API：路由入口与权限边界
- 关键数据：表/字段/状态机/去重键
- 关键链路：请求 → DB → 通知/WS → 前端刷新
- 常见坑：联调/线上排障时最容易踩的点

如果你是第一次读这个仓库，推荐阅读顺序：

1. 架构总览：`docs/ARCHITECTURE.md`
2. 模块地图（本页）：`docs/modules/INDEX.md`
3. 端到端数据流：`docs/modules/DATA_FLOWS.md`
4. 数据模型：`docs/DATA_MODEL.md`
5. API 速查：`docs/guides/API_QUICK_REFERENCE.md`

---

## 模块地图（按领域分组）

### A. 基础设施与横切能力（强烈建议先看）

- `docs/modules/BACKEND_INFRA.md`
  - 后端工程化/中间件/周期任务（PeriodicLockedRunner）/运行时约束
- `docs/modules/FRONTEND_ARCH.md`
  - 前端路由、React Query、WS 连接与缓存刷新策略
- `docs/modules/DATA_FLOWS.md`
  - 端到端链路：请求 → DB → 通知/WS → 前端刷新（排障时优先看这里）
- `docs/modules/SYSTEM_CONFIG.md`
  - SystemConfig（DB）与 env 的优先级、可配置项与安全约束
- `docs/modules/NOTIFICATIONS.md`
  - 通知数据模型、去重键、管理员广播、WS 推送与前端刷新条件
- `docs/modules/UPLOAD_STORAGE.md`
  - 上传 API、local/S3 存储、URL 约定与安全边界

### B. 内容与社区（用户侧高频）

- `docs/modules/NEWS_AI.md`
  - 新闻与 News AI：采集/标注/风控/去重的关键行为
- `docs/modules/FORUM.md`
  - 论坛：帖子/评论/审核/批量审核与通知
- `docs/modules/SEARCH.md`
  - 搜索：全局聚合搜索与历史记录

### C. 法律服务履约（咨询 → 复核 → 结算）

- `docs/modules/CONSULTATION.md`
  - AI 咨询 + 律师咨询预约：主流程、权限、会话/消息落库
- `docs/modules/REVIEWS_SLA.md`
  - 律师复核任务：状态机、SLA 计算、催办通知与 WS 推送

### D. 支付与结算（资金链路）

- `docs/modules/PAYMENT.md`
  - 支付订单、回调验签/审计、对账诊断、管理员运维入口
- `docs/modules/SETTLEMENT.md`
  - 律师钱包、冻结期结算、提现审批与收入记录分摊

### E. 内容生产工具与运营模块

- `docs/modules/DOCUMENTS.md`
  - 文书生成（含导出/报告）
- `docs/modules/DOCUMENT_TEMPLATES.md`
  - 文书模板管理（版本与发布）
- `docs/modules/CONTRACTS.md`
  - 合同审查
- `docs/modules/KNOWLEDGE.md`
  - 知识库（管理侧导入/向量化/同步）
- `docs/modules/CALENDAR.md`
  - 法律日历
- `docs/modules/FEEDBACK.md`
  - 客服反馈与工单
- `docs/modules/ADMIN_CONSOLE.md`
  - 管理后台统计与导出

---

## 常见阅读路线（按你的目标）

### 1) 我想快速上手跑通业务主链路

- 先看：`docs/modules/DATA_FLOWS.md`
- 再看：`docs/modules/PAYMENT.md`、`docs/modules/SETTLEMENT.md`、`docs/modules/REVIEWS_SLA.md`

### 2) 我在排查“通知没刷新/WS 有消息但 UI 不变”

- 先看：`docs/modules/NOTIFICATIONS.md`
- 再看：`docs/modules/DATA_FLOWS.md`（通知链路章节）
- 对照前端：`docs/modules/FRONTEND_ARCH.md`

### 3) 我在排查“支付回调来了但订单没变 paid”

- 先看：`docs/modules/PAYMENT.md`
- 再看排障：`docs/guides/TROUBLESHOOTING.md`

### 4) 我在排查“提现完成了但收入记录分摊不对”

- 先看：`docs/modules/SETTLEMENT.md`
- 再看：`docs/DATA_MODEL.md`（Settlement 相关表字段）
