import { useMemo, useState, useEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Calendar,
  Eye,
  Tag,
  Search,
  Newspaper,
  TrendingUp,
  Bell,
  Layers,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  Input,
  Chip,
  Button,
  Badge,
  EmptyState,
  Pagination,
  NewsCardSkeleton,
  FadeInImage,
  LinkButton,
} from "../components/ui";
import PageHeader from "../components/PageHeader";
import api from "../api/client";
import { usePrefetchLimiter, useToast } from "../hooks";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { getApiErrorMessage } from "../utils";
import { queryKeys } from "../queryKeys";

interface CategoryCount {
  category: string;
  count: number;
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
  ai_risk_level?: string | null;
  ai_keywords?: string[] | null;
  is_top: boolean;
  published_at: string | null;
  created_at: string;
}

interface NewsListResponse {
  items: NewsListItem[];
  total: number;
  page: number;
  page_size: number;
}

function getRiskBadge(
  riskLevel: string | null | undefined
): { variant: "warning" | "danger"; label: string } | null {
  const r = String(riskLevel ?? "")
    .trim()
    .toLowerCase();
  if (r === "warning") return { variant: "warning", label: "注意" };
  if (r === "danger") return { variant: "danger", label: "敏感" };
  return null;
}

export default function NewsPage() {
  const { actualTheme } = useTheme();
  const { isAuthenticated } = useAuth();
  const toast = useToast();
  const { prefetch } = usePrefetchLimiter();
  const location = useLocation();
  const navigate = useNavigate();
  const lastSyncedSearchRef = useRef<string>("");

  const formatDateInput = (d: Date) => {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  };

  const [page, setPage] = useState(1);
  const pageSize = 18;
  const [category, setCategory] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [riskLevel, setRiskLevel] = useState<string>("all");
  const [sourceSite, setSourceSite] = useState<string>("");
  const [from, setFrom] = useState<string>("");
  const [to, setTo] = useState<string>("");
  const [mode, setMode] = useState<
    "all" | "recommended" | "favorites" | "history" | "subscribed"
  >("all");

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const rawMode = String(params.get("mode") ?? "").trim().toLowerCase();
    const rawCategory = params.get("category");
    const rawKeyword = params.get("keyword");
    const rawRiskLevel = params.get("risk_level");
    const rawSourceSite = params.get("source_site");
    const rawFrom = params.get("from");
    const rawTo = params.get("to");

    const allowedModes = new Set([
      "all",
      "recommended",
      "favorites",
      "history",
      "subscribed",
    ]);
    if (rawMode && allowedModes.has(rawMode)) {
      if (
        (rawMode === "favorites" || rawMode === "history" || rawMode === "subscribed") &&
        !isAuthenticated
      ) {
        setMode("all");
      } else {
        setMode(rawMode as typeof mode);
      }
    }

    if (rawCategory !== null) {
      const v = String(rawCategory ?? "").trim();
      setCategory(v ? v : null);
    }

    if (rawKeyword !== null) {
      setKeyword(String(rawKeyword ?? ""));
    }

    if (rawRiskLevel !== null) {
      const v = String(rawRiskLevel ?? "").trim().toLowerCase();
      const allowedRiskLevels = new Set([
        "all",
        "unknown",
        "safe",
        "warning",
        "danger",
      ]);
      setRiskLevel(allowedRiskLevels.has(v) ? v : "all");
    }

    if (rawSourceSite !== null) {
      setSourceSite(String(rawSourceSite ?? ""));
    }

    if (rawFrom !== null) {
      setFrom(String(rawFrom ?? ""));
    }

    if (rawTo !== null) {
      setTo(String(rawTo ?? ""));
    }
  }, [isAuthenticated, location.search]);

  const [hotDays, setHotDays] = useState<7 | 30>(7);
  const hotLimit = 6;

  const [debouncedKeyword, setDebouncedKeyword] = useState("");

  const hasActiveFilters =
    mode !== "all" ||
    Boolean(category) ||
    Boolean(String(keyword || "").trim()) ||
    (String(riskLevel || "").trim().toLowerCase() !== "all" &&
      Boolean(String(riskLevel || "").trim())) ||
    Boolean(String(sourceSite || "").trim()) ||
    Boolean(String(from || "").trim()) ||
    Boolean(String(to || "").trim());

  const clearFilters = () => {
    setMode("all");
    setCategory(null);
    setKeyword("");
    setRiskLevel("all");
    setSourceSite("");
    setFrom("");
    setTo("");
    setPage(1);
  };

  const applyQuickRange = (days: 7 | 30) => {
    const end = new Date();
    const start = new Date(end);
    start.setDate(end.getDate() - (days - 1));
    setFrom(formatDateInput(start));
    setTo(formatDateInput(end));
    setPage(1);
  };

  const nowForQuickRange = new Date();
  const todayStr = formatDateInput(nowForQuickRange);
  const start7Str = (() => {
    const start = new Date(nowForQuickRange);
    start.setDate(nowForQuickRange.getDate() - (7 - 1));
    return formatDateInput(start);
  })();
  const start30Str = (() => {
    const start = new Date(nowForQuickRange);
    start.setDate(nowForQuickRange.getDate() - (30 - 1));
    return formatDateInput(start);
  })();

  const quick7Active = String(from || "").trim() === start7Str && String(to || "").trim() === todayStr;
  const quick30Active =
    String(from || "").trim() === start30Str && String(to || "").trim() === todayStr;

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedKeyword(keyword), 250);
    return () => window.clearTimeout(t);
  }, [keyword]);

  useEffect(() => {
    setPage(1);
  }, [category, keyword, mode, riskLevel, sourceSite, from, to]);

  useEffect(() => {
    const params = new URLSearchParams();

    const safeMode =
      !isAuthenticated &&
      (mode === "favorites" || mode === "history" || mode === "subscribed")
        ? "all"
        : mode;

    if (safeMode && safeMode !== "all") params.set("mode", safeMode);
    if (category) params.set("category", category);

    const kw = String(keyword || "").trim();
    if (kw) params.set("keyword", kw);

    const rl = String(riskLevel || "").trim().toLowerCase();
    if (rl && rl !== "all") params.set("risk_level", rl);

    const ss = String(sourceSite || "").trim();
    if (ss) params.set("source_site", ss);

    const fromValue = String(from || "").trim();
    if (fromValue) params.set("from", fromValue);

    const toValue = String(to || "").trim();
    if (toValue) params.set("to", toValue);

    const nextSearch = params.toString();
    const currentSearch = location.search.startsWith("?")
      ? location.search.slice(1)
      : location.search;

    if (nextSearch === currentSearch) {
      lastSyncedSearchRef.current = nextSearch;
      return;
    }

    if (lastSyncedSearchRef.current === nextSearch) {
      return;
    }

    lastSyncedSearchRef.current = nextSearch;
    navigate(
      {
        pathname: location.pathname,
        search: nextSearch ? `?${nextSearch}` : "",
      },
      { replace: true }
    );
  }, [
    category,
    from,
    isAuthenticated,
    keyword,
    location.pathname,
    location.search,
    mode,
    navigate,
    riskLevel,
    sourceSite,
    to,
  ]);

  const categoriesQuery = useQuery({
    queryKey: queryKeys.newsCategories(),
    queryFn: async () => {
      try {
        const res = await api.get("/news/categories");
        return (Array.isArray(res.data) ? res.data : []) as CategoryCount[];
      } catch {
        return [] as CategoryCount[];
      }
    },
    staleTime: 30 * 60 * 1000,
  });

  const hotNewsQuery = useQuery({
    queryKey: queryKeys.newsHot(hotDays, hotLimit, category),
    queryFn: async () => {
      try {
        const params = new URLSearchParams();
        params.set("days", String(hotDays));
        params.set("limit", String(hotLimit));
        if (category) params.set("category", category);

        const res = await api.get(`/news/hot?${params.toString()}`);
        return (Array.isArray(res.data) ? res.data : []) as NewsListItem[];
      } catch {
        return [] as NewsListItem[];
      }
    },
    staleTime: 60 * 1000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const newsQuery = useQuery({
    queryKey:
      mode === "recommended"
        ? queryKeys.newsRecommendedList(
            page,
            pageSize,
            category,
            debouncedKeyword.trim(),
            riskLevel,
            sourceSite.trim(),
            from.trim(),
            to.trim()
          )
        : mode === "favorites"
        ? queryKeys.newsFavoritesList(
            page,
            pageSize,
            category,
            debouncedKeyword.trim(),
            riskLevel,
            sourceSite.trim(),
            from.trim(),
            to.trim()
          )
        : mode === "history"
        ? queryKeys.newsHistoryList(
            page,
            pageSize,
            category,
            debouncedKeyword.trim(),
            riskLevel,
            sourceSite.trim(),
            from.trim(),
            to.trim()
          )
        : mode === "subscribed"
        ? queryKeys.newsSubscribedList(
            page,
            pageSize,
            category,
            debouncedKeyword.trim(),
            riskLevel,
            sourceSite.trim(),
            from.trim(),
            to.trim()
          )
        : queryKeys.newsList(
            page,
            pageSize,
            category,
            debouncedKeyword.trim(),
            riskLevel,
            sourceSite.trim(),
            from.trim(),
            to.trim()
          ),
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      if (category) params.set("category", category);
      if (debouncedKeyword.trim())
        params.set("keyword", debouncedKeyword.trim());

      const rl = String(riskLevel || "").trim().toLowerCase();
      if (rl && rl !== "all") params.set("risk_level", rl);

      const ss = String(sourceSite || "").trim();
      if (ss) params.set("source_site", ss);

      const fromValue = String(from || "").trim();
      if (fromValue) params.set("from", fromValue);

      const toValue = String(to || "").trim();
      if (toValue) params.set("to", toValue);

      const endpoint =
        mode === "recommended"
          ? "/news/recommended"
          : mode === "favorites"
          ? "/news/favorites"
          : mode === "history"
          ? "/news/history"
          : mode === "subscribed"
          ? "/news/subscribed"
          : "/news";
      const res = await api.get(`${endpoint}?${params.toString()}`);
      return res.data as NewsListResponse;
    },
    enabled:
      mode === "favorites" || mode === "history" || mode === "subscribed"
        ? isAuthenticated
        : true,
    placeholderData: (prev) => prev,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!newsQuery.error) return;
    toast.error(getApiErrorMessage(newsQuery.error));
  }, [newsQuery.error, toast]);

  const displayCategories = useMemo(() => {
    const fromApi = (categoriesQuery.data ?? [])
      .map((c) => c.category)
      .filter(Boolean);
    const unique = Array.from(new Set(fromApi));
    return ["全部", ...unique];
  }, [categoriesQuery.data]);

  const news = newsQuery.data?.items ?? [];
  const total = newsQuery.data?.total ?? 0;

  if (newsQuery.isLoading && news.length === 0) {
    return (
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
        {Array.from({ length: 6 }).map((_, i) => (
          <NewsCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

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

  return (
    <div className="space-y-12">
      <Card variant="surface" padding="md">
        <PageHeader
          eyebrow="法律资讯"
          title="法律新闻"
          description="最新法律资讯、政策解读和案例分析"
          layout="mdCenter"
          tone={actualTheme}
          right={
            <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
              <div className="w-full md:w-80">
                <Input
                  icon={Search}
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="搜索标题或摘要"
                  className="py-2.5"
                />
              </div>
              <LinkButton
                to="/news/topics"
                variant="outline"
                className="rounded-full px-6 py-3 text-sm"
                icon={Layers}
              >
                专题
              </LinkButton>
              {isAuthenticated ? (
                <LinkButton
                  to="/news/subscriptions"
                  variant="outline"
                  className="rounded-full px-6 py-3 text-sm"
                  icon={Bell}
                >
                  我的订阅
                </LinkButton>
              ) : null}
            </div>
          }
        />

        <div className="mt-5 flex flex-wrap gap-2">
          <Chip
            key="__recommended"
            size="sm"
            active={mode === "recommended"}
            onClick={() =>
              setMode((prev) => (prev === "recommended" ? "all" : "recommended"))
            }
          >
            推荐
          </Chip>
          {isAuthenticated ? (
            <Chip
              key="__favorites"
              size="sm"
              active={mode === "favorites"}
              onClick={() =>
                setMode((prev) => (prev === "favorites" ? "all" : "favorites"))
              }
            >
              我的收藏
            </Chip>
          ) : null}
          {isAuthenticated ? (
            <Chip
              key="__history"
              size="sm"
              active={mode === "history"}
              onClick={() =>
                setMode((prev) => (prev === "history" ? "all" : "history"))
              }
            >
              最近浏览
            </Chip>
          ) : null}
          {isAuthenticated ? (
            <Chip
              key="__subscribed"
              size="sm"
              active={mode === "subscribed"}
              onClick={() =>
                setMode((prev) => (prev === "subscribed" ? "all" : "subscribed"))
              }
            >
              订阅内容
            </Chip>
          ) : null}
          {displayCategories.map((cat) => {
            const active = (cat === "全部" && !category) || cat === category;
            return (
              <Chip
                key={cat}
                size="sm"
                active={active}
                onClick={() => setCategory(cat === "全部" ? null : cat)}
              >
                {cat}
              </Chip>
            );
          })}
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-white/70 mb-2">
              AI 风险
            </label>
            <select
              value={riskLevel}
              onChange={(e) => setRiskLevel(e.target.value)}
              className="w-full px-4 py-3 rounded-lg border border-slate-200 bg-white text-slate-900 outline-none transition focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
            >
              <option value="all">全部</option>
              <option value="unknown">未知</option>
              <option value="safe">安全</option>
              <option value="warning">注意</option>
              <option value="danger">敏感</option>
            </select>
          </div>
          <Input
            label="来源站点"
            value={sourceSite}
            onChange={(e) => setSourceSite(e.target.value)}
            placeholder="例如：court.gov.cn"
          />
          <Input
            label="从"
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
          <Input
            label="到"
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>

        <div className="mt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant={quick7Active ? "secondary" : "outline"}
              size="sm"
              onClick={() => applyQuickRange(7)}
            >
              近 7 天
            </Button>
            <Button
              variant={quick30Active ? "secondary" : "outline"}
              size="sm"
              onClick={() => applyQuickRange(30)}
            >
              近 30 天
            </Button>
          </div>
          <Button
            variant="outline"
            disabled={!hasActiveFilters}
            onClick={clearFilters}
          >
            清空筛选
          </Button>
        </div>
      </Card>

      <section data-testid="news-hot">
        <Card variant="surface" padding="md">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                热门新闻
              </h2>
            </div>

            <div className="flex items-center gap-2">
              <Chip
                size="sm"
                active={hotDays === 7}
                onClick={() => setHotDays(7)}
              >
                近7天
              </Chip>
              <Chip
                size="sm"
                active={hotDays === 30}
                onClick={() => setHotDays(30)}
              >
                近30天
              </Chip>
            </div>
          </div>

          <div className="mt-4">
            {hotNewsQuery.isLoading ? (
              <div className="text-sm text-slate-600 dark:text-white/45">
                加载中...
              </div>
            ) : (hotNewsQuery.data ?? []).length === 0 ? (
              <div className="text-sm text-slate-600 dark:text-white/45">
                暂无热门新闻
              </div>
            ) : (
              <div className="divide-y divide-slate-200/70 dark:divide-white/10">
                {(hotNewsQuery.data ?? []).map((item, idx) => (
                  <Link
                    key={item.id}
                    to={`/news/${item.id}`}
                    onMouseEnter={() => prefetchNewsDetail(item.id)}
                    onFocus={() => prefetchNewsDetail(item.id)}
                    className="flex items-center gap-3 py-3 hover:bg-slate-50/60 px-2 -mx-2 rounded-xl transition-colors dark:hover:bg-white/5"
                  >
                    <div className="w-6 text-sm font-semibold text-amber-600 dark:text-amber-400">
                      {idx + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-slate-900 truncate dark:text-white">
                        {item.title}
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-white/55">
                        <Badge variant="primary" size="sm" icon={Tag}>
                          {item.category}
                        </Badge>
                        {getRiskBadge(item.ai_risk_level) ? (
                          <Badge
                            variant={getRiskBadge(item.ai_risk_level)!.variant}
                            size="sm"
                          >
                            {getRiskBadge(item.ai_risk_level)!.label}
                          </Badge>
                        ) : null}
                        {Array.isArray(item.ai_keywords) && item.ai_keywords.length > 0
                          ? item.ai_keywords.slice(0, 2).map((k, kIdx) => (
                              <Badge key={`${item.id}-hot-kw-${kIdx}`} variant="info" size="sm">
                                {k}
                              </Badge>
                            ))
                          : null}
                        {(() => {
                          const riskNorm = String(item.ai_risk_level ?? "")
                            .trim()
                            .toLowerCase();
                          const hasKw =
                            Array.isArray(item.ai_keywords) && item.ai_keywords.length > 0;
                          if (hasKw) return null;
                          if (!riskNorm || riskNorm === "unknown") {
                            return (
                              <Badge variant="default" size="sm">
                                AI生成中
                              </Badge>
                            );
                          }
                          return null;
                        })()}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-white/55">
                      <Eye className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                      {item.view_count}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </Card>
      </section>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
        {news.length === 0 ? (
          <EmptyState
            icon={Newspaper}
            title="暂无符合条件的新闻"
            description="试试切换分类或修改搜索关键词"
            className="col-span-full"
          />
        ) : (
          news.map((item, index) => (
            <Link
              key={item.id}
              to={`/news/${item.id}`}
              onMouseEnter={() => prefetchNewsDetail(item.id)}
              onFocus={() => prefetchNewsDetail(item.id)}
              className="block opacity-0 animate-fade-in"
              style={{
                animationDelay: `${
                  Math.min(18, Math.max(0, index % 18)) * 35
                }ms`,
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
                  <div className="flex flex-wrap items-center gap-2 mb-3">
                    <Badge variant="primary" size="sm" icon={Tag}>
                      {item.category}
                    </Badge>
                    {getRiskBadge(item.ai_risk_level) ? (
                      <Badge
                        variant={getRiskBadge(item.ai_risk_level)!.variant}
                        size="sm"
                      >
                        {getRiskBadge(item.ai_risk_level)!.label}
                      </Badge>
                    ) : null}
                    {item.is_top ? (
                      <Badge variant="warning" size="sm">
                        置顶
                      </Badge>
                    ) : null}
                    {Array.isArray(item.ai_keywords) && item.ai_keywords.length > 0
                      ? item.ai_keywords.slice(0, 3).map((k, kIdx) => (
                          <Badge key={`${item.id}-kw-${kIdx}`} variant="info" size="sm">
                            {k}
                          </Badge>
                        ))
                      : null}
                    {(() => {
                      const riskNorm = String(item.ai_risk_level ?? "")
                        .trim()
                        .toLowerCase();
                      const hasKw =
                        Array.isArray(item.ai_keywords) && item.ai_keywords.length > 0;
                      if (hasKw) return null;
                      if (!riskNorm || riskNorm === "unknown") {
                        return (
                          <Badge variant="default" size="sm">
                            AI生成中
                          </Badge>
                        );
                      }
                      return null;
                    })()}
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
                      {new Date(
                        item.published_at || item.created_at
                      ).toLocaleDateString()}
                    </span>
                    <span className="flex items-center gap-2">
                      <Eye className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                      {item.view_count} 阅读
                    </span>
                  </div>
                </div>
              </Card>
            </Link>
          ))
        )}
      </div>

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
