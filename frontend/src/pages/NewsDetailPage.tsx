import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Calendar,
  Eye,
  Share2,
  Bookmark,
  MessageSquare,
  RefreshCw,
  Send,
  Trash2,
  User as UserIcon,
} from "lucide-react";
import {
  Card,
  Button,
  Badge,
  FadeInImage,
  EmptyState,
  Textarea,
  Pagination,
  Skeleton,
  ListSkeleton,
} from "../components/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { useToast } from "../hooks";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { getApiErrorMessage } from "../utils";
import { queryKeys } from "../queryKeys";
import MarkdownContent from "../components/MarkdownContent";

interface NewsAIAnnotation {
  summary: string | null;
  risk_level: string;
  sensitive_words: string[];
  highlights?: string[];
  keywords?: string[];
  duplicate_of_news_id: number | null;
  processed_at: string | null;
}

interface NewsDetail {
  id: number;
  title: string;
  summary: string | null;
  ai_annotation?: NewsAIAnnotation | null;
  content: string;
  category: string;
  source: string | null;
  author?: string | null;
  cover_image: string | null;
  view_count: number;
  favorite_count: number;
  is_favorited: boolean;
  published_at: string | null;
  created_at: string;
  updated_at?: string;
}

interface CommentAuthor {
  id: number;
  username: string;
  nickname?: string | null;
  avatar?: string | null;
}

interface NewsComment {
  id: number;
  news_id: number;
  user_id: number;
  content: string;
  review_status?: string | null;
  review_reason?: string | null;
  created_at: string;
  author?: CommentAuthor | null;
}

interface NewsCommentListResponse {
  items: NewsComment[];
  total: number;
  page: number;
  page_size: number;
}

interface RelatedNewsItem {
  id: number;
  title: string;
  summary: string | null;
  cover_image: string | null;
  category: string;
  source: string | null;
  author: string | null;
  view_count: number;
  favorite_count: number;
  is_favorited: boolean;
  is_top: boolean;
  published_at: string | null;
  created_at: string;
}

function stripMarkdown(input: string): string {
  return String(input || "")
    .replace(/!\[[^\]]*\]\([^)]+\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/[#>*_~|-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function upsertMetaTag(
  attr: "name" | "property",
  key: string,
  content: string
): () => void {
  const selector = `meta[${attr}="${key}"]`;
  const existing = document.head.querySelector(
    selector
  ) as HTMLMetaElement | null;
  const created = !existing;
  const el = existing ?? document.createElement("meta");
  if (created) {
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  const prev = el.getAttribute("content");
  el.setAttribute("content", content);
  return () => {
    if (created) {
      el.remove();
      return;
    }
    if (prev == null) {
      el.removeAttribute("content");
    } else {
      el.setAttribute("content", prev);
    }
  };
}

function upsertJsonLd(id: string, json: unknown): () => void {
  const selector = `script#${id}[type="application/ld+json"]`;
  const existing = document.head.querySelector(
    selector
  ) as HTMLScriptElement | null;
  const created = !existing;
  const el = existing ?? document.createElement("script");
  if (created) {
    el.id = id;
    el.type = "application/ld+json";
    document.head.appendChild(el);
  }
  const prev = el.textContent;
  el.textContent = JSON.stringify(json);
  return () => {
    if (created) {
      el.remove();
      return;
    }
    el.textContent = prev ?? "";
  };
}

function upsertLinkRel(rel: string, href: string): () => void {
  const selector = `link[rel="${rel}"]`;
  const existing = document.head.querySelector(
    selector
  ) as HTMLLinkElement | null;
  const created = !existing;
  const el = existing ?? document.createElement("link");
  if (created) {
    el.rel = rel;
    document.head.appendChild(el);
  }
  const prevHref = el.getAttribute("href");
  el.setAttribute("href", href);
  return () => {
    if (created) {
      el.remove();
      return;
    }
    if (prevHref == null) {
      el.removeAttribute("href");
    } else {
      el.setAttribute("href", prevHref);
    }
  };
}

export default function NewsDetailPage() {
  const { newsId } = useParams<{ newsId: string }>();
  const { isAuthenticated, user } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();

  const queryClient = useQueryClient();

  const newsDetailQueryKey = queryKeys.newsDetail(newsId);

  const newsQuery = useQuery({
    queryKey: newsDetailQueryKey,
    queryFn: async () => {
      const res = await api.get(`/news/${newsId}`);
      return res.data as NewsDetail;
    },
    enabled: !!newsId,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!newsQuery.error) return;
    toast.error(getApiErrorMessage(newsQuery.error));
  }, [newsQuery.error, toast]);

  const news = newsQuery.data ?? null;
  const bookmarked = !!news?.is_favorited;
  const favoriteCount = Number(news?.favorite_count || 0);
  const ai = news?.ai_annotation ?? null;
  const risk = String(ai?.risk_level ?? "").trim().toLowerCase();
  const riskVariant: "default" | "success" | "warning" | "danger" =
    risk === "safe"
      ? "success"
      : risk === "danger"
        ? "danger"
        : risk === "warning"
          ? "warning"
          : "default";
  const riskLabel =
    risk === "safe"
      ? "安全"
      : risk === "danger"
        ? "敏感"
        : risk === "warning"
          ? "注意"
          : "未知";

  const aiHighlights = Array.isArray(ai?.highlights) ? ai!.highlights! : [];
  const aiKeywords = Array.isArray(ai?.keywords) ? ai!.keywords! : [];
  const aiSensitive = Array.isArray(ai?.sensitive_words) ? ai!.sensitive_words : [];
  const aiPending =
    !ai ||
    !ai.processed_at ||
    (!ai.summary && !news?.summary && aiHighlights.length === 0 && aiKeywords.length === 0);

  const relatedLimit = 6;
  const relatedQuery = useQuery({
    queryKey: queryKeys.newsRelated(newsId, relatedLimit),
    queryFn: async () => {
      const res = await api.get(
        `/news/${newsId}/related?limit=${relatedLimit}`
      );
      return (Array.isArray(res.data) ? res.data : []) as RelatedNewsItem[];
    },
    enabled: !!newsId,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const [commentDraft, setCommentDraft] = useState("");
  const [commentPage, setCommentPage] = useState(1);
  const commentPageSize = 20;
  const [pendingDeleteCommentIds, setPendingDeleteCommentIds] = useState<Record<number, boolean>>({});

  useEffect(() => {
    setCommentPage(1);
  }, [newsId]);

  const commentsQuery = useQuery({
    queryKey: queryKeys.newsComments(newsId, commentPage, commentPageSize),
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(commentPage));
      params.set("page_size", String(commentPageSize));
      const res = await api.get(
        `/news/${newsId}/comments?${params.toString()}`
      );
      return res.data as NewsCommentListResponse;
    },
    enabled: !!newsId,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!commentsQuery.error) return;
    toast.error(getApiErrorMessage(commentsQuery.error));
  }, [commentsQuery.error, toast]);

  const comments = commentsQuery.data?.items ?? [];
  const commentsTotal = commentsQuery.data?.total ?? 0;
  const commentTotalPages = useMemo(() => {
    return Math.max(1, Math.ceil(commentsTotal / commentPageSize));
  }, [commentsTotal, commentPageSize]);

  const submitCommentMutation = useMutation({
    mutationFn: async (content: string) => {
      const res = await api.post(`/news/${newsId}/comments`, { content });
      return res.data as NewsComment;
    },
    onMutate: async (content: string) => {
      if (!newsId) return { previous: undefined, previousCount: undefined };
      await queryClient.cancelQueries({ queryKey: queryKeys.newsCommentsRoot(newsId) });

      const key = queryKeys.newsComments(newsId, commentPage, commentPageSize);
      const previous = queryClient.getQueryData<NewsCommentListResponse>(key);

      const authorName =
        (user as any)?.nickname ||
        (user as any)?.username ||
        (user as any)?.email ||
        (user ? `用户${user.id}` : "匿名用户");

      const temp: NewsComment = {
        id: -Math.trunc(Date.now()),
        news_id: Number(newsId),
        user_id: Number(user?.id ?? 0),
        content: String(content ?? ""),
        review_status: "pending",
        review_reason: null,
        created_at: new Date().toISOString(),
        author: user
          ? {
              id: Number(user.id),
              username: String((user as any)?.username ?? authorName),
              nickname: (user as any)?.nickname,
              avatar: (user as any)?.avatar,
            }
          : undefined,
      };

      queryClient.setQueryData<NewsCommentListResponse>(key, (old) => {
        if (!old) {
          return {
            items: [temp],
            total: 1,
            page: commentPage,
            page_size: commentPageSize,
          };
        }
        const nextItems = [temp, ...(old.items ?? [])];
        return { ...old, items: nextItems, total: Number(old.total || 0) + 1 };
      });

      return { previous, key };
    },
    onSuccess: async (created) => {
      setCommentDraft("");
      await queryClient.invalidateQueries({
        queryKey: queryKeys.newsCommentsRoot(newsId),
      });
      const status = String(created?.review_status ?? "").toLowerCase();
      toast.success(status === "pending" ? "评论已提交，等待审核" : "评论已发布");
    },
    onError: (err, _vars, ctx) => {
      if (ctx && typeof ctx === "object") {
        const anyCtx = ctx as any;
        if (anyCtx.key && anyCtx.previous) {
          queryClient.setQueryData(anyCtx.key, anyCtx.previous);
        }
      }
      toast.error(getApiErrorMessage(err, "评论失败"));
    },
  });

  const deleteCommentMutation = useMutation({
    mutationFn: async (commentId: number) => {
      const res = await api.delete(`/news/comments/${commentId}`);
      return res.data;
    },
    onMutate: async (commentId: number) => {
      if (!newsId) return { previous: undefined, key: undefined };
      setPendingDeleteCommentIds((prev) => ({ ...prev, [commentId]: true }));
      await queryClient.cancelQueries({ queryKey: queryKeys.newsCommentsRoot(newsId) });
      const key = queryKeys.newsComments(newsId, commentPage, commentPageSize);
      const previous = queryClient.getQueryData<NewsCommentListResponse>(key);

      queryClient.setQueryData<NewsCommentListResponse>(key, (old) => {
        if (!old) return old as any;
        const nextItems = (old.items ?? []).filter((c) => c.id !== commentId);
        const nextTotal = Math.max(0, Number(old.total || 0) - 1);
        return { ...old, items: nextItems, total: nextTotal };
      });

      return { previous, key };
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.newsCommentsRoot(newsId),
      });
      toast.success("已删除");
    },
    onError: (err, _vars, ctx) => {
      setPendingDeleteCommentIds((prev) => {
        const next = { ...prev };
        if (_vars != null) delete next[Number(_vars)];
        return next;
      });
      if (ctx && typeof ctx === "object") {
        const anyCtx = ctx as any;
        if (anyCtx.key && anyCtx.previous) {
          queryClient.setQueryData(anyCtx.key, anyCtx.previous);
        }
      }
      toast.error(getApiErrorMessage(err, "删除失败"));
    },
    onSettled: (_data, _err, commentId) => {
      setPendingDeleteCommentIds((prev) => {
        const next = { ...prev };
        delete next[commentId];
        return next;
      });
    },
  });

  const canDeleteComment = (c: NewsComment): boolean => {
    if (!user) return false;
    if (
      user.role === "admin" ||
      user.role === "super_admin" ||
      user.role === "moderator"
    )
      return true;
    return Number(user.id) === Number(c.user_id);
  };

  useEffect(() => {
    if (!news) return;

    const prevTitle = document.title;
    const safeTitle = typeof news.title === "string" ? news.title : "";
    const safeSummary =
      typeof (news as any).summary === "string" ? (news as any).summary : "";
    const safeContent = typeof news.content === "string" ? news.content : "";

    document.title = safeTitle ? `${safeTitle} - 法律资讯` : prevTitle;

    const url = window.location.href;
    const description = (
      safeSummary.trim() || stripMarkdown(safeContent).slice(0, 140)
    ).trim();
    const imageUrl =
      typeof news.cover_image === "string" && news.cover_image
        ? news.cover_image
        : "";

    const cleanups: Array<() => void> = [];

    if (description) {
      cleanups.push(upsertMetaTag("name", "description", description));
      cleanups.push(upsertMetaTag("property", "og:description", description));
      cleanups.push(upsertMetaTag("name", "twitter:description", description));
    }

    if (safeTitle) {
      cleanups.push(upsertMetaTag("property", "og:title", safeTitle));
      cleanups.push(upsertMetaTag("name", "twitter:title", safeTitle));
    }

    if (url) {
      cleanups.push(upsertMetaTag("property", "og:url", url));
      cleanups.push(upsertLinkRel("canonical", url));
    }

    const card = imageUrl ? "summary_large_image" : "summary";
    cleanups.push(upsertMetaTag("name", "twitter:card", card));

    if (imageUrl) {
      cleanups.push(upsertMetaTag("property", "og:image", imageUrl));
      cleanups.push(upsertMetaTag("name", "twitter:image", imageUrl));
    }

    cleanups.push(upsertMetaTag("property", "og:type", "article"));

    try {
      const jsonLd: Record<string, unknown> = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        headline: safeTitle,
        articleSection:
          typeof news.category === "string" ? news.category : undefined,
        description: description || undefined,
        datePublished:
          (news as any).published_at || (news as any).created_at || undefined,
        dateModified:
          (news as any).updated_at ||
          (news as any).published_at ||
          (news as any).created_at ||
          undefined,
        mainEntityOfPage: url || undefined,
        image: imageUrl ? [imageUrl] : undefined,
        author:
          typeof (news as any).author === "string" && (news as any).author
            ? { "@type": "Person", name: (news as any).author }
            : undefined,
        publisher: {
          "@type": "Organization",
          name:
            typeof (news as any).source === "string" && (news as any).source
              ? (news as any).source
              : "法律资讯",
        },
      };
      for (const k of Object.keys(jsonLd)) {
        if (jsonLd[k] === undefined) delete jsonLd[k];
      }
      cleanups.push(upsertJsonLd("news-jsonld", jsonLd));
    } catch {
      // ignore
    }

    return () => {
      document.title = prevTitle;
      for (const fn of cleanups.reverse()) fn();
    };
  }, [
    newsId,
    news?.title,
    (news as any)?.summary,
    news?.content,
    news?.cover_image,
    (news as any)?.author,
    (news as any)?.category,
    (news as any)?.source,
    (news as any)?.published_at,
    (news as any)?.created_at,
    (news as any)?.updated_at,
  ]);

  const bookmarkMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/news/${newsId}/favorite`);
      return res.data as {
        favorited: boolean;
        favorite_count: number;
        message?: string;
      };
    },
    onMutate: async () => {
      if (!newsId) return { previous: undefined };
      await queryClient.cancelQueries({ queryKey: newsDetailQueryKey });
      const previous = queryClient.getQueryData<NewsDetail>(newsDetailQueryKey);

      queryClient.setQueryData<NewsDetail>(newsDetailQueryKey, (old) => {
        if (!old) return old as any;
        const nextFavorited = !old.is_favorited;
        const nextCount = Math.max(
          0,
          Number(old.favorite_count || 0) + (nextFavorited ? 1 : -1)
        );
        return {
          ...old,
          is_favorited: nextFavorited,
          favorite_count: nextCount,
        };
      });

      return { previous };
    },
    onSuccess: (res) => {
      if (!newsId) return;
      queryClient.setQueryData<NewsDetail>(newsDetailQueryKey, (old) => {
        if (!old) return old as any;
        return {
          ...old,
          is_favorited: !!res.favorited,
          favorite_count: Number(res.favorite_count || 0),
        };
      });

      const msg = res?.message || (res?.favorited ? "收藏成功" : "取消收藏");
      toast.showToast("success", msg, {
        durationMs: 7000,
        action: {
          label: "撤销",
          onClick: () => {
            bookmarkMutation.mutate();
          },
        },
      });
    },
    onError: (err, _vars, ctx) => {
      if (newsId && ctx?.previous)
        queryClient.setQueryData(newsDetailQueryKey, ctx.previous);
      toast.error(getApiErrorMessage(err, "操作失败"));
    },
  });

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({
        title: news?.title,
        url: window.location.href,
      });
    } else {
      navigator.clipboard.writeText(window.location.href);
      toast.success("链接已复制到剪贴板");
    }
  };

  const handleBookmark = async () => {
    if (!newsId) return;
    if (!isAuthenticated) {
      toast.error("请先登录后再收藏");
      return;
    }
    if (bookmarkMutation.isPending) return;
    bookmarkMutation.mutate();
  };

  const refreshingAll = newsQuery.isFetching || commentsQuery.isFetching || relatedQuery.isFetching;
  const handleRefreshAll = () => {
    if (!newsId) return;
    if (refreshingAll) return;
    void Promise.all([
      newsQuery.refetch(),
      commentsQuery.refetch(),
      relatedQuery.refetch(),
    ]);
  };

  if (newsQuery.isLoading) {
    return (
      <div className="max-w-3xl mx-auto space-y-8">
        <div className="flex items-center gap-2 text-slate-600 dark:text-white/60">
          <Skeleton width="120px" height="16px" />
        </div>

        <div className="aspect-video rounded-2xl overflow-hidden bg-slate-900/5 dark:bg-white/5">
          <Skeleton variant="rectangular" height="100%" animation="wave" />
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Skeleton width="64px" height="22px" />
            <Skeleton width="120px" height="14px" />
          </div>
          <Skeleton width="90%" height="34px" />
          <Skeleton width="55%" height="34px" />
          <div className="flex flex-wrap items-center gap-4">
            <Skeleton width="120px" height="14px" />
            <Skeleton width="120px" height="14px" />
            <Skeleton width="120px" height="14px" />
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200/70 bg-white p-6 dark:border-white/10 dark:bg-white/[0.02]">
          <div className="flex items-center justify-between gap-3 mb-3">
            <Skeleton width="100px" height="18px" />
            <Skeleton width="60px" height="22px" />
          </div>
          <div className="space-y-2">
            <Skeleton width="100%" height="16px" />
            <Skeleton width="92%" height="16px" />
            <Skeleton width="86%" height="16px" />
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200/70 bg-white p-6 dark:border-white/10 dark:bg-white/[0.02]">
          <div className="flex items-center justify-between mb-4">
            <Skeleton width="120px" height="18px" />
            <Skeleton width="80px" height="28px" />
          </div>
          <ListSkeleton count={3} />
        </div>
      </div>
    );
  }

  if (!news) {
    const err = newsQuery.isError
      ? getApiErrorMessage(newsQuery.error, "新闻信息加载失败，请稍后重试")
      : null;
    return (
      <EmptyState
        icon={UserIcon}
        title={err ? "加载失败" : "新闻不存在或已被删除"}
        description={err || "请返回新闻列表重新选择，或稍后再试"}
        tone={actualTheme}
        action={
          <div className="flex flex-col sm:flex-row gap-3">
            <Link to="/news">
              <Button variant="outline">返回新闻列表</Button>
            </Link>
            {err ? <Button onClick={handleRefreshAll}>重试</Button> : null}
          </div>
        }
      />
    );
  }

  const relatedItems = (relatedQuery.data ?? []).filter(
    (i) => String(i.id) !== String(newsId)
  );

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* 返回按钮 */}
      <div className="flex items-center justify-between gap-3">
        <Link
          to="/news"
          className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors dark:text-white/60 dark:hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          返回新闻列表
        </Link>

        <Button
          variant="outline"
          size="sm"
          icon={RefreshCw}
          isLoading={refreshingAll}
          loadingText="刷新中..."
          onClick={handleRefreshAll}
          disabled={refreshingAll}
        >
          刷新
        </Button>
      </div>

      {/* 新闻内容 */}
      <article>
        {/* 封面图 */}
        {news.cover_image && (
          <div className="aspect-video rounded-2xl overflow-hidden mb-8 bg-slate-900/5 dark:bg-white/5">
            <FadeInImage
              src={news.cover_image}
              alt={news.title}
              wrapperClassName="w-full h-full"
              className="h-full w-full object-cover"
            />
          </div>
        )}

        {/* 标题和元信息 */}
        <header className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Badge variant="primary" size="sm">
              {news.category}
            </Badge>
            <span className="text-slate-500 text-sm dark:text-white/40">
              {news.source}
            </span>
          </div>

          <h1 className="text-3xl md:text-4xl font-bold text-slate-900 leading-tight mb-6 dark:text-white">
            {news.title}
          </h1>

          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600 dark:text-white/50">
            <span className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4" />
              {new Date(
                news.published_at || news.created_at
              ).toLocaleDateString()}
            </span>
            <span className="flex items-center gap-1.5">
              <Eye className="h-4 w-4" />
              {news.view_count} 次阅读
            </span>
            <span className="flex items-center gap-1.5">
              <Bookmark className="h-4 w-4" />
              {favoriteCount} 收藏
            </span>
          </div>
        </header>

        {/* 摘要 */}
        {news.summary && (
          <Card variant="surface" padding="md" className="mb-8">
            <p className="text-slate-700 leading-relaxed italic dark:text-white/70">
              {news.summary}
            </p>
          </Card>
        )}

        <Card variant="surface" padding="md" className="mb-8">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">
              AI 标注
            </h2>
            <Badge variant={riskVariant} size="sm">
              {riskLabel}
            </Badge>
          </div>

          {aiPending ? (
            <div className="space-y-3">
              <p className="text-sm text-slate-600 dark:text-white/55">
                AI 标注生成中，稍后会自动更新。你也可以手动刷新。
              </p>
              <div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => newsQuery.refetch()}
                  disabled={newsQuery.isFetching}
                >
                  {newsQuery.isFetching ? "刷新中..." : "刷新 AI 标注"}
                </Button>
              </div>
            </div>
          ) : (
            <>
              {ai?.summary && !news.summary ? (
                <p className="text-slate-700 leading-relaxed dark:text-white/70">
                  {ai.summary}
                </p>
              ) : null}

              <div className="mt-3">
                <div className="text-sm font-medium text-slate-700 dark:text-white/70 mb-2">
                  要点
                </div>
                {aiHighlights.length > 0 ? (
                  <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700 dark:text-white/70">
                    {aiHighlights.map((h, idx) => (
                      <li key={`${idx}-${h}`}>{h}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-slate-600 dark:text-white/55">
                    暂无要点
                  </p>
                )}
              </div>

              <div className="mt-3">
                <div className="text-sm font-medium text-slate-700 dark:text-white/70 mb-2">
                  关键词
                </div>
                {aiKeywords.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {aiKeywords.map((k) => (
                      <Badge key={k} variant="info" size="sm">
                        {k}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-600 dark:text-white/55">
                    暂无关键词
                  </p>
                )}
              </div>

              <div className="mt-3 space-y-2 text-sm text-slate-600 dark:text-white/50">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-slate-700 dark:text-white/70">
                    敏感词
                  </span>
                  {aiSensitive.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {aiSensitive.map((w) => (
                        <Badge key={w} variant="warning" size="sm">
                          {w}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <span>无</span>
                  )}
                </div>

                {ai?.duplicate_of_news_id != null ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-700 dark:text-white/70">
                      疑似重复
                    </span>
                    <Link
                      to={`/news/${ai.duplicate_of_news_id}`}
                      className="text-amber-600 hover:underline dark:text-amber-400"
                    >
                      查看 #{ai.duplicate_of_news_id}
                    </Link>
                  </div>
                ) : null}

                {ai?.processed_at ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-700 dark:text-white/70">
                      处理时间
                    </span>
                    <span>{new Date(ai.processed_at).toLocaleString()}</span>
                  </div>
                ) : null}
              </div>
            </>
          )}
        </Card>

        {/* 正文 */}
        <MarkdownContent content={news.content} className="text-base" />

        {/* 操作栏 */}
        <div className="flex items-center gap-4 mt-12 pt-8 border-t border-slate-200/70 dark:border-white/5">
          <Button
            variant={bookmarked ? "primary" : "outline"}
            onClick={handleBookmark}
            icon={Bookmark}
            isLoading={bookmarkMutation.isPending}
            loadingText={bookmarked ? "收藏中..." : "取消中..."}
            className="flex-1 sm:flex-none"
          >
            {bookmarked ? "已收藏" : "收藏"}
          </Button>
          <Button
            variant="outline"
            onClick={handleShare}
            icon={Share2}
            className="flex-1 sm:flex-none"
          >
            分享
          </Button>
        </div>
      </article>

      <section data-testid="news-comments">
        <Card variant="surface" padding="md">
          <div className="flex items-center justify-between gap-3 mb-4">
            <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2 dark:text-white">
              <MessageSquare className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              评论
              <span className="text-sm font-normal text-slate-500 dark:text-white/40">
                ({commentsTotal})
              </span>
            </h2>

            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              isLoading={commentsQuery.isFetching}
              loadingText="刷新中..."
              onClick={() => commentsQuery.refetch()}
              disabled={commentsQuery.isFetching}
            >
              刷新
            </Button>
          </div>

          <div className="space-y-3">
            <Textarea
              value={commentDraft}
              onChange={(e) => setCommentDraft(e.target.value)}
              placeholder={
                isAuthenticated ? "写下你的看法..." : "登录后可发表评论"
              }
              rows={4}
              disabled={!isAuthenticated}
            />
            <div className="flex justify-end">
              <Button
                icon={Send}
                onClick={() => {
                  const content = commentDraft.trim();
                  if (!isAuthenticated) {
                    toast.error("请先登录后再评论");
                    return;
                  }
                  if (!content) {
                    toast.error("请输入评论内容");
                    return;
                  }
                  if (submitCommentMutation.isPending) return;
                  submitCommentMutation.mutate(content);
                }}
                disabled={!isAuthenticated || submitCommentMutation.isPending}
                isLoading={submitCommentMutation.isPending}
                loadingText="发布中..."
              >
                发布评论
              </Button>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            {commentsQuery.isLoading ? (
              <ListSkeleton count={3} />
            ) : comments.length === 0 ? (
              <p className="text-sm text-slate-600 dark:text-white/50">
                暂无评论
              </p>
            ) : (
              <div className="space-y-4">
                {comments.map((c) => {
                  const name =
                    (c.author?.nickname ?? "").trim() ||
                    (c.author?.username ?? "").trim() ||
                    `用户${c.user_id}`;
                  const reviewStatus = String(c.review_status ?? "").toLowerCase();
                  const canDelete = canDeleteComment(c) && Number(c.id) > 0;
                  const deleting = Boolean(pendingDeleteCommentIds[c.id]);
                  return (
                    <div
                      key={c.id}
                      className="rounded-xl border border-slate-200/70 p-4 dark:border-white/10"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 text-sm text-slate-700 dark:text-white/70">
                            <UserIcon className="h-4 w-4 opacity-70" />
                            <span className="font-medium text-slate-900 dark:text-white">
                              {name}
                            </span>
                            {reviewStatus === "pending" ? (
                              <Badge variant="warning" size="sm">
                                审核中
                              </Badge>
                            ) : null}
                            {reviewStatus === "rejected" ? (
                              <Badge
                                variant="danger"
                                size="sm"
                                title={c.review_reason || undefined}
                              >
                                已驳回
                              </Badge>
                            ) : null}
                            <span className="text-slate-400 dark:text-white/30">
                              ·
                            </span>
                            <span className="text-slate-500 dark:text-white/40">
                              {new Date(c.created_at).toLocaleString()}
                            </span>
                          </div>
                          <div className="mt-2 text-slate-800 whitespace-pre-wrap break-words dark:text-white/80">
                            {c.content}
                          </div>
                        </div>

                        {canDelete ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className={deleting ? "px-3 py-2" : "p-2"}
                            icon={Trash2}
                            onClick={() => {
                              if (deleting) return;
                              deleteCommentMutation.mutate(c.id);
                            }}
                            title="删除"
                            isLoading={deleting}
                            loadingText="删除中..."
                            disabled={deleting}
                          />
                        ) : null}
                      </div>
                    </div>
                  );
                })}

                <Pagination
                  currentPage={commentPage}
                  totalPages={commentTotalPages}
                  onPageChange={(p) => setCommentPage(p)}
                  className="pt-2"
                />
              </div>
            )}
          </div>
        </Card>
      </section>

      {relatedQuery.isLoading || relatedQuery.isSuccess ? (
        <section data-testid="news-related">
          <Card variant="surface" padding="md">
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                相关推荐
              </h2>
              <Link
                to="/news"
                className="text-sm text-amber-600 hover:underline dark:text-amber-400"
              >
                更多
              </Link>
            </div>

            {relatedQuery.isLoading ? (
              <ListSkeleton count={3} />
            ) : relatedItems.length === 0 ? (
              <p className="text-sm text-slate-600 dark:text-white/50">
                暂无相关推荐
              </p>
            ) : (
              <div className="space-y-3">
                {relatedItems.map((item) => (
                  <Link
                    key={item.id}
                    to={`/news/${item.id}`}
                    className="block rounded-xl border border-slate-200/70 p-4 hover:bg-slate-50 transition-colors dark:border-white/10 dark:hover:bg-white/5"
                  >
                    <div className="flex gap-4">
                      {item.cover_image ? (
                        <div className="w-24 h-16 rounded-lg overflow-hidden bg-slate-900/5 dark:bg-white/5 flex-shrink-0">
                          <FadeInImage
                            src={item.cover_image}
                            alt={item.title}
                            wrapperClassName="w-full h-full"
                            className="w-full h-full object-cover"
                          />
                        </div>
                      ) : null}

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant="primary" size="sm">
                            {item.category}
                          </Badge>
                          {item.is_top ? (
                            <Badge variant="warning" size="sm">
                              置顶
                            </Badge>
                          ) : null}
                        </div>

                        <div className="text-slate-900 font-medium line-clamp-2 leading-snug dark:text-white">
                          {item.title}
                        </div>

                        {item.summary ? (
                          <div className="text-sm text-slate-600 line-clamp-2 mt-1 dark:text-white/50">
                            {item.summary}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </section>
      ) : null}
    </div>
  );
}
