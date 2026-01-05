import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Download, RefreshCw, TrendingUp } from "lucide-react";
import api from "../../api/client";
import { Badge, Button, Card, EmptyState, Loading } from "../../components/ui";
import { useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";

type WalletSummary = {
  total_income: number;
  withdrawn_amount: number;
  pending_amount: number;
  frozen_amount: number;
  available_amount: number;
};

type WithdrawalSummary = {
  pending_count: number;
  pending_amount: number;
  approved_count: number;
  approved_amount: number;
  completed_month_count: number;
  completed_month_amount: number;
};

type TopLawyerItem = {
  lawyer_id: number;
  lawyer_name: string | null;
  income_records: number;
  lawyer_income: number;
  platform_fee: number;
};

type StatsResp = {
  month_start: string;
  month_end: string;
  wallet_summary: WalletSummary;
  withdrawal_summary: WithdrawalSummary;
  platform_fee_month_total: number;
  lawyer_income_month_total: number;
  top_lawyers: TopLawyerItem[];
};

function formatMoney(n: number | null | undefined) {
  return `¥${Number(n || 0).toFixed(2)}`;
}

export default function SettlementStatsPage() {
  const toast = useToast();

  const [exporting, setExporting] = useState(false);

  const statsQuery = useQuery({
    queryKey: ["admin-settlement-stats"],
    queryFn: async () => {
      const res = await api.get("/admin/settlement-stats");
      return res.data as StatsResp;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!statsQuery.error) return;
    toast.error(getApiErrorMessage(statsQuery.error, "加载失败，请稍后重试"));
  }, [statsQuery.error, toast]);

  const data = statsQuery.data;

  const monthRangeText = useMemo(() => {
    if (!data) return "";
    const s = new Date(data.month_start);
    const e = new Date(data.month_end);
    if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return "";
    return `${s.toLocaleDateString()} - ${e.toLocaleDateString()}`;
  }, [data]);

  if (statsQuery.isLoading && !data) {
    return <Loading text="加载中..." />;
  }

  if (!data) {
    return (
      <EmptyState
        icon={BarChart3}
        title="暂无统计数据"
        description="当前没有可展示的结算统计"
      />
    );
  }

  const w = data.wallet_summary;
  const wd = data.withdrawal_summary;

  const exportIncomeRecords = async () => {
    if (exporting) return;
    try {
      setExporting(true);
      const res = await api.get("/admin/income-records/export", {
        params: {
          from: data.month_start,
          to: data.month_end,
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
      toast.error(getApiErrorMessage(e, "导出失败，请稍后重试"));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-white">
            结算统计
          </h1>
          <p className="text-sm text-slate-600 dark:text-white/50">
            {monthRangeText ? `本月区间：${monthRangeText}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            icon={Download}
            onClick={exportIncomeRecords}
            isLoading={exporting}
          >
            导出收入
          </Button>
          <Button
            variant="outline"
            icon={RefreshCw}
            onClick={() => statsQuery.refetch()}
            disabled={statsQuery.isFetching}
          >
            刷新
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card variant="surface" padding="md">
          <div className="text-sm text-slate-600 dark:text-white/50">累计收入</div>
          <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
            {formatMoney(w.total_income)}
          </div>
        </Card>
        <Card variant="surface" padding="md">
          <div className="text-sm text-slate-600 dark:text-white/50">可提现</div>
          <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
            {formatMoney(w.available_amount)}
          </div>
        </Card>
        <Card variant="surface" padding="md">
          <div className="text-sm text-slate-600 dark:text-white/50">待结算（冻结期）</div>
          <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
            {formatMoney(w.pending_amount)}
          </div>
        </Card>
        <Card variant="surface" padding="md">
          <div className="text-sm text-slate-600 dark:text-white/50">提现中（冻结）</div>
          <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
            {formatMoney(w.frozen_amount)}
          </div>
        </Card>
        <Card variant="surface" padding="md">
          <div className="text-sm text-slate-600 dark:text-white/50">已提现</div>
          <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
            {formatMoney(w.withdrawn_amount)}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card variant="surface" padding="md">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-slate-700 dark:text-white/70">
              待审核提现
            </div>
            <Badge variant="warning" size="sm">
              pending
            </Badge>
          </div>
          <div className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">
            {wd.pending_count} 笔 / {formatMoney(wd.pending_amount)}
          </div>
        </Card>
        <Card variant="surface" padding="md">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-slate-700 dark:text-white/70">
              待打款
            </div>
            <Badge variant="info" size="sm">
              approved
            </Badge>
          </div>
          <div className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">
            {wd.approved_count} 笔 / {formatMoney(wd.approved_amount)}
          </div>
        </Card>
        <Card variant="surface" padding="md">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-slate-700 dark:text-white/70">
              本月已完成提现
            </div>
            <Badge variant="success" size="sm">
              completed
            </Badge>
          </div>
          <div className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">
            {wd.completed_month_count} 笔 / {formatMoney(wd.completed_month_amount)}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card variant="surface" padding="md">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-slate-400 dark:text-white/40" />
            <div className="text-sm font-medium text-slate-700 dark:text-white/70">
              本月平台抽成
            </div>
          </div>
          <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
            {formatMoney(data.platform_fee_month_total)}
          </div>
        </Card>
        <Card variant="surface" padding="md">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-slate-400 dark:text-white/40" />
            <div className="text-sm font-medium text-slate-700 dark:text-white/70">
              本月律师收入
            </div>
          </div>
          <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
            {formatMoney(data.lawyer_income_month_total)}
          </div>
        </Card>
      </div>

      <Card variant="surface" padding="lg">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="h-4 w-4 text-slate-400 dark:text-white/40" />
          <div className="text-sm font-medium text-slate-700 dark:text-white/70">
            本月律师收入排行（Top 20）
          </div>
        </div>

        {data.top_lawyers.length === 0 ? (
          <EmptyState
            icon={BarChart3}
            title="暂无排行数据"
            description="本月尚无收入记录"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 dark:text-white/40">
                  <th className="py-2 pr-4">律师</th>
                  <th className="py-2 pr-4">收入记录</th>
                  <th className="py-2 pr-4">律师收入</th>
                  <th className="py-2 pr-4">平台抽成</th>
                </tr>
              </thead>
              <tbody>
                {data.top_lawyers.map((it) => (
                  <tr
                    key={it.lawyer_id}
                    className="border-t border-slate-200/70 dark:border-white/10"
                  >
                    <td className="py-2 pr-4 text-slate-900 dark:text-white">
                      {it.lawyer_name
                        ? `${it.lawyer_name} (#${it.lawyer_id})`
                        : `#${it.lawyer_id}`}
                    </td>
                    <td className="py-2 pr-4 text-slate-700 dark:text-white/70">
                      {Number(it.income_records || 0)}
                    </td>
                    <td className="py-2 pr-4 text-slate-700 dark:text-white/70">
                      {formatMoney(it.lawyer_income)}
                    </td>
                    <td className="py-2 pr-4 text-slate-700 dark:text-white/70">
                      {formatMoney(it.platform_fee)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
