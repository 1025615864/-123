# 代码审计报告（Tech Debt / Security / TODO）

> 本审计以静态阅读为主，覆盖：技术债/坏味道、安全隐患、TODO/未完成项与改进建议。引用的文件路径均来自当前仓库。

---

## 1. 技术债务与代码坏味道

### 1.1 数据库迁移策略混用（长期风险）

- **现状**：
  - `backend/app/database.py::init_db()` 使用 `Base.metadata.create_all()` 并包含大量 SQLite/PG 的“自修复”DDL（补列/补索引/更新 cents 字段等）。
  - Alembic 迁移目录存在，但 `versions/` 中 migration 数量有限。
- **风险**：
  - 结构演进不完全可追溯，容易出现“开发库 OK、生产库漂移”的情况。
  - `create_all` 会掩盖缺迁移的问题。
- **建议**：
  - 将所有结构变更固化到 Alembic migration。
  - `init_db()` 仅保留最小兜底（例如首次建库或极少量兼容补丁），并逐步削减。

### 1.2 内存限流器在生产多副本下不一致

- **现状**：`backend/app/utils/rate_limiter.py` 使用进程内内存滑动窗口。
- **风险**：
  - 多实例部署时每个实例独立计数，整体限流失真。
  - 进程重启会清空计数。
- **建议**：
  - 生产环境将限流迁移到 Redis（基于 INCR + EXPIRE 或 Lua 滑窗），或接入 API Gateway。

### 1.3 代码风格不统一（ORM 写法混杂）

- **现状**：
  - 大多数模型使用 SQLAlchemy 2.0 `Mapped/mapped_column`。
  - `backend/app/models/consultation.py` 使用旧式 `Column(...)`。
- **风险**：可维护性下降；静态检查/一致性降低。
- **建议**：统一迁移到 SQLAlchemy 2.x typed ORM 写法。

### 1.4 N+1 查询风险（性能）

- **现状**：部分列表接口在循环中进行额外查询（例如某些列表里统计字段、related_user_name 解析）。
- **建议**：
  - 对列表接口增加 join/子查询聚合
  - 使用 `selectinload/joinedload` 统一解决 N+1
  - 对热点接口增加缓存（或完善现有缓存策略）

---

## 2. 安全性隐患与风险点

### 2.1 默认弱密钥/示例口令（仅应存在于示例文件）

- `backend/app/config.py`：`secret_key` 有默认值 `your-super-secret-key-change-in-production`。
  - 好的一点：当 `DEBUG=false` 时强制校验密钥长度与安全性。
- `docker-compose.yml`：
  - DB 密码 `postgres123`
  - JWT key 为示例
- **建议**：
  - 明确标注这些仅用于本地演示，并在文档中强调生产替换。
  - 生产部署（Helm/Compose prod）只通过 Secret 注入。

### 2.2 回调接口暴露面与安全审计

- 已实现：
  - `payment_callback_events` 表做回调审计（provider+trade_no 唯一）。
  - 支付宝 RSA2、Ikunpay MD5 的验签与金额校验。
- 建议加强：
  - 对回调接口加“幂等锁/事务幂等保证”（当前通过订单状态与 unique index 已一定程度覆盖）。
  - 记录更多上下文（如来源 IP、User-Agent、原始 query/form hash）用于风控。

### 2.3 文件上传安全

- `backend/app/routers/upload.py` 已做：
  - 限制 content-type
  - 魔数检测（jpeg/png/gif/webp）
  - 文件名白名单校验（avatar/image/file）
- 风险与建议：
  - 当前写入本地磁盘：生产多副本下需共享存储或对象存储（S3/OSS）。
  - 可增加病毒扫描/内容安全检查（尤其是附件）。
  - 统一对上传接口做 rate limit（目前主要靠登录校验）。

### 2.4 “SystemConfig 禁止 secrets 入库”是亮点，但需持续保持

- `backend/app/routers/system.py` 对 key/value 做敏感校验与脱敏返回。
- 建议：
  - 增加单元测试覆盖：确保新增配置项不会误入库。
  - 对管理后台页面也做提示（UI 层），避免运营误操作。

---

## 3. TODO / 未完成项标记

- 本次扫描未在核心代码中发现大量 `TODO/FIXME`（主要命中在文档与任务追踪文件）。
- `TASKS.md` 中存在迭代计划与未完成事项（属于产品/交付层面的 TODO）。

建议：

- 将“关键未完成能力（例如微信支付未开放）”在用户侧与管理侧都做显式灰度与提示。

---

## 4. 具体可执行的改进建议（按优先级）

### P0（安全/一致性）

- 将生产限流迁移到 Redis/网关层，避免多副本失效。
- 将 DB 演进彻底迁移到 Alembic：
  - 为 `init_db()` 中的补列/补索引梳理出迁移脚本
  - 保留最小兼容补丁后逐步移除

### P1（可维护性）

- 统一 ORM 写法（Typed ORM）。
- 将部分路由文件（如 `payment.py`、`news.py`、`forum.py`）按子域再拆分（降低单文件体积）。

### P2（性能/可观测）

- 对热点列表接口消除 N+1；增加 Explain/索引检查。
- 增强指标：
  - 业务维度 metrics（支付成功率、回调失败原因 TopN、News AI pipeline 成功率）

---

## 5. 风险结论（给专家的 TL;DR）

- **总体风险可控**：鉴权、支付回调验签、secrets 不入库等有明确实现。
- **主要技术债集中在“DB 迁移策略混用”与“内存限流不适合多副本”**：建议优先收敛。
