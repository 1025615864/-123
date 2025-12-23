import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { queryKeys } from '../queryKeys'

export interface NewsSubscriptionItem {
  id: number
  sub_type: 'category' | 'keyword'
  value: string
  created_at: string
}

export function useNewsSubscriptionsQuery(enabled: boolean) {
  const queryKey = queryKeys.newsSubscriptions()
  const query = useQuery({
    queryKey,
    queryFn: async () => {
      const res = await api.get('/news/subscriptions')
      return (Array.isArray(res.data) ? res.data : []) as NewsSubscriptionItem[]
    },
    enabled,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  return { queryKey, query }
}
