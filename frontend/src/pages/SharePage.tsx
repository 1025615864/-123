import { useEffect, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Share2, User, Bot, RotateCcw } from "lucide-react";
import { Card, Button, EmptyState, Skeleton } from "../components/ui";
import PageHeader from "../components/PageHeader";
import api from "../api/client";
import { queryKeys } from "../queryKeys";
import { useTheme } from "../contexts/ThemeContext";
import { useLanguage } from "../contexts/LanguageContext";
import { getApiErrorMessage } from "../utils";

interface SharedMessage {
  role: string;
  content: string;
  references: string | null;
  created_at: string;
}

interface SharedConsultationResponse {
  session_id: string;
  title: string | null;
  created_at: string;
  messages: SharedMessage[];
}

export default function SharePage() {
  const { actualTheme } = useTheme();
  const { t, language } = useLanguage();
  const params = useParams();
  const token = String(params.token || "").trim();

  const sharedQuery = useQuery({
    queryKey: queryKeys.sharedConsultation(token),
    queryFn: async () => {
      const res = await api.get(`/ai/share/${encodeURIComponent(token)}`);
      return res.data as SharedConsultationResponse;
    },
    enabled: Boolean(token),
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!sharedQuery.error) return;
  }, [sharedQuery.error]);

  const data = sharedQuery.data ?? null;

  const pageTitle = useMemo(() => {
    const rawTitle = String(data?.title || "").trim();
    return rawTitle || t("sharePage.defaultTitle");
  }, [data?.title, t]);

  const createdAtText = useMemo(() => {
    const raw = String(data?.created_at || "").trim();
    if (!raw) return "";
    const ts = new Date(raw).getTime();
    if (Number.isNaN(ts)) return raw;
    const locale = language === "en" ? "en-US" : "zh-CN";
    return new Date(ts).toLocaleString(locale);
  }, [data?.created_at, language]);

  const handleCopyLink = async () => {
    const url = `${window.location.origin}/share/${token}`;
    try {
      await navigator.clipboard.writeText(url);
      window.alert(t("sharePage.copyLinkSuccess"));
    } catch {
      window.prompt(t("sharePage.copyLinkPromptTitle"), url);
    }
  };

  if (!token) {
    return (
      <EmptyState
        icon={Share2}
        title={t("sharePage.invalidLinkTitle")}
        description={t("sharePage.missingTokenDescription")}
        tone={actualTheme}
        action={
          <Link to="/">
            <Button icon={ArrowRight}>{t("sharePage.backHome")}</Button>
          </Link>
        }
      />
    );
  }

  if (sharedQuery.isLoading && !data) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow={t("sharePage.eyebrow")}
          title={t("sharePage.defaultTitle")}
          tone={actualTheme}
          right={
            <Button
              variant="outline"
              icon={RotateCcw}
              isLoading
              loadingText={t("sharePage.refreshing")}
              disabled
            >
              {t("sharePage.refresh")}
            </Button>
          }
        />

        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, idx) => (
            <Card key={idx} variant="surface" padding="lg">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-2">
                  <Skeleton variant="circular" width="32px" height="32px" />
                  <Skeleton width="72px" height="14px" />
                </div>
                <Skeleton width="96px" height="12px" />
              </div>
              <div className="mt-3 space-y-2">
                <Skeleton width="100%" height="14px" />
                <Skeleton width="92%" height="14px" />
                <Skeleton width="80%" height="14px" />
              </div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const errText = sharedQuery.isError
    ? getApiErrorMessage(sharedQuery.error, t("sharePage.loadFailedFallback"))
    : null;

  if (errText) {
    return (
      <EmptyState
        icon={Share2}
        title={t("sharePage.openFailedTitle")}
        description={errText}
        tone={actualTheme}
        action={
          <Button variant="outline" onClick={() => sharedQuery.refetch()}>
            {t("sharePage.retry")}
          </Button>
        }
      />
    );
  }

  if (!data) {
    return (
      <EmptyState
        icon={Share2}
        title={t("sharePage.noDataTitle")}
        description={t("sharePage.emptyDataDescription")}
        tone={actualTheme}
      />
    );
  }

  const messages = Array.isArray(data.messages) ? data.messages : [];

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow={t("sharePage.eyebrow")}
        title={pageTitle}
        description={
          createdAtText
            ? `${t("sharePage.createdAtPrefix")}${createdAtText}`
            : t("sharePage.readOnlyHint")
        }
        tone={actualTheme}
        right={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => sharedQuery.refetch()}
              icon={RotateCcw}
              isLoading={sharedQuery.isFetching}
              loadingText={t("sharePage.refreshing")}
              disabled={sharedQuery.isFetching}
            >
              {t("sharePage.refresh")}
            </Button>
            <Button variant="outline" onClick={handleCopyLink} icon={Share2}>
              {t("sharePage.copyLink")}
            </Button>
            <Link to="/chat">
              <Button
                icon={ArrowRight}
                className="bg-emerald-600 hover:bg-emerald-700 text-white focus-visible:ring-emerald-500/25"
              >
                {t("sharePage.goConsult")}
              </Button>
            </Link>
          </div>
        }
      />

      {messages.length === 0 ? (
        <EmptyState
          icon={Share2}
          title={t("sharePage.noMessagesTitle")}
          description={t("sharePage.noMessagesDescription")}
          tone={actualTheme}
        />
      ) : (
        <div className="space-y-4">
          {messages.map((m, idx) => {
            const role = String(m.role || "").trim();
            const isUser = role === "user";
            const Icon = isUser ? User : Bot;
            const label = isUser ? t("sharePage.userLabel") : t("sharePage.aiLabel");
            const atRaw = String(m.created_at || "").trim();
            const locale = language === "en" ? "en-US" : "zh-CN";
            const atText = atRaw ? new Date(atRaw).toLocaleString(locale) : "";

            return (
              <Card
                key={`${idx}-${role}`}
                variant="surface"
                padding="lg"
                className={
                  isUser
                    ? "border border-blue-500/10"
                    : "border border-amber-500/10"
                }
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-white">
                    <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-slate-900/5 dark:bg-white/5">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span>{label}</span>
                  </div>
                  <div className="text-xs text-slate-500 dark:text-white/40">
                    {atText}
                  </div>
                </div>
                <div className="mt-3 text-sm text-slate-700 whitespace-pre-wrap leading-relaxed dark:text-white/70">
                  {String(m.content || "")}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
