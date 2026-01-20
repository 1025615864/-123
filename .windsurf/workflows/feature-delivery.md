---
description: 新功能全链路交付（需求->方案->实现->回归->文档）
---

# feature-delivery

目标：把一个新功能从“需求”推进到“可验收交付”，并保证门禁与文档同步。

1. 调用 `/project-roles`，明确本次事项为“新功能”，输出主责/协作角色与必过门禁。
2. 调用 `/role-product`：
   - 对齐 PRD 的范围/非范围、验收点（至少 1 条失败/取消路径）
   - 将拆解任务写入 `TASKS_NEXT.md`
3. 调用 `/role-tech-lead`：
   - 输出方案草图（模块边界/API/数据/迁移/回滚/风险）
   - 明确质量门禁（`py -m pytest -q` / `npm --prefix frontend run build` / `npm --prefix frontend run test:e2e` / smoke/health）
4. 调用 `/role-backend`：
   - 实现 API/服务/模型/测试
   - 若涉及 DB 变更，补迁移或说明生产门禁策略
5. 调用 `/role-frontend`：
   - 完成页面/组件接入
   - 实现 loading/error/empty/retry
   - 补 1 条关键路径 Playwright 用例
6. 调用 `/role-qa`：
   - 回归验证（成功 + 失败/取消/异常）
   - 输出风险清单
7. 调用 `/role-docs`：
   - 更新文档入口互链（README/docs/README）
   - 必要时归档一次性材料到 `docs/_archive/`
8. 收尾输出：
   - 本次改动文件清单
   - 门禁执行结果
   - 仍待跟进事项（如有）
