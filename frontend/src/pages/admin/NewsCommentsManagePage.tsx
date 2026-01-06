import { useEffect, useMemo, useState } from "react";
import { Check, RotateCcw, Search, Trash2, XCircle } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import { queryKeys } from "../../queryKeys";
import {
  Card,
  Input,
  Button,
  Badge,
  Pagination,
  Modal,
  ModalActions,
  Textarea,
  ListSkeleton,
} from "../../components/ui";

interface CommentAuthor {
  id: number;
  username: string;
  nickname?: string | null;
  avatar?: string | null;
}

interface CommentNewsBrief {
  id: number;
  title: string;
}

interface AdminNewsCommentItem {
  id: number;
  news_id: number;
  user_id: number;
  content: string;
  is_deleted: boolean;
  review_status?: string | null;
  review_reason?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  author?: CommentAuthor | null;
  news?: CommentNewsBrief | null;
}

interface AdminNewsCommentListResponse {
  items: AdminNewsCommentItem[];
  total: number;
  page: number;
  page_size: number;
}

const REVIEW_REASON_TEMPLATES = [
  "广告引流",
  "辱骂/攻击",
  "涉政敏感",
  "色情低俗",
  "人身信息/联系方式",
  "其他",
];

type ReviewAction = "approve" | "reject" | "delete";

type ReasonModalTarget =
  | {
      mode: "single";
      commentId: number;
      action: Exclude<ReviewAction, "approve">;
    }
  | {
      mode: "batch";
      commentIds: number[];
      action: Exclude<ReviewAction, "approve">;
    };

type BatchReviewResponse = {
  processed: number[];
  missing: number[];
  action?: string;
  reason?: string | null;
  requested?: number[];
  counts?: {
    requested: number;
    processed: number;
    missing: number;
    notifications_created?: number;
  };
  message?: string;
};

function normalizeStatus(s: unknown): string {
  return String(s ?? "")
    .trim()
    .toLowerCase();
}

function getStatusBadgeVariant(
  status: string,
  isDeleted: boolean
): { label: string; variant: any } {
  if (isDeleted) return { label: "已删除", variant: "danger" };
  if (status === "approved") return { label: "已通过", variant: "success" };
  if (status === "rejected") return { label: "已驳回", variant: "danger" };
  if (status === "pending") return { label: "待审核", variant: "warning" };
  return { label: status || "-", variant: "default" };
}

export default function NewsCommentsManagePage() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [keyword, setKeyword] = useState("");
  const [reviewStatus, setReviewStatus] = useState<string>("pending");
  const [includeDeleted, setIncludeDeleted] = useState(false);

  const queryKey = useMemo(
    () =>
      queryKeys.adminNewsComments(
        page,
        pageSize,
        String(reviewStatus || ""),
        keyword.trim(),
        Boolean(includeDeleted)
      ),
    [page, pageSize, reviewStatus, keyword, includeDeleted]
  );

  const listQuery = useQuery({
    queryKey,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      const rs = String(reviewStatus || "").trim();
      if (rs && rs !== "all") params.set("review_status", rs);
      const kw = keyword.trim();
      if (kw) params.set("keyword", kw);
      if (includeDeleted) params.set("include_deleted", "true");

      const res = await api.get(`/news/admin/comments?${params.toString()}`);
      const data = res.data as AdminNewsCommentListResponse;
      return {
        items: Array.isArray(data?.items)
          ? data.items
          : ([] as AdminNewsCommentItem[]),
        total: Number((data as any)?.total || 0),
      };
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!listQuery.error) return;
    toast.error(getApiErrorMessage(listQuery.error));
  }, [listQuery.error, toast]);

  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    setSelectedIds(new Set());
  }, [queryKey]);

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(total / pageSize));
  }, [total, pageSize]);

  const [reasonModalOpen, setReasonModalOpen] = useState(false);
  const [reasonModalTarget, setReasonModalTarget] =
    useState<ReasonModalTarget | null>(null);
  const [reasonTemplateDraft, setReasonTemplateDraft] = useState("");
  const [reasonDraft, setReasonDraft] = useState("");
  const [activeAction, setActiveAction] = useState<
    | {
        id?: number;
        kind:
          | "approve"
          | "reject"
          | "delete"
          | "batch-approve"
          | "batch-reject"
          | "batch-delete";
      }
    | null
  >(null);

  const closeReasonModal = () => {
    setReasonModalOpen(false);
    setReasonModalTarget(null);
    setReasonTemplateDraft("");
    setReasonDraft("");
  };

  const openReasonModal = (target: ReasonModalTarget) => {
    setReasonModalTarget(target);
    setReasonTemplateDraft("");
    setReasonDraft("");
    setReasonModalOpen(true);
  };

  const reviewMutation = useAppMutation<
    void,
    { commentId: number; action: ReviewAction; reason?: string | null }
  >({
    mutationFn: async (payload) => {
      await api.post(`/news/admin/comments/${payload.commentId}/review`, {
        action: payload.action,
        reason: payload.reason ?? null,
      });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onMutate: async (payload) => {
      setActiveAction({ id: payload.commentId, kind: payload.action });
    },
    onSuccess: async () => {
      closeReasonModal();
      await queryClient.invalidateQueries({
        queryKey: ["admin-news-comments"],
      });
    },
    onSettled: (_data, _err, payload) => {
      setActiveAction((prev) =>
        prev && prev.id === payload?.commentId ? null : prev
      );
    },
  });

  const batchReviewMutation = useAppMutation<
    BatchReviewResponse,
    { ids: number[]; action: ReviewAction; reason?: string | null }
  >({
    mutationFn: async (payload) => {
      const res = await api.post(`/news/admin/comments/review/batch`, {
        ids: payload.ids,
        action: payload.action,
        reason: payload.reason ?? null,
      });
      return res.data as BatchReviewResponse;
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onMutate: async (payload) => {
      setActiveAction({ kind: `batch-${payload.action}` as any });
    },
    onSuccess: async (data) => {
      closeReasonModal();
      setSelectedIds(new Set());
      if (data?.message) toast.success(data.message);
      await queryClient.invalidateQueries({
        queryKey: ["admin-news-comments"],
      });
    },
    onSettled: (_data, _err, payload) => {
      setActiveAction((prev) =>
        prev && prev.kind === `batch-${payload?.action}` ? null : prev
      );
    },
  });

  const actionBusy = reviewMutation.isPending || batchReviewMutation.isPending;

  const handleReview = (commentId: number, action: ReviewAction) => {
    if (reviewMutation.isPending) return;

    if (action === "approve") {
      reviewMutation.mutate({ commentId, action, reason: null });
      return;
    }

    openReasonModal({ mode: "single", commentId, action });
  };

  const handleBatchReview = (action: ReviewAction) => {
    if (batchReviewMutation.isPending) return;
    if (reviewMutation.isPending) return;
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    if (action === "approve") {
      batchReviewMutation.mutate({ ids, action, reason: null });
      return;
    }

    openReasonModal({ mode: "batch", commentIds: ids, action });
  };

  const handleConfirmReasonModal = () => {
    if (!reasonModalTarget) return;
    if (reviewMutation.isPending || batchReviewMutation.isPending) return;

    const reason = reasonDraft.trim() ? reasonDraft.trim() : null;

    if (reasonModalTarget.mode === "single") {
      reviewMutation.mutate({
        commentId: reasonModalTarget.commentId,
        action: reasonModalTarget.action,
        reason,
      });
      return;
    }

    batchReviewMutation.mutate({
      ids: reasonModalTarget.commentIds,
      action: reasonModalTarget.action,
      reason,
    });
  };

  const modalTitle = reasonModalTarget
    ? reasonModalTarget.action === "delete"
      ? "删除评论"
      : "驳回评论"
    : "操作";

  const modalDescription = reasonModalTarget
    ? reasonModalTarget.action === "delete"
      ? "删除后将对用户不可见。建议填写原因。"
      : "驳回后将对用户不可见。建议填写原因。"
    : undefined;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            新闻评论
          </h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">
            审核与管理新闻评论
          </p>
        </div>
        <Button
          variant="outline"
          icon={RotateCcw}
          isLoading={listQuery.isFetching}
          loadingText="刷新中..."
          disabled={listQuery.isFetching || actionBusy}
          onClick={() => {
            if (actionBusy) return;
            listQuery.refetch();
          }}
        >
          刷新
        </Button>
      </div>

      <Card variant="surface" padding="md">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between mb-6">
          <div className="flex flex-1 flex-col gap-3 md:flex-row md:items-center">
            <div className="w-full md:max-w-md">
              <Input
                icon={Search}
                value={keyword}
                onChange={(e) => {
                  if (actionBusy) return;
                  setKeyword(e.target.value);
                  setPage(1);
                }}
                placeholder="搜索评论内容..."
                disabled={actionBusy}
              />
            </div>

            <select
              value={reviewStatus}
              onChange={(e) => {
                if (actionBusy) return;
                setReviewStatus(e.target.value);
                setPage(1);
              }}
              disabled={actionBusy}
              className="px-4 py-2 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            >
              <option value="pending">待审核</option>
              <option value="approved">已通过</option>
              <option value="rejected">已驳回</option>
              <option value="all">全部</option>
            </select>

            <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-white/70 select-none">
              <input
                type="checkbox"
                checked={includeDeleted}
                onChange={(e) => {
                  if (actionBusy) return;
                  setIncludeDeleted(e.target.checked);
                  setPage(1);
                }}
                disabled={actionBusy}
              />
              包含已删除
            </label>
          </div>
        </div>

        {listQuery.isLoading && items.length === 0 ? (
          <ListSkeleton count={6} />
        ) : (
          <>
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm text-slate-600 dark:text-white/60">
                已选 {selectedIds.size} 条
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="admin-news-comment-batch-approve"
                  aria-label="admin-news-comment-batch-approve"
                  onClick={() => handleBatchReview("approve")}
                  isLoading={
                    batchReviewMutation.isPending &&
                    activeAction?.kind === "batch-approve"
                  }
                  loadingText="处理中..."
                  disabled={
                    selectedIds.size === 0 ||
                    actionBusy
                  }
                >
                  批量通过
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="admin-news-comment-batch-reject"
                  aria-label="admin-news-comment-batch-reject"
                  onClick={() => handleBatchReview("reject")}
                  isLoading={
                    batchReviewMutation.isPending &&
                    activeAction?.kind === "batch-reject"
                  }
                  loadingText="处理中..."
                  disabled={
                    selectedIds.size === 0 ||
                    actionBusy
                  }
                >
                  批量驳回
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-400 hover:text-red-300"
                  data-testid="admin-news-comment-batch-delete"
                  aria-label="admin-news-comment-batch-delete"
                  onClick={() => handleBatchReview("delete")}
                  isLoading={
                    batchReviewMutation.isPending &&
                    activeAction?.kind === "batch-delete"
                  }
                  loadingText="处理中..."
                  disabled={
                    selectedIds.size === 0 ||
                    actionBusy
                  }
                >
                  批量删除
                </Button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200/70 dark:border-white/10">
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                      <input
                        type="checkbox"
                        data-testid="admin-news-comment-select-all"
                        aria-label="admin-news-comment-select-all"
                        checked={items.length > 0 && items.every((x) => selectedIds.has(x.id))}
                        disabled={actionBusy}
                        onChange={() => {
                          if (actionBusy) return;
                          const ids = items.map((x) => x.id);
                          setSelectedIds((prev) => {
                            const next = new Set(prev);
                            const all = ids.length > 0 && ids.every((id) => next.has(id));
                            if (all) ids.forEach((id) => next.delete(id));
                            else ids.forEach((id) => next.add(id));
                            return next;
                          });
                        }}
                      />
                    </th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">评论</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">新闻</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">用户</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">状态</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">时间</th>
                    <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td
                        colSpan={7}
                        className="py-10 text-center text-slate-500 dark:text-white/50"
                      >
                        暂无数据
                      </td>
                    </tr>
                  ) : (
                    items.map((c) => {
                      const status = normalizeStatus(c.review_status);
                      const { label, variant } = getStatusBadgeVariant(
                        status,
                        !!c.is_deleted
                      );
                      const authorName =
                        c.author?.nickname ||
                        c.author?.username ||
                        String(c.user_id);
                      const newsTitle = c.news?.title || `新闻 #${c.news_id}`;
                      const content = String(c.content || "");

                      const approveLoading =
                        reviewMutation.isPending &&
                        activeAction?.id === c.id &&
                        activeAction?.kind === "approve";
                      const rejectLoading =
                        reviewMutation.isPending &&
                        activeAction?.id === c.id &&
                        activeAction?.kind === "reject";
                      const deleteLoading =
                        reviewMutation.isPending &&
                        activeAction?.id === c.id &&
                        activeAction?.kind === "delete";
                      const disableOther = actionBusy && activeAction?.id !== c.id;
                      const rowBusy = actionBusy && activeAction?.id === c.id;

                      return (
                        <tr
                          key={c.id}
                          data-testid={`admin-news-comment-${c.id}`}
                          className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5"
                        >
                          <td className="py-4 px-4">
                            <input
                              type="checkbox"
                              data-testid={`admin-news-comment-select-${c.id}`}
                              aria-label={`admin-news-comment-select-${c.id}`}
                              checked={selectedIds.has(c.id)}
                              disabled={actionBusy}
                              onChange={() => {
                                if (actionBusy) return;
                                setSelectedIds((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(c.id)) next.delete(c.id);
                                  else next.add(c.id);
                                  return next;
                                });
                              }}
                            />
                          </td>
                          <td className="py-4 px-4">
                            <div className="max-w-xl">
                              <div className="text-slate-900 dark:text-white whitespace-pre-wrap line-clamp-3">
                                {content}
                              </div>
                              {c.review_reason ? (
                                <div className="mt-2 text-xs text-slate-500 dark:text-white/50">
                                  原因：{c.review_reason}
                                </div>
                              ) : null}
                            </div>
                          </td>
                          <td className="py-4 px-4">
                            <a
                              className="text-amber-700 hover:underline dark:text-amber-400"
                              href={`/news/${c.news_id}`}
                              target="_blank"
                              rel="noreferrer"
                              title={newsTitle}
                            >
                              <span className="line-clamp-2 max-w-xs">
                                {newsTitle}
                              </span>
                            </a>
                          </td>
                          <td className="py-4 px-4 text-slate-700 dark:text-white/70">
                            {authorName}
                          </td>
                          <td className="py-4 px-4">
                            <Badge variant={variant} size="sm">
                              {label}
                            </Badge>
                          </td>
                          <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                            {new Date(c.created_at).toLocaleString()}
                          </td>
                          <td className="py-4 px-4">
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                className={approveLoading ? "px-3 py-2" : "p-2"}
                                title="通过"
                                aria-label={`admin-news-comment-approve-${c.id}`}
                                data-testid={`admin-news-comment-approve-${c.id}`}
                                isLoading={approveLoading}
                                loadingText="处理中..."
                                disabled={(rowBusy && !approveLoading) || disableOther}
                                onClick={() => handleReview(c.id, "approve")}
                              >
                                <Check className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className={rejectLoading ? "px-3 py-2" : "p-2"}
                                title="驳回"
                                aria-label={`admin-news-comment-reject-${c.id}`}
                                data-testid={`admin-news-comment-reject-${c.id}`}
                                isLoading={rejectLoading}
                                loadingText="处理中..."
                                disabled={(rowBusy && !rejectLoading) || disableOther}
                                onClick={() => handleReview(c.id, "reject")}
                              >
                                <XCircle className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className={`${deleteLoading ? 'px-3 py-2' : 'p-2'} text-red-400 hover:text-red-300`}
                                title="删除"
                                aria-label={`admin-news-comment-delete-${c.id}`}
                                data-testid={`admin-news-comment-delete-${c.id}`}
                                isLoading={deleteLoading}
                                loadingText="处理中..."
                                disabled={(rowBusy && !deleteLoading) || disableOther}
                                onClick={() => handleReview(c.id, "delete")}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            <Pagination
              currentPage={page}
              totalPages={totalPages}
              onPageChange={(p) => {
                if (actionBusy) return;
                setPage(Math.max(1, p));
              }}
              className="mt-6"
            />
          </>
        )}
      </Card>

      <Modal
        isOpen={reasonModalOpen}
        onClose={() => {
          if (actionBusy) return;
          closeReasonModal();
        }}
        title={modalTitle}
        description={modalDescription}
      >
        <div className="space-y-4">
          <div>
            <p className="text-sm text-slate-700 dark:text-white/70 mb-2">
              原因模板
            </p>
            <select
              value={reasonTemplateDraft}
              onChange={(e) => {
                const v = e.target.value;
                setReasonTemplateDraft(v);
                if (!v) return;
                setReasonDraft((prev) => {
                  const prevText = String(prev || "");
                  if (!prevText.trim()) return v;
                  if (prevText.includes(v)) return prevText;
                  return `${prevText.trim()}\n${v}`;
                });
              }}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            >
              <option value="">选择模板...</option>
              {REVIEW_REASON_TEMPLATES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div>
            <p className="text-sm text-slate-700 dark:text-white/70 mb-2">
              原因（可选）
            </p>
            <Textarea
              value={reasonDraft}
              onChange={(e) => setReasonDraft(e.target.value)}
              rows={4}
              placeholder="可填写驳回/删除原因（将同步通知给用户）"
              disabled={actionBusy}
            />
          </div>

          <ModalActions className="pt-2">
            <Button
              variant="ghost"
              onClick={closeReasonModal}
              disabled={actionBusy}
            >
              取消
            </Button>
            <Button
              onClick={handleConfirmReasonModal}
              isLoading={actionBusy}
              loadingText="处理中..."
              disabled={actionBusy}
            >
              确认
            </Button>
          </ModalActions>
        </div>
      </Modal>
    </div>
  );
}
