import { useState, useEffect, useMemo, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { Save, Key, Globe, Bell, Shield, HelpCircle, Sparkles, CreditCard, RotateCcw } from "lucide-react";
import { Card, Input, Button, Textarea, ListSkeleton } from "../../components/ui";
import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import { queryKeys } from "../../queryKeys";

interface ConfigItem {
  key: string;
  value: string | null;
  description: string | null;
  category: string;
}

interface NewsAiProviderPublic {
  name: string | null;
  base_url: string;
  model: string | null;
  response_format: string | null;
  auth_type: string | null;
  auth_header_name: string | null;
  auth_prefix: string | null;
  chat_completions_path: string | null;
  weight: number | null;
  api_key_configured: boolean;
}

interface NewsAiRecentError {
  news_id: number;
  retry_count: number;
  last_error: string | null;
  last_error_at: string | null;
}

interface NewsAiErrorTrendItem {
  date: string;
  errors: number;
}

interface NewsAiTopError {
  message: string;
  count: number;
}

interface NewsAiStatusResponse {
  news_ai_enabled: boolean;
  news_ai_interval_seconds: number;
  summary_llm_enabled: boolean;
  response_format: string | null;
  provider_strategy: string;
  providers: NewsAiProviderPublic[];
  pending_total: number;
  errors_total: number;
  errors_last_24h: number;
  errors_last_7d: number;
  errors_trend_7d: NewsAiErrorTrendItem[];
  top_errors: NewsAiTopError[];
  recent_errors: NewsAiRecentError[];
  config_overrides: Record<string, string>;
}

interface AiOpsRecentError {
  at: string;
  request_id: string;
  endpoint: string;
  error_code: string;
  status_code: number | null;
  message: string | null;
}

interface AiOpsStatusResponse {
  ai_router_enabled: boolean;
  openai_api_key_configured: boolean;
  openai_base_url: string;
  ai_model: string;
  chroma_persist_dir: string;
  started_at: number;
  started_at_iso: string;
  chat_requests_total: number;
  chat_stream_requests_total: number;
  errors_total: number;
  recent_errors: AiOpsRecentError[];
  top_error_codes?: Array<{ error_code: string; count: number }>;
  top_endpoints?: Array<{ endpoint: string; count: number }>;
}

interface FaqItem {
  question: string;
  answer: string;
}

interface FaqPublicResponse {
  items: FaqItem[];
  updated_at: string | null;
}

function SimpleMiniBarChart({
  data,
  maxValue,
}: {
  data: { label: string; value: number }[];
  maxValue: number;
}) {
  return (
    <div className="flex items-end justify-between gap-2 h-24">
      {data.map((item, idx) => (
        <div key={idx} className="flex-1 flex flex-col items-center gap-2">
          <div className="w-full flex flex-col" style={{ height: "80px" }}>
            <div
              className="w-full bg-gradient-to-t from-amber-500 to-orange-400 rounded-t transition-all"
              style={{
                height: `${(item.value / Math.max(1, maxValue)) * 100}%`,
              }}
              title={`${item.value}`}
            />
          </div>
          <span className="text-[10px] text-slate-500 dark:text-white/50">
            {item.label}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function SettingsPage() {
  const toast = useToast();
  const [settings, setSettings] = useState({
    siteName: "百姓法律助手",
    siteDescription: "为普通百姓提供专业法律咨询服务",
    contactEmail: "support@baixinghelper.cn",
    contactPhone: "400-800-1234",
    enableAI: true,
    newsAiSummaryLlmEnabled: false,
    newsAiProviderStrategy: "priority",
    newsAiResponseFormat: "",
    newsAiProvidersScope: "default",
    newsAiProvidersJson: "",
    newsReviewPolicyEnabled: false,
    newsReviewPolicyJson:
      '{\n  "safe": "approved",\n  "warning": "pending",\n  "danger": "pending",\n  "unknown": "pending"\n}',
    contractReviewRulesJson:
      '{\n  "required_clauses": [\n    {\n      "name": "争议解决",\n      "patterns": ["争议解决", "仲裁", "诉讼"]\n    },\n    {\n      "name": "违约责任",\n      "patterns": ["违约责任", "违约金"]\n    }\n  ],\n  "risk_keywords": [\n    {\n      "keyword": "不可撤销",\n      "title": "存在不可撤销条款，请重点确认",\n      "severity": "medium",\n      "problem": "合同中出现不可撤销等强约束表述，可能导致单方权利受限。",\n      "suggestion": "核对是否符合交易习惯，必要时补充撤销/解除条件或例外情形。"\n    }\n  ]\n}',
    vipDefaultDays: "30",
    vipDefaultPrice: "29",
    aiChatPackOptionsJson: '{\n  "10": 12,\n  "50": 49,\n  "100": 79\n}',
    documentGeneratePackOptionsJson: '{\n  "10": 12,\n  "50": 49,\n  "100": 79\n}',
    freeAiChatDailyLimit: "5",
    vipAiChatDailyLimit: "1000000000",
    freeDocumentGenerateDailyLimit: "10",
    vipDocumentGenerateDailyLimit: "50",
    enableNotifications: true,
    maintenanceMode: false,
  });

  const tabItems = [
    { key: "base", label: "站点与基础", icon: Globe },
    { key: "ai", label: "AI 咨询", icon: Shield },
    { key: "commercial", label: "商业化", icon: CreditCard },
    { key: "news_ai", label: "新闻 AI", icon: Key },
    { key: "content", label: "内容与审核", icon: HelpCircle },
    { key: "notify", label: "通知与维护", icon: Bell },
  ] as const;

  type SettingsTabKey = (typeof tabItems)[number]["key"];
  const [activeTab, setActiveTab] = useState<SettingsTabKey>("base");

  const [urlParams, setUrlParams] = useSearchParams();
  const didInitTabFromUrlRef = useRef(false);

  useEffect(() => {
    if (didInitTabFromUrlRef.current) return;
    const rawTab = String(urlParams.get("tab") ?? "").trim();
    const nextTab = tabItems.some((t) => t.key === rawTab) ? (rawTab as SettingsTabKey) : "base";
    setActiveTab(nextTab);
    didInitTabFromUrlRef.current = true;
  }, [tabItems, urlParams]);

  useEffect(() => {
    if (!didInitTabFromUrlRef.current) return;
    setUrlParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (activeTab !== "base") next.set("tab", activeTab);
        else next.delete("tab");
        return next;
      },
      { replace: true }
    );
  }, [activeTab, setUrlParams]);

  const faqPublicQuery = useQuery({
    queryKey: queryKeys.publicFaq(),
    queryFn: async () => {
      const res = await api.get("/system/public/faq");
      return res.data as FaqPublicResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const configsQuery = useQuery({
    queryKey: queryKeys.systemConfigs(),
    queryFn: async () => {
      const res = await api.get("/system/configs");
      return (Array.isArray(res.data) ? res.data : []) as ConfigItem[];
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!configsQuery.error) return;
    toast.error(getApiErrorMessage(configsQuery.error, "配置加载失败"));
  }, [configsQuery.error, toast]);

  const configMap = useMemo((): Record<string, string> => {
    const configs = configsQuery.data;
    const out: Record<string, string> = {};
    if (!configs || configs.length === 0) return out;
    configs.forEach((c) => {
      if (c.value !== null) out[c.key] = c.value;
    });
    return out;
  }, [configsQuery.data]);

  const newsAiStatusQuery = useQuery({
    queryKey: queryKeys.newsAiStatus(),
    queryFn: async () => {
      const res = await api.get("/system/news-ai/status");
      return res.data as NewsAiStatusResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const aiOpsStatusQuery = useQuery({
    queryKey: queryKeys.aiOpsStatus(),
    queryFn: async () => {
      const res = await api.get("/system/ai/status");
      return res.data as AiOpsStatusResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!newsAiStatusQuery.error) return;
    toast.error(
      getApiErrorMessage(newsAiStatusQuery.error, "新闻AI状态加载失败")
    );
  }, [newsAiStatusQuery.error, toast]);

  useEffect(() => {
    if (!aiOpsStatusQuery.error) return;
    toast.error(getApiErrorMessage(aiOpsStatusQuery.error, "AI运维状态加载失败"));
  }, [aiOpsStatusQuery.error, toast]);

  useEffect(() => {
    if (!faqPublicQuery.error) return;
    toast.error(getApiErrorMessage(faqPublicQuery.error, "FAQ 加载失败"));
  }, [faqPublicQuery.error, toast]);

  useEffect(() => {
    setSettings((prev) => {
      const scopeRaw = String((prev as any).newsAiProvidersScope || "default").trim();
      const scope = scopeRaw && scopeRaw !== "default" ? scopeRaw : "default";
      const providersKey =
        scope === "default"
          ? "NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON"
          : `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON_${scope}`;

      return {
        ...prev,
        siteName: configMap["site_name"] || prev.siteName,
        siteDescription: configMap["site_description"] || prev.siteDescription,
        contactEmail: configMap["contact_email"] || prev.contactEmail,
        contactPhone: configMap["contact_phone"] || prev.contactPhone,
        enableAI: configMap["enable_ai"] !== "false",
        newsAiSummaryLlmEnabled: configMap["NEWS_AI_SUMMARY_LLM_ENABLED"]
          ? configMap["NEWS_AI_SUMMARY_LLM_ENABLED"] !== "false"
          : prev.newsAiSummaryLlmEnabled,
        newsAiProviderStrategy:
          configMap["NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY"] ||
          prev.newsAiProviderStrategy,
        newsAiResponseFormat:
          configMap["NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT"] ||
          prev.newsAiResponseFormat,
        newsAiProvidersJson: configMap[providersKey] ? "••••••••••••••••" : "",
        newsReviewPolicyEnabled: configMap["NEWS_REVIEW_POLICY_ENABLED"]
          ? configMap["NEWS_REVIEW_POLICY_ENABLED"] !== "false"
          : prev.newsReviewPolicyEnabled,
        newsReviewPolicyJson:
          typeof configMap["NEWS_REVIEW_POLICY_JSON"] === "string"
            ? configMap["NEWS_REVIEW_POLICY_JSON"]
            : prev.newsReviewPolicyJson,
        contractReviewRulesJson:
          typeof configMap["CONTRACT_REVIEW_RULES_JSON"] === "string"
            ? configMap["CONTRACT_REVIEW_RULES_JSON"]
            : prev.contractReviewRulesJson,
        vipDefaultDays: configMap["VIP_DEFAULT_DAYS"] || prev.vipDefaultDays,
        vipDefaultPrice: configMap["VIP_DEFAULT_PRICE"] || prev.vipDefaultPrice,
        aiChatPackOptionsJson:
          configMap["AI_CHAT_PACK_OPTIONS_JSON"] || prev.aiChatPackOptionsJson,
        documentGeneratePackOptionsJson:
          configMap["DOCUMENT_GENERATE_PACK_OPTIONS_JSON"] ||
          prev.documentGeneratePackOptionsJson,
        freeAiChatDailyLimit:
          configMap["FREE_AI_CHAT_DAILY_LIMIT"] || prev.freeAiChatDailyLimit,
        vipAiChatDailyLimit:
          configMap["VIP_AI_CHAT_DAILY_LIMIT"] || prev.vipAiChatDailyLimit,
        freeDocumentGenerateDailyLimit:
          configMap["FREE_DOCUMENT_GENERATE_DAILY_LIMIT"] ||
          prev.freeDocumentGenerateDailyLimit,
        vipDocumentGenerateDailyLimit:
          configMap["VIP_DOCUMENT_GENERATE_DAILY_LIMIT"] ||
          prev.vipDocumentGenerateDailyLimit,
        enableNotifications: configMap["enable_notifications"] !== "false",
        maintenanceMode: configMap["maintenance_mode"] === "true",
      };
    });
  }, [configMap]);

  const saveMutation = useAppMutation<
    void,
    { configs: Array<{ key: string; value: string; category: string }> }
  >({
    mutationFn: async (payload) => {
      await api.post("/system/configs/batch", payload);
    },
    successMessage: "设置保存成功",
    errorMessageFallback: "保存失败，请稍后重试",
    invalidateQueryKeys: [queryKeys.systemConfigs(), queryKeys.newsAiStatus()],
  });

  const generateFaqMutation = useAppMutation<void, void>({
    mutationFn: async (_: void) => {
      await api.post("/system/faq/generate", null, {
        params: {
          days: 30,
          max_items: 20,
          scan_limit: 200,
        },
      });
    },
    successMessage: "FAQ 已生成",
    errorMessageFallback: "FAQ 生成失败",
    invalidateQueryKeys: [queryKeys.publicFaq()],
    onSuccess: async () => {
      await faqPublicQuery.refetch();
    },
  });

  const handleSave = async () => {
    try {
      const configs = [
        { key: "site_name", value: settings.siteName, category: "general" },
        {
          key: "site_description",
          value: settings.siteDescription,
          category: "general",
        },
        {
          key: "contact_email",
          value: settings.contactEmail,
          category: "general",
        },
        {
          key: "contact_phone",
          value: settings.contactPhone,
          category: "general",
        },
        { key: "enable_ai", value: String(settings.enableAI), category: "ai" },
        {
          key: "NEWS_AI_SUMMARY_LLM_ENABLED",
          value: String(settings.newsAiSummaryLlmEnabled),
          category: "news_ai",
        },
        {
          key: "NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY",
          value: settings.newsAiProviderStrategy,
          category: "news_ai",
        },
        {
          key: "NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT",
          value: settings.newsAiResponseFormat,
          category: "news_ai",
        },
        {
          key: "NEWS_REVIEW_POLICY_ENABLED",
          value: String(settings.newsReviewPolicyEnabled),
          category: "news_review",
        },
        {
          key: "NEWS_REVIEW_POLICY_JSON",
          value: settings.newsReviewPolicyJson,
          category: "news_review",
        },
        {
          key: "CONTRACT_REVIEW_RULES_JSON",
          value: settings.contractReviewRulesJson,
          category: "ai",
        },
        {
          key: "VIP_DEFAULT_DAYS",
          value: String(settings.vipDefaultDays || "").trim(),
          category: "commercial",
        },
        {
          key: "VIP_DEFAULT_PRICE",
          value: String(settings.vipDefaultPrice || "").trim(),
          category: "commercial",
        },
        {
          key: "AI_CHAT_PACK_OPTIONS_JSON",
          value: String(settings.aiChatPackOptionsJson || "").trim(),
          category: "commercial",
        },
        {
          key: "DOCUMENT_GENERATE_PACK_OPTIONS_JSON",
          value: String(settings.documentGeneratePackOptionsJson || "").trim(),
          category: "commercial",
        },
        {
          key: "FREE_AI_CHAT_DAILY_LIMIT",
          value: String(settings.freeAiChatDailyLimit || "").trim(),
          category: "commercial",
        },
        {
          key: "VIP_AI_CHAT_DAILY_LIMIT",
          value: String(settings.vipAiChatDailyLimit || "").trim(),
          category: "commercial",
        },
        {
          key: "FREE_DOCUMENT_GENERATE_DAILY_LIMIT",
          value: String(settings.freeDocumentGenerateDailyLimit || "").trim(),
          category: "commercial",
        },
        {
          key: "VIP_DOCUMENT_GENERATE_DAILY_LIMIT",
          value: String(settings.vipDocumentGenerateDailyLimit || "").trim(),
          category: "commercial",
        },
        {
          key: "enable_notifications",
          value: String(settings.enableNotifications),
          category: "notification",
        },
        {
          key: "maintenance_mode",
          value: String(settings.maintenanceMode),
          category: "security",
        },
      ];

      if (settings.newsReviewPolicyEnabled) {
        const raw = String(settings.newsReviewPolicyJson || "");
        if (raw.trim()) {
          try {
            const parsed: unknown = JSON.parse(raw);
            if (
              !parsed ||
              typeof parsed !== "object" ||
              Array.isArray(parsed)
            ) {
              toast.error(
                "NEWS_REVIEW_POLICY_JSON 必须是 JSON 对象（key: risk_level, value: approved/pending/rejected）"
              );
              return;
            }
            const allowed = new Set(["approved", "pending", "rejected"]);
            for (const [k, v] of Object.entries(
              parsed as Record<string, unknown>
            )) {
              const kk = String(k || "")
                .trim()
                .toLowerCase();
              const vv = String(v || "")
                .trim()
                .toLowerCase();
              if (!kk) continue;
              if (!allowed.has(vv)) {
                toast.error(`NEWS_REVIEW_POLICY_JSON 无效映射：${kk} -> ${vv}`);
                return;
              }
            }
          } catch {
            toast.error("NEWS_REVIEW_POLICY_JSON 必须是合法 JSON");
            return;
          }
        }
      }

      if (String(settings.contractReviewRulesJson || "").trim()) {
        try {
          const parsed: unknown = JSON.parse(String(settings.contractReviewRulesJson || ""));
          if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            toast.error("CONTRACT_REVIEW_RULES_JSON 必须是 JSON 对象");
            return;
          }
          const obj = parsed as Record<string, unknown>;

          const required = obj["required_clauses"];
          if (required !== undefined && !Array.isArray(required)) {
            toast.error("CONTRACT_REVIEW_RULES_JSON.required_clauses 必须是数组");
            return;
          }

          const riskKeywords = obj["risk_keywords"];
          if (riskKeywords !== undefined && !Array.isArray(riskKeywords)) {
            toast.error("CONTRACT_REVIEW_RULES_JSON.risk_keywords 必须是数组");
            return;
          }

          if (Array.isArray(riskKeywords)) {
            const allowed = new Set(["low", "medium", "high", ""]);
            for (const it of riskKeywords) {
              if (!it || typeof it !== "object" || Array.isArray(it)) continue;
              const anyIt = it as any;
              const sev = String(anyIt?.severity ?? "").trim().toLowerCase();
              if (!allowed.has(sev)) {
                toast.error(`CONTRACT_REVIEW_RULES_JSON.risk_keywords.severity 无效：${sev}`);
                return;
              }
            }
          }
        } catch {
          toast.error("CONTRACT_REVIEW_RULES_JSON 必须是合法 JSON");
          return;
        }
      }

      const maskedPlaceholder = "••••••••••••••••";
      if (
        settings.newsAiProvidersJson &&
        settings.newsAiProvidersJson !== maskedPlaceholder
      ) {
        const scopeRaw = String((settings as any).newsAiProvidersScope || "default").trim();
        const scope = scopeRaw && scopeRaw !== "default" ? scopeRaw : "default";
        const key =
          scope === "default"
            ? "NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON"
            : `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON_${scope}`;
        configs.push({
          key,
          value: settings.newsAiProvidersJson,
          category: "news_ai",
        });
      }

      const vipDays = Number(String(settings.vipDefaultDays || "").trim());
      if (!Number.isFinite(vipDays) || vipDays <= 0) {
        toast.error("VIP_DEFAULT_DAYS 必须是大于 0 的数字");
        return;
      }
      const vipPrice = Number(String(settings.vipDefaultPrice || "").trim());
      if (!Number.isFinite(vipPrice) || vipPrice <= 0) {
        toast.error("VIP_DEFAULT_PRICE 必须是大于 0 的数字");
        return;
      }

      const freeAi = Number(String(settings.freeAiChatDailyLimit || "").trim());
      const vipAi = Number(String(settings.vipAiChatDailyLimit || "").trim());
      const freeDoc = Number(String(settings.freeDocumentGenerateDailyLimit || "").trim());
      const vipDoc = Number(String(settings.vipDocumentGenerateDailyLimit || "").trim());
      if (!Number.isFinite(freeAi) || freeAi < 0) {
        toast.error("FREE_AI_CHAT_DAILY_LIMIT 必须是大于等于 0 的数字");
        return;
      }
      if (!Number.isFinite(vipAi) || vipAi < 0) {
        toast.error("VIP_AI_CHAT_DAILY_LIMIT 必须是大于等于 0 的数字");
        return;
      }
      if (!Number.isFinite(freeDoc) || freeDoc < 0) {
        toast.error("FREE_DOCUMENT_GENERATE_DAILY_LIMIT 必须是大于等于 0 的数字");
        return;
      }
      if (!Number.isFinite(vipDoc) || vipDoc < 0) {
        toast.error("VIP_DOCUMENT_GENERATE_DAILY_LIMIT 必须是大于等于 0 的数字");
        return;
      }

      if (String(settings.aiChatPackOptionsJson || "").trim()) {
        try {
          const parsed: unknown = JSON.parse(String(settings.aiChatPackOptionsJson || ""));
          if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            throw new Error("AI_CHAT_PACK_OPTIONS_JSON 必须为对象 JSON");
          }
        } catch (e) {
          toast.error("AI咨询次数包配置 JSON 格式不正确");
          return;
        }
      }

      if (String(settings.documentGeneratePackOptionsJson || "").trim()) {
        try {
          const parsed: unknown = JSON.parse(
            String(settings.documentGeneratePackOptionsJson || "")
          );
          if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            throw new Error("DOCUMENT_GENERATE_PACK_OPTIONS_JSON 必须为对象 JSON");
          }
        } catch (e) {
          toast.error("文书生成次数包配置 JSON 格式不正确");
          return;
        }
      }

      if (saveMutation.isPending) return;
      saveMutation.mutate({ configs });
    } catch (e) {
      toast.error(getApiErrorMessage(e, "保存失败，请稍后重试"));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          系统设置
        </h1>
        <p className="text-slate-600 mt-1 dark:text-white/50">
          配置系统参数和功能开关
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabItems.map((t) => {
          const Icon = t.icon;
          const isActive = activeTab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveTab(t.key)}
              className={
                "inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all outline-none focus-visible:ring-2 focus-visible:ring-amber-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 " +
                (isActive
                  ? "bg-amber-500 border-amber-500 text-white"
                  : "bg-white border-slate-200/70 text-slate-700 hover:bg-slate-50 hover:border-slate-300 dark:bg-white/5 dark:border-white/10 dark:text-white/70 dark:hover:bg-white/10 dark:hover:border-white/20")
              }
              aria-current={isActive ? "page" : undefined}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      <div className={activeTab === "base" ? "grid gap-6" : "grid lg:grid-cols-2 gap-6"}>
        {activeTab === "base" ? (
          <>
            {/* 基本设置 */}
            <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <Globe className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                基本设置
              </h3>
              <p className="text-slate-600 text-sm dark:text-white/40">
                网站基本信息配置
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <Input
              label="网站名称"
              value={settings.siteName}
              onChange={(e) =>
                setSettings({ ...settings, siteName: e.target.value })
              }
            />
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                网站描述
              </label>
              <textarea
                value={settings.siteDescription}
                onChange={(e) =>
                  setSettings({ ...settings, siteDescription: e.target.value })
                }
                rows={3}
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none resize-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              />
            </div>
            <Input
              label="联系邮箱"
              value={settings.contactEmail}
              onChange={(e) =>
                setSettings({ ...settings, contactEmail: e.target.value })
              }
            />
            <Input
              label="联系电话"
              value={settings.contactPhone}
              onChange={(e) =>
                setSettings({ ...settings, contactPhone: e.target.value })
              }
            />
          </div>
            </Card>
          </>
        ) : null}

        {activeTab === "commercial" ? (
          <>
            <Card variant="surface" padding="lg">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                  <CreditCard className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                    商业化配置
                  </h3>
                  <p className="text-slate-600 text-sm dark:text-white/40">
                    VIP 与次数包定价（保存后对新订单生效）
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <Input
                  label="VIP_DEFAULT_DAYS"
                  value={settings.vipDefaultDays}
                  onChange={(e) =>
                    setSettings({ ...settings, vipDefaultDays: e.target.value })
                  }
                  placeholder="30"
                />
                <Input
                  label="VIP_DEFAULT_PRICE"
                  value={settings.vipDefaultPrice}
                  onChange={(e) =>
                    setSettings({ ...settings, vipDefaultPrice: e.target.value })
                  }
                  placeholder="29"
                />
                <Textarea
                  label="AI_CHAT_PACK_OPTIONS_JSON"
                  value={settings.aiChatPackOptionsJson}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      aiChatPackOptionsJson: e.target.value,
                    })
                  }
                  placeholder='{
  "10": 12,
  "50": 49,
  "100": 79
}'
                />
                <Textarea
                  label="DOCUMENT_GENERATE_PACK_OPTIONS_JSON"
                  value={settings.documentGeneratePackOptionsJson}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      documentGeneratePackOptionsJson: e.target.value,
                    })
                  }
                  placeholder='{
  "10": 12,
  "50": 49,
  "100": 79
}'
                />
              </div>
            </Card>

            <Card variant="surface" padding="lg">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                  <CreditCard className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                    配额配置
                  </h3>
                  <p className="text-slate-600 text-sm dark:text-white/40">
                    每日可用次数（保存后对新请求生效）
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <Input
                  label="FREE_AI_CHAT_DAILY_LIMIT"
                  value={settings.freeAiChatDailyLimit}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      freeAiChatDailyLimit: e.target.value,
                    })
                  }
                  placeholder="5"
                />
                <Input
                  label="VIP_AI_CHAT_DAILY_LIMIT"
                  value={settings.vipAiChatDailyLimit}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      vipAiChatDailyLimit: e.target.value,
                    })
                  }
                  placeholder="1000000000"
                />
                <Input
                  label="FREE_DOCUMENT_GENERATE_DAILY_LIMIT"
                  value={settings.freeDocumentGenerateDailyLimit}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      freeDocumentGenerateDailyLimit: e.target.value,
                    })
                  }
                  placeholder="10"
                />
                <Input
                  label="VIP_DOCUMENT_GENERATE_DAILY_LIMIT"
                  value={settings.vipDocumentGenerateDailyLimit}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      vipDocumentGenerateDailyLimit: e.target.value,
                    })
                  }
                  placeholder="50"
                />
              </div>
            </Card>
          </>
        ) : null}

        {activeTab === "content" ? (
          <Card variant="surface" padding="lg">
          <div className="flex items-center justify-between gap-3 mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                <Sparkles className="h-5 w-5 text-purple-600 dark:text-purple-300" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  FAQ 自动生成
                </h3>
                <p className="text-slate-600 text-sm dark:text-white/40">
                  从最近好评咨询中提取高频问答，并发布到 /faq
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => faqPublicQuery.refetch()}
                isLoading={faqPublicQuery.isFetching}
                loadingText="刷新中..."
                icon={RotateCcw}
              >
                刷新
              </Button>
              <Button
                size="sm"
                onClick={() => generateFaqMutation.mutate()}
                isLoading={generateFaqMutation.isPending}
                loadingText="生成中..."
              >
                生成
              </Button>
            </div>
          </div>

          {faqPublicQuery.isLoading ? (
            <ListSkeleton count={3} />
          ) : faqPublicQuery.isError ? (
            <p className="text-sm text-red-600 dark:text-red-300">{getApiErrorMessage(faqPublicQuery.error)}</p>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-xl bg-slate-900/5 px-4 py-3 dark:bg-white/5">
                <div className="text-sm text-slate-700 dark:text-white/70">
                  当前公开 FAQ：{Array.isArray(faqPublicQuery.data?.items) ? faqPublicQuery.data?.items.length : 0} 条
                </div>
                <div className="text-xs text-slate-500 dark:text-white/40">
                  {faqPublicQuery.data?.updated_at ? `更新时间：${faqPublicQuery.data.updated_at}` : "更新时间：-"}
                </div>
              </div>

              {Array.isArray(faqPublicQuery.data?.items) && faqPublicQuery.data.items.length > 0 ? (
                <div className="space-y-3">
                  {faqPublicQuery.data.items.slice(0, 8).map((it, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-slate-200/70 bg-white px-4 py-3 dark:border-white/10 dark:bg-white/5"
                    >
                      <div className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-white">
                        <HelpCircle className="h-4 w-4 text-amber-500" />
                        {it.question}
                      </div>
                      <p className="mt-2 text-sm text-slate-600 dark:text-white/60">
                        {it.answer}
                      </p>
                    </div>
                  ))}
                  {faqPublicQuery.data.items.length > 8 ? (
                    <p className="text-xs text-slate-500 dark:text-white/40">仅展示前 8 条</p>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-slate-600 dark:text-white/40">暂无 FAQ（请点击“生成”）</p>
              )}
            </div>
          )}
          </Card>
        ) : null}

        {activeTab === "ai" ? (
          <>
            {/* AI咨询运维状态 */}
            <Card variant="surface" padding="lg">
          <div className="flex items-center justify-between gap-3 mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center">
                <Shield className="h-5 w-5 text-indigo-600 dark:text-indigo-300" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  AI咨询运维状态
                </h3>
                <p className="text-slate-600 text-sm dark:text-white/40">
                  AI咨询可用性、请求量、错误与最近错误
                </p>
              </div>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => aiOpsStatusQuery.refetch()}
              isLoading={aiOpsStatusQuery.isFetching}
            >
              刷新
            </Button>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/60 dark:bg-white/5 dark:border-white/10">
                <p className="text-xs text-slate-600 dark:text-white/40">AI路由启用</p>
                <p className="text-lg font-semibold text-slate-900 dark:text-white">
                  {aiOpsStatusQuery.data?.ai_router_enabled ? "是" : "否"}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/60 dark:bg-white/5 dark:border-white/10">
                <p className="text-xs text-slate-600 dark:text-white/40">OPENAI_API_KEY</p>
                <p className="text-lg font-semibold text-slate-900 dark:text-white">
                  {aiOpsStatusQuery.data?.openai_api_key_configured ? "已配置" : "未配置"}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/60 dark:bg-white/5 dark:border-white/10">
                <p className="text-xs text-slate-600 dark:text-white/40">chat 总请求</p>
                <p className="text-lg font-semibold text-slate-900 dark:text-white">
                  {aiOpsStatusQuery.data?.chat_requests_total ?? "-"}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/60 dark:bg-white/5 dark:border-white/10">
                <p className="text-xs text-slate-600 dark:text-white/40">stream 总请求</p>
                <p className="text-lg font-semibold text-slate-900 dark:text-white">
                  {aiOpsStatusQuery.data?.chat_stream_requests_total ?? "-"}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/60 dark:bg-white/5 dark:border-white/10">
                <p className="text-xs text-slate-600 dark:text-white/40">错误总数</p>
                <p className="text-lg font-semibold text-slate-900 dark:text-white">
                  {aiOpsStatusQuery.data?.errors_total ?? "-"}
                </p>
              </div>
            </div>

            <div className="text-sm text-slate-700 dark:text-white/70 space-y-1">
              <p>base_url：{aiOpsStatusQuery.data?.openai_base_url ?? "-"}</p>
              <p>model：{aiOpsStatusQuery.data?.ai_model ?? "-"}</p>
              <p>chroma：{aiOpsStatusQuery.data?.chroma_persist_dir ?? "-"}</p>
              <p>started_at：{aiOpsStatusQuery.data?.started_at_iso ?? "-"}</p>
            </div>

            {Array.isArray(aiOpsStatusQuery.data?.top_error_codes) &&
              (aiOpsStatusQuery.data?.top_error_codes?.length ?? 0) > 0 && (
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-white mb-2">
                    Top 错误码
                  </p>
                  <div className="space-y-2">
                    {(aiOpsStatusQuery.data?.top_error_codes ?? []).map((e, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl border border-slate-200/70 bg-white dark:bg-white/5 dark:border-white/10"
                      >
                        <p className="text-sm text-slate-900 dark:text-white">
                          {e.count} 次 - {e.error_code}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            {Array.isArray(aiOpsStatusQuery.data?.top_endpoints) &&
              (aiOpsStatusQuery.data?.top_endpoints?.length ?? 0) > 0 && (
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-white mb-2">
                    Top 端点
                  </p>
                  <div className="space-y-2">
                    {(aiOpsStatusQuery.data?.top_endpoints ?? []).map((e, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl border border-slate-200/70 bg-white dark:bg-white/5 dark:border-white/10"
                      >
                        <p className="text-sm text-slate-900 dark:text-white">
                          {e.count} 次 - {e.endpoint}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            <div>
              <p className="text-sm font-medium text-slate-900 dark:text-white mb-2">
                最近错误（最多 50 条）
              </p>
              <div className="space-y-2">
                {(aiOpsStatusQuery.data?.recent_errors ?? []).slice(0, 20).map((e, idx) => (
                  <div
                    key={`${e.request_id}-${idx}`}
                    className="p-3 rounded-xl border border-slate-200/70 bg-white dark:bg-white/5 dark:border-white/10"
                  >
                    <p className="text-sm text-slate-900 dark:text-white">
                      {e.endpoint} / {e.error_code}
                      {e.status_code != null ? `（${e.status_code}）` : ""}
                    </p>
                    <p className="text-xs text-slate-600 dark:text-white/40">{e.at}</p>
                    <p className="text-xs text-slate-600 dark:text-white/40 break-words">
                      请求ID：{e.request_id}
                    </p>
                    <p className="text-xs text-slate-600 dark:text-white/40 break-words">
                      {e.message || "-"}
                    </p>
                  </div>
                ))}
                {(!aiOpsStatusQuery.data ||
                  (aiOpsStatusQuery.data.recent_errors ?? []).length === 0) && (
                  <p className="text-sm text-slate-600 dark:text-white/40">暂无错误记录</p>
                )}
              </div>
            </div>
          </div>
            </Card>
          </>
        ) : null}

        {activeTab === "news_ai" ? (
          <>
            {/* 新闻AI配置 */}
            <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <Key className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                新闻AI配置
              </h3>
              <p className="text-slate-600 text-sm dark:text-white/40">
                摘要/要点/关键词的 LLM 配置（支持多 Provider）
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-slate-200/70 dark:border-white/5">
              <div>
                <p className="text-slate-900 font-medium dark:text-white">
                  启用新闻摘要 LLM
                </p>
                <p className="text-slate-600 text-sm dark:text-white/40">
                  关闭后会使用本地兜底规则生成
                </p>
              </div>
              <button
                onClick={() =>
                  setSettings({
                    ...settings,
                    newsAiSummaryLlmEnabled: !settings.newsAiSummaryLlmEnabled,
                  })
                }
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings.newsAiSummaryLlmEnabled
                    ? "bg-amber-500"
                    : "bg-slate-200 dark:bg-white/20"
                }`}
              >
                <div
                  className={`w-5 h-5 rounded-full bg-white transition-transform ${
                    settings.newsAiSummaryLlmEnabled
                      ? "translate-x-6"
                      : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                Provider 策略
              </label>
              <select
                value={settings.newsAiProviderStrategy}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    newsAiProviderStrategy: e.target.value,
                  })
                }
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              >
                <option value="priority">priority（按顺序优先）</option>
                <option value="round_robin">round_robin（轮询）</option>
                <option value="random">random（随机/权重）</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                Providers JSON 作用域
              </label>
              <select
                value={(settings as any).newsAiProvidersScope || "default"}
                onChange={(e) =>
                  setSettings((prev) => {
                    const scopeRaw = String(e.target.value || "default").trim();
                    const scope = scopeRaw && scopeRaw !== "default" ? scopeRaw : "default";
                    const providersKey =
                      scope === "default"
                        ? "NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON"
                        : `NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON_${scope}`;
                    const masked = "••••••••••••••••";
                    return {
                      ...prev,
                      newsAiProvidersScope: scopeRaw || "default",
                      newsAiProvidersJson: configMap[providersKey] ? masked : "",
                    };
                  })
                }
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              >
                <option value="default">default（不区分环境）</option>
                <option value="DEV">DEV</option>
                <option value="STAGING">STAGING</option>
                <option value="PROD">PROD</option>
              </select>
            </div>

            <Input
              label="response_format"
              placeholder="例如 json_object / json_schema / off"
              value={settings.newsAiResponseFormat}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  newsAiResponseFormat: e.target.value,
                })
              }
            />

            <Textarea
              label="Providers JSON（不回显已配置内容）"
              placeholder='例如：[{"name":"p1","base_url":"https://...","model":"gpt-4o-mini"}]'
              value={settings.newsAiProvidersJson}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  newsAiProvidersJson: e.target.value,
                })
              }
              rows={5}
            />
          </div>
            </Card>
          </>
        ) : null}

        {activeTab === "content" ? (
          <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
              <Shield className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                新闻审核策略
              </h3>
              <p className="text-slate-600 text-sm dark:text-white/40">
                基于 AI risk_level 自动调整 review_status（仅对 pending 生效）
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-slate-200/70 dark:border-white/5">
              <div>
                <p className="text-slate-900 font-medium dark:text-white">
                  启用自动审核策略
                </p>
                <p className="text-slate-600 text-sm dark:text-white/40">
                  例如 safe 自动通过、danger 进入待审/驳回
                </p>
              </div>
              <button
                onClick={() =>
                  setSettings({
                    ...settings,
                    newsReviewPolicyEnabled: !settings.newsReviewPolicyEnabled,
                  })
                }
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings.newsReviewPolicyEnabled
                    ? "bg-amber-500"
                    : "bg-slate-200 dark:bg-white/20"
                }`}
              >
                <div
                  className={`w-5 h-5 rounded-full bg-white transition-transform ${
                    settings.newsReviewPolicyEnabled
                      ? "translate-x-6"
                      : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>

            <Textarea
              label="NEWS_REVIEW_POLICY_JSON"
              placeholder='例如：{"safe":"approved","warning":"pending","danger":"pending","unknown":"pending"}'
              value={settings.newsReviewPolicyJson}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  newsReviewPolicyJson: e.target.value,
                })
              }
              rows={6}
            />
          </div>
          </Card>
        ) : null}

        {activeTab === "news_ai" ? (
          <>
            {/* 新闻AI运维状态 */}
            <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-slate-500/10 flex items-center justify-center">
              <Shield className="h-5 w-5 text-slate-600 dark:text-white/70" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                新闻AI运维状态
              </h3>
              <p className="text-slate-600 text-sm dark:text-white/40">
                积压量、错误统计、当前生效 Provider
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/60 dark:bg-white/5 dark:border-white/10">
                <p className="text-xs text-slate-600 dark:text-white/40">
                  待处理积压
                </p>
                <p className="text-lg font-semibold text-slate-900 dark:text-white">
                  {newsAiStatusQuery.data?.pending_total ?? "-"}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/60 dark:bg-white/5 dark:border-white/10">
                <p className="text-xs text-slate-600 dark:text-white/40">
                  有错误的条目
                </p>
                <p className="text-lg font-semibold text-slate-900 dark:text-white">
                  {newsAiStatusQuery.data?.errors_total ?? "-"}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/60 dark:bg-white/5 dark:border-white/10">
                <p className="text-xs text-slate-600 dark:text-white/40">
                  近 24h 错误
                </p>
                <p className="text-lg font-semibold text-slate-900 dark:text-white">
                  {newsAiStatusQuery.data?.errors_last_24h ?? "-"}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/60 dark:bg-white/5 dark:border-white/10">
                <p className="text-xs text-slate-600 dark:text-white/40">
                  近 7d 错误
                </p>
                <p className="text-lg font-semibold text-slate-900 dark:text-white">
                  {newsAiStatusQuery.data?.errors_last_7d ?? "-"}
                </p>
              </div>
            </div>

            <div className="text-sm text-slate-700 dark:text-white/70">
              <p>策略：{newsAiStatusQuery.data?.provider_strategy ?? "-"}</p>
              <p>
                response_format：
                {newsAiStatusQuery.data?.response_format ?? "-"}
              </p>
            </div>

            <div>
              <p className="text-sm font-medium text-slate-900 dark:text-white mb-2">
                Providers
              </p>
              <div className="space-y-2">
                {(newsAiStatusQuery.data?.providers ?? []).map((p, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl border border-slate-200/70 bg-white dark:bg-white/5 dark:border-white/10"
                  >
                    <p className="text-sm text-slate-900 dark:text-white font-medium">
                      {p.name || p.base_url}
                    </p>
                    <p className="text-xs text-slate-600 dark:text-white/40">
                      {p.base_url}
                    </p>
                    <p className="text-xs text-slate-600 dark:text-white/40">
                      model：{p.model || "-"}
                    </p>
                    <p className="text-xs text-slate-600 dark:text-white/40">
                      api_key：{p.api_key_configured ? "已配置" : "未配置"}
                    </p>
                  </div>
                ))}
                {(!newsAiStatusQuery.data ||
                  (newsAiStatusQuery.data.providers ?? []).length === 0) && (
                  <p className="text-sm text-slate-600 dark:text-white/40">
                    暂无 provider 配置
                  </p>
                )}
              </div>
            </div>

            <div>
              <p className="text-sm font-medium text-slate-900 dark:text-white mb-2">
                近 7 天错误趋势
              </p>
              {(() => {
                const trend = newsAiStatusQuery.data?.errors_trend_7d ?? [];
                const points = trend.map((t) => {
                  const d = new Date(t.date);
                  const label = Number.isNaN(d.getTime())
                    ? String(t.date).slice(5)
                    : `${d.getMonth() + 1}/${d.getDate()}`;
                  return { label, value: Number(t.errors || 0) };
                });
                if (!points || points.length === 0) {
                  return (
                    <p className="text-sm text-slate-600 dark:text-white/40">
                      暂无趋势数据
                    </p>
                  );
                }
                return (
                  <SimpleMiniBarChart
                    data={points}
                    maxValue={Math.max(1, ...points.map((p) => p.value))}
                  />
                );
              })()}
            </div>

            <div>
              <p className="text-sm font-medium text-slate-900 dark:text-white mb-2">
                Top 错误（最多 10 条）
              </p>
              <div className="space-y-2">
                {(newsAiStatusQuery.data?.top_errors ?? []).map((e, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl border border-slate-200/70 bg-white dark:bg-white/5 dark:border-white/10"
                  >
                    <p className="text-sm text-slate-900 dark:text-white">
                      {e.count} 次
                    </p>
                    <p className="text-xs text-slate-600 dark:text-white/40 break-words">
                      {e.message}
                    </p>
                  </div>
                ))}
                {(!newsAiStatusQuery.data ||
                  (newsAiStatusQuery.data.top_errors ?? []).length === 0) && (
                  <p className="text-sm text-slate-600 dark:text-white/40">
                    暂无错误 Top 统计
                  </p>
                )}
              </div>
            </div>

            <div>
              <p className="text-sm font-medium text-slate-900 dark:text-white mb-2">
                最近错误（最多 20 条）
              </p>
              <div className="space-y-2">
                {(newsAiStatusQuery.data?.recent_errors ?? []).map((e) => (
                  <div
                    key={e.news_id}
                    className="p-3 rounded-xl border border-slate-200/70 bg-white dark:bg-white/5 dark:border-white/10"
                  >
                    <p className="text-sm text-slate-900 dark:text-white">
                      news_id：{e.news_id}（重试 {e.retry_count}）
                    </p>
                    <p className="text-xs text-slate-600 dark:text-white/40">
                      {e.last_error_at || "-"}
                    </p>
                    <p className="text-xs text-slate-600 dark:text-white/40">
                      {e.last_error || "-"}
                    </p>
                  </div>
                ))}
                {(!newsAiStatusQuery.data ||
                  (newsAiStatusQuery.data.recent_errors ?? []).length ===
                    0) && (
                  <p className="text-sm text-slate-600 dark:text-white/40">
                    暂无错误记录
                  </p>
                )}
              </div>
            </div>
          </div>
            </Card>
          </>
        ) : null}

        {activeTab === "ai" ? (
          <>
            {/* AI设置 */}
            <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
              <Key className="h-5 w-5 text-purple-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                AI配置
              </h3>
              <p className="text-slate-600 text-sm dark:text-white/40">
                AI助手相关配置
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <Input
              label="OpenAI API Key（通过部署环境变量配置）"
              type="password"
              value={""}
              placeholder="请在部署环境设置 OPENAI_API_KEY"
              disabled
            />
            <div className="flex items-center justify-between py-3 border-b border-slate-200/70 dark:border-white/5">
              <div>
                <p className="text-slate-900 font-medium dark:text-white">
                  启用AI助手
                </p>
                <p className="text-slate-600 text-sm dark:text-white/40">
                  开启后用户可使用AI法律咨询
                </p>
              </div>
              <button
                onClick={() =>
                  setSettings({ ...settings, enableAI: !settings.enableAI })
                }
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings.enableAI
                    ? "bg-amber-500"
                    : "bg-slate-200 dark:bg-white/20"
                }`}
              >
                <div
                  className={`w-5 h-5 rounded-full bg-white transition-transform ${
                    settings.enableAI ? "translate-x-6" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>

            <Textarea
              label="CONTRACT_REVIEW_RULES_JSON"
              placeholder='例如：{ "required_clauses":[{"name":"争议解决","patterns":["仲裁","诉讼"]}], "risk_keywords":[{"keyword":"不可撤销","severity":"medium"}] }'
              value={settings.contractReviewRulesJson}
              onChange={(e) =>
                setSettings({ ...settings, contractReviewRulesJson: e.target.value })
              }
            />
          </div>
            </Card>
          </>
        ) : null}

        {activeTab === "notify" ? (
          <>
            {/* 通知设置 */}
            <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
              <Bell className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                通知设置
              </h3>
              <p className="text-slate-600 text-sm dark:text-white/40">
                系统通知配置
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-slate-200/70 dark:border-white/5">
              <div>
                <p className="text-slate-900 font-medium dark:text-white">
                  启用通知
                </p>
                <p className="text-slate-600 text-sm dark:text-white/40">
                  发送系统通知给用户
                </p>
              </div>
              <button
                onClick={() =>
                  setSettings({
                    ...settings,
                    enableNotifications: !settings.enableNotifications,
                  })
                }
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings.enableNotifications
                    ? "bg-amber-500"
                    : "bg-slate-200 dark:bg-white/20"
                }`}
              >
                <div
                  className={`w-5 h-5 rounded-full bg-white transition-transform ${
                    settings.enableNotifications
                      ? "translate-x-6"
                      : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>

            <Textarea
              label="CONSULT_REVIEW_SLA_JSON"
              placeholder='例如：{"pending_sla_minutes":1440,"claimed_sla_minutes":720,"remind_before_minutes":60}'
              value={(settings as any).consultReviewSlaJson}
              onChange={(e) =>
                setSettings({ ...(settings as any), consultReviewSlaJson: e.target.value })
              }
              rows={5}
            />
          </div>
            </Card>

            {/* 维护模式 */}
            <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
              <Shield className="h-5 w-5 text-red-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                维护模式
              </h3>
              <p className="text-slate-600 text-sm dark:text-white/40">
                系统维护设置
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-slate-200/70 dark:border-white/5">
              <div>
                <p className="text-slate-900 font-medium dark:text-white">
                  开启维护模式
                </p>
                <p className="text-slate-600 text-sm dark:text-white/40">
                  开启后普通用户无法访问网站
                </p>
              </div>
              <button
                onClick={() =>
                  setSettings({
                    ...settings,
                    maintenanceMode: !settings.maintenanceMode,
                  })
                }
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings.maintenanceMode
                    ? "bg-red-500"
                    : "bg-slate-200 dark:bg-white/20"
                }`}
              >
                <div
                  className={`w-5 h-5 rounded-full bg-white transition-transform ${
                    settings.maintenanceMode
                      ? "translate-x-6"
                      : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>
          </div>
            </Card>
          </>
        ) : null}
      </div>

      <div className="flex justify-end">
        <Button
          icon={Save}
          onClick={handleSave}
          isLoading={saveMutation.isPending}
          className="px-8"
        >
          保存设置
        </Button>
      </div>
    </div>
  );
}
