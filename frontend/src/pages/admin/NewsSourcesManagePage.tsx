import { useEffect, useMemo, useState } from "react";
import { Plus, Edit, Trash2, Power, Play, RefreshCw, Rss } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import {
  Card,
  Button,
  Badge,
  Modal,
  ModalActions,
  Input,
  ListSkeleton,
} from "../../components/ui";

interface NewsSource {
  id: number;
  name: string;
  source_type: string;
  feed_url: string;
  site?: string | null;
  category?: string | null;
  is_enabled: boolean;
  fetch_timeout_seconds?: number | null;
  max_items_per_feed?: number | null;
  last_run_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  last_error_at?: string | null;
  created_at: string;
  updated_at: string;
}

interface NewsSourceListResponse {
  items: NewsSource[];
}

type CreateOrUpdateForm = {
  name: string;
  feed_url: string;
  site: string;
  category: string;
  is_enabled: boolean;
  fetch_timeout_seconds: string;
  max_items_per_feed: string;
};

type RunOnceResponse = {
  message?: string;
  fetched?: number;
  inserted?: number;
  skipped?: number;
  errors?: number;
};

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

export default function NewsSourcesManagePage() {
  const toast = useToast();

  const sourcesQueryKey = useMemo(() => ["admin-news-sources"] as const, []);

  const sourcesQuery = useQuery({
    queryKey: sourcesQueryKey,
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
    toast.error(getApiErrorMessage(sourcesQuery.error, "来源列表加载失败"));
  }, [sourcesQuery.error, toast]);

  const sources = sourcesQuery.data?.items ?? [];

  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<NewsSource | null>(null);
  const [activeAction, setActiveAction] = useState<
    { id: number; kind: "run" | "toggle" | "delete" } | null
  >(null);

  const emptyForm: CreateOrUpdateForm = {
    name: "",
    feed_url: "",
    site: "",
    category: "",
    is_enabled: true,
    fetch_timeout_seconds: "",
    max_items_per_feed: "",
  };

  const [form, setForm] = useState<CreateOrUpdateForm>(emptyForm);

  const openCreate = () => {
    setForm(emptyForm);
    setEditing(null);
    setCreateOpen(true);
  };

  const openEdit = (src: NewsSource) => {
    setEditing(src);
    setForm({
      name: String(src.name || ""),
      feed_url: String(src.feed_url || ""),
      site: String(src.site || ""),
      category: String(src.category || ""),
      is_enabled: Boolean(src.is_enabled),
      fetch_timeout_seconds:
        src.fetch_timeout_seconds === null ||
        src.fetch_timeout_seconds === undefined
          ? ""
          : String(src.fetch_timeout_seconds),
      max_items_per_feed:
        src.max_items_per_feed === null || src.max_items_per_feed === undefined
          ? ""
          : String(src.max_items_per_feed),
    });
    setEditOpen(true);
  };

  const closeModals = () => {
    setCreateOpen(false);
    setEditOpen(false);
    setEditing(null);
  };

  const createMutation = useAppMutation<NewsSource, CreateOrUpdateForm>({
    mutationFn: async (payload) => {
      const res = await api.post("/news/admin/sources", {
        name: payload.name.trim()
          ? payload.name.trim()
          : payload.feed_url.trim(),
        feed_url: payload.feed_url.trim(),
        site: payload.site.trim() ? payload.site.trim() : null,
        category: payload.category.trim() ? payload.category.trim() : null,
        is_enabled: Boolean(payload.is_enabled),
        fetch_timeout_seconds: payload.fetch_timeout_seconds.trim()
          ? Number(payload.fetch_timeout_seconds)
          : null,
        max_items_per_feed: payload.max_items_per_feed.trim()
          ? Number(payload.max_items_per_feed)
          : null,
      });
      return res.data as NewsSource;
    },
    successMessage: "已创建来源",
    errorMessageFallback: "创建失败",
    invalidateQueryKeys: [sourcesQueryKey as any],
    onSuccess: () => {
      setCreateOpen(false);
    },
  });

  const updateMutation = useAppMutation<
    NewsSource,
    { id: number; payload: CreateOrUpdateForm }
  >({
    mutationFn: async ({ id, payload }) => {
      const res = await api.put(`/news/admin/sources/${id}`, {
        name: payload.name.trim() ? payload.name.trim() : null,
        feed_url: payload.feed_url.trim() ? payload.feed_url.trim() : null,
        site: payload.site.trim() ? payload.site.trim() : null,
        category: payload.category.trim() ? payload.category.trim() : null,
        is_enabled: Boolean(payload.is_enabled),
        fetch_timeout_seconds: payload.fetch_timeout_seconds.trim()
          ? Number(payload.fetch_timeout_seconds)
          : null,
        max_items_per_feed: payload.max_items_per_feed.trim()
          ? Number(payload.max_items_per_feed)
          : null,
      });
      return res.data as NewsSource;
    },
    successMessage: "已更新来源",
    errorMessageFallback: "更新失败",
    invalidateQueryKeys: [sourcesQueryKey as any],
    onSuccess: () => {
      setEditOpen(false);
      setEditing(null);
    },
  });

  const deleteMutation = useAppMutation<void, number>({
    mutationFn: async (id) => {
      await api.delete(`/news/admin/sources/${id}`);
    },
    successMessage: "已删除来源",
    errorMessageFallback: "删除失败",
    invalidateQueryKeys: [sourcesQueryKey as any],
    onMutate: async (id) => {
      setActiveAction({ id, kind: "delete" });
    },
    onSettled: (_data, _err, id) => {
      setActiveAction((prev) =>
        prev && prev.id === id && prev.kind === "delete" ? null : prev
      );
    },
  });

  const toggleEnabledMutation = useAppMutation<
    NewsSource,
    { id: number; is_enabled: boolean }
  >({
    mutationFn: async ({ id, is_enabled }) => {
      const res = await api.put(`/news/admin/sources/${id}`, {
        is_enabled,
      });
      return res.data as NewsSource;
    },
    errorMessageFallback: "操作失败",
    invalidateQueryKeys: [sourcesQueryKey as any],
    onMutate: async (payload) => {
      setActiveAction({ id: payload.id, kind: "toggle" });
    },
    onSettled: (_data, _err, payload) => {
      setActiveAction((prev) =>
        prev && prev.id === payload?.id && prev.kind === "toggle" ? null : prev
      );
    },
    onSuccess: (res) => {
      toast.success(res.is_enabled ? "已启用" : "已停用");
    },
  });

  const runOnceMutation = useAppMutation<RunOnceResponse, number>({
    mutationFn: async (id) => {
      const res = await api.post(
        `/news/admin/sources/${id}/ingest/run-once`,
        {}
      );
      return res.data as RunOnceResponse;
    },
    errorMessageFallback: "触发采集失败",
    invalidateQueryKeys: [sourcesQueryKey as any],
    onMutate: async (id) => {
      setActiveAction({ id, kind: "run" });
    },
    onSettled: (_data, _err, id) => {
      setActiveAction((prev) =>
        prev && prev.id === id && prev.kind === "run" ? null : prev
      );
    },
    onSuccess: (data) => {
      const fetched = Number(data?.fetched ?? 0);
      const inserted = Number(data?.inserted ?? 0);
      const skipped = Number(data?.skipped ?? 0);
      const errors = Number(data?.errors ?? 0);
      toast.success(
        `已触发采集：fetched=${fetched} inserted=${inserted} skipped=${skipped} errors=${errors}`
      );
    },
  });

  const saving = createMutation.isPending || updateMutation.isPending;

  const handleSubmitCreate = () => {
    if (saving) return;
    if (!form.feed_url.trim()) {
      toast.error("feed_url 不能为空");
      return;
    }
    createMutation.mutate(form);
  };

  const handleSubmitEdit = () => {
    if (saving) return;
    if (!editing) return;
    if (!form.feed_url.trim()) {
      toast.error("feed_url 不能为空");
      return;
    }
    updateMutation.mutate({ id: editing.id, payload: form });
  };

  const busy =
    sourcesQuery.isFetching ||
    deleteMutation.isPending ||
    toggleEnabledMutation.isPending ||
    runOnceMutation.isPending ||
    saving;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            RSS 来源管理
          </h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">
            管理 RSS 采集来源（新增/编辑/启停/手动触发）
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            icon={RefreshCw}
            onClick={() => sourcesQuery.refetch()}
            isLoading={sourcesQuery.isFetching}
            loadingText="刷新中..."
            disabled={busy}
          >
            刷新
          </Button>
          <Button
            icon={Plus}
            onClick={() => {
              if (busy) return;
              openCreate();
            }}
            disabled={busy}
          >
            新增来源
          </Button>
        </div>
      </div>

      <Card variant="surface" padding="none">
        {sourcesQuery.isLoading && sources.length === 0 ? (
          <div className="p-6">
            <ListSkeleton count={6} />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200/70 dark:border-white/10">
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    ID
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    名称
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    Feed URL
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    站点/分类
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    状态
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    最近运行
                  </th>
                  <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr
                    key={s.id}
                    className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5"
                  >
                    <td className="py-3 px-4 text-slate-700 text-sm dark:text-white/70">
                      {s.id}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
                          <Rss className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-slate-900 text-sm font-medium truncate dark:text-white">
                            {s.name}
                          </p>
                          <p className="text-xs text-slate-500 dark:text-white/40">
                            {s.source_type}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="max-w-[520px]">
                        <p className="text-slate-700 text-sm break-all dark:text-white/70">
                          {s.feed_url}
                        </p>
                        {s.last_error ? (
                          <p className="mt-1 text-xs text-red-500/90 break-words">
                            {s.last_error_at
                              ? `${formatTime(s.last_error_at)}：`
                              : ""}
                            {s.last_error}
                          </p>
                        ) : null}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="info" size="sm">
                          {s.site || "-"}
                        </Badge>
                        <Badge variant="default" size="sm">
                          {s.category || "-"}
                        </Badge>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge
                        variant={s.is_enabled ? "success" : "danger"}
                        size="sm"
                      >
                        {s.is_enabled ? "启用" : "停用"}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-sm text-slate-600 dark:text-white/60">
                      <div className="space-y-1">
                        <p>last_run：{formatTime(s.last_run_at)}</p>
                        <p>last_ok：{formatTime(s.last_success_at)}</p>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-end gap-2">
                        {(() => {
                          const isActive = activeAction?.id === s.id;
                          const actionBusy =
                            deleteMutation.isPending ||
                            toggleEnabledMutation.isPending ||
                            runOnceMutation.isPending ||
                            saving;
                          const disableOther = actionBusy && !isActive;
                          const runLoading =
                            runOnceMutation.isPending &&
                            isActive &&
                            activeAction?.kind === "run";
                          const toggleLoading =
                            toggleEnabledMutation.isPending &&
                            isActive &&
                            activeAction?.kind === "toggle";
                          const deleteLoading =
                            deleteMutation.isPending &&
                            isActive &&
                            activeAction?.kind === "delete";

                          return (
                            <>
                        <Button
                          variant="outline"
                          size="sm"
                          icon={Play}
                          isLoading={runLoading}
                          loadingText="采集中..."
                          onClick={() => {
                            if (actionBusy) return;
                            runOnceMutation.mutate(s.id);
                          }}
                          disabled={disableOther || runLoading}
                        >
                          采集
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          icon={Power}
                          isLoading={toggleLoading}
                          loadingText="处理中..."
                          onClick={() =>
                            toggleEnabledMutation.mutate({
                              id: s.id,
                              is_enabled: !s.is_enabled,
                            })
                          }
                          disabled={disableOther || toggleLoading}
                        >
                          {s.is_enabled ? "停用" : "启用"}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          icon={Edit}
                          onClick={() => openEdit(s)}
                          disabled={actionBusy}
                        >
                          编辑
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          icon={Trash2}
                          isLoading={deleteLoading}
                          loadingText="删除中..."
                          onClick={() => {
                            if (
                              window.confirm(
                                `确认删除来源：${s.name}？（会同时删除运行记录）`
                              )
                            ) {
                              deleteMutation.mutate(s.id);
                            }
                          }}
                          disabled={disableOther || deleteLoading}
                        >
                          删除
                        </Button>
                            </>
                          );
                        })()}
                      </div>
                    </td>
                  </tr>
                ))}

                {sources.length === 0 ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="py-10 text-center text-slate-500 text-sm dark:text-white/40"
                    >
                      暂无来源
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 创建 */}
      <Modal
        isOpen={createOpen}
        onClose={() => {
          if (saving) return;
          closeModals();
        }}
        title="新增 RSS 来源"
        size="lg"
      >
        <div className="space-y-4">
          <Input
            label="名称"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="例如：司法部政策发布"
            disabled={saving}
          />
          <Input
            label="Feed URL"
            value={form.feed_url}
            onChange={(e) => setForm({ ...form, feed_url: e.target.value })}
            placeholder="https://baixinghelper.cn/rss.xml"
            disabled={saving}
          />
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="站点（可选）"
              value={form.site}
              onChange={(e) => setForm({ ...form, site: e.target.value })}
              placeholder="例如：gov.cn"
              disabled={saving}
            />
            <Input
              label="分类（可选）"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              placeholder="例如：法律动态"
              disabled={saving}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="超时秒数（可选）"
              value={form.fetch_timeout_seconds}
              onChange={(e) =>
                setForm({ ...form, fetch_timeout_seconds: e.target.value })
              }
              placeholder="例如：10"
              disabled={saving}
            />
            <Input
              label="每次最大条数（可选）"
              value={form.max_items_per_feed}
              onChange={(e) =>
                setForm({ ...form, max_items_per_feed: e.target.value })
              }
              placeholder="例如：50"
              disabled={saving}
            />
          </div>

          <div className="flex items-center justify-between rounded-xl border border-slate-200/70 bg-slate-50 px-4 py-3 dark:border-white/10 dark:bg-white/5">
            <div>
              <p className="text-slate-900 font-medium dark:text-white">启用</p>
              <p className="text-slate-600 text-sm dark:text-white/40">
                关闭后不会参与周期采集
              </p>
            </div>
            <button
              onClick={() => {
                if (saving) return;
                setForm({ ...form, is_enabled: !form.is_enabled });
              }}
              disabled={saving}
              className={`w-12 h-6 rounded-full transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${
                form.is_enabled
                  ? "bg-amber-500"
                  : "bg-slate-200 dark:bg-white/20"
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full bg-white transition-transform ${
                  form.is_enabled ? "translate-x-6" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>

          <ModalActions>
            <Button
              variant="ghost"
              onClick={() => {
                if (saving) return;
                closeModals();
              }}
              disabled={saving}
            >
              取消
            </Button>
            <Button
              onClick={handleSubmitCreate}
              isLoading={createMutation.isPending}
              loadingText="创建中..."
              disabled={saving}
            >
              创建
            </Button>
          </ModalActions>
        </div>
      </Modal>

      {/* 编辑 */}
      <Modal
        isOpen={editOpen}
        onClose={() => {
          if (saving) return;
          closeModals();
        }}
        title={`编辑来源${editing ? `：${editing.name}` : ""}`}
        size="lg"
      >
        <div className="space-y-4">
          <Input
            label="名称"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            disabled={saving}
          />
          <Input
            label="Feed URL"
            value={form.feed_url}
            onChange={(e) => setForm({ ...form, feed_url: e.target.value })}
            disabled={saving}
          />
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="站点（可选）"
              value={form.site}
              onChange={(e) => setForm({ ...form, site: e.target.value })}
              disabled={saving}
            />
            <Input
              label="分类（可选）"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              disabled={saving}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="超时秒数（可选）"
              value={form.fetch_timeout_seconds}
              onChange={(e) =>
                setForm({ ...form, fetch_timeout_seconds: e.target.value })
              }
              disabled={saving}
            />
            <Input
              label="每次最大条数（可选）"
              value={form.max_items_per_feed}
              onChange={(e) =>
                setForm({ ...form, max_items_per_feed: e.target.value })
              }
              disabled={saving}
            />
          </div>

          <div className="flex items-center justify-between rounded-xl border border-slate-200/70 bg-slate-50 px-4 py-3 dark:border-white/10 dark:bg-white/5">
            <div>
              <p className="text-slate-900 font-medium dark:text-white">启用</p>
              <p className="text-slate-600 text-sm dark:text-white/40">
                关闭后不会参与周期采集
              </p>
            </div>
            <button
              onClick={() => {
                if (saving) return;
                setForm({ ...form, is_enabled: !form.is_enabled })
              }}
              disabled={saving}
              className={`w-12 h-6 rounded-full transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${
                form.is_enabled
                  ? "bg-amber-500"
                  : "bg-slate-200 dark:bg-white/20"
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full bg-white transition-transform ${
                  form.is_enabled ? "translate-x-6" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>

          {editing?.last_error ? (
            <Card variant="surface" padding="md">
              <div className="text-sm">
                <p className="text-slate-900 font-medium dark:text-white">
                  最近错误
                </p>
                <p className="text-xs text-slate-600 dark:text-white/40">
                  {formatTime(editing.last_error_at)}
                </p>
                <p className="mt-2 text-sm text-red-500/90 break-words">
                  {editing.last_error}
                </p>
              </div>
            </Card>
          ) : null}

          <ModalActions>
            <Button
              variant="ghost"
              onClick={() => {
                if (saving) return;
                closeModals();
              }}
              disabled={saving}
            >
              取消
            </Button>
            <Button
              onClick={handleSubmitEdit}
              isLoading={updateMutation.isPending}
              loadingText="保存中..."
              disabled={saving}
            >
              保存
            </Button>
          </ModalActions>
        </div>
      </Modal>
    </div>
  );
}
