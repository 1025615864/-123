import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Check, Trash2, RefreshCw } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import PageHeader from '../components/PageHeader'
import { Button, Card, EmptyState, Loading, Pagination } from '../components/ui'
import api from '../api/client'
import { useToast } from '../hooks'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { getApiErrorMessage } from '../utils'
import { useNotificationsQuery, type NotificationsResponse } from '../queries/notifications'

export default function NotificationsPage() {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()
  const [page, setPage] = useState(1)
  const pageSize = 20

  const queryClient = useQueryClient()

  const { queryKey: notificationsQueryKey, query: notificationsQuery } = useNotificationsQuery(
    page,
    pageSize,
    isAuthenticated
  )

  useEffect(() => {
    if (!notificationsQuery.error) return
    toast.error(getApiErrorMessage(notificationsQuery.error))
  }, [notificationsQuery.error, toast])

  const items = notificationsQuery.data?.items ?? []
  const total = notificationsQuery.data?.total ?? 0
  const unreadCount = notificationsQuery.data?.unread_count ?? 0

  const markAsReadMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.put(`/notifications/${id}/read`, {})
      return id
    },
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: notificationsQueryKey })
      const previous = queryClient.getQueryData<NotificationsResponse>(notificationsQueryKey)

      queryClient.setQueryData<NotificationsResponse>(notificationsQueryKey, (old) => {
        if (!old) return old as any
        let decremented = 0
        const nextItems = old.items.map((n) => {
          if (n.id !== id) return n
          if (!n.is_read) decremented = 1
          return { ...n, is_read: true }
        })
        return { ...old, items: nextItems, unread_count: Math.max(0, old.unread_count - decremented) }
      })

      return { previous }
    },
    onError: (err, _id, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(notificationsQueryKey, ctx.previous)
      toast.error(getApiErrorMessage(err))
    },
  })

  const markAllAsReadMutation = useMutation({
    mutationFn: async () => {
      await api.put('/notifications/read-all', {})
    },
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: notificationsQueryKey })
      const previous = queryClient.getQueryData<NotificationsResponse>(notificationsQueryKey)
      queryClient.setQueryData<NotificationsResponse>(notificationsQueryKey, (old) => {
        if (!old) return old as any
        return { ...old, items: old.items.map((n) => ({ ...n, is_read: true })), unread_count: 0 }
      })
      return { previous }
    },
    onSuccess: () => {
      toast.success('已全部标记为已读')
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(notificationsQueryKey, ctx.previous)
      toast.error(getApiErrorMessage(err))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/notifications/${id}`)
      return id
    },
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: notificationsQueryKey })
      const previous = queryClient.getQueryData<NotificationsResponse>(notificationsQueryKey)
      queryClient.setQueryData<NotificationsResponse>(notificationsQueryKey, (old) => {
        if (!old) return old as any
        const removed = old.items.find((n) => n.id === id)
        const nextItems = old.items.filter((n) => n.id !== id)
        const nextUnread = removed && !removed.is_read ? Math.max(0, old.unread_count - 1) : old.unread_count
        const nextTotal = Math.max(0, old.total - 1)
        return { ...old, items: nextItems, total: nextTotal, unread_count: nextUnread }
      })
      return { previous }
    },
    onSuccess: () => {
      toast.success('已删除')
    },
    onError: (err, _id, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(notificationsQueryKey, ctx.previous)
      toast.error(getApiErrorMessage(err))
    },
  })

  const handleMarkAsRead = async (id: number) => {
    if (markAsReadMutation.isPending) return
    markAsReadMutation.mutate(id)
  }

  const handleMarkAllAsRead = async () => {
    if (markAllAsReadMutation.isPending) return
    markAllAsReadMutation.mutate()
  }

  const handleDelete = async (id: number) => {
    if (deleteMutation.isPending) return
    deleteMutation.mutate(id)
  }

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="通知"
          title="通知中心"
          description="查看系统通知与互动提醒"
          layout="mdStart"
          tone={actualTheme}
        />

        <EmptyState
          icon={Bell}
          title="请先登录"
          description="登录后即可查看你的通知消息"
          tone={actualTheme}
          action={
            <Link to="/login" className="mt-6 inline-block">
              <Button>去登录</Button>
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="通知"
        title="通知中心"
        description={`未读 ${unreadCount} 条`}
        layout="mdStart"
        tone={actualTheme}
        right={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => notificationsQuery.refetch()} disabled={notificationsQuery.isFetching}>
              <RefreshCw className={`h-4 w-4 mr-2 ${notificationsQuery.isFetching ? 'animate-spin' : ''}`} />
              刷新
            </Button>
            <Button
              variant="outline"
              onClick={handleMarkAllAsRead}
              disabled={notificationsQuery.isFetching || unreadCount === 0 || markAllAsReadMutation.isPending}
              icon={Check}
            >
              全部已读
            </Button>
          </div>
        }
      />

      {notificationsQuery.isLoading && items.length === 0 ? (
        <Loading text="加载中..." tone={actualTheme} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="暂无通知"
          description="你的通知会显示在这里"
          tone={actualTheme}
        />
      ) : (
        <Card variant="surface" padding="none">
          <div className="divide-y divide-slate-200/70 dark:divide-white/10">
            {items.map((n) => (
              <div
                key={n.id}
                className={`p-5 flex items-start gap-4 ${n.is_read ? '' : 'bg-amber-50/70 dark:bg-amber-500/5'}`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p
                        className={`text-sm truncate ${
                          n.is_read
                            ? 'text-slate-700 dark:text-white/80'
                            : 'text-slate-900 font-medium dark:text-white'
                        }`}
                      >
                        {n.title}
                      </p>
                      <p className="text-xs text-slate-500 mt-1 dark:text-white/40">
                        {new Date(n.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {!n.is_read && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-2"
                          title="标记已读"
                          onClick={() => handleMarkAsRead(n.id)}
                        >
                          <Check className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-2 hover:text-red-600 dark:hover:text-red-300"
                        title="删除"
                        onClick={() => handleDelete(n.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {n.content && (
                    <p className="text-sm text-slate-600 mt-3 whitespace-pre-wrap dark:text-white/60">{n.content}</p>
                  )}

                  {n.link && (
                    <a
                      className="inline-block text-sm text-amber-700 hover:underline mt-3 dark:text-amber-400"
                      href={n.link}
                      target="_blank"
                      rel="noreferrer"
                    >
                      查看链接
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>

          {total > pageSize && (
            <div className="p-5 border-t border-slate-200/70 dark:border-white/10">
              <Pagination
                currentPage={page}
                totalPages={Math.ceil(total / pageSize)}
                onPageChange={setPage}
              />
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
