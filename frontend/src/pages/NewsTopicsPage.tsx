import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Layers, ArrowRight } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Card, Loading, EmptyState, Badge, FadeInImage } from "../components/ui";
import PageHeader from "../components/PageHeader";
import api from "../api/client";
import { useToast } from "../hooks";
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

interface NewsTopicListResponse {
  items: NewsTopic[];
}

export default function NewsTopicsPage() {
  const { actualTheme } = useTheme();
  const toast = useToast();

  useEffect(() => {
    const prevTitle = document.title;
    const title = "专题合集 - 法律资讯";
    const desc = "法律资讯专题合集列表";
    const url = window.location.href;

    document.title = title;
    const cleanups: Array<() => void> = [];
    cleanups.push(upsertMetaTag("name", "description", desc));
    cleanups.push(upsertMetaTag("property", "og:title", title));
    cleanups.push(upsertMetaTag("property", "og:description", desc));
    cleanups.push(upsertMetaTag("property", "og:type", "website"));
    cleanups.push(upsertMetaTag("property", "og:url", url));

    return () => {
      document.title = prevTitle;
      for (const fn of cleanups) fn();
    };
  }, []);

  const topicsQuery = useQuery({
    queryKey: queryKeys.newsTopics(),
    queryFn: async () => {
      const res = await api.get("/news/topics");
      return res.data as NewsTopicListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!topicsQuery.error) return;
    toast.error(getApiErrorMessage(topicsQuery.error));
  }, [topicsQuery.error, toast]);

  const topics = topicsQuery.data?.items ?? [];

  return (
    <div className="space-y-10">
      <Card variant="surface" padding="md">
        <PageHeader
          eyebrow="法律资讯"
          title="专题合集"
          description="聚合热点政策、典型案例与专题解读"
          layout="mdCenter"
          tone={actualTheme}
        />
      </Card>

      {topicsQuery.isLoading ? (
        <Loading />
      ) : topics.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="暂无专题"
          description="当前还没有可浏览的专题合集"
        />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {topics.map((t) => (
            <Link
              key={t.id}
              to={`/news/topics/${t.id}`}
              className="block"
            >
              <Card
                variant="surface"
                hover
                padding="none"
                className="overflow-hidden"
              >
                <div className="aspect-[16/9] bg-slate-900/5 relative dark:bg-white/[0.03]">
                  {t.cover_image ? (
                    <FadeInImage
                      src={t.cover_image}
                      alt={t.title}
                      wrapperClassName="w-full h-full"
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Layers className="h-10 w-10 text-slate-400 dark:text-white/30" />
                    </div>
                  )}
                </div>

                <div className="p-6">
                  <div className="flex items-center justify-between gap-4">
                    <h3 className="text-base font-semibold text-slate-900 dark:text-white line-clamp-1">
                      {t.title}
                    </h3>
                    <ArrowRight className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  </div>

                  {t.description ? (
                    <p className="mt-2 text-sm text-slate-600 dark:text-white/50 line-clamp-2">
                      {t.description}
                    </p>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500 dark:text-white/40">
                      暂无简介
                    </p>
                  )}

                  <div className="mt-4 flex items-center gap-2">
                    <Badge variant="primary" size="sm">
                      专题
                    </Badge>
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
