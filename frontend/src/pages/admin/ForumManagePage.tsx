import { useEffect, useMemo, useState } from "react";
import {
  Search,
  Trash2,
  Pin,
  Award,
  Flame,
  Eye,
  MessageSquare,
  ThumbsUp,
  BarChart3,
  RotateCcw,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Card, Input, Button, Badge, Modal, ModalActions, Textarea } from "../../components/ui";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import { queryKeys } from "../../queryKeys";

const REVIEW_REASON_TEMPLATES = [
  "广告引流",
  "辱骂/攻击",
  "涉政敏感",
  "涉嫌诈骗",
  "包含联系方式/链接",
  "灌水/无意义内容",
  "其他",
] as const;

interface Author {
  id: number;
  username: string;
  nickname?: string;
}

interface PostItem {
  id: number;
  title: string;
  category: string;
  user_id: number;
  author: Author | null;
  view_count: number;
  like_count: number;
  comment_count: number;
  heat_score: number;
  is_pinned: boolean;
  is_hot: boolean;
  is_essence: boolean;
  is_deleted: boolean;
  review_status?: string | null;
  review_reason?: string | null;
  created_at: string;
}

interface ForumStats {
  total_posts: number;
  total_views: number;
  total_likes: number;
  total_comments: number;
  hot_posts_count: number;
  essence_posts_count: number;
  category_stats: Array<{ category: string; count: number }>;
}

interface PendingCommentItem {
  id: number;
  content: string;
  user_id: number;
  username: string | null;
  post_id: number;
  post_title: string | null;
  created_at: string;
}

interface PendingPostItem {
  id: number;
  title: string;
  user_id: number;
  username: string | null;
  category: string | null;
  created_at: string;
  review_reason: string | null;
}

interface ContentStats {
  posts: {
    total: number;
    deleted: number;
    active: number;
  };
  comments: {
    total: number;
    deleted: number;
    active: number;
  };
  sensitive_words_count: number;
  ad_words_count: number;
}

type ForumReviewConfig = { comment_review_enabled: boolean };
type ForumPostReviewConfig = { post_review_enabled: boolean; post_review_mode: string };
type ForumContentFilterConfig = {
  sensitive_words: string[];
  ad_words: string[];
  ad_words_threshold: number;
  check_url: boolean;
  check_phone: boolean;
};

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

export default function ForumManagePage() {
  const [activeView, setActiveView] = useState<
    "posts" | "moderation" | "words"
  >("posts");

  const [postsTab, setPostsTab] = useState<"active" | "recycle">("active");

  const toast = useToast();

  const [stats, setStats] = useState<ForumStats | null>(null);
  const [keyword, setKeyword] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [activePage, setActivePage] = useState(1);
  const [recyclePage, setRecyclePage] = useState(1);
  const pageSize = 20;

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const [pendingComments, setPendingComments] = useState<PendingCommentItem[]>([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [pendingPage, setPendingPage] = useState(1);
  const pendingPageSize = 20;

  const [selectedPendingCommentIds, setSelectedPendingCommentIds] = useState<Set<number>>(new Set());

  const [pendingPosts, setPendingPosts] = useState<PendingPostItem[]>([]);
  const [pendingPostsTotal, setPendingPostsTotal] = useState(0);
  const [pendingPostsPage, setPendingPostsPage] = useState(1);
  const pendingPostsPageSize = 20;

  const [selectedPendingPostIds, setSelectedPendingPostIds] = useState<Set<number>>(new Set());

  const [reasonModalOpen, setReasonModalOpen] = useState(false);
  const [reasonTemplateDraft, setReasonTemplateDraft] = useState("");
  const [reasonDraft, setReasonDraft] = useState("");
  const [reasonModalTarget, setReasonModalTarget] = useState<
    | {
        kind: "post" | "comment";
        mode: "single" | "batch";
        action: "reject" | "delete";
        ids: number[];
      }
    | null
  >(null);

  const [postReviewModeDraft, setPostReviewModeDraft] = useState<"all" | "rule">("rule");

  const [contentStats, setContentStats] = useState<ContentStats | null>(null);

  const [newSensitiveWord, setNewSensitiveWord] = useState("");
  const [newAdWord, setNewAdWord] = useState("");

  const [adWordsThresholdDraft, setAdWordsThresholdDraft] = useState<number>(2);
  const [checkUrlDraft, setCheckUrlDraft] = useState(true);
  const [checkPhoneDraft, setCheckPhoneDraft] = useState(true);
  const statsQuery = useQuery({
    queryKey: queryKeys.forumStats(),
    queryFn: async () => {
      const res = await api.get("/forum/stats");
      return res.data as ForumStats;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!statsQuery.data) return;
    setStats(statsQuery.data);
  }, [statsQuery.data]);

  useEffect(() => {
    setActivePage(1);
    setRecyclePage(1);
  }, [keyword, selectedCategory]);

  useEffect(() => {
    setSelectedIds(new Set());
  }, [postsTab]);

  const deleted = postsTab === "recycle";
  const page = deleted ? recyclePage : activePage;
  const setPage = deleted ? setRecyclePage : setActivePage;

  const postsQueryKey = useMemo(
    () => queryKeys.adminForumPosts(page, pageSize, keyword.trim(), selectedCategory, deleted),
    [page, pageSize, keyword, selectedCategory, deleted]
  );

  const postsQuery = useQuery({
    queryKey: postsQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("page_size", pageSize.toString());
      if (keyword) params.append("keyword", keyword);
      if (selectedCategory) params.append("category", selectedCategory);
      params.append("deleted", String(deleted));

      const res = await api.get(`/forum/admin/posts?${params.toString()}`);
      const data = res.data;
      return {
        items: Array.isArray(data?.items)
          ? (data.items as PostItem[])
          : ([] as PostItem[]),
        total: Number(data?.total || 0),
      };
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const posts = postsQuery.data?.items ?? [];
  const total = postsQuery.data?.total ?? 0;
  const loading = postsQuery.isLoading;

  const pendingQueryKey = useMemo(
    () => queryKeys.adminForumPendingComments(pendingPage, pendingPageSize),
    [pendingPage, pendingPageSize]
  );

  const pendingQuery = useQuery({
    queryKey: pendingQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.append("page", pendingPage.toString());
      params.append("page_size", pendingPageSize.toString());
      const res = await api.get(`/forum/admin/pending-comments?${params.toString()}`);
      const data = res.data;
      return {
        items: Array.isArray(data?.items)
          ? (data.items as PendingCommentItem[])
          : ([] as PendingCommentItem[]),
        total: Number(data?.total || 0),
      };
    },
    enabled: activeView === "moderation",
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const reviewConfigQuery = useQuery({
    queryKey: ["forum-review-config"] as const,
    queryFn: async () => {
      const res = await api.get("/forum/admin/review-config");
      return res.data as ForumReviewConfig;
    },
    enabled: activeView === "moderation",
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const postReviewConfigQuery = useQuery({
    queryKey: queryKeys.adminForumPostReviewConfig(),
    queryFn: async () => {
      const res = await api.get("/forum/admin/post-review-config");
      return res.data as ForumPostReviewConfig;
    },
    enabled: activeView === "moderation",
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const pendingPostsQueryKey = useMemo(
    () => queryKeys.adminForumPendingPosts(pendingPostsPage, pendingPostsPageSize),
    [pendingPostsPage, pendingPostsPageSize]
  );

  const pendingPostsQuery = useQuery({
    queryKey: pendingPostsQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.append("page", pendingPostsPage.toString());
      params.append("page_size", pendingPostsPageSize.toString());
      const res = await api.get(`/forum/admin/pending-posts?${params.toString()}`);
      const data = res.data;
      return {
        items: Array.isArray(data?.items)
          ? (data.items as PendingPostItem[])
          : ([] as PendingPostItem[]),
        total: Number(data?.total || 0),
      };
    },
    enabled: activeView === "moderation",
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!pendingQuery.data) return;
    setPendingComments(pendingQuery.data.items);
    setPendingTotal(pendingQuery.data.total);
    setSelectedPendingCommentIds(new Set());
  }, [pendingQuery.data]);

  useEffect(() => {
    if (!pendingPostsQuery.data) return;
    setPendingPosts(pendingPostsQuery.data.items);
    setPendingPostsTotal(pendingPostsQuery.data.total);
    setSelectedPendingPostIds(new Set());
  }, [pendingPostsQuery.data]);

  useEffect(() => {
    if (!postReviewConfigQuery.data) return;
    const mode = (postReviewConfigQuery.data.post_review_mode || "rule").toLowerCase();
    setPostReviewModeDraft(mode === "all" ? "all" : "rule");
  }, [postReviewConfigQuery.data]);

  const contentStatsQuery = useQuery({
    queryKey: queryKeys.adminForumContentStats(),
    queryFn: async () => {
      const res = await api.get("/forum/admin/content-stats");
      return res.data as ContentStats;
    },
    enabled: activeView !== "posts",
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const contentFilterConfigQuery = useQuery({
    queryKey: queryKeys.adminForumContentFilterConfig(),
    queryFn: async () => {
      const res = await api.get("/forum/admin/content-filter-config");
      return res.data as ForumContentFilterConfig;
    },
    enabled: activeView === "words",
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (contentStatsQuery.isError) {
      setContentStats(null);
      return;
    }
    if (contentStatsQuery.data) {
      setContentStats(contentStatsQuery.data);
    }
  }, [contentStatsQuery.data, contentStatsQuery.isError]);

  const wordsQuery = useQuery({
    queryKey: queryKeys.adminForumWords(),
    queryFn: async () => {
      const res = await api.get("/forum/admin/sensitive-words");
      return res.data as { sensitive_words: string[]; ad_words: string[] };
    },
    enabled: activeView === "words",
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!contentFilterConfigQuery.data) return;
    setAdWordsThresholdDraft(
      Number(contentFilterConfigQuery.data.ad_words_threshold || 2)
    );
    setCheckUrlDraft(Boolean(contentFilterConfigQuery.data.check_url));
    setCheckPhoneDraft(Boolean(contentFilterConfigQuery.data.check_phone));
  }, [contentFilterConfigQuery.data]);

  const sensitiveWords = wordsQuery.data?.sensitive_words ?? [];
  const adWords = wordsQuery.data?.ad_words ?? [];

  const wordsLoading = wordsQuery.isFetching;
  const pendingLoading = pendingQuery.isFetching;

  useEffect(() => {
    const err =
      statsQuery.error ||
      postsQuery.error ||
      pendingQuery.error ||
      pendingPostsQuery.error ||
      contentStatsQuery.error ||
      wordsQuery.error ||
      reviewConfigQuery.error ||
      postReviewConfigQuery.error;
    if (!err) return;
    toast.error(getApiErrorMessage(err));
  }, [
    contentStatsQuery.error,
    pendingQuery.error,
    pendingPostsQuery.error,
    postsQuery.error,
    postReviewConfigQuery.error,
    reviewConfigQuery.error,
    statsQuery.error,
    toast,
    wordsQuery.error,
  ]);

  const commentReviewEnabled = reviewConfigQuery.data?.comment_review_enabled ?? true;
  const postReviewEnabled = postReviewConfigQuery.data?.post_review_enabled ?? false;

  const closeReasonModal = () => {
    setReasonModalOpen(false);
    setReasonModalTarget(null);
    setReasonTemplateDraft("");
    setReasonDraft("");
  };

  const openReasonModal = (target: {
    kind: "post" | "comment";
    mode: "single" | "batch";
    action: "reject" | "delete";
    ids: number[];
  }) => {
    setReasonModalTarget(target);
    setReasonTemplateDraft("");
    setReasonDraft("");
    setReasonModalOpen(true);
  };

  const updatePostReviewConfigMutation = useAppMutation<
    { message?: string; post_review_enabled: boolean; post_review_mode: string },
    { enabled: boolean; mode: "all" | "rule" }
  >({
    mutationFn: async (payload) => {
      const res = await api.put("/forum/admin/post-review-config", {
        post_review_enabled: payload.enabled,
        post_review_mode: payload.mode,
      });
      return res.data as { message?: string; post_review_enabled: boolean; post_review_mode: string };
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async (data) => {
      toast.success(data?.message || "已更新");
      await Promise.all([
        postReviewConfigQuery.refetch(),
        pendingPostsQuery.refetch(),
        contentStatsQuery.refetch(),
        statsQuery.refetch(),
      ]);
    },
  });

  const batchReviewPostsMutation = useAppMutation<
    BatchReviewResponse,
    { ids: number[]; action: "approve" | "reject" | "delete"; reason?: string | null }
  >({
    mutationFn: async (payload) => {
      const res = await api.post("/forum/admin/posts/review/batch", payload);
      return res.data as BatchReviewResponse;
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async (data) => {
      closeReasonModal();
      setSelectedPendingPostIds(new Set());
      if (data?.message) toast.success(data.message);
      await Promise.all([
        pendingPostsQuery.refetch(),
        contentStatsQuery.refetch(),
        statsQuery.refetch(),
        postsQuery.refetch(),
      ]);
    },
  });

  const reviewPostMutation = useAppMutation<
    void,
    { postId: number; action: "approve" | "reject" | "delete"; reason?: string | null }
  >({
    mutationFn: async (payload) => {
      await api.post(`/forum/admin/posts/${payload.postId}/review`, {
        action: payload.action,
        reason: payload.reason ?? null,
      });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async () => {
      closeReasonModal();
      await Promise.all([
        pendingPostsQuery.refetch(),
        contentStatsQuery.refetch(),
        statsQuery.refetch(),
        postsQuery.refetch(),
      ]);
    },
  });

  const batchReviewCommentsMutation = useAppMutation<
    BatchReviewResponse,
    { ids: number[]; action: "approve" | "reject" | "delete"; reason?: string | null }
  >({
    mutationFn: async (payload) => {
      const res = await api.post("/forum/admin/comments/review/batch", payload);
      return res.data as BatchReviewResponse;
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async (data) => {
      closeReasonModal();
      setSelectedPendingCommentIds(new Set());
      if (data?.message) toast.success(data.message);
      await Promise.all([
        pendingQuery.refetch(),
        contentStatsQuery.refetch(),
        statsQuery.refetch(),
        postsQuery.refetch(),
      ]);
    },
  });

  const reviewCommentMutation = useAppMutation<
    void,
    { commentId: number; action: "approve" | "reject" | "delete"; reason?: string | null }
  >({
    mutationFn: async (payload) => {
      await api.post(`/forum/admin/comments/${payload.commentId}/review`, {
        action: payload.action,
        reason: payload.reason ?? null,
      });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async () => {
      closeReasonModal();
      await Promise.all([
        pendingQuery.refetch(),
        contentStatsQuery.refetch(),
        statsQuery.refetch(),
        postsQuery.refetch(),
      ]);
    },
  });

  const handleConfirmReasonModal = () => {
    if (!reasonModalTarget) return;

    const reason = reasonDraft.trim() ? reasonDraft.trim() : null;

    if (reasonModalTarget.kind === "post") {
      if (reasonModalTarget.mode === "batch") {
        batchReviewPostsMutation.mutate({
          ids: reasonModalTarget.ids,
          action: reasonModalTarget.action,
          reason,
        });
        return;
      }

      reviewPostMutation.mutate({
        postId: reasonModalTarget.ids[0],
        action: reasonModalTarget.action,
        reason,
      });
      return;
    }

    if (reasonModalTarget.kind === "comment") {
      if (reasonModalTarget.mode === "batch") {
        batchReviewCommentsMutation.mutate({
          ids: reasonModalTarget.ids,
          action: reasonModalTarget.action,
          reason,
        });
        return;
      }

      reviewCommentMutation.mutate({
        commentId: reasonModalTarget.ids[0],
        action: reasonModalTarget.action,
        reason,
      });
    }
  };

  const handleReviewPost = async (postId: number, action: "approve" | "reject" | "delete") => {
    if (reviewPostMutation.isPending) return;

    if (action === "approve") {
      reviewPostMutation.mutate({ postId, action, reason: null });
      return;
    }

    openReasonModal({ kind: "post", mode: "single", action, ids: [postId] });
  };

  const handleBatchReviewPosts = async (action: "approve" | "reject" | "delete") => {
    if (batchReviewPostsMutation.isPending) return;
    const ids = Array.from(selectedPendingPostIds);
    if (ids.length === 0) return;

    if (action === "approve") {
      batchReviewPostsMutation.mutate({ ids, action, reason: null });
      return;
    }

    openReasonModal({ kind: "post", mode: "batch", action, ids });
  };

  const updateReviewConfigMutation = useAppMutation<
    { message?: string; comment_review_enabled: boolean },
    boolean
  >({
    mutationFn: async (enabled) => {
      const res = await api.put("/forum/admin/review-config", {
        comment_review_enabled: enabled,
      });
      return res.data as { message?: string; comment_review_enabled: boolean };
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async (data) => {
      toast.success(data?.message || "已更新");
      await Promise.all([
        reviewConfigQuery.refetch(),
        pendingQuery.refetch(),
        contentStatsQuery.refetch(),
        statsQuery.refetch(),
      ]);
    },
  });

  const pinMutation = useAppMutation<void, { postId: number; is_pinned: boolean }>({
    mutationFn: async (payload) => {
      await api.post(`/forum/admin/posts/${payload.postId}/pin`, { is_pinned: payload.is_pinned });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [postsQueryKey as any],
  });

  const hotMutation = useAppMutation<void, { postId: number; is_hot: boolean }>({
    mutationFn: async (payload) => {
      await api.post(`/forum/admin/posts/${payload.postId}/hot`, { is_hot: payload.is_hot });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [postsQueryKey as any, queryKeys.forumStats() as any],
  });

  const essenceMutation = useAppMutation<void, { postId: number; is_essence: boolean }>({
    mutationFn: async (payload) => {
      await api.post(`/forum/admin/posts/${payload.postId}/essence`, { is_essence: payload.is_essence });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [postsQueryKey as any, queryKeys.forumStats() as any],
  });

  const deletePostMutation = useAppMutation<{ message?: string }, number>({
    mutationFn: async (postId: number) => {
      const res = await api.delete(`/forum/posts/${postId}`);
      return res.data as { message?: string };
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [["admin-forum-posts"] as any, queryKeys.forumStats() as any],
    onSuccess: async (data) => {
      toast.success(data?.message || "删除成功");
    },
  });

  const purgePostMutation = useAppMutation<{ message?: string }, number>({
    mutationFn: async (postId: number) => {
      const res = await api.delete(`/forum/posts/${postId}/purge`);
      return res.data as { message?: string };
    },
    errorMessageFallback: "永久删除失败，请稍后重试",
    invalidateQueryKeys: [["admin-forum-posts"] as any, queryKeys.forumStats() as any],
    onSuccess: async (data) => {
      toast.success(data?.message || "已永久删除");
    },
  });

  const restorePostMutation = useAppMutation<{ message?: string }, number>({
    mutationFn: async (postId: number) => {
      const res = await api.post(`/forum/posts/${postId}/restore`);
      return res.data as { message?: string };
    },
    errorMessageFallback: "恢复失败，请稍后重试",
    invalidateQueryKeys: [["admin-forum-posts"] as any, queryKeys.forumStats() as any],
    onSuccess: async (data) => {
      toast.success(data?.message || "已恢复");
    },
  });

  type BatchFailedItem = { id: number; reason: string };

  const batchDeleteMutation = useAppMutation<
    { success_ids: number[]; failed: BatchFailedItem[] },
    { ids: number[] }
  >({
    mutationFn: async (payload) => {
      const res = await api.post("/forum/posts/batch/delete", payload);
      return res.data as { success_ids: number[]; failed: BatchFailedItem[] };
    },
    errorMessageFallback: "批量删除失败，请稍后重试",
    invalidateQueryKeys: [["admin-forum-posts"] as any, queryKeys.forumStats() as any],
    onSuccess: async (data) => {
      setSelectedIds(new Set());
      const ok = Array.isArray(data?.success_ids) ? data.success_ids.length : 0;
      const fail = Array.isArray(data?.failed) ? data.failed.length : 0;
      toast.success(`已删除 ${ok} 条`);
      if (fail > 0) toast.error(`失败 ${fail} 条`);
    },
  });

  const batchRestoreMutation = useAppMutation<
    { success_ids: number[]; failed: BatchFailedItem[] },
    { ids: number[] }
  >({
    mutationFn: async (payload) => {
      const res = await api.post("/forum/posts/batch/restore", payload);
      return res.data as { success_ids: number[]; failed: BatchFailedItem[] };
    },
    errorMessageFallback: "批量恢复失败，请稍后重试",
    invalidateQueryKeys: [["admin-forum-posts"] as any, queryKeys.forumStats() as any],
    onSuccess: async (data) => {
      setSelectedIds(new Set());
      const ok = Array.isArray(data?.success_ids) ? data.success_ids.length : 0;
      const fail = Array.isArray(data?.failed) ? data.failed.length : 0;
      toast.success(`已恢复 ${ok} 条`);
      if (fail > 0) toast.error(`失败 ${fail} 条`);
    },
  });

  const batchPurgeMutation = useAppMutation<
    { success_ids: number[]; failed: BatchFailedItem[] },
    { ids: number[] }
  >({
    mutationFn: async (payload) => {
      const res = await api.post("/forum/posts/batch/purge", payload);
      return res.data as { success_ids: number[]; failed: BatchFailedItem[] };
    },
    errorMessageFallback: "批量永久删除失败，请稍后重试",
    invalidateQueryKeys: [["admin-forum-posts"] as any, queryKeys.forumStats() as any],
    onSuccess: async (data) => {
      setSelectedIds(new Set());
      const ok = Array.isArray(data?.success_ids) ? data.success_ids.length : 0;
      const fail = Array.isArray(data?.failed) ? data.failed.length : 0;
      toast.success(`已永久删除 ${ok} 条`);
      if (fail > 0) toast.error(`失败 ${fail} 条`);
    },
  });

  const updateHeatMutation = useAppMutation<void, void>({
    mutationFn: async () => {
      await api.post("/forum/admin/update-heat-scores", {});
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [postsQueryKey as any],
  });

  const addSensitiveMutation = useAppMutation<void, string>({
    mutationFn: async (word) => {
      await api.post("/forum/admin/sensitive-words", { word });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async () => {
      setNewSensitiveWord("");
      await Promise.all([wordsQuery.refetch(), contentStatsQuery.refetch()]);
    },
  });

  const deleteSensitiveMutation = useAppMutation<void, string>({
    mutationFn: async (word) => {
      await api.delete(`/forum/admin/sensitive-words/${encodeURIComponent(word)}`);
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async () => {
      await Promise.all([wordsQuery.refetch(), contentStatsQuery.refetch()]);
    },
  });

  const addAdMutation = useAppMutation<void, string>({
    mutationFn: async (word) => {
      await api.post("/forum/admin/ad-words", { word });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async () => {
      setNewAdWord("");
      await Promise.all([wordsQuery.refetch(), contentStatsQuery.refetch()]);
    },
  });

  const deleteAdMutation = useAppMutation<void, string>({
    mutationFn: async (word) => {
      await api.delete(`/forum/admin/ad-words/${encodeURIComponent(word)}`);
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async () => {
      await Promise.all([wordsQuery.refetch(), contentStatsQuery.refetch()]);
    },
  });

  const updateContentFilterRulesMutation = useAppMutation<
    ForumContentFilterConfig,
    { ad_words_threshold: number; check_url: boolean; check_phone: boolean }
  >({
    mutationFn: async (payload) => {
      const res = await api.put("/forum/admin/content-filter-config", payload);
      return res.data as ForumContentFilterConfig;
    },
    successMessage: "规则已保存",
    errorMessageFallback: "保存失败，请稍后重试",
    onSuccess: async () => {
      await Promise.all([
        contentFilterConfigQuery.refetch(),
        wordsQuery.refetch(),
        contentStatsQuery.refetch(),
      ]);
    },
  });

  const handleReviewComment = async (
    commentId: number,
    action: "approve" | "reject" | "delete"
  ) => {
    if (reviewCommentMutation.isPending) return;

    if (action === "approve") {
      reviewCommentMutation.mutate({ commentId, action, reason: null });
      return;
    }

    openReasonModal({ kind: "comment", mode: "single", action, ids: [commentId] });
  };

  const handleBatchReviewComments = async (action: "approve" | "reject" | "delete") => {
    if (batchReviewCommentsMutation.isPending) return;
    const ids = Array.from(selectedPendingCommentIds);
    if (ids.length === 0) return;

    if (action === "approve") {
      batchReviewCommentsMutation.mutate({ ids, action, reason: null });
      return;
    }

    openReasonModal({ kind: "comment", mode: "batch", action, ids });
  };

  const handleAddSensitiveWord = async () => {
    const word = newSensitiveWord.trim();
    if (!word) return;
    if (addSensitiveMutation.isPending) return;
    addSensitiveMutation.mutate(word);
  };

  const handleDeleteSensitiveWord = async (word: string) => {
      if (!confirm(`确定要删除敏感词：${word} 吗？`)) return;
      if (deleteSensitiveMutation.isPending) return;
      deleteSensitiveMutation.mutate(word);
    };

  const handleAddAdWord = async () => {
    const word = newAdWord.trim();
    if (!word) return;
    if (addAdMutation.isPending) return;
    addAdMutation.mutate(word);
  };

  const handleDeleteAdWord = async (word: string) => {
      if (!confirm(`确定要删除广告词：${word} 吗？`)) return;
      if (deleteAdMutation.isPending) return;
      deleteAdMutation.mutate(word);
    };

  const handleSaveContentFilterRules = async () => {
    if (updateContentFilterRulesMutation.isPending) return;

    const threshold = Number(adWordsThresholdDraft);
    updateContentFilterRulesMutation.mutate({
      ad_words_threshold: Number.isFinite(threshold) && threshold > 0 ? threshold : 2,
      check_url: Boolean(checkUrlDraft),
      check_phone: Boolean(checkPhoneDraft),
    });
  };

  const handleTogglePin = async (postId: number, isPinned: boolean) => {
    if (pinMutation.isPending) return;
    pinMutation.mutate({ postId, is_pinned: !isPinned });
  };

  const handleToggleHot = async (postId: number, isHot: boolean) => {
    if (hotMutation.isPending) return;
    hotMutation.mutate({ postId, is_hot: !isHot });
  };

  const handleToggleEssence = async (postId: number, isEssence: boolean) => {
    if (essenceMutation.isPending) return;
    essenceMutation.mutate({ postId, is_essence: !isEssence });
  };

  const handleDelete = async (postId: number) => {
    if (!deleted) {
      if (!confirm("确定要删除这个帖子吗？")) return;
      if (deletePostMutation.isPending) return;
      deletePostMutation.mutate(postId);
      return;
    }

    if (!confirm("确定要永久删除这个帖子吗？（不可恢复）")) return;
    if (purgePostMutation.isPending) return;
    purgePostMutation.mutate(postId);
  };

  const handleRestore = async (postId: number) => {
    if (!confirm("确定要恢复这个帖子吗？")) return;
    if (restorePostMutation.isPending) return;
    restorePostMutation.mutate(postId);
  };

  const handleBatchDelete = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (!confirm(`确定要批量删除已选择的 ${ids.length} 条帖子吗？`)) return;
    if (batchDeleteMutation.isPending) return;
    batchDeleteMutation.mutate({ ids });
  };

  const handleBatchRestore = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (!confirm(`确定要批量恢复已选择的 ${ids.length} 条帖子吗？`)) return;
    if (batchRestoreMutation.isPending) return;
    batchRestoreMutation.mutate({ ids });
  };

  const handleBatchPurge = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (!confirm(`确定要批量永久删除已选择的 ${ids.length} 条帖子吗？（不可恢复）`)) return;
    if (batchPurgeMutation.isPending) return;
    batchPurgeMutation.mutate({ ids });
  };

  const handleUpdateHeatScores = async () => {
    if (updateHeatMutation.isPending) return;
    updateHeatMutation.mutate();
  };

  const categories = ["法律咨询", "经验分享", "案例讨论", "政策解读", "其他"];

  const reasonModalLoading =
    reviewPostMutation.isPending ||
    reviewCommentMutation.isPending ||
    batchReviewPostsMutation.isPending ||
    batchReviewCommentsMutation.isPending;

  const reasonModalTitle = reasonModalTarget
    ? `${reasonModalTarget.action === "delete" ? "删除" : "驳回"}${
        reasonModalTarget.kind === "post" ? "帖子" : "评论"
      }`
    : "";

  const reasonModalDescription = reasonModalTarget
    ? `将${reasonModalTarget.mode === "batch" ? "批量" : ""}${
        reasonModalTarget.action === "delete" ? "删除" : "驳回"
      } ${reasonModalTarget.ids.length} 条${reasonModalTarget.kind === "post" ? "帖子" : "评论"}`
    : "";

  return (
    <div className="space-y-6">
      <Modal
        isOpen={reasonModalOpen}
        onClose={() => {
          if (reasonModalLoading) return;
          closeReasonModal();
        }}
        title={reasonModalTitle}
        description={reasonModalDescription}
        size="md"
      >
        <div className="space-y-4">
          <div>
            <p className="text-sm text-slate-700 dark:text-white/70 mb-2">原因模板</p>
            <select
              value={reasonTemplateDraft}
              onChange={(e) => {
                const v = e.target.value;
                setReasonTemplateDraft(v);
                setReasonDraft(v);
              }}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              disabled={reasonModalLoading}
            >
              <option value="">请选择原因模板（可选）</option>
              {REVIEW_REASON_TEMPLATES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <Textarea
            label="原因说明（可选）"
            value={reasonDraft}
            onChange={(e) => setReasonDraft(e.target.value)}
            rows={4}
            placeholder="可填写更具体的原因..."
            disabled={reasonModalLoading}
          />

          <ModalActions>
            <Button
              variant="outline"
              onClick={() => {
                if (reasonModalLoading) return;
                closeReasonModal();
              }}
            >
              取消
            </Button>
            <Button
              variant={reasonModalTarget?.action === "delete" ? "danger" : "primary"}
              onClick={handleConfirmReasonModal}
              isLoading={reasonModalLoading}
              disabled={!reasonModalTarget}
            >
              确认
            </Button>
          </ModalActions>
        </div>
      </Modal>
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">论坛管理</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">管理社区帖子、设置热门和精华</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={activeView === "posts" ? "primary" : "outline"}
            onClick={() => setActiveView("posts")}
          >
            帖子管理
          </Button>
          <Button
            variant={activeView === "moderation" ? "primary" : "outline"}
            onClick={() => setActiveView("moderation")}
          >
            内容审核
          </Button>
          <Button
            variant={activeView === "words" ? "primary" : "outline"}
            onClick={() => setActiveView("words")}
          >
            词库管理
          </Button>
          <Button
            variant="outline"
            icon={BarChart3}
            onClick={handleUpdateHeatScores}
          >
            更新热度
          </Button>
        </div>
      </div>

      {/* 统计卡片 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <Card variant="surface" padding="md">
            <div className="text-center">
              <p className="text-slate-600 text-sm dark:text-white/50">总帖子</p>
              <p className="text-2xl font-bold text-slate-900 mt-1 dark:text-white">
                {stats.total_posts}
              </p>
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="text-center">
              <p className="text-slate-600 text-sm dark:text-white/50">总浏览</p>
              <p className="text-2xl font-bold text-slate-900 mt-1 dark:text-white">
                {stats.total_views.toLocaleString()}
              </p>
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="text-center">
              <p className="text-slate-600 text-sm dark:text-white/50">总点赞</p>
              <p className="text-2xl font-bold text-slate-900 mt-1 dark:text-white">
                {stats.total_likes.toLocaleString()}
              </p>
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="text-center">
              <p className="text-slate-600 text-sm dark:text-white/50">总评论</p>
              <p className="text-2xl font-bold text-slate-900 mt-1 dark:text-white">
                {stats.total_comments.toLocaleString()}
              </p>
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="text-center">
              <p className="text-slate-600 text-sm dark:text-white/50">热门帖</p>
              <p className="text-2xl font-bold text-orange-600 mt-1 dark:text-orange-400">
                {stats.hot_posts_count}
              </p>
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="text-center">
              <p className="text-slate-600 text-sm dark:text-white/50">精华帖</p>
              <p className="text-2xl font-bold text-green-600 mt-1 dark:text-green-400">
                {stats.essence_posts_count}
              </p>
            </div>
          </Card>
        </div>
      )}

      {activeView === "posts" && (
        <Card variant="surface" padding="md">
          <div className="flex flex-wrap gap-4 mb-6">
            <div className="flex items-center gap-2">
              <Button
                variant={postsTab === "active" ? "primary" : "outline"}
                size="sm"
                onClick={() => setPostsTab("active")}
              >
                存在的帖子
              </Button>
              <Button
                variant={postsTab === "recycle" ? "primary" : "outline"}
                size="sm"
                onClick={() => setPostsTab("recycle")}
              >
                回收站
              </Button>
            </div>

            <div className="flex-1 min-w-[200px] max-w-md">
              <Input
                icon={Search}
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="搜索帖子标题..."
              />
            </div>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-4 py-2 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            >
              <option value="">全部分类</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-600 dark:text-white/60">已选 {selectedIds.size} 条</span>

              {!deleted ? (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handleBatchDelete}
                  disabled={selectedIds.size === 0 || batchDeleteMutation.isPending}
                >
                  批量删除
                </Button>
              ) : (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    icon={RotateCcw}
                    onClick={handleBatchRestore}
                    disabled={selectedIds.size === 0 || batchRestoreMutation.isPending}
                  >
                    批量恢复
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={handleBatchPurge}
                    disabled={selectedIds.size === 0 || batchPurgeMutation.isPending}
                  >
                    批量永久删除
                  </Button>
                </>
              )}
            </div>
          </div>

          {/* 表格 */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200/70 dark:border-white/10">
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    <input
                      type="checkbox"
                      checked={posts.length > 0 && posts.every((x) => selectedIds.has(x.id))}
                      onChange={() => {
                        const ids = posts.map((x) => x.id);
                        setSelectedIds((prev) => {
                          const next = new Set(prev);
                          const all = ids.length > 0 && ids.every((id) => next.has(id));
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
                    作者
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    分类
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    数据
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    热度
                  </th>
                  <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    标签
                  </th>
                  <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                {posts.map((item) => (
                  <tr
                    key={item.id}
                    className={`border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5 ${
                      item.is_deleted ? "opacity-60" : ""
                    }`}
                  >
                    <td className="py-4 px-4">
                      <input
                        type="checkbox"
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
                      <p className="text-slate-500 text-xs mt-1 dark:text-white/40">
                        {new Date(item.created_at).toLocaleDateString()}
                      </p>
                    </td>
                    <td className="py-4 px-4 text-slate-700 text-sm dark:text-white/70">
                      {item.author?.nickname || item.author?.username || "匿名"}
                    </td>
                    <td className="py-4 px-4">
                      <Badge variant="info" size="sm">
                        {item.category}
                      </Badge>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-white/50">
                        <span className="flex items-center gap-1">
                          <Eye className="h-3.5 w-3.5" />
                          {item.view_count}
                        </span>
                        <span className="flex items-center gap-1">
                          <ThumbsUp className="h-3.5 w-3.5" />
                          {item.like_count}
                        </span>
                        <span className="flex items-center gap-1">
                          <MessageSquare className="h-3.5 w-3.5" />
                          {item.comment_count}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-orange-400 font-medium">
                        {item.heat_score.toFixed(0)}
                      </span>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-1">
                        {!item.is_deleted && item.review_status === "pending" && (
                          <Badge variant="warning" size="sm" title={item.review_reason || undefined}>
                            审核中
                          </Badge>
                        )}
                        {!item.is_deleted && item.review_status === "rejected" && (
                          <Badge variant="danger" size="sm" title={item.review_reason || undefined}>
                            已驳回
                          </Badge>
                        )}
                        {item.is_deleted && (
                          <Badge variant="default" size="sm">
                            已删除
                          </Badge>
                        )}
                        {item.is_pinned && (
                          <Badge variant="warning" size="sm">
                            置顶
                          </Badge>
                        )}
                        {item.is_hot && (
                          <Badge variant="danger" size="sm">
                            热门
                          </Badge>
                        )}
                        {item.is_essence && (
                          <Badge variant="success" size="sm">
                            精华
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center justify-end gap-1">
                        {!deleted ? (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className={`p-2 ${
                                item.is_pinned ? "text-amber-400" : ""
                              }`}
                              onClick={() =>
                                handleTogglePin(item.id, item.is_pinned)
                              }
                              title={item.is_pinned ? "取消置顶" : "置顶"}
                            >
                              <Pin className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className={`p-2 ${
                                item.is_hot ? "text-orange-400" : ""
                              }`}
                              onClick={() => handleToggleHot(item.id, item.is_hot)}
                              title={item.is_hot ? "取消热门" : "设为热门"}
                            >
                              <Flame className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className={`p-2 ${
                                item.is_essence ? "text-green-400" : ""
                              }`}
                              onClick={() =>
                                handleToggleEssence(item.id, item.is_essence)
                              }
                              title={item.is_essence ? "取消精华" : "设为精华"}
                            >
                              <Award className="h-4 w-4" />
                            </Button>
                          </>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-2"
                            onClick={() => handleRestore(item.id)}
                            title="恢复"
                            disabled={restorePostMutation.isPending}
                          >
                            <RotateCcw className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-2 text-red-400 hover:text-red-300"
                          onClick={() => {
                            handleDelete(item.id)
                          }}
                          title="删除"
                          disabled={deletePostMutation.isPending || purgePostMutation.isPending}
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

          {posts.length === 0 && !loading && (
            <div className="text-center py-12 text-slate-500 dark:text-white/40">暂无帖子</div>
          )}

          {/* 分页 */}
          {total > pageSize && (
            <div className="flex items-center justify-center gap-4 mt-6">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                上一页
              </Button>
              <span className="text-slate-600 text-sm dark:text-white/60">
                第 {page} / {Math.ceil(total / pageSize)} 页
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= Math.ceil(total / pageSize)}
              >
                下一页
              </Button>
            </div>
          )}
        </Card>
      )}

      {activeView === "moderation" && (
        <div className="space-y-6">
          {contentStats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card variant="surface" padding="md">
                <div className="text-center">
                  <p className="text-slate-600 text-sm dark:text-white/50">评论总数</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1 dark:text-white">
                    {contentStats.comments.total}
                  </p>
                </div>
              </Card>
              <Card variant="surface" padding="md">
                <div className="text-center">
                  <p className="text-slate-600 text-sm dark:text-white/50">已删除评论</p>
                  <p className="text-2xl font-bold text-red-400 mt-1">
                    {contentStats.comments.deleted}
                  </p>
                </div>
              </Card>
              <Card variant="surface" padding="md">
                <div className="text-center">
                  <p className="text-slate-600 text-sm dark:text-white/50">敏感词数量</p>
                  <p className="text-2xl font-bold text-amber-400 mt-1">
                    {contentStats.sensitive_words_count}
                  </p>
                </div>
              </Card>
              <Card variant="surface" padding="md">
                <div className="text-center">
                  <p className="text-slate-600 text-sm dark:text-white/50">广告词数量</p>
                  <p className="text-2xl font-bold text-orange-400 mt-1">
                    {contentStats.ad_words_count}
                  </p>
                </div>
              </Card>
            </div>
          )}

          <Card variant="surface" padding="md">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">帖子审核</h2>
                <p className="text-slate-600 text-sm mt-1 dark:text-white/50">
                  控制帖子发布是否进入待审核队列（支持全量审核/命中规则审核）
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={postReviewEnabled ? "success" : "warning"} size="sm">
                  {postReviewConfigQuery.isFetching
                    ? "审核状态读取中"
                    : postReviewEnabled
                    ? "审核已开启"
                    : "审核已关闭"}
                </Badge>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (updatePostReviewConfigMutation.isPending) return;
                    updatePostReviewConfigMutation.mutate({
                      enabled: !postReviewEnabled,
                      mode: postReviewModeDraft,
                    });
                  }}
                  disabled={postReviewConfigQuery.isFetching || updatePostReviewConfigMutation.isPending}
                >
                  {postReviewEnabled ? "关闭审核" : "开启审核"}
                </Button>

                <select
                  value={postReviewModeDraft}
                  onChange={(e) => {
                    const mode = (e.target.value || "rule") === "all" ? "all" : "rule";
                    setPostReviewModeDraft(mode);
                    if (!postReviewConfigQuery.isFetching && !updatePostReviewConfigMutation.isPending) {
                      updatePostReviewConfigMutation.mutate({ enabled: postReviewEnabled, mode });
                    }
                  }}
                  className="px-3 py-2 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
                  disabled={postReviewConfigQuery.isFetching || updatePostReviewConfigMutation.isPending}
                >
                  <option value="rule">命中规则审核</option>
                  <option value="all">全量审核</option>
                </select>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    pendingPostsQuery.refetch();
                    contentStatsQuery.refetch();
                    statsQuery.refetch();
                    postReviewConfigQuery.refetch();
                  }}
                >
                  刷新
                </Button>
              </div>
            </div>
          </Card>

          <Card variant="surface" padding="md">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">待审核帖子</h2>
                <p className="text-slate-600 text-sm mt-1 dark:text-white/50">对帖子执行通过/驳回/删除</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-600 dark:text-white/60">已选 {selectedPendingPostIds.size} 条</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBatchReviewPosts("approve")}
                  disabled={
                    selectedPendingPostIds.size === 0 ||
                    pendingPostsQuery.isFetching ||
                    batchReviewPostsMutation.isPending
                  }
                >
                  批量通过
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBatchReviewPosts("reject")}
                  disabled={
                    selectedPendingPostIds.size === 0 ||
                    pendingPostsQuery.isFetching ||
                    batchReviewPostsMutation.isPending
                  }
                >
                  批量驳回
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-400 hover:text-red-300"
                  onClick={() => handleBatchReviewPosts("delete")}
                  disabled={
                    selectedPendingPostIds.size === 0 ||
                    pendingPostsQuery.isFetching ||
                    batchReviewPostsMutation.isPending
                  }
                >
                  批量删除
                </Button>
                <span className="text-sm text-slate-600 dark:text-white/60">共 {pendingPostsTotal} 条</span>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200/70 dark:border-white/10">
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      <input
                        type="checkbox"
                        checked={
                          pendingPosts.length > 0 &&
                          pendingPosts.every((x) => selectedPendingPostIds.has(x.id))
                        }
                        onChange={() => {
                          const ids = pendingPosts.map((x) => x.id);
                          setSelectedPendingPostIds((prev) => {
                            const next = new Set(prev);
                            const all = ids.length > 0 && ids.every((id) => next.has(id));
                            if (all) ids.forEach((id) => next.delete(id));
                            else ids.forEach((id) => next.add(id));
                            return next;
                          });
                        }}
                      />
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">标题</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">用户</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">分类</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">原因</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">时间</th>
                    <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingPosts.map((p) => (
                    <tr
                      key={p.id}
                      className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5"
                    >
                      <td className="py-4 px-4">
                        <input
                          type="checkbox"
                          checked={selectedPendingPostIds.has(p.id)}
                          onChange={() => {
                            setSelectedPendingPostIds((prev) => {
                              const next = new Set(prev);
                              if (next.has(p.id)) next.delete(p.id);
                              else next.add(p.id);
                              return next;
                            });
                          }}
                        />
                      </td>
                      <td className="py-4 px-4">
                        <p className="text-slate-700 text-sm line-clamp-2 max-w-xl dark:text-white/80">{p.title}</p>
                        <p className="text-xs text-slate-500 mt-1 dark:text-white/40">ID: {p.id}</p>
                      </td>
                      <td className="py-4 px-4 text-slate-700 text-sm dark:text-white/70">{p.username || `用户#${p.user_id}`}</td>
                      <td className="py-4 px-4">
                        <Badge variant="info" size="sm">
                          {p.category || "-"}
                        </Badge>
                      </td>
                      <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                        {p.review_reason || "-"}
                      </td>
                      <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                        {new Date(p.created_at).toLocaleString()}
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleReviewPost(p.id, "approve")}
                            disabled={pendingPostsQuery.isFetching || reviewPostMutation.isPending}
                          >
                            通过
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleReviewPost(p.id, "reject")}
                            disabled={pendingPostsQuery.isFetching || reviewPostMutation.isPending}
                          >
                            驳回
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-400 hover:text-red-300"
                            onClick={() => handleReviewPost(p.id, "delete")}
                            disabled={pendingPostsQuery.isFetching || reviewPostMutation.isPending}
                          >
                            删除
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {pendingPosts.length === 0 && !pendingPostsQuery.isFetching && (
              <div className="text-center py-12 text-slate-500 dark:text-white/40">暂无待审核帖子</div>
            )}

            {pendingPostsTotal > pendingPostsPageSize && (
              <div className="flex items-center justify-center gap-4 mt-6">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPendingPostsPage((p) => Math.max(1, p - 1))}
                  disabled={pendingPostsPage <= 1}
                >
                  上一页
                </Button>
                <span className="text-slate-600 text-sm dark:text-white/60">
                  第 {pendingPostsPage} / {Math.ceil(pendingPostsTotal / pendingPostsPageSize)} 页
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPendingPostsPage((p) => p + 1)}
                  disabled={pendingPostsPage >= Math.ceil(pendingPostsTotal / pendingPostsPageSize)}
                >
                  下一页
                </Button>
              </div>
            )}
          </Card>

          <Card variant="surface" padding="md">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">评论审核</h2>
                <p className="text-slate-600 text-sm mt-1 dark:text-white/50">对评论执行通过/驳回/删除（用于人工审核队列）</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge
                  variant={commentReviewEnabled ? "success" : "warning"}
                  size="sm"
                >
                  {reviewConfigQuery.isFetching
                    ? "审核状态读取中"
                    : commentReviewEnabled
                    ? "审核已开启"
                    : "审核已关闭"}
                </Badge>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (updateReviewConfigMutation.isPending) return;
                    updateReviewConfigMutation.mutate(!commentReviewEnabled);
                  }}
                  disabled={reviewConfigQuery.isFetching || updateReviewConfigMutation.isPending}
                >
                  {commentReviewEnabled ? "关闭审核" : "开启审核"}
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    pendingQuery.refetch();
                    contentStatsQuery.refetch();
                    statsQuery.refetch();
                    reviewConfigQuery.refetch();
                  }}
                >
                  刷新
                </Button>
              </div>
            </div>

            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-600 dark:text-white/60">已选 {selectedPendingCommentIds.size} 条</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBatchReviewComments("approve")}
                  disabled={
                    selectedPendingCommentIds.size === 0 ||
                    pendingLoading ||
                    batchReviewCommentsMutation.isPending
                  }
                >
                  批量通过
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBatchReviewComments("reject")}
                  disabled={
                    selectedPendingCommentIds.size === 0 ||
                    pendingLoading ||
                    batchReviewCommentsMutation.isPending
                  }
                >
                  批量驳回
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-400 hover:text-red-300"
                  onClick={() => handleBatchReviewComments("delete")}
                  disabled={
                    selectedPendingCommentIds.size === 0 ||
                    pendingLoading ||
                    batchReviewCommentsMutation.isPending
                  }
                >
                  批量删除
                </Button>
              </div>
              <div className="text-sm text-slate-600 dark:text-white/60">共 {pendingTotal} 条</div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200/70 dark:border-white/10">
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      <input
                        type="checkbox"
                        checked={
                          pendingComments.length > 0 &&
                          pendingComments.every((x) => selectedPendingCommentIds.has(x.id))
                        }
                        onChange={() => {
                          const ids = pendingComments.map((x) => x.id);
                          setSelectedPendingCommentIds((prev) => {
                            const next = new Set(prev);
                            const all = ids.length > 0 && ids.every((id) => next.has(id));
                            if (all) ids.forEach((id) => next.delete(id));
                            else ids.forEach((id) => next.add(id));
                            return next;
                          });
                        }}
                      />
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      评论内容
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      用户
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      帖子
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      时间
                    </th>
                    <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {pendingComments.map((c) => (
                    <tr
                      key={c.id}
                      className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5"
                    >
                      <td className="py-4 px-4">
                        <input
                          type="checkbox"
                          checked={selectedPendingCommentIds.has(c.id)}
                          onChange={() => {
                            setSelectedPendingCommentIds((prev) => {
                              const next = new Set(prev);
                              if (next.has(c.id)) next.delete(c.id);
                              else next.add(c.id);
                              return next;
                            });
                          }}
                        />
                      </td>
                      <td className="py-4 px-4">
                        <p className="text-slate-700 text-sm line-clamp-2 max-w-xl dark:text-white/80">
                          {c.content}
                        </p>
                      </td>
                      <td className="py-4 px-4 text-slate-700 text-sm dark:text-white/70">
                        {c.username || `用户#${c.user_id}`}
                      </td>
                      <td className="py-4 px-4">
                        <p className="text-slate-700 text-sm truncate max-w-xs dark:text-white/70">
                          {c.post_title || `帖子#${c.post_id}`}
                        </p>
                      </td>
                      <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                        {new Date(c.created_at).toLocaleString()}
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleReviewComment(c.id, "approve")}
                            disabled={pendingLoading || reviewCommentMutation.isPending}
                          >
                            通过
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleReviewComment(c.id, "reject")}
                            disabled={pendingLoading || reviewCommentMutation.isPending}
                          >
                            驳回
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-400 hover:text-red-300"
                            onClick={() => handleReviewComment(c.id, "delete")}
                            disabled={pendingLoading || reviewCommentMutation.isPending}
                          >
                            删除
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {pendingComments.length === 0 && !pendingLoading && (
              <div className="text-center py-12 text-slate-500 dark:text-white/40">
                暂无待审核评论
              </div>
            )}

            {pendingTotal > pendingPageSize && (
              <div className="flex items-center justify-center gap-4 mt-6">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPendingPage((p) => Math.max(1, p - 1))}
                  disabled={pendingPage <= 1}
                >
                  上一页
                </Button>
                <span className="text-slate-600 text-sm dark:text-white/60">
                  第 {pendingPage} / {Math.ceil(pendingTotal / pendingPageSize)}{" "}
                  页
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPendingPage((p) => p + 1)}
                  disabled={
                    pendingPage >= Math.ceil(pendingTotal / pendingPageSize)
                  }
                >
                  下一页
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}

      {activeView === "words" && (
        <div className="space-y-6">
          {contentStats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card variant="surface" padding="md">
                <div className="text-center">
                  <p className="text-slate-600 text-sm dark:text-white/50">敏感词数量</p>
                  <p className="text-2xl font-bold text-amber-400 mt-1">
                    {contentStats.sensitive_words_count}
                  </p>
                </div>
              </Card>
              <Card variant="surface" padding="md">
                <div className="text-center">
                  <p className="text-slate-600 text-sm dark:text-white/50">广告词数量</p>
                  <p className="text-2xl font-bold text-orange-400 mt-1">
                    {contentStats.ad_words_count}
                  </p>
                </div>
              </Card>
              <Card variant="surface" padding="md">
                <div className="text-center">
                  <p className="text-slate-600 text-sm dark:text-white/50">帖子总数</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1 dark:text-white">
                    {contentStats.posts.total}
                  </p>
                </div>
              </Card>
              <Card variant="surface" padding="md">
                <div className="text-center">
                  <p className="text-slate-600 text-sm dark:text-white/50">评论总数</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1 dark:text-white">
                    {contentStats.comments.total}
                  </p>
                </div>
              </Card>
            </div>
          )}

          <Card variant="surface" padding="md">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                  命中规则审核 - 规则配置
                </h2>
                <p className="text-slate-600 text-sm mt-1 dark:text-white/50">
                  这些规则用于 mode=rule 下判断内容是否需要进入待审核队列
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => contentFilterConfigQuery.refetch()}
                  disabled={contentFilterConfigQuery.isFetching}
                >
                  刷新
                </Button>
                <Button
                  variant="primary"
                  onClick={handleSaveContentFilterRules}
                  disabled={
                    contentFilterConfigQuery.isFetching ||
                    updateContentFilterRulesMutation.isPending
                  }
                >
                  保存
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="space-y-2">
                <p className="text-slate-900 font-medium text-sm dark:text-white">
                  广告词命中阈值
                </p>
                <Input
                  type="number"
                  min={1}
                  value={Number.isFinite(adWordsThresholdDraft) ? adWordsThresholdDraft : 2}
                  onChange={(e) => setAdWordsThresholdDraft(Number(e.target.value))}
                  placeholder="例如：2"
                />
                <p className="text-slate-500 text-sm dark:text-white/40">
                  命中 ≥ 阈值 个广告词则判定“疑似广告”，进入待审核
                </p>
              </div>

              <div className="space-y-3">
                <p className="text-slate-900 font-medium text-sm dark:text-white">链接检测</p>
                <label className="flex items-center gap-2 text-slate-700 text-sm dark:text-white/70">
                  <input
                    type="checkbox"
                    checked={checkUrlDraft}
                    onChange={(e) => setCheckUrlDraft(e.target.checked)}
                    className="h-4 w-4"
                  />
                  检查 http/https 链接
                </label>
                <p className="text-slate-500 text-sm dark:text-white/40">
                  开启后，内容包含链接会进入待审核
                </p>
              </div>

              <div className="space-y-3">
                <p className="text-slate-900 font-medium text-sm dark:text-white">手机号检测</p>
                <label className="flex items-center gap-2 text-slate-700 text-sm dark:text-white/70">
                  <input
                    type="checkbox"
                    checked={checkPhoneDraft}
                    onChange={(e) => setCheckPhoneDraft(e.target.checked)}
                    className="h-4 w-4"
                  />
                  检查手机号
                </label>
                <p className="text-slate-500 text-sm dark:text-white/40">
                  开启后，内容包含手机号会进入待审核
                </p>
              </div>
            </div>
          </Card>

          <Card variant="surface" padding="md">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                  敏感词/广告词管理
                </h2>
                <p className="text-slate-600 text-sm mt-1 dark:text-white/50">维护内容过滤词库</p>
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  wordsQuery.refetch();
                  contentFilterConfigQuery.refetch();
                  contentStatsQuery.refetch();
                }}
                disabled={wordsLoading}
              >
                刷新
              </Button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-slate-900 font-medium dark:text-white">敏感词</h3>
                  <Badge variant="warning" size="sm">
                    {sensitiveWords.length}
                  </Badge>
                </div>
                <div className="flex gap-2">
                  <Input
                    value={newSensitiveWord}
                    onChange={(e) => setNewSensitiveWord(e.target.value)}
                    placeholder="添加敏感词..."
                  />
                  <Button
                    variant="outline"
                    onClick={handleAddSensitiveWord}
                    disabled={wordsLoading || addSensitiveMutation.isPending}
                  >
                    添加
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {sensitiveWords.map((w) => (
                    <span
                      key={w}
                      className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/5 border border-slate-200/70 text-slate-700 text-sm dark:bg-white/5 dark:border-white/10 dark:text-white/80"
                    >
                      {w}
                      <button
                        className="text-slate-400 hover:text-red-600 dark:text-white/40 dark:hover:text-red-300"
                        onClick={() => handleDeleteSensitiveWord(w)}
                        title="删除"
                        type="button"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  {sensitiveWords.length === 0 && !wordsLoading && (
                    <p className="text-slate-500 text-sm dark:text-white/40">暂无敏感词</p>
                  )}
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-slate-900 font-medium dark:text-white">广告词</h3>
                  <Badge variant="danger" size="sm">
                    {adWords.length}
                  </Badge>
                </div>
                <div className="flex gap-2">
                  <Input
                    value={newAdWord}
                    onChange={(e) => setNewAdWord(e.target.value)}
                    placeholder="添加广告词..."
                  />
                  <Button
                    variant="outline"
                    onClick={handleAddAdWord}
                    disabled={wordsLoading || addAdMutation.isPending}
                  >
                    添加
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {adWords.map((w) => (
                    <span
                      key={w}
                      className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/5 border border-slate-200/70 text-slate-700 text-sm dark:bg-white/5 dark:border-white/10 dark:text-white/80"
                    >
                      {w}
                      <button
                        className="text-slate-400 hover:text-red-600 dark:text-white/40 dark:hover:text-red-300"
                        onClick={() => handleDeleteAdWord(w)}
                        title="删除"
                        type="button"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  {adWords.length === 0 && !wordsLoading && (
                    <p className="text-slate-500 text-sm dark:text-white/40">暂无广告词</p>
                  )}
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
