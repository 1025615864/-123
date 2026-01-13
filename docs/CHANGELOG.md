# 变更记录（Changelog）

> 说明：本文件用于记录对外可感知的版本变化与工程交付节点。更细节的交接信息见 `docs/_archive/PROJECT_REPORT.md`。

## 维护约定

- 版本号：采用 **SemVer**（例如 `v0.3.0`），发布 tag 也使用 `vX.Y.Z`。
- 结构：保持 `Unreleased` 为开发中汇总；每次发布前将 `Unreleased` 内容整理到新版本段落：
  - `## [vX.Y.Z] - YYYY-MM-DD`
  - 发布后重新创建空的 `Unreleased`。
- Release Notes：发布工作流会优先从 `CHANGELOG` 中提取与 tag 同名的版本段落作为 Release 内容；若未找到，会回退到 `Unreleased`。
- 只记录“对外可感知”的变更（功能/修复/性能/兼容性/部署与运维）。纯重构/格式化不写，或合并为一句。

### 发布清单（Checklist）

- 版本号与变更记录
  - 确认 tag 使用 `vX.Y.Z`（SemVer），并且 `docs/CHANGELOG.md` 存在同名版本段落或 `Unreleased` 已整理
  - 确认 Release Notes 不包含敏感信息（密钥/Token/内网地址）
- 本地回归（建议最小集）
  - 后端：`py -m pytest -q`
  - 前端：`npm --prefix frontend run build`
  - 必要时：Playwright 最小闭环 `npm --prefix frontend run test:e2e -- --grep "documents:"`
- CI 与交付
  - 确认 CI 全绿（`ci.yml`）
  - 触发 tag 发布后，确认 `release.yml` 产出：GitHub Release + 前端 dist + Helm chart 包
  - 如启用镜像发布：确认 GHCR 镜像 tag 与版本一致
- 数据与回滚
  - 若包含数据库变更：确认 Alembic 迁移可执行（含回滚策略）
  - 明确回滚方案：上一版本 tag + 镜像/Helm 回滚命令（生产环境）

## [Unreleased]

- 修复：前端补齐账户相关路由（/verify-email、/forgot-password、/reset-password），避免邮件链接 404
- 新增：后端短信/邮箱验证回归测试（`backend/tests/test_user_verification.py`）
- 修复：调整 `pyrightconfig.json` 的 `executionEnvironments.extraPaths`，确保 tests 中 `app.*` 导入可被正确解析
- 修复：敏感操作验证兜底（改密要求手机号+邮箱验证；前端 403 按手机号/邮箱引导至个人中心验证）
- 新增：支付链路冒烟回归测试（webhook 回调 -> 订单 paid -> 管理端回调审计可查）
- 优化：第三方支付回跳 return_url 自动携带 order_no；前端支付提示提供直达支付结果页入口
- 新增：CI 自动回归（GitHub Actions）：backend pytest、frontend build、Playwright 最小 documents E2E
- 新增：`backend/requirements-dev.txt`（集中管理测试依赖，CI 与本地一致）
- 新增：支付管理页 `/admin/payment-callbacks` 支持渠道密钥维护（env 热更新）与回调审计高级筛选
- 优化：初始化数据脚本幂等化（`backend/scripts/seed_data.py` / `seed_legal_knowledge.py`），支持一键重置与清晰日志
- 优化：管理后台侧边栏信息架构（多分组二级菜单）
- 新增：Release 工作流（tag -> GitHub Release + 构建产物上传）
- 文档：一致性审计并按代码真实状态同步核心文档
  - 更新：`docs/核心文档清单/03_DIRECTORY_STRUCTURE.md`（补齐实际路由模块与 init_db 门禁说明）
  - 更新：`docs/核心文档清单/02_TECH_STACK_ARCHITECTURE.md`（前端依赖固定版本；迁移/限流描述与代码一致）
  - 更新：`docs/核心文档清单/04_DATABASE_SCHEMA_ERD.md`（补充律师复核相关表与关系；更新迁移说明）
  - 更新：`docs/核心文档清单/05_BUSINESS_LOGIC_DATA_FLOW.md`（补充合同审查/律师复核/支付渠道状态；修正 Redis 强依赖与周期任务锁策略）
  - 更新：`docs/核心文档清单/06_CODE_AUDIT.md`（迁移/限流现状描述与代码一致）
  - 更新：`docs/TECH_SPEC.md`、`docs/API_DESIGN.md`、`docs/DATABASE.md`（补齐新模块与生产门禁要点）
  - 更新：`docs/README.md`（更新时间与“以代码为准”说明）、`继任者必读.md`（生产门禁与模块定位补充）
  - 更新：`docs/核心文档清单/02_TECH_STACK_ARCHITECTURE.md`（补充架构总览 Mermaid 图、关键不变量与互链入口）
  - 更新：`docs/TECH_SPEC.md`（补充运行模式与门禁矩阵，并链接架构总览/DB 运维）
  - 更新：`docs/DATABASE.md`（补充 DB 运维 Runbook：备份/恢复/演练/迁移发布/回滚）
  - 更新：`docs/核心文档清单/README.md`（补充指向 TECH_SPEC/DATABASE 的权威入口链接）

## [2026-01-08]

- 新增：面向 AI 编程的标准文档体系
  - `docs/PRD.md`
  - `docs/TECH_SPEC.md`
  - `docs/API_DESIGN.md`
  - `docs/DATABASE.md`
  - `docs/CHANGELOG.md`
  - 根目录：`CLAUDE.md`、`TASKS.md`

## [2025-12-29] - news-module-20251229

- 发布：News 模块阶段性版本（见仓库 tag/release）
- 完善：文档入口与交付口径收敛

## [2025-12-27]

- 强化：Secrets 不入库策略（SystemConfig 写入拦截）
- 增强：News AI 运维状态与相关兜底

## [2026-01-06]

- 完成：E2E 回归全绿（pytest/Playwright/pyright）
- 完善：律师结算/提现与商业化配额交付口径

## [2026-01-07]

- 更新：项目报告（`docs/_archive/PROJECT_REPORT.md`）
- 更新：技术对接报告（`docs/_archive/TECHNICAL_INTEGRATION_REPORT.md`）
