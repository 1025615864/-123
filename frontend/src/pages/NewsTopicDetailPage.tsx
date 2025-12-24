import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Calendar, Eye, Layers, Newspaper, Tag } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  Loading,
  EmptyState,
  Badge,
  Pagination,
  FadeInImage,
} from "../components/ui";
import PageHeader from "../components/PageHeader";
import api from "../api/client";
import { usePrefetchLimiter, useToast } from "../hooks";
import { useTheme } from "../contexts/ThemeContext";
import { getApiErrorMessage } from "../utils";
import { queryKeys } from "../queryKeys";

function upsertMetaTag(
  attr: "name" | "property",
  key: string,
  content: string
): () => void {
  const selector = `meta[${attr}="${key}"]`;
  const existing = document.head.querySelector(selector) as HTMLMetaElement | null;
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

function upsertLinkRel(rel: string, href: string): () => void {
  const selector = `link[rel="${rel}"]`;
  const existing = document.head.querySelector(selector) as HTMLLinkElement | null;
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

interface NewsListItem {
  id: number;
  title: string;
  summary: string | null;
  category: string;
  cover_image: string | null;
  source: string | null;
  author: string | null;
  view_count: number;
  favorite_count: number;
  is_favorited: boolean;
  is_top: boolean;
  published_at: string | null;
  created_at: string;
}

interface NewsTopic {
  id: number;
  title: string;
  description: string | null;
  cover_image: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

interface TopicDetailResponse {
  topic: NewsTopic;
  items: NewsListItem[];
  total: number;
  page: number;
  page_size: number;
}

export default function NewsTopicDetailPage() {
  const { actualTheme } = useTheme();
  const toast = useToast();
  const { prefetch } = usePrefetchLimiter();
  const { topicId } = useParams<{ topicId: string }>();

  const [page, setPage] = useState(1);
  const pageSize = 18;

  useEffect(() => {
    setPage(1);
  }, [topicId]);

  const detailQuery = useQuery({
    queryKey: queryKeys.newsTopicDetail(topicId, page, pageSize),
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      const res = await api.get(`/news/topics/${topicId}?${params.toString()}`);
      return res.data as TopicDetailResponse;
    },
    enabled: !!topicId,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!detailQuery.error) return;
    toast.error(getApiErrorMessage(detailQuery.error));
  }, [detailQuery.error, toast]);

  const topic = detailQuery.data?.topic ?? null;
  const items = detailQuery.data?.items ?? [];
  const total = detailQuery.data?.total ?? 0;
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

  useEffect(() => {
    if (!topic) return;
    const prevTitle = document.title;
    const safeTitle = typeof topic.title === "string" ? topic.title : "专题";
    const safeDesc =
      typeof topic.description === "string" && topic.description.trim()
        ? topic.description.trim()
        : "法律资讯专题合集";
    const url = window.location.href;

    document.title = safeTitle ? `${safeTitle} - 专题 - 法律资讯` : prevTitle;

    const cleanups: Array<() => void> = [];
    cleanups.push(upsertMetaTag("name", "description", safeDesc));
    cleanups.push(upsertMetaTag("property", "og:title", safeTitle));
    cleanups.push(upsertMetaTag("property", "og:description", safeDesc));
    cleanups.push(upsertMetaTag("property", "og:type", "article"));
    cleanups.push(upsertMetaTag("property", "og:url", url));
    if (topic.cover_image) {
      cleanups.push(upsertMetaTag("property", "og:image", topic.cover_image));
    }
    cleanups.push(upsertLinkRel("canonical", url));

    return () => {
      document.title = prevTitle;
      for (const fn of cleanups) fn();
    };
  }, [topic]);

  const prefetchNewsDetail = (id: number) => {
    const newsId = String(id);
    prefetch({
      queryKey: queryKeys.newsDetail(newsId),
      queryFn: async () => {
        const res = await api.get(`/news/${newsId}`);
        return res.data;
      },
    });
  };

  if (detailQuery.isLoading && !topic) {
    return <Loading />;
  }

  return (
    <div className="space-y-10">
      <Card variant="surface" padding="md">
        <div className="mb-4">
          <Link
            to="/news/topics"
            className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 dark:text-white/60 dark:hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            返回专题
          </Link>
        </div>
        <PageHeader
          eyebrow="法律资讯"
          title={topic?.title ?? "专题"}
          description={topic?.description ?? ""}
          layout="mdCenter"
          tone={actualTheme}
        />
      </Card>

      {topic?.cover_image ? (
        <Card variant="surface" padding="none" className="overflow-hidden">
          <div className="aspect-[21/9] bg-slate-900/5 relative dark:bg-white/[0.03]">
            <FadeInImage
              src={topic.cover_image}
              alt={topic.title}
              wrapperClassName="w-full h-full"
              className="h-full w-full object-cover"
            />
          </div>
        </Card>
      ) : null}

      <div className="flex items-center gap-2">
        <Badge variant="primary" size="sm" icon={Layers}>
          专题合集
        </Badge>
      </div>

      {items.length === 0 ? (
        <EmptyState
          icon={Newspaper}
          title="暂无内容"
          description="该专题暂未配置新闻内容"
        />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {items.map((item, index) => (
            <Link
              key={item.id}
              to={`/news/${item.id}`}
              onMouseEnter={() => prefetchNewsDetail(item.id)}
              onFocus={() => prefetchNewsDetail(item.id)}
              className="block opacity-0 animate-fade-in"
              style={{
                animationDelay: `${Math.min(18, Math.max(0, index % 18)) * 35}ms`,
              }}
            >
              <Card
                variant="surface"
                hover
                padding="none"
                className="overflow-hidden"
              >
                <div className="aspect-[16/10] bg-slate-900/5 relative dark:bg-white/[0.03]">
                  {item.cover_image ? (
                    <FadeInImage
                      src={item.cover_image}
                      alt={item.title}
                      wrapperClassName="w-full h-full"
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Newspaper className="h-10 w-10 text-slate-400 dark:text-white/30" />
                    </div>
                  )}
                </div>

                <div className="p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <Badge variant="primary" size="sm" icon={Tag}>
                      {item.category}
                    </Badge>
                    {item.is_top ? (
                      <Badge variant="warning" size="sm">
                        置顶
                      </Badge>
                    ) : null}
                  </div>

                  <h3 className="text-base font-semibold text-slate-900 mb-2 line-clamp-2 leading-snug dark:text-white">
                    {item.title}
                  </h3>
                  <p className="text-slate-600 text-sm line-clamp-3 leading-relaxed dark:text-white/50">
                    {item.summary}
                  </p>

                  <div className="flex items-center justify-between text-xs text-slate-500 pt-4 mt-4 border-t border-slate-200/70 dark:text-white/55 dark:border-white/10">
                    <span className="flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                      {new Date(item.published_at || item.created_at).toLocaleDateString()}
                    </span>
                    <span className="flex items-center gap-2">
                      <Eye className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                      {item.view_count} 阅读
                    </span>
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {totalPages > 1 ? (
        <Pagination
          currentPage={page}
          totalPages={totalPages}
          onPageChange={(p) => setPage(p)}
        />
      ) : null}
    </div>
  );
}
