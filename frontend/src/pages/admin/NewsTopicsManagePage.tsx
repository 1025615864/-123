import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Trash2, Edit, Layers, ArrowLeft, ArrowDown, ArrowUp, Search, GripVertical } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  Button,
  Input,
  Modal,
  Loading,
  EmptyState,
  Badge,
  Pagination,
} from "../../components/ui";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import { queryKeys } from "../../queryKeys";

interface NewsTopic {
  id: number;
  title: string;
  description: string | null;
  cover_image: string | null;
  is_active: boolean;
  sort_order: number;
  auto_category?: string | null;
  auto_keyword?: string | null;
  auto_limit?: number;
  created_at: string;
  updated_at: string;
}

interface TopicListResponse {
  items: NewsTopic[];
}

interface TopicItemBrief {
  id: number;
  news_id: number;
  position: number;
  title: string;
  category: string;
}

interface TopicAdminDetailResponse {
  topic: NewsTopic;
  items: TopicItemBrief[];
}

interface TopicReportItem {
  id: number;
  title: string;
  is_active: boolean;
  sort_order: number;
  manual_item_count: number;
  manual_view_count: number;
  manual_favorite_count: number;
  manual_conversion_rate: number;
}

interface TopicReportResponse {
  items: TopicReportItem[];
}

interface NewsAdminListItem {
  id: number;
  title: string;
  category: string;
  is_published: boolean;
  is_top: boolean;
  published_at?: string | null;
  created_at: string;
}

interface NewsAdminListResponse {
  items: NewsAdminListItem[];
  total: number;
  page: number;
  page_size: number;
}

export default function NewsTopicsManagePage() {
  const toast = useToast();

  const [manageTopicId, setManageTopicId] = useState<number | null>(null);
  const [manageOpen, setManageOpen] = useState(false);
  const [newsIdToAdd, setNewsIdToAdd] = useState("");
  const [newsSearchKeyword, setNewsSearchKeyword] = useState("");
  const [newsSearchPage, setNewsSearchPage] = useState(1);
  const newsSearchPageSize = 10;
  const [selectedNewsIds, setSelectedNewsIds] = useState<Set<number>>(new Set());
  const [selectedItemIds, setSelectedItemIds] = useState<Set<number>>(new Set());
  const [importCategory, setImportCategory] = useState("");
  const [importLimit, setImportLimit] = useState(50);
  const [manualOrderItemIds, setManualOrderItemIds] = useState<number[]>([]);
  const [draggingItemId, setDraggingItemId] = useState<number | null>(null);

  const reportQuery = useQuery({
    queryKey: ["admin-news-topics-report"] as const,
    queryFn: async () => {
      const res = await api.get("/news/admin/topics/report");
      return res.data as TopicReportResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const reorderMutation = useAppMutation<{ updated: number }, { topicId: number; itemIds: number[] }>({
    mutationFn: async ({ topicId, itemIds }) => {
      const res = await api.post(`/news/admin/topics/${topicId}/items/reorder`, {
        item_ids: itemIds,
      });
      return res.data as { updated: number };
    },
    errorMessageFallback: "拖拽排序失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopicDetail(manageTopicId)],
    onSuccess: () => {
      toast.success("已更新顺序");
    },
    onError: () => {
      setManualOrderItemIds([]);
    },
  });

  const autoCacheRefreshMutation = useAppMutation<{ cached: number }, { topicId: number }>({
    mutationFn: async ({ topicId }) => {
      const res = await api.post(`/news/admin/topics/${topicId}/auto-cache/refresh`, {});
      return res.data as { cached: number };
    },
    errorMessageFallback: "刷新缓存失败",
    onSuccess: (data) => {
      toast.success(`已刷新自动收录缓存：${data.cached} 条`);
    },
  });

  const reportById = useMemo(() => {
    const map = new Map<number, TopicReportItem>();
    for (const it of reportQuery.data?.items ?? []) {
      map.set(Number(it.id), it);
    }
    return map;
  }, [reportQuery.data]);

  const topicsQuery = useQuery({
    queryKey: queryKeys.adminNewsTopics(),
    queryFn: async () => {
      const res = await api.get("/news/admin/topics");
      return res.data as TopicListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const bulkRemoveMutation = useAppMutation<
    { requested: number; deleted: number; skipped: number },
    { topicId: number; itemIds: number[] }
  >({
    mutationFn: async ({ topicId, itemIds }) => {
      const res = await api.post(`/news/admin/topics/${topicId}/items/bulk-delete`, {
        item_ids: itemIds,
      });
      return res.data as { requested: number; deleted: number; skipped: number };
    },
    errorMessageFallback: "批量移除失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopicDetail(manageTopicId)],
    onSuccess: (data) => {
      setSelectedItemIds(new Set());
      toast.success(`已移除 ${data.deleted} 条，跳过 ${data.skipped} 条`);
    },
  });

  const reindexMutation = useAppMutation<{ updated: number }, { topicId: number }>({
    mutationFn: async ({ topicId }) => {
      const res = await api.post(`/news/admin/topics/${topicId}/items/reindex`, {});
      return res.data as { updated: number };
    },
    errorMessageFallback: "重排失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopicDetail(manageTopicId)],
    onSuccess: (data) => {
      toast.success(`已重排 ${data.updated} 条`);
    },
  });

  const importMutation = useAppMutation<
    { requested: number; added: number; skipped: number },
    { topicId: number; category: string; keyword: string; limit: number }
  >({
    mutationFn: async ({ topicId, category, keyword, limit }) => {
      const res = await api.post(`/news/admin/topics/${topicId}/import`, {
        category: category.trim() ? category.trim() : null,
        keyword: keyword.trim() ? keyword.trim() : null,
        limit: Number(limit || 50),
        include_unpublished: false,
      });
      return res.data as { requested: number; added: number; skipped: number };
    },
    errorMessageFallback: "导入失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopicDetail(manageTopicId)],
    onSuccess: (data) => {
      toast.success(`导入请求 ${data.requested} 条，新增 ${data.added} 条，跳过 ${data.skipped} 条`);
    },
  });

  useEffect(() => {
    if (!topicsQuery.error) return;
    toast.error(getApiErrorMessage(topicsQuery.error));
  }, [topicsQuery.error, toast]);

  const topics = topicsQuery.data?.items ?? [];

  const [showCreate, setShowCreate] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editing, setEditing] = useState<NewsTopic | null>(null);

  const [form, setForm] = useState({
    title: "",
    description: "",
    cover_image: "",
    is_active: true,
    sort_order: 0,
    auto_category: "",
    auto_keyword: "",
    auto_limit: 0,
  });

  const resetForm = () => {
    setForm({
      title: "",
      description: "",
      cover_image: "",
      is_active: true,
      sort_order: 0,
      auto_category: "",
      auto_keyword: "",
      auto_limit: 0,
    });
  };

  const openEdit = (t: NewsTopic) => {
    setEditing(t);
    setForm({
      title: t.title,
      description: t.description ?? "",
      cover_image: t.cover_image ?? "",
      is_active: !!t.is_active,
      sort_order: Number(t.sort_order || 0),
      auto_category: String(t.auto_category ?? ""),
      auto_keyword: String(t.auto_keyword ?? ""),
      auto_limit: Number(t.auto_limit || 0),
    });
    setShowEdit(true);
  };

  const createMutation = useAppMutation<NewsTopic, typeof form>({
    mutationFn: async (payload) => {
      const res = await api.post("/news/admin/topics", {
        title: payload.title.trim(),
        description: payload.description.trim() ? payload.description.trim() : null,
        cover_image: payload.cover_image.trim() ? payload.cover_image.trim() : null,
        is_active: !!payload.is_active,
        sort_order: Number(payload.sort_order || 0),
        auto_category: payload.auto_category.trim() ? payload.auto_category.trim() : null,
        auto_keyword: payload.auto_keyword.trim() ? payload.auto_keyword.trim() : null,
        auto_limit: Number(payload.auto_limit || 0),
      });
      return res.data as NewsTopic;
    },
    successMessage: "创建成功",
    errorMessageFallback: "创建失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopics()],
    onSuccess: () => {
      setShowCreate(false);
      resetForm();
    },
  });

  const updateMutation = useAppMutation<NewsTopic, { id: number; payload: typeof form }>({
    mutationFn: async ({ id, payload }) => {
      const res = await api.put(`/news/admin/topics/${id}`, {
        title: payload.title.trim() ? payload.title.trim() : undefined,
        description: payload.description.trim() ? payload.description.trim() : null,
        cover_image: payload.cover_image.trim() ? payload.cover_image.trim() : null,
        is_active: payload.is_active,
        sort_order: Number(payload.sort_order || 0),
        auto_category: payload.auto_category.trim() ? payload.auto_category.trim() : null,
        auto_keyword: payload.auto_keyword.trim() ? payload.auto_keyword.trim() : null,
        auto_limit: Number(payload.auto_limit || 0),
      });
      return res.data as NewsTopic;
    },
    successMessage: "保存成功",
    errorMessageFallback: "保存失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopics()],
    onSuccess: () => {
      setShowEdit(false);
      setEditing(null);
      resetForm();
    },
  });

  const deleteMutation = useAppMutation<void, number>({
    mutationFn: async (id) => {
      await api.delete(`/news/admin/topics/${id}`);
    },
    successMessage: "删除成功",
    errorMessageFallback: "删除失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopics()],
  });

  useEffect(() => {
    setNewsSearchPage(1);
    setSelectedNewsIds(new Set());
    setSelectedItemIds(new Set());
    setManualOrderItemIds([]);
    setDraggingItemId(null);
  }, [newsSearchKeyword, manageTopicId, manageOpen]);

  const topicDetailQuery = useQuery({
    queryKey: queryKeys.adminNewsTopicDetail(manageTopicId),
    queryFn: async () => {
      const res = await api.get(`/news/admin/topics/${manageTopicId}`);
      return res.data as TopicAdminDetailResponse;
    },
    enabled: manageOpen && !!manageTopicId,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!topicDetailQuery.error) return;
    toast.error(getApiErrorMessage(topicDetailQuery.error));
  }, [topicDetailQuery.error, toast]);

  const items = topicDetailQuery.data?.items ?? [];

  const itemsById = useMemo(() => {
    const map = new Map<number, TopicItemBrief>();
    for (const it of items) {
      map.set(Number(it.id), it);
    }
    return map;
  }, [items]);

  const defaultOrderedItemIds = useMemo(() => {
    return items
      .slice()
      .sort((a, b) => a.position - b.position)
      .map((it) => Number(it.id));
  }, [items]);

  const orderedItems = useMemo(() => {
    const order = manualOrderItemIds.length > 0 ? manualOrderItemIds : defaultOrderedItemIds;
    const result: TopicItemBrief[] = [];
    const seen = new Set<number>();

    for (const id of order) {
      const it = itemsById.get(Number(id));
      if (!it) continue;
      result.push(it);
      seen.add(Number(id));
    }

    for (const it of items) {
      if (seen.has(Number(it.id))) continue;
      result.push(it);
    }

    return result;
  }, [defaultOrderedItemIds, items, itemsById, manualOrderItemIds]);

  const handleDragStart = (itemId: number) => {
    setDraggingItemId(Number(itemId));
    const cur = manualOrderItemIds;
    const changed =
      cur.length === 0 ||
      cur.length !== items.length ||
      cur.some((id) => !itemsById.has(Number(id))) ||
      defaultOrderedItemIds.some((id) => !cur.includes(Number(id)));
    if (changed) {
      setManualOrderItemIds(defaultOrderedItemIds);
    }
  };

  const handleDropOn = (targetItemId: number) => {
    const tId = manageTopicId;
    const dragging = draggingItemId;
    if (!tId) return;
    if (!dragging) return;
    if (Number(dragging) === Number(targetItemId)) return;

    const base = (manualOrderItemIds.length > 0 ? manualOrderItemIds : defaultOrderedItemIds).slice();
    const fromIdx = base.findIndex((x) => Number(x) === Number(dragging));
    const toIdx = base.findIndex((x) => Number(x) === Number(targetItemId));
    if (fromIdx < 0 || toIdx < 0) return;

    base.splice(fromIdx, 1);
    base.splice(toIdx, 0, Number(dragging));

    setManualOrderItemIds(base);
    setDraggingItemId(null);
    if (reorderMutation.isPending) return;
    reorderMutation.mutate({ topicId: tId, itemIds: base });
  };

  const toggleItemSelected = (id: number) => {
    setSelectedItemIds((prev) => {
      const next = new Set(prev);
      const key = Number(id);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const selectAllItems = () => {
    setSelectedItemIds(new Set(items.map((it) => Number(it.id))));
  };

  const trimmedNewsSearchKeyword = newsSearchKeyword.trim();

  const newsSearchQueryKey = useMemo(
    () =>
      [
        "admin-news-search",
        { keyword: trimmedNewsSearchKeyword, page: newsSearchPage, pageSize: newsSearchPageSize },
      ] as const,
    [trimmedNewsSearchKeyword, newsSearchPage, newsSearchPageSize]
  );

  const newsSearchQuery = useQuery({
    queryKey: newsSearchQueryKey,
    queryFn: async () => {
      const params: Record<string, unknown> = {
        page: newsSearchPage,
        page_size: newsSearchPageSize,
      };
      if (trimmedNewsSearchKeyword) params.keyword = trimmedNewsSearchKeyword;
      const res = await api.get("/news/admin/all", { params });
      return res.data as NewsAdminListResponse;
    },
    enabled: manageOpen,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!newsSearchQuery.error) return;
    toast.error(getApiErrorMessage(newsSearchQuery.error));
  }, [newsSearchQuery.error, toast]);

  const searchResults = newsSearchQuery.data?.items ?? [];
  const searchTotal = newsSearchQuery.data?.total ?? 0;
  const searchTotalPages = Math.max(1, Math.ceil(searchTotal / newsSearchPageSize));

  const bulkAddMutation = useAppMutation<
    { requested: number; added: number; skipped: number },
    { topicId: number; newsIds: number[] }
  >({
    mutationFn: async ({ topicId, newsIds }) => {
      const res = await api.post(`/news/admin/topics/${topicId}/items/bulk`, {
        news_ids: newsIds,
      });
      return res.data as { requested: number; added: number; skipped: number };
    },
    errorMessageFallback: "批量添加失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopicDetail(manageTopicId)],
    onSuccess: (data) => {
      setSelectedNewsIds(new Set());
      toast.success(`已添加 ${data.added} 条，跳过 ${data.skipped} 条`);
    },
  });

  const toggleSelected = (id: number) => {
    setSelectedNewsIds((prev) => {
      const next = new Set(prev);
      const key = Number(id);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const selectAllVisible = () => {
    setSelectedNewsIds((prev) => {
      const next = new Set(prev);
      for (const n of searchResults) {
        const id = Number(n.id);
        const already = items.some((it) => Number(it.news_id) === id);
        if (already) continue;
        next.add(id);
      }
      return next;
    });
  };

  const clearSelected = () => {
    setSelectedNewsIds(new Set());
  };

  const addItemMutation = useAppMutation<{ id: number; message: string }, { topicId: number; newsId: number }>({
    mutationFn: async ({ topicId, newsId }) => {
      const res = await api.post(`/news/admin/topics/${topicId}/items`, { news_id: newsId });
      return res.data as { id: number; message: string };
    },
    successMessage: "已添加",
    errorMessageFallback: "添加失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopicDetail(manageTopicId)],
    onSuccess: () => {
      setNewsIdToAdd("");
    },
  });

  const removeItemMutation = useAppMutation<void, { topicId: number; itemId: number }>({
    mutationFn: async ({ topicId, itemId }) => {
      await api.delete(`/news/admin/topics/${topicId}/items/${itemId}`);
    },
    successMessage: "已移除",
    errorMessageFallback: "移除失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopicDetail(manageTopicId)],
  });

  const updatePosMutation = useAppMutation<void, { topicId: number; itemId: number; position: number }>({
    mutationFn: async ({ topicId, itemId, position }) => {
      await api.put(`/news/admin/topics/${topicId}/items/${itemId}`, { position });
    },
    errorMessageFallback: "更新失败",
    invalidateQueryKeys: [queryKeys.adminNewsTopicDetail(manageTopicId)],
  });

  const move = (dir: -1 | 1, idx: number) => {
    const tId = manageTopicId;
    if (!tId) return;
    const cur = items[idx];
    const other = items[idx + dir];
    if (!cur || !other) return;
    if (updatePosMutation.isPending) return;

    // 交换 position
    updatePosMutation.mutate({ topicId: tId, itemId: cur.id, position: other.position });
    updatePosMutation.mutate({ topicId: tId, itemId: other.id, position: cur.position });
  };

  return (
    <div className="space-y-8">
      <Card variant="surface" padding="md">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">
              新闻专题管理
            </h1>
            <p className="mt-1 text-sm text-slate-600 dark:text-white/50">
              创建专题并配置专题内新闻
            </p>
          </div>
          <Button
            onClick={() => {
              resetForm();
              setShowCreate(true);
            }}
          >
            <Plus className="h-4 w-4" />
            新建专题
          </Button>
        </div>
      </Card>

      {topicsQuery.isLoading ? (
        <Loading />
      ) : topics.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="暂无专题"
          description="点击右上角创建一个专题合集"
        />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {topics.map((t) => (
            <Card
              key={t.id}
              variant="surface"
              padding="md"
              hover
              data-testid={`admin-topic-${t.id}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-semibold text-slate-900 dark:text-white line-clamp-1">
                      {t.title}
                    </h3>
                    {t.is_active ? (
                      <Badge variant="primary" size="sm">
                        启用
                      </Badge>
                    ) : (
                      <Badge variant="default" size="sm">
                        停用
                      </Badge>
                    )}
                  </div>
                  <p className="mt-2 text-sm text-slate-600 dark:text-white/50 line-clamp-2">
                    {t.description || "暂无简介"}
                  </p>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => openEdit(t)}
                >
                  <Edit className="h-4 w-4" />
                  编辑
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setManageTopicId(t.id);
                    setManageOpen(true);
                  }}
                  data-testid={`admin-topic-config-${t.id}`}
                >
                  <Layers className="h-4 w-4" />
                  配置新闻
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (!confirm("确定删除该专题吗？")) return;
                    deleteMutation.mutate(t.id);
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                  删除
                </Button>
                <Link
                  to={`/news/topics/${t.id}`}
                  className="inline-flex items-center gap-2 text-sm text-amber-700 hover:underline dark:text-amber-400"
                >
                  预览
                  <ArrowLeft className="h-4 w-4 rotate-180" />
                </Link>
              </div>

              {reportById.get(Number(t.id)) ? (
                <div className="mt-4 text-xs text-slate-500 dark:text-white/45">
                  条目 {reportById.get(Number(t.id))?.manual_item_count ?? 0} · 浏览 {reportById.get(Number(t.id))?.manual_view_count ?? 0} · 收藏 {reportById.get(Number(t.id))?.manual_favorite_count ?? 0} · 转化 {(((reportById.get(Number(t.id))?.manual_conversion_rate ?? 0) as number) * 100).toFixed(1)}%
                </div>
              ) : null}
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        title="新建专题"
        size="lg"
      >
        <div className="space-y-4">
          <Input
            label="标题"
            value={form.title}
            onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
            placeholder="专题标题"
          />
          <Input
            label="简介"
            value={form.description}
            onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
            placeholder="专题简介（可选）"
          />
          <Input
            label="封面图"
            value={form.cover_image}
            onChange={(e) => setForm((p) => ({ ...p, cover_image: e.target.value }))}
            placeholder="封面图 URL（可选）"
          />
          <Input
            label="排序"
            value={String(form.sort_order)}
            onChange={(e) =>
              setForm((p) => ({ ...p, sort_order: Number(e.target.value || 0) }))
            }
            placeholder="数字越大越靠前"
          />
          <Input
            label="自动收录分类"
            value={form.auto_category}
            onChange={(e) => setForm((p) => ({ ...p, auto_category: e.target.value }))}
            placeholder="例如：法律动态（可选）"
          />
          <Input
            label="自动收录关键词"
            value={form.auto_keyword}
            onChange={(e) => setForm((p) => ({ ...p, auto_keyword: e.target.value }))}
            placeholder="例如：劳动（可选）"
          />
          <Input
            label="自动收录数量"
            value={String(form.auto_limit)}
            onChange={(e) => setForm((p) => ({ ...p, auto_limit: Number(e.target.value || 0) }))}
            placeholder="0 表示关闭自动收录"
          />
          <div className="flex items-center gap-3">
            <Button
              variant={form.is_active ? "primary" : "outline"}
              onClick={() => setForm((p) => ({ ...p, is_active: true }))}
              size="sm"
            >
              启用
            </Button>
            <Button
              variant={!form.is_active ? "primary" : "outline"}
              onClick={() => setForm((p) => ({ ...p, is_active: false }))}
              size="sm"
            >
              停用
            </Button>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              取消
            </Button>
            <Button
              onClick={() => {
                if (!form.title.trim()) return;
                if (createMutation.isPending) return;
                createMutation.mutate(form);
              }}
            >
              创建
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showEdit}
        onClose={() => {
          setShowEdit(false);
          setEditing(null);
        }}
        title="编辑专题"
        size="lg"
      >
        <div className="space-y-4">
          <Input
            label="标题"
            value={form.title}
            onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
            placeholder="专题标题"
          />
          <Input
            label="简介"
            value={form.description}
            onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
            placeholder="专题简介（可选）"
          />
          <Input
            label="封面图"
            value={form.cover_image}
            onChange={(e) => setForm((p) => ({ ...p, cover_image: e.target.value }))}
            placeholder="封面图 URL（可选）"
          />
          <Input
            label="排序"
            value={String(form.sort_order)}
            onChange={(e) =>
              setForm((p) => ({ ...p, sort_order: Number(e.target.value || 0) }))
            }
            placeholder="数字越大越靠前"
          />
          <div className="flex items-center gap-3">
            <Button
              variant={form.is_active ? "primary" : "outline"}
              onClick={() => setForm((p) => ({ ...p, is_active: true }))}
              size="sm"
            >
              启用
            </Button>
            <Button
              variant={!form.is_active ? "primary" : "outline"}
              onClick={() => setForm((p) => ({ ...p, is_active: false }))}
              size="sm"
            >
              停用
            </Button>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="outline"
              onClick={() => {
                setShowEdit(false);
                setEditing(null);
              }}
            >
              取消
            </Button>
            <Button
              onClick={() => {
                if (!editing) return;
                if (!form.title.trim()) return;
                if (updateMutation.isPending) return;
                updateMutation.mutate({ id: editing.id, payload: form });
              }}
            >
              保存
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={manageOpen}
        onClose={() => {
          setManageOpen(false);
          setManageTopicId(null);
          setNewsIdToAdd("");
          setNewsSearchKeyword("");
          setNewsSearchPage(1);
          setSelectedNewsIds(new Set());
          setSelectedItemIds(new Set());
          setImportCategory("");
          setImportLimit(50);
        }}
        title="配置专题新闻"
        size="xl"
      >
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Input
              label="添加新闻ID"
              value={newsIdToAdd}
              onChange={(e) => setNewsIdToAdd(e.target.value)}
              placeholder="例如 123"
            />
            <Button
              onClick={() => {
                const tId = manageTopicId;
                const nId = Number(newsIdToAdd);
                if (!tId || !Number.isFinite(nId) || nId <= 0) return;
                if (addItemMutation.isPending) return;
                addItemMutation.mutate({ topicId: tId, newsId: nId });
              }}
            >
              添加
            </Button>
          </div>

          <div className="flex items-center gap-3">
            <Input
              label="搜索新闻"
              value={newsSearchKeyword}
              onChange={(e) => setNewsSearchKeyword(e.target.value)}
              placeholder="输入关键词搜索标题/摘要"
              icon={Search}
            />
          </div>

          <div className="grid md:grid-cols-3 gap-3">
            <Input
              label="导入分类"
              value={importCategory}
              onChange={(e) => setImportCategory(e.target.value)}
              placeholder="可选：法律动态"
            />
            <Input
              label="导入数量"
              value={String(importLimit)}
              onChange={(e) => setImportLimit(Number(e.target.value || 0))}
              placeholder="默认 50"
            />
            <div className="flex items-end">
              <Button
                variant="outline"
                data-testid="admin-topic-import"
                disabled={!manageTopicId || importMutation.isPending}
                onClick={() => {
                  const tId = manageTopicId;
                  if (!tId) return;
                  if (importMutation.isPending) return;
                  importMutation.mutate({
                    topicId: tId,
                    category: importCategory,
                    keyword: newsSearchKeyword,
                    limit: importLimit,
                  });
                }}
              >
                一键导入
              </Button>
            </div>
          </div>

          <Card variant="surface" padding="sm">
            <div className="flex items-center justify-between gap-4">
              <div className="text-sm font-semibold text-slate-900 dark:text-white">
                搜索结果
              </div>
              <div className="flex items-center gap-2">
                <div className="text-xs text-slate-500 dark:text-white/45">
                  {newsSearchQuery.isLoading ? "加载中..." : `共 ${searchTotal} 条`}
                </div>
                {selectedNewsIds.size > 0 ? (
                  <div className="text-xs text-slate-600 dark:text-white/55">
                    已选 {selectedNewsIds.size}
                  </div>
                ) : null}
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="admin-news-search-select-all"
                  disabled={searchResults.length === 0 || newsSearchQuery.isLoading}
                  onClick={() => selectAllVisible()}
                >
                  全选
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="admin-news-search-clear"
                  disabled={selectedNewsIds.size === 0}
                  onClick={() => clearSelected()}
                >
                  清空
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="admin-news-search-bulk-add"
                  disabled={!manageTopicId || selectedNewsIds.size === 0 || bulkAddMutation.isPending}
                  onClick={() => {
                    const tId = manageTopicId;
                    if (!tId) return;
                    if (bulkAddMutation.isPending) return;
                    const ids = Array.from(selectedNewsIds).map((x) => Number(x));
                    if (ids.length === 0) return;
                    bulkAddMutation.mutate({ topicId: tId, newsIds: ids });
                  }}
                >
                  批量添加
                </Button>
              </div>
            </div>

            <div className="mt-3 space-y-2">
              {newsSearchQuery.isLoading ? (
                <div className="text-sm text-slate-600 dark:text-white/50">加载中...</div>
              ) : searchResults.length === 0 ? (
                <div className="text-sm text-slate-600 dark:text-white/50">暂无结果</div>
              ) : (
                searchResults.map((n) => {
                  const tId = manageTopicId;
                  const already = items.some((it) => Number(it.news_id) === Number(n.id));
                  const selected = selectedNewsIds.has(Number(n.id));
                  return (
                    <div
                      key={n.id}
                      data-testid={`admin-news-search-${n.id}`}
                      className="flex items-center justify-between gap-3 rounded-xl border border-slate-200/70 p-3 dark:border-white/10"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <input
                          type="checkbox"
                          className="h-4 w-4"
                          checked={selected}
                          disabled={!tId || already}
                          data-testid={`admin-news-search-select-${n.id}`}
                          onChange={() => toggleSelected(Number(n.id))}
                        />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <Badge variant="primary" size="sm">
                              {n.category}
                            </Badge>
                            {n.is_published ? null : (
                              <Badge variant="warning" size="sm">
                                未发布
                              </Badge>
                            )}
                          </div>
                          <div className="mt-1 text-sm font-medium text-slate-900 dark:text-white line-clamp-1">
                            {n.title}
                          </div>
                          <div className="mt-1 text-xs text-slate-500 dark:text-white/45">
                            #{n.id}
                          </div>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!tId || already || addItemMutation.isPending}
                        data-testid={`admin-news-search-add-${n.id}`}
                        onClick={() => {
                          if (!tId) return;
                          addItemMutation.mutate({ topicId: tId, newsId: Number(n.id) });
                        }}
                      >
                        {already ? "已添加" : "添加"}
                      </Button>
                    </div>
                  );
                })
              )}
            </div>

            {searchTotalPages > 1 ? (
              <div className="mt-3">
                <Pagination
                  currentPage={newsSearchPage}
                  totalPages={searchTotalPages}
                  onPageChange={(p) => setNewsSearchPage(p)}
                />
              </div>
            ) : null}
          </Card>

          {topicDetailQuery.isLoading ? (
            <Loading />
          ) : items.length === 0 ? (
            <EmptyState
              icon={Layers}
              title="暂无条目"
              description="先添加一些新闻到专题中"
            />
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  当前条目
                </div>
                <div className="flex items-center gap-2">
                  {selectedItemIds.size > 0 ? (
                    <div className="text-xs text-slate-600 dark:text-white/55">已选 {selectedItemIds.size}</div>
                  ) : null}
                  <Button variant="outline" size="sm" onClick={() => selectAllItems()} disabled={items.length === 0}>
                    全选
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!manageTopicId || autoCacheRefreshMutation.isPending}
                    data-testid="admin-topic-auto-cache-refresh"
                    onClick={() => {
                      const tId = manageTopicId;
                      if (!tId) return;
                      autoCacheRefreshMutation.mutate({ topicId: tId });
                    }}
                  >
                    刷新自动缓存
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!manageTopicId || reindexMutation.isPending}
                    onClick={() => {
                      const tId = manageTopicId;
                      if (!tId) return;
                      reindexMutation.mutate({ topicId: tId });
                    }}
                  >
                    一键重排
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!manageTopicId || selectedItemIds.size === 0 || bulkRemoveMutation.isPending}
                    data-testid="admin-topic-items-bulk-remove"
                    onClick={() => {
                      const tId = manageTopicId;
                      if (!tId) return;
                      if (!confirm(`确定批量移除 ${selectedItemIds.size} 个条目吗？`)) return;
                      bulkRemoveMutation.mutate({
                        topicId: tId,
                        itemIds: Array.from(selectedItemIds).map((x) => Number(x)),
                      });
                    }}
                  >
                    批量移除
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
              {orderedItems.map((it, idx) => (
                  <Card key={it.id} variant="surface" padding="sm">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <button
                          type="button"
                          className="cursor-grab text-slate-400 hover:text-slate-700 dark:hover:text-white"
                          draggable
                          data-testid={`admin-topic-item-drag-${it.id}`}
                          onDragStart={() => handleDragStart(Number(it.id))}
                          onDragEnd={() => setDraggingItemId(null)}
                          onDragOver={(e) => {
                            e.preventDefault();
                          }}
                          onDrop={() => handleDropOn(Number(it.id))}
                          title="拖拽排序"
                        >
                          <GripVertical className="h-4 w-4" />
                        </button>

                        <input
                          type="checkbox"
                          className="h-4 w-4"
                          checked={selectedItemIds.has(Number(it.id))}
                          onChange={() => toggleItemSelected(Number(it.id))}
                        />

                        <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <Badge variant="primary" size="sm">
                            {it.category}
                          </Badge>
                          <span className="text-xs text-slate-500 dark:text-white/45">
                            #{it.news_id} / pos {it.position}
                          </span>
                        </div>
                        <div className="mt-1 text-sm font-medium text-slate-900 dark:text-white line-clamp-1">
                          {it.title}
                        </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => move(-1, idx)}
                          disabled={idx === 0 || updatePosMutation.isPending}
                        >
                          <ArrowUp className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => move(1, idx)}
                          disabled={idx === items.length - 1 || updatePosMutation.isPending}
                        >
                          <ArrowDown className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            const tId = manageTopicId;
                            if (!tId) return;
                            if (!confirm("确定移除该条目吗？")) return;
                            removeItemMutation.mutate({ topicId: tId, itemId: it.id });
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          <div className="pt-2 flex justify-end">
            <Button
              variant="outline"
              data-testid="admin-topic-items-close"
              onClick={() => {
                setManageOpen(false);
                setManageTopicId(null);
                setNewsIdToAdd("");
                setNewsSearchKeyword("");
                setNewsSearchPage(1);
                setSelectedNewsIds(new Set());
              }}
            >
              关闭
            </Button>
          </div>
        </div>
      </Modal>

      <div className="text-xs text-slate-500 dark:text-white/40">
        提示：前台专题入口为 <Link to="/news/topics" className="underline">/news/topics</Link>
      </div>
    </div>
  );
}
