import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CreditCard, Wallet, Send, RefreshCw } from "lucide-react";
import PageHeader from "../components/PageHeader";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  ListSkeleton,
  Skeleton,
} from "../components/ui";
import api from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useAppMutation, useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";

type WalletResp = {
  lawyer_id: number;
  total_income: number;
  withdrawn_amount: number;
  pending_amount: number;
  frozen_amount: number;
  available_amount: number;
  created_at: string;
  updated_at: string;
};

type BankAccount = {
  id: number;
  lawyer_id: number;
  account_type: string;
  bank_name: string | null;
  account_no_masked: string;
  account_holder: string;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type BankListResp = {
  items: BankAccount[];
  total: number;
};

export default function LawyerWithdrawPage() {
  const { isAuthenticated, user } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();

  const ensureVerified = () => {
    if (!user) return false;
    if (!user.phone_verified) {
      toast.warning("请先完成手机号验证");
      window.location.href = "/profile?phoneVerify=1";
      return false;
    }
    if (!user.email_verified) {
      toast.warning("请先完成邮箱验证");
      window.location.href = "/profile?emailVerify=1";
      return false;
    }
    return true;
  };

  const [amount, setAmount] = useState("");
  const [accountId, setAccountId] = useState<number | null>(null);

  const walletQuery = useQuery({
    queryKey: ["lawyer-wallet"],
    queryFn: async () => {
      const res = await api.get("/lawyer/wallet");
      return res.data as WalletResp;
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const bankQuery = useQuery({
    queryKey: ["lawyer-bank-accounts"],
    queryFn: async () => {
      const res = await api.get("/lawyer/bank-accounts");
      return res.data as BankListResp;
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    const err = walletQuery.error || bankQuery.error;
    if (!err) return;
    const status = (err as any)?.response?.status;
    if (status === 401) return;
    toast.error(getApiErrorMessage(err, "加载失败，请稍后重试"));
  }, [walletQuery.error, bankQuery.error, toast]);

  const accounts = bankQuery.data?.items ?? [];
  const defaultAccount = useMemo(
    () => accounts.find((a) => a.is_default) ?? accounts[0] ?? null,
    [accounts]
  );

  useEffect(() => {
    if (accountId != null) return;
    if (defaultAccount) setAccountId(defaultAccount.id);
  }, [accountId, defaultAccount]);

  const createWithdrawMutation = useAppMutation<
    any,
    { amount: number; bank_account_id: number }
  >({
    mutationFn: async (payload) => {
      const res = await api.post("/lawyer/withdrawals", {
        amount: payload.amount,
        withdraw_method: "bank_card",
        bank_account_id: payload.bank_account_id,
      });
      return res.data;
    },
    successMessage: "已提交提现申请",
    errorMessageFallback: "提交失败，请稍后重试",
    onSuccess: () => {
      setAmount("");
      walletQuery.refetch();
      bankQuery.refetch();
    },
  });

  const actionBusy = createWithdrawMutation.isPending;

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律师"
          title="申请提现"
          description="提交提现申请并等待管理员审核"
          layout="mdStart"
          tone={actualTheme}
        />
        <EmptyState
          icon={Wallet}
          title="请先登录"
          description="登录后即可申请提现"
          tone={actualTheme}
        />
      </div>
    );
  }

  if (walletQuery.isLoading && !walletQuery.data) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律师"
          title="申请提现"
          description="提交提现申请并等待管理员审核"
          layout="mdStart"
          tone={actualTheme}
          right={<Skeleton width="90px" height="36px" />}
        />

        <Card variant="surface" padding="lg">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-slate-400 dark:text-white/40" />
              <div className="text-sm text-slate-700 dark:text-white/70">
                可提现金额
              </div>
            </div>
            <Skeleton width="90px" height="20px" />
          </div>
        </Card>

        <Card variant="surface" padding="lg">
          <ListSkeleton count={2} />
        </Card>
      </div>
    );
  }

  const wallet = walletQuery.data;
  const available = wallet ? Number(wallet.available_amount || 0) : 0;

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="律师"
        title="申请提现"
        description="提交提现申请并等待管理员审核"
        layout="mdStart"
        tone={actualTheme}
        right={
          <Button
            variant="outline"
            icon={RefreshCw}
            onClick={() => {
              if (actionBusy) return;
              walletQuery.refetch();
              bankQuery.refetch();
            }}
            isLoading={walletQuery.isFetching || bankQuery.isFetching}
            loadingText="刷新中..."
            disabled={
              walletQuery.isFetching || bankQuery.isFetching || actionBusy
            }
          >
            刷新
          </Button>
        }
      />

      <Card variant="surface" padding="lg">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <CreditCard className="h-4 w-4 text-slate-400 dark:text-white/40" />
            <div className="text-sm text-slate-700 dark:text-white/70">
              可提现金额
            </div>
          </div>
          <div className="text-lg font-semibold text-slate-900 dark:text-white">
            ¥{available.toFixed(2)}
          </div>
        </div>
      </Card>

      <Card variant="surface" padding="lg">
        <div className="space-y-4">
          <Input
            label="提现金额（元）"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="例如：100"
            disabled={actionBusy}
          />

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-white/70 mb-2">
              收款账户
            </label>
            {bankQuery.isLoading && accounts.length === 0 ? (
              <div className="space-y-2">
                <Skeleton width="80%" height="16px" />
                <Skeleton width="60%" height="16px" />
              </div>
            ) : accounts.length === 0 ? (
              <EmptyState
                icon={Wallet}
                title="请先绑定银行卡"
                description="绑定银行卡后才能提现"
                tone={actualTheme}
                size="md"
                action={
                  <Button
                    onClick={() =>
                      (window.location.href = "/lawyer/bank-accounts")
                    }
                    disabled={actionBusy}
                  >
                    去绑定
                  </Button>
                }
              />
            ) : (
              <select
                value={accountId ?? ""}
                onChange={(e) => setAccountId(Number(e.target.value))}
                disabled={actionBusy}
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition hover:border-slate-300 focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-900"
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.bank_name ? a.bank_name + " " : ""} {a.account_no_masked}{" "}
                    {a.account_holder}
                    {a.is_default ? "（默认）" : ""}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="text-sm text-slate-600 dark:text-white/60">
              说明：MVP 为人工打款，审核通过后一般 3 个工作日内到账。
            </div>
            <Badge variant="info" size="sm">
              人工打款
            </Badge>
          </div>

          <div className="flex justify-end gap-2">
            <Button
              icon={Send}
              isLoading={createWithdrawMutation.isPending}
              loadingText="提交中..."
              onClick={() => {
                if (createWithdrawMutation.isPending) return;
                if (!ensureVerified()) return;
                const v = Number(String(amount || "").trim());
                if (!v || Number.isNaN(v) || v <= 0) {
                  toast.error("请输入正确金额");
                  return;
                }
                if (!accountId) {
                  toast.error("请选择收款账户");
                  return;
                }
                createWithdrawMutation.mutate({
                  amount: v,
                  bank_account_id: accountId,
                });
              }}
              disabled={accounts.length === 0 || actionBusy}
            >
              确认提现
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
