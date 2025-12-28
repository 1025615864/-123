import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Search,
  Plus,
  Sparkles,
  Edit,
  Trash2,
  Eye,
  EyeOff,
  Pin,
  Check,
  XCircle,
  Clock,
  RotateCcw,
  Link2,
  History,
} from "lucide-react";
import {
  Card,
  Input,
  Button,
  Badge,
  FadeInImage,
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
import MarkdownContent from "../../components/MarkdownContent";

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

function tryParseFirstJsonObject(text: string): Record<string, unknown> | null {
  const raw = String(text || "");
  if (!raw.trim()) return null;

  const fenced = raw.match(/```json\s*([\s\S]*?)\s*```/i);
  if (fenced && fenced[1]) {
    try {
      const obj = JSON.parse(String(fenced[1]).trim());
      if (obj && typeof obj === "object" && !Array.isArray(obj)) {
        return obj as Record<string, unknown>;
      }
    } catch {
      // ignore
    }
  }

  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start >= 0 && end > start) {
    try {
      const obj = JSON.parse(raw.slice(start, end + 1));
      if (obj && typeof obj === "object" && !Array.isArray(obj)) {
        return obj as Record<string, unknown>;
      }
    } catch {
      // ignore
    }
  }
  return null;
}

function tryParseJson(text: unknown): Record<string, unknown> | null {
  if (typeof text !== "string") return null;
  const t = text.trim();
  if (!t) return null;
  try {
    const obj = JSON.parse(t);
    if (obj && typeof obj === "object" && !Array.isArray(obj)) {
      return obj as Record<string, unknown>;
    }
  } catch {
    return null;
  }
  return null;
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

type NewsBatchAction = "publish" | "unpublish" | "top" | "untop" | "rerun_ai";

type NewsBatchActionResponse = {
  requested: number[];
  processed: number[];
  missing: number[];
  skipped: number[];
  action: string;
  reason?: string | null;
  message: string;
};

type NewsVersionItem = {
  id: number;
  news_id: number;
  action: string;
  reason?: string | null;
  snapshot_json: string;
  created_by: number;
  created_at: string;
};

type NewsVersionListResponse = {
  items: NewsVersionItem[];
};

type NewsLinkCheckItem = {
  id: number;
  run_id: string;
  user_id: number;
  news_id?: number | null;
  url: string;
  final_url?: string | null;
  ok: boolean;
  status_code?: number | null;
  error?: string | null;
  checked_at: string;
};

type NewsLinkCheckResponse = {
  run_id: string;
  items: NewsLinkCheckItem[];
};

type NewsAIGenerationItem = {
  id: number;
  user_id: number;
  news_id?: number | null;
  task_type: string;
  status: string;
  input_json: string;
  output_json?: string | null;
  raw_output?: string | null;
  error?: string | null;
  created_at: string;
};

type NewsAIGenerationListResponse = {
  items: NewsAIGenerationItem[];
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

  const [createPublishMode, setCreatePublishMode] = useState<
    "publish" | "draft" | "schedule"
  >("publish");
  const [aiTopic, setAiTopic] = useState("");
  const [aiHints, setAiHints] = useState("");
  const [aiAutoRerunNewsAi, setAiAutoRerunNewsAi] = useState(true);
  const [createContentMode, setCreateContentMode] = useState<
    "edit" | "preview"
  >("edit");
  const [editContentMode, setEditContentMode] = useState<"edit" | "preview">(
    "edit"
  );

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
  const [batchAction, setBatchAction] = useState<NewsBatchAction>("publish");

  const [showVersionsModal, setShowVersionsModal] = useState(false);
  const [showLinkCheckModal, setShowLinkCheckModal] = useState(false);
  const [showWorkbenchModal, setShowWorkbenchModal] = useState(false);

  const [linkCheckTimeoutSeconds, setLinkCheckTimeoutSeconds] = useState("6");
  const [linkCheckMaxUrls, setLinkCheckMaxUrls] = useState("50");
  const [linkCheckRunId, setLinkCheckRunId] = useState("");
  const [linkCheckResult, setLinkCheckResult] =
    useState<NewsLinkCheckResponse | null>(null);

  const [workbenchTaskType, setWorkbenchTaskType] = useState("rewrite");
  const [workbenchStyle, setWorkbenchStyle] = useState("");
  const [workbenchWordMin, setWorkbenchWordMin] = useState("");
  const [workbenchWordMax, setWorkbenchWordMax] = useState("");
  const [workbenchAppend, setWorkbenchAppend] = useState(false);
  const [workbenchOutput, setWorkbenchOutput] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [workbenchRaw, setWorkbenchRaw] = useState("");

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

  const batchActionMutation = useAppMutation<
    NewsBatchActionResponse,
    { ids: number[]; action: NewsBatchAction; reason?: string | null }
  >({
    mutationFn: async (payload) => {
      const res = await api.post(`/news/admin/batch`, {
        ids: payload.ids,
        action: payload.action,
        reason: payload.reason ?? null,
      });
      return res.data as NewsBatchActionResponse;
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: (data) => {
      setSelectedIds(new Set());
      if (data?.message) toast.success(data.message);
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

  const handleBatchAction = async () => {
    if (batchActionMutation.isPending) return;
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    const action = batchAction;

    let reason: string | null = null;
    if (action !== "rerun_ai") {
      const r = prompt("原因（可选）", "");
      reason = r && r.trim() ? r.trim() : null;
    }

    await batchActionMutation.mutateAsync({ ids, action, reason });
  };

  const applyWorkbenchDraftToEditForm = (
    draft: Record<string, unknown>,
    rawAnswer: string
  ) => {
    const title = String(draft.title ?? "").trim();
    const summary = String(draft.summary ?? "").trim();
    const content =
      String(draft.content ?? "").trim() || String(rawAnswer || "").trim();

    setEditForm((prev) => ({
      ...prev,
      title: title || prev.title,
      summary: summary || prev.summary,
      content: content || prev.content,
    }));

    if (content) {
      setEditImages(extractMarkdownImageUrls(content));
    }
  };

  const versionsQuery = useQuery({
    queryKey: ["news-versions", { id: editingId, limit: 50 }] as const,
    enabled: showVersionsModal && !!editingId,
    queryFn: async () => {
      if (!editingId) return { items: [] } as NewsVersionListResponse;
      const res = await api.get(`/news/admin/${editingId}/versions`, {
        params: { limit: 50 },
      });
      return res.data as NewsVersionListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const rollbackMutation = useAppMutation<
    NewsItem,
    { version_id: number; reason?: string | null }
  >({
    mutationFn: async (payload) => {
      if (!editingId) throw new Error("missing editingId");
      const res = await api.post(`/news/admin/${editingId}/rollback`, {
        version_id: payload.version_id,
        reason: payload.reason ?? null,
      });
      return res.data as NewsItem;
    },
    errorMessageFallback: "回滚失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: async () => {
      if (editingId) {
        try {
          await loadAdminDetailForEdit(editingId);
        } catch (e) {
          toast.error(getApiErrorMessage(e, "加载失败，请稍后重试"));
        }
      }
      toast.success("已回滚并刷新内容");
      setShowVersionsModal(false);
    },
  });

  const linkCheckMutation = useAppMutation<
    NewsLinkCheckResponse,
    { markdown: string; timeout_seconds: number; max_urls: number }
  >({
    mutationFn: async (payload) => {
      const res = await api.post(`/news/admin/link_check`, {
        news_id: editingId,
        markdown: payload.markdown,
        timeout_seconds: payload.timeout_seconds,
        max_urls: payload.max_urls,
      });
      return res.data as NewsLinkCheckResponse;
    },
    errorMessageFallback: "链接检查失败，请稍后重试",
    onSuccess: (data) => {
      setLinkCheckResult(data);
      setLinkCheckRunId(String(data?.run_id || ""));
    },
  });

  const linkCheckFetchMutation = useAppMutation<
    NewsLinkCheckResponse,
    { run_id: string }
  >({
    mutationFn: async (payload) => {
      const rid = String(payload.run_id || "").trim();
      const res = await api.get(`/news/admin/link_check/${rid}`);
      return res.data as NewsLinkCheckResponse;
    },
    errorMessageFallback: "获取检查结果失败，请稍后重试",
    onSuccess: (data) => {
      setLinkCheckResult(data);
      setLinkCheckRunId(String(data?.run_id || ""));
    },
  });

  const workbenchGenerateMutation = useAppMutation<
    NewsAIGenerationItem,
    {
      task_type: string;
      style?: string | null;
      word_count_min?: number | null;
      word_count_max?: number | null;
      append: boolean;
    }
  >({
    mutationFn: async (payload) => {
      const res = await api.post(`/news/admin/ai/generate`, {
        news_id: editingId,
        task_type: payload.task_type,
        title: editForm.title || null,
        summary: editForm.summary || null,
        content: editForm.content || null,
        style: payload.style ?? null,
        word_count_min: payload.word_count_min ?? null,
        word_count_max: payload.word_count_max ?? null,
        append: !!payload.append,
        use_news_content: false,
      });
      return res.data as NewsAIGenerationItem;
    },
    errorMessageFallback: "AI 生成失败，请稍后重试",
    onSuccess: (data) => {
      const raw = String((data as any)?.raw_output || "");
      const outJson = (data as any)?.output_json;
      const parsed =
        tryParseJson(outJson) || tryParseFirstJsonObject(raw) || null;
      setWorkbenchOutput(parsed);
      setWorkbenchRaw(raw);
    },
  });

  const workbenchGenerationsQuery = useQuery({
    queryKey: ["news-ai-generations", { id: editingId, limit: 20 }] as const,
    enabled: showWorkbenchModal && !!editingId,
    queryFn: async () => {
      if (!editingId) return { items: [] } as NewsAIGenerationListResponse;
      const res = await api.get(`/news/admin/ai/generations`, {
        params: { news_id: editingId, limit: 20 },
      });
      return res.data as NewsAIGenerationListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

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
    successMessage: "已触发重跑AI标注，请稍等后刷新查看结果",
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
    { id: number },
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
      const res = await api.post("/news", payload);
      return (res.data ?? {}) as { id: number };
    },
    errorMessageFallback: "发布失败，请稍后重试",
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: (data, payload) => {
      const isPublished = Boolean((payload as any)?.is_published);
      const hasSchedule = Boolean((payload as any)?.scheduled_publish_at);
      if (hasSchedule) toast.success("已创建定时发布");
      else if (isPublished) toast.success("已发布");
      else toast.success("已保存草稿");

      setShowCreateModal(false);
      setCreateImages([]);
      setCreatePublishMode("publish");
      setAiTopic("");
      setAiHints("");
      setAiAutoRerunNewsAi(true);
      setCreateContentMode("edit");
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

      const createdId = Number((data as any)?.id || 0);
      if (createdId > 0 && aiAutoRerunNewsAi) {
        rerunAiMutation.mutate({ id: createdId });
      }
    },
  });

  const aiGenerateMutation = useAppMutation<
    { draft: Record<string, unknown>; rawAnswer: string },
    { topic: string; hints: string; category: string }
  >({
    mutationFn: async (payload) => {
      const topic = String(payload.topic || "").trim();
      const hints = String(payload.hints || "").trim();
      const cat = String(payload.category || "").trim();

      const prompt = [
        "你是一名法律资讯编辑。请根据给定主题与要点，生成一篇适合普通读者的法律资讯新闻。",
        "请只输出一个 JSON 对象，不要输出任何额外文字。",
        "字段为：title, summary, content, category, source, source_url, source_site, author。",
        "content 使用 Markdown，800~1200 字。",
        `主题：${topic}`,
        hints ? `要点：${hints}` : "",
        cat ? `分类建议：${cat}` : "",
      ]
        .filter(Boolean)
        .join("\n");

      const res = await api.post("/ai/chat", { message: prompt });
      const answer = String((res.data as any)?.answer || "");
      const parsed = tryParseFirstJsonObject(answer) || {};
      return { draft: parsed, rawAnswer: answer };
    },
    errorMessageFallback: "AI 生成失败，请稍后重试",
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

    const mode = createPublishMode;
    const reviewStatus = String(createForm.review_status || "")
      .trim()
      .toLowerCase();

    const scheduledPublish = createForm.scheduled_publish_at.trim();
    const scheduledUnpublish = createForm.scheduled_unpublish_at.trim();

    if (mode === "publish") {
      if (reviewStatus !== "approved") {
        toast.error("立即发布需要审核状态为：已通过");
        return;
      }
    }

    if (mode === "schedule") {
      if (!scheduledPublish) {
        toast.error("请选择定时发布时间");
        return;
      }
      if (reviewStatus !== "approved") {
        toast.error("定时发布需要审核状态为：已通过");
        return;
      }
      try {
        const pub = new Date(scheduledPublish);
        if (Number.isNaN(pub.getTime())) throw new Error("bad");
        if (pub.getTime() < Date.now() - 60 * 1000) {
          toast.error("定时发布时间不能早于当前时间");
          return;
        }
        if (scheduledUnpublish) {
          const un = new Date(scheduledUnpublish);
          if (Number.isNaN(un.getTime())) throw new Error("bad");
          if (un.getTime() <= pub.getTime()) {
            toast.error("定时下线时间需晚于定时发布时间");
            return;
          }
        }
      } catch {
        toast.error("定时日期格式不正确");
        return;
      }
    }

    const isPublished = mode === "publish";
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
      is_published: isPublished,
      review_status: createForm.review_status || null,
      review_reason: createForm.review_reason.trim()
        ? createForm.review_reason.trim()
        : null,
      scheduled_publish_at:
        mode === "schedule" && scheduledPublish ? scheduledPublish : null,
      scheduled_unpublish_at:
        mode === "schedule" && scheduledUnpublish ? scheduledUnpublish : null,
    });
  };

  const applyAiDraftToCreateForm = (
    draft: Record<string, unknown>,
    rawAnswer: string
  ) => {
    const title = String(draft.title ?? "").trim();
    const summary = String(draft.summary ?? "").trim();
    const content =
      String(draft.content ?? "").trim() || String(rawAnswer || "").trim();
    const category = String(draft.category ?? "").trim();

    setCreateForm((prev) => ({
      ...prev,
      title: title || prev.title,
      summary: summary || prev.summary,
      content: content || prev.content,
      category: category || prev.category,
      source: String(draft.source ?? "").trim() || prev.source,
      source_url: String(draft.source_url ?? "").trim() || prev.source_url,
      source_site: String(draft.source_site ?? "").trim() || prev.source_site,
      author: String(draft.author ?? "").trim() || prev.author,
    }));

    if (content) {
      setCreateImages(extractMarkdownImageUrls(content));
    }
  };

  const handleAiGenerateFill = async (autoPublish: boolean) => {
    if (aiGenerateMutation.isPending) return;
    if (createMutation.isPending) return;

    const topic = aiTopic.trim();
    if (!topic) {
      toast.error("请输入 AI 主题");
      return;
    }

    const result = await aiGenerateMutation.mutateAsync({
      topic,
      hints: aiHints.trim(),
      category: createForm.category,
    });

    applyAiDraftToCreateForm(result.draft, result.rawAnswer);

    if (autoPublish) {
      setCreatePublishMode("publish");
      setCreateForm((prev) => ({
        ...prev,
        is_published: true,
        review_status: "approved",
        scheduled_publish_at: "",
        scheduled_unpublish_at: "",
      }));

      const title = String(
        (result.draft as any)?.title || createForm.title || ""
      ).trim();
      const content = String(
        (result.draft as any)?.content ||
          createForm.content ||
          result.rawAnswer ||
          ""
      ).trim();
      if (!title || !content) {
        toast.error("AI 生成内容不完整，请先检查后再发布");
        return;
      }

      await createMutation.mutateAsync({
        title: title || createForm.title.trim(),
        category: String(
          (result.draft as any)?.category || createForm.category || "法律动态"
        ),
        summary:
          String(
            (result.draft as any)?.summary || createForm.summary || ""
          ).trim() || null,
        cover_image: createForm.cover_image.trim()
          ? createForm.cover_image.trim()
          : null,
        source:
          String(
            (result.draft as any)?.source || createForm.source || ""
          ).trim() || null,
        source_url:
          String(
            (result.draft as any)?.source_url || createForm.source_url || ""
          ).trim() || null,
        source_site:
          String(
            (result.draft as any)?.source_site || createForm.source_site || ""
          ).trim() || null,
        author:
          String(
            (result.draft as any)?.author || createForm.author || ""
          ).trim() || null,
        content,
        is_top: !!createForm.is_top,
        is_published: true,
        review_status: "approved",
        review_reason: null,
        scheduled_publish_at: null,
        scheduled_unpublish_at: null,
      });
    }
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
                <select
                  value={batchAction}
                  onChange={(e) =>
                    setBatchAction(e.target.value as NewsBatchAction)
                  }
                  className="px-3 py-2 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none text-sm dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
                  disabled={
                    selectedIds.size === 0 ||
                    batchActionMutation.isPending ||
                    batchReviewNewsMutation.isPending ||
                    reviewNewsMutation.isPending
                  }
                >
                  <option value="publish">批量发布</option>
                  <option value="unpublish">批量下线</option>
                  <option value="top">批量置顶</option>
                  <option value="untop">批量取消置顶</option>
                  <option value="rerun_ai">批量重跑AI</option>
                </select>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBatchAction}
                  disabled={
                    selectedIds.size === 0 ||
                    batchActionMutation.isPending ||
                    batchReviewNewsMutation.isPending ||
                    reviewNewsMutation.isPending
                  }
                >
                  {batchActionMutation.isPending ? "执行中..." : "执行"}
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
                            variant="outline"
                            size="sm"
                            className="p-2 sm:px-3"
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
                            <span className="hidden sm:inline">重跑AI</span>
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
        isOpen={showVersionsModal}
        onClose={() => setShowVersionsModal(false)}
        title="版本历史"
        description="查看历史快照并回滚"
        size="lg"
        zIndexClass="z-[60]"
      >
        <div className="space-y-4">
          {versionsQuery.isLoading ? (
            <Loading text="加载中..." tone={actualTheme} />
          ) : versionsQuery.isError ? (
            <div className="text-sm text-red-600 dark:text-red-300">
              {getApiErrorMessage(versionsQuery.error, "加载失败，请稍后重试")}
            </div>
          ) : (
            <div className="space-y-3">
              {(versionsQuery.data?.items ?? []).length === 0 ? (
                <div className="text-sm text-slate-500 dark:text-white/50">
                  暂无版本记录
                </div>
              ) : (
                <div className="space-y-2">
                  {(versionsQuery.data?.items ?? []).map((v) => (
                    <div
                      key={v.id}
                      className="rounded-xl border border-slate-200/70 bg-white p-3 dark:border-white/10 dark:bg-white/5"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-sm text-slate-800 dark:text-white/80">
                          <span className="font-medium">#{v.id}</span>
                          <span className="ml-2">
                            {String(v.action || "-")}
                          </span>
                          {v.reason ? (
                            <span className="ml-2 text-slate-500 dark:text-white/50">
                              {v.reason}
                            </span>
                          ) : null}
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="text-xs text-slate-500 dark:text-white/40">
                            {v.created_at
                              ? new Date(v.created_at).toLocaleString()
                              : ""}
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              if (rollbackMutation.isPending) return;
                              if (!confirm(`确认回滚到版本 #${v.id}？`)) return;
                              const r = prompt("回滚原因（可选）", "");
                              const rsn = r && r.trim() ? r.trim() : null;
                              rollbackMutation.mutate({
                                version_id: v.id,
                                reason: rsn,
                              });
                            }}
                            disabled={rollbackMutation.isPending}
                          >
                            {rollbackMutation.isPending ? "回滚中..." : "回滚"}
                          </Button>
                        </div>
                      </div>
                      <div className="mt-1 text-xs text-slate-500 dark:text-white/40">
                        操作人：{v.created_by}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>

      <Modal
        isOpen={showLinkCheckModal}
        onClose={() => {
          setShowLinkCheckModal(false);
          setLinkCheckResult(null);
          setLinkCheckRunId("");
        }}
        title="链接检查"
        description="提取正文中的链接并检测可访问性"
        size="xl"
        zIndexClass="z-[60]"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Input
              label="超时（秒）"
              value={linkCheckTimeoutSeconds}
              onChange={(e) => setLinkCheckTimeoutSeconds(e.target.value)}
              placeholder="6"
            />
            <Input
              label="最多链接数"
              value={linkCheckMaxUrls}
              onChange={(e) => setLinkCheckMaxUrls(e.target.value)}
              placeholder="50"
            />
            <div className="flex items-end justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  const md = String(editForm.content || "");
                  if (!md.trim()) {
                    toast.error("正文为空，无法检查");
                    return;
                  }
                  const t = Number(linkCheckTimeoutSeconds || 6);
                  const m = Number(linkCheckMaxUrls || 50);
                  linkCheckMutation.mutate({
                    markdown: md,
                    timeout_seconds: Number.isFinite(t) ? t : 6,
                    max_urls: Number.isFinite(m) ? m : 50,
                  });
                }}
                disabled={linkCheckMutation.isPending}
              >
                {linkCheckMutation.isPending ? "检查中..." : "开始检查"}
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Input
              label="run_id（可选）"
              value={linkCheckRunId}
              onChange={(e) => setLinkCheckRunId(e.target.value)}
              placeholder="粘贴 run_id 以加载历史结果"
            />
            <div className="flex items-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  const rid = linkCheckRunId.trim();
                  if (!rid) return;
                  linkCheckFetchMutation.mutate({ run_id: rid });
                }}
                disabled={
                  linkCheckFetchMutation.isPending || !linkCheckRunId.trim()
                }
              >
                {linkCheckFetchMutation.isPending ? "加载中..." : "加载结果"}
              </Button>
              {linkCheckResult?.run_id ? (
                <Badge variant="info" size="sm">
                  {linkCheckResult.run_id}
                </Badge>
              ) : null}
            </div>
          </div>

          {linkCheckResult ? (
            <div className="rounded-xl border border-slate-200/70 bg-white p-3 dark:border-white/10 dark:bg-white/5">
              <div className="text-sm font-medium text-slate-800 dark:text-white/80 mb-2">
                检查结果（{linkCheckResult.items.length}）
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200/70 dark:border-white/10">
                      <th className="text-left py-2 pr-3 text-slate-500 font-medium dark:text-white/50">
                        URL
                      </th>
                      <th className="text-left py-2 pr-3 text-slate-500 font-medium dark:text-white/50">
                        状态
                      </th>
                      <th className="text-left py-2 pr-3 text-slate-500 font-medium dark:text-white/50">
                        Code
                      </th>
                      <th className="text-left py-2 pr-3 text-slate-500 font-medium dark:text-white/50">
                        备注
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {linkCheckResult.items.map((x) => (
                      <tr
                        key={x.id}
                        className="border-b border-slate-200/50 dark:border-white/5"
                      >
                        <td className="py-2 pr-3">
                          <a
                            href={x.final_url || x.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-amber-600 hover:underline dark:text-amber-400 break-all"
                          >
                            {x.url}
                          </a>
                        </td>
                        <td className="py-2 pr-3">
                          <Badge
                            variant={x.ok ? "success" : "danger"}
                            size="sm"
                          >
                            {x.ok ? "OK" : "FAIL"}
                          </Badge>
                        </td>
                        <td className="py-2 pr-3 text-slate-600 dark:text-white/60">
                          {x.status_code ?? "-"}
                        </td>
                        <td className="py-2 pr-3 text-slate-500 dark:text-white/50 break-all">
                          {x.error || ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </div>
      </Modal>

      <Modal
        isOpen={showWorkbenchModal}
        onClose={() => {
          setShowWorkbenchModal(false);
          setWorkbenchOutput(null);
          setWorkbenchRaw("");
        }}
        title="AI 工作台"
        description="生成/改写/润色/提纲等（支持一键应用到编辑表单）"
        size="xl"
        zIndexClass="z-[60]"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                任务类型
              </label>
              <select
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
                value={workbenchTaskType}
                onChange={(e) => setWorkbenchTaskType(e.target.value)}
              >
                <option value="rewrite">改写</option>
                <option value="polish">润色</option>
                <option value="outline">大纲</option>
                <option value="title_candidates">标题建议</option>
                <option value="summary_candidates">摘要建议</option>
                <option value="risk_warnings">风险提示</option>
              </select>
            </div>
            <Input
              label="风格（可选）"
              value={workbenchStyle}
              onChange={(e) => setWorkbenchStyle(e.target.value)}
              placeholder="例如：简洁 / 口语化 / 严谨"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Input
              label="字数最小（可选）"
              value={workbenchWordMin}
              onChange={(e) => setWorkbenchWordMin(e.target.value)}
              placeholder="800"
            />
            <Input
              label="字数最大（可选）"
              value={workbenchWordMax}
              onChange={(e) => setWorkbenchWordMax(e.target.value)}
              placeholder="1200"
            />
            <div className="flex items-center gap-2 pt-7">
              <input
                type="checkbox"
                checked={workbenchAppend}
                onChange={(e) => setWorkbenchAppend(e.target.checked)}
              />
              <span className="text-sm text-slate-700 dark:text-white/70">
                追加到正文
              </span>
            </div>
          </div>
          <div className="flex justify-end">
            <Button
              variant="outline"
              onClick={() => {
                const min = workbenchWordMin.trim()
                  ? Number(workbenchWordMin)
                  : null;
                const max = workbenchWordMax.trim()
                  ? Number(workbenchWordMax)
                  : null;
                workbenchGenerateMutation.mutate({
                  task_type: workbenchTaskType,
                  style: workbenchStyle.trim() ? workbenchStyle.trim() : null,
                  word_count_min: min && Number.isFinite(min) ? min : null,
                  word_count_max: max && Number.isFinite(max) ? max : null,
                  append: !!workbenchAppend,
                });
              }}
              disabled={workbenchGenerateMutation.isPending}
            >
              {workbenchGenerateMutation.isPending ? "生成中..." : "生成"}
            </Button>
          </div>

          {workbenchOutput || workbenchRaw ? (
            <div className="rounded-xl border border-slate-200/70 bg-white p-3 dark:border-white/10 dark:bg-white/5">
              <div className="flex items-center justify-between gap-2 mb-2">
                <div className="text-sm font-medium text-slate-800 dark:text-white/80">
                  输出
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const draft = workbenchOutput || {};
                    applyWorkbenchDraftToEditForm(draft, workbenchRaw);
                    toast.success("已应用到编辑表单");
                  }}
                  disabled={!workbenchOutput && !workbenchRaw}
                >
                  应用到正文
                </Button>
              </div>
              <Textarea
                value={
                  workbenchOutput
                    ? JSON.stringify(workbenchOutput, null, 2)
                    : String(workbenchRaw || "")
                }
                onChange={() => {}}
                rows={10}
              />
            </div>
          ) : null}

          <div className="rounded-xl border border-slate-200/70 bg-slate-50 p-3 dark:border-white/10 dark:bg-white/5">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-medium text-slate-800 dark:text-white/80">
                生成历史（最近 20 条）
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => workbenchGenerationsQuery.refetch()}
                disabled={workbenchGenerationsQuery.isFetching}
              >
                刷新
              </Button>
            </div>
            <div className="mt-3 space-y-2">
              {workbenchGenerationsQuery.isLoading ? (
                <div className="text-sm text-slate-500 dark:text-white/50">
                  加载中...
                </div>
              ) : workbenchGenerationsQuery.isError ? (
                <div className="text-sm text-red-600 dark:text-red-300">
                  {getApiErrorMessage(
                    workbenchGenerationsQuery.error,
                    "加载失败，请稍后重试"
                  )}
                </div>
              ) : (workbenchGenerationsQuery.data?.items ?? []).length === 0 ? (
                <div className="text-sm text-slate-500 dark:text-white/50">
                  暂无记录
                </div>
              ) : (
                (workbenchGenerationsQuery.data?.items ?? []).map((g) => {
                  const out = tryParseJson(g.output_json) || null;
                  return (
                    <div
                      key={g.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200/70 bg-white px-3 py-2 dark:border-white/10 dark:bg-white/5"
                    >
                      <div className="text-sm text-slate-800 dark:text-white/80">
                        <span className="font-medium">#{g.id}</span>
                        <span className="ml-2">{g.task_type}</span>
                        <span className="ml-2 text-slate-500 dark:text-white/50">
                          {g.status}
                        </span>
                        <span className="ml-2 text-xs text-slate-500 dark:text-white/40">
                          {g.created_at
                            ? new Date(g.created_at).toLocaleString()
                            : ""}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            if (!out) {
                              toast.error("该记录没有可应用的结构化输出");
                              return;
                            }
                            setWorkbenchOutput(out);
                            setWorkbenchRaw(String(g.raw_output || ""));
                          }}
                          disabled={!out}
                        >
                          查看
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            if (!out) return;
                            applyWorkbenchDraftToEditForm(
                              out,
                              String(g.raw_output || "")
                            );
                            toast.success("已应用到编辑表单");
                          }}
                          disabled={!out}
                        >
                          应用
                        </Button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateImages([]);
          setCreateContentMode("edit");
        }}
        title="发布新闻"
        description="填写新闻内容"
        size="xl"
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200/70 bg-slate-50 px-4 py-3 dark:border-white/10 dark:bg-white/5">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-800 dark:text-white/80">
              <Sparkles className="h-4 w-4" />
              AI 一键生成 / 发布
            </div>
            <div className="mt-3 space-y-3">
              <Input
                label="AI 主题"
                placeholder="例如：普通人如何识别和防范电信网络诈骗"
                value={aiTopic}
                onChange={(e) => setAiTopic(e.target.value)}
              />
              <Textarea
                label="要点（可选）"
                placeholder="可填写关键要点/结构要求，例如：风险点、法律依据、常见话术、操作清单等"
                value={aiHints}
                onChange={(e) => setAiHints(e.target.value)}
                rows={3}
              />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-white/70">
                  <input
                    type="checkbox"
                    checked={aiAutoRerunNewsAi}
                    onChange={(e) => setAiAutoRerunNewsAi(e.target.checked)}
                  />
                  发布后自动触发 News AI 标注
                </label>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => handleAiGenerateFill(false)}
                    disabled={
                      aiGenerateMutation.isPending || createMutation.isPending
                    }
                  >
                    {aiGenerateMutation.isPending ? "生成中..." : "AI生成填充"}
                  </Button>
                  <Button
                    onClick={() => handleAiGenerateFill(true)}
                    disabled={
                      aiGenerateMutation.isPending || createMutation.isPending
                    }
                  >
                    {aiGenerateMutation.isPending
                      ? "生成中..."
                      : createMutation.isPending
                      ? "发布中..."
                      : "AI一键发布"}
                  </Button>
                </div>
              </div>
            </div>
          </div>

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

          {createForm.cover_image?.trim() ? (
            <div className="rounded-xl border border-slate-200/70 bg-white p-3 dark:border-white/10 dark:bg-white/5">
              <div className="text-xs text-slate-500 dark:text-white/40 mb-2">
                封面预览
              </div>
              <FadeInImage
                src={createForm.cover_image.trim()}
                alt="cover"
                wrapperClassName="w-full rounded-2xl bg-slate-900/5 dark:bg-white/5"
                className="h-48 w-full object-cover"
              />
            </div>
          ) : null}

          {createImages.length > 0 ? (
            <div className="rounded-xl border border-slate-200/70 bg-slate-50 p-3 dark:border-white/10 dark:bg-white/5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium text-slate-800 dark:text-white/80">
                  从正文图片选择封面
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setCreateForm((prev) => ({ ...prev, cover_image: "" }))
                  }
                  disabled={!createForm.cover_image.trim()}
                >
                  清空封面
                </Button>
              </div>
              <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
                {createImages.slice(0, 8).map((url) => {
                  const isSelected = createForm.cover_image.trim() === url;
                  return (
                    <button
                      key={url}
                      type="button"
                      onClick={() =>
                        setCreateForm((prev) => ({ ...prev, cover_image: url }))
                      }
                      className={`rounded-xl overflow-hidden border transition-all ${
                        isSelected
                          ? "border-amber-500/60 ring-2 ring-amber-500/30"
                          : "border-slate-200/70 hover:border-slate-300 dark:border-white/10 dark:hover:border-white/20"
                      }`}
                      title="设为封面"
                    >
                      <FadeInImage
                        src={url}
                        alt="img"
                        wrapperClassName="w-full bg-slate-900/5 dark:bg-white/5"
                        className="h-20 w-full object-cover"
                      />
                    </button>
                  );
                })}
              </div>
              {createImages.length > 8 ? (
                <div className="mt-2 text-xs text-slate-500 dark:text-white/40">
                  仅展示前 8 张图片
                </div>
              ) : null}
            </div>
          ) : null}
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
              发布模式
            </label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={createPublishMode}
              onChange={(e) => {
                const v = String(e.target.value || "publish") as
                  | "publish"
                  | "draft"
                  | "schedule";
                setCreatePublishMode(v);
                setCreateForm((prev) => ({
                  ...prev,
                  is_published: v === "publish",
                  scheduled_publish_at:
                    v === "schedule" ? prev.scheduled_publish_at : "",
                  scheduled_unpublish_at:
                    v === "schedule" ? prev.scheduled_unpublish_at : "",
                  review_status:
                    v === "publish" || v === "schedule"
                      ? "approved"
                      : prev.review_status,
                }));
              }}
            >
              <option value="publish">立即发布</option>
              <option value="draft">保存草稿</option>
              <option value="schedule">定时发布</option>
            </select>
          </div>
          {createPublishMode === "schedule" ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                  定时发布
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
          ) : null}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              内容
            </label>
            <div className="flex items-center justify-end gap-2 mb-2">
              <Button
                variant={createContentMode === "edit" ? "primary" : "outline"}
                size="sm"
                onClick={() => setCreateContentMode("edit")}
              >
                编辑
              </Button>
              <Button
                variant={
                  createContentMode === "preview" ? "primary" : "outline"
                }
                size="sm"
                onClick={() => setCreateContentMode("preview")}
                disabled={!createForm.content.trim()}
              >
                预览
              </Button>
            </div>

            {createContentMode === "edit" ? (
              <RichTextEditor
                value={createForm.content}
                onChange={(v) => {
                  setCreateForm((prev) => ({ ...prev, content: v }));
                  setCreateImages(extractMarkdownImageUrls(v));
                }}
                images={createImages}
                onImagesChange={setCreateImages}
                placeholder="请输入内容，支持 Markdown、表情、图片链接..."
                minHeight="260px"
              />
            ) : (
              <div className="rounded-2xl border border-slate-200/70 bg-white p-4 dark:border-white/10 dark:bg-white/5">
                <div className="text-xl font-bold text-slate-900 dark:text-white">
                  {createForm.title.trim() || "（无标题）"}
                </div>
                {createForm.summary.trim() ? (
                  <div className="mt-2 text-slate-600 dark:text-white/60">
                    {createForm.summary.trim()}
                  </div>
                ) : null}
                {createForm.cover_image.trim() ? (
                  <div className="mt-4">
                    <FadeInImage
                      src={createForm.cover_image.trim()}
                      alt="cover"
                      wrapperClassName="w-full rounded-2xl bg-slate-900/5 dark:bg-white/5"
                      className="h-56 w-full object-cover"
                    />
                  </div>
                ) : null}
                <MarkdownContent
                  content={createForm.content}
                  className="mt-4"
                />
              </div>
            )}
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
              {createPublishMode === "schedule"
                ? "创建定时发布"
                : createPublishMode === "draft"
                ? "保存草稿"
                : "发布"}
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
          setEditContentMode("edit");
          setShowVersionsModal(false);
          setShowLinkCheckModal(false);
          setShowWorkbenchModal(false);
          setLinkCheckResult(null);
          setLinkCheckRunId("");
          setWorkbenchOutput(null);
          setWorkbenchRaw("");
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
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowWorkbenchModal(true)}
              disabled={!editingId}
            >
              <Sparkles className="h-4 w-4" />
              <span className="ml-2">AI工作台</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowLinkCheckModal(true)}
              disabled={!editingId}
            >
              <Link2 className="h-4 w-4" />
              <span className="ml-2">链接检查</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowVersionsModal(true)}
              disabled={!editingId}
            >
              <History className="h-4 w-4" />
              <span className="ml-2">版本历史</span>
            </Button>
          </div>
          {editingAi?.summary ? (
            <div className="rounded-xl border border-slate-200/70 bg-white px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-white/70">
              {editingAi.summary}
            </div>
          ) : null}
          {editingAi?.duplicate_of_news_id != null ? (
            <div className="rounded-xl border border-slate-200/70 bg-white px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-white/70">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-slate-800 dark:text-white/80">
                  疑似重复
                </span>
                <Link
                  to={`/news/${editingAi.duplicate_of_news_id}`}
                  className="text-amber-600 hover:underline dark:text-amber-400"
                  target="_blank"
                  rel="noreferrer"
                >
                  查看 #{editingAi.duplicate_of_news_id}
                </Link>
              </div>
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

          {editForm.cover_image?.trim() ? (
            <div className="rounded-xl border border-slate-200/70 bg-white p-3 dark:border-white/10 dark:bg-white/5">
              <div className="text-xs text-slate-500 dark:text-white/40 mb-2">
                封面预览
              </div>
              <FadeInImage
                src={editForm.cover_image.trim()}
                alt="cover"
                wrapperClassName="w-full rounded-2xl bg-slate-900/5 dark:bg-white/5"
                className="h-48 w-full object-cover"
              />
            </div>
          ) : null}

          {editImages.length > 0 ? (
            <div className="rounded-xl border border-slate-200/70 bg-slate-50 p-3 dark:border-white/10 dark:bg-white/5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium text-slate-800 dark:text-white/80">
                  从正文图片选择封面
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setEditForm((prev) => ({ ...prev, cover_image: "" }))
                  }
                  disabled={!editForm.cover_image.trim()}
                >
                  清空封面
                </Button>
              </div>
              <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
                {editImages.slice(0, 8).map((url) => {
                  const isSelected = editForm.cover_image.trim() === url;
                  return (
                    <button
                      key={url}
                      type="button"
                      onClick={() =>
                        setEditForm((prev) => ({ ...prev, cover_image: url }))
                      }
                      className={`rounded-xl overflow-hidden border transition-all ${
                        isSelected
                          ? "border-amber-500/60 ring-2 ring-amber-500/30"
                          : "border-slate-200/70 hover:border-slate-300 dark:border-white/10 dark:hover:border-white/20"
                      }`}
                      title="设为封面"
                    >
                      <FadeInImage
                        src={url}
                        alt="img"
                        wrapperClassName="w-full bg-slate-900/5 dark:bg-white/5"
                        className="h-20 w-full object-cover"
                      />
                    </button>
                  );
                })}
              </div>
              {editImages.length > 8 ? (
                <div className="mt-2 text-xs text-slate-500 dark:text-white/40">
                  仅展示前 8 张图片
                </div>
              ) : null}
            </div>
          ) : null}
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
            <div className="flex items-center justify-end gap-2 mb-2">
              <Button
                variant={editContentMode === "edit" ? "primary" : "outline"}
                size="sm"
                onClick={() => setEditContentMode("edit")}
              >
                编辑
              </Button>
              <Button
                variant={editContentMode === "preview" ? "primary" : "outline"}
                size="sm"
                onClick={() => setEditContentMode("preview")}
                disabled={!editForm.content.trim()}
              >
                预览
              </Button>
            </div>

            {editContentMode === "edit" ? (
              <RichTextEditor
                value={editForm.content}
                onChange={(v) => {
                  setEditForm((prev) => ({ ...prev, content: v }));
                  setEditImages(extractMarkdownImageUrls(v));
                }}
                images={editImages}
                onImagesChange={setEditImages}
                placeholder="请输入内容，支持 Markdown、表情、图片链接..."
                minHeight="260px"
              />
            ) : (
              <div className="rounded-2xl border border-slate-200/70 bg-white p-4 dark:border-white/10 dark:bg-white/5">
                <div className="text-xl font-bold text-slate-900 dark:text-white">
                  {editForm.title.trim() || "（无标题）"}
                </div>
                {editForm.summary.trim() ? (
                  <div className="mt-2 text-slate-600 dark:text-white/60">
                    {editForm.summary.trim()}
                  </div>
                ) : null}
                {editForm.cover_image.trim() ? (
                  <div className="mt-4">
                    <FadeInImage
                      src={editForm.cover_image.trim()}
                      alt="cover"
                      wrapperClassName="w-full rounded-2xl bg-slate-900/5 dark:bg-white/5"
                      className="h-56 w-full object-cover"
                    />
                  </div>
                ) : null}
                <MarkdownContent content={editForm.content} className="mt-4" />
              </div>
            )}
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
