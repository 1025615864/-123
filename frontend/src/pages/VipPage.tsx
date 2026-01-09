import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Crown, ExternalLink, RefreshCw, Sparkles, Wallet } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useAppMutation, useToast } from "../hooks";
import { queryKeys } from "../queryKeys";
import { getApiErrorMessage } from "../utils";
import PageHeader from "../components/PageHeader";
import PaymentMethodModal, {
  type PaymentMethod,
} from "../components/PaymentMethodModal";
import { Badge, Button, Card, Input, Modal } from "../components/ui";

export default function VipPage() {
  const { user, refreshUser } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  type PricingResp = {
    vip: { days: number; price: number };
  };

  type PaymentChannelStatus = {
    alipay_configured: boolean;
    wechatpay_configured: boolean;
    ikunpay_configured: boolean;
    available_methods: string[];
  };

  const pricingQuery = useQuery({
    queryKey: ["payment-pricing"],
    queryFn: async () => {
      const res = await api.get("/payment/pricing");
      return res.data as PricingResp;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const channelStatusQuery = useQuery({
    queryKey: queryKeys.paymentChannelStatus(),
    queryFn: async () => {
      const res = await api.get("/payment/channel-status");
      return (res.data || {}) as PaymentChannelStatus;
    },
    enabled: Boolean(user),
    retry: 1,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const vipPlan = pricingQuery.data?.vip;
  const vipDays = Number(vipPlan?.days || 30);
  const vipPrice = Number(vipPlan?.price || 29);

  const vipExpiresAt = useMemo(() => {
    const raw = user?.vip_expires_at;
    if (!raw) return null;
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return null;
    return d;
  }, [user?.vip_expires_at]);

  const isVipActive = useMemo(() => {
    if (!vipExpiresAt) return false;
    return vipExpiresAt.getTime() > Date.now();
  }, [vipExpiresAt]);

  const [showRechargeModal, setShowRechargeModal] = useState(false);
  const [rechargeAmount, setRechargeAmount] = useState("100");
  const [showPaymentGuideModal, setShowPaymentGuideModal] = useState(false);
  const [paymentGuideOrderNo, setPaymentGuideOrderNo] = useState<string | null>(
    null
  );

  const [showPaymentMethodModal, setShowPaymentMethodModal] = useState(false);
  const [paymentMethodContext, setPaymentMethodContext] = useState<
    | null
    | { kind: "vip" }
    | { kind: "recharge"; amount: number }
  >(null);

  const openRecharge = (amount?: number) => {
    if (typeof amount === "number" && Number.isFinite(amount) && amount > 0) {
      setRechargeAmount(String(amount));
    }
    setShowRechargeModal(true);
  };

  const openPaymentGuide = (orderNo: string | null) => {
    setPaymentGuideOrderNo(orderNo);
    setShowPaymentGuideModal(true);
  };

  const buyVipMutation = useAppMutation<
    any,
    { payment_method: "balance" | "alipay" | "ikunpay" }
  >({
    mutationFn: async ({ payment_method }) => {
      const createRes = await api.post("/payment/orders", {
        order_type: "vip",
        amount: vipPrice,
        title: "VIP会员",
        description: "VIP会员",
      });
      const orderNo = String(createRes.data?.order_no || "").trim();
      if (!orderNo) throw new Error("未获取到订单号");

      const payRes = await api.post(
        `/payment/orders/${encodeURIComponent(orderNo)}/pay`,
        {
          payment_method,
        }
      );

      return { order_no: orderNo, ...(payRes.data || {}) };
    },
    errorMessageFallback: "开通失败，请稍后重试",
    disableErrorToast: true,
  });

  const rechargeMutation = useAppMutation<
    { order_no: string; pay_url?: string },
    { amount: number; payment_method: "alipay" | "ikunpay" }
  >({
    mutationFn: async ({ amount, payment_method }) => {
      const createRes = await api.post("/payment/orders", {
        order_type: "recharge",
        amount,
        title: "余额充值",
        description: "余额充值",
      });
      const orderNo = String(createRes.data?.order_no || "").trim();
      if (!orderNo) throw new Error("未获取到订单号");

      const payRes = await api.post(
        `/payment/orders/${encodeURIComponent(orderNo)}/pay`,
        {
          payment_method,
        }
      );

      return {
        order_no: orderNo,
        pay_url: String((payRes.data as any)?.pay_url || "").trim() || undefined,
      };
    },
    errorMessageFallback: "充值失败，请稍后重试",
  });

  const handleBuyVip = () => {
    if (!user) {
      toast.info("登录后可开通 VIP");
      navigate("/login");
      return;
    }
    if (buyVipMutation.isPending) return;

    setPaymentMethodContext({ kind: "vip" });
    setShowPaymentMethodModal(true);
  };

  const benefits = [
    {
      title: "更高的每日额度",
      desc: "提升 AI 咨询/文书生成每日可用次数，减少等待与限制。",
    },
    {
      title: "优先体验新功能",
      desc: "优先获得新模型/新模板/新工具的灰度体验机会。",
    },
    {
      title: "更顺滑的使用体验",
      desc: "更少的弹窗打断与更清晰的权益提示，帮助你快速完成咨询与生成。",
    },
  ];

  const faq = [
    {
      q: "VIP 是否自动续费？",
      a: "目前不自动续费，到期后你可以在本页或个人中心手动续费。",
    },
    {
      q: "开通后多久到账？",
      a: "余额支付即时生效；第三方支付完成后请返回本站并点击“我已支付，刷新权益”。",
    },
    {
      q: "余额不足怎么办？",
      a: "你可以先充值余额，再选择余额支付开通 VIP。",
    },
  ];

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="VIP 会员"
        title="开通 VIP，解锁更充足的使用额度"
        description="更高的每日额度与更顺滑的咨询/生成体验，适合高频使用场景"
        tone={actualTheme}
        right={
          <div className="flex flex-col items-start gap-2">
            <Button
              icon={Crown}
              onClick={handleBuyVip}
              isLoading={buyVipMutation.isPending}
              loadingText="处理中..."
              className="bg-amber-600 hover:bg-amber-700 text-white focus-visible:ring-amber-500/25"
            >
              {isVipActive ? "续费 VIP" : "立即开通"}
            </Button>
            <div className="text-xs text-slate-600 dark:text-white/55">
              {pricingQuery.isLoading
                ? "价格加载中..."
                : `¥${vipPrice.toFixed(2)} / ${vipDays} 天`}
            </div>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card variant="surface" padding="lg">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-lg font-semibold text-slate-900 dark:text-white">
                当前状态
              </div>
              <div className="text-sm text-slate-600 mt-1 dark:text-white/55">
                {user ? "你的会员权益状态" : "登录后查看你的会员状态"}
              </div>
            </div>
            <Badge
              variant={isVipActive ? "success" : "default"}
              icon={isVipActive ? Sparkles : Wallet}
            >
              {isVipActive ? "VIP 生效中" : "未开通"}
            </Badge>
          </div>

          <div className="mt-5 space-y-2 text-sm text-slate-700 dark:text-white/70">
            <div>
              <span className="text-slate-500 dark:text-white/45">到期时间：</span>
              {vipExpiresAt
                ? vipExpiresAt.toLocaleString("zh-CN")
                : "—"}
            </div>
            <div>
              <span className="text-slate-500 dark:text-white/45">建议：</span>
              开通后可在个人中心查看每日剩余额度与购买记录。
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-2">
            <Link to="/profile" className="block">
              <Button variant="outline" fullWidth icon={ExternalLink}>
                去个人中心查看额度
              </Button>
            </Link>
          </div>
        </Card>

        <Card variant="surface" padding="lg" className="lg:col-span-2">
          <div className="text-lg font-semibold text-slate-900 dark:text-white">
            VIP 权益
          </div>
          <div className="text-sm text-slate-600 mt-1 dark:text-white/55">
            我们会持续迭代权益内容，以页面展示为准
          </div>

          <div className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-4">
            {benefits.map((b) => (
              <div
                key={b.title}
                className="rounded-xl border border-slate-200/70 bg-white px-4 py-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]"
              >
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  {b.title}
                </div>
                <div className="text-xs text-slate-600 mt-2 leading-relaxed dark:text-white/55">
                  {b.desc}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex flex-col sm:flex-row gap-3">
            <Button
              icon={Crown}
              onClick={handleBuyVip}
              isLoading={buyVipMutation.isPending}
              loadingText="处理中..."
              className="bg-amber-600 hover:bg-amber-700 text-white focus-visible:ring-amber-500/25"
            >
              {isVipActive ? "续费 VIP" : "立即开通"}
            </Button>
            <Button variant="outline" onClick={() => openRecharge(vipPrice)}>
              余额不足？先充值
            </Button>
          </div>
        </Card>
      </div>

      <Card variant="surface" padding="lg">
        <div className="text-lg font-semibold text-slate-900 dark:text-white">
          常见问题
        </div>
        <div className="text-sm text-slate-600 mt-1 dark:text-white/55">
          如果仍有疑问，可前往 FAQ 或直接咨询 AI
        </div>

        <div className="mt-5 space-y-3">
          {faq.map((it) => (
            <div
              key={it.q}
              className="rounded-xl border border-slate-200/70 px-4 py-4 dark:border-white/10"
            >
              <div className="text-sm font-semibold text-slate-900 dark:text-white">
                {it.q}
              </div>
              <div className="text-sm text-slate-600 mt-2 dark:text-white/60">
                {it.a}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 flex flex-col sm:flex-row gap-3">
          <Link to="/faq" className="block">
            <Button variant="outline" fullWidth>
              查看更多 FAQ
            </Button>
          </Link>
          <Link to="/chat" className="block">
            <Button fullWidth>
              去咨询 AI
            </Button>
          </Link>
        </div>
      </Card>

      <Modal
        isOpen={showRechargeModal}
        onClose={() => {
          if (rechargeMutation.isPending) return;
          setShowRechargeModal(false);
        }}
        title="余额充值"
        description="选择充值金额并跳转支付"
        size="sm"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[50, 100, 200].map((amt) => (
              <Button
                key={amt}
                type="button"
                variant={
                  String(amt) === String(rechargeAmount).trim()
                    ? "primary"
                    : "outline"
                }
                disabled={rechargeMutation.isPending}
                onClick={() => setRechargeAmount(String(amt))}
              >
                ¥{amt}
              </Button>
            ))}
          </div>

          <Input
            label="自定义金额（元）"
            value={rechargeAmount}
            onChange={(e) => setRechargeAmount(e.target.value)}
            disabled={rechargeMutation.isPending}
            placeholder="例如：100"
          />

          <Button
            type="button"
            fullWidth
            icon={ExternalLink}
            isLoading={rechargeMutation.isPending}
            loadingText="创建订单中..."
            disabled={rechargeMutation.isPending}
            onClick={() => {
              const amt = Number(String(rechargeAmount || "").trim());
              if (!Number.isFinite(amt) || amt <= 0) {
                toast.error("请输入正确的充值金额");
                return;
              }

              setPaymentMethodContext({ kind: "recharge", amount: amt });
              setShowRechargeModal(false);
              setShowPaymentMethodModal(true);
            }}
          >
            去支付
          </Button>

          <Button
            type="button"
            variant="secondary"
            fullWidth
            onClick={() => setShowRechargeModal(false)}
            disabled={rechargeMutation.isPending}
          >
            取消
          </Button>
        </div>
      </Modal>

      <Modal
        isOpen={showPaymentGuideModal}
        onClose={() => setShowPaymentGuideModal(false)}
        title="支付提示"
        description="支付完成后请返回本站刷新状态"
        size="sm"
      >
        <div className="space-y-3">
          <Button
            type="button"
            fullWidth
            icon={RefreshCw}
            onClick={async () => {
              setShowPaymentGuideModal(false);
              await refreshUser();
              toast.success("已刷新权益");
            }}
          >
            我已支付，刷新权益
          </Button>

          {paymentGuideOrderNo ? (
            <Link
              to={`/payment/return?order_no=${encodeURIComponent(
                paymentGuideOrderNo
              )}`}
              className="block"
            >
              <Button type="button" variant="outline" fullWidth icon={ExternalLink}>
                去支付结果页查看订单
              </Button>
            </Link>
          ) : null}

          <Link to="/orders" className="block">
            <Button type="button" variant="outline" fullWidth>
              去订单列表
            </Button>
          </Link>

          {paymentGuideOrderNo ? (
            <div className="text-xs text-slate-500 dark:text-white/45">
              订单号：{paymentGuideOrderNo}
            </div>
          ) : null}
        </div>
      </Modal>

      <PaymentMethodModal
        isOpen={showPaymentMethodModal}
        onClose={() => {
          if (buyVipMutation.isPending || rechargeMutation.isPending) return;
          setShowPaymentMethodModal(false);
        }}
        onBack={(() => {
          const ctx = paymentMethodContext;
          if (!ctx) return undefined;
          if (ctx.kind === "recharge") {
            return () => {
              if (rechargeMutation.isPending) return;
              setShowPaymentMethodModal(false);
              setShowRechargeModal(true);
            };
          }
          return undefined;
        })()}
        backLabel="返回修改"
        title="选择支付方式"
        description={
          paymentMethodContext?.kind === "vip"
            ? `开通/续费 VIP（${vipDays}天 ¥${vipPrice.toFixed(2)}）`
            : paymentMethodContext?.kind === "recharge"
              ? `充值 ¥${Number(paymentMethodContext.amount || 0).toFixed(2)}`
              : undefined
        }
        busy={buyVipMutation.isPending || rechargeMutation.isPending}
        options={(() => {
          const loadingChannels = !channelStatusQuery.data && channelStatusQuery.isLoading;
          const canAlipay = channelStatusQuery.data?.alipay_configured === true;
          const canIkunpay = channelStatusQuery.data?.ikunpay_configured === true;
          const thirdPartyDisabledReason = loadingChannels ? "加载中" : "未配置";

          if (paymentMethodContext?.kind === "recharge") {
            return [
              {
                method: "alipay" as PaymentMethod,
                label: "支付宝",
                description: "跳转到支付宝完成支付",
                enabled: canAlipay,
                disabledReason: thirdPartyDisabledReason,
              },
              {
                method: "ikunpay" as PaymentMethod,
                label: "爱坤支付",
                description: "跳转到爱坤支付完成支付",
                enabled: canIkunpay,
                disabledReason: thirdPartyDisabledReason,
              },
            ];
          }

          return [
            {
              method: "balance" as PaymentMethod,
              label: "余额支付",
              description: "即时生效",
              enabled: true,
            },
            {
              method: "alipay" as PaymentMethod,
              label: "支付宝",
              description: "跳转到支付宝完成支付",
              enabled: canAlipay,
              disabledReason: thirdPartyDisabledReason,
            },
            {
              method: "ikunpay" as PaymentMethod,
              label: "爱坤支付",
              description: "跳转到爱坤支付完成支付",
              enabled: canIkunpay,
              disabledReason: thirdPartyDisabledReason,
            },
          ];
        })()}
        onSelect={(method) => {
          const ctx = paymentMethodContext;
          setShowPaymentMethodModal(false);
          if (!ctx) return;

          if (ctx.kind === "vip") {
            buyVipMutation.mutate(
              { payment_method: method as any },
              {
                onSuccess: async (data) => {
                  if (method !== "balance") {
                    const url = String((data as any)?.pay_url || "").trim();
                    if (url) {
                      window.open(url, "_blank", "noopener,noreferrer");
                      toast.success("已打开支付页面");
                      openPaymentGuide(String((data as any)?.order_no || null));
                    } else {
                      toast.error("未获取到支付链接");
                    }
                    return;
                  }

                  toast.success("开通成功");
                  await refreshUser();
                  queryClient.invalidateQueries({ queryKey: ["user-me"] as any });
                  queryClient.invalidateQueries({
                    queryKey: queryKeys.userMeQuotas() as any,
                  });
                },
                onError: (err) => {
                  const msg = getApiErrorMessage(err, "开通失败");
                  if (String(msg).includes("余额不足")) {
                    toast.warning("余额不足，请先充值");
                    openRecharge(vipPrice);
                    return;
                  }
                  toast.error(msg);
                },
              }
            );
            return;
          }

          if (ctx.kind === "recharge") {
            if (method === "balance") {
              toast.error("充值不支持余额支付");
              return;
            }
            rechargeMutation.mutate(
              { amount: ctx.amount, payment_method: method as any },
              {
                onSuccess: async (data) => {
                  const payUrl = String((data as any)?.pay_url || "").trim();
                  if (payUrl) {
                    window.open(payUrl, "_blank", "noopener,noreferrer");
                    toast.success("已打开支付页面");
                    openPaymentGuide(String((data as any)?.order_no || null));
                    setShowRechargeModal(false);
                    return;
                  }
                  toast.success("订单已创建，请前往订单页继续支付");
                  setShowRechargeModal(false);
                },
                onError: (err) => {
                  toast.error(getApiErrorMessage(err, "充值失败"));
                },
              }
            );
          }
        }}
      />
    </div>
  );
}
