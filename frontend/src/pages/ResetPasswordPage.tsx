import { useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Eye, EyeOff, Lock, AlertCircle, CheckCircle } from "lucide-react";

import api from "../api/client";
import PageHeader from "../components/PageHeader";
import { Button, Card, EmptyState, Input } from "../components/ui";
import { useTheme } from "../contexts/ThemeContext";
import { useLanguage } from "../contexts/LanguageContext";
import { useAppMutation, useToast } from "../hooks";

export default function ResetPasswordPage() {
  const { actualTheme } = useTheme();
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useLanguage();

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
    errorMessageFallback: t("passwordReset.resetErrorFallback"),
    onSuccess: (data) => {
      setDone(true);
      toast.success(String(data?.message || t("passwordReset.resetSuccessToastFallback")));
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
      toast.error(t("passwordReset.newPasswordRequired"));
      return;
    }
    if (p.length < 6) {
      passwordRef.current?.focus();
      toast.error(t("passwordReset.newPasswordTooShort"));
      return;
    }
    if (!c.trim()) {
      confirmRef.current?.focus();
      toast.error(t("passwordReset.confirmNewPasswordRequired"));
      return;
    }
    if (p !== c) {
      confirmRef.current?.focus();
      toast.error(t("passwordReset.passwordNotMatch"));
      return;
    }

    if (confirmMutation.isPending || done) return;
    confirmMutation.mutate({ token, new_password: p });
  };

  if (!token) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow={t("passwordReset.eyebrow")}
          title={t("passwordReset.resetTitle")}
          description={t("passwordReset.openFromEmailDescription")}
          layout="mdStart"
          tone={actualTheme}
        />
        <Card variant="surface" padding="lg">
          <EmptyState
            icon={AlertCircle}
            title={t("passwordReset.missingTokenTitle")}
            description={t("passwordReset.missingTokenDescription")}
            tone={actualTheme}
            action={
              <div className="flex flex-wrap items-center gap-2">
                <Link to="/forgot-password">
                  <Button>{t("passwordReset.goForgotPassword")}</Button>
                </Link>
                <Link to="/login">
                  <Button variant="outline">{t("passwordReset.backToLogin")}</Button>
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
        eyebrow={t("passwordReset.eyebrow")}
        title={t("passwordReset.resetTitle")}
        description={t("passwordReset.resetDescription")}
        layout="mdStart"
        tone={actualTheme}
      />

      <Card variant="surface" padding="lg" className="max-w-xl">
        {done ? (
          <EmptyState
            icon={CheckCircle}
            title={t("passwordReset.doneTitle")}
            description={t("passwordReset.doneDescription")}
            tone={actualTheme}
            action={
              <Link to="/login">
                <Button>{t("passwordReset.goLogin")}</Button>
              </Link>
            }
          />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label={t("passwordReset.newPasswordLabel")}
              icon={Lock}
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("auth.passwordPlaceholderMin6")}
              autoComplete="new-password"
              ref={passwordRef}
              disabled={confirmMutation.isPending}
              right={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="p-2 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-900/5 transition disabled:opacity-60 disabled:cursor-not-allowed dark:text-white/40 dark:hover:text-white/70 dark:hover:bg-white/5"
                  aria-label={showPassword ? t("auth.hidePassword") : t("auth.showPassword")}
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
              label={t("passwordReset.confirmNewPasswordLabel")}
              icon={Lock}
              type={showPassword ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder={t("passwordReset.confirmNewPasswordPlaceholder")}
              autoComplete="new-password"
              ref={confirmRef}
              disabled={confirmMutation.isPending}
            />

            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="submit"
                isLoading={confirmMutation.isPending}
                loadingText={t("passwordReset.submitting")}
                disabled={confirmMutation.isPending}
              >
                {t("passwordReset.confirmReset")}
              </Button>
              <Link to="/login">
                <Button variant="outline" disabled={confirmMutation.isPending}>
                  {t("passwordReset.backToLogin")}
                </Button>
              </Link>
            </div>
          </form>
        )}
      </Card>
    </div>
  );
}
