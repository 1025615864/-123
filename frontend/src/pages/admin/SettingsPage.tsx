import { useState, useEffect } from "react";
import { Save, Key, Globe, Bell, Shield } from "lucide-react";
import { Card, Input, Button, Textarea } from "../../components/ui";
import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import { queryKeys } from "../../queryKeys";
import { useMemo } from "react";

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
    contactEmail: "contact@example.com",
    contactPhone: "400-123-4567",
    enableAI: true,
    newsAiSummaryLlmEnabled: false,
    newsAiProviderStrategy: "priority",
    newsAiResponseFormat: "",
    newsAiProvidersScope: "default",
    newsAiProvidersJson: "",
    newsReviewPolicyEnabled: false,
    newsReviewPolicyJson:
      '{\n  "safe": "approved",\n  "warning": "pending",\n  "danger": "pending",\n  "unknown": "pending"\n}',
    enableNotifications: true,
    maintenanceMode: false,
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

  useEffect(() => {
    if (!newsAiStatusQuery.error) return;
    toast.error(
      getApiErrorMessage(newsAiStatusQuery.error, "新闻AI状态加载失败")
    );
  }, [newsAiStatusQuery.error, toast]);

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

      if (saveMutation.isPending) return;
      saveMutation.mutate({ configs });
    } catch {
      // 错误已处理
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

      <div className="grid lg:grid-cols-2 gap-6">
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
          </div>
        </Card>

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
