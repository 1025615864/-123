import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as Sentry from '@sentry/react'
import App from './App'
import { ThemeProvider } from './contexts/ThemeContext'
import { LanguageProvider } from './contexts/LanguageContext'
import { emitToast } from './hooks/useToast'
import './index.css'

import { getApiErrorMessage } from './utils'

const toastDedupe = new Map<string, number>()

const sentryDsn = (import.meta.env.VITE_SENTRY_DSN ?? '') as string
if (sentryDsn && sentryDsn.trim()) {
  const env = (import.meta.env.VITE_SENTRY_ENVIRONMENT ?? '') as string
  const release = (import.meta.env.VITE_SENTRY_RELEASE ?? '') as string
  const tracesRaw = (import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? '0') as string
  let traces = 0
  try {
    traces = Math.max(0, Math.min(1, Number(tracesRaw)))
  } catch {
    traces = 0
  }

  Sentry.init({
    dsn: sentryDsn,
    environment: env && env.trim() ? env.trim() : undefined,
    release: release && release.trim() ? release.trim() : undefined,
    tracesSampleRate: traces,
  })
}

function emitToastDeduped(type: 'success' | 'error' | 'info' | 'warning', message: string, dedupeMs = 2500) {
  const key = `${type}:${message}`
  const now = Date.now()
  const last = toastDedupe.get(key) ?? 0
  if (now - last < dedupeMs) return
  toastDedupe.set(key, now)
  emitToast(type, message)
}

function handleGlobalApiError(err: unknown, fallback: string) {
  const anyErr = err as any
  const status: number | undefined = anyErr?.response?.status

  if (status === 401) {
    emitToastDeduped('warning', '登录已失效，请重新登录')
    return
  }

  const msgRaw = String(anyErr?.message ?? '')
  if (!anyErr?.response && msgRaw) {
    const lower = msgRaw.toLowerCase()
    if (
      lower.includes('network error') ||
      lower.includes('failed to fetch') ||
      lower.includes('timeout') ||
      lower.includes('ecconnaborted')
    ) {
      emitToastDeduped('error', '网络异常，请检查网络后重试')
      return
    }
  }

  emitToastDeduped('error', getApiErrorMessage(err, fallback))
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      const meta = (query as any)?.meta
      if (meta?.disableGlobalErrorToast === true) return
      handleGlobalApiError(error, '请求失败，请稍后重试')
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      const meta = (mutation as any)?.options?.meta
      if (meta?.disableGlobalErrorToast === true) return
      handleGlobalApiError(error, '操作失败，请稍后重试')
    },
  }),
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5分钟内不重新请求
      gcTime: 10 * 60 * 1000, // 10分钟后垃圾回收
    },
    mutations: {
      retry: 0,
    },
  },
})

if (import.meta.env.DEV && localStorage.getItem('trace_hook_deps_warning') === '1') {
  const originalConsoleError = console.error
  console.error = (...args: any[]) => {
    try {
      const first = String(args?.[0] ?? '')
      if (first.includes('final argument passed') && first.includes('changed size')) {
        originalConsoleError('[hook-deps-warning] url:', window.location.href)
        originalConsoleError('[hook-deps-warning] args:', ...args)
        originalConsoleError('[hook-deps-warning] stack:', new Error('hook-deps-warning').stack)
      }
    } catch {
    }
    originalConsoleError(...args)
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <LanguageProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </LanguageProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
