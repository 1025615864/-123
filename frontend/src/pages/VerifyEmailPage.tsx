import { useEffect, useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Mail, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import api from "../api/client";
import PageHeader from "../components/PageHeader";
import { Button, Card, EmptyState } from "../components/ui";
import { useTheme } from "../contexts/ThemeContext";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";

export default function VerifyEmailPage() {
  const { actualTheme } = useTheme();
  const { refreshUser } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const token = useMemo(() => {
    const raw = String(searchParams.get("token") ?? "").trim();
    return raw || null;
  }, [searchParams]);

  const verifyQuery = useQuery({
    queryKey: ["verify-email", { token }],
    queryFn: async () => {
      const res = await api.get("/user/email-verification/verify", {
        params: { token },
      });
      return res.data as { message?: string; success?: boolean };
    },
    enabled: !!token,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!verifyQuery.error) return;
    toast.error(getApiErrorMessage(verifyQuery.error, "邮箱验证失败"));
  }, [toast, verifyQuery.error]);

  useEffect(() => {
    if (!verifyQuery.data) return;
    void refreshUser();
  }, [refreshUser, verifyQuery.data]);

  const content = (() => {
    if (!token) {
      return (
        <EmptyState
          icon={Mail}
          title="缺少验证参数"
          description="请从验证邮件中打开链接，或重新请求验证邮件。"
          tone={actualTheme}
          action={
            <Link to="/profile">
              <Button>返回个人中心</Button>
            </Link>
          }
        />
      );
    }

    if (verifyQuery.isLoading) {
      return (
        <div className="flex flex-col items-center justify-center py-10 gap-4">
          <div className="w-12 h-12 rounded-full bg-amber-500/10 flex items-center justify-center">
            <Loader2 className="h-6 w-6 text-amber-600 animate-spin dark:text-amber-400" />
          </div>
          <div className="text-sm text-slate-600 dark:text-white/60">验证中，请稍候...</div>
        </div>
      );
    }

    if (verifyQuery.isError) {
      return (
        <EmptyState
          icon={AlertCircle}
          title="邮箱验证失败"
          description={getApiErrorMessage(verifyQuery.error, "链接无效或已过期")}
          tone={actualTheme}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <Link to="/profile">
                <Button>返回个人中心</Button>
              </Link>
              <Button
                variant="outline"
                onClick={() => {
                  navigate("/profile", { replace: true });
                }}
              >
                去重新发送
              </Button>
            </div>
          }
        />
      );
    }

    return (
      <EmptyState
        icon={CheckCircle}
        title="邮箱验证成功"
        description={String(verifyQuery.data?.message || "你的邮箱已验证成功")}
        tone={actualTheme}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Link to="/profile">
              <Button>返回个人中心</Button>
            </Link>
            <Link to="/login">
              <Button variant="outline">去登录</Button>
            </Link>
          </div>
        }
      />
    );
  })();

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="账户"
        title="邮箱验证"
        description="验证邮箱以提升账户安全与可恢复性"
        layout="mdStart"
        tone={actualTheme}
      />

      <Card variant="surface" padding="lg">
        {content}
      </Card>
    </div>
  );
}
