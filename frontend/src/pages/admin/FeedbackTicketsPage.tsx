import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MessageSquare, RefreshCw, Send } from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Modal,
  Pagination,
  Textarea,
  ListSkeleton,
  Skeleton,
} from "../../components/ui";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import { queryKeys } from "../../queryKeys";

type FeedbackTicketItem = {
  id: number;
  user_id: number;
  subject: string;
  content: string;
  status: string;
  admin_reply: string | null;
  admin_id: number | null;
  created_at: string;
  updated_at: string;
};

type FeedbackTicketListResponse = {
  items: FeedbackTicketItem[];
  total: number;
  page: number;
  page_size: number;
};

function statusToBadgeVariant(
  status: string
): "default" | "primary" | "success" | "warning" | "danger" | "info" {
  const s = String(status || "").toLowerCase();
  if (s === "open") return "warning";
  if (s === "processing") return "info";
  if (s === "closed") return "success";
  return "default";
}

function statusToLabel(status: string): string {
  const s = String(status || "").toLowerCase();
  if (s === "open") return "待处理";
  if (s === "processing") return "处理中";
  if (s === "closed") return "已关闭";
  return status || "未知";
}

function normalizeStatus(
  value: string | null | undefined
): "" | "open" | "processing" | "closed" {
  const s = String(value || "")
    .trim()
    .toLowerCase();
  if (s === "open" || s === "processing" || s === "closed") return s;
  return "";
}

export default function FeedbackTicketsPage() {
  const toast = useToast();

  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [statusFilter, setStatusFilter] = useState<
    "" | "open" | "processing" | "closed"
  >("");
  const [keyword, setKeyword] = useState("");

  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<FeedbackTicketItem | null>(null);
  const [reply, setReply] = useState("");
  const [nextStatus, setNextStatus] = useState<
    "" | "open" | "processing" | "closed"
  >("");

  const listQuery = useQuery({
    queryKey: queryKeys.adminFeedbackTickets(
      page,
      pageSize,
      statusFilter || null,
      keyword.trim() || null
    ),
    queryFn: async () => {
      const res = await api.get("/feedback/admin/tickets", {
        params: {
          page,
          page_size: pageSize,
          ...(statusFilter ? { status: statusFilter } : {}),
          ...(keyword.trim() ? { keyword: keyword.trim() } : {}),
        },
      });
      const data = res.data || {};
      return {
        items: Array.isArray(data?.items)
          ? (data.items as FeedbackTicketItem[])
          : ([] as FeedbackTicketItem[]),
        total: Number(data?.total || 0),
        page: Number(data?.page || page),
        page_size: Number(data?.page_size || pageSize),
      } satisfies FeedbackTicketListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!listQuery.error) return;
    toast.error(getApiErrorMessage(listQuery.error, "加载失败，请稍后重试"));
  }, [listQuery.error, toast]);

  const updateMutation = useAppMutation<
    FeedbackTicketItem,
    { id: number; status: string | null; admin_reply: string | null }
  >({
    mutationFn: async ({ id, status, admin_reply }) => {
      const res = await api.put(`/feedback/admin/tickets/${id}`, {
        ...(status !== null ? { status } : {}),
        ...(admin_reply !== null ? { admin_reply } : {}),
      });
      return res.data as FeedbackTicketItem;
    },
    successMessage: "已更新",
    errorMessageFallback: "更新失败，请稍后重试",
    invalidateQueryKeys: [queryKeys.adminFeedbackTicketsRoot()],
    onSuccess: () => {
      setEditOpen(false);
      setEditing(null);
      setReply("");
      setNextStatus("");
    },
  });

  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total]
  );

  const openEdit = (t: FeedbackTicketItem) => {
    setEditing(t);
    setReply(String(t.admin_reply || ""));
    setNextStatus(normalizeStatus(t.status));
    setEditOpen(true);
  };

  const closeEdit = () => {
    setEditOpen(false);
    setEditing(null);
    setReply("");
    setNextStatus("");
  };

  if (listQuery.isLoading && items.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <Skeleton width="120px" height="20px" />
            <div className="mt-2">
              <Skeleton width="240px" height="14px" />
            </div>
          </div>
          <Skeleton width="90px" height="36px" />
        </div>

        <Card variant="surface" padding="lg">
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {Array.from({ length: 4 }).map((_, idx) => (
              <Skeleton key={idx} width="64px" height="32px" />
            ))}
            <div className="flex-1" />
            <Skeleton width="220px" height="40px" />
          </div>
          <ListSkeleton count={4} />
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-white">
            客服反馈工单
          </h1>
          <p className="text-sm text-slate-600 dark:text-white/50">
            查看与处理用户反馈（回复/更新状态）
          </p>
        </div>
        <Button
          variant="outline"
          icon={RefreshCw}
          onClick={() => listQuery.refetch()}
          isLoading={listQuery.isFetching}
          loadingText="刷新中..."
          disabled={listQuery.isFetching}
        >
          刷新
        </Button>
      </div>

      <Card variant="surface" padding="lg">
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <Button
            variant={statusFilter === "" ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              setPage(1);
              setStatusFilter("");
            }}
          >
            全部
          </Button>
          <Button
            variant={statusFilter === "open" ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              setPage(1);
              setStatusFilter("open");
            }}
          >
            待处理
          </Button>
          <Button
            variant={statusFilter === "processing" ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              setPage(1);
              setStatusFilter("processing");
            }}
          >
            处理中
          </Button>
          <Button
            variant={statusFilter === "closed" ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              setPage(1);
              setStatusFilter("closed");
            }}
          >
            已关闭
          </Button>

          <div className="flex-1" />

          <div className="w-full sm:w-72">
            <Input
              label="关键词"
              value={keyword}
              onChange={(e) => {
                setPage(1);
                setKeyword(e.target.value);
              }}
              placeholder="搜索标题/内容/回复"
            />
          </div>
        </div>

        {listQuery.isLoading && items.length === 0 ? (
          <ListSkeleton count={4} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="暂无工单"
            description="当前没有匹配的反馈工单"
          />
        ) : (
          <div className="space-y-4">
            {items.map((t) => (
              <Card
                key={t.id}
                variant="surface"
                padding="md"
                className="border border-slate-200/70 dark:border-white/10"
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-base font-semibold text-slate-900 dark:text-white truncate">
                        {t.subject}
                      </h3>
                      <Badge variant={statusToBadgeVariant(t.status)} size="sm">
                        {statusToLabel(t.status)}
                      </Badge>
                    </div>
                    <div className="mt-2 space-y-2 text-sm text-slate-600 dark:text-white/60">
                      <div>用户：#{t.user_id}</div>
                      <div>
                        提交时间：{new Date(t.created_at).toLocaleString()}
                      </div>
                      <div className="text-slate-700 dark:text-white/70 whitespace-pre-wrap">
                        {t.content}
                      </div>
                      {t.admin_reply ? (
                        <div className="rounded-xl bg-slate-50 border border-slate-200/70 p-3 dark:bg-white/5 dark:border-white/10">
                          <div className="text-xs text-slate-500 dark:text-white/50 mb-1">
                            客服回复
                          </div>
                          <div className="text-sm text-slate-800 dark:text-white/80 whitespace-pre-wrap">
                            {t.admin_reply}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 sm:flex-col sm:items-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEdit(t)}
                    >
                      处理
                    </Button>
                    <div className="text-xs text-slate-500 dark:text-white/40">
                      #{t.id}
                    </div>
                  </div>
                </div>
              </Card>
            ))}

            <div className="pt-4">
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                onPageChange={setPage}
              />
            </div>
          </div>
        )}
      </Card>

      <Modal
        isOpen={editOpen}
        onClose={() => {
          if (updateMutation.isPending) return
          closeEdit()
        }}
        title="处理工单"
        description={
          editing
            ? `工单 #${editing.id}（用户 #${editing.user_id}）`
            : undefined
        }
        size="lg"
      >
        {editing ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant={nextStatus === "open" ? "primary" : "outline"}
                size="sm"
                onClick={() => setNextStatus("open")}
                disabled={updateMutation.isPending}
              >
                待处理
              </Button>
              <Button
                variant={nextStatus === "processing" ? "primary" : "outline"}
                size="sm"
                onClick={() => setNextStatus("processing")}
                disabled={updateMutation.isPending}
              >
                处理中
              </Button>
              <Button
                variant={nextStatus === "closed" ? "primary" : "outline"}
                size="sm"
                onClick={() => setNextStatus("closed")}
                disabled={updateMutation.isPending}
              >
                已关闭
              </Button>
            </div>

            <Textarea
              label="回复内容"
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              rows={8}
              placeholder="填写客服回复"
              disabled={updateMutation.isPending}
            />

            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  if (updateMutation.isPending) return
                  closeEdit()
                }}
                disabled={updateMutation.isPending}
              >
                取消
              </Button>
              <Button
                icon={Send}
                isLoading={updateMutation.isPending}
                loadingText="保存中..."
                onClick={() => {
                  if (updateMutation.isPending) return
                  const s = nextStatus || null;
                  const r = reply.trim() ? reply.trim() : null;
                  updateMutation.mutate({
                    id: editing.id,
                    status: s,
                    admin_reply: r,
                  });
                }}
              >
                保存
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
