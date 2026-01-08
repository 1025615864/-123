import { useEffect, useMemo, useState } from "react";
import {
  CreditCard,
  RefreshCw,
  Filter,
  ShieldCheck,
  ShieldAlert,
  KeyRound,
  Search,
  Copy,
  Eye,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import {
  Card,
  Input,
  Button,
  Badge,
  Pagination,
  Textarea,
  Modal,
  ModalActions,
  ListSkeleton,
  Skeleton,
} from "../../components/ui";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import { queryKeys } from "../../queryKeys";

type CallbackEventItem = {
  id: number;
  provider: string;
  order_no: string | null;
  trade_no: string | null;
  amount: number | null;
  verified: boolean;
  error_message: string | null;
  created_at: string;
};

type CallbackEventsResponse = {
  items: CallbackEventItem[];
  total: number;
};

type CallbackStatsResponse = {
  minutes: number;
  provider: string | null;
  all_total: number;
  all_verified: number;
  all_failed: number;
  window_total: number;
  window_verified: number;
  window_failed: number;
};

type PlatformCertItem = { serial_no: string; expire_time: string | null };

type PlatformCertListResponse = {
  items: PlatformCertItem[];
  total: number;
};

type PaymentChannelStatusResponse = {
  alipay_configured: boolean;
  wechatpay_configured: boolean;
  ikunpay_configured: boolean;
  payment_webhook_secret_configured: boolean;
  wechatpay_platform_certs_cached: boolean;
  wechatpay_platform_certs_total: number;
  wechatpay_platform_certs_updated_at: number | null;
  wechatpay_cert_refresh_enabled: boolean;
  details: Record<string, unknown>;
};

type ReconcileResponse = {
  order_no: string;
  order_status: string;
  payment_method: string | null;
  actual_amount: number;
  trade_no: string | null;
  callbacks_total: number;
  callbacks_verified: number;
  callbacks_failed: number;
  diagnosis: string;
  details: Record<string, unknown>;
  paid_at: string | null;
  recent_events: Array<{
    provider: string;
    order_no: string | null;
    trade_no: string | null;
    amount: number | null;
    verified: boolean;
    error_message: string | null;
    created_at: string;
  }>;
};

type CallbackEventDetailResponse = CallbackEventItem & {
  raw_payload: string | null;
  masked_payload: string | null;
};

function formatTime(dateStr: string) {
  const date = new Date(dateStr);
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function providerLabel(provider: string) {
  const p = String(provider || "").toLowerCase();
  if (p === "alipay") return "支付宝";
  if (p === "ikunpay") return "爱坤支付";
  if (p === "wechat") return "微信";
  return provider;
}

function diagnosisLabel(d: string) {
  switch (d) {
    case "ok":
      return { label: "正常", color: "success" as const };
    case "no_callback":
      return { label: "无回调", color: "warning" as const };
    case "amount_mismatch":
      return { label: "金额不一致", color: "danger" as const };
    case "decrypt_failed":
      return { label: "解密失败", color: "danger" as const };
    case "signature_failed":
      return { label: "验签失败", color: "danger" as const };
    case "paid_without_success_callback":
      return { label: "已支付但无成功回调", color: "warning" as const };
    case "success_callback_but_order_not_paid":
      return { label: "有成功回调但订单未支付", color: "warning" as const };
    default:
      return { label: d || "unknown", color: "info" as const };
  }
}

export default function PaymentCallbacksPage() {
  const toast = useToast();

  const [page, setPage] = useState(1);
  const pageSize = 50;

  const [provider, setProvider] = useState("");
  const [orderNo, setOrderNo] = useState("");
  const [tradeNo, setTradeNo] = useState("");
  const [verified, setVerified] = useState<"" | "true" | "false">("");

  const [statsMinutes, setStatsMinutes] = useState(60);

  const [reconcileOrderNo, setReconcileOrderNo] = useState("");
  const [reconcileResult, setReconcileResult] =
    useState<ReconcileResponse | null>(null);

  const [payloadModalOpen, setPayloadModalOpen] = useState(false);
  const [payloadLoading, setPayloadLoading] = useState(false);
  const [payloadEvent, setPayloadEvent] =
    useState<CallbackEventDetailResponse | null>(null);
  const [payloadShowRaw, setPayloadShowRaw] = useState(false);

  const [platformCertImportJson, setPlatformCertImportJson] = useState("");
  const [platformCertImportPem, setPlatformCertImportPem] = useState("");
  const [platformCertImportSerialNo, setPlatformCertImportSerialNo] =
    useState("");
  const [platformCertImportExpireTime, setPlatformCertImportExpireTime] =
    useState("");
  const [platformCertImportMerge, setPlatformCertImportMerge] = useState(true);

  const listQueryKey = useMemo(
    () =>
      queryKeys.adminPaymentCallbackEvents(
        page,
        pageSize,
        provider.trim(),
        orderNo.trim(),
        tradeNo.trim(),
        verified
      ),
    [page, pageSize, provider, orderNo, tradeNo, verified]
  );

  const listQuery = useQuery({
    queryKey: listQueryKey,
    queryFn: async () => {
      const res = await api.get("/payment/admin/callback-events", {
        params: {
          page,
          page_size: pageSize,
          ...(provider.trim() ? { provider: provider.trim() } : {}),
          ...(orderNo.trim() ? { order_no: orderNo.trim() } : {}),
          ...(tradeNo.trim() ? { trade_no: tradeNo.trim() } : {}),
          ...(verified ? { verified: verified === "true" } : {}),
        },
      });
      const data = res.data;
      return {
        items: Array.isArray(data?.items)
          ? (data.items as CallbackEventItem[])
          : ([] as CallbackEventItem[]),
        total: Number(data?.total || 0),
      } satisfies CallbackEventsResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const statsQuery = useQuery({
    queryKey: queryKeys.adminPaymentCallbackStats(
      statsMinutes,
      provider.trim() || null
    ),
    queryFn: async () => {
      const res = await api.get("/payment/admin/callback-events/stats", {
        params: {
          minutes: statsMinutes,
          ...(provider.trim() ? { provider: provider.trim() } : {}),
        },
      });
      return res.data as CallbackStatsResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const channelStatusQuery = useQuery({
    queryKey: ["admin-payment-channel-status"],
    queryFn: async () => {
      const res = await api.get("/payment/admin/channel-status");
      return res.data as PaymentChannelStatusResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const platformCertsQuery = useQuery({
    queryKey: queryKeys.adminWeChatPlatformCerts(),
    queryFn: async () => {
      const res = await api.get("/payment/admin/wechat/platform-certs");
      const data = res.data;
      return {
        items: Array.isArray(data?.items)
          ? (data.items as PlatformCertItem[])
          : ([] as PlatformCertItem[]),
        total: Number(data?.total || 0),
      } satisfies PlatformCertListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (listQuery.error) toast.error(getApiErrorMessage(listQuery.error));
  }, [listQuery.error, toast]);

  useEffect(() => {
    if (statsQuery.error) toast.error(getApiErrorMessage(statsQuery.error));
  }, [statsQuery.error, toast]);

  useEffect(() => {
    if (platformCertsQuery.error)
      toast.error(getApiErrorMessage(platformCertsQuery.error));
  }, [platformCertsQuery.error, toast]);

  useEffect(() => {
    if (channelStatusQuery.error)
      toast.error(getApiErrorMessage(channelStatusQuery.error));
  }, [channelStatusQuery.error, toast]);

  const refreshCertsMutation = useAppMutation<
    { message: string; count: number },
    void
  >({
    mutationFn: async () => {
      const res = await api.post(
        "/payment/admin/wechat/platform-certs/refresh"
      );
      return res.data as { message: string; count: number };
    },
    errorMessageFallback: "刷新失败",
    invalidateQueryKeys: [queryKeys.adminWeChatPlatformCerts()],
    onSuccess: (data) => {
      toast.success(`已刷新平台证书：${Number((data as any)?.count ?? 0)} 条`);
    },
  });

  const importCertsMutation = useAppMutation<
    { message: string; count: number },
    {
      platform_certs_json?: string;
      cert_pem?: string;
      serial_no?: string;
      expire_time?: string;
      merge: boolean;
    }
  >({
    mutationFn: async (payload) => {
      const res = await api.post(
        "/payment/admin/wechat/platform-certs/import",
        payload
      );
      return res.data as { message: string; count: number };
    },
    errorMessageFallback: "导入失败",
    invalidateQueryKeys: [
      queryKeys.adminWeChatPlatformCerts(),
      ["admin-payment-channel-status"],
    ],
    onSuccess: (data) => {
      toast.success(`已导入平台证书：${Number((data as any)?.count ?? 0)} 条`);
      setPlatformCertImportJson("");
      setPlatformCertImportPem("");
      setPlatformCertImportSerialNo("");
      setPlatformCertImportExpireTime("");
    },
  });

  const reconcileMutation = useAppMutation<ReconcileResponse, string>({
    mutationFn: async (orderNoValue) => {
      const res = await api.get(
        `/payment/admin/reconcile/${encodeURIComponent(orderNoValue)}`
      );
      return res.data as ReconcileResponse;
    },
    errorMessageFallback: "对账失败",
    onSuccess: (data) => {
      setReconcileResult(data);
    },
  });

  const eventDetailMutation = useAppMutation<
    CallbackEventDetailResponse,
    number
  >({
    mutationFn: async (eventId) => {
      const res = await api.get(
        `/payment/admin/callback-events/${encodeURIComponent(String(eventId))}`
      );
      return res.data as CallbackEventDetailResponse;
    },
    errorMessageFallback: "加载回调详情失败",
    onSuccess: (data) => {
      setPayloadEvent(data);
    },
    onError: () => {
      setPayloadEvent(null);
    },
  });

  const total = listQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const items = listQuery.data?.items ?? [];

  const stat = statsQuery.data;

  const clearFilters = () => {
    setProvider("");
    setOrderNo("");
    setTradeNo("");
    setVerified("");
    setPage(1);
  };

  const doReconcile = () => {
    const v = reconcileOrderNo.trim();
    if (!v) {
      toast.error("请输入订单号");
      return;
    }
    setReconcileResult(null);
    reconcileMutation.mutate(v);
  };

  const doReconcileByOrderNo = (value: string) => {
    const v = String(value || "").trim();
    if (!v) {
      toast.error("该回调事件未包含订单号");
      return;
    }
    setReconcileOrderNo(v);
    setReconcileResult(null);
    reconcileMutation.mutate(v);
  };

  const openPayloadModal = async (eventId: number) => {
    setPayloadModalOpen(true);
    setPayloadLoading(true);
    setPayloadEvent(null);
    setPayloadShowRaw(false);
    try {
      await eventDetailMutation.mutateAsync(eventId);
    } finally {
      setPayloadLoading(false);
    }
  };

  const reconcileBadge = reconcileResult
    ? diagnosisLabel(String(reconcileResult.diagnosis || ""))
    : null;

  const alipayDetails = (channelStatusQuery.data?.details as any)?.alipay as
    | {
        app_id_set?: boolean;
        public_key_set?: boolean;
        private_key_set?: boolean;
        notify_url_set?: boolean;
        public_key_check?: {
          ok?: boolean;
          key_size?: number;
          error?: string;
        } | null;
        private_key_check?: {
          ok?: boolean;
          key_size?: number;
          error?: string;
        } | null;
        gateway_url?: string | null;
        notify_url?: string | null;
        return_url?: string | null;
        effective_return_url?: string | null;
      }
    | undefined;

  const handleCopyText = async (value: string, label: string) => {
    const v = String(value || "").trim();
    if (!v) {
      toast.error(`${label} 为空`);
      return;
    }
    try {
      await navigator.clipboard.writeText(v);
      toast.success(`已复制${label}`);
    } catch {
      toast.error(`复制${label}失败，请手动复制`);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            支付回调审计
          </h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">
            回调事件列表、统计、微信平台证书、订单对账
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            icon={RefreshCw}
            onClick={() => {
              listQuery.refetch();
              statsQuery.refetch();
              platformCertsQuery.refetch();
              channelStatusQuery.refetch();
            }}
            isLoading={
              listQuery.isFetching ||
              statsQuery.isFetching ||
              platformCertsQuery.isFetching ||
              channelStatusQuery.isFetching
            }
            loadingText="刷新中..."
            disabled={
              listQuery.isFetching ||
              statsQuery.isFetching ||
              platformCertsQuery.isFetching ||
              channelStatusQuery.isFetching
            }
          >
            刷新
          </Button>
        </div>
      </div>

      <Card variant="surface" padding="md">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
              支付渠道配置状态
            </h2>
            <p className="text-slate-600 text-sm mt-1 dark:text-white/50">
              出于安全原因不会回显密钥，仅展示是否已配置与就绪状态
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-5 gap-3">
          <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
            <div className="text-xs text-slate-500 dark:text-white/40">
              支付宝
            </div>
            <div className="mt-1">
              {channelStatusQuery.isLoading ? (
                <Skeleton width="72px" height="18px" />
              ) : channelStatusQuery.data?.alipay_configured ? (
                <Badge variant="success" size="sm">
                  已配置
                </Badge>
              ) : (
                <Badge variant="warning" size="sm">
                  未配置
                </Badge>
              )}
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
            <div className="text-xs text-slate-500 dark:text-white/40">
              爱坤支付
            </div>
            <div className="mt-1">
              {channelStatusQuery.isLoading ? (
                <Skeleton width="72px" height="18px" />
              ) : channelStatusQuery.data?.ikunpay_configured ? (
                <Badge variant="success" size="sm">
                  已配置
                </Badge>
              ) : (
                <Badge variant="warning" size="sm">
                  未配置
                </Badge>
              )}
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
            <div className="text-xs text-slate-500 dark:text-white/40">
              微信支付
            </div>
            <div className="mt-1">
              {channelStatusQuery.isLoading ? (
                <Skeleton width="72px" height="18px" />
              ) : channelStatusQuery.data?.wechatpay_configured ? (
                <Badge variant="success" size="sm">
                  已配置
                </Badge>
              ) : (
                <Badge variant="warning" size="sm">
                  未配置
                </Badge>
              )}
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
            <div className="text-xs text-slate-500 dark:text-white/40">
              平台证书缓存
            </div>
            <div className="mt-1">
              {channelStatusQuery.isLoading ? (
                <Skeleton width="72px" height="18px" />
              ) : channelStatusQuery.data?.wechatpay_platform_certs_cached ? (
                <Badge variant="success" size="sm">
                  {channelStatusQuery.data?.wechatpay_platform_certs_total ?? 0}{" "}
                  条
                </Badge>
              ) : (
                <Badge variant="warning" size="sm">
                  无
                </Badge>
              )}
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
            <div className="text-xs text-slate-500 dark:text-white/40">
              证书自动刷新
            </div>
            <div className="mt-1">
              {channelStatusQuery.isLoading ? (
                <Skeleton width="72px" height="18px" />
              ) : channelStatusQuery.data?.wechatpay_cert_refresh_enabled ? (
                <Badge variant="success" size="sm">
                  已启用
                </Badge>
              ) : (
                <Badge variant="info" size="sm">
                  未启用
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
            <div className="text-sm font-semibold text-slate-900 dark:text-white">
              支付宝配置明细
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="text-xs text-slate-500 dark:text-white/40">
                APP_ID
              </div>
              <div className="text-xs">
                {alipayDetails?.app_id_set ? (
                  <Badge variant="success" size="sm">
                    已配置
                  </Badge>
                ) : (
                  <Badge variant="warning" size="sm">
                    未配置
                  </Badge>
                )}
              </div>

              <div className="text-xs text-slate-500 dark:text-white/40">
                PUBLIC_KEY
              </div>
              <div className="text-xs">
                {alipayDetails?.public_key_set ? (
                  <Badge variant="success" size="sm">
                    已配置
                  </Badge>
                ) : (
                  <Badge variant="warning" size="sm">
                    未配置
                  </Badge>
                )}
              </div>

              <div className="text-xs text-slate-500 dark:text-white/40">
                PUBLIC_KEY 自检
              </div>
              <div className="text-xs">
                {alipayDetails?.public_key_check ? (
                  alipayDetails.public_key_check.ok ? (
                    <Badge variant="success" size="sm">
                      通过
                      {alipayDetails.public_key_check.key_size
                        ? `（${alipayDetails.public_key_check.key_size}）`
                        : ""}
                    </Badge>
                  ) : (
                    <Badge variant="danger" size="sm">
                      失败
                    </Badge>
                  )
                ) : (
                  "-"
                )}
              </div>

              <div className="text-xs text-slate-500 dark:text-white/40">
                PRIVATE_KEY
              </div>
              <div className="text-xs">
                {alipayDetails?.private_key_set ? (
                  <Badge variant="success" size="sm">
                    已配置
                  </Badge>
                ) : (
                  <Badge variant="warning" size="sm">
                    未配置
                  </Badge>
                )}
              </div>

              <div className="text-xs text-slate-500 dark:text-white/40">
                PRIVATE_KEY 自检
              </div>
              <div className="text-xs">
                {alipayDetails?.private_key_check ? (
                  alipayDetails.private_key_check.ok ? (
                    <Badge variant="success" size="sm">
                      通过
                      {alipayDetails.private_key_check.key_size
                        ? `（${alipayDetails.private_key_check.key_size}）`
                        : ""}
                    </Badge>
                  ) : (
                    <Badge variant="danger" size="sm">
                      失败
                    </Badge>
                  )
                ) : (
                  "-"
                )}
              </div>

              <div className="text-xs text-slate-500 dark:text-white/40">
                NOTIFY_URL
              </div>
              <div className="text-xs">
                {alipayDetails?.notify_url_set ? (
                  <Badge variant="success" size="sm">
                    已配置
                  </Badge>
                ) : (
                  <Badge variant="warning" size="sm">
                    未配置
                  </Badge>
                )}
              </div>
            </div>

            {alipayDetails?.public_key_check &&
            !alipayDetails.public_key_check.ok ? (
              <div className="mt-3 text-xs text-red-600 dark:text-red-400 break-all">
                PUBLIC_KEY 自检失败：
                {String(alipayDetails.public_key_check.error || "").trim() ||
                  "未知错误"}
              </div>
            ) : null}
            {alipayDetails?.private_key_check &&
            !alipayDetails.private_key_check.ok ? (
              <div className="mt-2 text-xs text-red-600 dark:text-red-400 break-all">
                PRIVATE_KEY 自检失败：
                {String(alipayDetails.private_key_check.error || "").trim() ||
                  "未知错误"}
              </div>
            ) : null}

            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div className="text-xs text-slate-600 dark:text-white/60 break-all">
                  notify_url: {alipayDetails?.notify_url || "-"}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={Copy}
                  onClick={() =>
                    void handleCopyText(
                      String(alipayDetails?.notify_url || ""),
                      "notify_url"
                    )
                  }
                  disabled={!alipayDetails?.notify_url}
                >
                  复制
                </Button>
              </div>

              <div className="flex items-center justify-between gap-3">
                <div className="text-xs text-slate-600 dark:text-white/60 break-all">
                  return_url: {alipayDetails?.return_url || "-"}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={Copy}
                  onClick={() =>
                    void handleCopyText(
                      String(alipayDetails?.return_url || ""),
                      "return_url"
                    )
                  }
                  disabled={!alipayDetails?.return_url}
                >
                  复制
                </Button>
              </div>

              <div className="flex items-center justify-between gap-3">
                <div className="text-xs text-slate-600 dark:text-white/60 break-all">
                  effective_return_url:{" "}
                  {alipayDetails?.effective_return_url || "-"}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={Copy}
                  onClick={() =>
                    void handleCopyText(
                      String(alipayDetails?.effective_return_url || ""),
                      "effective_return_url"
                    )
                  }
                  disabled={!alipayDetails?.effective_return_url}
                >
                  复制
                </Button>
              </div>

              <div className="text-xs text-slate-600 dark:text-white/60 break-all">
                gateway_url: {alipayDetails?.gateway_url || "-"}
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
            <div className="text-sm font-semibold text-slate-900 dark:text-white">
              联调提示
            </div>
            <div className="mt-3 text-xs text-slate-600 dark:text-white/60 space-y-2">
              <div>
                - 支付宝后台配置的异步通知地址必须与 notify_url
                一致（必须公网可访问）。
              </div>
              <div>
                - 回跳页 return_url 用于用户浏览器跳转；真实支付以 notify 为准。
              </div>
              <div>
                -
                如订单未更新：先查“回调事件列表”是否有验签失败/金额不一致，再用“订单对账”定位原因。
              </div>
            </div>
          </div>
        </div>

        <div className="mt-3 text-xs text-slate-500 dark:text-white/40">
          {channelStatusQuery.data?.wechatpay_platform_certs_updated_at
            ? `证书缓存更新时间戳：${channelStatusQuery.data.wechatpay_platform_certs_updated_at}`
            : "证书缓存更新时间戳：-"}
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card variant="surface" padding="md">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-amber-500/15">
              <CreditCard className="h-6 w-6 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <p className="text-slate-600 text-sm dark:text-white/50">
                回调总数
              </p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">
                {stat ? stat.window_total : "-"}
              </p>
              <p className="text-xs text-slate-500 dark:text-white/40">
                最近 {statsMinutes} 分钟
              </p>
            </div>
          </div>
        </Card>

        <Card variant="surface" padding="md">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-green-500/15">
              <ShieldCheck className="h-6 w-6 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-slate-600 text-sm dark:text-white/50">
                验签/解密成功
              </p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">
                {stat ? stat.window_verified : "-"}
              </p>
              <p className="text-xs text-slate-500 dark:text-white/40">
                最近 {statsMinutes} 分钟
              </p>
            </div>
          </div>
        </Card>

        <Card variant="surface" padding="md">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-red-500/15">
              <ShieldAlert className="h-6 w-6 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <p className="text-slate-600 text-sm dark:text-white/50">
                失败/异常
              </p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">
                {stat ? stat.window_failed : "-"}
              </p>
              <p className="text-xs text-slate-500 dark:text-white/40">
                最近 {statsMinutes} 分钟
              </p>
            </div>
          </div>
        </Card>
      </div>

      <Card variant="surface" padding="md">
        <div className="flex flex-wrap gap-3 items-center justify-between">
          <div className="flex flex-wrap gap-3 items-center">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-slate-500 dark:text-white/50" />
              <span className="text-slate-700 text-sm dark:text-white/70">
                筛选：
              </span>
            </div>

            <select
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 rounded-lg border border-slate-200/70 bg-white text-slate-900 text-sm outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            >
              <option value="">全部渠道</option>
              <option value="alipay">支付宝</option>
              <option value="ikunpay">爱坤支付</option>
              <option value="wechat">微信</option>
            </select>

            <select
              value={verified}
              onChange={(e) => {
                setVerified(e.target.value as any);
                setPage(1);
              }}
              className="px-3 py-2 rounded-lg border border-slate-200/70 bg-white text-slate-900 text-sm outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            >
              <option value="">全部结果</option>
              <option value="true">已验证</option>
              <option value="false">未验证</option>
            </select>

            <div className="w-56">
              <Input
                value={orderNo}
                onChange={(e) => {
                  setOrderNo(e.target.value);
                  setPage(1);
                }}
                placeholder="订单号 order_no"
              />
            </div>

            <div className="w-56">
              <Input
                value={tradeNo}
                onChange={(e) => {
                  setTradeNo(e.target.value);
                  setPage(1);
                }}
                placeholder="流水号 trade_no"
              />
            </div>

            {(provider || orderNo || tradeNo || verified) && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                清除筛选
              </Button>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-slate-600 text-sm dark:text-white/50">
                统计窗口
              </span>
              <select
                value={statsMinutes}
                onChange={(e) => setStatsMinutes(Number(e.target.value))}
                className="px-3 py-2 rounded-lg border border-slate-200/70 bg-white text-slate-900 text-sm outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              >
                <option value={15}>15 分钟</option>
                <option value={60}>60 分钟</option>
                <option value={6 * 60}>6 小时</option>
                <option value={24 * 60}>24 小时</option>
              </select>
            </div>
          </div>
        </div>
      </Card>

      <Card variant="surface" padding="none">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200/70 dark:border-white/10">
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  时间
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  渠道
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  订单号
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  流水号
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  金额
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  验证
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  错误
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {listQuery.isLoading ? (
                <tr>
                  <td
                    colSpan={8}
                    className="py-10 text-center text-slate-500 dark:text-white/50"
                  >
                    <div className="px-4">
                      <ListSkeleton count={6} />
                    </div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td
                    colSpan={8}
                    className="py-10 text-center text-slate-500 dark:text-white/50"
                  >
                    暂无数据
                  </td>
                </tr>
              ) : (
                items.map((it) => (
                  <tr
                    key={it.id}
                    className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5"
                  >
                    <td className="py-3 px-4 text-slate-600 text-sm dark:text-white/60">
                      {formatTime(it.created_at)}
                    </td>
                    <td className="py-3 px-4 text-slate-900 text-sm dark:text-white">
                      {providerLabel(it.provider)}
                    </td>
                    <td className="py-3 px-4 text-slate-700 text-sm dark:text-white/70">
                      {it.order_no || "-"}
                    </td>
                    <td className="py-3 px-4 text-slate-700 text-sm dark:text-white/70">
                      {it.trade_no || "-"}
                    </td>
                    <td className="py-3 px-4 text-slate-700 text-sm dark:text-white/70">
                      {typeof it.amount === "number"
                        ? it.amount.toFixed(2)
                        : "-"}
                    </td>
                    <td className="py-3 px-4">
                      {it.verified ? (
                        <Badge variant="success" size="sm">
                          已验证
                        </Badge>
                      ) : (
                        <Badge variant="danger" size="sm">
                          未验证
                        </Badge>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-600 text-sm dark:text-white/60">
                      {it.error_message || "-"}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={Eye}
                          onClick={() => void openPayloadModal(it.id)}
                        >
                          查看
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={Search}
                          onClick={() =>
                            doReconcileByOrderNo(it.order_no || "")
                          }
                          disabled={!it.order_no}
                        >
                          对账
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="p-4">
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={(p) => setPage(p)}
          />
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card variant="surface" padding="md">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                微信平台证书
              </h2>
              <p className="text-slate-600 text-sm mt-1 dark:text-white/50">
                用于微信支付 V3 回调验签（可多证书轮换）
              </p>
            </div>
            <Button
              icon={KeyRound}
              onClick={() => refreshCertsMutation.mutate()}
              isLoading={refreshCertsMutation.isPending}
              loadingText="刷新中..."
              disabled={refreshCertsMutation.isPending}
            >
              刷新证书
            </Button>
          </div>

          <div className="mt-4 space-y-2">
            {platformCertsQuery.isLoading ? (
              <ListSkeleton count={3} />
            ) : (platformCertsQuery.data?.items?.length ?? 0) === 0 ? (
              <div className="text-center py-8 text-slate-500 dark:text-white/50">
                暂无证书
              </div>
            ) : (
              (platformCertsQuery.data?.items ?? []).map((c) => (
                <div
                  key={c.serial_no}
                  className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-slate-900 text-sm font-medium dark:text-white">
                      {c.serial_no}
                    </div>
                    <div className="text-slate-500 text-xs dark:text-white/40">
                      {c.expire_time || "-"}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="mt-6 border-t border-slate-200/70 pt-4 dark:border-white/10">
            <div className="text-slate-900 text-sm font-semibold dark:text-white">
              离线导入证书（当无法刷新/无法访问微信接口时）
            </div>
            <div className="text-slate-600 text-xs mt-1 dark:text-white/50">
              支持两种方式：1) 粘贴平台证书 JSON（dump 格式）；2) 粘贴单个证书
              PEM（可选填 serial/expire）
            </div>

            <div className="mt-3 grid grid-cols-1 gap-3">
              <Textarea
                value={platformCertImportJson}
                onChange={(e) => setPlatformCertImportJson(e.target.value)}
                disabled={importCertsMutation.isPending}
                rows={5}
                placeholder='平台证书 JSON（示例：{"updated_at":...,"certs":[{"serial_no":"...","pem":"-----BEGIN CERTIFICATE-----...","expire_time":"..."}]})'
              />

              <Textarea
                value={platformCertImportPem}
                onChange={(e) => setPlatformCertImportPem(e.target.value)}
                disabled={importCertsMutation.isPending}
                rows={5}
                placeholder="单个证书 PEM（-----BEGIN CERTIFICATE----- ... -----END CERTIFICATE-----）"
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Input
                  value={platformCertImportSerialNo}
                  onChange={(e) =>
                    setPlatformCertImportSerialNo(e.target.value)
                  }
                  disabled={importCertsMutation.isPending}
                  placeholder="serial_no（可选）"
                />
                <Input
                  value={platformCertImportExpireTime}
                  onChange={(e) =>
                    setPlatformCertImportExpireTime(e.target.value)
                  }
                  disabled={importCertsMutation.isPending}
                  placeholder="expire_time（可选，ISO8601）"
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-white/70">
                <input
                  type="checkbox"
                  checked={platformCertImportMerge}
                  onChange={(e) => setPlatformCertImportMerge(e.target.checked)}
                  disabled={importCertsMutation.isPending}
                />
                合并导入（保留已有证书）
              </label>

              <div className="flex items-center gap-3">
                <Button
                  onClick={() => {
                    const payload = {
                      merge: platformCertImportMerge,
                      ...(platformCertImportJson.trim()
                        ? { platform_certs_json: platformCertImportJson.trim() }
                        : {}),
                      ...(platformCertImportPem.trim()
                        ? {
                            cert_pem: platformCertImportPem.trim(),
                            ...(platformCertImportSerialNo.trim()
                              ? { serial_no: platformCertImportSerialNo.trim() }
                              : {}),
                            ...(platformCertImportExpireTime.trim()
                              ? {
                                  expire_time:
                                    platformCertImportExpireTime.trim(),
                                }
                              : {}),
                          }
                        : {}),
                    };

                    if (!payload.platform_certs_json && !payload.cert_pem) {
                      toast.error("请至少填写 platform_certs_json 或 cert_pem");
                      return;
                    }
                    importCertsMutation.mutate(payload);
                  }}
                  isLoading={importCertsMutation.isPending}
                  loadingText="导入中..."
                  disabled={importCertsMutation.isPending}
                >
                  导入证书
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setPlatformCertImportJson("");
                    setPlatformCertImportPem("");
                    setPlatformCertImportSerialNo("");
                    setPlatformCertImportExpireTime("");
                  }}
                  disabled={importCertsMutation.isPending}
                >
                  清空
                </Button>
              </div>
            </div>
          </div>
        </Card>

        <Card variant="surface" padding="md">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                订单对账
              </h2>
              <p className="text-slate-600 text-sm mt-1 dark:text-white/50">
                输入订单号，返回回调情况诊断（无回调/验签失败/金额不一致等）
              </p>
            </div>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1">
              <Input
                value={reconcileOrderNo}
                onChange={(e) => setReconcileOrderNo(e.target.value)}
                disabled={reconcileMutation.isPending}
                placeholder="请输入订单号"
              />
            </div>
            <Button
              icon={Search}
              onClick={doReconcile}
              isLoading={reconcileMutation.isPending}
              loadingText="查询中..."
              disabled={reconcileMutation.isPending}
            >
              对账
            </Button>
          </div>

          {reconcileResult ? (
            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-slate-700 text-sm dark:text-white/70">
                  诊断：
                </span>
                {reconcileBadge ? (
                  <Badge variant={reconcileBadge.color} size="sm">
                    {reconcileBadge.label}
                  </Badge>
                ) : null}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                  <div className="text-xs text-slate-500 dark:text-white/40">
                    订单状态
                  </div>
                  <div className="text-sm font-medium text-slate-900 dark:text-white">
                    {reconcileResult.order_status}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                  <div className="text-xs text-slate-500 dark:text-white/40">
                    支付方式
                  </div>
                  <div className="text-sm font-medium text-slate-900 dark:text-white">
                    {reconcileResult.payment_method || "-"}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                  <div className="text-xs text-slate-500 dark:text-white/40">
                    金额
                  </div>
                  <div className="text-sm font-medium text-slate-900 dark:text-white">
                    {Number(reconcileResult.actual_amount).toFixed(2)}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                  <div className="text-xs text-slate-500 dark:text-white/40">
                    订单流水号
                  </div>
                  <div className="text-sm font-medium text-slate-900 dark:text-white">
                    {reconcileResult.trade_no || "-"}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                  <div className="text-xs text-slate-500 dark:text-white/40">
                    回调总数
                  </div>
                  <div className="text-sm font-medium text-slate-900 dark:text-white">
                    {reconcileResult.callbacks_total}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                  <div className="text-xs text-slate-500 dark:text-white/40">
                    成功/失败
                  </div>
                  <div className="text-sm font-medium text-slate-900 dark:text-white">
                    {reconcileResult.callbacks_verified}/
                    {reconcileResult.callbacks_failed}
                  </div>
                </div>
              </div>

              <div className="mt-2">
                <div className="text-slate-700 text-sm font-medium dark:text-white/80">
                  最近回调
                </div>
                <div className="mt-2 space-y-2">
                  {(reconcileResult.recent_events ?? []).length === 0 ? (
                    <div className="text-slate-500 text-sm dark:text-white/50">
                      暂无回调事件
                    </div>
                  ) : (
                    (reconcileResult.recent_events ?? [])
                      .slice(0, 20)
                      .map((e, idx) => (
                        <div
                          key={`${e.created_at}-${idx}`}
                          className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="text-slate-900 text-sm font-medium dark:text-white">
                              {providerLabel(e.provider)}
                            </div>
                            <div className="text-slate-500 text-xs dark:text-white/40">
                              {formatTime(e.created_at)}
                            </div>
                          </div>
                          <div className="mt-1 grid grid-cols-2 gap-2">
                            <div className="text-xs text-slate-600 dark:text-white/60 break-all">
                              order_no: {e.order_no || "-"}
                            </div>
                            <div className="text-xs text-slate-600 dark:text-white/60 break-all">
                              trade_no: {e.trade_no || "-"}
                            </div>
                            <div className="text-xs text-slate-600 dark:text-white/60">
                              amount:{" "}
                              {typeof e.amount === "number"
                                ? e.amount.toFixed(2)
                                : "-"}
                            </div>
                            <div className="text-xs text-slate-600 dark:text-white/60">
                              {e.verified ? (
                                <Badge variant="success" size="sm">
                                  已验证
                                </Badge>
                              ) : (
                                <Badge variant="danger" size="sm">
                                  未验证
                                </Badge>
                              )}
                            </div>
                          </div>
                          <div className="mt-2 text-xs text-slate-600 dark:text-white/60">
                            error: {e.error_message || "-"}
                          </div>
                        </div>
                      ))
                  )}
                </div>
              </div>

              <div className="text-xs text-slate-500 dark:text-white/40 break-all">
                details:{" "}
                {JSON.stringify(reconcileResult.details ?? {}, null, 2)}
              </div>
            </div>
          ) : null}
        </Card>
      </div>

      <Modal
        isOpen={payloadModalOpen}
        onClose={() => {
          setPayloadModalOpen(false);
          setPayloadEvent(null);
          setPayloadLoading(false);
          setPayloadShowRaw(false);
        }}
        title="回调 Raw Payload"
        description={
          payloadEvent
            ? `${providerLabel(payloadEvent.provider)} · order_no=${
                payloadEvent.order_no || "-"
              } · trade_no=${payloadEvent.trade_no || "-"}`
            : "用于排障：查看支付回调原始入参（已脱敏/不回显密钥）"
        }
        size="lg"
      >
        <div className="space-y-3">
          <Textarea
            value={
              payloadShowRaw
                ? payloadEvent?.raw_payload || ""
                : payloadEvent?.masked_payload ||
                  payloadEvent?.raw_payload ||
                  ""
            }
            readOnly
            rows={12}
            className="font-mono text-xs"
            placeholder={payloadLoading ? "加载中..." : "无 payload"}
          />

          <ModalActions>
            <Button
              variant="outline"
              onClick={() => {
                setPayloadModalOpen(false);
                setPayloadEvent(null);
                setPayloadShowRaw(false);
              }}
            >
              关闭
            </Button>
            <Button
              variant="outline"
              onClick={() => setPayloadShowRaw((v) => !v)}
              disabled={payloadLoading || !payloadEvent?.raw_payload}
            >
              {payloadShowRaw ? "显示脱敏" : "显示原文"}
            </Button>
            <Button
              icon={Copy}
              onClick={async () => {
                const v = payloadShowRaw
                  ? String(payloadEvent?.raw_payload || "")
                  : String(
                      payloadEvent?.masked_payload ||
                        payloadEvent?.raw_payload ||
                        ""
                    );
                if (!v.trim()) {
                  toast.error("payload 为空");
                  return;
                }
                try {
                  await navigator.clipboard.writeText(v);
                  toast.success(
                    payloadShowRaw ? "已复制原始 payload" : "已复制脱敏 payload"
                  );
                } catch {
                  toast.error("复制失败，请手动复制");
                }
              }}
              disabled={
                payloadLoading ||
                (!payloadShowRaw &&
                  !payloadEvent?.masked_payload &&
                  !payloadEvent?.raw_payload) ||
                (payloadShowRaw && !payloadEvent?.raw_payload)
              }
              isLoading={payloadLoading}
              loadingText="加载中..."
            >
              复制
            </Button>
          </ModalActions>
        </div>
      </Modal>
    </div>
  );
}
