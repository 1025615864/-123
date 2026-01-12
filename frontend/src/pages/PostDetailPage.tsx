import { useEffect, useMemo, useRef, useState } from "react";
import {
  useParams,
  Link,
  useNavigate,
  useLocation,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowLeft,
  Clock,
  Loader2,
  ThumbsUp,
  MessageSquare,
  Send,
  User,
  Star,
  Eye,
  Flame,
  Award,
  Pin,
  ChevronLeft,
  ChevronRight,
  Reply,
  X,
  ExternalLink,
  Download,
  FileText,
  FileImage,
  FileArchive,
  FileAudio,
  FileVideo,
  FileSpreadsheet,
  Presentation,
  Pencil,
  RotateCcw,
  Trash2,
} from "lucide-react";
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import api from "../api/client";
import { useAppMutation, useToast } from "../hooks";
import { useAuth } from "../contexts/AuthContext";
import {
  Card,
  Button,
  Badge,
  FadeInImage,
  EmptyState,
  Modal,
  ModalActions,
  Skeleton,
  ListSkeleton,
} from "../components/ui";
import MarkdownContent from "../components/MarkdownContent";
import RichTextEditor from "../components/RichTextEditor";
import { getApiErrorMessage } from "../utils";
import { queryKeys } from "../queryKeys";
import { useTheme } from "../contexts/ThemeContext";

interface Author {
  id: number;
  username: string;
  nickname?: string;
  avatar?: string;
}

type AttachmentItem = { name: string; url: string };

function getUrlFileName(url: string): string {
  const withoutQuery = url.split("?")[0];
  const parts = withoutQuery.split("/");
  return parts[parts.length - 1] || "";
}

function getAttachmentExt(att: AttachmentItem): string {
  const name = att.name?.trim() || getUrlFileName(att.url);
  const base = name.split("?")[0];
  const dot = base.lastIndexOf(".");
  if (dot <= 0) return "";
  return base.slice(dot + 1).toLowerCase();
}

function isImageExt(ext: string): boolean {
  return ["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"].includes(ext);
}

function isPdfExt(ext: string): boolean {
  return ext === "pdf";
}

function getAttachmentIcon(ext: string) {
  if (isPdfExt(ext)) return FileText;
  if (isImageExt(ext)) return FileImage;
  if (["zip", "rar", "7z", "tar", "gz"].includes(ext)) return FileArchive;
  if (["mp3", "wav", "ogg", "m4a", "aac"].includes(ext)) return FileAudio;
  if (["mp4", "webm", "mov", "mkv", "avi", "ogv"].includes(ext))
    return FileVideo;
  if (["xls", "xlsx", "csv"].includes(ext)) return FileSpreadsheet;
  if (["ppt", "pptx"].includes(ext)) return Presentation;
  return FileText;
}

function getAttachmentPreviewType(ext: string): "image" | "pdf" | "none" {
  if (isPdfExt(ext)) return "pdf";
  if (isImageExt(ext)) return "image";
  return "none";
}

interface Comment {
  id: number;
  content: string;
  post_id: number;
  user_id: number;
  parent_id: number | null;
  like_count: number;
  images?: string[];
  created_at: string;
  review_status?: string | null;
  review_reason?: string | null;
  reviewed_at?: string | null;
  author: Author | null;
  is_liked: boolean;
  replies: Comment[];
}

type CommentListResponse = { items: Comment[]; total: number };

interface ReactionCount {
  emoji: string;
  count: number;
}

interface PostDetail {
  id: number;
  title: string;
  content: string;
  category: string;
  user_id: number;
  view_count: number;
  like_count: number;
  comment_count: number;
  share_count: number;
  favorite_count: number;
  is_pinned: boolean;
  is_hot: boolean;
  is_essence: boolean;
  heat_score: number;
  cover_image?: string;
  images?: string[];
  attachments?: Array<{ name: string; url: string }>;
  reactions?: ReactionCount[];
  created_at: string;
  updated_at: string;
  is_deleted?: boolean;
  review_status?: string | null;
  review_reason?: string | null;
  reviewed_at?: string | null;
  author: Author | null;
  is_liked: boolean;
  is_favorited: boolean;
}

// 常用表情
const QUICK_REACTIONS = ["👍", "❤️", "😀", "🎉", "🤔", "😢"];

// 图片展示组件
function ImageGallery({ images }: { images: string[] }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showLightbox, setShowLightbox] = useState(false);

  if (images.length === 0) return null;

  const handlePrev = () =>
    setCurrentIndex((i) => (i > 0 ? i - 1 : images.length - 1));
  const handleNext = () =>
    setCurrentIndex((i) => (i < images.length - 1 ? i + 1 : 0));

  return (
    <>
      <div
        className="grid gap-2"
        style={{
          gridTemplateColumns:
            images.length === 1
              ? "1fr"
              : images.length === 2
              ? "repeat(2, 1fr)"
              : "repeat(3, 1fr)",
        }}
      >
        {images.slice(0, 9).map((img, idx) => (
          <div
            key={idx}
            className={`relative cursor-pointer rounded-xl overflow-hidden bg-slate-900/5 dark:bg-white/5 ${
              images.length === 1 ? "max-h-96" : "aspect-square"
            }`}
            onClick={() => {
              setCurrentIndex(idx);
              setShowLightbox(true);
            }}
          >
            <FadeInImage
              src={img}
              alt=""
              wrapperClassName="w-full h-full"
              className="h-full w-full object-cover hover:scale-105 transition-transform duration-300"
            />
            {idx === 8 && images.length > 9 && (
              <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                <span className="text-white text-2xl font-bold">
                  +{images.length - 9}
                </span>
              </div>
            )}
          </div>
        ))}
      </div>

      {showLightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
          onClick={() => setShowLightbox(false)}
        >
          <button
            className="absolute left-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-white/10 hover:bg-white/20 text-white"
            onClick={(e) => {
              e.stopPropagation();
              handlePrev();
            }}
          >
            <ChevronLeft className="h-6 w-6" />
          </button>
          <img
            src={images[currentIndex]}
            alt=""
            className="max-h-[90vh] max-w-[90vw] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          <button
            className="absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-white/10 hover:bg-white/20 text-white"
            onClick={(e) => {
              e.stopPropagation();
              handleNext();
            }}
          >
            <ChevronRight className="h-6 w-6" />
          </button>
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-white/70 text-sm">
            {currentIndex + 1} / {images.length}
          </div>
        </div>
      )}
    </>
  );
}

export default function PostDetailPage() {
  const { postId } = useParams<{ postId: string }>();
  const { isAuthenticated, user } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const isDeletedView = searchParams.get("deleted") === "1";
  const commentIdParam = searchParams.get("commentId");

  const [postDetail, setPostDetail] = useState<PostDetail | null>(null);
  const [newComment, setNewComment] = useState("");
  const [newCommentImages, setNewCommentImages] = useState<string[]>([]);
  const [replyTo, setReplyTo] = useState<{ id: number; name: string } | null>(
    null
  );
  const commentJumpHintShownRef = useRef(false);
  const [highlightedCommentId, setHighlightedCommentId] = useState<number | null>(
    null
  );
  const highlightTimerRef = useRef<number | null>(null);
  const [previewAttachment, setPreviewAttachment] =
    useState<AttachmentItem | null>(null);
  const [confirmDeletePost, setConfirmDeletePost] = useState(false);
  const [confirmRestorePost, setConfirmRestorePost] = useState(false);
  const [confirmPurgePost, setConfirmPurgePost] = useState(false);

  const [pendingCommentLikes, setPendingCommentLikes] = useState<Record<number, boolean>>({});
  const [pendingCommentDeletes, setPendingCommentDeletes] = useState<Record<number, boolean>>({});

  const commentPageSize = 20;

  const postQueryKey = queryKeys.forumPost(postId);
  const commentsQueryKey = [
    ...queryKeys.forumPostComments(postId),
    {
      include_unapproved: isAuthenticated ? 1 : 0,
      viewer: isAuthenticated ? user?.id ?? null : null,
      page_size: commentPageSize,
    },
  ] as const;

  useEffect(() => {
    setPostDetail(null);
    commentJumpHintShownRef.current = false;
    setHighlightedCommentId(null);
    if (highlightTimerRef.current) {
      window.clearTimeout(highlightTimerRef.current);
      highlightTimerRef.current = null;
    }
  }, [postId, isDeletedView, user?.id, isAuthenticated]);

  const postQuery = useQuery({
    queryKey: [
      ...postQueryKey,
      {
        deleted: isDeletedView,
        viewer: isAuthenticated ? user?.id ?? null : null,
      },
    ] as const,
    queryFn: async () => {
      const url = isDeletedView
        ? `/forum/posts/${postId}/recycle`
        : `/forum/posts/${postId}`;
      const res = await api.get(url);
      return res.data as PostDetail;
    },
    enabled: !!postId && (!isDeletedView || isAuthenticated),
    retry: (failureCount, err: any) => {
      const status = err?.response?.status;
      if (status === 403 || status === 404) return false;
      return failureCount < 1;
    },
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const deletePostMutation = useAppMutation<{ message?: string }, void>({
    mutationFn: async () => {
      const res = await api.delete(`/forum/posts/${postId}`);
      return res.data as { message?: string };
    },
    errorMessageFallback: "删除失败，请稍后重试",
    onSuccess: async () => {
      setConfirmDeletePost(false);
      const id = postId;
      if (id) {
        queryClient.removeQueries({ queryKey: queryKeys.forumPost(id) });
        queryClient.removeQueries({
          queryKey: queryKeys.forumPostComments(id),
        });
      }
      toast.showToast("success", "已移入回收站", {
        durationMs: 7000,
        action: {
          label: "撤销",
          onClick: () => {
            if (!id) return;
            void (async () => {
              try {
                await api.post(`/forum/posts/${id}/restore`);
                await queryClient.invalidateQueries({
                  queryKey: queryKeys.forumPostsRoot(),
                });
                navigate(`/forum/post/${id}`);
                toast.success("已撤销删除");
              } catch (e) {
                toast.error(getApiErrorMessage(e, "撤销失败"));
              }
            })();
          },
          closeOnAction: true,
        },
      });
      navigate("/forum/recycle-bin");
      await queryClient.invalidateQueries({
        queryKey: queryKeys.forumPostsRoot(),
      });
    },
  });

  const updateCommentLike = (
    items: Comment[],
    targetId: number,
    liked: boolean,
    likeCount: number
  ): Comment[] => {
    return items.map((c) => {
      if (c.id === targetId) {
        return { ...c, is_liked: liked, like_count: likeCount };
      }
      if (c.replies && c.replies.length > 0) {
        return {
          ...c,
          replies: updateCommentLike(c.replies, targetId, liked, likeCount),
        };
      }
      return c;
    });
  };

  const findComment = (items: Comment[], targetId: number): Comment | null => {
    for (const c of items) {
      if (c.id === targetId) return c;
      if (c.replies && c.replies.length > 0) {
        const found = findComment(c.replies, targetId);
        if (found) return found;
      }
    }
    return null;
  };

  const removeCommentById = (
    items: Comment[],
    targetId: number
  ): { nextItems: Comment[]; removed: number } => {
    let removed = 0;

    const walk = (list: Comment[]): Comment[] => {
      const next: Comment[] = [];
      for (const c of list) {
        if (c.id === targetId) {
          removed += 1;
          continue;
        }
        let nextItem = c;
        if (Array.isArray(c.replies) && c.replies.length > 0) {
          const nextReplies = walk(c.replies);
          if (nextReplies.length !== c.replies.length) {
            nextItem = { ...c, replies: nextReplies };
          }
        }
        next.push(nextItem);
      }
      return next;
    };

    return { nextItems: walk(items), removed };
  };

  const insertTempComment = (
    items: Comment[],
    temp: Comment,
    parentId: number | null
  ): Comment[] => {
    if (!parentId) {
      return [temp, ...items];
    }

    return items.map((c) => {
      if (c.id === parentId) {
        const replies = Array.isArray(c.replies) ? c.replies : [];
        return { ...c, replies: [temp, ...replies] };
      }
      if (c.replies && c.replies.length > 0) {
        return { ...c, replies: insertTempComment(c.replies, temp, parentId) };
      }
      return c;
    });
  };

  const commentLikeMutation = useAppMutation<
    { liked: boolean; like_count: number },
    number
  >({
    mutationFn: async (commentId: number) => {
      const res = await api.post(`/forum/comments/${commentId}/like`);
      return res.data as { liked: boolean; like_count: number };
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onMutate: async (commentId) => {
      setPendingCommentLikes((prev) => ({ ...prev, [commentId]: true }));
      const previousCache = queryClient.getQueryData<
        InfiniteData<CommentListResponse>
      >(commentsQueryKey);

      const source = previousCache?.pages
        ? previousCache.pages.flatMap((p) => p.items ?? [])
        : [];
      const current = Array.isArray(source) ? findComment(source, commentId) : null;
      if (!current) return { previousCache };

      const nextLiked = !current.is_liked;
      const nextCount = Math.max(
        0,
        Number(current.like_count || 0) + (nextLiked ? 1 : -1)
      );

      queryClient.setQueryData<InfiniteData<CommentListResponse>>(
        commentsQueryKey,
        (old) => {
          if (!old) return old;
          return {
            ...old,
            pages: old.pages.map((p) => ({
              ...p,
              items: updateCommentLike(
                Array.isArray(p.items) ? p.items : [],
                commentId,
                nextLiked,
                nextCount
              ),
            })),
          };
        }
      );

      return { previousCache };
    },
    onSuccess: (result, commentId) => {
      queryClient.setQueryData<InfiniteData<CommentListResponse>>(
        commentsQueryKey,
        (old) => {
          if (!old) return old;
          return {
            ...old,
            pages: old.pages.map((p) => ({
              ...p,
              items: updateCommentLike(
                Array.isArray(p.items) ? p.items : [],
                commentId,
                result.liked,
                result.like_count
              ),
            })),
          };
        }
      );

      const msg = result.liked ? "已点赞" : "已取消点赞";
      toast.showToast("success", msg, {
        durationMs: 5000,
        action: {
          label: "撤销",
          onClick: () => {
            commentLikeMutation.mutate(commentId);
          },
          closeOnAction: true,
        },
      });
    },
    onError: (err, _commentId, ctx) => {
      if (ctx && typeof ctx === "object") {
        const anyCtx = ctx as any;
        if (anyCtx.previousCache !== undefined) {
          queryClient.setQueryData(commentsQueryKey, anyCtx.previousCache);
        }
      }
      return err as any;
    },
    onSettled: (_data, _err, commentId) => {
      setPendingCommentLikes((prev) => {
        const next = { ...prev };
        delete next[commentId];
        return next;
      });
    },
  });

  const deleteCommentMutation = useAppMutation<
    { message?: string },
    number,
    {
      previousCache?: InfiniteData<CommentListResponse>;
      previousPostState?: PostDetail | null;
      previousPostCache?: PostDetail | undefined;
    }
  >({
    mutationFn: async (commentId: number) => {
      const res = await api.delete(`/forum/comments/${commentId}`);
      return res.data as { message?: string };
    },
    errorMessageFallback: "删除失败，请稍后重试",
    onMutate: async (commentId) => {
      setPendingCommentDeletes((prev) => ({ ...prev, [commentId]: true }));
      await queryClient.cancelQueries({ queryKey: commentsQueryKey });

      const previousCache = queryClient.getQueryData<
        InfiniteData<CommentListResponse>
      >(commentsQueryKey);
      const previousPostState = postDetail;
      const previousPostCache = postId
        ? queryClient.getQueryData<PostDetail>(postQueryKey)
        : undefined;

      let removedTotal = 0;
      queryClient.setQueryData<InfiniteData<CommentListResponse>>(
        commentsQueryKey,
        (old) => {
          if (!old) return old;
          const pages = Array.isArray(old.pages) ? old.pages : [];
          if (pages.length === 0) return old;

          removedTotal = 0;
          const processed = pages.map((p) => {
            const items = Array.isArray((p as any).items)
              ? ((p as any).items as Comment[])
              : [];
            const result = removeCommentById(items, commentId);
            removedTotal += result.removed;
            return { p, result };
          });

          const nextPages = processed.map(({ p, result }, idx) => {
            const nextPage: any = { ...p, items: result.nextItems };
            if (idx === 0 && typeof (p as any).total === "number" && removedTotal > 0) {
              nextPage.total = Math.max(0, Number((p as any).total || 0) - removedTotal);
            }
            return nextPage;
          });

          return { ...old, pages: nextPages };
        }
      );

      if (removedTotal > 0) {
        setPostDetail((prev) =>
          prev
            ? {
                ...prev,
                comment_count: Math.max(
                  0,
                  Number(prev.comment_count || 0) - removedTotal
                ),
              }
            : prev
        );
        if (postId) {
          queryClient.setQueryData<PostDetail>(postQueryKey, (old) =>
            old
              ? {
                  ...old,
                  comment_count: Math.max(
                    0,
                    Number(old.comment_count || 0) - removedTotal
                  ),
                }
              : old
          );
        }
      }

      return { previousCache, previousPostState, previousPostCache };
    },
    onSuccess: async (_data, commentId) => {
      if (!postId) return;
      toast.showToast("success", "已删除", {
        durationMs: 7000,
        action: {
          label: "撤销",
          onClick: () => {
            const id = postId;
            void (async () => {
              try {
                await api.post(`/forum/comments/${commentId}/restore`);
                await Promise.all([
                  queryClient.invalidateQueries({
                    queryKey: queryKeys.forumPostComments(id),
                  }),
                  queryClient.invalidateQueries({ queryKey: postQueryKey }),
                ]);
                toast.success("已撤销删除");
              } catch (e) {
                toast.error(getApiErrorMessage(e, "撤销失败"));
              }
            })();
          },
          closeOnAction: true,
        },
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.forumPostComments(postId) }),
        queryClient.invalidateQueries({ queryKey: postQueryKey }),
      ]);
    },
    onError: (err, commentId, ctx) => {
      if (ctx && typeof ctx === "object") {
        const anyCtx = ctx as any;
        if (anyCtx.previousCache !== undefined) {
          queryClient.setQueryData(commentsQueryKey, anyCtx.previousCache);
        }
        if (anyCtx.previousPostState !== undefined) {
          setPostDetail(anyCtx.previousPostState ?? null);
        }
        if (postId && anyCtx.previousPostCache !== undefined) {
          queryClient.setQueryData(postQueryKey, anyCtx.previousPostCache);
        }
      }
      setPendingCommentDeletes((prev) => {
        const next = { ...prev };
        delete next[commentId];
        return next;
      });
      return err as any;
    },
    onSettled: (_data, _err, commentId) => {
      setPendingCommentDeletes((prev) => {
        const next = { ...prev };
        delete next[commentId];
        return next;
      });
    },
  });

  const commentsQuery = useInfiniteQuery({
    queryKey: commentsQueryKey,
    initialPageParam: 1,
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams();
      params.set("page", String(pageParam));
      params.set("page_size", String(commentPageSize));
      if (isAuthenticated) params.append("include_unapproved", "1");

      const url = `/forum/posts/${postId}/comments?${params.toString()}`;
      const res = await api.get(url);
      const items = res.data?.items ?? [];
      const total = Number(res.data?.total ?? 0);
      return {
        items: (Array.isArray(items) ? items : []) as Comment[],
        total: Number.isFinite(total) ? total : 0,
      } as CommentListResponse;
    },
    getNextPageParam: (lastPage, pages) => {
      const loaded = pages.reduce((sum, p) => sum + (p.items?.length ?? 0), 0);
      if (loaded >= Number(lastPage?.total ?? 0)) return undefined;
      return pages.length + 1;
    },
    enabled: !!postId && !isDeletedView && !!postDetail,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const comments = useMemo<Comment[]>(() => {
    const pages = commentsQuery.data?.pages ?? [];
    return pages.flatMap((p) => (Array.isArray(p.items) ? p.items : []));
  }, [commentsQuery.data]);

  const commentsTotal =
    Number(commentsQuery.data?.pages?.[0]?.total ?? 0) || comments.length;

  const handleRefreshComments = () => {
    queryClient.setQueryData<InfiniteData<CommentListResponse>>(
      commentsQueryKey,
      (old) => {
        if (!old) return old;
        const firstPage = old.pages?.[0];
        const firstParam = old.pageParams?.[0];
        if (!firstPage) return old;
        return {
          ...old,
          pages: [firstPage],
          pageParams: [firstParam ?? 1],
        };
      }
    );
    void commentsQuery.refetch();
  };

  useEffect(() => {
    if (!postQuery.error) return;
    const status = (postQuery.error as any)?.response?.status;
    const msg = getApiErrorMessage(postQuery.error);
    if (status === 403 || status === 404) {
      setPostDetail(null);
      return;
    }
    toast.error(msg);
  }, [postQuery.error, toast]);

  useEffect(() => {
    if (!commentsQuery.error) return;
    if (!postDetail) return;
    toast.error(getApiErrorMessage(commentsQuery.error));
  }, [commentsQuery.error, toast, postDetail]);

  useEffect(() => {
    if (!postQuery.isSuccess) return;
    if (!postQuery.data) return;
    setPostDetail(postQuery.data);
  }, [postQuery.isSuccess, postQuery.data]);

  useEffect(() => {
    if (isDeletedView) return;
    const hash = (window.location.hash || "").trim();

    const rawId = (commentIdParam || "").trim();
    const hasTarget = rawId.length > 0 || hash.startsWith("#comment-");
    if (!hasTarget) return;
    if (!commentsQuery.isFetched) return;

    const parsed = rawId ? Number(rawId) : NaN;
    const targetId =
      Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null;

    const highlight = (id: number) => {
      setHighlightedCommentId(id);
      if (highlightTimerRef.current) {
        window.clearTimeout(highlightTimerRef.current);
      }
      highlightTimerRef.current = window.setTimeout(() => {
        setHighlightedCommentId((prev) => (prev === id ? null : prev));
        highlightTimerRef.current = null;
      }, 3500);
    };

    const scrollToEl = (id: string) => {
      const el = document.getElementById(id);
      if (!el) return false;
      el.scrollIntoView({ behavior: "smooth", block: "center" });

      if (id.startsWith("comment-")) {
        const n = Number(id.slice("comment-".length));
        if (Number.isFinite(n) && n > 0) {
          highlight(Math.trunc(n));
        }
      }

      return true;
    };

    // Prefer explicit commentId
    if (targetId) {
      const targetDomId = `comment-${targetId}`;
      const ok = scrollToEl(targetDomId);
      if (!ok) {
        if (commentsQuery.hasNextPage && !commentsQuery.isFetchingNextPage) {
          commentsQuery.fetchNextPage();
          return;
        }

        window.setTimeout(() => {
          const ok2 = scrollToEl(targetDomId);
          if (!ok2 && !commentJumpHintShownRef.current) {
            commentJumpHintShownRef.current = true;
            toast.info("已打开帖子，但指定评论可能仍在审核、已被驳回或已删除");
          }
        }, 500);
      }
      return;
    }

    // Fallback to hash like #comment-123
    if (hash.startsWith("#comment-")) {
      const id = hash.slice(1);
      const ok = scrollToEl(id);
      if (!ok) {
        window.setTimeout(() => {
          const ok2 = scrollToEl(id);
          if (!ok2 && !commentJumpHintShownRef.current) {
            commentJumpHintShownRef.current = true;
            toast.info("已打开帖子，但指定评论可能仍在审核、已被驳回或已删除");
          }
        }, 400);
      }
    }
  }, [
    commentIdParam,
    comments,
    commentsQuery.hasNextPage,
    commentsQuery.isFetched,
    commentsQuery.isFetchingNextPage,
    isDeletedView,
    postId,
    postDetail,
    toast,
  ]);

  const restorePostMutation = useAppMutation<{ message?: string }, void>({
    mutationFn: async () => {
      const res = await api.post(`/forum/posts/${postId}/restore`);
      return res.data as { message?: string };
    },
    errorMessageFallback: "恢复失败，请稍后重试",
    onSuccess: async () => {
      if (!postId) return;
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.forumPostsRoot() }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.forumPost(postId),
        }),
      ]);
      toast.success("已恢复");
      navigate(`/forum/post/${postId}`);
    },
  });

  const purgePostMutation = useAppMutation<{ message?: string }, void>({
    mutationFn: async () => {
      const res = await api.delete(`/forum/posts/${postId}/purge`);
      return res.data as { message?: string };
    },
    errorMessageFallback: "永久删除失败，请稍后重试",
    onSuccess: async () => {
      toast.success("已永久删除");
      navigate("/forum/recycle-bin");
    },
  });

  const likeMutation = useAppMutation<
    { liked: boolean; like_count: number },
    void
  >({
    mutationFn: async (_: void) => {
      const res = await api.post(`/forum/posts/${postId}/like`);
      return res.data as { liked: boolean; like_count: number };
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onMutate: async () => {
      const previousState = postDetail;
      const previousCache = postId
        ? queryClient.getQueryData<PostDetail>(postQueryKey)
        : undefined;

      const current = previousState ?? previousCache;
      if (!current) return { previousState, previousCache };

      const nextLiked = !current.is_liked;
      const nextCount = Math.max(
        0,
        Number(current.like_count || 0) + (nextLiked ? 1 : -1)
      );

      setPostDetail((prev) =>
        prev ? { ...prev, is_liked: nextLiked, like_count: nextCount } : prev
      );
      if (postId) {
        queryClient.setQueryData<PostDetail>(postQueryKey, (old) =>
          old ? { ...old, is_liked: nextLiked, like_count: nextCount } : old
        );
      }

      return { previousState, previousCache };
    },
    onSuccess: (result) => {
      setPostDetail((prev) =>
        prev
          ? { ...prev, is_liked: result.liked, like_count: result.like_count }
          : prev
      );
      if (!postId) return;
      queryClient.setQueryData<PostDetail>(postQueryKey, (old) =>
        old
          ? { ...old, is_liked: result.liked, like_count: result.like_count }
          : old
      );

      const msg = result.liked ? "已点赞" : "已取消点赞";
      toast.showToast("success", msg, {
        durationMs: 5000,
        action: {
          label: "撤销",
          onClick: () => {
            likeMutation.mutate();
          },
          closeOnAction: true,
        },
      });
    },
    onError: (err, _vars, ctx) => {
      if (ctx && typeof ctx === "object") {
        const anyCtx = ctx as any;
        if (anyCtx.previousState !== undefined) {
          setPostDetail(anyCtx.previousState ?? null);
        }
        if (postId && anyCtx.previousCache !== undefined) {
          queryClient.setQueryData(postQueryKey, anyCtx.previousCache);
        }
      }
      return err as any;
    },
  });

  const favoriteMutation = useAppMutation<
    { favorited: boolean; favorite_count: number },
    void
  >({
    mutationFn: async (_: void) => {
      const res = await api.post(`/forum/posts/${postId}/favorite`);
      return res.data as { favorited: boolean; favorite_count: number };
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onMutate: async () => {
      const previousState = postDetail;
      const previousCache = postId
        ? queryClient.getQueryData<PostDetail>(postQueryKey)
        : undefined;

      const current = previousState ?? previousCache;
      if (!current) return { previousState, previousCache };

      const nextFavorited = !current.is_favorited;
      const nextCount = Math.max(
        0,
        Number(current.favorite_count || 0) + (nextFavorited ? 1 : -1)
      );

      setPostDetail((prev) =>
        prev
          ? {
              ...prev,
              is_favorited: nextFavorited,
              favorite_count: nextCount,
            }
          : prev
      );

      if (postId) {
        queryClient.setQueryData<PostDetail>(postQueryKey, (old) =>
          old
            ? {
                ...old,
                is_favorited: nextFavorited,
                favorite_count: nextCount,
              }
            : old
        );
      }

      return { previousState, previousCache };
    },
    onSuccess: (result) => {
      setPostDetail((prev) =>
        prev
          ? {
              ...prev,
              is_favorited: result.favorited,
              favorite_count: result.favorite_count,
            }
          : prev
      );
      if (!postId) return;
      queryClient.setQueryData<PostDetail>(postQueryKey, (old) =>
        old
          ? {
              ...old,
              is_favorited: result.favorited,
              favorite_count: result.favorite_count,
            }
          : old
      );

      const msg = result.favorited ? "收藏成功" : "已取消收藏";
      toast.showToast("success", msg, {
        durationMs: 7000,
        action: {
          label: "撤销",
          onClick: () => {
            favoriteMutation.mutate();
          },
          closeOnAction: true,
        },
      });
    },
    onError: (err, _vars, ctx) => {
      if (ctx && typeof ctx === "object") {
        const anyCtx = ctx as any;
        if (anyCtx.previousState !== undefined) {
          setPostDetail(anyCtx.previousState ?? null);
        }
        if (postId && anyCtx.previousCache !== undefined) {
          queryClient.setQueryData(postQueryKey, anyCtx.previousCache);
        }
      }
      return err as any;
    },
  });

  const reactionMutation = useAppMutation<
    { reactions: ReactionCount[] },
    string
  >({
    mutationFn: async (emoji: string) => {
      const res = await api.post(`/forum/posts/${postId}/reaction`, { emoji });
      return res.data as { reactions: ReactionCount[] };
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: (result) => {
      setPostDetail((prev) =>
        prev ? { ...prev, reactions: result.reactions } : prev
      );
      if (!postId) return;
      queryClient.setQueryData<PostDetail>(postQueryKey, (old) =>
        old ? { ...old, reactions: result.reactions } : old
      );
    },
  });

  const commentMutation = useAppMutation<
    { review_status?: string | null },
    { content: string; images: string[]; parent_id?: number | null }
  >({
    mutationFn: async (payload) => {
      const res = await api.post(`/forum/posts/${postId}/comments`, payload);
      return res.data as { review_status?: string | null };
    },
    errorMessageFallback: "发表评论失败，请稍后重试",
    onMutate: async (payload) => {
      if (!postId || !user)
        return {
          previousCache: queryClient.getQueryData<InfiniteData<CommentListResponse>>(
            commentsQueryKey
          ),
          previousPostState: postDetail,
          previousPostCache: queryClient.getQueryData<PostDetail>(postQueryKey),
        };

      const previousCache = queryClient.getQueryData<InfiniteData<CommentListResponse>>(
        commentsQueryKey
      );
      const previousPostState = postDetail;
      const previousPostCache = queryClient.getQueryData<PostDetail>(postQueryKey);

      const tempId = -Math.trunc(Date.now());
      const nowIso = new Date().toISOString();
      const temp: Comment = {
        id: tempId,
        content: payload.content,
        post_id: Number(postId),
        user_id: Number(user.id),
        parent_id: payload.parent_id ?? null,
        like_count: 0,
        images: payload.images ?? [],
        created_at: nowIso,
        review_status: "pending",
        review_reason: null,
        reviewed_at: null,
        author: {
          id: Number(user.id),
          username: String(user.username ?? ""),
          nickname: (user as any)?.nickname,
          avatar: (user as any)?.avatar,
        },
        is_liked: false,
        replies: [],
      };

      const isTopLevel = payload.parent_id == null;
      queryClient.setQueryData<InfiniteData<CommentListResponse>>(
        commentsQueryKey,
        (old) => {
          if (!old) return old;
          const pages = Array.isArray(old.pages) ? old.pages : [];
          if (pages.length === 0) return old;
          const nextPages = pages.map((p, idx) => {
            const items = Array.isArray(p.items) ? p.items : [];
            if (isTopLevel) {
              if (idx !== 0) return p;
              return {
                ...p,
                items: insertTempComment(items, temp, null),
                total: Math.max(0, Number(p.total || 0) + 1),
              };
            }
            return { ...p, items: insertTempComment(items, temp, payload.parent_id ?? null) };
          });
          return { ...old, pages: nextPages };
        }
      );

      setPostDetail((prev) =>
        prev
          ? { ...prev, comment_count: Math.max(0, Number(prev.comment_count || 0) + 1) }
          : prev
      );
      queryClient.setQueryData<PostDetail>(postQueryKey, (old) =>
        old
          ? { ...old, comment_count: Math.max(0, Number(old.comment_count || 0) + 1) }
          : old
      );

      return { previousCache, previousPostState, previousPostCache };
    },
    onSuccess: async (data) => {
      setNewComment("");
      setNewCommentImages([]);
      setReplyTo(null);
      if (!postId) return;

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.forumPostComments(postId) }),
        queryClient.invalidateQueries({ queryKey: postQueryKey }),
      ]);

      if (data?.review_status === "pending") {
        toast.info("评论已提交审核，通过后将展示");
      }
    },
    onError: (err, _payload, ctx) => {
      if (ctx && typeof ctx === "object") {
        const anyCtx = ctx as any;
        if (anyCtx.previousCache !== undefined) {
          queryClient.setQueryData(commentsQueryKey, anyCtx.previousCache);
        }
        if (anyCtx.previousPostState !== undefined) {
          setPostDetail(anyCtx.previousPostState ?? null);
        }
        if (postId && anyCtx.previousPostCache !== undefined) {
          queryClient.setQueryData(postQueryKey, anyCtx.previousPostCache);
        }
      }
      return err as any;
    },
  });

  const handleLike = async () => {
    if (!isAuthenticated || !postId) {
      toast.info("登录后可点赞");
      return;
    }
    if (likeMutation.isPending) return;
    likeMutation.mutate();
  };

  const handleFavorite = async () => {
    if (!isAuthenticated || !postId) {
      toast.info("登录后可收藏");
      return;
    }
    if (favoriteMutation.isPending) return;
    favoriteMutation.mutate();
  };

  const postLikeLoading = likeMutation.isPending;
  const postFavoriteLoading = favoriteMutation.isPending;
  const postActionBusy = postLikeLoading || postFavoriteLoading;
  const disablePostLike = !isAuthenticated || (postActionBusy && !postLikeLoading);
  const disablePostFavorite =
    !isAuthenticated || (postActionBusy && !postFavoriteLoading);

  const handleSubmitComment = async () => {
    if (!newComment.trim() || commentMutation.isPending) return;
    if (!postId) return;
    commentMutation.mutate({
      content: newComment.trim(),
      images: newCommentImages,
      parent_id: replyTo?.id ?? null,
    });
  };

  const canDeleteComment = (c: Comment): boolean => {
    if (!user) return false;
    if (["admin", "super_admin", "moderator"].includes(String((user as any).role))) return true;
    return Number(user.id) === Number(c.user_id);
  };

  const renderComment = (comment: Comment, depth: number) => {
    const commentMarkdownHasImages = /!\[[^\]]*\]\(([^)]+)\)/.test(
      comment.content
    );
    const showCommentGallery =
      !commentMarkdownHasImages && (comment.images?.length ?? 0) > 0;
    const authorName =
      comment.author?.nickname || comment.author?.username || "匿名用户";
    const indentClass = depth <= 0 ? "" : depth === 1 ? "ml-8" : "ml-14";
    const commentReviewStatus = comment.review_status || null;
    const canInteractWithComment =
      commentReviewStatus !== "pending" && commentReviewStatus !== "rejected";

    const canReplyOrLike = isAuthenticated && canInteractWithComment;
    const canDelete = isAuthenticated && canDeleteComment(comment) && comment.id > 0;
    const likeLoading = Boolean(pendingCommentLikes[comment.id]);
    const deleteLoading = Boolean(pendingCommentDeletes[comment.id]);

    const isHighlighted = highlightedCommentId === comment.id;

    return (
      <div
        key={comment.id}
        id={`comment-${comment.id}`}
        className={`${indentClass} ${
          isHighlighted
            ? "rounded-2xl ring-2 ring-amber-400/50 ring-offset-2 ring-offset-white dark:ring-offset-slate-950"
            : ""
        }`}
      >
        <div className="flex gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-amber-500/20 to-orange-500/10 flex items-center justify-center flex-shrink-0">
            {comment.author?.avatar ? (
              <FadeInImage
                src={comment.author.avatar}
                alt=""
                wrapperClassName="w-full h-full rounded-full"
                className="h-full w-full rounded-full object-cover"
              />
            ) : (
              <User className="h-4 w-4 text-amber-400" />
            )}
          </div>

          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-slate-900 font-medium text-sm dark:text-white">
                {authorName}
              </span>
              {commentReviewStatus === "pending" ? (
                <Badge
                  variant="warning"
                  size="sm"
                  title={comment.review_reason || undefined}
                >
                  审核中
                </Badge>
              ) : null}
              {commentReviewStatus === "rejected" ? (
                <Badge
                  variant="danger"
                  size="sm"
                  title={comment.review_reason || undefined}
                >
                  已驳回
                </Badge>
              ) : null}
              <span className="text-slate-400 text-xs dark:text-white/30">
                {new Date(comment.created_at).toLocaleString()}
              </span>
            </div>
            <div className="text-sm">
              <MarkdownContent content={comment.content} />
            </div>
            {showCommentGallery && comment.images ? (
              <div className="mt-3">
                <ImageGallery images={comment.images} />
              </div>
            ) : null}

            {canReplyOrLike || canDelete ? (
              <div className="mt-2 flex items-center gap-4">
                {canReplyOrLike ? (
                  <button
                    type="button"
                    onClick={() => setReplyTo({ id: comment.id, name: authorName })}
                    className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 dark:text-white/40 dark:hover:text-white"
                  >
                    <Reply className="h-3.5 w-3.5" />
                    回复
                  </button>
                ) : null}

                {canReplyOrLike ? (
                  <button
                    type="button"
                    onClick={() => {
                      if (likeLoading) return;
                      commentLikeMutation.mutate(comment.id);
                    }}
                    disabled={likeLoading}
                    className={`inline-flex items-center gap-1.5 text-xs transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${
                      comment.is_liked
                        ? "text-amber-700 dark:text-amber-400"
                        : "text-slate-500 hover:text-slate-900 dark:text-white/40 dark:hover:text-white"
                    }`}
                  >
                    {likeLoading ? (
                      <span className="h-3.5 w-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" />
                    ) : (
                      <ThumbsUp className="h-3.5 w-3.5" />
                    )}
                    {comment.like_count || 0}
                  </button>
                ) : null}

                {canDelete ? (
                  <button
                    type="button"
                    onClick={() => {
                      if (deleteLoading) return;
                      deleteCommentMutation.mutate(comment.id);
                    }}
                    disabled={deleteLoading}
                    className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-red-600 dark:text-white/40 dark:hover:text-red-300 disabled:opacity-60 disabled:cursor-not-allowed"
                    title="删除"
                  >
                    {deleteLoading ? (
                      <span className="h-3.5 w-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                    删除
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        {comment.replies && comment.replies.length > 0 ? (
          <div className="mt-4 space-y-5">
            {comment.replies.map((child) => renderComment(child, depth + 1))}
          </div>
        ) : null}
      </div>
    );
  };

  const handleReaction = async (emoji: string) => {
    if (!isAuthenticated || !postId) return;
    if (reactionMutation.isPending) return;
    reactionMutation.mutate(emoji);
  };

  if (postQuery.isLoading && !postDetail && !postQuery.error) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-2 text-slate-600 dark:text-white/60">
          <Skeleton width="120px" height="16px" />
        </div>

        <div className="rounded-2xl border border-slate-200/70 bg-white p-6 dark:border-white/10 dark:bg-white/[0.02]">
          <div className="space-y-5">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-3 w-full">
                <div className="flex items-center gap-2 flex-wrap">
                  <Skeleton width="64px" height="22px" />
                  <Skeleton width="56px" height="22px" />
                  <Skeleton width="72px" height="22px" />
                </div>
                <Skeleton width="70%" height="28px" />
              </div>
              <Skeleton width="42px" height="16px" />
            </div>

            <div className="flex items-center gap-3 pb-6 border-b border-slate-200/70 dark:border-white/5">
              <Skeleton variant="circular" width="40px" height="40px" />
              <div className="space-y-2 flex-1">
                <Skeleton width="120px" height="14px" />
                <Skeleton width="200px" height="12px" />
              </div>
            </div>

            <div className="space-y-3">
              <Skeleton width="100%" height="16px" />
              <Skeleton width="92%" height="16px" />
              <Skeleton width="86%" height="16px" />
              <Skeleton width="78%" height="16px" />
            </div>
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

  if (isDeletedView && !isAuthenticated) {
    const redirect = `${location.pathname}${location.search}`
    return (
      <EmptyState
        icon={Trash2}
        title="请先登录"
        description="登录后可查看回收站帖子"
        tone={actualTheme}
        action={
          <div className="flex flex-col sm:flex-row gap-3">
            <Link to={`/login?return_to=${encodeURIComponent(redirect)}`}>
              <Button>去登录</Button>
            </Link>
            <Link to="/forum">
              <Button variant="outline">返回论坛</Button>
            </Link>
          </div>
        }
      />
    );
  }

  if (!postDetail) {
    const status = (postQuery.error as any)?.response?.status;
    const detail = (postQuery.error as any)?.response?.data?.detail;
    const isForbidden = status === 403;
    const isNotFound = status === 404;
    const hint = isForbidden
      ? "该内容可能正在审核中或已被驳回，仅作者或管理员可查看"
      : isNotFound
      ? "帖子不存在，或你暂无权限查看（可能正在审核中/已被驳回/已被删除）"
      : "帖子不存在或已被删除";

    const redirect = `${location.pathname}${location.search}`
    const title = isForbidden ? "暂无权限" : isNotFound ? "帖子不存在" : "加载失败"
    const desc = detail ? `${hint}（${String(detail)}）` : hint

    return (
      <EmptyState
        icon={FileText}
        title={title}
        description={desc}
        tone={actualTheme}
        action={
          <div className="flex flex-col sm:flex-row gap-3">
            {!isAuthenticated ? (
              <Link to={`/login?return_to=${encodeURIComponent(redirect)}`}>
                <Button>登录后再试</Button>
              </Link>
            ) : null}
            <Link to="/forum">
              <Button variant={isAuthenticated ? "primary" : "outline"}>返回论坛</Button>
            </Link>
          </div>
        }
      />
    );
  }

  const markdownHasEmbeddedImages = /!\[[^\]]*\]\(([^)]+)\)/.test(
    postDetail.content
  );
  const shouldShowImageGallery =
    !markdownHasEmbeddedImages && (postDetail.images?.length ?? 0) > 0;
  const previewExt = previewAttachment
    ? getAttachmentExt(previewAttachment)
    : "";
  const previewType = previewAttachment
    ? getAttachmentPreviewType(previewExt)
    : "none";

  const canManagePost =
    !!user &&
    (user.id === postDetail.user_id ||
      ["admin", "super_admin", "moderator"].includes(user.role));

  const reviewStatus = postDetail.review_status || null;
  const reviewReason = postDetail.review_reason || null;

  return (
    <div className="space-y-8">
      {/* 返回按钮 */}
      <Link
        to={isDeletedView ? "/forum/recycle-bin" : "/forum"}
        className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors dark:text-white/60 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        {isDeletedView ? "返回回收站" : "返回论坛"}
      </Link>

      {/* 帖子内容 */}
      <Card variant="surface" padding="lg">
        <div className="space-y-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              {/* 标签 */}
              <div className="flex items-center gap-2 flex-wrap mb-4">
                {canManagePost && reviewStatus === "pending" ? (
                  <Badge
                    variant="warning"
                    size="sm"
                    title={reviewReason || undefined}
                  >
                    审核中
                  </Badge>
                ) : null}
                {canManagePost && reviewStatus === "rejected" ? (
                  <Badge
                    variant="danger"
                    size="sm"
                    title={reviewReason || undefined}
                  >
                    {postDetail.is_deleted ? "已删除" : "已驳回"}
                  </Badge>
                ) : null}
                {canManagePost &&
                reviewStatus &&
                reviewStatus !== "pending" &&
                reviewStatus !== "rejected" ? (
                  <Badge
                    variant="success"
                    size="sm"
                    title={reviewReason || undefined}
                  >
                    已通过
                  </Badge>
                ) : null}
                {postDetail.is_pinned && (
                  <Badge
                    variant="warning"
                    size="sm"
                    className="flex items-center gap-1"
                  >
                    <Pin className="h-3 w-3" />
                    置顶
                  </Badge>
                )}
                {postDetail.is_essence && (
                  <Badge
                    variant="success"
                    size="sm"
                    className="flex items-center gap-1"
                  >
                    <Award className="h-3 w-3" />
                    精华
                  </Badge>
                )}
                {postDetail.is_hot && (
                  <Badge
                    variant="danger"
                    size="sm"
                    className="flex items-center gap-1"
                  >
                    <Flame className="h-3 w-3" />
                    热门
                  </Badge>
                )}
                <Badge variant="primary" size="sm">
                  {postDetail.category}
                </Badge>
              </div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                {postDetail.title}
              </h1>
            </div>
            <div className="flex flex-col items-end gap-3">
              <div className="flex items-center gap-1.5 text-slate-500 text-sm dark:text-white/40">
                <Eye className="h-4 w-4" />
                <span>{postDetail.view_count}</span>
              </div>

              {isAuthenticated && canManagePost ? (
                <div className="flex items-center gap-2">
                  {isDeletedView ? (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        icon={RotateCcw}
                        onClick={() => setConfirmRestorePost(true)}
                      >
                        恢复
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        icon={Trash2}
                        onClick={() => setConfirmPurgePost(true)}
                      >
                        永久删除
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        icon={Pencil}
                        onClick={() =>
                          navigate(`/forum/post/${postDetail.id}/edit`)
                        }
                      >
                        编辑
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        icon={Trash2}
                        onClick={() => setConfirmDeletePost(true)}
                      >
                        删除
                      </Button>
                    </>
                  )}
                </div>
              ) : null}
            </div>
          </div>

          {/* 作者信息 */}
          <div className="flex items-center gap-3 pb-6 border-b border-slate-200/70 dark:border-white/5">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-500/20 to-orange-500/10 flex items-center justify-center">
              {postDetail.author?.avatar ? (
                <FadeInImage
                  src={postDetail.author.avatar}
                  alt=""
                  wrapperClassName="w-full h-full rounded-full"
                  className="h-full w-full rounded-full object-cover"
                />
              ) : (
                <User className="h-5 w-5 text-amber-400" />
              )}
            </div>
            <div>
              <p className="text-slate-900 font-medium dark:text-white">
                {postDetail.author?.nickname ||
                  postDetail.author?.username ||
                  "匿名用户"}
              </p>
              <p className="text-slate-500 text-sm flex items-center gap-2 dark:text-white/40">
                <Clock className="h-3.5 w-3.5" />
                {new Date(postDetail.created_at).toLocaleString()}
              </p>
            </div>
          </div>

          {/* 帖子正文 */}
          {canManagePost && reviewStatus === "pending" ? (
            <div className="rounded-2xl border border-amber-200/70 bg-amber-50/70 px-4 py-3 text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
              <p className="text-sm font-semibold">你的帖子正在审核中</p>
              <p className="text-sm mt-1">审核通过后将会出现在论坛列表中。</p>
              {reviewReason ? (
                <p className="text-sm mt-1">原因：{reviewReason}</p>
              ) : null}
            </div>
          ) : null}

          {canManagePost && reviewStatus === "rejected" ? (
            <div className="rounded-2xl border border-red-200/70 bg-red-50/70 px-4 py-3 text-red-900 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
              <p className="text-sm font-semibold">你的帖子未通过审核</p>
              {reviewReason ? (
                <p className="text-sm mt-1">原因：{reviewReason}</p>
              ) : null}
              <p className="text-sm mt-1">
                你可以根据原因修改内容后再尝试发布。
              </p>
              {!isDeletedView ? (
                <button
                  type="button"
                  className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-red-800 hover:underline dark:text-red-200"
                  onClick={() => navigate(`/forum/post/${postDetail.id}/edit`)}
                >
                  去编辑
                </button>
              ) : null}
            </div>
          ) : null}

          {canManagePost && postDetail.is_deleted ? (
            <div className="rounded-2xl border border-slate-200/70 bg-slate-50/70 px-4 py-3 text-slate-800 dark:border-white/10 dark:bg-white/5 dark:text-white/80">
              <p className="text-sm font-semibold">该帖子已删除</p>
              <p className="text-sm mt-1">
                当前为回收站视图，只有作者或管理员可见。
              </p>
            </div>
          ) : null}

          <MarkdownContent content={postDetail.content} />

          {shouldShowImageGallery && postDetail.images ? (
            <ImageGallery images={postDetail.images} />
          ) : null}

          {/* 附件 */}
          {postDetail.attachments && postDetail.attachments.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm text-slate-500 dark:text-white/50">附件</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {postDetail.attachments.map((att, idx) => {
                  const ext = getAttachmentExt(att);
                  const Icon = getAttachmentIcon(ext);
                  const canPreview = getAttachmentPreviewType(ext) !== "none";

                  return (
                    <div
                      key={idx}
                      className="group flex items-start justify-between gap-3 rounded-2xl border border-slate-200/70 bg-white px-4 py-3 shadow-sm transition hover:shadow-md dark:border-white/10 dark:bg-white/[0.03]"
                    >
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900/5 text-slate-700 dark:bg-white/10 dark:text-white/80">
                          <Icon className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-slate-900 truncate dark:text-white">
                            {att.name || "附件"}
                          </p>
                          <p className="text-xs text-slate-500 mt-1 dark:text-white/40">
                            {ext ? ext.toUpperCase() : "FILE"}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        {canPreview ? (
                          <button
                            type="button"
                            onClick={() => setPreviewAttachment(att)}
                            className="inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold bg-slate-900/5 text-slate-700 hover:bg-slate-900/10 transition dark:bg-white/10 dark:text-white/80 dark:hover:bg-white/15"
                          >
                            <Eye className="h-4 w-4" />
                            预览
                          </button>
                        ) : null}

                        <a
                          href={att.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold bg-slate-900/5 text-slate-700 hover:bg-slate-900/10 transition dark:bg-white/10 dark:text-white/80 dark:hover:bg-white/15"
                        >
                          <ExternalLink className="h-4 w-4" />
                          打开
                        </a>

                        <a
                          href={att.url}
                          download
                          className="inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold bg-slate-900/5 text-slate-700 hover:bg-slate-900/10 transition dark:bg-white/10 dark:text-white/80 dark:hover:bg-white/15"
                        >
                          <Download className="h-4 w-4" />
                          下载
                        </a>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <Modal
            isOpen={!!previewAttachment}
            onClose={() => setPreviewAttachment(null)}
            title={previewAttachment?.name || "附件预览"}
            size={previewType === "pdf" ? "xl" : "lg"}
          >
            {previewAttachment && previewType === "image" ? (
              <div className="space-y-4">
                <div className="rounded-2xl overflow-hidden bg-slate-900/5 dark:bg-white/5">
                  <img
                    src={previewAttachment.url}
                    alt=""
                    className="w-full max-h-[70vh] object-contain"
                  />
                </div>
                <div className="flex justify-end gap-3">
                  <a
                    href={previewAttachment.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold bg-slate-900/5 text-slate-700 hover:bg-slate-900/10 transition dark:bg-white/10 dark:text-white/80 dark:hover:bg-white/15"
                  >
                    <ExternalLink className="h-4 w-4" />
                    新窗口打开
                  </a>
                  <a
                    href={previewAttachment.url}
                    download
                    className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold bg-slate-900/5 text-slate-700 hover:bg-slate-900/10 transition dark:bg-white/10 dark:text-white/80 dark:hover:bg-white/15"
                  >
                    <Download className="h-4 w-4" />
                    下载
                  </a>
                </div>
              </div>
            ) : null}

            {previewAttachment && previewType === "pdf" ? (
              <div className="space-y-4">
                <div className="rounded-2xl overflow-hidden border border-slate-200/70 bg-white dark:border-white/10 dark:bg-white/[0.03]">
                  <iframe
                    src={previewAttachment.url}
                    title="pdf-preview"
                    className="w-full h-[70vh]"
                  />
                </div>
                <div className="flex justify-end gap-3">
                  <a
                    href={previewAttachment.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold bg-slate-900/5 text-slate-700 hover:bg-slate-900/10 transition dark:bg-white/10 dark:text-white/80 dark:hover:bg-white/15"
                  >
                    <ExternalLink className="h-4 w-4" />
                    新窗口打开
                  </a>
                  <a
                    href={previewAttachment.url}
                    download
                    className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold bg-slate-900/5 text-slate-700 hover:bg-slate-900/10 transition dark:bg-white/10 dark:text-white/80 dark:hover:bg-white/15"
                  >
                    <Download className="h-4 w-4" />
                    下载
                  </a>
                </div>
              </div>
            ) : null}

            {previewAttachment && previewType === "none" ? (
              <div className="space-y-4">
                <p className="text-sm text-slate-600 dark:text-white/60">
                  该文件暂不支持站内预览。
                </p>
                <div className="flex justify-end gap-3">
                  <a
                    href={previewAttachment.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold bg-slate-900/5 text-slate-700 hover:bg-slate-900/10 transition dark:bg-white/10 dark:text-white/80 dark:hover:bg-white/15"
                  >
                    <ExternalLink className="h-4 w-4" />
                    新窗口打开
                  </a>
                  <a
                    href={previewAttachment.url}
                    download
                    className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold bg-slate-900/5 text-slate-700 hover:bg-slate-900/10 transition dark:bg-white/10 dark:text-white/80 dark:hover:bg-white/15"
                  >
                    <Download className="h-4 w-4" />
                    下载
                  </a>
                </div>
              </div>
            ) : null}
          </Modal>

          <Modal
            isOpen={confirmRestorePost}
            onClose={() => {
              if (restorePostMutation.isPending) return;
              setConfirmRestorePost(false);
            }}
            title="恢复帖子"
            description="恢复后帖子将重新出现在论坛列表中"
            size="sm"
          >
            <ModalActions>
              <Button
                variant="ghost"
                onClick={() => {
                  if (restorePostMutation.isPending) return;
                  setConfirmRestorePost(false);
                }}
                disabled={restorePostMutation.isPending}
              >
                取消
              </Button>
              <Button
                icon={RotateCcw}
                onClick={() => {
                  if (restorePostMutation.isPending) return;
                  restorePostMutation.mutate();
                }}
                isLoading={restorePostMutation.isPending}
                loadingText="恢复中..."
                disabled={restorePostMutation.isPending}
              >
                确认恢复
              </Button>
            </ModalActions>
          </Modal>

          <Modal
            isOpen={confirmPurgePost}
            onClose={() => {
              if (purgePostMutation.isPending) return;
              setConfirmPurgePost(false);
            }}
            title="永久删除"
            description="永久删除后将无法恢复，且会清理相关点赞/收藏/评论数据"
            size="sm"
          >
            <ModalActions>
              <Button
                variant="ghost"
                onClick={() => {
                  if (purgePostMutation.isPending) return;
                  setConfirmPurgePost(false);
                }}
                disabled={purgePostMutation.isPending}
              >
                取消
              </Button>
              <Button
                variant="danger"
                icon={Trash2}
                onClick={() => {
                  if (purgePostMutation.isPending) return;
                  purgePostMutation.mutate();
                }}
                isLoading={purgePostMutation.isPending}
                loadingText="删除中..."
                disabled={purgePostMutation.isPending}
              >
                确认永久删除
              </Button>
            </ModalActions>
          </Modal>

          <Modal
            isOpen={confirmDeletePost}
            onClose={() => {
              if (deletePostMutation.isPending) return;
              setConfirmDeletePost(false);
            }}
            title="删除帖子"
            description="删除后会进入回收站，可在回收站恢复或永久删除"
            size="sm"
          >
            <ModalActions>
              <Button
                variant="ghost"
                onClick={() => {
                  if (deletePostMutation.isPending) return;
                  setConfirmDeletePost(false);
                }}
                disabled={deletePostMutation.isPending}
              >
                取消
              </Button>
              <Button
                variant="danger"
                icon={Trash2}
                onClick={() => {
                  if (deletePostMutation.isPending) return;
                  deletePostMutation.mutate();
                }}
                isLoading={deletePostMutation.isPending}
                loadingText="删除中..."
                disabled={deletePostMutation.isPending}
              >
                确认删除
              </Button>
            </ModalActions>
          </Modal>

          {/* 表情反应 */}
          {!isDeletedView &&
            postDetail.reactions &&
            postDetail.reactions.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 pt-4">
                {postDetail.reactions.map((reaction, idx) => (
                  <span
                    key={idx}
                    className="flex items-center gap-1 px-2 py-1 rounded-full bg-slate-900/5 text-sm dark:bg-white/5"
                  >
                    <span>{reaction.emoji}</span>
                    <span className="text-slate-600 dark:text-white/60">
                      {reaction.count}
                    </span>
                  </span>
                ))}
              </div>
            )}

          {/* 快速表情反应 */}
          {!isDeletedView && isAuthenticated && (
            <div className="flex items-center gap-2 pt-2">
              <span className="text-xs text-slate-500 mr-1 dark:text-white/40">
                添加反应:
              </span>
              {QUICK_REACTIONS.map((emoji) => (
                <button
                  key={emoji}
                  onClick={() => handleReaction(emoji)}
                  className="p-1.5 rounded-lg hover:bg-slate-900/10 text-lg transition-colors dark:hover:bg-white/10"
                  title={`添加 ${emoji} 反应`}
                >
                  {emoji}
                </button>
              ))}
            </div>
          )}

          {/* 操作栏 */}
          {!isDeletedView ? (
            <div className="flex items-center gap-6 pt-6 border-t border-slate-200/70 dark:border-white/5">
              <button
                onClick={() => {
                  if (disablePostLike) return;
                  void handleLike();
                }}
                disabled={disablePostLike}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  postDetail.is_liked
                    ? "bg-amber-500/15 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400"
                    : "bg-slate-900/5 text-slate-600 hover:bg-slate-900/10 hover:text-slate-900 dark:bg-white/5 dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white"
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {postLikeLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ThumbsUp
                    className={`h-4 w-4 ${
                      postDetail.is_liked ? "fill-amber-400" : ""
                    }`}
                  />
                )}
                <span>{postLikeLoading ? "点赞中..." : postDetail.like_count}</span>
              </button>

              <button
                onClick={() => {
                  if (disablePostFavorite) return;
                  void handleFavorite();
                }}
                disabled={disablePostFavorite}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  postDetail.is_favorited
                    ? "bg-amber-500/15 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400"
                    : "bg-slate-900/5 text-slate-600 hover:bg-slate-900/10 hover:text-slate-900 dark:bg-white/5 dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white"
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {postFavoriteLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Star
                    className={`h-4 w-4 ${
                      postDetail.is_favorited ? "fill-amber-400" : ""
                    }`}
                  />
                )}
                <span>
                  {postFavoriteLoading ? "收藏中..." : postDetail.favorite_count}
                </span>
              </button>

              <div className="flex items-center gap-2 text-slate-500 dark:text-white/50">
                <MessageSquare className="h-4 w-4" />
                <span>{postDetail.comment_count} 评论</span>
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      {/* 评论区 */}
      {!isDeletedView ? (
        <Card variant="surface" padding="lg">
          <div className="flex items-center justify-between gap-3 mb-6">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
              评论 ({comments.length}/{commentsTotal})
            </h3>
            <Button
              variant="outline"
              size="sm"
              icon={RotateCcw}
              isLoading={commentsQuery.isFetching && !commentsQuery.isFetchingNextPage}
              loadingText="刷新中..."
              onClick={handleRefreshComments}
            >
              刷新评论
            </Button>
          </div>

          {/* 发表评论 */}
          {isAuthenticated ? (
            <div className="mb-8">
              {replyTo ? (
                <div className="mb-3 flex items-center justify-between gap-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 dark:border-amber-500/20 dark:bg-amber-500/10">
                  <div className="text-sm text-amber-900 dark:text-amber-200">
                    正在回复{" "}
                    <span className="font-semibold">{replyTo.name}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setReplyTo(null)}
                    className="p-1.5 rounded-lg text-amber-900/70 hover:bg-black/5 dark:text-amber-200/80 dark:hover:bg-white/10"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ) : null}
              <RichTextEditor
                value={newComment}
                onChange={setNewComment}
                images={newCommentImages}
                onImagesChange={setNewCommentImages}
                placeholder="写下你的评论...（支持 Markdown、图片）"
                minHeight="140px"
              />
              <div className="mt-3 flex justify-end">
                <Button
                  onClick={handleSubmitComment}
                  disabled={!newComment.trim() || commentMutation.isPending}
                  isLoading={commentMutation.isPending}
                  loadingText="发表中..."
                  icon={Send}
                  className="px-6"
                >
                  发表评论
                </Button>
              </div>
            </div>
          ) : (
            <div className="mb-8 p-4 rounded-xl bg-slate-900/5 text-center dark:bg-white/5">
              <p className="text-slate-600 dark:text-white/50">
                <Link
                  to="/login"
                  className="text-amber-600 hover:underline dark:text-amber-400"
                >
                  登录
                </Link>
                后即可发表评论
              </p>
            </div>
          )}

          {/* 评论列表 */}
          <div className="space-y-6">
            {commentsQuery.isLoading ? (
              <ListSkeleton count={3} />
            ) : comments.length === 0 ? (
              <p className="text-center text-slate-500 py-8 dark:text-white/40">
                暂无评论，来发表第一条评论吧
              </p>
            ) : (
              comments.map((comment) => renderComment(comment, 0))
            )}
          </div>

          {commentsQuery.hasNextPage ? (
            <div className="pt-6 flex justify-center">
              <Button
                variant="outline"
                isLoading={commentsQuery.isFetchingNextPage}
                loadingText="加载更多中..."
                disabled={commentsQuery.isFetchingNextPage}
                onClick={() => commentsQuery.fetchNextPage()}
              >
                加载更多
              </Button>
            </div>
          ) : commentsTotal > 0 ? (
            <div className="pt-6 text-center text-xs text-slate-500 dark:text-white/45">
              已加载全部
            </div>
          ) : null}

          {commentsQuery.isFetchingNextPage ? (
            <div className="pt-4">
              <ListSkeleton count={1} />
            </div>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
