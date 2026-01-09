import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CreditCard, Plus, RefreshCw, Trash2 } from "lucide-react";
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

type ListResp = { items: BankAccount[]; total: number };

export default function LawyerBankAccountsPage() {
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

  const [activeDeleteId, setActiveDeleteId] = useState<number | null>(null);
  const [activeDefaultId, setActiveDefaultId] = useState<number | null>(null);

  const [bankName, setBankName] = useState("");
  const [accountNo, setAccountNo] = useState("");
  const [accountHolder, setAccountHolder] = useState("");
  const [isDefault, setIsDefault] = useState(true);

  const listQuery = useQuery({
    queryKey: ["lawyer-bank-accounts"],
    queryFn: async () => {
      const res = await api.get("/lawyer/bank-accounts");
      return res.data as ListResp;
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!listQuery.error) return;
    const status = (listQuery.error as any)?.response?.status;
    if (status === 401) return;
    if (status === 403) {
      const detail = String(
        (listQuery.error as any)?.response?.data?.detail || ""
      );
      if (user && user.phone_verified === false) {
        toast.warning("请先完成手机号验证");
        window.location.href = "/profile?phoneVerify=1";
        return;
      }
      if (user && user.email_verified === false) {
        toast.warning("请先完成邮箱验证");
        window.location.href = "/profile?emailVerify=1";
        return;
      }
      if (detail.includes("手机号")) {
        toast.warning("请先完成手机号验证");
        window.location.href = "/profile?phoneVerify=1";
        return;
      }
      if (detail.includes("邮箱")) {
        toast.warning("请先完成邮箱验证");
        window.location.href = "/profile?emailVerify=1";
        return;
      }
    }
    toast.error(getApiErrorMessage(listQuery.error, "加载失败，请稍后重试"));
  }, [listQuery.error, toast, user]);

  const items = listQuery.data?.items ?? [];

  const createMutation = useAppMutation<
    unknown,
    {
      bank_name: string;
      account_no: string;
      account_holder: string;
      is_default: boolean;
    }
  >({
    mutationFn: async (payload) => {
      await api.post("/lawyer/bank-accounts", {
        account_type: "bank_card",
        ...payload,
      });
    },
    successMessage: "已添加",
    errorMessageFallback: "添加失败，请稍后重试",
    onSuccess: () => {
      setBankName("");
      setAccountNo("");
      setAccountHolder("");
      setIsDefault(true);
      listQuery.refetch();
    },
  });

  const deleteMutation = useAppMutation<unknown, number>({
    mutationFn: async (id) => {
      await api.delete(`/lawyer/bank-accounts/${id}`);
    },
    successMessage: "已删除",
    errorMessageFallback: "删除失败",
    onSuccess: () => {
      listQuery.refetch();
    },
    onMutate: async (id) => {
      setActiveDeleteId(id);
    },
    onSettled: (_data, _err, id) => {
      setActiveDeleteId((prev) => (prev === id ? null : prev));
    },
  });

  const setDefaultMutation = useAppMutation<unknown, number>({
    mutationFn: async (id) => {
      await api.put(`/lawyer/bank-accounts/${id}/default`, {});
    },
    successMessage: "已设为默认",
    errorMessageFallback: "操作失败",
    onSuccess: () => {
      listQuery.refetch();
    },
    onMutate: async (id) => {
      setActiveDefaultId(id);
    },
    onSettled: (_data, _err, id) => {
      setActiveDefaultId((prev) => (prev === id ? null : prev));
    },
  });

  const actionBusy =
    createMutation.isPending ||
    deleteMutation.isPending ||
    setDefaultMutation.isPending;

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律师"
          title="收款账户"
          description="管理银行卡（MVP）"
          layout="mdStart"
          tone={actualTheme}
        />
        <EmptyState
          icon={CreditCard}
          title="请先登录"
          description="登录后即可管理收款账户"
          tone={actualTheme}
        />
      </div>
    );
  }

  if (listQuery.isLoading && !listQuery.data) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律师"
          title="收款账户"
          description="管理银行卡（MVP）"
          layout="mdStart"
          tone={actualTheme}
          right={<Skeleton width="90px" height="36px" />}
        />

        <Card variant="surface" padding="lg">
          <ListSkeleton count={3} />
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="律师"
        title="收款账户"
        description="管理银行卡（MVP）"
        layout="mdStart"
        tone={actualTheme}
        right={
          <Button
            variant="outline"
            icon={RefreshCw}
            onClick={() => listQuery.refetch()}
            isLoading={listQuery.isFetching}
            loadingText="刷新中..."
            disabled={listQuery.isFetching || actionBusy}
          >
            刷新
          </Button>
        }
      />

      <Card variant="surface" padding="lg">
        {items.length === 0 ? (
          <EmptyState
            icon={CreditCard}
            title="暂无账户"
            description="请先添加银行卡"
            tone={actualTheme}
          />
        ) : (
          <div className="space-y-3">
            {items.map((a) => {
              const defaultLoading =
                setDefaultMutation.isPending && activeDefaultId === a.id;
              const deleteLoading =
                deleteMutation.isPending && activeDeleteId === a.id;
              const disableOther =
                actionBusy && !(defaultLoading || deleteLoading);

              return (
                <Card
                  key={a.id}
                  variant="surface"
                  padding="md"
                  className="border border-slate-200/70 dark:border-white/10"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <div className="text-sm font-semibold text-slate-900 dark:text-white">
                          {a.bank_name ? a.bank_name + " " : ""}{" "}
                          {a.account_no_masked}
                        </div>
                        {a.is_default ? (
                          <Badge variant="success" size="sm">
                            默认
                          </Badge>
                        ) : null}
                        {!a.is_active ? (
                          <Badge variant="warning" size="sm">
                            已停用
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-2 text-xs text-slate-600 dark:text-white/60">
                        户名：{a.account_holder}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          if (actionBusy) return;
                          if (!ensureVerified()) return;
                          setDefaultMutation.mutate(a.id);
                        }}
                        isLoading={defaultLoading}
                        loadingText="设置中..."
                        disabled={
                          a.is_default ||
                          (actionBusy && !defaultLoading) ||
                          disableOther
                        }
                      >
                        设为默认
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        icon={Trash2}
                        onClick={() => {
                          if (actionBusy) return;
                          if (!ensureVerified()) return;
                          deleteMutation.mutate(a.id);
                        }}
                        isLoading={deleteLoading}
                        loadingText="删除中..."
                        disabled={
                          (actionBusy && !deleteLoading) || disableOther
                        }
                      >
                        删除
                      </Button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </Card>

      <Card variant="surface" padding="lg">
        <div className="flex items-center gap-2 mb-4">
          <Plus className="h-4 w-4 text-slate-400 dark:text-white/40" />
          <div className="text-sm font-medium text-slate-700 dark:text-white/70">
            添加银行卡
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          <Input
            label="银行"
            value={bankName}
            onChange={(e) => setBankName(e.target.value)}
            placeholder="例如：工商银行"
            disabled={actionBusy}
          />
          <Input
            label="卡号"
            value={accountNo}
            onChange={(e) => setAccountNo(e.target.value)}
            placeholder="例如：6222..."
            disabled={actionBusy}
          />
          <Input
            label="户名"
            value={accountHolder}
            onChange={(e) => setAccountHolder(e.target.value)}
            placeholder="例如：张三"
            disabled={actionBusy}
          />
        </div>

        <div className="mt-4 flex items-center justify-between flex-wrap gap-3">
          <label className="inline-flex items-center gap-2 text-sm text-slate-700 dark:text-white/70">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
              disabled={actionBusy}
              className="rounded"
            />
            设为默认
          </label>

          <Button
            icon={Plus}
            isLoading={createMutation.isPending}
            loadingText="添加中..."
            disabled={actionBusy}
            onClick={() => {
              if (actionBusy || createMutation.isPending) return;
              if (!ensureVerified()) return;
              const bn = bankName.trim();
              const an = accountNo.trim();
              const ah = accountHolder.trim();
              if (!bn) {
                toast.error("请填写银行名称");
                return;
              }
              if (!an || an.length < 4) {
                toast.error("请填写正确卡号");
                return;
              }
              if (!ah) {
                toast.error("请填写户名");
                return;
              }
              createMutation.mutate({
                bank_name: bn,
                account_no: an,
                account_holder: ah,
                is_default: isDefault,
              });
            }}
          >
            添加
          </Button>
        </div>
      </Card>
    </div>
  );
}
