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
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Card, Input, Button, Badge } from "../../components/ui";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import { queryKeys } from "../../queryKeys";

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

export default function ForumManagePage() {
  const [activeView, setActiveView] = useState<
    "posts" | "moderation" | "words"
  >("posts");

  const toast = useToast();

  const [stats, setStats] = useState<ForumStats | null>(null);
  const [keyword, setKeyword] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [pendingComments, setPendingComments] = useState<PendingCommentItem[]>([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [pendingPage, setPendingPage] = useState(1);
  const pendingPageSize = 20;

  const [contentStats, setContentStats] = useState<ContentStats | null>(null);

  const [newSensitiveWord, setNewSensitiveWord] = useState("");
  const [newAdWord, setNewAdWord] = useState("");
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

  const postsQueryKey = useMemo(
    () => queryKeys.adminForumPosts(page, pageSize, keyword.trim(), selectedCategory),
    [page, pageSize, keyword, selectedCategory]
  );

  const postsQuery = useQuery({
    queryKey: postsQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("page_size", pageSize.toString());
      if (keyword) params.append("keyword", keyword);
      if (selectedCategory) params.append("category", selectedCategory);

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

  useEffect(() => {
    if (!pendingQuery.data) return;
    setPendingComments(pendingQuery.data.items);
    setPendingTotal(pendingQuery.data.total);
  }, [pendingQuery.data]);

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

  const sensitiveWords = wordsQuery.data?.sensitive_words ?? [];
  const adWords = wordsQuery.data?.ad_words ?? [];

  const wordsLoading = wordsQuery.isFetching;
  const pendingLoading = pendingQuery.isFetching;

  useEffect(() => {
    const err =
      statsQuery.error ||
      postsQuery.error ||
      pendingQuery.error ||
      contentStatsQuery.error ||
      wordsQuery.error;
    if (!err) return;
    toast.error(getApiErrorMessage(err));
  }, [contentStatsQuery.error, pendingQuery.error, postsQuery.error, statsQuery.error, toast, wordsQuery.error]);

  const reviewCommentMutation = useAppMutation<void, { commentId: number; action: "approve" | "reject" | "delete" }>({
    mutationFn: async (payload) => {
      await api.post(`/forum/admin/comments/${payload.commentId}/review`, { action: payload.action });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: async () => {
      await Promise.all([pendingQuery.refetch(), contentStatsQuery.refetch()]);
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

  const deletePostMutation = useAppMutation<void, number>({
    mutationFn: async (postId: number) => {
      await api.delete(`/forum/posts/${postId}`);
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [postsQueryKey as any, queryKeys.forumStats() as any],
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

  const handleReviewComment = async (
    commentId: number,
    action: "approve" | "reject" | "delete"
  ) => {
    if (reviewCommentMutation.isPending) return;
    reviewCommentMutation.mutate({ commentId, action });
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
    if (!confirm("确定要删除这个帖子吗？")) return;
    if (deletePostMutation.isPending) return;
    deletePostMutation.mutate(postId);
  };

  const handleUpdateHeatScores = async () => {
    if (updateHeatMutation.isPending) return;
    updateHeatMutation.mutate();
  };

  const categories = ["法律咨询", "经验分享", "案例讨论", "政策解读", "其他"];

  return (
    <div className="space-y-6">
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
          </div>

          {/* 表格 */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200/70 dark:border-white/10">
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
                    className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5"
                  >
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
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-2 text-red-400 hover:text-red-300"
                          onClick={() => handleDelete(item.id)}
                          title="删除"
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
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">评论审核</h2>
                <p className="text-slate-600 text-sm mt-1 dark:text-white/50">对评论执行通过/驳回/删除（用于人工审核队列）</p>
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  pendingQuery.refetch();
                  contentStatsQuery.refetch();
                }}
              >
                刷新
              </Button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200/70 dark:border-white/10">
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
                  敏感词/广告词管理
                </h2>
                <p className="text-slate-600 text-sm mt-1 dark:text-white/50">维护内容过滤词库</p>
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  wordsQuery.refetch();
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
