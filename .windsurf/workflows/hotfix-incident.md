---
description: 线上问题/紧急修复（复现->修复->回归->发布->复盘）
---

# hotfix-incident

目标：用一套固定流程处理线上问题/紧急修复，确保可复现、可回归、可发布、可复盘。

1. 先收集信息并固化：
   - 现象、触发条件、影响范围、发生频率
   - 关键日志/`request_id`（参考 `docs/TECH_SPEC.md` 的 request_id 说明）
2. 调用 `/role-qa`：
   - 将问题复现为最小用例（优先 Playwright 或 pytest）
   - 明确“期望 vs 实际”
3. 调用 `/role-tech-lead`：
   - 做影响面分析（接口/数据/权限/支付/并发）
   - 给出最小修复策略与回滚策略
4. 调用 `/role-backend` 或 `/role-frontend`（按问题归属）：
   - 先修根因，再处理症状
   - 必要时增加日志/错误信息（可追踪）
5. 回归门禁：
   - 后端：`py -m pytest -q`
   - 前端：`npm --prefix frontend run build`
   - E2E：关键路径用例（`npm --prefix frontend run test:e2e`）
6. 发布与验证：
   - 调用 `/role-devops`：发布/冒烟/回滚预案
7. 复盘与留痕：
   - 调用 `/role-docs`：将“复现/修复/验证/发布/结论”归档到 `docs/_archive/`
