import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Bell,
  Check,
  Trash2,
  MessageSquare,
  Heart,
  Bookmark,
  AlertCircle,
  Newspaper,
} from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { useToast } from "../hooks";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "./ui";
import { getApiErrorMessage } from "../utils";
import {
  useNotificationsPreviewQuery,
  type NotificationsPreviewResponse,
} from "../queries/notifications";

export default function NotificationBell({
  tone = "dark",
}: {
  tone?: "dark" | "light";
}) {
  const isLight = tone === "light";
  const [isOpen, setIsOpen] = useState(false);
  const { isAuthenticated } = useAuth();
  const toast = useToast();

  const queryClient = useQueryClient();

  const { queryKey: previewQueryKey, query: previewQuery } =
    useNotificationsPreviewQuery(10, isAuthenticated);

  const notifications = previewQuery.data?.items ?? [];
  const unreadCount = previewQuery.data?.unread_count ?? 0;

  const markAsReadMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.put(`/notifications/${id}/read`, {});
      return id;
    },
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: previewQueryKey });
      const previous =
        queryClient.getQueryData<NotificationsPreviewResponse>(previewQueryKey);

      queryClient.setQueryData<NotificationsPreviewResponse>(
        previewQueryKey,
        (old) => {
          if (!old) return old as any;
          let decremented = 0;
          const nextItems = old.items.map((n) => {
            if (n.id !== id) return n;
            if (!n.is_read) decremented = 1;
            return { ...n, is_read: true };
          });
          return {
            ...old,
            items: nextItems,
            unread_count: Math.max(0, old.unread_count - decremented),
          };
        }
      );

      return { previous };
    },
    onError: (err, _id, ctx) => {
      if (ctx?.previous)
        queryClient.setQueryData(previewQueryKey, ctx.previous);
      toast.error(getApiErrorMessage(err, "操作失败"));
    },
  });

  const markAllAsReadMutation = useMutation({
    mutationFn: async () => {
      await api.put("/notifications/read-all", {});
    },
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: previewQueryKey });
      const previous =
        queryClient.getQueryData<NotificationsPreviewResponse>(previewQueryKey);
      queryClient.setQueryData<NotificationsPreviewResponse>(
        previewQueryKey,
        (old) => {
          if (!old) return old as any;
          return {
            ...old,
            items: old.items.map((n) => ({ ...n, is_read: true })),
            unread_count: 0,
          };
        }
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("已全部标记为已读");
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous)
        queryClient.setQueryData(previewQueryKey, ctx.previous);
      toast.error(getApiErrorMessage(err, "操作失败"));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/notifications/${id}`);
      return id;
    },
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: previewQueryKey });
      const previous =
        queryClient.getQueryData<NotificationsPreviewResponse>(previewQueryKey);
      queryClient.setQueryData<NotificationsPreviewResponse>(
        previewQueryKey,
        (old) => {
          if (!old) return old as any;
          const removed = old.items.find((n) => n.id === id);
          const nextItems = old.items.filter((n) => n.id !== id);
          const nextUnread =
            removed && !removed.is_read
              ? Math.max(0, old.unread_count - 1)
              : old.unread_count;
          return { ...old, items: nextItems, unread_count: nextUnread };
        }
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("已删除");
    },
    onError: (err, _id, ctx) => {
      if (ctx?.previous)
        queryClient.setQueryData(previewQueryKey, ctx.previous);
      toast.error(getApiErrorMessage(err, "删除失败"));
    },
  });

  const handleMarkAsRead = async (id: number) => {
    if (markAsReadMutation.isPending) return;
    markAsReadMutation.mutate(id);
  };

  const handleMarkAllAsRead = async () => {
    if (markAllAsReadMutation.isPending) return;
    markAllAsReadMutation.mutate();
  };

  const handleDelete = async (id: number) => {
    if (deleteMutation.isPending) return;
    deleteMutation.mutate(id);
  };

  const getIcon = (type: string) => {
    switch (type) {
      case "comment_reply":
      case "post_comment":
        return <MessageSquare className="h-4 w-4 text-blue-400" />;
      case "post_like":
        return <Heart className="h-4 w-4 text-red-400" />;
      case "post_favorite":
        return <Bookmark className="h-4 w-4 text-amber-400" />;
      case "news":
        return <Newspaper className="h-4 w-4 text-amber-400" />;
      default:
        return (
          <AlertCircle
            className={`h-4 w-4 ${isLight ? "text-slate-500" : "text-white/50"}`}
          />
        );
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return "刚刚";
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 7) return `${days}天前`;
    return date.toLocaleDateString();
  };

  if (!isAuthenticated) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`relative p-2 rounded-full outline-none transition-all active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 ${
          isLight ? "hover:bg-slate-100" : "hover:bg-white/10"
        }`}
      >
        <Bell
          className={`h-5 w-5 ${isLight ? "text-slate-700" : "text-white/70"}`}
        />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-xs text-white flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div
            className={`absolute right-0 top-full mt-2 w-80 sm:w-96 rounded-xl shadow-xl z-50 overflow-hidden ${
              isLight
                ? "bg-white border border-slate-200"
                : "bg-[#1a1425] border border-white/10"
            }`}
          >
            <div
              className={`flex items-center justify-between px-4 py-3 border-b ${
                isLight ? "border-slate-200" : "border-white/10"
              }`}
            >
              <h3
                className={`font-semibold ${
                  isLight ? "text-slate-900" : "text-white"
                }`}
              >
                通知消息
              </h3>
              {unreadCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleMarkAllAsRead}
                  className={`text-xs ${
                    isLight
                      ? "text-emerald-700 hover:text-emerald-800"
                      : "text-amber-400 hover:text-amber-300"
                  }`}
                >
                  <Check className="h-3 w-3 mr-1" />
                  全部已读
                </Button>
              )}
            </div>

            <div className="max-h-80 overflow-y-auto">
              {notifications.length === 0 ? (
                <div
                  className={`py-12 text-center ${
                    isLight ? "text-slate-500" : "text-white/40"
                  }`}
                >
                  <Bell
                    className={`h-8 w-8 mx-auto mb-2 ${
                      isLight ? "text-slate-400" : "opacity-50"
                    }`}
                  />
                  <p>暂无通知</p>
                </div>
              ) : (
                notifications.map((notification) => (
                  <div
                    key={notification.id}
                    className={`px-4 py-3 border-b transition-colors ${
                      isLight
                        ? `border-slate-100 hover:bg-slate-50 ${
                            !notification.is_read ? "bg-emerald-50" : ""
                          }`
                        : `border-white/5 hover:bg-white/5 ${
                            !notification.is_read ? "bg-amber-500/5" : ""
                          }`
                    }`}
                  >
                    <div className="flex gap-3">
                      <div className="flex-shrink-0 mt-1">
                        {getIcon(notification.type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p
                          className={`text-sm ${
                            notification.is_read
                              ? isLight
                                ? "text-slate-700"
                                : "text-white/70"
                              : isLight
                              ? "text-slate-900 font-medium"
                              : "text-white font-medium"
                          }`}
                        >
                          {notification.title}
                        </p>
                        {notification.content && (
                          <p
                            className={`text-xs mt-1 line-clamp-2 ${
                              isLight ? "text-slate-600" : "text-white/50"
                            }`}
                          >
                            {notification.content}
                          </p>
                        )}
                        <div className="flex items-center justify-between mt-2">
                          <span
                            className={`text-xs ${
                              isLight ? "text-slate-500" : "text-white/40"
                            }`}
                          >
                            {formatTime(notification.created_at)}
                          </span>
                          <div className="flex gap-1">
                            {!notification.is_read && (
                              <button
                                onClick={() =>
                                  handleMarkAsRead(notification.id)
                                }
                                className={`p-1 rounded outline-none transition-all active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 ${
                                  isLight
                                    ? "hover:bg-slate-100 text-slate-400 hover:text-slate-700"
                                    : "hover:bg-white/10 text-white/40 hover:text-white/70"
                                }`}
                                title="标记已读"
                              >
                                <Check className="h-3 w-3" />
                              </button>
                            )}
                            <button
                              onClick={() => handleDelete(notification.id)}
                              className={`p-1 rounded outline-none transition-all active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 ${
                                isLight
                                  ? "hover:bg-slate-100 text-slate-400 hover:text-red-600"
                                  : "hover:bg-white/10 text-white/40 hover:text-red-400"
                              }`}
                              title="删除"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {notifications.length > 0 && (
              <div
                className={`px-4 py-2 border-t text-center ${
                  isLight ? "border-slate-200" : "border-white/10"
                }`}
              >
                <Link
                  to="/notifications"
                  className={`text-sm outline-none rounded-md transition-all active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 ${
                    isLight
                      ? "text-emerald-700 hover:text-emerald-800"
                      : "text-amber-400 hover:text-amber-300"
                  }`}
                  onClick={() => setIsOpen(false)}
                >
                  查看全部通知
                </Link>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
