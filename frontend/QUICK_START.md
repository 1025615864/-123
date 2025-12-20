# 快速开始指南

## 安装和运行

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问 `http://localhost:5173`

### 3. 确保后端运行

后端需要在 `http://localhost:8000` 运行

## 常用命令

```bash
# 开发模式
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview

# 类型检查
npx tsc --noEmit
```

## 组件快速使用

### 创建一个新页面

```tsx
import { Card, Button, Input } from "@/components/ui";
import { useApi, useToast } from "@/hooks";

export default function MyPage() {
  const { post, loading } = useApi({ showErrorToast: true });
  const toast = useToast();

  const handleSubmit = async () => {
    try {
      await post("/api/endpoint", { data: "value" });
      toast.success("操作成功");
    } catch (error) {
      // 错误已自动处理
    }
  };

  return (
    <Card>
      <h1 className="text-2xl font-bold">我的页面</h1>
      <Button onClick={handleSubmit} isLoading={loading}>
        提交
      </Button>
    </Card>
  );
}
```

### 使用表单

```tsx
import { useState } from "react";
import { Input, Textarea, Button } from "@/components/ui";

export default function FormExample() {
  const [formData, setFormData] = useState({
    title: "",
    content: "",
  });

  return (
    <form onSubmit={handleSubmit}>
      <Input
        label="标题"
        value={formData.title}
        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
        placeholder="请输入标题"
        required
      />

      <Textarea
        label="内容"
        value={formData.content}
        onChange={(e) => setFormData({ ...formData, content: e.target.value })}
        rows={5}
        required
      />

      <Button type="submit">提交</Button>
    </form>
  );
}
```

### 使用模态框

```tsx
import { useState } from "react";
import { Modal, Button } from "@/components/ui";

export default function ModalExample() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Button onClick={() => setIsOpen(true)}>打开模态框</Button>

      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="模态框标题"
        description="这是描述文字"
      >
        <p>模态框内容</p>
        <Button onClick={() => setIsOpen(false)}>关闭</Button>
      </Modal>
    </>
  );
}
```

### API 调用

```tsx
import { useEffect, useState } from "react";
import { useApi } from "@/hooks";
import { Loading } from "@/components/ui";

export default function DataList() {
  const [items, setItems] = useState([]);
  const { get, loading } = useApi();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const response = await get("/api/items");
      setItems(response.items);
    } catch (error) {
      console.error("加载失败", error);
    }
  };

  if (loading) return <Loading text="加载中..." />;

  return (
    <div>
      {items.map((item) => (
        <div key={item.id}>{item.name}</div>
      ))}
    </div>
  );
}
```

## 样式指南

### TailwindCSS 常用类

```tsx
// 布局
<div className="flex items-center justify-between gap-4">
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

// 间距
<div className="p-4 m-4">        // padding & margin
<div className="px-4 py-2">      // 水平和垂直
<div className="space-y-4">      // 子元素垂直间距

// 文字
<h1 className="text-2xl font-bold text-slate-900">
<p className="text-sm text-slate-600">

// 颜色
bg-indigo-600    // 背景色
text-white       // 文字色
border-slate-200 // 边框色

// 圆角
rounded-xl       // 大圆角
rounded-full     // 完全圆形

// 阴影
shadow-sm        // 小阴影
shadow-lg        // 大阴影
```

### 自定义样式类

```tsx
// 玻璃态效果
<div className="glass">

// 卡片悬停效果
<div className="card-hover">

// 主按钮样式
<button className="btn-primary">

// 渐变文字
<span className="gradient-text">

// 动画
<div className="animate-fade-in">
<div className="animate-slide-in">
```

## 常见问题

### Q: 如何添加新路由？

在 `App.tsx` 中添加：

```tsx
<Route path="newpage" element={<NewPage />} />
```

### Q: 如何处理认证？

```tsx
import { useAuth } from "@/contexts/AuthContext";

const { isAuthenticated, user, login, logout } = useAuth();

if (!isAuthenticated) {
  return <Navigate to="/login" />;
}
```

### Q: 如何显示通知？

```tsx
import { useToast } from "@/hooks";

const toast = useToast();

toast.success("成功消息");
toast.error("错误消息");
toast.info("提示消息");
toast.warning("警告消息");
```

### Q: 如何处理表单验证？

```tsx
const [errors, setErrors] = useState({});

const validate = () => {
  const newErrors = {};

  if (!formData.title) {
    newErrors.title = "标题不能为空";
  }

  setErrors(newErrors);
  return Object.keys(newErrors).length === 0;
};

const handleSubmit = (e) => {
  e.preventDefault();
  if (validate()) {
    // 提交表单
  }
};

// 在Input组件中显示错误
<Input
  label="标题"
  value={formData.title}
  onChange={handleChange}
  error={errors.title}
/>;
```

## 开发技巧

1. **使用 TypeScript** - 充分利用类型提示
2. **组件复用** - 优先使用 UI 组件库
3. **状态管理** - 局部状态用 useState，全局用 Context
4. **错误处理** - 使用 useApi 自动处理错误
5. **代码格式** - 保持一致的代码风格

## 调试

### React DevTools

安装 React DevTools 浏览器扩展进行调试

### 查看网络请求

打开浏览器开发者工具 -> Network 标签

### 查看 Console 日志

打开浏览器开发者工具 -> Console 标签

## 下一步

- 阅读 [README.md](./README.md) 了解完整文档
- 查看 [REFACTORING_SUMMARY.md](./REFACTORING_SUMMARY.md) 了解重构细节
- 浏览 `src/components/ui/` 查看所有可用组件
- 查看 `src/pages/` 中的示例代码

## 获取帮助

- 查看组件源码了解用法
- 阅读 TailwindCSS 文档
- 参考现有页面的实现
