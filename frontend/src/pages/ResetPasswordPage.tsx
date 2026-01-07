import { useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Eye, EyeOff, Lock, AlertCircle, CheckCircle } from "lucide-react";

import api from "../api/client";
import PageHeader from "../components/PageHeader";
import { Button, Card, EmptyState, Input } from "../components/ui";
import { useTheme } from "../contexts/ThemeContext";
import { useAppMutation, useToast } from "../hooks";

export default function ResetPasswordPage() {
  const { actualTheme } = useTheme();
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const token = useMemo(() => {
    const raw = String(searchParams.get("token") ?? "").trim();
    return raw || null;
  }, [searchParams]);

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [done, setDone] = useState(false);

  const passwordRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLInputElement>(null);

  const confirmMutation = useAppMutation<
    { message?: string },
    { token: string; new_password: string }
  >({
    mutationFn: async (payload) => {
      const res = await api.post("/user/password-reset/confirm", payload);
      return res.data as { message?: string };
    },
    errorMessageFallback: "重置失败，请稍后重试",
    onSuccess: (data) => {
      setDone(true);
      toast.success(String(data?.message || "密码重置成功"));
      setTimeout(() => {
        navigate("/login", { replace: true });
      }, 300);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    const p = String(password || "");
    const c = String(confirmPassword || "");

    if (!p.trim()) {
      passwordRef.current?.focus();
      toast.error("请输入新密码");
      return;
    }
    if (p.length < 6) {
      passwordRef.current?.focus();
      toast.error("新密码长度至少6位");
      return;
    }
    if (!c.trim()) {
      confirmRef.current?.focus();
      toast.error("请再次输入新密码");
      return;
    }
    if (p !== c) {
      confirmRef.current?.focus();
      toast.error("两次输入的新密码不一致");
      return;
    }

    if (confirmMutation.isPending || done) return;
    confirmMutation.mutate({ token, new_password: p });
  };

  if (!token) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="账户"
          title="重置密码"
          description="请通过邮件链接打开该页面"
          layout="mdStart"
          tone={actualTheme}
        />
        <Card variant="surface" padding="lg">
          <EmptyState
            icon={AlertCircle}
            title="缺少重置参数"
            description="请从重置邮件中打开链接，或重新发起找回密码。"
            tone={actualTheme}
            action={
              <div className="flex flex-wrap items-center gap-2">
                <Link to="/forgot-password">
                  <Button>去找回密码</Button>
                </Link>
                <Link to="/login">
                  <Button variant="outline">返回登录</Button>
                </Link>
              </div>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="账户"
        title="重置密码"
        description="设置一个新的登录密码"
        layout="mdStart"
        tone={actualTheme}
      />

      <Card variant="surface" padding="lg" className="max-w-xl">
        {done ? (
          <EmptyState
            icon={CheckCircle}
            title="已重置"
            description="密码已重置成功，即将跳转到登录页"
            tone={actualTheme}
            action={
              <Link to="/login">
                <Button>去登录</Button>
              </Link>
            }
          />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="新密码"
              icon={Lock}
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入新密码（至少6位）"
              autoComplete="new-password"
              ref={passwordRef}
              disabled={confirmMutation.isPending}
              right={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="p-2 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-900/5 transition disabled:opacity-60 disabled:cursor-not-allowed dark:text-white/40 dark:hover:text-white/70 dark:hover:bg-white/5"
                  aria-label={showPassword ? "隐藏密码" : "显示密码"}
                  disabled={confirmMutation.isPending}
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              }
            />

            <Input
              label="确认新密码"
              icon={Lock}
              type={showPassword ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="请再次输入新密码"
              autoComplete="new-password"
              ref={confirmRef}
              disabled={confirmMutation.isPending}
            />

            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="submit"
                isLoading={confirmMutation.isPending}
                loadingText="提交中..."
                disabled={confirmMutation.isPending}
              >
                确认重置
              </Button>
              <Link to="/login">
                <Button variant="outline" disabled={confirmMutation.isPending}>
                  返回登录
                </Button>
              </Link>
            </div>
          </form>
        )}
      </Card>
    </div>
  );
}
