import { useEffect, useMemo, useState } from "react";
import {
  Search,
  Plus,
  Edit,
  Trash2,
  Eye,
  EyeOff,
  Pin,
  Check,
  XCircle,
  Clock,
  RotateCcw,
} from "lucide-react";
import {
  Card,
  Input,
  Button,
  Badge,
  Modal,
  Loading,
  Pagination,
  ModalActions,
  Textarea,
} from "../../components/ui";
import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { useTheme } from "../../contexts/ThemeContext";
import { getApiErrorMessage } from "../../utils";
import RichTextEditor from "../../components/RichTextEditor";

function extractMarkdownImageUrls(content: string): string[] {
  if (!content) return [];
  const urls: string[] = [];
  const re = /!\[[^\]]*\]\(([^)]+)\)/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(content)) !== null) {
    const url = match?.[1];
    if (typeof url === "string" && url.trim()) urls.push(url.trim());
  }
  return Array.from(new Set(urls));
}

interface NewsItem {
  id: number;
  title: string;
  category: string;
  summary?: string | null;
  cover_image?: string | null;
  source?: string | null;
  source_url?: string | null;
  source_site?: string | null;
  author?: string | null;
  ai_risk_level?: string | null;
  ai_annotation?: NewsAIAnnotation | null;
  is_top: boolean;
  is_published: boolean;
  review_status?: string | null;
  review_reason?: string | null;
  reviewed_at?: string | null;
  view_count: number;
  published_at?: string | null;
  scheduled_publish_at?: string | null;
  scheduled_unpublish_at?: string | null;
  created_at: string;
  updated_at?: string;
}

type NewsReviewAction = "approve" | "reject" | "pending";

type BatchReviewResponse = {
  processed: number[];
  missing: number[];
  action?: string;
  reason?: string | null;
  requested?: number[];
  counts?: {
    requested: number;
    processed: number;
    missing: number;
    notifications_created?: number;
  };
  message?: string;
};

function normalizeReviewStatus(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

function getReviewBadge(statusRaw: unknown) {
  const s = normalizeReviewStatus(statusRaw);
  if (s === "approved") return { label: "已通过", variant: "success" as const };
  if (s === "rejected") return { label: "已驳回", variant: "danger" as const };
  if (s === "pending") return { label: "待审核", variant: "warning" as const };
  return { label: s || "-", variant: "default" as const };
}

interface NewsAIAnnotation {
  summary: string | null;
  risk_level: string;
  sensitive_words: string[];
  highlights?: string[];
  keywords?: string[];
  duplicate_of_news_id: number | null;
  processed_at: string | null;
}

function normalizeRiskLevel(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

function getRiskBadge(riskLevelRaw: unknown) {
  const r = normalizeRiskLevel(riskLevelRaw);
  if (r === "safe") return { label: "安全", variant: "success" as const };
  if (r === "warning") return { label: "注意", variant: "warning" as const };
  if (r === "danger") return { label: "敏感", variant: "danger" as const };
  if (r === "unknown" || !r)
    return { label: "未知", variant: "default" as const };
  return { label: r, variant: "default" as const };
}

function toDatetimeLocalValue(value: unknown): string {
  if (typeof value !== "string") return "";
  const v = value.trim();
  if (!v) return "";
  const normalized =
    v.includes(" ") && !v.includes("T") ? v.replace(" ", "T") : v;
  return normalized.slice(0, 16);
}

interface NewsAdminListResponse {
  items: NewsItem[];
  total: number;
  page: number;
  page_size: number;
}

export default function NewsManagePage() {
  const { actualTheme } = useTheme();
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [reviewStatus, setReviewStatus] = useState<string>("all");
  const [riskLevel, setRiskLevel] = useState<string>("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const toast = useToast();

  const [createImages, setCreateImages] = useState<string[]>([]);
  const [editImages, setEditImages] = useState<string[]>([]);
  const [editingAi, setEditingAi] = useState<NewsAIAnnotation | null>(null);
  const [editingAiRisk, setEditingAiRisk] = useState<string>("unknown");

  const [createForm, setCreateForm] = useState({
    title: "",
    category: "法律动态",
    summary: "",
    cover_image: "",
    source: "",
    source_url: "",
    source_site: "",
    author: "",
    content: "",
    is_top: false,
    is_published: true,
    review_status: "approved",
    review_reason: "",
    scheduled_publish_at: "",
    scheduled_unpublish_at: "",
  });

  const loadAdminDetailForEdit = async (id: number) => {
    const res = await api.get(`/news/admin/${id}`);
    const detail = res.data as any;
    setEditingAi((detail?.ai_annotation ?? null) as NewsAIAnnotation | null);
    setEditingAiRisk(String(detail?.ai_risk_level ?? "unknown"));
    setEditForm({
      title: detail.title || "",
      category: detail.category || "法律动态",
      summary: detail.summary || "",
      cover_image: detail.cover_image || "",
      source: detail.source || "",
      source_url: detail.source_url || "",
      source_site: detail.source_site || "",
      author: detail.author || "",
      content: detail.content || "",
      is_top: !!detail.is_top,
      is_published: !!detail.is_published,
      review_status: String(detail.review_status || "approved"),
      review_reason: detail.review_reason || "",
      scheduled_publish_at: toDatetimeLocalValue(detail.scheduled_publish_at),
      scheduled_unpublish_at: toDatetimeLocalValue(
        detail.scheduled_unpublish_at
      ),
    });
    setEditImages(extractMarkdownImageUrls(String(detail.content || "")));
  };

  const [editForm, setEditForm] = useState({
    title: "",
    category: "法律动态",
    summary: "",
    cover_image: "",
    source: "",
    source_url: "",
    source_site: "",
    author: "",
    content: "",
    is_top: false,
    is_published: true,
    review_status: "approved",
    review_reason: "",
    scheduled_publish_at: "",
    scheduled_unpublish_at: "",
  });

  const newsQueryKey = useMemo(
    () =>
      [
        "admin-news",
        {
          keyword: keyword.trim(),
          page,
          pageSize,
          reviewStatus: String(reviewStatus || ""),
          riskLevel: String(riskLevel || ""),
        },
      ] as const,
    [keyword, page, pageSize, reviewStatus, riskLevel]
  );

  const newsQuery = useQuery({
    queryKey: newsQueryKey,
    queryFn: async () => {
      const trimmed = keyword.trim();
      const params: any = { page, page_size: pageSize };
      if (trimmed) params.keyword = trimmed;
      const rs = String(reviewStatus || "").trim();
      if (rs && rs !== "all") params.review_status = rs;
      const rl = String(riskLevel || "").trim();
      if (rl && rl !== "all") params.risk_level = rl;
      const res = await api.get("/news/admin/all", { params });
      return res.data as NewsAdminListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const news = newsQuery.data?.items ?? [];
  const total = newsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const loading = newsQuery.isLoading;
  const loadError = newsQuery.isError
    ? getApiErrorMessage(newsQuery.error, "新闻列表加载失败，请稍后重试")
    : null;

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    setSelectedIds(new Set());
  }, [newsQueryKey]);

  const deleteMutation = useAppMutation<void, number>({
    mutationFn: async (id) => {
      await api.delete(`/news/${id}`);
    },
    successMessage: "删除成功",
    errorMessageFallback: "删除失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
  });

  const togglePublishMutation = useAppMutation<
    NewsItem,
    { id: number; is_published: boolean }
  >({
    mutationFn: async (payload) => {
      const res = await api.put(`/news/${payload.id}`, {
        is_published: payload.is_published,
      });
      return res.data as NewsItem;
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: (res) => {
      const ok = Boolean((res as any)?.is_published);
      const rs = normalizeReviewStatus((res as any)?.review_status);
      if (!ok && rs && rs !== "approved") {
        toast.success("已保存为未发布（需审核通过后才能发布）");
        return;
      }
      toast.success(ok ? "已发布" : "已取消发布");
    },
  });

  const batchReviewNewsMutation = useAppMutation<
    BatchReviewResponse,
    { ids: number[]; action: NewsReviewAction; reason?: string | null }
  >({
    mutationFn: async (payload) => {
      const res = await api.post(`/news/admin/review/batch`, {
        ids: payload.ids,
        action: payload.action,
        reason: payload.reason ?? null,
      });
      return res.data as BatchReviewResponse;
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: (data) => {
      closeReviewReasonModal();
      setSelectedIds(new Set());
      if (data?.message) toast.success(data.message);
    },
  });

  const handleBatchReview = (action: NewsReviewAction) => {
    if (batchReviewNewsMutation.isPending) return;
    if (reviewNewsMutation.isPending) return;

    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    if (action === "approve") {
      batchReviewNewsMutation.mutate({ ids, action, reason: null });
      return;
    }

    openReviewReasonModal({ mode: "batch", ids, action });
  };

  const [reviewReasonModalOpen, setReviewReasonModalOpen] = useState(false);
  const [reviewReasonDraft, setReviewReasonDraft] = useState("");
  const [reviewTarget, setReviewTarget] = useState<
    | {
        mode: "single";
        id: number;
        action: Exclude<NewsReviewAction, "approve">;
      }
    | {
        mode: "batch";
        ids: number[];
        action: Exclude<NewsReviewAction, "approve">;
      }
    | null
  >(null);

  const closeReviewReasonModal = () => {
    setReviewReasonModalOpen(false);
    setReviewReasonDraft("");
    setReviewTarget(null);
  };

  const openReviewReasonModal = (
    target: Exclude<typeof reviewTarget, null>
  ) => {
    setReviewTarget(target);
    setReviewReasonDraft("");
    setReviewReasonModalOpen(true);
  };

  const reviewNewsMutation = useAppMutation<
    NewsItem,
    { id: number; action: NewsReviewAction; reason?: string | null }
  >({
    mutationFn: async (payload) => {
      const res = await api.post(`/news/admin/${payload.id}/review`, {
        action: payload.action,
        reason: payload.reason ?? null,
      });
      return res.data as NewsItem;
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: (res, payload) => {
      closeReviewReasonModal();
      if (payload.action === "approve") toast.success("已通过审核");
      else if (payload.action === "reject") toast.success("已驳回");
      else toast.success("已标记为待审核");

      if (payload.action === "approve" && Boolean((res as any)?.is_published)) {
        toast.success("审核通过并已发布");
      }
    },
  });

  const toggleTopMutation = useAppMutation<
    void,
    { id: number; is_top: boolean }
  >({
    mutationFn: async (payload) => {
      await api.put(`/news/${payload.id}`, { is_top: payload.is_top });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: (_res, payload) => {
      toast.success(payload.is_top ? "已置顶" : "已取消置顶");
    },
  });

  const rerunAiMutation = useAppMutation<{ message?: string }, { id: number }>({
    mutationFn: async ({ id }) => {
      const res = await api.post(`/news/admin/${id}/ai/rerun`);
      return (res.data ?? {}) as { message?: string };
    },
    successMessage: "已触发重跑AI标注",
    errorMessageFallback: "重跑失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: async (_data, payload) => {
      if (editingId && editingId === payload.id) {
        try {
          await loadAdminDetailForEdit(payload.id);
        } catch (e) {
          toast.error(getApiErrorMessage(e, "加载失败，请稍后重试"));
        }
      }
    },
  });

  const createMutation = useAppMutation<
    void,
    {
      title: string;
      category: string;
      summary?: string | null;
      cover_image?: string | null;
      source?: string | null;
      source_url?: string | null;
      source_site?: string | null;
      author?: string | null;
      content: string;
      is_top: boolean;
      is_published: boolean;
      review_status?: string | null;
      review_reason?: string | null;
      scheduled_publish_at?: string | null;
      scheduled_unpublish_at?: string | null;
    }
  >({
    mutationFn: async (payload) => {
      await api.post("/news", payload);
    },
    successMessage: "发布成功",
    errorMessageFallback: "发布失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: () => {
      setShowCreateModal(false);
      setCreateImages([]);
      setCreateForm({
        title: "",
        category: "法律动态",
        summary: "",
        cover_image: "",
        source: "",
        source_url: "",
        source_site: "",
        author: "",
        content: "",
        is_top: false,
        is_published: true,
        review_status: "approved",
        review_reason: "",
        scheduled_publish_at: "",
        scheduled_unpublish_at: "",
      });
    },
  });

  const editMutation = useAppMutation<
    void,
    {
      id: number;
      payload: {
        title: string;
        category: string;
        summary?: string | null;
        cover_image?: string | null;
        source?: string | null;
        source_url?: string | null;
        source_site?: string | null;
        author?: string | null;
        content: string;
        is_top: boolean;
        is_published: boolean;
        review_status?: string | null;
        review_reason?: string | null;
        scheduled_publish_at?: string | null;
        scheduled_unpublish_at?: string | null;
      };
    }
  >({
    mutationFn: async ({ id, payload }) => {
      await api.put(`/news/${id}`, payload);
    },
    successMessage: "保存成功",
    errorMessageFallback: "保存失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: () => {
      setShowEditModal(false);
      setEditingId(null);
    },
  });

  const handleDelete = async (id: number) => {
    if (!confirm("确定要删除这篇新闻吗？")) return;
    if (deleteMutation.isPending) return;
    deleteMutation.mutate(id);
  };

  const togglePublish = async (id: number, currentStatus: boolean) => {
    if (togglePublishMutation.isPending) return;
    togglePublishMutation.mutate({ id, is_published: !currentStatus });
  };

  const toggleTop = async (id: number, currentTop: boolean) => {
    if (toggleTopMutation.isPending) return;
    toggleTopMutation.mutate({ id, is_top: !currentTop });
  };

  const handleCreate = async () => {
    if (!createForm.title.trim() || !createForm.content.trim()) return;
    if (createMutation.isPending) return;
    createMutation.mutate({
      title: createForm.title.trim(),
      category: createForm.category,
      summary: createForm.summary.trim() ? createForm.summary.trim() : null,
      cover_image: createForm.cover_image.trim()
        ? createForm.cover_image.trim()
        : null,
      source: createForm.source.trim() ? createForm.source.trim() : null,
      source_url: createForm.source_url.trim()
        ? createForm.source_url.trim()
        : null,
      source_site: createForm.source_site.trim()
        ? createForm.source_site.trim()
        : null,
      author: createForm.author.trim() ? createForm.author.trim() : null,
      content: createForm.content.trim(),
      is_top: !!createForm.is_top,
      is_published: createForm.is_published,
      review_status: createForm.review_status || null,
      review_reason: createForm.review_reason.trim()
        ? createForm.review_reason.trim()
        : null,
      scheduled_publish_at: createForm.scheduled_publish_at.trim()
        ? createForm.scheduled_publish_at.trim()
        : null,
      scheduled_unpublish_at: createForm.scheduled_unpublish_at.trim()
        ? createForm.scheduled_unpublish_at.trim()
        : null,
    });
  };

  const openEdit = async (id: number) => {
    setEditingId(id);
    setShowEditModal(true);
    setEditingAi(null);
    setEditingAiRisk("unknown");
    try {
      await loadAdminDetailForEdit(id);
    } catch (e) {
      toast.error(getApiErrorMessage(e, "加载失败，请稍后重试"));
    }
  };

  const handleEdit = async () => {
    if (!editingId) return;
    if (!editForm.title.trim() || !editForm.content.trim()) return;
    if (editMutation.isPending) return;
    editMutation.mutate({
      id: editingId,
      payload: {
        title: editForm.title.trim(),
        category: editForm.category,
        summary: editForm.summary.trim() ? editForm.summary.trim() : null,
        cover_image: editForm.cover_image.trim()
          ? editForm.cover_image.trim()
          : null,
        source: editForm.source.trim() ? editForm.source.trim() : null,
        source_url: editForm.source_url.trim()
          ? editForm.source_url.trim()
          : null,
        source_site: editForm.source_site.trim()
          ? editForm.source_site.trim()
          : null,
        author: editForm.author.trim() ? editForm.author.trim() : null,
        content: editForm.content.trim(),
        is_top: !!editForm.is_top,
        is_published: editForm.is_published,
        review_status: editForm.review_status || null,
        review_reason: editForm.review_reason.trim()
          ? editForm.review_reason.trim()
          : null,
        scheduled_publish_at: editForm.scheduled_publish_at.trim()
          ? editForm.scheduled_publish_at.trim()
          : null,
        scheduled_unpublish_at: editForm.scheduled_unpublish_at.trim()
          ? editForm.scheduled_unpublish_at.trim()
          : null,
      },
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            新闻管理
          </h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">
            管理法律新闻和资讯
          </p>
        </div>
        <Button icon={Plus} onClick={() => setShowCreateModal(true)}>
          发布新闻
        </Button>
      </div>

      <Card variant="surface" padding="md">
        <div className="flex gap-4 mb-6">
          <div className="flex-1 max-w-md">
            <Input
              icon={Search}
              value={keyword}
              onChange={(e) => {
                setKeyword(e.target.value);
                setPage(1);
              }}
              placeholder="搜索新闻标题..."
            />
          </div>
          <select
            data-testid="admin-news-review-filter"
            value={reviewStatus}
            onChange={(e) => {
              setReviewStatus(e.target.value);
              setPage(1);
            }}
            className="px-4 py-2 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
          >
            <option value="all">全部审核状态</option>
            <option value="pending">待审核</option>
            <option value="approved">已通过</option>
            <option value="rejected">已驳回</option>
          </select>
          <select
            data-testid="admin-news-risk-filter"
            value={riskLevel}
            onChange={(e) => {
              setRiskLevel(e.target.value);
              setPage(1);
            }}
            className="px-4 py-2 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
          >
            <option value="all">全部AI风险</option>
            <option value="unknown">未知</option>
            <option value="safe">安全</option>
            <option value="warning">注意</option>
            <option value="danger">敏感</option>
          </select>
        </div>

        {loading ? (
          <Loading text="加载中..." tone={actualTheme} />
        ) : loadError ? (
          <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
            <div>{loadError}</div>
            <Button variant="outline" onClick={() => newsQuery.refetch()}>
              重试
            </Button>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm text-slate-600 dark:text-white/60">
                已选 {selectedIds.size} 条
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBatchReview("approve")}
                  data-testid="admin-news-batch-approve"
                  aria-label="admin-news-batch-approve"
                  disabled={
                    selectedIds.size === 0 ||
                    batchReviewNewsMutation.isPending ||
                    reviewNewsMutation.isPending
                  }
                >
                  批量通过
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBatchReview("reject")}
                  data-testid="admin-news-batch-reject"
                  aria-label="admin-news-batch-reject"
                  disabled={
                    selectedIds.size === 0 ||
                    batchReviewNewsMutation.isPending ||
                    reviewNewsMutation.isPending
                  }
                >
                  批量驳回
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBatchReview("pending")}
                  data-testid="admin-news-batch-pending"
                  aria-label="admin-news-batch-pending"
                  disabled={
                    selectedIds.size === 0 ||
                    batchReviewNewsMutation.isPending ||
                    reviewNewsMutation.isPending
                  }
                >
                  批量待审
                </Button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200/70 dark:border-white/10">
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      <input
                        type="checkbox"
                        data-testid="admin-news-select-all"
                        aria-label="admin-news-select-all"
                        checked={
                          news.length > 0 &&
                          news.every((x) => selectedIds.has(x.id))
                        }
                        onChange={() => {
                          const ids = news.map((x) => x.id);
                          setSelectedIds((prev) => {
                            const next = new Set(prev);
                            const all =
                              ids.length > 0 && ids.every((id) => next.has(id));
                            if (all) ids.forEach((id) => next.delete(id));
                            else ids.forEach((id) => next.add(id));
                            return next;
                          });
                        }}
                      />
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      标题
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      分类
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      AI风险
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      状态
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      审核
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      置顶
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      阅读量
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      发布时间
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      定时
                    </th>
                    <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {news.map((item) => (
                    <tr
                      key={item.id}
                      data-testid={`admin-news-${item.id}`}
                      className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5"
                    >
                      <td className="py-4 px-4">
                        <input
                          type="checkbox"
                          data-testid={`admin-news-select-${item.id}`}
                          aria-label={`admin-news-select-${item.id}`}
                          checked={selectedIds.has(item.id)}
                          onChange={() => {
                            setSelectedIds((prev) => {
                              const next = new Set(prev);
                              if (next.has(item.id)) next.delete(item.id);
                              else next.add(item.id);
                              return next;
                            });
                          }}
                        />
                      </td>
                      <td className="py-4 px-4">
                        <p className="text-slate-900 font-medium truncate max-w-xs dark:text-white">
                          {item.title}
                        </p>
                      </td>
                      <td className="py-4 px-4">
                        <Badge variant="info" size="sm">
                          {item.category}
                        </Badge>
                      </td>
                      <td className="py-4 px-4">
                        {(() => {
                          const r = getRiskBadge(item.ai_risk_level);
                          return (
                            <Badge variant={r.variant} size="sm">
                              {r.label}
                            </Badge>
                          );
                        })()}
                      </td>
                      <td className="py-4 px-4">
                        {item.is_published ? (
                          <Badge variant="success" size="sm">
                            已发布
                          </Badge>
                        ) : (
                          <Badge variant="warning" size="sm">
                            草稿
                          </Badge>
                        )}
                      </td>
                      <td className="py-4 px-4">
                        {(() => {
                          const r = getReviewBadge(item.review_status);
                          return (
                            <Badge variant={r.variant} size="sm">
                              {r.label}
                            </Badge>
                          );
                        })()}
                      </td>
                      <td className="py-4 px-4">
                        {item.is_top ? (
                          <Badge variant="warning" size="sm">
                            置顶
                          </Badge>
                        ) : (
                          <span className="text-slate-400 dark:text-white/30">
                            -
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-4 text-slate-700 dark:text-white/70">
                        {item.view_count.toLocaleString()}
                      </td>
                      <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                        {new Date(
                          item.published_at || item.created_at
                        ).toLocaleDateString()}
                      </td>
                      <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                        {item.scheduled_publish_at ? (
                          <div className="leading-5">
                            <div>
                              发：
                              {new Date(
                                item.scheduled_publish_at
                              ).toLocaleString()}
                            </div>
                            {item.scheduled_unpublish_at ? (
                              <div>
                                下：
                                {new Date(
                                  item.scheduled_unpublish_at
                                ).toLocaleString()}
                              </div>
                            ) : null}
                          </div>
                        ) : item.scheduled_unpublish_at ? (
                          <div className="leading-5">
                            下：
                            {new Date(
                              item.scheduled_unpublish_at
                            ).toLocaleString()}
                          </div>
                        ) : (
                          <span className="text-slate-400 dark:text-white/30">
                            -
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-2"
                            onClick={() =>
                              reviewNewsMutation.mutate({
                                id: item.id,
                                action: "approve",
                                reason: null,
                              })
                            }
                            title="审核通过"
                            aria-label={`admin-news-approve-${item.id}`}
                            data-testid={`admin-news-approve-${item.id}`}
                            disabled={
                              reviewNewsMutation.isPending ||
                              batchReviewNewsMutation.isPending
                            }
                          >
                            <Check className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-2"
                            onClick={() =>
                              openReviewReasonModal({
                                mode: "single",
                                id: item.id,
                                action: "reject",
                              })
                            }
                            title="审核驳回"
                            aria-label={`admin-news-reject-${item.id}`}
                            data-testid={`admin-news-reject-${item.id}`}
                            disabled={
                              reviewNewsMutation.isPending ||
                              batchReviewNewsMutation.isPending
                            }
                          >
                            <XCircle className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-2"
                            onClick={() =>
                              openReviewReasonModal({
                                mode: "single",
                                id: item.id,
                                action: "pending",
                              })
                            }
                            title="设为待审核"
                            aria-label={`admin-news-pending-${item.id}`}
                            data-testid={`admin-news-pending-${item.id}`}
                            disabled={
                              reviewNewsMutation.isPending ||
                              batchReviewNewsMutation.isPending
                            }
                          >
                            <Clock className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-2"
                            onClick={() => toggleTop(item.id, !!item.is_top)}
                            title={item.is_top ? "取消置顶" : "置顶"}
                            aria-label={`admin-news-toggle-top-${item.id}`}
                            data-testid={`admin-news-toggle-top-${item.id}`}
                            disabled={
                              reviewNewsMutation.isPending ||
                              batchReviewNewsMutation.isPending
                            }
                          >
                            <Pin
                              className={`h-4 w-4 ${
                                item.is_top ? "" : "opacity-60"
                              }`}
                            />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-2"
                            onClick={() =>
                              togglePublish(item.id, item.is_published)
                            }
                            title={item.is_published ? "取消发布" : "发布"}
                            aria-label={`admin-news-toggle-publish-${item.id}`}
                            data-testid={`admin-news-toggle-publish-${item.id}`}
                            disabled={
                              reviewNewsMutation.isPending ||
                              batchReviewNewsMutation.isPending ||
                              rerunAiMutation.isPending
                            }
                          >
                            {item.is_published ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-2"
                            title="重跑AI标注"
                            aria-label={`admin-news-ai-rerun-${item.id}`}
                            data-testid={`admin-news-ai-rerun-${item.id}`}
                            onClick={() => {
                              if (rerunAiMutation.isPending) return;
                              if (!confirm("确认重跑该新闻的AI标注？")) return;
                              rerunAiMutation.mutate({ id: item.id });
                            }}
                            disabled={
                              reviewNewsMutation.isPending ||
                              batchReviewNewsMutation.isPending ||
                              rerunAiMutation.isPending
                            }
                          >
                            <RotateCcw className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-2"
                            title="编辑"
                            aria-label={`admin-news-edit-${item.id}`}
                            data-testid={`admin-news-edit-${item.id}`}
                            onClick={() => openEdit(item.id)}
                            disabled={
                              reviewNewsMutation.isPending ||
                              batchReviewNewsMutation.isPending
                            }
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-2 text-red-400 hover:text-red-300"
                            onClick={() => handleDelete(item.id)}
                            title="删除"
                            aria-label={`admin-news-delete-${item.id}`}
                            data-testid={`admin-news-delete-${item.id}`}
                            disabled={
                              reviewNewsMutation.isPending ||
                              batchReviewNewsMutation.isPending
                            }
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {news.length === 0 && (
              <div className="text-center py-12 text-slate-500 dark:text-white/40">
                暂无新闻
              </div>
            )}

            {totalPages > 1 ? (
              <div className="pt-6">
                <Pagination
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={setPage}
                />
              </div>
            ) : null}
          </>
        )}
      </Card>

      <Modal
        isOpen={reviewReasonModalOpen}
        onClose={closeReviewReasonModal}
        title={reviewTarget?.action === "pending" ? "设为待审核" : "驳回新闻"}
        description={
          reviewTarget?.action === "pending"
            ? "设为待审核后将自动设为未发布。可填写原因用于审核记录。"
            : "驳回后将自动设为未发布。填写原因将通知运营侧/审核记录。"
        }
      >
        <div className="space-y-4">
          <div>
            <p className="text-sm text-slate-700 dark:text-white/70 mb-2">
              原因（可选）
            </p>
            <Textarea
              value={reviewReasonDraft}
              onChange={(e) => setReviewReasonDraft(e.target.value)}
              rows={4}
              placeholder="例如：来源不明 / 内容不准确 / 涉及敏感信息"
            />
          </div>
          <ModalActions className="pt-2">
            <Button
              variant="ghost"
              onClick={closeReviewReasonModal}
              disabled={
                reviewNewsMutation.isPending ||
                batchReviewNewsMutation.isPending
              }
            >
              取消
            </Button>
            <Button
              onClick={() => {
                if (!reviewTarget) return;
                const reason = reviewReasonDraft.trim()
                  ? reviewReasonDraft.trim()
                  : null;
                if (reviewTarget.mode === "single") {
                  reviewNewsMutation.mutate({
                    id: reviewTarget.id,
                    action: reviewTarget.action,
                    reason,
                  });
                  return;
                }
                batchReviewNewsMutation.mutate({
                  ids: reviewTarget.ids,
                  action: reviewTarget.action,
                  reason,
                });
              }}
              disabled={
                reviewNewsMutation.isPending ||
                batchReviewNewsMutation.isPending
              }
            >
              {reviewNewsMutation.isPending || batchReviewNewsMutation.isPending
                ? "处理中..."
                : reviewTarget?.action === "pending"
                ? "确认设置"
                : "确认驳回"}
            </Button>
          </ModalActions>
        </div>
      </Modal>

      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateImages([]);
        }}
        title="发布新闻"
        description="填写新闻内容"
        size="xl"
      >
        <div className="space-y-4">
          <Input
            label="标题"
            placeholder="请输入新闻标题"
            value={createForm.title}
            onChange={(e) =>
              setCreateForm((prev) => ({ ...prev, title: e.target.value }))
            }
          />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              分类
            </label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={createForm.category}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, category: e.target.value }))
              }
            >
              <option value="法律动态">法律动态</option>
              <option value="政策解读">政策解读</option>
              <option value="案例分析">案例分析</option>
              <option value="法律知识">法律知识</option>
            </select>
          </div>
          <Input
            label="摘要"
            placeholder="可选：一句话概括"
            value={createForm.summary}
            onChange={(e) =>
              setCreateForm((prev) => ({ ...prev, summary: e.target.value }))
            }
          />
          <Input
            label="封面图URL"
            placeholder="可选：http(s)://..."
            value={createForm.cover_image}
            onChange={(e) =>
              setCreateForm((prev) => ({
                ...prev,
                cover_image: e.target.value,
              }))
            }
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="来源"
              placeholder="可选"
              value={createForm.source}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, source: e.target.value }))
              }
            />
            <Input
              label="来源站点"
              placeholder="可选"
              value={createForm.source_site}
              onChange={(e) =>
                setCreateForm((prev) => ({
                  ...prev,
                  source_site: e.target.value,
                }))
              }
            />
            <Input
              label="来源链接"
              placeholder="可选：http(s)://..."
              value={createForm.source_url}
              onChange={(e) =>
                setCreateForm((prev) => ({
                  ...prev,
                  source_url: e.target.value,
                }))
              }
            />
            <Input
              label="作者"
              placeholder="可选"
              value={createForm.author}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, author: e.target.value }))
              }
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                审核状态
              </label>
              <select
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
                value={createForm.review_status}
                onChange={(e) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    review_status: e.target.value,
                  }))
                }
              >
                <option value="approved">已通过</option>
                <option value="pending">待审核</option>
                <option value="rejected">已驳回</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                审核原因（可选）
              </label>
              <Input
                value={createForm.review_reason}
                onChange={(e) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    review_reason: e.target.value,
                  }))
                }
                placeholder="可选"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              置顶
            </label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={createForm.is_top ? "top" : "normal"}
              onChange={(e) =>
                setCreateForm((prev) => ({
                  ...prev,
                  is_top: e.target.value === "top",
                }))
              }
            >
              <option value="normal">普通</option>
              <option value="top">置顶</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              状态
            </label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={createForm.is_published ? "published" : "draft"}
              onChange={(e) =>
                setCreateForm((prev) => ({
                  ...prev,
                  is_published: e.target.value === "published",
                }))
              }
            >
              <option value="published">发布</option>
              <option value="draft">草稿</option>
            </select>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                定时发布（可选）
              </label>
              <input
                type="datetime-local"
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
                value={createForm.scheduled_publish_at}
                onChange={(e) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    scheduled_publish_at: e.target.value,
                  }))
                }
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                定时下线（可选）
              </label>
              <input
                type="datetime-local"
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
                value={createForm.scheduled_unpublish_at}
                onChange={(e) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    scheduled_unpublish_at: e.target.value,
                  }))
                }
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              内容
            </label>
            <RichTextEditor
              value={createForm.content}
              onChange={(v) =>
                setCreateForm((prev) => ({ ...prev, content: v }))
              }
              images={createImages}
              onImagesChange={setCreateImages}
              placeholder="请输入内容，支持 Markdown、表情、图片链接..."
              minHeight="260px"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowCreateModal(false);
                setCreateImages([]);
              }}
            >
              取消
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!createForm.title.trim() || !createForm.content.trim()}
            >
              发布
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditingId(null);
          setEditImages([]);
          setEditingAi(null);
          setEditingAiRisk("unknown");
        }}
        title="编辑新闻"
        description="修改新闻内容"
        size="xl"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-200/70 bg-slate-50 px-4 py-3 dark:border-white/10 dark:bg-white/5">
            <div className="text-sm text-slate-700 dark:text-white/70">
              AI 风险
            </div>
            <Badge variant={getRiskBadge(editingAiRisk).variant} size="sm">
              {getRiskBadge(editingAiRisk).label}
            </Badge>
          </div>
          <div className="flex justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (!editingId) return;
                if (rerunAiMutation.isPending) return;
                if (!confirm("确认重跑该新闻的AI标注？")) return;
                rerunAiMutation.mutate({ id: editingId });
              }}
              disabled={!editingId || rerunAiMutation.isPending}
            >
              {rerunAiMutation.isPending ? "重跑中..." : "重跑AI标注"}
            </Button>
          </div>
          {editingAi?.summary ? (
            <div className="rounded-xl border border-slate-200/70 bg-white px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-white/70">
              {editingAi.summary}
            </div>
          ) : null}
          {Array.isArray(editingAi?.highlights) &&
          (editingAi?.highlights?.length || 0) > 0 ? (
            <div className="rounded-xl border border-slate-200/70 bg-white px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-white/70">
              <div className="font-medium text-slate-800 mb-2 dark:text-white/80">
                要点
              </div>
              <ul className="list-disc pl-5 space-y-1">
                {editingAi?.highlights?.map((h, idx) => (
                  <li key={`${idx}-${h}`}>{h}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {Array.isArray(editingAi?.keywords) &&
          (editingAi?.keywords?.length || 0) > 0 ? (
            <div className="rounded-xl border border-slate-200/70 bg-white px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-white/70">
              <div className="font-medium text-slate-800 mb-2 dark:text-white/80">
                关键词
              </div>
              <div className="flex flex-wrap gap-2">
                {editingAi?.keywords?.map((k) => (
                  <Badge key={k} variant="info" size="sm">
                    {k}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}
          <Input
            label="标题"
            placeholder="请输入新闻标题"
            value={editForm.title}
            onChange={(e) =>
              setEditForm((prev) => ({ ...prev, title: e.target.value }))
            }
          />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              分类
            </label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={editForm.category}
              onChange={(e) =>
                setEditForm((prev) => ({ ...prev, category: e.target.value }))
              }
            >
              <option value="法律动态">法律动态</option>
              <option value="政策解读">政策解读</option>
              <option value="案例分析">案例分析</option>
              <option value="法律知识">法律知识</option>
            </select>
          </div>
          <Input
            label="摘要"
            placeholder="可选：一句话概括"
            value={editForm.summary}
            onChange={(e) =>
              setEditForm((prev) => ({ ...prev, summary: e.target.value }))
            }
          />
          <Input
            label="封面图URL"
            placeholder="可选：http(s)://..."
            value={editForm.cover_image}
            onChange={(e) =>
              setEditForm((prev) => ({ ...prev, cover_image: e.target.value }))
            }
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="来源"
              placeholder="可选"
              value={editForm.source}
              onChange={(e) =>
                setEditForm((prev) => ({ ...prev, source: e.target.value }))
              }
            />
            <Input
              label="来源站点"
              placeholder="可选"
              value={editForm.source_site}
              onChange={(e) =>
                setEditForm((prev) => ({
                  ...prev,
                  source_site: e.target.value,
                }))
              }
            />
            <Input
              label="来源链接"
              placeholder="可选：http(s)://..."
              value={editForm.source_url}
              onChange={(e) =>
                setEditForm((prev) => ({ ...prev, source_url: e.target.value }))
              }
            />
            <Input
              label="作者"
              placeholder="可选"
              value={editForm.author}
              onChange={(e) =>
                setEditForm((prev) => ({ ...prev, author: e.target.value }))
              }
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                审核状态
              </label>
              <select
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
                value={editForm.review_status}
                onChange={(e) =>
                  setEditForm((prev) => ({
                    ...prev,
                    review_status: e.target.value,
                  }))
                }
              >
                <option value="approved">已通过</option>
                <option value="pending">待审核</option>
                <option value="rejected">已驳回</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                审核原因（可选）
              </label>
              <Input
                value={editForm.review_reason}
                onChange={(e) =>
                  setEditForm((prev) => ({
                    ...prev,
                    review_reason: e.target.value,
                  }))
                }
                placeholder="可选"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              置顶
            </label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={editForm.is_top ? "top" : "normal"}
              onChange={(e) =>
                setEditForm((prev) => ({
                  ...prev,
                  is_top: e.target.value === "top",
                }))
              }
            >
              <option value="normal">普通</option>
              <option value="top">置顶</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              状态
            </label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={editForm.is_published ? "published" : "draft"}
              onChange={(e) =>
                setEditForm((prev) => ({
                  ...prev,
                  is_published: e.target.value === "published",
                }))
              }
            >
              <option value="published">发布</option>
              <option value="draft">草稿</option>
            </select>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                定时发布（可选）
              </label>
              <input
                type="datetime-local"
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
                value={editForm.scheduled_publish_at}
                onChange={(e) =>
                  setEditForm((prev) => ({
                    ...prev,
                    scheduled_publish_at: e.target.value,
                  }))
                }
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                定时下线（可选）
              </label>
              <input
                type="datetime-local"
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
                value={editForm.scheduled_unpublish_at}
                onChange={(e) =>
                  setEditForm((prev) => ({
                    ...prev,
                    scheduled_unpublish_at: e.target.value,
                  }))
                }
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              内容
            </label>
            <RichTextEditor
              value={editForm.content}
              onChange={(v) => setEditForm((prev) => ({ ...prev, content: v }))}
              images={editImages}
              onImagesChange={setEditImages}
              placeholder="请输入内容，支持 Markdown、表情、图片链接..."
              minHeight="260px"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowEditModal(false);
                setEditingId(null);
                setEditImages([]);
                setEditingAi(null);
                setEditingAiRisk("unknown");
              }}
            >
              取消
            </Button>
            <Button
              onClick={handleEdit}
              disabled={!editForm.title.trim() || !editForm.content.trim()}
            >
              保存
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
