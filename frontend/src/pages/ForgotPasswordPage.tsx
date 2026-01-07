import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Mail, ShieldCheck } from "lucide-react";

import api from "../api/client";
import PageHeader from "../components/PageHeader";
import { Button, Card, Input } from "../components/ui";
import { useTheme } from "../contexts/ThemeContext";
import { useAppMutation, useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";

export default function ForgotPasswordPage() {
  const { actualTheme } = useTheme();
  const toast = useToast();

  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);

  const requestMutation = useAppMutation<{ message?: string }, { email: string }>({
    mutationFn: async (payload) => {
      const res = await api.post("/user/password-reset/request", payload);
      return res.data as { message?: string };
    },
    errorMessageFallback: "发送失败，请稍后重试",
    onSuccess: (data) => {
      setSent(true);
      toast.success(String(data?.message || "如果邮箱存在，我们将发送重置链接"));
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const v = String(email || "").trim();
    if (!v) {
      emailRef.current?.focus();
      toast.error("请输入邮箱");
      return;
    }
    if (requestMutation.isPending) return;
    requestMutation.mutate({ email: v });
  };

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="账户"
        title="找回密码"
        description="输入注册邮箱，我们会发送密码重置链接"
        layout="mdStart"
        tone={actualTheme}
      />

      <Card variant="surface" padding="lg" className="max-w-xl">
        <div className="flex items-start gap-3">
          <div className="mt-1 h-10 w-10 rounded-2xl bg-slate-900/5 border border-slate-200/70 flex items-center justify-center dark:bg-white/[0.03] dark:border-white/[0.08]">
            <ShieldCheck className="h-5 w-5 text-amber-400" />
          </div>
          <div className="min-w-0">
            <div className="text-base font-semibold text-slate-900 dark:text-white">通过邮箱找回</div>
            <div className="text-sm text-slate-600 dark:text-white/60">
              发送后请检查收件箱与垃圾箱，链接通常在 1 小时内有效。
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <Input
            label="邮箱"
            icon={Mail}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="请输入注册邮箱"
            ref={emailRef}
            disabled={requestMutation.isPending || sent}
          />

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="submit"
              isLoading={requestMutation.isPending}
              loadingText="发送中..."
              disabled={requestMutation.isPending || sent}
            >
              发送重置邮件
            </Button>
            <Link to="/login">
              <Button variant="outline" disabled={requestMutation.isPending}>
                返回登录
              </Button>
            </Link>
          </div>

          {requestMutation.isError ? (
            <div className="text-sm text-red-400">
              {getApiErrorMessage(requestMutation.error, "发送失败")}
            </div>
          ) : null}

          {sent ? (
            <div className="text-sm text-emerald-600 dark:text-emerald-400">
              如果邮箱存在，我们将发送重置链接。请打开邮件完成重置。
            </div>
          ) : null}
        </form>
      </Card>
    </div>
  );
}
