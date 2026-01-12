import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle, Clock, ExternalLink, RefreshCw, XCircle } from "lucide-react";
import PageHeader from "../components/PageHeader";
import { Badge, Button, Card, EmptyState, Skeleton } from "../components/ui";
import api from "../api/client";
import { useTheme } from "../contexts/ThemeContext";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../hooks";

type OrderDetail = {
  order_no: string;
  order_type: string;
  amount: number;
  actual_amount: number;
  status: string;
  payment_method: string | null;
  title: string;
  created_at: string;
  paid_at: string | null;
};

function statusToBadgeVariant(status: string):
  | "default"
  | "primary"
  | "success"
  | "warning"
  | "danger"
  | "info" {
  const s = String(status || "").toLowerCase();
  if (s === "paid") return "success";
  if (s === "pending") return "warning";
  if (s === "cancelled" || s === "failed") return "danger";
  if (s === "refunded") return "info";
  return "default";
}

function statusToText(status: string): string {
  const s = String(status || "").toLowerCase();
  if (s === "paid") return "支付成功";
  if (s === "pending") return "待支付";
  if (s === "cancelled") return "已取消";
  if (s === "failed") return "支付失败";
  if (s === "refunded") return "已退款";
  return status || "未知";
}

function orderTypeToNextStep(orderType: string | null | undefined): {
  label: string;
  to: string;
} | null {
  const t = String(orderType || "")
    .trim()
    .toLowerCase();
  if (!t) return null;
  if (t === "vip" || t === "ai_pack" || t === "recharge") {
    return { label: "去个人中心查看余额/权益", to: "/profile" };
  }
  if (t === "consultation") {
    return { label: "查看我的预约", to: "/orders?tab=consultations" };
  }
  if (t === "service") {
    return { label: "去律所服务", to: "/lawfirm" };
  }
  return null;
}

export default function PaymentReturnPage() {
  const { actualTheme } = useTheme();
  const { isAuthenticated } = useAuth();
  const toast = useToast();
  const [urlParams] = useSearchParams();
  const location = useLocation();

  const orderNo = useMemo(() => {
    const byOrderNo = String(urlParams.get("order_no") ?? "").trim();
    if (byOrderNo) return byOrderNo;
    const byOutTradeNo = String(urlParams.get("out_trade_no") ?? "").trim();
    if (byOutTradeNo) return byOutTradeNo;
    return "";
  }, [urlParams]);

  const detailQuery = useQuery({
    queryKey: ["payment-order-return", { orderNo }],
    queryFn: async () => {
      const res = await api.get(`/payment/orders/${encodeURIComponent(orderNo)}`);
      return res.data as OrderDetail;
    },
    enabled: Boolean(orderNo) && isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const isUnauthorized = useMemo(() => {
    const err: any = detailQuery.error;
    const status = err?.response?.status;
    return status === 401 || status === 403;
  }, [detailQuery.error]);

  const [pollingLeft, setPollingLeft] = useState(0);
  const pollingTimerRef = useRef<number | null>(null);
  const pollingStartedRef = useRef(false);

  useEffect(() => {
    pollingStartedRef.current = false;
    setPollingLeft(0);
    if (pollingTimerRef.current != null) {
      window.clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, [orderNo]);

  useEffect(() => {
    if (!orderNo) return;
    if (!detailQuery.data) return;

    const status = String(detailQuery.data.status || "").toLowerCase();
    if (status === "paid" || status === "cancelled" || status === "failed" || status === "refunded") {
      return;
    }

    if (pollingStartedRef.current) {
      return;
    }
    pollingStartedRef.current = true;

    if (pollingTimerRef.current != null) {
      window.clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }

    setPollingLeft(20);
    pollingTimerRef.current = window.setInterval(() => {
      setPollingLeft((left) => {
        const next = Math.max(0, left - 1);
        if (next <= 0) {
          if (pollingTimerRef.current != null) {
            window.clearInterval(pollingTimerRef.current);
            pollingTimerRef.current = null;
          }
          return 0;
        }
        void detailQuery.refetch();
        return next;
      });
    }, 3000);

    return () => {
      if (pollingTimerRef.current != null) {
        window.clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [detailQuery.data?.status, detailQuery.refetch, orderNo]);

  useEffect(() => {
    const status = String(detailQuery.data?.status || "").toLowerCase();
    if (status === "paid" || status === "cancelled" || status === "failed" || status === "refunded") {
      setPollingLeft(0);
      if (pollingTimerRef.current != null) {
        window.clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    }
  }, [detailQuery.data?.status]);

  const detail = detailQuery.data;
  const normalizedStatus = String(detail?.status || "").toLowerCase();
  const nextStep = useMemo(
    () => orderTypeToNextStep(detail?.order_type),
    [detail?.order_type]
  );

  const statusHint = useMemo(() => {
    if (normalizedStatus === "paid") {
      return "订单已支付成功。你可以前往对应功能查看权益或服务进度。";
    }
    if (normalizedStatus === "pending") {
      return "如果你已完成支付，异步通知可能会有延迟；请稍后刷新或前往订单页确认状态。";
    }
    if (normalizedStatus === "failed") {
      return "支付失败，可前往订单页重新支付或更换支付方式。";
    }
    if (normalizedStatus === "cancelled") {
      return "订单已取消。如需继续购买，请前往订单页重新下单。";
    }
    if (normalizedStatus === "refunded") {
      return "订单已退款。退款通常原路返回，到账时间以支付渠道为准。";
    }
    return "如状态未更新，请稍后刷新或前往订单页查看。";
  }, [normalizedStatus]);

  const headline = useMemo(() => {
    if (!orderNo) return "支付结果";
    if (normalizedStatus === "paid") return "支付成功";
    if (normalizedStatus === "pending") return "支付处理中";
    if (normalizedStatus === "failed") return "支付失败";
    if (normalizedStatus === "cancelled") return "订单已取消";
    if (normalizedStatus === "refunded") return "已退款";
    return "支付结果";
  }, [normalizedStatus, orderNo]);

  const icon = useMemo(() => {
    if (normalizedStatus === "paid") return CheckCircle;
    if (normalizedStatus === "failed" || normalizedStatus === "cancelled") return XCircle;
    return Clock;
  }, [normalizedStatus]);

  const Icon = icon;

  if (!isAuthenticated || isUnauthorized) {
    const redirect = `${location.pathname}${location.search}`
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="支付"
          title="请先登录"
          description="登录后即可查看支付结果与订单状态"
          layout="mdStart"
          tone={actualTheme}
        />

        <EmptyState
          icon={ExternalLink}
          title="需要登录"
          description="支付回跳页需要登录后才能查询订单状态"
          tone={actualTheme}
          action={
            <Link to={`/login?return_to=${encodeURIComponent(redirect)}`} className="mt-6 inline-block">
              <Button>去登录</Button>
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="支付"
        title={headline}
        description="如状态未更新，请稍后点击刷新或前往订单页查看"
        layout="mdStart"
        tone={actualTheme}
        right={
          orderNo && isAuthenticated && !isUnauthorized ? (
            <Button
              variant="outline"
              icon={RefreshCw}
              isLoading={detailQuery.isFetching}
              loadingText="刷新中..."
              onClick={async () => {
                const res = await detailQuery.refetch();
                if (res.error) {
                  return;
                }
                toast.success("已刷新订单状态");
              }}
              disabled={detailQuery.isFetching}
            >
              刷新
            </Button>
          ) : null
        }
      />

      {!orderNo ? (
        <EmptyState
          icon={Clock}
          title="未获取到订单号"
          description="请从订单页进入查看支付结果"
          tone={actualTheme}
          action={
            <Link to="/orders?tab=payment">
              <Button icon={ExternalLink}>去订单页</Button>
            </Link>
          }
        />
      ) : detailQuery.isLoading && !detail ? (
        <Card variant="surface" padding="lg">
          <div className="space-y-3">
            <Skeleton width="220px" height="18px" />
            <Skeleton width="180px" height="18px" />
            <Skeleton width="260px" height="18px" />
          </div>
        </Card>
      ) : detail ? (
        <Card variant="surface" padding="lg">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-2xl bg-slate-900/5 border border-slate-200/70 flex items-center justify-center dark:bg-white/[0.03] dark:border-white/[0.08]">
                {Icon ? <Icon className="h-5 w-5 text-amber-500" /> : null}
              </div>
              <div>
                <div className="text-base font-semibold text-slate-900 dark:text-white">
                  {detail.title}
                </div>
                <div className="mt-1 text-sm text-slate-600 dark:text-white/60">
                  订单号：{detail.order_no}
                </div>
              </div>
            </div>
            <Badge variant={statusToBadgeVariant(detail.status)} size="sm">
              {statusToText(detail.status)}
            </Badge>
          </div>

          <div className="mt-5 grid sm:grid-cols-2 gap-3 text-sm text-slate-700 dark:text-white/70">
            <div>应付：¥{Number(detail.amount || 0).toFixed(2)}</div>
            <div>实付：¥{Number(detail.actual_amount || 0).toFixed(2)}</div>
            <div>创建时间：{new Date(detail.created_at).toLocaleString()}</div>
            <div>
              支付时间：
              {detail.paid_at ? new Date(detail.paid_at).toLocaleString() : "—"}
            </div>
          </div>

          {normalizedStatus === "pending" ? (
            <div className="mt-5 rounded-xl border border-slate-200/70 bg-slate-900/5 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/70">
              <div>{statusHint}</div>
              {pollingLeft > 0 ? (
                <div className="mt-1 text-xs text-slate-500 dark:text-white/45">
                  自动刷新中（剩余约 {pollingLeft * 3}s）
                </div>
              ) : null}
            </div>
          ) : normalizedStatus ? (
            <div className="mt-5 rounded-xl border border-slate-200/70 bg-slate-900/5 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/70">
              <div>{statusHint}</div>
            </div>
          ) : null}

          <div className="mt-6 grid sm:grid-cols-2 gap-3">
            {normalizedStatus === "paid" && nextStep ? (
              <Link to={nextStep.to} className="block">
                <Button fullWidth icon={ExternalLink}>
                  {nextStep.label}
                </Button>
              </Link>
            ) : (
              <Link to="/orders?tab=payment" className="block">
                <Button fullWidth icon={ExternalLink}>
                  {normalizedStatus === "failed"
                    ? "去订单页重新支付"
                    : normalizedStatus === "cancelled"
                      ? "去订单页重新下单"
                      : "去订单页查看"}
                </Button>
              </Link>
            )}

            <Link
              to={
                normalizedStatus === "paid" && nextStep && nextStep.to !== "/profile"
                  ? "/orders?tab=payment"
                  : "/profile"
              }
              className="block"
            >
              <Button
                variant={
                  normalizedStatus === "paid" && nextStep && nextStep.to !== "/profile"
                    ? "outline"
                    : "primary"
                }
                fullWidth
                icon={ExternalLink}
              >
                {normalizedStatus === "paid" && nextStep && nextStep.to !== "/profile"
                  ? "去订单页查看"
                  : "去个人中心查看余额/权益"}
              </Button>
            </Link>
          </div>
        </Card>
      ) : (
        <EmptyState
          icon={Clock}
          title="未获取到订单详情"
          description="你可以稍后再试，或前往订单页查看"
          tone={actualTheme}
          action={
            <Link to="/orders?tab=payment">
              <Button icon={ExternalLink}>去订单页</Button>
            </Link>
          }
        />
      )}
    </div>
  );
}
