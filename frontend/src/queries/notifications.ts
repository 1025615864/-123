import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { queryKeys } from '../queryKeys'

export interface NotificationItem {
  id: number
  type: string
  title: string
  content: string | null
  link: string | null
  is_read: boolean
  related_user_id?: number | null
  related_user_name?: string | null
  created_at: string
}

export interface NotificationsResponse {
  items: NotificationItem[]
  total: number
  unread_count: number
}

export interface NotificationsPreviewResponse {
  items: NotificationItem[]
  unread_count: number
}

export interface SystemNotification {
  id: number
  title: string
  content: string | null
  link: string | null
  created_at: string
}

export function useNotificationsQuery(page: number, pageSize: number, enabled: boolean) {
  const queryKey = queryKeys.notifications(page, pageSize)
  const query = useQuery({
    queryKey,
    queryFn: async () => {
      const res = await api.get(`/notifications?page=${page}&page_size=${pageSize}`)
      const data = res.data as NotificationsResponse
      return {
        items: Array.isArray(data?.items) ? data.items : [],
        total: Number(data?.total || 0),
        unread_count: Number(data?.unread_count || 0),
      } as NotificationsResponse
    },
    enabled,
    placeholderData: (prev) => prev,
    retry: 1,
    refetchOnWindowFocus: false,
  })

  return { queryKey, query }
}

export function useNotificationsPreviewQuery(pageSize: number, enabled: boolean) {
  const queryKey = queryKeys.notificationsPreview(pageSize)
  const query = useQuery({
    queryKey,
    queryFn: async () => {
      const res = await api.get(`/notifications?page_size=${pageSize}`)
      const data = res.data as NotificationsPreviewResponse
      return {
        items: Array.isArray(data?.items) ? data.items : [],
        unread_count: Number(data?.unread_count || 0),
      } as NotificationsPreviewResponse
    },
    enabled,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
    refetchInterval: 30000,
  })

  return { queryKey, query }
}

export function useAdminSystemNotificationsQuery() {
  const queryKey = queryKeys.adminSystemNotifications()
  const query = useQuery({
    queryKey,
    queryFn: async () => {
      const res = await api.get('/notifications/admin/system')
      const items = res.data?.items ?? []
      return (Array.isArray(items) ? items : []) as SystemNotification[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
  })

  return { queryKey, query }
}
