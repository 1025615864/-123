import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Calendar, Filter, RefreshCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import { useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import { Badge, Button, Card, Input, ListSkeleton, Pagination } from "../../components/ui";

interface NewsSource {
  id: number;
  name: string;
  is_enabled: boolean;
}

interface NewsSourceListResponse {
  items: NewsSource[];
}

interface NewsIngestRun {
  id: number;
  source_id?: number | null;
  source_name?: string | null;
  feed_url?: string | null;
  status: string;
  fetched: number;
  inserted: number;
  skipped: number;
  errors: number;
  last_error?: string | null;
  started_at: string;
  finished_at?: string | null;
  created_at: string;
}

interface NewsIngestRunListResponse {
  items: NewsIngestRun[];
  total: number;
  page: number;
  page_size: number;
}

function normalizeStatus(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

function getStatusBadge(statusRaw: unknown) {
  const s = normalizeStatus(statusRaw);
  if (s === "success") return { label: "成功", variant: "success" as const };
  if (s === "running") return { label: "运行中", variant: "warning" as const };
  if (s === "failed") return { label: "失败", variant: "danger" as const };
  return { label: s || "-", variant: "default" as const };
}

function formatTime(value: string | null | undefined): string {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function NewsIngestRunsPage() {
  const toast = useToast();
  const [searchParams] = useSearchParams();

  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [sourceId, setSourceId] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [fromDt, setFromDt] = useState<string>("");
  const [toDt, setToDt] = useState<string>("");

  useEffect(() => {
    const sid = String(searchParams.get("source_id") || "").trim();
    if (sid) setSourceId(sid);
  }, [searchParams]);

  useEffect(() => {
    setPage(1);
  }, [sourceId, status, fromDt, toDt]);

  const sourcesQuery = useQuery({
    queryKey: ["admin-news-sources-mini"] as const,
    queryFn: async () => {
      const res = await api.get("/news/admin/sources");
      return res.data as NewsSourceListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!sourcesQuery.error) return;
    toast.error(getApiErrorMessage(sourcesQuery.error, "来源加载失败"));
  }, [sourcesQuery.error, toast]);

  const runsQueryKey = useMemo(
    () =>
      [
        "admin-news-ingest-runs",
        {
          page,
          pageSize,
          sourceId,
          status,
          fromDt,
          toDt,
        },
      ] as const,
    [page, pageSize, sourceId, status, fromDt, toDt]
  );

  const runsQuery = useQuery({
    queryKey: runsQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      if (sourceId.trim()) params.set("source_id", sourceId.trim());
      if (status.trim()) params.set("status", status.trim());
      if (fromDt.trim()) params.set("from", fromDt.trim());
      if (toDt.trim()) params.set("to", toDt.trim());

      const res = await api.get(`/news/admin/ingest-runs?${params.toString()}`);
      return res.data as NewsIngestRunListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!runsQuery.error) return;
    toast.error(getApiErrorMessage(runsQuery.error, "运行记录加载失败"));
  }, [runsQuery.error, toast]);

  const runs = runsQuery.data?.items ?? [];
  const total = Number(runsQuery.data?.total ?? 0);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const busy = runsQuery.isFetching;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            采集运行记录
          </h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">
            查看每次 RSS 抓取的运行状态与统计
          </p>
        </div>
        <Button
          variant="outline"
          icon={RefreshCw}
          onClick={() => runsQuery.refetch()}
          isLoading={busy}
          loadingText="刷新中..."
          disabled={busy}
        >
          刷新
        </Button>
      </div>

      {/* 筛选器 */}
      <Card variant="surface" padding="md">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-slate-500 dark:text-white/50" />
            <span className="text-slate-700 text-sm dark:text-white/70">筛选：</span>
          </div>

          <div className="min-w-[220px]">
            <label className="block text-sm font-medium text-slate-700 dark:text-white/70 mb-2">
              来源
            </label>
            <select
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-200/70 bg-white text-slate-900 text-sm outline-none transition hover:border-slate-300 focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-900"
            >
              <option value="">全部来源</option>
              {(sourcesQuery.data?.items ?? []).map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.name} {s.is_enabled ? "" : "(停用)"}
                </option>
              ))}
            </select>
          </div>

          <div className="min-w-[160px]">
            <label className="block text-sm font-medium text-slate-700 dark:text-white/70 mb-2">
              状态
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-200/70 bg-white text-slate-900 text-sm outline-none transition hover:border-slate-300 focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-900"
            >
              <option value="">全部</option>
              <option value="running">running</option>
              <option value="success">success</option>
              <option value="failed">failed</option>
            </select>
          </div>

          <div className="min-w-[220px]">
            <Input
              label="开始时间（from）"
              type="datetime-local"
              value={fromDt}
              onChange={(e) => setFromDt(e.target.value)}
              right={<Calendar className="h-4 w-4 text-slate-400 dark:text-white/35" />}
            />
          </div>

          <div className="min-w-[220px]">
            <Input
              label="结束时间（to）"
              type="datetime-local"
              value={toDt}
              onChange={(e) => setToDt(e.target.value)}
              right={<Calendar className="h-4 w-4 text-slate-400 dark:text-white/35" />}
            />
          </div>

          {(sourceId || status || fromDt || toDt) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSourceId("");
                setStatus("");
                setFromDt("");
                setToDt("");
              }}
            >
              清除筛选
            </Button>
          )}
        </div>
      </Card>

      {/* 列表 */}
      <Card variant="surface" padding="none">
        {runsQuery.isLoading && runs.length === 0 ? (
          <div className="p-6">
            <ListSkeleton count={6} />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200/70 dark:border-white/10">
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    时间
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    来源
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    状态
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    统计
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    错误
                  </th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const st = getStatusBadge(r.status);
                  return (
                    <tr
                      key={r.id}
                      className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5"
                    >
                      <td className="py-3 px-4 text-sm text-slate-600 dark:text-white/60">
                        <div className="space-y-1">
                          <p>start：{formatTime(r.started_at)}</p>
                          <p>end：{formatTime(r.finished_at)}</p>
                          <p className="text-xs text-slate-500 dark:text-white/40">
                            created：{formatTime(r.created_at)}
                          </p>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="space-y-1">
                          <p className="text-slate-900 text-sm font-medium dark:text-white">
                            {r.source_name || `source#${r.source_id ?? "-"}`}
                          </p>
                          <p className="text-xs text-slate-500 dark:text-white/40 break-all">
                            {r.feed_url || "-"}
                          </p>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={st.variant} size="sm">
                          {st.label}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-sm text-slate-700 dark:text-white/70">
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="info" size="sm">
                            fetched:{Number(r.fetched ?? 0)}
                          </Badge>
                          <Badge variant="success" size="sm">
                            inserted:{Number(r.inserted ?? 0)}
                          </Badge>
                          <Badge variant="default" size="sm">
                            skipped:{Number(r.skipped ?? 0)}
                          </Badge>
                          <Badge
                            variant={Number(r.errors ?? 0) > 0 ? "danger" : "default"}
                            size="sm"
                          >
                            errors:{Number(r.errors ?? 0)}
                          </Badge>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm">
                        {r.last_error ? (
                          <p className="text-red-500/90 break-words max-w-[520px]">
                            {r.last_error}
                          </p>
                        ) : (
                          <span className="text-slate-400 dark:text-white/30">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}

                {runs.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="py-10 text-center text-slate-500 text-sm dark:text-white/40"
                    >
                      暂无运行记录
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
