import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MessageSquareText, Send } from "lucide-react";
import api from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { useAppMutation, useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";
import { Button, Loading, Modal, Textarea } from "./ui";

type MessageItem = {
  id: number;
  consultation_id: number;
  sender_user_id: number;
  sender_role: string;
  sender_name?: string | null;
  content: string;
  created_at: string;
};

type MessageListResponse = {
  items: MessageItem[];
  total: number;
  page: number;
  page_size: number;
};

export interface LawyerConsultationMessagesModalProps {
  isOpen: boolean;
  onClose: () => void;
  consultationId: number | null;
  title?: string;
}

function fmtMaybeDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString();
}

export default function LawyerConsultationMessagesModal({
  isOpen,
  onClose,
  consultationId,
  title,
}: LawyerConsultationMessagesModalProps) {
  const { user } = useAuth();
  const toast = useToast();

  const [draft, setDraft] = useState("");

  const queryKey = useMemo(
    () => ["lawfirm-consultation-messages", { consultationId }] as const,
    [consultationId]
  );

  const listQuery = useQuery({
    queryKey,
    enabled: isOpen && typeof consultationId === "number" && consultationId > 0,
    queryFn: async () => {
      const id = Number(consultationId);
      const res = await api.get(`/lawfirm/consultations/${id}/messages`, {
        params: { page: 1, page_size: 200 },
      });
      const data = res.data || {};
      return {
        items: Array.isArray(data?.items) ? (data.items as MessageItem[]) : [],
        total: Number(data?.total || 0),
        page: Number(data?.page || 1),
        page_size: Number(data?.page_size || 200),
      } satisfies MessageListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!isOpen) {
      setDraft("");
    }
  }, [isOpen]);

  useEffect(() => {
    if (!listQuery.error) return;
    const status = (listQuery.error as any)?.response?.status;
    if (status === 401) return;
    toast.error(getApiErrorMessage(listQuery.error, "留言加载失败，请稍后重试"));
  }, [listQuery.error, toast]);

  const sendMutation = useAppMutation<MessageItem, void>({
    mutationFn: async () => {
      if (typeof consultationId !== "number") {
        throw new Error("invalid consultation id");
      }
      const id = Number(consultationId);
      const content = String(draft || "").trim();
      const res = await api.post(`/lawfirm/consultations/${id}/messages`, {
        content,
      });
      return (res.data || {}) as MessageItem;
    },
    errorMessageFallback: "发送失败，请稍后重试",
    onSuccess: async () => {
      setDraft("");
      await listQuery.refetch();
    },
  });

  const items = listQuery.data?.items ?? [];
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    window.setTimeout(() => {
      bottomRef.current?.scrollIntoView({ block: "end" });
    }, 50);
  }, [isOpen, items.length]);

  const canSend = String(draft || "").trim().length > 0;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title || "咨询留言"}
      description="与对方沟通（非实时）"
      size="lg"
    >
      {listQuery.isLoading ? (
        <Loading text="加载中..." />
      ) : (
        <div className="space-y-4">
          {items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200/70 p-6 text-sm text-slate-600 dark:border-white/10 dark:text-white/60">
              <div className="flex items-center gap-2">
                <MessageSquareText className="h-5 w-5" />
                暂无留言，开始和对方沟通吧。
              </div>
            </div>
          ) : (
            <div className="space-y-3 max-h-[55vh] overflow-y-auto pr-1">
              {items.map((m) => {
                const mine = typeof user?.id === "number" && Number(m.sender_user_id) === Number(user.id);
                const bubble = mine
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 text-slate-900 dark:bg-white/5 dark:text-white";
                const wrap = mine ? "justify-end" : "justify-start";
                return (
                  <div key={m.id} className={`flex ${wrap}`}>
                    <div className="max-w-[85%]">
                      <div
                        className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${bubble}`}
                      >
                        <div className="whitespace-pre-wrap break-words">{m.content}</div>
                      </div>
                      <div
                        className={`mt-1 text-xs text-slate-500 dark:text-white/45 ${
                          mine ? "text-right" : "text-left"
                        }`}
                      >
                        {m.sender_name ? `${m.sender_name} · ` : ""}
                        {fmtMaybeDate(m.created_at)}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>
          )}

          <div className="pt-2 border-t border-slate-200/70 dark:border-white/10">
            <div className="flex flex-col gap-3">
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="输入留言内容..."
                rows={3}
              />
              <div className="flex items-center justify-end">
                <Button
                  variant="primary"
                  size="sm"
                  icon={Send}
                  isLoading={sendMutation.isPending}
                  disabled={!canSend || sendMutation.isPending}
                  onClick={() => {
                    if (!canSend || sendMutation.isPending) return;
                    sendMutation.mutate();
                  }}
                >
                  发送
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
