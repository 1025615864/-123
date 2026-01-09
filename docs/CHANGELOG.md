# 变更记录（Changelog）

> 说明：本文件用于记录对外可感知的版本变化与工程交付节点。更细节的交接信息见 `docs/_archive/PROJECT_REPORT.md`。

## [Unreleased]

- 修复：前端补齐账户相关路由（/verify-email、/forgot-password、/reset-password），避免邮件链接 404
- 新增：后端短信/邮箱验证回归测试（`backend/tests/test_user_verification.py`）
- 修复：调整 `pyrightconfig.json` 的 `executionEnvironments.extraPaths`，确保 tests 中 `app.*` 导入可被正确解析
- 修复：敏感操作验证兜底（改密要求手机号+邮箱验证；前端 403 按手机号/邮箱引导至个人中心验证）
- 新增：支付链路冒烟回归测试（webhook 回调 -> 订单 paid -> 管理端回调审计可查）
- 优化：第三方支付回跳 return_url 自动携带 order_no；前端支付提示提供直达支付结果页入口
- 新增：CI 自动回归（GitHub Actions）：backend pytest、frontend build、Playwright 最小 documents E2E
- 新增：`backend/requirements-dev.txt`（集中管理测试依赖，CI 与本地一致）

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
