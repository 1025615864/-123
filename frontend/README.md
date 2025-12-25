# 百姓法律助手 - 前端应用

一个现代化的法律服务平台前端应用，基于 React + TypeScript + TailwindCSS 构建。

## 功能特性

- 🤖 **AI 法律咨询** - 24 小时智能法律顾问
- 💬 **法律论坛** - 用户交流与讨论平台
- 📰 **法律新闻** - 最新法律资讯和政策解读
- 🏢 **律所查询** - 查找专业律师事务所
- 🔐 **用户认证** - 安全的登录注册系统

## 技术栈

- **React 19.2** - 最新版本的 React 框架
- **TypeScript 5.9** - 类型安全的 JavaScript 超集
- **Vite 7.2** - 下一代前端构建工具
- **TailwindCSS 4.1** - 实用优先的 CSS 框架
- **React Router 7.10** - 声明式路由
- **Axios 1.13** - Promise based HTTP 客户端
- **Lucide React** - 美观的图标库
- **React Query 5.90** - 强大的数据同步

## 项目结构

```
src/
├── components/          # 组件
│   ├── ui/             # UI组件库
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   ├── Input.tsx
│   │   ├── Textarea.tsx
│   │   ├── Modal.tsx
│   │   ├── Badge.tsx
│   │   └── Loading.tsx
│   └── Layout.tsx      # 布局组件
├── pages/              # 页面组件
│   ├── HomePage.tsx
│   ├── ChatPage.tsx
│   ├── ForumPage.tsx
│   ├── NewsPage.tsx
│   ├── LawFirmPage.tsx
│   ├── LoginPage.tsx
│   └── RegisterPage.tsx
├── hooks/              # 自定义Hooks
│   ├── useApi.ts
│   ├── useToast.tsx
│   └── index.ts
├── contexts/           # React Context
│   └── AuthContext.tsx
├── types/              # TypeScript类型
│   └── index.ts
├── api/                # API配置
│   └── client.ts
├── App.tsx             # 应用入口
├── main.tsx            # 主入口
└── index.css           # 全局样式
```

## 开始使用

### 前置要求

- Node.js >= 18.0.0
- npm >= 9.0.0

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev
```

应用将在 `http://localhost:5173` 启动

### 构建生产版本

```bash
npm run build
```

构建产物将输出到 `dist/` 目录

### 预览生产构建

```bash
npm run preview
```

## 端到端测试（Playwright E2E）

本项目已提供 Playwright 端到端测试，用于覆盖论坛审核/通知深链等关键回归场景。

### 前置条件

- 后端服务已启动且可访问（默认前端通过 Vite 代理访问 `http://localhost:8000`）
- 数据库可写（E2E 会注册新用户、创建帖子/评论、触发审核/驳回等）

### 安装浏览器（首次/Playwright 更新后需要）

```bash
npm run test:e2e:install
```

### 运行 E2E

```bash
npm run test:e2e
```

可选：以 UI 模式调试

```bash
npm run test:e2e:ui
```

### 可选环境变量

- `E2E_API_BASE`
  - 默认：`http://localhost:5173/api`
  - 说明：Playwright 通过该地址直连后端 API（通常由 Vite 代理转发到后端）。
- `E2E_ADMIN_USER`
  - 默认：`admin`
  - 说明：用于执行管理员审核/驳回接口的账号。
- `E2E_ADMIN_PASS`
  - 默认：`admin123`

在 PowerShell 中示例：

```powershell
$env:E2E_API_BASE="http://localhost:5173/api"
$env:E2E_ADMIN_USER="admin"
$env:E2E_ADMIN_PASS="admin123"
npm run test:e2e
```

## 环境配置

后端 API 代理配置在 `vite.config.ts` 中：

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    }
  }
}
```

## 组件库使用

### Button 组件

```tsx
import { Button } from "@/components/ui";

<Button variant="primary" size="md" icon={Plus}>
  点击按钮
</Button>;
```

**Props:**

- `variant`: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
- `size`: 'sm' | 'md' | 'lg'
- `icon`: Lucide 图标组件
- `isLoading`: 显示加载状态
- `fullWidth`: 全宽按钮

### Card 组件

```tsx
import { Card } from "@/components/ui";

<Card variant="glass" hover padding="md">
  卡片内容
</Card>;
```

**Props:**

- `variant`: 'default' | 'glass' | 'bordered'
- `hover`: 启用悬停效果
- `padding`: 'none' | 'sm' | 'md' | 'lg'

### Input 组件

```tsx
import { Input } from "@/components/ui";

<Input
  label="用户名"
  placeholder="请输入用户名"
  icon={User}
  error="错误提示"
/>;
```

### Modal 组件

```tsx
import { Modal } from "@/components/ui";

<Modal
  isOpen={isOpen}
  onClose={() => setIsOpen(false)}
  title="标题"
  description="描述"
>
  模态框内容
</Modal>;
```

## Hooks 使用

### useApi Hook

```tsx
import { useApi } from "@/hooks";

const { get, post, loading, error } = useApi({
  showErrorToast: true,
  showSuccessToast: true,
  successMessage: "操作成功",
});

// GET请求
const data = await get("/api/posts");

// POST请求
await post("/api/posts", { title: "标题", content: "内容" });
```

### useToast Hook

```tsx
import { useToast } from "@/hooks";

const toast = useToast();

toast.success("操作成功");
toast.error("操作失败");
toast.info("提示信息");
toast.warning("警告信息");
```

## 样式系统

### TailwindCSS 配置

项目使用 TailwindCSS 4.1，配置文件为 `tailwind.config.js`

### 自定义样式类

在 `index.css` 中定义了一些自定义样式：

- `.glass` - 玻璃态效果
- `.card-hover` - 卡片悬停动画
- `.btn-primary` - 主按钮样式
- `.gradient-text` - 渐变文字

### 动画

```css
.animate-fade-in      /* 淡入动画 */
/* 淡入动画 */
/* 淡入动画 */
/* 淡入动画 */
/* 淡入动画 */
/* 淡入动画 */
/* 淡入动画 */
/* 淡入动画 */
.animate-slide-in     /* 滑入动画 */
.animate-float        /* 浮动动画 */
.animate-gradient; /* 渐变动画 */
```

## API 集成

### 认证

```tsx
import { useAuth } from "@/contexts/AuthContext";

const { user, login, logout, isAuthenticated } = useAuth();

// 登录
await login(username, password);

// 登出
logout();
```

### API 调用示例

```tsx
// 获取论坛帖子
const { get } = useApi();
const response = await get("/forum/posts");
const posts = response.items;

// 创建帖子
const { post } = useApi({ showSuccessToast: true });
await post("/forum/posts", {
  title: "标题",
  content: "内容",
  category: "法律咨询",
});
```

## 类型定义

所有类型定义在 `src/types/index.ts`：

```typescript
interface User {
  id: number;
  username: string;
  email: string;
  role: string;
}

interface Post {
  id: number;
  title: string;
  content: string;
  category: string;
  author?: Author;
  like_count: number;
  comment_count: number;
  created_at: string;
}
```

## 路由配置

```tsx
<Routes>
  <Route path="/" element={<Layout />}>
    <Route index element={<HomePage />} />
    <Route path="chat" element={<ChatPage />} />
    <Route path="forum" element={<ForumPage />} />
    <Route path="news" element={<NewsPage />} />
    <Route path="lawfirm" element={<LawFirmPage />} />
    <Route path="login" element={<LoginPage />} />
    <Route path="register" element={<RegisterPage />} />
  </Route>
</Routes>
```

## 最佳实践

### 1. 组件开发

- 使用函数组件和 Hooks
- 保持组件单一职责
- 使用 TypeScript 类型
- 提取可复用逻辑到自定义 Hooks

### 2. 状态管理

- 局部状态使用 useState
- 全局状态使用 Context
- 服务器状态使用 React Query

### 3. 样式规范

- 优先使用 TailwindCSS 工具类
- 复杂样式提取到 CSS 类
- 保持响应式设计

### 4. 性能优化

- 使用 React.memo 避免不必要的重渲染
- 使用 useCallback 和 useMemo 优化性能
- 路由级别的代码分割

## 浏览器支持

- Chrome >= 90
- Firefox >= 88
- Safari >= 14
- Edge >= 90

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

MIT License

## 联系方式

- 项目地址: [GitHub](https://github.com/yourusername/baixing-law-assistant)
- 问题反馈: [Issues](https://github.com/yourusername/baixing-law-assistant/issues)

## 更新日志

### v2.0.0 (2024-12)

- ✨ 完整重构前端架构
- 🎨 创建可复用 UI 组件库
- 🔧 添加自定义 Hooks (useApi, useToast)
- 📝 完善 TypeScript 类型定义
- 🚀 优化性能和用户体验
- 📱 改进响应式设计

### v1.0.0 (2024-11)

- 🎉 初始版本发布
