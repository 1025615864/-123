import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Mail, ShieldCheck } from "lucide-react";

import api from "../api/client";
import PageHeader from "../components/PageHeader";
import { Button, Card, Input } from "../components/ui";
import { useTheme } from "../contexts/ThemeContext";
import { useLanguage } from "../contexts/LanguageContext";
import { useAppMutation, useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";

export default function ForgotPasswordPage() {
  const { actualTheme } = useTheme();
  const toast = useToast();
  const { t } = useLanguage();

  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);

  const requestMutation = useAppMutation<{ message?: string }, { email: string }>({
    mutationFn: async (payload) => {
      const res = await api.post("/user/password-reset/request", payload);
      return res.data as { message?: string };
    },
    errorMessageFallback: t("passwordReset.forgotErrorFallback"),
    onSuccess: (data) => {
      setSent(true);
      toast.success(String(data?.message || t("passwordReset.forgotSuccessToastFallback")));
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const v = String(email || "").trim();
    if (!v) {
      emailRef.current?.focus();
      toast.error(t("passwordReset.emailRequired"));
      return;
    }
    if (requestMutation.isPending) return;
    requestMutation.mutate({ email: v });
  };

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow={t("passwordReset.eyebrow")}
        title={t("passwordReset.forgotTitle")}
        description={t("passwordReset.forgotDescription")}
        layout="mdStart"
        tone={actualTheme}
      />

      <Card variant="surface" padding="lg" className="max-w-xl">
        <div className="flex items-start gap-3">
          <div className="mt-1 h-10 w-10 rounded-2xl bg-slate-900/5 border border-slate-200/70 flex items-center justify-center dark:bg-white/[0.03] dark:border-white/[0.08]">
            <ShieldCheck className="h-5 w-5 text-amber-400" />
          </div>
          <div className="min-w-0">
            <div className="text-base font-semibold text-slate-900 dark:text-white">{t("passwordReset.viaEmailTitle")}</div>
            <div className="text-sm text-slate-600 dark:text-white/60">
              {t("passwordReset.viaEmailDescription")}
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <Input
            label={t("auth.email")}
            icon={Mail}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("passwordReset.emailPlaceholder")}
            ref={emailRef}
            disabled={requestMutation.isPending || sent}
          />

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="submit"
              isLoading={requestMutation.isPending}
              loadingText={t("passwordReset.sending")}
              disabled={requestMutation.isPending || sent}
            >
              {t("passwordReset.sendResetEmail")}
            </Button>
            <Link to="/login">
              <Button variant="outline" disabled={requestMutation.isPending}>
                {t("passwordReset.backToLogin")}
              </Button>
            </Link>
          </div>

          {requestMutation.isError ? (
            <div className="text-sm text-red-400">
              {getApiErrorMessage(requestMutation.error, t("passwordReset.forgotSendFailed"))}
            </div>
          ) : null}

          {sent ? (
            <div className="text-sm text-emerald-600 dark:text-emerald-400">
              {t("passwordReset.sentHint")}
            </div>
          ) : null}
        </form>
      </Card>
    </div>
  );
}
