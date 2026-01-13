---
description: 项目角色总览与分派
---

# project-roles

目标：当你要做“全方位项目开发”时，用最短路径完成角色分派、产出物与门禁对齐。

1. 先问用户：本次要推进的事项属于哪类？
   - 新功能 / Bug 修复 / 运维发布 / 安全整改 / 文档整理
2. 读取权威入口，形成统一口径：
   - 需求：`docs/PRD.md`
   - 技术：`docs/TECH_SPEC.md`
   - 接口：`docs/API_DESIGN.md`
   - 数据：`docs/DATABASE.md`
   - 任务：`TASKS_NEXT.md`
3. 根据事项自动分派“主责角色 + 协作角色”，并输出：
   - 本次目标（可验收的）
   - 需要修改的目录/文件（预估）
   - 必过门禁（pytest/frontend build/E2E/smoke 等）
4. 执行过程中遵守：
   - 修改核心接口/数据结构必须同步更新前端与测试
   - secrets 永不入库
5. 进入执行：
   - 新功能：优先调用 `/role-tech-lead` -> `/role-backend` -> `/role-frontend` -> `/role-qa` -> `/role-docs`
   - Bug：`/role-qa`（定位复现）-> `/role-backend`/`/role-frontend`（修复）-> `/role-qa`（回归）-> `/role-docs`
   - 发布：`/role-devops`（演练/冒烟/回滚）-> `/role-docs`
