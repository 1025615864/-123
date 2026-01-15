# 前端架构（FRONTEND_ARCH）

本文件面向前端/全栈开发者，描述前端路由、API client、鉴权状态、React Query、WebSocket 与错误处理的真实实现。

## 1. 应用入口

- `frontend/src/main.tsx`
  - 初始化 Sentry（可选）：`VITE_SENTRY_DSN` 等
  - 初始化 React Query：`QueryClientProvider`
    - QueryCache/MutationCache 全局 onError（统一 toast）
  - `ThemeProvider` + `LanguageProvider` + `BrowserRouter`

## 2. API Client（axios）

- `frontend/src/api/client.ts`

关键行为：

- `baseURL`：`VITE_API_BASE_URL`
- 默认 header：
  - `Authorization: Bearer <token>`（来自 localStorage）
  - `X-Api-Envelope: 1`（启用后端 envelope）
  - `X-Request-Id`（链路 id）

401 行为：

- 若响应 401，client 会清理 token 并触发 `window.dispatchEvent(new Event('auth:logout'))`

## 3. 鉴权状态（AuthContext）

- `frontend/src/contexts/AuthContext.tsx`

实现要点：

- token 存储：`localStorage['token']`
- 初始化时会尝试解析 JWT payload，并在过期/非法时清理 token
- token 变更时：
  - 写入 axios 默认 Authorization
  - 调 `GET /user/me` 拉取用户信息（失败会 logout）
- 监听全局事件：`auth:logout`

路由守卫：

- `frontend/src/components/RouteGuards.tsx`
  - `RequireAuth`：未登录跳转登录
  - `RequireLawyer`：要求律师身份

## 4. 路由结构（App.tsx）

- `frontend/src/App.tsx`

特点：

- 大多数页面使用 `React.lazy()` 懒加载
- 采用两套 Layout：
  - 前台：`Layout`
  - 管理后台：`AdminLayout`

## 5. React Query 约定

- query keys 统一收敛：`frontend/src/queryKeys.ts`
- 典型 queries：`frontend/src/queries/*`
  - notifications：`useNotificationsQuery/useNotificationsPreviewQuery`

全局错误 toast：

- `main.tsx` 中的 QueryCache/MutationCache onError 会调用 `getApiErrorMessage()` 并去重 toast
- 401 会提示“登录已失效，请重新登录”

## 6. WebSocket（/ws）

接入：

- `frontend/src/components/Layout.tsx`
  - 登录态 `isAuthenticated=true` 才会 connect

Hook：

- `frontend/src/hooks/useWebSocket.ts`

URL 推导：

- 优先使用 `VITE_API_BASE_URL` 解析 host（会去掉尾部 `/api`）
- 否则使用 `window.location.host`
- 拼接：`ws(s)://<host>/ws?token=<jwt>`

消息处理：

- Layout 中只对 `msg.type === 'notification'` 做 react-query invalidate

## 7. 前端开发与代理

- `frontend/vite.config.ts`
  - dev server: 5173
  - proxy：`/api`、`/robots.txt`、`/sitemap.xml`、`/ws` -> 后端

本地联调建议：

- 使用根目录 `start-dev.ps1` 同时拉起前后端

## 8. E2E

- `npm --prefix frontend run test:e2e`

后端配合点：

- AI SSE/转写/文件分析支持 `X-E2E-Mock-AI: 1`（仅 debug）
