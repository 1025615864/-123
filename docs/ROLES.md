# 项目角色划分（RACI + 交付物）

更新时间：2026-01-13

本文件用于把“谁负责什么、产出什么、如何协作、如何验收”的口径一次性讲清楚，避免在全方位开发时发生职责重叠/缺口。

关联入口：

- 需求口径：`docs/PRD.md`
- 技术口径：`docs/TECH_SPEC.md`
- 接口口径：`docs/API_DESIGN.md`（以 Swagger 为权威）
- 数据口径：`docs/DATABASE.md`（以 SQLAlchemy models 为权威）
- 开发约束：`CLAUDE.md`
- 任务入口：`TASKS_NEXT.md`
- Windsurf Workflows：`.windsurf/workflows/*.md`（在 Cascade 中用 `/workflow-name` 调用）

---

## 1. 角色设计原则

- **单一责任 + 明确交付物**：每个角色都必须能用“输入/输出/门禁”描述。
- **代码为准（Source of Truth）**：文档服务于代码；当不一致时优先修正文档。
- **门禁前置**：每次变更必须明确需要通过的质量门禁（测试/构建/E2E/冒烟）。
- **跨域协作靠接口**：角色之间的协作以“接口（API/Schema/契约）+ 验收标准（DoD）”为主。

---

## 2. 角色清单与职责

### 2.1 产品负责人（PO/PM）

- **目标**
  - 保证功能价值与验收口径清晰，减少返工与“做了但不可验收”。
- **核心职责**
  - PRD 维护：范围/非范围、用户旅程、关键页面、边界条件。
  - 验收标准：每个功能必须有可执行的验收点（包含失败/异常路径）。
  - 需求拆解：将需求拆到可实现的子任务（前端/后端/数据/运维）。
- **主要交付物**
  - `docs/PRD.md` 的对应章节更新
  - `TASKS_NEXT.md` 的任务条目（P0/P1/P2 标注）
- **协作接口**
  - 与架构/技术负责人对齐：数据模型变化、权限模型、关键不变量
  - 与 QA 对齐：验收用例、回归范围
- **完成定义（DoD）**
  - PRD 明确：用户入口、核心流程、异常/回退、验收清单

### 2.2 技术负责人 / 架构师（Tech Lead/Architect）

- **目标**
  - 保障架构一致性与关键不变量（安全、可交付性、可回滚、可运维）。
- **核心职责**
  - 模块边界：API/服务层/模型层的职责划分与依赖方向。
  - 技术方案：关键链路（支付/鉴权/AI/RAG/News AI）的设计与演进策略。
  - 风险控制：迁移、兼容、性能、监控告警策略。
- **主要交付物**
  - `docs/TECH_SPEC.md`：约束/门禁/运行模式矩阵等
  - `docs/API_DESIGN.md`：模块拆分与关键接口说明
  - 必要时在 `docs/_archive/` 归档一次性分析报告
- **协作接口**
  - 对后端：数据模型/事务/幂等/一致性
  - 对前端：接口契约/错误码/空状态与重试策略
  - 对运维：部署/回滚/监控
- **完成定义（DoD）**
  - 关键不变量写入文档；变更影响面与回滚策略明确

### 2.3 后端负责人（Backend Owner）

- **目标**
  - 提供稳定、可演进、可测试的 API 与业务服务。
- **核心职责**
  - 路由层薄：参数校验/权限校验；业务逻辑在 `services/`。
  - 数据一致性：事务边界清晰；幂等/防重入。
  - 迁移门禁：生产口径下走 Alembic；避免破坏启动门禁。
- **主要交付物**
  - 代码：`backend/app/routers/*`、`backend/app/services/*`、`backend/app/models/*`
  - 测试：`backend/tests/*`
  - 必要时迁移：`backend/alembic/versions/*`
- **协作接口**
  - 与前端：OpenAPI/响应结构/分页/错误码
  - 与 QA：回归用例覆盖与可复现步骤
  - 与运维：环境变量、生产门禁与 runbook
- **完成定义（DoD）**
  - 新功能至少包含：接口实现 + 基础测试 + 文档口径更新

### 2.4 前端负责人（Frontend Owner）

- **目标**
  - 提供一致、可用、可回归的用户体验与管理后台体验。
- **核心职责**
  - 路由与页面：`frontend/src/App.tsx` 与 `pages/`。
  - API 调用统一：尽量收敛到 `frontend/src/hooks/useApi.ts`/`frontend/src/api/client.ts`。
  - 可用性：加载/错误/空状态/重试。
- **主要交付物**
  - 页面/组件/状态：`frontend/src/pages/*`、`frontend/src/components/*`
  - E2E：`frontend/tests/e2e/*`
- **协作接口**
  - 与后端：接口契约、鉴权、错误码
  - 与 QA：关键路径 E2E 与回归范围
- **完成定义（DoD）**
  - 构建通过（`npm --prefix frontend run build`）
  - 关键路径具备最小 E2E 覆盖

### 2.5 测试与质量负责人（QA/QE）

- **目标**
  - 把“可交付性”具体化为可执行的回归与门禁。
- **核心职责**
  - 验收用例：覆盖成功/失败/取消/异常。
  - 回归策略：单测/集成/E2E 的范围与触发方式。
  - 缺陷管理：复现步骤、期望/实际、影响面。
- **主要交付物**
  - E2E 用例（优先关键闭环）：`frontend/tests/e2e/*`
  - 后端回归用例：`backend/tests/*`
  - 归档：一次性测试报告进 `docs/_archive/`
- **完成定义（DoD）**
  - 给出“可验收”结论与风险列表

### 2.6 运维 / SRE（DevOps/SRE）

- **目标**
  - 保证环境可复制、可观测、可回滚。
- **核心职责**
  - 部署：Compose/Helm 的一致性维护。
  - 冒烟：可一键执行，结果可留痕。
  - 变更：发布前检查、发布后验证。
- **主要交付物**
  - `docker-compose*.yml` / `helm/baixing-assistant/*`
  - `scripts/*`（smoke / 运维脚本）
  - `docs/DATABASE.md`（备份/恢复/runbook）
- **完成定义（DoD）**
  - 具备可重复的发布/回滚 SOP；冒烟可通过

### 2.7 安全与合规负责人（Security）

- **目标**
  - 降低敏感数据/鉴权/注入/越权风险，保证 secrets 处理合规。
- **核心职责**
  - secrets：不入库、不进 SystemConfig；生产注入方式审计。
  - 鉴权：JWT、权限依赖（admin/lawyer/用户）审计。
  - 安全基线：OWASP 常见风险排查（XSS/CSRF/注入/文件上传）。
- **主要交付物**
  - 风险清单与修复建议（必要时归档到 `docs/_archive/`）
  - 配置建议：`docs/TECH_SPEC.md` 相关章节
- **完成定义（DoD）**
  - 关键风险有结论与处置；上线前门禁明确

### 2.8 文档与交付负责人（Docs/Delivery）

- **目标**
  - 保证“对外可解释、对内可延续”。
- **核心职责**
  - 入口维护：README / docs/README / 索引互链。
  - 归档策略：阶段性材料进入 `docs/_archive/`。
  - 变更记录：对外可感知变更写入 `docs/CHANGELOG.md`。
- **主要交付物**
  - 文档互链维护与审计结果（必要时归档）
- **完成定义（DoD）**
  - 文档口径与代码一致；入口无断链

### 2.9 AI 能力负责人（Prompt/RAG/LLM Engineer，可由后端兼任）

- **目标**
  - AI 输出可控、可追踪、可迭代（A/B + prompt_version）。
- **核心职责**
  - Prompt 版本化与灰度策略。
  - RAG：向量库、召回、引用与可解释性。
  - 反馈闭环：用户评价、管理端统计。
- **主要交付物**
  - 相关后端服务与统计接口
  - 管理端观测面板
- **完成定义（DoD）**
  - 可观测：能按 `prompt_version` 看效果；异常可追踪

---

## 3. 常见事项的 RACI（简化版）

| 事项                  | PO/PM | Tech Lead | Backend | Frontend | QA  | DevOps | Security | Docs |
| --------------------- | ----- | --------- | ------- | -------- | --- | ------ | -------- | ---- |
| 新功能（含需求/验收） | R/A   | C         | R       | R        | C   | C      | C        | C    |
| API/数据模型变更      | C     | A         | R       | C        | C   | C      | C        | C    |
| UI/交互改版           | C     | C         | C       | R/A      | C   | -      | -        | C    |
| Bug 修复（线上）      | C     | A         | R       | R        | R   | R      | C        | C    |
| 发布/回滚             | C     | A         | C       | C        | C   | R/A    | C        | C    |
| secrets/权限策略调整  | C     | A         | C       | C        | -   | C      | R/A      | C    |

说明：

- R=Responsible（执行）A=Accountable（最终负责）C=Consulted（需协商）

---

## 4. 与 Windsurf Workflows 的对应

本仓库已提供按角色拆分的工作流（在 Windsurf Cascade 输入以下命令可调用）：

- `/project-roles`：角色总览与快速分派
- `/feature-delivery`：新功能全链路交付（需求->方案->实现->回归->文档）
- `/hotfix-incident`：线上问题/紧急修复（复现->修复->回归->发布->复盘）
- `/role-product`：PO/PM 工作流（PRD/验收/拆解）
- `/role-tech-lead`：架构/技术方案工作流
- `/role-backend`：后端实现工作流（routers/services/models/tests）
- `/role-frontend`：前端实现工作流（pages/components/e2e）
- `/role-qa`：回归与验收工作流
- `/role-devops`：部署/冒烟/runbook 工作流
- `/role-security`：安全审计工作流
- `/role-docs`：文档互链/归档/变更记录工作流
