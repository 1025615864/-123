import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Search, TrendingUp, Trash2, History, ArrowRight, Sparkles } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import PageHeader from "../components/PageHeader";
import {
  Card,
  Input,
  Button,
  Badge,
  EmptyState,
  Loading,
  VirtualWindowList,
} from "../components/ui";
import api from "../api/client";
import { useToast, useAppMutation } from "../hooks";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { getApiErrorMessage } from "../utils";
import { queryKeys } from "../queryKeys";
import { toolNavItems } from "../navigation";

interface SearchResultItemBase {
  id: number;
  type: string;
}

interface NewsResultItem extends SearchResultItemBase {
  type: "news";
  title: string;
  summary?: string | null;
  snippet?: string | null;
}

interface PostResultItem extends SearchResultItemBase {
  type: "post";
  title: string;
  content?: string | null;
}

interface LawFirmResultItem extends SearchResultItemBase {
  type: "lawfirm";
  name: string;
  address?: string | null;
}

interface LawyerResultItem extends SearchResultItemBase {
  type: "lawyer";
  name: string;
  specialties?: string | null;
}

interface KnowledgeResultItem extends SearchResultItemBase {
  type: "knowledge";
  title: string;
  category?: string | null;
}

interface SearchResults {
  news: NewsResultItem[];
  posts: PostResultItem[];
  lawfirms: LawFirmResultItem[];
  lawyers: LawyerResultItem[];
  knowledge: KnowledgeResultItem[];
}

interface HotKeyword {
  keyword: string;
  count: number;
}

export default function SearchPage() {
  const [urlParams, setUrlParams] = useSearchParams();
  const { isAuthenticated } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [q, setQ] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [suggestionsEnabled, setSuggestionsEnabled] = useState(true);

  useEffect(() => {
    if (submittedQuery.trim()) return;
    const initial = String(urlParams.get("q") ?? "").trim();
    if (!initial) return;
    setQ(initial);
    setSubmittedQuery(initial);
    setSuggestionsEnabled(false);
  }, [submittedQuery, urlParams]);

  const [debouncedQ, setDebouncedQ] = useState("");

  useEffect(() => {
    const kw = q.trim();
    if (!kw) {
      setDebouncedQ("");
      return;
    }
    const t = window.setTimeout(() => setDebouncedQ(kw), 250);
    return () => window.clearTimeout(t);
  }, [q]);

  const hotQuery = useQuery({
    queryKey: queryKeys.searchHot(10),
    queryFn: async () => {
      const res = await api.get("/search/hot?limit=10");
      const list = (res.data?.keywords ?? []) as HotKeyword[];
      return Array.isArray(list) ? list : [];
    },
    staleTime: 10 * 60 * 1000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const historyQuery = useQuery({
    queryKey: queryKeys.searchHistory(10),
    queryFn: async () => {
      const res = await api.get("/search/history?limit=10");
      const list = res.data?.history ?? [];
      return Array.isArray(list) ? (list as string[]) : ([] as string[]);
    },
    enabled: isAuthenticated,
    staleTime: 2 * 60 * 1000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const suggestionsQuery = useQuery({
    queryKey: queryKeys.searchSuggestions(debouncedQ, 5),
    queryFn: async () => {
      const res = await api.get(
        `/search/suggestions?q=${encodeURIComponent(debouncedQ)}&limit=5`
      );
      const list = res.data?.suggestions ?? [];
      return Array.isArray(list) ? (list as string[]) : ([] as string[]);
    },
    enabled: suggestionsEnabled && debouncedQ.length > 0,
    staleTime: 30 * 1000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const searchQuery = useQuery({
    queryKey: queryKeys.search(submittedQuery, 10),
    queryFn: async () => {
      const res = await api.get(
        `/search?q=${encodeURIComponent(submittedQuery)}&limit=10`
      );
      const data = res.data;
      return {
        news: Array.isArray(data?.news) ? (data.news as NewsResultItem[]) : [],
        posts: Array.isArray(data?.posts)
          ? (data.posts as PostResultItem[])
          : [],
        lawfirms: Array.isArray(data?.lawfirms)
          ? (data.lawfirms as LawFirmResultItem[])
          : [],
        lawyers: Array.isArray(data?.lawyers)
          ? (data.lawyers as LawyerResultItem[])
          : [],
        knowledge: Array.isArray(data?.knowledge)
          ? (data.knowledge as KnowledgeResultItem[])
          : [],
      } as SearchResults;
    },
    enabled: submittedQuery.trim().length >= 2,
    placeholderData: (prev) => prev,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const hasAnyResults = useMemo(() => {
    const results = searchQuery.data ?? null;
    if (!results) return false;
    return (
      results.news.length > 0 ||
      results.posts.length > 0 ||
      results.lawfirms.length > 0 ||
      results.lawyers.length > 0 ||
      results.knowledge.length > 0
    );
  }, [searchQuery.data]);

  useEffect(() => {
    if (!searchQuery.error) return;
    toast.error(getApiErrorMessage(searchQuery.error));
  }, [searchQuery.error, toast]);

  const clearHistoryMutation = useAppMutation({
    mutationFn: async (_: void) => {
      await api.delete("/search/history");
    },
    successMessage: "已清空搜索历史",
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [queryKeys.searchHistoryRoot()],
  });

  const clearHistory = useCallback(async () => {
    if (!isAuthenticated) {
      toast.error("请先登录");
      return;
    }
    clearHistoryMutation.mutate();
  }, [clearHistoryMutation, isAuthenticated, toast]);

  const performSearch = useCallback(
    async (keyword?: string) => {
      const query = (keyword ?? q).trim();
      if (query.length < 2) {
        toast.error("请输入至少 2 个字符");
        return;
      }

      setQ(query);
      setSuggestionsEnabled(false);
      setSubmittedQuery(query);
      setUrlParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("q", query);
        return next;
      });
      if (isAuthenticated) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.searchHistoryRoot(),
        });
      }
    },
    [isAuthenticated, q, queryClient, toast, setUrlParams]
  );

  const suggestions = suggestionsQuery.data ?? [];
  const hotKeywords = hotQuery.data ?? [];
  const history = isAuthenticated ? historyQuery.data ?? [] : [];
  const results = useMemo(() => {
    if (submittedQuery.trim().length < 2) return null;
    return searchQuery.data ?? null;
  }, [searchQuery.data, submittedQuery]);
  const searching = searchQuery.isFetching;

  const categoryCounts = useMemo(() => {
    if (!results) return null;
    const news = results.news.length;
    const posts = results.posts.length;
    const lawfirms = results.lawfirms.length;
    const lawyers = results.lawyers.length;
    const knowledge = results.knowledge.length;
    const total = news + posts + lawfirms + lawyers + knowledge;
    return { total, news, posts, lawfirms, lawyers, knowledge };
  }, [results]);

  const clearAllConditions = useCallback(() => {
    setQ("");
    setDebouncedQ("");
    setSubmittedQuery("");
    setSuggestionsEnabled(true);

    setUrlParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("q");
      return next;
    });

    queryClient.removeQueries({ queryKey: ["search"] });
  }, [queryClient, setUrlParams]);

  const escapeRegExp = useCallback((value: string) => {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }, []);

  const highlightText = useCallback(
    (text: string | null | undefined) => {
      const source = String(text ?? "");
      const kw = submittedQuery.trim();
      if (!source || !kw) return source;
      const parts = source.split(new RegExp(`(${escapeRegExp(kw)})`, "ig"));
      return parts.map((p, idx) => {
        const isHit = p.toLowerCase() === kw.toLowerCase();
        if (!isHit) return <span key={idx}>{p}</span>;
        return (
          <span
            key={idx}
            className="rounded px-0.5 bg-amber-200/70 text-slate-900 dark:bg-amber-400/20 dark:text-white"
          >
            {p}
          </span>
        );
      });
    },
    [escapeRegExp, submittedQuery]
  );

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="全局搜索"
        title="搜索"
        description="搜索新闻、论坛帖子、律所、律师与知识库内容"
        layout="mdStart"
        tone={actualTheme}
      />

      <Card variant="surface" padding="lg">
        <div className="max-w-2xl">
          <Input
            icon={Search}
            value={q}
            onChange={(e) => {
              setSuggestionsEnabled(true);
              setQ(e.target.value);
            }}
            placeholder="请输入关键词..."
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                performSearch();
              }
            }}
          />

          {suggestionsEnabled && suggestions.length > 0 && (
            <div className="mt-3 rounded-xl border border-slate-200/70 bg-white overflow-hidden dark:border-white/10 dark:bg-white/5">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors dark:text-white/70 dark:hover:bg-white/10 dark:hover:text-white"
                  onClick={() => performSearch(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <div className="flex gap-3 mt-4">
            <Button onClick={() => performSearch()} disabled={searching}>
              搜索
            </Button>
            <Button
              variant="outline"
              onClick={clearAllConditions}
              disabled={searching && submittedQuery.trim().length > 0}
            >
              清空条件
            </Button>
            {isAuthenticated && (
              <Button variant="outline" icon={Trash2} onClick={clearHistory}>
                清空历史
              </Button>
            )}
          </div>
        </div>
      </Card>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card variant="surface" padding="lg" data-testid="search-hot-card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2 dark:text-white">
              <TrendingUp className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              热门搜索
            </h3>
          </div>
          {hotKeywords.length === 0 ? (
            <div className="text-slate-500 text-sm dark:text-white/40">
              暂无数据
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {hotKeywords.map((k) => (
                <button
                  key={k.keyword}
                  type="button"
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/5 border border-slate-200/70 text-slate-700 hover:text-slate-900 hover:bg-slate-50 transition-colors dark:bg-white/5 dark:border-white/10 dark:text-white/70 dark:hover:text-white dark:hover:bg-white/10"
                  onClick={() => performSearch(k.keyword)}
                >
                  <span>{k.keyword}</span>
                  <Badge variant="info" size="sm">
                    {k.count}
                  </Badge>
                </button>
              ))}
            </div>
          )}
        </Card>

        <Card variant="surface" padding="lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2 dark:text-white">
              <History className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              搜索历史
            </h3>
          </div>

          {!isAuthenticated ? (
            <div className="text-slate-500 text-sm dark:text-white/40">
              请先{" "}
              <Link
                to="/login"
                className="text-amber-600 hover:underline dark:text-amber-400"
              >
                登录
              </Link>{" "}
              后查看搜索历史
            </div>
          ) : history.length === 0 ? (
            <div className="text-slate-500 text-sm dark:text-white/40">
              暂无历史
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {history.map((h) => (
                <button
                  key={h}
                  type="button"
                  className="px-3 py-1.5 rounded-full bg-slate-900/5 border border-slate-200/70 text-slate-700 hover:text-slate-900 hover:bg-slate-50 transition-colors dark:bg-white/5 dark:border-white/10 dark:text-white/70 dark:hover:text-white dark:hover:bg-white/10"
                  onClick={() => performSearch(h)}
                >
                  {h}
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card variant="surface" padding="lg">
        <h3 className="text-lg font-semibold text-slate-900 mb-6 dark:text-white">
          搜索结果
        </h3>

        {searching ? (
          <Loading text="搜索中..." tone={actualTheme} />
        ) : !results ? (
          <EmptyState
            icon={Search}
            title="请输入关键词开始搜索"
            description="你可以从热门词或历史记录开始"
            tone={actualTheme}
            action={
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <Button
                  variant="outline"
                  onClick={() => {
                    document.querySelector('[data-testid="search-hot-card"]')?.scrollIntoView({
                      behavior: "smooth",
                      block: "center",
                    });
                  }}
                >
                  看看热门搜索
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Link
                  to="/chat"
                  className="inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all outline-none focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 active:scale-[0.99] px-5 py-3 text-sm btn-primary text-white"
                >
                  去 AI 咨询
                  <Sparkles className="h-4 w-4" />
                </Link>
              </div>
            }
          />
        ) : !hasAnyResults ? (
          <EmptyState
            icon={Search}
            title="没有找到相关内容"
            description="试试换个关键词、减少限制，或直接进入 AI 咨询获得建议"
            tone={actualTheme}
            action={
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                  <Button variant="outline" onClick={clearAllConditions}>
                    清空条件
                  </Button>
                  <Link
                    to={`/chat?draft=${encodeURIComponent(submittedQuery.trim())}`}
                    className="inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all outline-none focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 active:scale-[0.99] px-5 py-3 text-sm btn-primary text-white"
                  >
                    让 AI 帮我分析
                    <Sparkles className="h-4 w-4" />
                  </Link>
                  <Link
                    to="/lawfirm"
                    className="inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all outline-none focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 active:scale-[0.99] px-5 py-3 text-sm btn-outline"
                  >
                    找律师
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>

                <div className="text-left max-w-3xl mx-auto">
                  <div className="text-sm font-medium text-slate-900 mb-3 dark:text-white">
                    你可以尝试：
                  </div>
                  <div className="grid md:grid-cols-3 gap-3">
                    <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 text-sm text-slate-700 dark:bg-white/5 dark:border-white/10 dark:text-white/70">
                      换同义词（如“辞退/解除/补偿”）
                    </div>
                    <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 text-sm text-slate-700 dark:bg-white/5 dark:border-white/10 dark:text-white/70">
                      增加关键事实（时间、金额、地区）
                    </div>
                    <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 text-sm text-slate-700 dark:bg-white/5 dark:border-white/10 dark:text-white/70">
                      先用工具自查，再去咨询
                    </div>
                  </div>
                </div>

                <div className="max-w-3xl mx-auto text-left">
                  <div className="text-sm font-medium text-slate-900 mb-3 dark:text-white">
                    热门工具推荐
                  </div>
                  <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    {toolNavItems.map(({ path, label, icon: Icon }) => (
                      <Link
                        key={path}
                        to={path}
                        className="group p-4 rounded-xl bg-white border border-slate-200/70 hover:bg-slate-50 transition-colors dark:bg-white/5 dark:border-white/10 dark:hover:bg-white/10"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                            <Icon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-sm font-medium text-slate-900 dark:text-white">
                              {label}
                            </div>
                            <div className="text-xs text-slate-500 dark:text-white/40">
                              立即使用
                            </div>
                          </div>
                        </div>
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            }
          />
        ) : (
          <div className="space-y-8">
            {categoryCounts && (
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="info">共 {categoryCounts.total} 条</Badge>
                <Badge variant="default">新闻 {categoryCounts.news}</Badge>
                <Badge variant="default">帖子 {categoryCounts.posts}</Badge>
                <Badge variant="default">律所 {categoryCounts.lawfirms}</Badge>
                <Badge variant="default">律师 {categoryCounts.lawyers}</Badge>
                <Badge variant="default">知识库 {categoryCounts.knowledge}</Badge>
              </div>
            )}
            {results.news.length > 0 && (
              <div>
                <h4 className="text-slate-700 font-medium mb-3 dark:text-white/80">
                  新闻
                </h4>
                <VirtualWindowList
                  items={results.news}
                  estimateItemHeight={92}
                  overscan={8}
                  getItemKey={(n) => `news-${n.id}`}
                  itemClassName="pb-3"
                  renderItem={(n) => (
                    <Link
                      to={`/news/${n.id}`}
                      className="block p-4 rounded-xl bg-white border border-slate-200/70 hover:bg-slate-50 transition-colors dark:bg-white/5 dark:border-white/10 dark:hover:bg-white/10"
                    >
                      <div className="text-slate-900 font-medium dark:text-white">
                        {highlightText(n.title)}
                      </div>
                      {n.snippet || n.summary ? (
                        <div className="text-slate-600 text-sm mt-1 dark:text-white/50">
                          {highlightText(n.snippet || n.summary)}
                        </div>
                      ) : null}
                    </Link>
                  )}
                />
              </div>
            )}

            {results.posts.length > 0 && (
              <div>
                <h4 className="text-slate-700 font-medium mb-3 dark:text-white/80">
                  论坛帖子
                </h4>
                <VirtualWindowList
                  items={results.posts}
                  estimateItemHeight={96}
                  overscan={8}
                  getItemKey={(p) => `post-${p.id}`}
                  itemClassName="pb-3"
                  renderItem={(p) => (
                    <Link
                      to={`/forum/post/${p.id}`}
                      className="block p-4 rounded-xl bg-white border border-slate-200/70 hover:bg-slate-50 transition-colors dark:bg-white/5 dark:border-white/10 dark:hover:bg-white/10"
                    >
                      <div className="text-slate-900 font-medium dark:text-white">
                        {p.title}
                      </div>
                      {p.content && (
                        <div className="text-slate-600 text-sm mt-1 dark:text-white/50">
                          {p.content}
                        </div>
                      )}
                    </Link>
                  )}
                />
              </div>
            )}

            {results.lawfirms.length > 0 && (
              <div>
                <h4 className="text-slate-700 font-medium mb-3 dark:text-white/80">
                  律所
                </h4>
                <VirtualWindowList
                  items={results.lawfirms}
                  estimateItemHeight={88}
                  overscan={8}
                  getItemKey={(f) => `firm-${f.id}`}
                  itemClassName="pb-3"
                  renderItem={(f) => (
                    <Link
                      to={`/lawfirm/${f.id}`}
                      className="block p-4 rounded-xl bg-white border border-slate-200/70 hover:bg-slate-50 transition-colors dark:bg-white/5 dark:border-white/10 dark:hover:bg-white/10"
                    >
                      <div className="text-slate-900 font-medium dark:text-white">
                        {f.name}
                      </div>
                      {f.address && (
                        <div className="text-slate-600 text-sm mt-1 dark:text-white/50">
                          {f.address}
                        </div>
                      )}
                    </Link>
                  )}
                />
              </div>
            )}

            {results.lawyers.length > 0 && (
              <div>
                <h4 className="text-slate-700 font-medium mb-3 dark:text-white/80">
                  律师
                </h4>
                <div className="grid md:grid-cols-2 gap-3">
                  {results.lawyers.map((l) => (
                    <div
                      key={`lawyer-${l.id}`}
                      className="p-4 rounded-xl bg-white border border-slate-200/70 dark:bg-white/5 dark:border-white/10"
                    >
                      <div className="text-slate-900 font-medium dark:text-white">
                        {l.name}
                      </div>
                      {l.specialties && (
                        <div className="text-slate-600 text-sm mt-1 dark:text-white/50">
                          {l.specialties}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {results.knowledge.length > 0 && (
              <div>
                <h4 className="text-slate-700 font-medium mb-3 dark:text-white/80">
                  知识库
                </h4>
                <div className="grid md:grid-cols-2 gap-3">
                  {results.knowledge.map((k) => (
                    <div
                      key={`knowledge-${k.id}`}
                      className="p-4 rounded-xl bg-white border border-slate-200/70 dark:bg-white/5 dark:border-white/10"
                    >
                      <div className="text-slate-900 font-medium dark:text-white">
                        {k.title}
                      </div>
                      {k.category && (
                        <div className="text-slate-600 text-sm mt-1 dark:text-white/50">
                          {k.category}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
