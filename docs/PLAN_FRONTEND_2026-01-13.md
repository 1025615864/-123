# 前端问题发现与布局优化计划

更新时间：2026-01-13

本计划用于承接：

- 前端问题发现（质量/安全/构建门禁）
- 前端布局设计评审（可用性/交互/一致性）

并将修复动作落实到代码与文档。

---

## 1. 问题发现结论（已执行）

### 1.1 构建门禁

- 已执行：`npm --prefix frontend ci`
- 已执行：`npm --prefix frontend run build`（`tsc && vite build`）
- 结论：构建通过；未发现 TypeScript 编译/打包错误。

### 1.2 依赖安全（npm audit）

- 发现：`react-router-dom` 所依赖的 `react-router` 版本范围存在已披露安全问题（`npm audit` 报 high/moderate）。
- 已修复：将 `react-router-dom` 升级至 `7.12.0`（exact），并更新 lock。
- 验证：`npm --prefix frontend audit` 结果为 `0 vulnerabilities`。

---

## 2. 修复计划（质量/安全）

- **P0：依赖安全基线（已完成）**

  - 升级 `react-router-dom@7.12.0`
  - 目标：`npm audit` 清零
  - 门禁：`npm --prefix frontend run build`

- **P1：持续门禁建议（可选后续）**
  - 将 `npm audit` 纳入 CI（可先只在 main 分支/定期执行），避免供应链回归。

---

## 3. 布局设计评审：问题与建议

### 3.1 发现的问题（Layout 侧）

- **桌面端 Tools 下拉菜单**：

  - 目前缺少“点击空白处关闭”的交互；只在路由切换时关闭。
  - 缺少 `Esc` 快捷键关闭。

- **移动端菜单（Hamburger）**：
  - 打开后缺少更强的“关闭一致性”（`Esc` / 点击空白处）。
  - 打开菜单时，页面背景滚动体验容易混乱；建议锁定背景滚动，并保证菜单内容可滚动。

### 3.2 建议的修复策略

- 增加：
  - `Esc` 关闭（对 `toolsMenuOpen` 与 `mobileMenuOpen` 生效）
  - 点击菜单区域外自动关闭
  - 移动端菜单开启时锁定 body 滚动，同时让菜单区域 `overflow-auto`

---

## 4. 修复计划（布局/交互）

- **P0：菜单可关闭性与滚动锁定（已完成）**

  - 修改文件：`frontend/src/components/Layout.tsx`
  - 实现：
    - `Esc` 关闭
    - click-outside 关闭
    - mobile menu open 时 lock body scroll
    - mobile menu panel 增加 `max-h` + `overflow-auto`
  - 门禁：
    - `npm --prefix frontend run build`
  - 验证：构建通过

- **P1：回归建议（可选后续）**
  - 新增 1 条 Playwright 用例（例如 `layout:`）：
    - 打开 mobile menu -> 点击空白处关闭
    - 打开 tools menu -> Esc 关闭

---

## 5. 文档更新清单（计划执行）

- 更新角色与工作流入口：`docs/ROLES.md`
- 更新 docs 入口：`docs/README.md`
- 更新仓库入口：`README.md`
- 在 `TASKS_NEXT.md` 记录本次前端质量/布局修复事项

---

## 6. Hotfix：翻译系统与语音功能（本轮执行）

### 6.1 翻译系统问题（无法完整翻译网站）

- 原因（阶段性判断）：
  - 页面大量硬编码中文，未统一接入 `LanguageContext.t()`。
  - 翻译缺失 key 时默认回显 key，导致体验像“没翻译”。
- 已做：
  - `translate()` 缺失 key 时：英文回落中文（避免回显 key）。
  - 关键路径页面接入 `t()`：`/login`、`/register`、`/chat`。
- 本轮补齐：
  - i18n 覆盖扩展：`/`（Home）、`/forgot-password`、`/reset-password`、`/verify-email` 接入 `t()` 并补齐 `zh/en` key。
  - Layout footer 文案（简介/地址/版权）接入 `t()`，英文模式不再夹杂中文。
  - i18n 覆盖扩展：`/search`（SearchPage）、`/news`（NewsPage）、`/forum`（ForumPage）接入 `t()`，并补齐 `searchPage.*` / `newsPage.*` / `forumPage.*` 的 `zh/en` key。
  - i18n 覆盖扩展：`/news/:newsId`（NewsDetailPage）、`/forum/post/:postId`（PostDetailPage）接入 `t()`，并补齐 `newsDetailPage.*` / `postDetailPage.*` 的 `zh/en` key。
  - i18n 覆盖扩展：`/news/topics`（NewsTopicsPage）、`/news/topics/:topicId`（NewsTopicDetailPage）接入 `t()`，并补齐 `newsTopicsPage.*` / `newsTopicDetailPage.*` 的 `zh/en` key。
  - i18n 覆盖扩展：`/share/:token`（SharePage）接入 `t()`，并补齐 `sharePage.*` 的 `zh/en` key。
  - i18n 覆盖扩展：`/chat/history`（ChatHistoryPage）接入 `t()`，并补齐 `chatHistoryPage.*` 的 `zh/en` key。
  - i18n 覆盖扩展：`/documents`（DocumentGeneratorPage）接入 `t()`，并补齐 `documentGeneratorPage.*` 的 `zh/en` key。
  - i18n 覆盖扩展：`/contracts`（ContractReviewPage）接入 `t()`，并补齐 `contractReviewPage.*` 的 `zh/en` key。
- 门禁：`npm --prefix frontend run build` 通过。

### 6.2 AI 助手语音功能问题

- 现状：前端使用 `MediaRecorder` 录音，上传到 `/ai/transcribe`（后端 OpenAI Whisper）。
- 已做（兼容性增强）：
  - 自动选择浏览器支持的 `mimeType`（优先 opus/webm/ogg）。
  - `stop()` 前尝试 `requestData()`，提升“短录音无数据”的成功率。
  - 更清晰的错误提示（忙碌/权限拒绝/转写失败）。
- 已做（可用性检测）：
  - 新增后端公开接口：`GET /system/public/ai/status`（不需管理员权限，不泄露敏感信息），用于判断语音转写是否可用。
  - 前端 Chat 在语音按钮处读取该状态：不可用则禁用语音按钮并提示（避免用户反复失败）。
  - E2E：语音用例 mock 该接口，避免测试环境未配置 OpenAI 时用例不稳定。
- 回归：`npm --prefix frontend run test:e2e -- --grep chat-voice-input` 通过。

---

## 7. 视觉与交互优化（待分期交付）

- P0：统一关键路径（首页/登录注册/咨询页）视觉层级与间距，优先解决“不够美观、交互不一致”。
- P1：补齐全站 i18n 覆盖（逐页清理硬编码文案），并纳入 E2E/CI 约束。

### 7.1 已完成（本轮追加）

- PageHeader：增强一致性（防溢出、light tone 使用 amber/slate 色系），不改业务。
- Layout：header/main/footer 统一容器 padding 与留白节奏；header 增加轻微阴影层级。
- UI primitives：
  - Modal：close 按钮 aria-label 统一为英文 Close（避免硬编码中文，提升一致性）。
  - Button：默认 loadingText 统一为英文 Loading...；图标尺寸随 size 自适配（sm 不再显得过大）。
- 关键页面密度：
  - `/documents`（DocumentGeneratorPage）：步骤指示器/按钮组支持换行，配额分隔符统一，生成结果区/历史详情操作按钮统一 icon 与密度。
  - `/contracts`（ContractReviewPage）：文件操作按钮组支持换行，提升小屏可用性。
