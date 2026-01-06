import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Plus, Send, RefreshCw } from "lucide-react";
import PageHeader from "../components/PageHeader";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ListSkeleton,
  Modal,
  Pagination,
  Textarea,
  Input,
} from "../components/ui";
import api from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useAppMutation, useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";
import { queryKeys } from "../queryKeys";

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

export default function FeedbackPage() {
  const { isAuthenticated } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [page, setPage] = useState(1);
  const pageSize = 10;

  const [createOpen, setCreateOpen] = useState(false);
  const [subject, setSubject] = useState("");
  const [content, setContent] = useState("");

  const listQuery = useQuery({
    queryKey: queryKeys.feedbackTickets(page, pageSize),
    queryFn: async () => {
      const res = await api.get("/feedback", {
        params: { page, page_size: pageSize },
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
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!listQuery.error) return;
    const status = (listQuery.error as any)?.response?.status;
    if (status === 401) return;
    toast.error(getApiErrorMessage(listQuery.error, "加载失败，请稍后重试"));
  }, [listQuery.error, toast]);

  const createMutation = useAppMutation<
    FeedbackTicketItem,
    { subject: string; content: string }
  >({
    mutationFn: async (payload) => {
      const res = await api.post("/feedback", payload);
      return res.data as FeedbackTicketItem;
    },
    successMessage: "提交成功",
    errorMessageFallback: "提交失败，请稍后重试",
    invalidateQueryKeys: [queryKeys.feedbackTicketsRoot()],
    onMutate: async (payload) => {
      if (page !== 1)
        return {
          previous: undefined as unknown,
          applied: false,
          tempId: undefined as unknown,
          queryKey: queryKeys.feedbackTickets(page, pageSize),
        };

      const queryKey = queryKeys.feedbackTickets(1, pageSize);
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<FeedbackTicketListResponse>(
        queryKey
      );

      const tempId = -Math.trunc(Date.now());
      const nowIso = new Date().toISOString();
      const optimistic: FeedbackTicketItem = {
        id: tempId,
        user_id: 0,
        subject: String(payload.subject ?? ""),
        content: String(payload.content ?? ""),
        status: "open",
        admin_reply: null,
        admin_id: null,
        created_at: nowIso,
        updated_at: nowIso,
      };

      queryClient.setQueryData<FeedbackTicketListResponse>(queryKey, (old) => {
        if (!old) return old as any;
        const nextItems = [optimistic, ...(old.items ?? [])].slice(0, pageSize);
        return {
          ...old,
          items: nextItems,
          total: Math.max(0, Number(old.total || 0) + 1),
        };
      });

      return { previous, tempId, applied: true, queryKey };
    },
    onSuccess: (data, _payload, ctx) => {
      setCreateOpen(false);
      setSubject("");
      setContent("");
      if (page !== 1) {
        setPage(1);
      }

      const anyCtx = ctx as any;
      if (anyCtx?.applied && anyCtx?.queryKey) {
        const targetKey = anyCtx.queryKey as any;
        const tempId = Number(anyCtx.tempId);
        queryClient.setQueryData<FeedbackTicketListResponse>(targetKey, (old) => {
          if (!old) return old as any;
          const items = Array.isArray(old.items) ? old.items : [];
          const idx = items.findIndex((it) => it.id === tempId);

          if (idx >= 0) {
            const nextItems = [...items];
            nextItems[idx] = data;
            return { ...old, items: nextItems };
          }

          return { ...old, items: [data, ...items].slice(0, pageSize) };
        });
      }
    },
    onError: (err, _payload, ctx) => {
      const anyCtx = ctx as any;
      if (anyCtx?.previous && anyCtx?.queryKey) {
        queryClient.setQueryData(anyCtx.queryKey, anyCtx.previous);
      }
      return err as any;
    },
  });

  const actionBusy = createMutation.isPending;

  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total]
  );

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="客服"
          title="反馈与工单"
          description="提交问题反馈并查看处理进度"
          layout="mdStart"
          tone={actualTheme}
        />
        <EmptyState
          icon={MessageSquare}
          title="请先登录"
          description="登录后即可提交与查看反馈工单"
          tone={actualTheme}
        />
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="客服"
        title="反馈与工单"
        description="提交问题反馈并查看处理进度"
        layout="mdStart"
        tone={actualTheme}
        right={
          <div className="flex gap-2">
            <Button
              variant="outline"
              icon={RefreshCw}
              isLoading={listQuery.isFetching}
              loadingText="刷新中..."
              onClick={() => listQuery.refetch()}
              disabled={listQuery.isFetching || actionBusy}
            >
              刷新
            </Button>
            <Button
              icon={Plus}
              onClick={() => {
                if (actionBusy) return;
                setCreateOpen(true);
              }}
              disabled={actionBusy}
            >
              新建工单
            </Button>
          </div>
        }
      />

      <Card variant="surface" padding="lg">
        {listQuery.isLoading && items.length === 0 ? (
          <ListSkeleton count={4} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="暂无工单"
            description="你提交的反馈会显示在这里"
            tone={actualTheme}
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
                <div className="flex items-start justify-between gap-4">
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

                  <div className="text-xs text-slate-500 dark:text-white/40 flex-shrink-0">
                    #{t.id}
                  </div>
                </div>
              </Card>
            ))}

            <div className="pt-4">
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                onPageChange={(p) => {
                  if (actionBusy) return;
                  setPage(p);
                }}
              />
            </div>
          </div>
        )}
      </Card>

      <Modal
        isOpen={createOpen}
        onClose={() => {
          if (createMutation.isPending) return;
          setCreateOpen(false);
        }}
        title="新建反馈工单"
        description="请尽量描述清楚问题与复现步骤"
        size="lg"
      >
        <div className="space-y-4">
          <Input
            label="标题"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="例如：支付页面打不开"
            disabled={createMutation.isPending}
          />
          <Textarea
            label="内容"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="请描述问题现象、复现步骤、期望结果等"
            rows={8}
            disabled={createMutation.isPending}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                if (createMutation.isPending) return;
                setCreateOpen(false);
              }}
              disabled={createMutation.isPending}
            >
              取消
            </Button>
            <Button
              icon={Send}
              isLoading={createMutation.isPending}
              loadingText="提交中..."
              disabled={createMutation.isPending}
              onClick={() => {
                if (createMutation.isPending) return;
                const s = subject.trim();
                const c = content.trim();
                if (!s) {
                  toast.error("请填写标题");
                  return;
                }
                if (!c) {
                  toast.error("请填写内容");
                  return;
                }
                createMutation.mutate({ subject: s, content: c });
              }}
            >
              提交
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
