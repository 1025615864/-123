import { useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { QueryKey } from '@tanstack/react-query'

type QueryFn<TData> = () => Promise<TData>

export interface PrefetchLimiterOptions {
  maxInFlight?: number
  freshMs?: number
}

export interface PrefetchRequest<TData> {
  queryKey: QueryKey
  queryFn: QueryFn<TData>
}

export function usePrefetchLimiter(options: PrefetchLimiterOptions = {}) {
  const queryClient = useQueryClient()
  const inFlightRef = useRef(0)

  const maxInFlight = options.maxInFlight ?? 4
  const freshMs = options.freshMs ?? 5 * 60 * 1000

  const prefetch = useCallback(
    <TData,>({ queryKey, queryFn }: PrefetchRequest<TData>) => {
      if (inFlightRef.current >= maxInFlight) return

      const state = queryClient.getQueryState(queryKey)
      if (state?.fetchStatus === 'fetching') return
      if (state?.status === 'success' && Date.now() - (state.dataUpdatedAt || 0) < freshMs) return

      inFlightRef.current += 1

      queryClient
        .prefetchQuery({
          queryKey,
          queryFn,
        })
        .finally(() => {
          inFlightRef.current = Math.max(0, inFlightRef.current - 1)
        })
    },
    [freshMs, maxInFlight, queryClient]
  )

  return { prefetch }
}
