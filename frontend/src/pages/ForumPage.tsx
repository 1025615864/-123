import { useMemo, useState, useEffect, useCallback, useRef } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { FileText, MessageSquare, Plus, Search, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  Input,
  Button,
  Chip,
  EmptyState,
  LinkButton,
  PostCardSkeleton,
  VirtualWindowList,
  Pagination,
} from "../components/ui";
import PageHeader from "../components/PageHeader";
import PostCard from "../components/PostCard";
import api from "../api/client";
import { usePrefetchLimiter, useToast } from "../hooks";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import type { Post } from "../types";
import { getApiErrorMessage } from "../utils";
import { queryKeys } from "../queryKeys";

interface PostsListResponse {
  items: Post[];
  total: number;
}

export default function ForumPage() {
  const [urlParams, setUrlParams] = useSearchParams();
  const didInitFromUrlRef = useRef(false);

  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [activeCategory, setActiveCategory] = useState("全部");
  const [keyword, setKeyword] = useState("");
  const { isAuthenticated, user } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [pendingFavoriteIds, setPendingFavoriteIds] = useState<number[]>([]);

  const { prefetch } = usePrefetchLimiter();

  const postCategories = useMemo(
    () => ["法律咨询", "经验分享", "案例讨论", "政策解读", "其他"],
    []
  );

  const categories = useMemo(
    () =>
      isAuthenticated
        ? ["我的帖子", "我的收藏", "全部", "精选案例", ...postCategories]
        : ["全部", "精选案例", ...postCategories],
    [isAuthenticated, postCategories]
  );

  useEffect(() => {
    if (didInitFromUrlRef.current) return;

    const rawPage = Number(String(urlParams.get("page") ?? "1"));
    const nextPage =
      Number.isFinite(rawPage) && rawPage >= 1 ? Math.floor(rawPage) : 1;

    const rawCat = String(urlParams.get("cat") ?? "").trim();
    const nextCategory =
      rawCat && categories.includes(rawCat) ? rawCat : "全部";

    const nextKeyword = String(urlParams.get("kw") ?? "");

    setPage(nextPage);
    setActiveCategory(nextCategory);
    setKeyword(nextKeyword);
    didInitFromUrlRef.current = true;
  }, [categories, urlParams]);

  useEffect(() => {
    if (!didInitFromUrlRef.current) return;
    if (isAuthenticated) return;
    if (activeCategory !== "我的收藏" && activeCategory !== "我的帖子") return;
    setActiveCategory("全部");
    setPage(1);
  }, [activeCategory, isAuthenticated]);

  useEffect(() => {
    if (!didInitFromUrlRef.current) return;
    setUrlParams(
      (prev) => {
        const next = new URLSearchParams(prev);

        if (page > 1) next.set("page", String(page));
        else next.delete("page");

        if (activeCategory && activeCategory !== "全部")
          next.set("cat", activeCategory);
        else next.delete("cat");

        const kw = keyword.trim();
        if (kw) next.set("kw", kw);
        else next.delete("kw");

        return next;
      },
      { replace: true }
    );
  }, [activeCategory, keyword, page, setUrlParams]);

  const [debouncedKeyword, setDebouncedKeyword] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => window.clearTimeout(timer);
  }, [keyword]);

  const isFavoritesMode = isAuthenticated && activeCategory === "我的收藏";
  const isMyPostsMode = isAuthenticated && activeCategory === "我的帖子";
  const isCasesMode = activeCategory === "精选案例";

  const postsQueryKey = useMemo(
    () =>
      queryKeys.forumPosts(
        page,
        pageSize,
        activeCategory,
        debouncedKeyword.trim(),
        isFavoritesMode
      ),
    [activeCategory, debouncedKeyword, isFavoritesMode, page, pageSize]
  );

  const postsQuery = useQuery({
    queryKey: postsQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(pageSize));

      if (
        !isFavoritesMode &&
        !isMyPostsMode &&
        !isCasesMode &&
        activeCategory &&
        activeCategory !== "全部"
      ) {
        params.set("category", activeCategory);
      }

      if (!isFavoritesMode && !isMyPostsMode && isCasesMode) {
        params.set("is_essence", "true");
      }
      if (debouncedKeyword.trim()) {
        params.set("keyword", debouncedKeyword.trim());
      }

      const endpoint = isFavoritesMode
        ? "/forum/favorites"
        : isMyPostsMode
        ? "/forum/me/posts"
        : "/forum/posts";
      const res = await api.get(`${endpoint}?${params.toString()}`);
      const data = res.data as PostsListResponse;
      return {
        items: Array.isArray(data?.items) ? data.items : [],
        total: Number(data?.total || 0),
      } as PostsListResponse;
    },
    placeholderData: (prev) => prev,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!postsQuery.error) return;
    toast.error(getApiErrorMessage(postsQuery.error));
  }, [postsQuery.error, toast]);

  useEffect(() => {
    setPage(1);
  }, [activeCategory, keyword]);

  const toggleFavoriteMutation = useMutation({
    mutationFn: async (postId: number) => {
      const res = await api.post(`/forum/posts/${postId}/favorite`);
      return res.data as { favorited: boolean; favorite_count: number };
    },
    onMutate: async (postId) => {
      if (!isAuthenticated) return;
      setPendingFavoriteIds((prev) =>
        prev.includes(postId) ? prev : [...prev, postId]
      );
      await queryClient.cancelQueries({ queryKey: postsQueryKey });

      const previous =
        queryClient.getQueryData<PostsListResponse>(postsQueryKey);

      queryClient.setQueryData<PostsListResponse>(postsQueryKey, (old) => {
        if (!old) return old as any;
        const nextItems = old.items.map((p) => {
          if (p.id !== postId) return p;
          const nextFavorited = !p.is_favorited;
          const nextCount = Math.max(
            0,
            (p.favorite_count ?? 0) + (nextFavorited ? 1 : -1)
          );
          return {
            ...p,
            is_favorited: nextFavorited,
            favorite_count: nextCount,
          };
        });

        if (isFavoritesMode) {
          return {
            ...old,
            items: nextItems.filter((p) => p.is_favorited),
            total: nextItems.filter((p) => p.is_favorited).length,
          };
        }

        return { ...old, items: nextItems };
      });

      return { previous };
    },
    onSettled: (_data, _err, postId) => {
      setPendingFavoriteIds((prev) => prev.filter((id) => id !== postId));
    },
    onError: (err, _postId, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(postsQueryKey, ctx.previous);
      }
      toast.error(getApiErrorMessage(err));
    },
    onSuccess: (result, postId) => {
      queryClient.setQueryData<PostsListResponse>(postsQueryKey, (old) => {
        if (!old) return old as any;
        const nextItems = old.items
          .map((p) =>
            p.id === postId
              ? {
                  ...p,
                  is_favorited: !!result.favorited,
                  favorite_count: Number(result.favorite_count ?? 0),
                }
              : p
          )
          .filter((p) => (isFavoritesMode ? p.is_favorited : true));
        return {
          ...old,
          items: nextItems,
          total: isFavoritesMode ? nextItems.length : old.total,
        };
      });

      const msg = result?.favorited ? "已收藏" : "已取消收藏";
      toast.showToast("success", msg, {
        durationMs: 7000,
        action: {
          label: "撤销",
          onClick: () => {
            toggleFavoriteMutation.mutate(postId);
          },
          closeOnAction: true,
        },
      });
    },
  });

  const handleToggleFavorite = useCallback(
    async (postId: number) => {
      if (!isAuthenticated) {
        toast.info("登录后可收藏");
        return;
      }
      if (pendingFavoriteIds.includes(postId)) return;
      toggleFavoriteMutation.mutate(postId);
    },
    [isAuthenticated, pendingFavoriteIds, toast, toggleFavoriteMutation]
  );

  const hotLimit = 8;
  const activeCategoryForHot =
    !isFavoritesMode &&
    !isMyPostsMode &&
    activeCategory &&
    activeCategory !== "全部"
      ? activeCategory
      : null;
  const hotQuery = useQuery({
    queryKey: queryKeys.forumHotPosts(hotLimit, activeCategoryForHot),
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("limit", String(hotLimit));
      if (activeCategoryForHot) {
        params.set("category", activeCategoryForHot);
      }
      const res = await api.get(`/forum/hot?${params.toString()}`);
      const items = res.data?.items ?? [];
      return (Array.isArray(items) ? items : []) as Post[];
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const sidebarRefreshing = hotQuery.isFetching || postsQuery.isFetching;

  const posts = postsQuery.data?.items ?? [];
  const total = postsQuery.data?.total ?? 0;

  if (postsQuery.isLoading && posts.length === 0) {
    return (
      <div className="space-y-6">
        {Array.from({ length: 5 }).map((_, i) => (
          <PostCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const emptyStateTitle = isFavoritesMode
    ? "暂无收藏帖子"
    : isMyPostsMode
    ? "你还没有发布帖子"
    : isCasesMode
    ? "暂无精选案例"
    : "暂无符合条件的帖子";

  const emptyStateDescription = isFavoritesMode
    ? "去论坛逛逛，收藏感兴趣的帖子会显示在这里"
    : isMyPostsMode
    ? "发布你的第一篇帖子，获取社区帮助"
    : isCasesMode
    ? "这里会展示管理员加精沉淀的高质量内容"
    : "试试切换分类或修改搜索关键词";

  const prefetchPostDetail = (id: number) => {
    const postId = String(id);
    prefetch({
      queryKey: queryKeys.forumPost(postId),
      queryFn: async () => {
        const res = await api.get(`/forum/posts/${postId}`);
        return res.data;
      },
    });

    const commentsQueryKey = [
      ...queryKeys.forumPostComments(postId),
      {
        include_unapproved: isAuthenticated ? 1 : 0,
        viewer: isAuthenticated ? user?.id ?? null : null,
      },
    ] as const;

    prefetch({
      queryKey: commentsQueryKey,
      queryFn: async () => {
        const params = new URLSearchParams();
        if (isAuthenticated) params.append("include_unapproved", "1");
        const url = params.toString()
          ? `/forum/posts/${postId}/comments?${params.toString()}`
          : `/forum/posts/${postId}/comments`;

        const res = await api.get(url);
        const items = res.data?.items ?? [];
        return Array.isArray(items) ? items : [];
      },
    });
  };

  return (
    <div className="w-full space-y-14">
      <PageHeader
        eyebrow="社区交流"
        title="法律论坛"
        description="与律师和法律爱好者交流讨论，分享经验与观点"
        layout="lgEnd"
        tone={actualTheme}
        right={
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="w-full sm:w-64">
              <Input
                icon={Search}
                value={keyword}
                onChange={(e) => {
                  setPage(1);
                  setKeyword(e.target.value);
                }}
                placeholder="搜索帖子..."
                className="py-2.5"
              />
            </div>
            {isAuthenticated ? (
              <>
                <LinkButton
                  to="/forum/my-comments"
                  variant="outline"
                  size="md"
                  className="px-5 py-2.5"
                  icon={MessageSquare}
                >
                  我的评论
                </LinkButton>
                <LinkButton
                  to="/forum/drafts"
                  variant="outline"
                  size="md"
                  className="px-5 py-2.5"
                  icon={FileText}
                >
                  草稿箱
                </LinkButton>
                <LinkButton
                  to="/forum/recycle-bin"
                  variant="outline"
                  size="md"
                  className="px-5 py-2.5"
                  icon={Trash2}
                >
                  回收站
                </LinkButton>
                <Button
                  onClick={() => navigate("/forum/new")}
                  icon={Plus}
                  className="py-2.5"
                >
                  发布
                </Button>
              </>
            ) : (
              <LinkButton
                to="/login"
                variant="outline"
                size="md"
                className="px-5 py-2.5"
              >
                登录后发帖
              </LinkButton>
            )}
          </div>
        }
      />

      <div className="flex flex-wrap gap-3">
        {categories.map((cat) => (
          <Chip
            key={cat}
            active={activeCategory === cat}
            onClick={() => {
              setPage(1);
              setActiveCategory(cat);
            }}
          >
            {cat}
          </Chip>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        <div className="lg:col-span-8">
          {posts.length === 0 ? (
            <EmptyState
              icon={MessageSquare}
              title={emptyStateTitle}
              description={emptyStateDescription}
              size="lg"
              action={
                isFavoritesMode ? (
                  <div className="mt-6">
                    <Button
                      variant="outline"
                      onClick={() => {
                        setActiveCategory("全部");
                        setKeyword("");
                        setPage(1);
                      }}
                      className="py-2.5"
                    >
                      去逛逛论坛
                    </Button>
                  </div>
                ) : isAuthenticated ? (
                  <div className="mt-6">
                    <Button
                      onClick={() => navigate("/forum/new")}
                      icon={Plus}
                      className="py-2.5"
                    >
                      发布第一个帖子
                    </Button>
                  </div>
                ) : null
              }
            />
          ) : (
            <VirtualWindowList
              items={posts}
              estimateItemHeight={220}
              overscan={8}
              getItemKey={(post: Post) => post.id}
              itemClassName="pb-6"
              renderItem={(post) => (
                <PostCard
                  post={post}
                  onToggleFavorite={handleToggleFavorite}
                  favoriteDisabled={
                    !isAuthenticated || pendingFavoriteIds.includes(post.id)
                  }
                  favoriteLoading={pendingFavoriteIds.includes(post.id)}
                  onPrefetch={prefetchPostDetail}
                />
              )}
            />
          )}

          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={(p) => setPage(p)}
            className="pt-2"
          />
        </div>

        <aside className="lg:col-span-4 space-y-6">
          <Card variant="surface" padding="lg" className="rounded-3xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-slate-900 dark:text-white">
                热度榜
              </h3>
              <button
                type="button"
                className="text-xs text-slate-500 hover:text-slate-900 dark:text-white/40 dark:hover:text-white disabled:opacity-60 disabled:cursor-not-allowed"
                onClick={() => {
                  if (sidebarRefreshing) return;
                  hotQuery.refetch();
                  postsQuery.refetch();
                }}
                disabled={sidebarRefreshing}
              >
                {sidebarRefreshing ? "刷新中..." : "刷新"}
              </button>
            </div>

            {hotQuery.isLoading && (hotQuery.data ?? []).length === 0 ? (
              <div className="space-y-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-10 rounded-xl bg-slate-900/5 dark:bg-white/5"
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {(hotQuery.data ?? []).slice(0, hotLimit).map((p, idx) => (
                  <Link
                    key={p.id}
                    to={`/forum/post/${p.id}`}
                    className="flex items-start gap-3 p-3 rounded-2xl hover:bg-slate-900/5 transition-colors dark:hover:bg-white/5"
                    onMouseEnter={() => prefetchPostDetail(p.id)}
                  >
                    <div
                      className={`w-7 h-7 rounded-xl flex items-center justify-center text-xs font-bold ${
                        idx < 3
                          ? "bg-amber-500/15 text-amber-700 dark:text-amber-400"
                          : "bg-slate-900/5 text-slate-600 dark:bg-white/5 dark:text-white/60"
                      }`}
                    >
                      {idx + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-900 line-clamp-2 dark:text-white">
                        {p.title}
                      </p>
                      <p className="text-xs text-slate-500 mt-1 dark:text-white/40">
                        热度 {(p.heat_score ?? 0).toFixed(0)} · 浏览{" "}
                        {p.view_count ?? 0}
                      </p>
                    </div>
                  </Link>
                ))}

                {(hotQuery.data ?? []).length === 0 ? (
                  <p className="text-sm text-slate-500 dark:text-white/40">
                    暂无热榜数据
                  </p>
                ) : null}
              </div>
            )}
          </Card>

          <Card variant="surface" padding="lg" className="rounded-3xl">
            <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-2">
              发帖小贴士
            </h3>
            <p className="text-sm text-slate-600 leading-relaxed dark:text-white/50">
              贴出关键事实、时间线、合同/聊天截图（可打码），更容易获得高质量回复。
            </p>
          </Card>
        </aside>
      </div>
    </div>
  );
}
