import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CreditCard,
  Download,
  RefreshCw,
  Search,
  ShieldCheck,
  ShieldX,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Modal,
  Pagination,
  Textarea,
  ListSkeleton,
  Skeleton,
} from "../../components/ui";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";

type WithdrawalItem = {
  id: number;
  request_no: string;
  lawyer_id: number;
  lawyer_name?: string | null;
  lawyer_rating?: number | null;
  lawyer_completed_count?: number | null;
  platform_fee_rate?: number | null;
  amount: number;
  fee: number;
  actual_amount: number;
  withdraw_method: string;
  account_info_masked: string;
  status: string;
  reject_reason: string | null;
  admin_id: number | null;
  reviewed_at: string | null;
  completed_at: string | null;
  remark: string | null;
  created_at: string;
  updated_at: string;
};

type ListResp = {
  items: WithdrawalItem[];
  total: number;
  page: number;
  page_size: number;
};

type DetailResp = {
  id: number;
  request_no: string;
  lawyer_id: number;
  lawyer_name?: string | null;
  lawyer_rating?: number | null;
  lawyer_completed_count?: number | null;
  platform_fee_rate?: number | null;
  amount: number;
  fee: number;
  actual_amount: number;
  withdraw_method: string;
  account_info: string;
  status: string;
  reject_reason: string | null;
  admin_id: number | null;
  reviewed_at: string | null;
  completed_at: string | null;
  remark: string | null;
  created_at: string;
  updated_at: string;
};

function statusVariant(
  s: string
): "default" | "primary" | "success" | "warning" | "danger" | "info" {
  const v = String(s || "").toLowerCase();
  if (v === "pending") return "warning";
  if (v === "approved") return "info";
  if (v === "completed") return "success";
  if (v === "rejected" || v === "failed") return "danger";
  return "default";
}

function formatPlatformFeeRate(rate: number | null | undefined): string {
  if (rate == null || Number.isNaN(Number(rate))) return "-";
  return `${(Number(rate) * 100).toFixed(0)}%`;
}

function statusLabel(s: string): string {
  const v = String(s || "").toLowerCase();
  if (v === "pending") return "待审核";
  if (v === "approved") return "已通过（待打款）";
  if (v === "completed") return "已完成";
  if (v === "rejected") return "已驳回";
  if (v === "failed") return "打款失败";
  return s || "未知";
}

export default function WithdrawalsPage() {
  const toast = useToast();

  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [statusFilter, setStatusFilter] = useState("");
  const [keyword, setKeyword] = useState("");

  const [exporting, setExporting] = useState(false);

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DetailResp | null>(null);

  const [remark, setRemark] = useState("");
  const [rejectReason, setRejectReason] = useState("");

  const listQuery = useQuery({
    queryKey: ["admin-withdrawals", { page, pageSize, statusFilter, keyword }],
    queryFn: async () => {
      const res = await api.get("/admin/withdrawals", {
        params: {
          page,
          page_size: pageSize,
          ...(statusFilter ? { status: statusFilter } : {}),
          ...(keyword.trim() ? { keyword: keyword.trim() } : {}),
        },
      });
      const data = res.data || {};
      return {
        items: Array.isArray(data?.items)
          ? (data.items as WithdrawalItem[])
          : ([] as WithdrawalItem[]),
        total: Number(data?.total || 0),
        page: Number(data?.page || page),
        page_size: Number(data?.page_size || pageSize),
      } satisfies ListResp;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!listQuery.error) return;
    toast.error(getApiErrorMessage(listQuery.error, "加载失败，请稍后重试"));
  }, [listQuery.error, toast]);

  const total = listQuery.data?.total ?? 0;
  const items = listQuery.data?.items ?? [];
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total]
  );

  const exportWithdrawals = async () => {
    if (exporting) return;
    try {
      setExporting(true);
      const res = await api.get("/admin/withdrawals/export", {
        params: {
          ...(statusFilter ? { status: statusFilter } : {}),
          ...(keyword.trim() ? { keyword: keyword.trim() } : {}),
        },
        responseType: "blob",
      });

      const cd = (res.headers as any)?.["content-disposition"];
      let filename = "withdrawals.csv";
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
      toast.error(getApiErrorMessage(e, "导出失败，请稍后重试"));
    } finally {
      setExporting(false);
    }
  };

  const openDetail = async (id: number) => {
    setDetailOpen(true);
    setDetailId(id);
    setDetail(null);
    setRemark("");
    setRejectReason("");
    try {
      const res = await api.get(`/admin/withdrawals/${id}`);
      const d = res.data as DetailResp;
      setDetail(d);
      setRemark(String(d.remark || ""));
      setRejectReason(String(d.reject_reason || ""));
    } catch (e) {
      toast.error(getApiErrorMessage(e, "加载详情失败"));
    }
  };

  const approveMutation = useAppMutation<
    unknown,
    { id: number; remark: string }
  >({
    mutationFn: async ({ id, remark }) => {
      await api.post(`/admin/withdrawals/${id}/approve`, {
        remark: remark.trim() || null,
      });
    },
    successMessage: "已通过",
    errorMessageFallback: "操作失败",
    onSuccess: () => {
      listQuery.refetch();
      if (detailId) openDetail(detailId);
    },
  });

  const rejectMutation = useAppMutation<
    unknown,
    { id: number; reject_reason: string; remark: string }
  >({
    mutationFn: async ({ id, reject_reason, remark }) => {
      await api.post(`/admin/withdrawals/${id}/reject`, {
        reject_reason: reject_reason.trim(),
        remark: remark.trim() || null,
      });
    },
    successMessage: "已驳回",
    errorMessageFallback: "操作失败",
    onSuccess: () => {
      listQuery.refetch();
      if (detailId) openDetail(detailId);
    },
  });

  const completeMutation = useAppMutation<
    unknown,
    { id: number; remark: string }
  >({
    mutationFn: async ({ id, remark }) => {
      await api.post(`/admin/withdrawals/${id}/complete`, {
        remark: remark.trim() || null,
      });
    },
    successMessage: "已标记完成",
    errorMessageFallback: "操作失败",
    onSuccess: () => {
      listQuery.refetch();
      if (detailId) openDetail(detailId);
    },
  });

  const failMutation = useAppMutation<unknown, { id: number; remark: string }>({
    mutationFn: async ({ id, remark }) => {
      await api.post(`/admin/withdrawals/${id}/fail`, {
        remark: remark.trim() || null,
      });
    },
    successMessage: "已标记失败",
    errorMessageFallback: "操作失败",
    onSuccess: () => {
      listQuery.refetch();
      if (detailId) openDetail(detailId);
    },
  });

  if (listQuery.isLoading && items.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <Skeleton width="96px" height="20px" />
            <div className="mt-2">
              <Skeleton width="220px" height="14px" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Skeleton width="86px" height="36px" />
            <Skeleton width="86px" height="36px" />
          </div>
        </div>

        <Card variant="surface" padding="lg">
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {Array.from({ length: 4 }).map((_, idx) => (
              <Skeleton key={idx} width="64px" height="32px" />
            ))}
            <div className="flex-1" />
            <Skeleton width="220px" height="40px" />
          </div>
          <ListSkeleton count={4} />
        </Card>
      </div>
    );
  }

  const detailActionBusy =
    approveMutation.isPending ||
    rejectMutation.isPending ||
    completeMutation.isPending ||
    failMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-white">
            提现审核
          </h1>
          <p className="text-sm text-slate-600 dark:text-white/50">
            审核提现申请并标记打款结果
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            icon={Download}
            onClick={exportWithdrawals}
            isLoading={exporting}
            loadingText="导出中..."
          >
            导出
          </Button>
          <Button
            variant="outline"
            icon={RefreshCw}
            onClick={() => listQuery.refetch()}
            isLoading={listQuery.isFetching}
            loadingText="刷新中..."
            disabled={listQuery.isFetching}
          >
            刷新
          </Button>
        </div>
      </div>

      <Card variant="surface" padding="lg">
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
            待审核
          </Button>
          <Button
            variant={statusFilter === "approved" ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              setPage(1);
              setStatusFilter("approved");
            }}
          >
            待打款
          </Button>
          <Button
            variant={statusFilter === "completed" ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              setPage(1);
              setStatusFilter("completed");
            }}
          >
            已完成
          </Button>

          <div className="flex-1" />

          <div className="w-full sm:w-72">
            <Input
              icon={Search}
              value={keyword}
              onChange={(e) => {
                setPage(1);
                setKeyword(e.target.value);
              }}
              placeholder="搜索申请单号"
            />
          </div>
        </div>

        {items.length === 0 ? (
          <EmptyState
            icon={CreditCard}
            title="暂无数据"
            description="当前没有匹配的提现申请"
          />
        ) : (
          <div className="space-y-3">
            {items.map((w) => (
              <Card
                key={w.id}
                variant="surface"
                padding="md"
                className="border border-slate-200/70 dark:border-white/10"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <div className="text-sm font-semibold text-slate-900 dark:text-white">
                        {w.request_no}
                      </div>
                      <Badge variant={statusVariant(w.status)} size="sm">
                        {statusLabel(w.status)}
                      </Badge>
                    </div>

                    <div className="mt-2 text-xs text-slate-600 dark:text-white/60 space-y-1">
                      <div>
                        律师：
                        {w.lawyer_name
                          ? `${w.lawyer_name} (#${w.lawyer_id})`
                          : `#${w.lawyer_id}`}
                      </div>
                      <div>
                        评分：
                        {w.lawyer_rating != null
                          ? Number(w.lawyer_rating).toFixed(1)
                          : "-"}
                        ，完成单：
                        {w.lawyer_completed_count != null
                          ? Number(w.lawyer_completed_count)
                          : "-"}
                        ，平台抽成：
                        {formatPlatformFeeRate(w.platform_fee_rate)}
                      </div>
                      <div>
                        金额：¥{Number(w.amount || 0).toFixed(2)}（实际到账 ¥
                        {Number(w.actual_amount || 0).toFixed(2)}）
                      </div>
                      <div>账户：{w.account_info_masked}</div>
                      <div>
                        申请时间：{new Date(w.created_at).toLocaleString()}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openDetail(w.id)}
                    >
                      处理
                    </Button>
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

      <Modal
        isOpen={detailOpen}
        onClose={() => {
          if (detailActionBusy) return;
          setDetailOpen(false);
        }}
        title="提现审核"
        description={detail ? `申请单号：${detail.request_no}` : undefined}
        size="lg"
      >
        {!detail ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <Skeleton width="120px" height="18px" />
              <Skeleton width="80px" height="22px" />
            </div>
            <Skeleton width="100%" height="14px" />
            <Skeleton width="92%" height="14px" />
            <Skeleton width="86%" height="14px" />
            <div className="pt-2">
              <Skeleton width="100%" height="96px" />
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Card variant="surface" padding="md">
              <div className="text-sm text-slate-700 dark:text-white/70">
                律师：
                {detail.lawyer_name
                  ? `${detail.lawyer_name} (#${detail.lawyer_id})`
                  : `#${detail.lawyer_id}`}
              </div>
              <div className="mt-1 text-xs text-slate-600 dark:text-white/60">
                评分：
                {detail.lawyer_rating != null
                  ? Number(detail.lawyer_rating).toFixed(1)
                  : "-"}
                ，完成单：
                {detail.lawyer_completed_count != null
                  ? Number(detail.lawyer_completed_count)
                  : "-"}
                ，平台抽成：
                {formatPlatformFeeRate(detail.platform_fee_rate)}
              </div>
              <div className="mt-1 text-sm text-slate-700 dark:text-white/70">
                金额：¥{Number(detail.amount || 0).toFixed(2)}（手续费 ¥
                {Number(detail.fee || 0).toFixed(2)}，实际到账 ¥
                {Number(detail.actual_amount || 0).toFixed(2)}）
              </div>
              <div className="mt-1 text-xs text-slate-600 dark:text-white/60 break-words">
                账户信息：{detail.account_info}
              </div>
              <div className="mt-2">
                <Badge variant={statusVariant(detail.status)} size="sm">
                  {statusLabel(detail.status)}
                </Badge>
              </div>
            </Card>

            <Textarea
              label="备注（可选）"
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              disabled={detailActionBusy}
              rows={4}
            />
            <Textarea
              label="驳回原因（驳回时必填）"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              disabled={detailActionBusy}
              rows={3}
            />

            <div className="flex flex-wrap justify-end gap-2">
              <Button
                variant="outline"
                icon={ShieldCheck}
                isLoading={approveMutation.isPending}
                loadingText="处理中..."
                onClick={() => {
                  approveMutation.mutate({ id: detail.id, remark });
                }}
                disabled={String(detail.status).toLowerCase() !== "pending" || detailActionBusy}
              >
                通过
              </Button>
              <Button
                variant="danger"
                icon={ShieldX}
                isLoading={rejectMutation.isPending}
                loadingText="处理中..."
                onClick={() => {
                  if (!rejectReason.trim()) {
                    toast.error("请填写驳回原因");
                    return;
                  }
                  rejectMutation.mutate({
                    id: detail.id,
                    reject_reason: rejectReason,
                    remark,
                  });
                }}
                disabled={String(detail.status).toLowerCase() !== "pending" || detailActionBusy}
              >
                驳回
              </Button>
              <Button
                variant="outline"
                icon={CheckCircle2}
                isLoading={completeMutation.isPending}
                loadingText="处理中..."
                onClick={() => {
                  completeMutation.mutate({ id: detail.id, remark });
                }}
                disabled={String(detail.status).toLowerCase() !== "approved" || detailActionBusy}
              >
                标记完成
              </Button>
              <Button
                variant="danger"
                icon={XCircle}
                isLoading={failMutation.isPending}
                loadingText="处理中..."
                onClick={() => {
                  failMutation.mutate({ id: detail.id, remark });
                }}
                disabled={String(detail.status).toLowerCase() !== "approved" || detailActionBusy}
              >
                标记失败
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
