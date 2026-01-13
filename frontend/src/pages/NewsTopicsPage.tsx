import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Layers, ArrowRight, RefreshCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Card, Button, EmptyState, Badge, FadeInImage, ListSkeleton } from "../components/ui";
import PageHeader from "../components/PageHeader";
import api from "../api/client";
import { useToast } from "../hooks";
import { useTheme } from "../contexts/ThemeContext";
import { useLanguage } from "../contexts/LanguageContext";
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

function upsertJsonLd(id: string, json: unknown): () => void {
  const selector = `script#${id}[type="application/ld+json"]`;
  const existing = document.head.querySelector(selector) as HTMLScriptElement | null;
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
  const { t } = useLanguage();

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

  useEffect(() => {
    const prevTitle = document.title;
    const title = `${t("newsTopicsPage.title")} - ${t("nav.news")}`;
    const desc = t("newsTopicsPage.seoDescription");
    const url = window.location.href;
    const canonical = url;
    const heroImageUrl =
      topics.find((x) => typeof x.cover_image === "string" && x.cover_image)?.cover_image ??
      "";

    document.title = title;
    const cleanups: Array<() => void> = [];
    cleanups.push(upsertMetaTag("name", "description", desc));

    cleanups.push(upsertMetaTag("property", "og:title", title));
    cleanups.push(upsertMetaTag("property", "og:description", desc));
    cleanups.push(upsertMetaTag("property", "og:type", "website"));
    cleanups.push(upsertMetaTag("property", "og:url", canonical));

    cleanups.push(upsertMetaTag("name", "twitter:title", title));
    cleanups.push(upsertMetaTag("name", "twitter:description", desc));

    cleanups.push(upsertLinkRel("canonical", canonical));

    const card = heroImageUrl ? "summary_large_image" : "summary";
    cleanups.push(upsertMetaTag("name", "twitter:card", card));

    if (heroImageUrl) {
      cleanups.push(upsertMetaTag("property", "og:image", heroImageUrl));
      cleanups.push(upsertMetaTag("name", "twitter:image", heroImageUrl));
    }

    try {
      const origin = window.location.origin;
      const collectionJsonLd: Record<string, unknown> = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        name: title,
        description: desc,
        url: canonical,
        image: heroImageUrl || undefined,
        mainEntity: {
          "@type": "ItemList",
          itemListElement: topics.map((topic, idx) => ({
            "@type": "ListItem",
            position: idx + 1,
            item: {
              "@type": "Thing",
              name: topic.title,
              url: `${origin}/news/topics/${topic.id}`,
            },
          })),
        },
      };
      for (const k of Object.keys(collectionJsonLd)) {
        if (collectionJsonLd[k] === undefined) delete collectionJsonLd[k];
      }
      cleanups.push(upsertJsonLd("news-topics-jsonld", collectionJsonLd));

      const breadcrumbJsonLd: Record<string, unknown> = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: [
          {
            "@type": "ListItem",
            position: 1,
            name: t("nav.home"),
            item: `${origin}/`,
          },
          {
            "@type": "ListItem",
            position: 2,
            name: t("nav.news"),
            item: `${origin}/news`,
          },
          {
            "@type": "ListItem",
            position: 3,
            name: t("newsTopicsPage.title"),
            item: `${origin}/news/topics`,
          },
        ],
      };
      cleanups.push(upsertJsonLd("news-topics-breadcrumb-jsonld", breadcrumbJsonLd));
    } catch {
      // ignore
    }

    return () => {
      document.title = prevTitle;
      for (const fn of cleanups.reverse()) fn();
    };
  }, [t, topics]);

  return (
    <div className="space-y-10">
      <Card variant="surface" padding="md">
        <PageHeader
          eyebrow={t("newsPage.eyebrow")}
          title={t("newsTopicsPage.title")}
          description={t("newsTopicsPage.description")}
          layout="mdCenter"
          tone={actualTheme}
          right={
            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              isLoading={topicsQuery.isFetching}
              loadingText={t("newsPage.refreshing")}
              onClick={() => topicsQuery.refetch()}
              disabled={topicsQuery.isFetching}
            >
              {t("newsPage.refresh")}
            </Button>
          }
        />
      </Card>

      {topicsQuery.isLoading && topics.length === 0 ? (
        <ListSkeleton count={6} />
      ) : topics.length === 0 ? (
        <EmptyState
          icon={Layers}
          title={t("newsTopicsPage.emptyTitle")}
          description={t("newsTopicsPage.emptyDescription")}
        />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {topics.map((topic) => (
            <Link
              key={topic.id}
              to={`/news/topics/${topic.id}`}
              className="block"
            >
              <Card
                variant="surface"
                hover
                padding="none"
                className="overflow-hidden"
              >
                <div className="aspect-[16/9] bg-slate-900/5 relative dark:bg-white/[0.03]">
                  {topic.cover_image ? (
                    <FadeInImage
                      src={topic.cover_image}
                      alt={topic.title}
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
                      {topic.title}
                    </h3>
                    <ArrowRight className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  </div>

                  {topic.description ? (
                    <p className="mt-2 text-sm text-slate-600 dark:text-white/50 line-clamp-2">
                      {topic.description}
                    </p>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500 dark:text-white/40">
                      {t("newsTopicsPage.noDescription")}
                    </p>
                  )}

                  <div className="mt-4 flex items-center gap-2">
                    <Badge variant="primary" size="sm">
                      {t("newsTopicsPage.badgeTopic")}
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
