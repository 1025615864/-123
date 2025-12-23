import { createContext, useContext, useState, useCallback, ReactNode, useEffect, useMemo, useRef } from 'react'
import { X, CheckCircle2, AlertCircle, Info, AlertTriangle } from 'lucide-react'

type ToastType = 'success' | 'error' | 'info' | 'warning'

interface Toast {
  id: string
  type: ToastType
  message: string
  leaving: boolean
  paused: boolean
}

interface ToastContextType {
  showToast: (type: ToastType, message: string) => void
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
  warning: (message: string) => void
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const toastDurationMs = 5000
  const toastExitMs = 220

  const timersRef = useRef(
    new Map<
      string,
      {
        timeoutId: number | null
        startAt: number
        remainingMs: number
      }
    >()
  )

  useEffect(() => {
    return () => {
      timersRef.current.forEach((t) => {
        if (t.timeoutId != null) window.clearTimeout(t.timeoutId)
      })
      timersRef.current.clear()
    }
  }, [])

  const scheduleRemove = useCallback((id: string, delayMs: number) => {
    const existing = timersRef.current.get(id)
    if (existing?.timeoutId != null) {
      window.clearTimeout(existing.timeoutId)
    }
    const now = Date.now()
    timersRef.current.set(id, {
      timeoutId: window.setTimeout(() => {
        triggerRemove(id)
      }, Math.max(0, delayMs)),
      startAt: now,
      remainingMs: Math.max(0, delayMs),
    })
  }, [])

  const triggerRemove = useCallback((id: string) => {
    const t = timersRef.current.get(id)
    if (t?.timeoutId != null) window.clearTimeout(t.timeoutId)
    timersRef.current.delete(id)
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)))
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id))
    }, toastExitMs)
  }, [toastExitMs])

  const showToast = useCallback((type: ToastType, message: string) => {
    const id = Math.random().toString(36).substring(7)
    setToasts((prev) => [...prev, { id, type, message, leaving: false, paused: false }])

    scheduleRemove(id, Math.max(0, toastDurationMs - toastExitMs))
  }, [scheduleRemove, toastDurationMs, toastExitMs])

  const success = useCallback((message: string) => showToast('success', message), [showToast])
  const error = useCallback((message: string) => showToast('error', message), [showToast])
  const info = useCallback((message: string) => showToast('info', message), [showToast])
  const warning = useCallback((message: string) => showToast('warning', message), [showToast])

  const contextValue = useMemo(
    () => ({ showToast, success, error, info, warning }),
    [showToast, success, error, info, warning]
  )

  const removeToast = (id: string) => {
    triggerRemove(id)
  }

  const pauseToast = useCallback((id: string) => {
    setToasts((prev) =>
      prev.map((t) => {
        if (t.id !== id || t.leaving || t.paused) return t
        return { ...t, paused: true }
      })
    )

    const timer = timersRef.current.get(id)
    if (!timer) return
    if (timer.timeoutId != null) window.clearTimeout(timer.timeoutId)
    const elapsed = Date.now() - timer.startAt
    const remainingMs = Math.max(0, timer.remainingMs - elapsed)
    timersRef.current.set(id, { timeoutId: null, startAt: Date.now(), remainingMs })
  }, [])

  const resumeToast = useCallback((id: string) => {
    setToasts((prev) =>
      prev.map((t) => {
        if (t.id !== id || t.leaving || !t.paused) return t
        return { ...t, paused: false }
      })
    )

    const timer = timersRef.current.get(id)
    if (!timer) return
    if (timer.remainingMs <= 0) {
      triggerRemove(id)
      return
    }
    scheduleRemove(id, timer.remainingMs)
  }, [scheduleRemove, triggerRemove])

  const getIcon = (type: ToastType) => {
    switch (type) {
      case 'success':
        return <CheckCircle2 className="h-5 w-5" />
      case 'error':
        return <AlertCircle className="h-5 w-5" />
      case 'warning':
        return <AlertTriangle className="h-5 w-5" />
      case 'info':
        return <Info className="h-5 w-5" />
    }
  }

  const getStyles = (type: ToastType) => {
    switch (type) {
      case 'success':
        return 'bg-emerald-50 text-emerald-900 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-200 dark:border-emerald-500/20'
      case 'error':
        return 'bg-red-50 text-red-900 border-red-200 dark:bg-red-500/10 dark:text-red-200 dark:border-red-500/20'
      case 'warning':
        return 'bg-amber-50 text-amber-900 border-amber-200 dark:bg-amber-500/10 dark:text-amber-200 dark:border-amber-500/20'
      case 'info':
        return 'bg-blue-50 text-blue-900 border-blue-200 dark:bg-blue-500/10 dark:text-blue-200 dark:border-blue-500/20'
    }
  }

  const getProgressStyles = (type: ToastType) => {
    switch (type) {
      case 'success':
        return 'bg-emerald-500/60 dark:bg-emerald-400/50'
      case 'error':
        return 'bg-red-500/60 dark:bg-red-400/50'
      case 'warning':
        return 'bg-amber-500/60 dark:bg-amber-400/50'
      case 'info':
        return 'bg-blue-500/60 dark:bg-blue-400/50'
    }
  }

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <div className="fixed top-4 right-4 z-[100] space-y-3 max-w-md">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`relative overflow-hidden flex items-start gap-3 p-4 rounded-xl border shadow-lg backdrop-blur-sm ${toast.leaving ? 'toast-leave' : 'toast-enter'} ${getStyles(toast.type)}`}
            onMouseEnter={() => pauseToast(toast.id)}
            onMouseLeave={() => resumeToast(toast.id)}
          >
            <div className="flex-shrink-0 mt-0.5">
              {getIcon(toast.type)}
            </div>
            <p className="flex-1 text-sm font-medium">{toast.message}</p>
            <button
              onClick={() => removeToast(toast.id)}
              className="flex-shrink-0 p-1 rounded-lg hover:bg-black/5 transition dark:hover:bg-white/10"
            >
              <X className="h-4 w-4" />
            </button>

            <div className="absolute left-0 right-0 bottom-0 h-1 bg-black/5 dark:bg-white/10">
              <div
                className={`h-full toast-progress ${getProgressStyles(toast.type)}`}
                style={{ animationDuration: `${toastDurationMs}ms`, animationPlayState: toast.leaving || toast.paused ? 'paused' : 'running' }}
              />
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (context === undefined) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}
