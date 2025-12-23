import { useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Calendar, Eye, Share2, Bookmark } from "lucide-react";
import { Card, Button, Loading, Badge, FadeInImage } from "../components/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { useToast } from "../hooks";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { getApiErrorMessage } from "../utils";
import { queryKeys } from "../queryKeys";
import MarkdownContent from "../components/MarkdownContent";

interface NewsDetail {
  id: number;
  title: string;
  summary: string;
  content: string;
  category: string;
  source: string;
  cover_image: string | null;
  view_count: number;
  favorite_count: number;
  is_favorited: boolean;
  published_at: string;
  created_at: string;
}

function stripMarkdown(input: string): string {
  return String(input || '')
    .replace(/!\[[^\]]*\]\([^)]+\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/[#>*_~|-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function upsertMetaTag(
  attr: 'name' | 'property',
  key: string,
  content: string
): () => void {
  const selector = `meta[${attr}="${key}"]`;
  const existing = document.head.querySelector(selector) as HTMLMetaElement | null;
  const created = !existing;
  const el = existing ?? document.createElement('meta');
  if (created) {
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  const prev = el.getAttribute('content');
  el.setAttribute('content', content);
  return () => {
    if (created) {
      el.remove();
      return;
    }
    if (prev == null) {
      el.removeAttribute('content');
    } else {
      el.setAttribute('content', prev);
    }
  };
}

function upsertLinkRel(rel: string, href: string): () => void {
  const selector = `link[rel="${rel}"]`;
  const existing = document.head.querySelector(selector) as HTMLLinkElement | null;
  const created = !existing;
  const el = existing ?? document.createElement('link');
  if (created) {
    el.rel = rel;
    document.head.appendChild(el);
  }
  const prevHref = el.getAttribute('href');
  el.setAttribute('href', href);
  return () => {
    if (created) {
      el.remove();
      return;
    }
    if (prevHref == null) {
      el.removeAttribute('href');
    } else {
      el.setAttribute('href', prevHref);
    }
  };
}

export default function NewsDetailPage() {
  const { newsId } = useParams<{ newsId: string }>();
  const { isAuthenticated } = useAuth();
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

  useEffect(() => {
    if (!news) return;

    const prevTitle = document.title;
    const safeTitle = typeof news.title === 'string' ? news.title : '';
    const safeSummary = typeof (news as any).summary === 'string' ? (news as any).summary : '';
    const safeContent = typeof news.content === 'string' ? news.content : '';

    document.title = safeTitle ? `${safeTitle} - 法律资讯` : prevTitle;

    const url = window.location.href;
    const description = (safeSummary.trim() || stripMarkdown(safeContent).slice(0, 140)).trim();
    const imageUrl = typeof news.cover_image === 'string' && news.cover_image ? news.cover_image : '';

    const cleanups: Array<() => void> = [];

    if (description) {
      cleanups.push(upsertMetaTag('name', 'description', description));
      cleanups.push(upsertMetaTag('property', 'og:description', description));
      cleanups.push(upsertMetaTag('name', 'twitter:description', description));
    }

    if (safeTitle) {
      cleanups.push(upsertMetaTag('property', 'og:title', safeTitle));
      cleanups.push(upsertMetaTag('name', 'twitter:title', safeTitle));
    }

    if (url) {
      cleanups.push(upsertMetaTag('property', 'og:url', url));
      cleanups.push(upsertLinkRel('canonical', url));
    }

    const card = imageUrl ? 'summary_large_image' : 'summary';
    cleanups.push(upsertMetaTag('name', 'twitter:card', card));

    if (imageUrl) {
      cleanups.push(upsertMetaTag('property', 'og:image', imageUrl));
      cleanups.push(upsertMetaTag('name', 'twitter:image', imageUrl));
    }

    cleanups.push(upsertMetaTag('property', 'og:type', 'article'));

    return () => {
      document.title = prevTitle;
      for (const fn of cleanups.reverse()) fn();
    };
  }, [newsId, news?.title, (news as any)?.summary, news?.content, news?.cover_image]);

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
      toast.success(res?.message || (res?.favorited ? "收藏成功" : "取消收藏"));
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

  if (newsQuery.isLoading) {
    return <Loading text="加载中..." tone={actualTheme} />;
  }

  if (!news) {
    return (
      <div className="text-center py-20">
        <p className="text-slate-600 dark:text-white/50">
          新闻不存在或已被删除
        </p>
        <Link
          to="/news"
          className="text-amber-600 hover:underline mt-4 inline-block dark:text-amber-400"
        >
          返回新闻列表
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* 返回按钮 */}
      <Link
        to="/news"
        className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors dark:text-white/60 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        返回新闻列表
      </Link>

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

        {/* 正文 */}
        <MarkdownContent content={news.content} className="text-base" />

        {/* 操作栏 */}
        <div className="flex items-center gap-4 mt-12 pt-8 border-t border-slate-200/70 dark:border-white/5">
          <Button
            variant={bookmarked ? "primary" : "outline"}
            onClick={handleBookmark}
            icon={Bookmark}
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
    </div>
  );
}
