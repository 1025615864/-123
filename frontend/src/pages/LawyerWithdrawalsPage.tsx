import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { History, RefreshCw } from "lucide-react";
import PageHeader from "../components/PageHeader";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Loading,
  Modal,
  Pagination,
} from "../components/ui";
import api from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";

type WithdrawalItem = {
  id: number;
  request_no: string;
  lawyer_id: number;
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

type DetailResp = WithdrawalItem;

type ListResp = {
  items: WithdrawalItem[];
  total: number;
  page: number;
  page_size: number;
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

function statusLabel(s: string): string {
  const v = String(s || "").toLowerCase();
  if (v === "pending") return "待审核";
  if (v === "approved") return "已通过（待打款）";
  if (v === "completed") return "已完成";
  if (v === "rejected") return "已驳回";
  if (v === "failed") return "打款失败";
  return s || "未知";
}

export default function LawyerWithdrawalsPage() {
  const { isAuthenticated } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();

  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<DetailResp | null>(null);

  const listQuery = useQuery({
    queryKey: ["lawyer-withdrawals", { page, pageSize }],
    queryFn: async () => {
      const res = await api.get("/lawyer/withdrawals", {
        params: { page, page_size: pageSize },
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
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!listQuery.error) return;
    const status = (listQuery.error as any)?.response?.status;
    if (status === 401) return;
    toast.error(getApiErrorMessage(listQuery.error, "加载失败，请稍后重试"));
  }, [listQuery.error, toast]);

  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total]
  );

  const openDetail = async (id: number) => {
    setDetailOpen(true);
    setDetail(null);
    try {
      const res = await api.get(`/lawyer/withdrawals/${id}`);
      setDetail(res.data as DetailResp);
    } catch (e) {
      toast.error(getApiErrorMessage(e, "加载详情失败"));
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律师"
          title="提现记录"
          description="查看提现申请与审核状态"
          layout="mdStart"
          tone={actualTheme}
        />
        <EmptyState
          icon={History}
          title="请先登录"
          description="登录后即可查看提现记录"
          tone={actualTheme}
        />
      </div>
    );
  }

  if (listQuery.isLoading && items.length === 0) {
    return <Loading text="加载中..." tone={actualTheme} />;
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="律师"
        title="提现记录"
        description="查看提现申请与审核状态"
        layout="mdStart"
        tone={actualTheme}
        right={
          <Button
            variant="outline"
            icon={RefreshCw}
            onClick={() => listQuery.refetch()}
            disabled={listQuery.isFetching}
          >
            刷新
          </Button>
        }
      />

      <Card variant="surface" padding="lg">
        {items.length === 0 ? (
          <EmptyState
            icon={History}
            title="暂无记录"
            description="你还没有提现申请"
            tone={actualTheme}
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
                        ¥{Number(w.amount || 0).toFixed(2)}
                      </div>
                      <Badge variant={statusVariant(w.status)} size="sm">
                        {statusLabel(w.status)}
                      </Badge>
                    </div>
                    <div className="mt-2 text-xs text-slate-600 dark:text-white/60 space-y-1">
                      <div>申请单号：{w.request_no}</div>
                      <div>收款账户：{w.account_info_masked}</div>
                      <div>
                        申请时间：{new Date(w.created_at).toLocaleString()}
                      </div>
                      {w.reject_reason ? (
                        <div className="text-red-600 dark:text-red-300">
                          驳回原因：{w.reject_reason}
                        </div>
                      ) : null}
                      {w.remark ? <div>备注：{w.remark}</div> : null}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => openDetail(w.id)}>
                      查看详情
                    </Button>
                    <div className="text-xs text-slate-500 dark:text-white/40">#{w.id}</div>
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
        onClose={() => setDetailOpen(false)}
        title="提现详情"
        description={detail ? `申请单号：${detail.request_no}` : undefined}
        size="lg"
      >
        {!detail ? (
          <Loading text="加载中..." tone={actualTheme} />
        ) : (
          <div className="space-y-3">
            <Card variant="surface" padding="md">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  ¥{Number(detail.amount || 0).toFixed(2)}
                </div>
                <Badge variant={statusVariant(detail.status)} size="sm">
                  {statusLabel(detail.status)}
                </Badge>
              </div>
              <div className="mt-2 text-xs text-slate-600 dark:text-white/60 space-y-1 break-words">
                <div>手续费：¥{Number(detail.fee || 0).toFixed(2)}，实际到账：¥{Number(detail.actual_amount || 0).toFixed(2)}</div>
                <div>收款账户：{detail.account_info_masked}</div>
                <div>申请时间：{new Date(detail.created_at).toLocaleString()}</div>
                {detail.reviewed_at ? <div>审核时间：{new Date(detail.reviewed_at).toLocaleString()}</div> : null}
                {detail.completed_at ? <div>完成时间：{new Date(detail.completed_at).toLocaleString()}</div> : null}
                {detail.reject_reason ? (
                  <div className="text-red-600 dark:text-red-300">驳回原因：{detail.reject_reason}</div>
                ) : null}
                {detail.remark ? <div>备注：{detail.remark}</div> : null}
              </div>
            </Card>

            <div className="flex justify-end">
              <Button variant="outline" onClick={() => setDetailOpen(false)}>
                关闭
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
