import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { ThemeProvider } from './contexts/ThemeContext'
import { LanguageProvider } from './contexts/LanguageContext'
import './index.css'

const queryClient = new QueryClient({
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
