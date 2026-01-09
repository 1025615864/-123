import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CreditCard, FileText, RefreshCw, Download } from "lucide-react";
import PageHeader from "../components/PageHeader";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ListSkeleton,
  Pagination,
  Skeleton,
} from "../components/ui";
import api from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";

type Wallet = {
  lawyer_id: number;
  total_income: number;
  withdrawn_amount: number;
  pending_amount: number;
  frozen_amount: number;
  available_amount: number;
  created_at: string;
  updated_at: string;
};

type IncomeRecord = {
  id: number;
  lawyer_id: number;
  consultation_id: number | null;
  consultation_subject?: string | null;
  order_no: string | null;
  user_paid_amount: number;
  platform_fee: number;
  lawyer_income: number;
  withdrawn_amount: number;
  status: string;
  settle_time: string | null;
  created_at: string;
  updated_at: string;
};

type ListResp = {
  items: IncomeRecord[];
  total: number;
  page: number;
  page_size: number;
};

function statusLabel(s: string) {
  const v = String(s || "").toLowerCase();
  if (v === "pending") return "冻结中";
  if (v === "settled") return "可提现";
  if (v === "withdrawn") return "已提现";
  return s || "未知";
}

function statusVariant(
  s: string
): "default" | "primary" | "success" | "warning" | "danger" | "info" {
  const v = String(s || "").toLowerCase();
  if (v === "pending") return "warning";
  if (v === "settled") return "success";
  if (v === "withdrawn") return "info";
  return "default";
}

export default function LawyerIncomePage() {
  const { isAuthenticated, user } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();

  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [exporting, setExporting] = useState(false);

  const walletQuery = useQuery({
    queryKey: ["lawyer-wallet"],
    queryFn: async () => {
      const res = await api.get("/lawyer/wallet");
      return res.data as Wallet;
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const listQuery = useQuery({
    queryKey: ["lawyer-income-records", { page, pageSize, statusFilter }],
    queryFn: async () => {
      const res = await api.get("/lawyer/income-records", {
        params: {
          page,
          page_size: pageSize,
          ...(statusFilter ? { status: statusFilter } : {}),
        },
      });
      const data = res.data || {};
      return {
        items: Array.isArray(data?.items)
          ? (data.items as IncomeRecord[])
          : ([] as IncomeRecord[]),
        total: Number(data?.total || 0),
        page: Number(data?.page || page),
        page_size: Number(data?.page_size || pageSize),
      } satisfies ListResp;
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    const err = walletQuery.error || listQuery.error;
    if (!err) return;
    const status = (err as any)?.response?.status;
    if (status === 401) return;
    if (status === 403) {
      const detail = String((err as any)?.response?.data?.detail || "");
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
    toast.error(getApiErrorMessage(err, "加载失败，请稍后重试"));
  }, [walletQuery.error, listQuery.error, toast, user]);

  const total = listQuery.data?.total ?? 0;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total]
  );
  const items = listQuery.data?.items ?? [];

  const exportIncomeRecords = async () => {
    if (exporting) return;
    try {
      setExporting(true);
      const res = await api.get("/lawyer/income-records/export", {
        params: {
          ...(statusFilter ? { status: statusFilter } : {}),
        },
        responseType: "blob",
      });

      const cd = (res.headers as any)?.["content-disposition"];
      let filename = "income_records.csv";
      if (typeof cd === "string") {
        const m = /filename\*=UTF-8''([^;]+)|filename=([^;]+)/i.exec(cd);
        const raw = (m?.[1] || m?.[2] || "").trim();
        if (raw) {
          filename = decodeURIComponent(raw.replace(/^"|"$/g, ""));
        }
      }

      const blob = new Blob([res.data], {
        type: (res.headers as any)?.["content-type"] || "text/csv",
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      const status = (e as any)?.response?.status;
      if (status === 403) {
        const detail = String((e as any)?.response?.data?.detail || "");
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
      toast.error(getApiErrorMessage(e, "导出失败，请稍后重试"));
    } finally {
      setExporting(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律师"
          title="我的收入"
          description="查看收入与结算状态"
          layout="mdStart"
          tone={actualTheme}
        />
        <EmptyState
          icon={CreditCard}
          title="请先登录"
          description="登录后即可查看收入"
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
          title="我的收入"
          description="查看收入与结算状态"
          layout="mdStart"
          tone={actualTheme}
          right={<Skeleton width="90px" height="36px" />}
        />

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, idx) => (
            <div
              key={idx}
              className="rounded-2xl border border-slate-200/70 bg-white p-4 dark:border-white/10 dark:bg-white/[0.02]"
            >
              <Skeleton width="72px" height="12px" />
              <div className="mt-2">
                <Skeleton width="90px" height="20px" />
              </div>
            </div>
          ))}
        </div>

        <Card variant="surface" padding="lg">
          <div className="flex items-center justify-between gap-2 mb-4">
            <Skeleton width="120px" height="18px" />
            <Skeleton width="72px" height="32px" />
          </div>
          <ListSkeleton count={3} />
        </Card>
      </div>
    );
  }

  const wallet = walletQuery.data;

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="律师"
        title="我的收入"
        description="查看收入与结算状态"
        layout="mdStart"
        tone={actualTheme}
        right={
          <Button
            variant="outline"
            icon={RefreshCw}
            onClick={() => {
              walletQuery.refetch();
              listQuery.refetch();
            }}
            isLoading={walletQuery.isFetching || listQuery.isFetching}
            loadingText="刷新中..."
            disabled={walletQuery.isFetching || listQuery.isFetching}
          >
            刷新
          </Button>
        }
      />

      {wallet ? (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <Card variant="surface" padding="md">
            <div className="text-sm text-slate-600 dark:text-white/50">
              累计收入
            </div>
            <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
              ¥{wallet.total_income.toFixed(2)}
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="text-sm text-slate-600 dark:text-white/50">
              可提现
            </div>
            <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
              ¥{wallet.available_amount.toFixed(2)}
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="text-sm text-slate-600 dark:text-white/50">
              待结算（冻结期）
            </div>
            <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
              ¥{wallet.pending_amount.toFixed(2)}
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="text-sm text-slate-600 dark:text-white/50">
              提现中（冻结）
            </div>
            <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
              ¥{wallet.frozen_amount.toFixed(2)}
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="text-sm text-slate-600 dark:text-white/50">
              已提现
            </div>
            <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
              ¥{wallet.withdrawn_amount.toFixed(2)}
            </div>
          </Card>
        </div>
      ) : null}

      <Card variant="surface" padding="lg">
        <div className="flex items-center justify-between gap-2 mb-4">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-slate-400 dark:text-white/40" />
            <div className="text-sm font-medium text-slate-700 dark:text-white/70">
              收入明细
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            icon={Download}
            onClick={exportIncomeRecords}
            isLoading={exporting}
            loadingText="导出中..."
          >
            导出
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-2 mb-4">
          <Button
            variant={statusFilter === "" ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              setPage(1);
              setStatusFilter("");
            }}
          >
            全部
          </Button>
          <Button
            variant={statusFilter === "pending" ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              setPage(1);
              setStatusFilter("pending");
            }}
          >
            冻结中
          </Button>
          <Button
            variant={statusFilter === "settled" ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              setPage(1);
              setStatusFilter("settled");
            }}
          >
            可提现
          </Button>
          <Button
            variant={statusFilter === "withdrawn" ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              setPage(1);
              setStatusFilter("withdrawn");
            }}
          >
            已提现
          </Button>
        </div>

        {listQuery.isLoading && items.length === 0 ? (
          <ListSkeleton count={3} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="暂无收入记录"
            description="完成咨询后会生成收入记录"
            tone={actualTheme}
          />
        ) : (
          <div className="space-y-3">
            {items.map((r) => (
              <Card
                key={r.id}
                variant="surface"
                padding="md"
                className="border border-slate-200/70 dark:border-white/10"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <div className="text-sm font-semibold text-slate-900 dark:text-white">
                        收入 ¥{Number(r.lawyer_income || 0).toFixed(2)}
                      </div>
                      <Badge variant={statusVariant(r.status)} size="sm">
                        {statusLabel(r.status)}
                      </Badge>
                    </div>
                    <div className="mt-2 text-xs text-slate-600 dark:text-white/60 space-y-1">
                      <div>
                        来源：
                        {r.consultation_subject
                          ? r.consultation_subject
                          : r.consultation_id
                          ? `咨询 #${r.consultation_id}`
                          : "-"}
                      </div>
                      <div>订单：{r.order_no ? r.order_no : "-"}</div>
                      <div>
                        用户支付：¥{Number(r.user_paid_amount || 0).toFixed(2)}
                        ，平台抽成：¥{Number(r.platform_fee || 0).toFixed(2)}
                      </div>
                      <div>
                        创建时间：{new Date(r.created_at).toLocaleString()}
                      </div>
                      {r.settle_time ? (
                        <div>
                          可结算时间：{new Date(r.settle_time).toLocaleString()}
                        </div>
                      ) : null}
                    </div>
                  </div>
                  <div className="text-xs text-slate-500 dark:text-white/40">
                    #{r.id}
                  </div>
                </div>
              </Card>
            ))}

            <div className="pt-4">
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                onPageChange={setPage}
              />
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
