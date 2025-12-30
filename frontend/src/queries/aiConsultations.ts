import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { queryKeys } from '../queryKeys'

export interface ConsultationItem {
  id: number
  session_id: string
  title: string
  created_at: string
  message_count: number
}

export function useAiConsultationsQuery(enabled = true, q: string = '') {
  const queryKey = queryKeys.aiConsultations(q)
  const query = useQuery({
    queryKey,
    queryFn: async () => {
      const qNorm = String(q ?? '').trim()
      const res = await api.get('/ai/consultations', {
        params: qNorm ? { q: qNorm } : undefined,
      })
      return (Array.isArray(res.data) ? res.data : []) as ConsultationItem[]
    },
    enabled,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  return { queryKey, query }
}
