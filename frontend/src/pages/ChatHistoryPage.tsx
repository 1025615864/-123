import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  MessageSquare,
  Clock,
  Trash2,
  Download,
  ArrowRight,
  Search,
  X,
  Share2,
  RotateCcw,
  FileText,
  Copy,
} from 'lucide-react'
import api from '../api/client'
import { useAppMutation, useToast } from '../hooks'
import {
  Card,
  Button,
  EmptyState,
  Input,
  ListSkeleton,
  Modal,
  ModalActions,
  SideBySideModal,
  Badge,
} from '../components/ui'
import PageHeader from '../components/PageHeader'
import PaymentMethodPicker, { type PaymentMethod } from '../components/PaymentMethodPicker'
import MarkdownContent from '../components/MarkdownContent'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'
import { useAiConsultationsQuery, type ConsultationItem } from '../queries/aiConsultations'

interface ExportMessage {
  role: string
  content: string
  created_at: string | null
  references?: Array<{ law_name: string; article: string; content: string }>
  references_meta?: Record<string, any>
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value)

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), Math.max(0, delayMs))
    return () => window.clearTimeout(t)
  }, [value, delayMs])

  return debounced
}

interface ExportData {
  title: string
  session_id: string
  created_at: string
  messages: ExportMessage[]
}

interface ShareLinkResponse {
  token: string
  share_path: string
  expires_at: string
}

type PaymentChannelStatus = {
  alipay_configured: boolean
  wechatpay_configured: boolean
  ikunpay_configured: boolean
  available_methods: string[]
}

type PricingResp = {
  services?: {
    light_consult_review?: {
      price?: number
    }
  }
}

type ConsultationReviewTaskItem = {
  id: number
  consultation_id: number
  user_id: number
  order_no: string
  status: string
  lawyer_id: number | null
  result_markdown: string | null
  claimed_at: string | null
  submitted_at: string | null
  created_at: string
  updated_at: string
  latest_version?: {
    id: number
    task_id: number
    editor_user_id: number
    editor_role: string
    content_markdown: string
    created_at: string
  } | null
}

type ConsultationReviewTaskDetailResponse = {
  task: ConsultationReviewTaskItem | null
}

 function sanitizeDownloadFilename(filename: string): string {
   const s = String(filename ?? '').trim()
   if (!s) return ''
   return s.replace(/[\\/:*?"<>|]+/g, '_').trim()
 }

 function parseContentDispositionFilename(headerValue: unknown): string | null {
   const s = String(headerValue ?? '').trim()
   if (!s) return null

   const mStar = s.match(/filename\*\s*=\s*([^']*)''([^;]+)/i)
   if (mStar) {
     const raw = String(mStar[2] ?? '').trim().replace(/^"|"$/g, '')
     try {
       const decoded = decodeURIComponent(raw)
       return sanitizeDownloadFilename(decoded) || null
     } catch {
       return sanitizeDownloadFilename(raw) || null
     }

   }

   const m = s.match(/filename\s*=\s*([^;]+)/i)
   if (m) {
     const raw = String(m[1] ?? '').trim().replace(/^"|"$/g, '')
     return sanitizeDownloadFilename(raw) || null
   }

   return null
 }

export default function ChatHistoryPage() {
  const toast = useToast()
  const { actualTheme } = useTheme()
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [q, setQ] = useState('')
  const [rangeDays, setRangeDays] = useState<0 | 7 | 30>(0)
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewTarget, setPreviewTarget] = useState<ConsultationItem | null>(null)
  const [previewData, setPreviewData] = useState<ExportData | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [activeShareId, setActiveShareId] = useState<string | null>(null)
  const [activeDeleteId, setActiveDeleteId] = useState<string | null>(null)
  const [exportingId, setExportingId] = useState<string | null>(null)

  const [reviewPurchaseOpen, setReviewPurchaseOpen] = useState(false)
  const [reviewPurchaseTarget, setReviewPurchaseTarget] = useState<ConsultationItem | null>(null)
  const [showReviewPaymentPanel, setShowReviewPaymentPanel] = useState(false)
  const [paymentGuideOpen, setPaymentGuideOpen] = useState(false)
  const [paymentGuideOrderNo, setPaymentGuideOrderNo] = useState<string | null>(null)
  const [paymentGuideConsultationId, setPaymentGuideConsultationId] = useState<number | null>(null)

  const debouncedQ = useDebouncedValue(q, 300)
  const { query: consultationsQuery } = useAiConsultationsQuery(isAuthenticated, debouncedQ)

  const pricingQuery = useQuery({
    queryKey: ['payment-pricing'] as const,
    queryFn: async () => {
      const res = await api.get('/payment/pricing')
      return (res.data || {}) as PricingResp
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const channelStatusQuery = useQuery({
    queryKey: queryKeys.paymentChannelStatus(),
    queryFn: async () => {
      const res = await api.get('/payment/channel-status')
      return (res.data || {}) as PaymentChannelStatus
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  })

  const reviewTaskQuery = useQuery({
    queryKey: queryKeys.consultationReviewTask(previewTarget?.id ?? null),
    queryFn: async () => {
      const consultationId = previewTarget?.id
      if (!consultationId) return { task: null } satisfies ConsultationReviewTaskDetailResponse
      const res = await api.get(`/reviews/consultations/${consultationId}`)
      return (res.data || { task: null }) as ConsultationReviewTaskDetailResponse
    },
    enabled: isAuthenticated && previewOpen && !!previewTarget?.id,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!consultationsQuery.error) return
    const status = (consultationsQuery.error as any)?.response?.status
    if (status === 401) return
    toast.error(getApiErrorMessage(consultationsQuery.error))
  }, [consultationsQuery.error, toast])

  const consultations = consultationsQuery.data ?? []

  const qTrimmed = useMemo(() => String(q ?? '').trim(), [q])

  const rangeStart = useMemo(() => {
    if (rangeDays === 0) return null
    const d = new Date()
    d.setDate(d.getDate() - rangeDays)
    return d
  }, [rangeDays])

  const fromDateTs = useMemo(() => {
    const s = String(fromDate || '').trim()
    if (!s) return null
    const d = new Date(`${s}T00:00:00`)
    const t = d.getTime()
    return Number.isFinite(t) ? t : null
  }, [fromDate])

  const toDateTs = useMemo(() => {
    const s = String(toDate || '').trim()
    if (!s) return null
    const d = new Date(`${s}T23:59:59.999`)
    const t = d.getTime()
    return Number.isFinite(t) ? t : null
  }, [toDate])

  const visibleConsultations = useMemo(() => {
    const base = Array.isArray(consultations) ? consultations : []

    const quickStartTs = rangeStart ? rangeStart.getTime() : null
    const startTs = typeof fromDateTs === 'number' ? fromDateTs : quickStartTs
    const endTs = typeof toDateTs === 'number' ? toDateTs : null

    const filtered = base.filter((c) => {
      const t = new Date(c.created_at).getTime()
      if (!Number.isFinite(t)) return true
      if (typeof startTs === 'number' && t < startTs) return false
      if (typeof endTs === 'number' && t > endTs) return false
      return true
    })

    const sorted = [...filtered].sort((a, b) => {
      const ta = new Date(a.created_at).getTime()
      const tb = new Date(b.created_at).getTime()
      const va = Number.isFinite(ta) ? ta : 0
      const vb = Number.isFinite(tb) ? tb : 0
      return sortOrder === 'asc' ? va - vb : vb - va
    })

    return sorted
  }, [consultations, fromDateTs, rangeStart, sortOrder, toDateTs])

  const hasTimeFilter =
    rangeDays !== 0 || Boolean(String(fromDate || '').trim()) || Boolean(String(toDate || '').trim())

  const hasAnyFilter =
    Boolean(String(qTrimmed || '').trim()) || hasTimeFilter || sortOrder !== 'desc'

  const clearAllFilters = () => {
    setQ('')
    setRangeDays(0)
    setFromDate('')
    setToDate('')
    setSortOrder('desc')
  }

  const closePreview = () => {
    setPreviewOpen(false)
    setPreviewTarget(null)
    setPreviewData(null)
    setPreviewLoading(false)
  }

  const openReviewPurchase = (consultation: ConsultationItem) => {
    setReviewPurchaseTarget(consultation)
    setReviewPurchaseOpen(true)
    setShowReviewPaymentPanel(false)
  }

  const closeReviewPurchase = () => {
    setReviewPurchaseOpen(false)
    setShowReviewPaymentPanel(false)
    setReviewPurchaseTarget(null)
  }

  const openPaymentGuide = (orderNo: string | null, consultationId: number | null) => {
    setPaymentGuideOrderNo(orderNo)
    setPaymentGuideConsultationId(consultationId)
    setPaymentGuideOpen(true)
  }

  const buyReviewMutation = useAppMutation<
    { order_no: string; pay_url?: string },
    { consultation_id: number; payment_method: PaymentMethod }
  >({
    mutationFn: async ({ consultation_id, payment_method }) => {
      const createRes = await api.post('/payment/orders', {
        order_type: 'light_consult_review',
        amount: 0.01,
        title: 'AI咨询律师复核',
        description: 'AI咨询律师复核',
        related_id: consultation_id,
        related_type: 'ai_consultation',
      })
      const orderNo = String(createRes.data?.order_no || '').trim()
      if (!orderNo) throw new Error('未获取到订单号')

      const payRes = await api.post(`/payment/orders/${encodeURIComponent(orderNo)}/pay`, {
        payment_method,
      })
      return { order_no: orderNo, ...(payRes.data || {}) } as { order_no: string; pay_url?: string }
    },
    errorMessageFallback: '购买失败，请稍后重试',
    disableErrorToast: true,
  })

  const openPreview = async (consultation: ConsultationItem) => {
    setPreviewTarget(consultation)
    setPreviewOpen(true)
    setPreviewData(null)
    setPreviewLoading(true)
    try {
      const res = await api.get(`/ai/consultations/${consultation.session_id}/export`)
      setPreviewData(res.data as ExportData)
    } catch (e) {
      toast.error(getApiErrorMessage(e, '加载摘要失败，请稍后重试'))
    } finally {
      setPreviewLoading(false)
    }
  }

  const previewSummary = useMemo(() => {
    const data = previewData
    if (!data) return null

    const msgs: ExportMessage[] = Array.isArray(data.messages) ? data.messages : []
    const firstUser = msgs.find((m: ExportMessage) => String(m.role || '').toLowerCase() === 'user')
    const firstAssistant = msgs.find(
      (m: ExportMessage) => String(m.role || '').toLowerCase() === 'assistant'
    )

    const laws = new Map<string, string>()
    for (const m of msgs) {
      const refs = Array.isArray(m.references) ? m.references : []
      for (const ref of refs) {
        const lawName = String(ref.law_name || '').trim()
        const article = String(ref.article || '').trim()
        const content = String(ref.content || '').trim()
        if (!lawName && !article) continue
        const key = `${lawName} ${article}`.trim()
        if (!laws.has(key)) {
          laws.set(key, content)
        }
      }
    }

    return {
      firstUser: String(firstUser?.content || '').trim(),
      firstAssistant: String(firstAssistant?.content || '').trim(),
      laws: Array.from(laws.entries()).map(([k, v]) => ({ title: k, content: v })),
    }
  }, [previewData])

  const copyPreview = async () => {
    const title = String(previewTarget?.title || previewData?.title || '法律咨询').trim() || '法律咨询'
    const sid = String(previewTarget?.session_id || previewData?.session_id || '').trim()
    const createdAt = previewTarget?.created_at
      ? new Date(previewTarget.created_at).toLocaleString()
      : previewData?.created_at
      ? new Date(previewData.created_at).toLocaleString()
      : ''

    const userPart = previewSummary?.firstUser ? `用户首问：\n${previewSummary.firstUser}` : ''
    const aiPart = previewSummary?.firstAssistant ? `AI首答：\n${previewSummary.firstAssistant}` : ''
    const lawsPart =
      previewSummary && previewSummary.laws.length > 0
        ? `引用法条：\n${previewSummary.laws.map((l: { title: string }) => `- ${l.title}`).join('\n')}`
        : ''

    const parts = [
      `标题：${title}`,
      sid ? `咨询编号：${sid}` : '',
      createdAt ? `时间：${createdAt}` : '',
      '',
      userPart,
      '',
      aiPart,
      '',
      lawsPart,
    ].filter((p) => String(p).trim() !== '')

    const text = parts.join('\n')
    try {
      await navigator.clipboard.writeText(text)
      toast.success('已复制摘要')
    } catch {
      window.prompt('复制摘要', text)
    }
  }

  const deleteMutation = useAppMutation<void, string>({
    mutationFn: async (sid: string) => {
      await api.delete(`/ai/consultations/${sid}`)
    },
    successMessage: '删除成功',
    errorMessageFallback: '删除失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.aiConsultationsBase()],
    onMutate: async (sid) => {
      setActiveDeleteId(sid)
    },
    onSettled: (_data, _err, sid) => {
      setActiveDeleteId((prev) => (prev === sid ? null : prev))
    },
  })

  const shareMutation = useAppMutation<ShareLinkResponse, string>({
    mutationFn: async (sid: string) => {
      const res = await api.post(`/ai/consultations/${sid}/share`, null, {
        params: { expires_days: 7 },
      })
      return res.data as ShareLinkResponse
    },
    errorMessageFallback: '生成分享链接失败，请稍后重试',
    onMutate: async (sid) => {
      setActiveShareId(sid)
    },
    onSettled: (_data, _err, sid) => {
      setActiveShareId((prev) => (prev === sid ? null : prev))
    },
  })

  const actionBusy = shareMutation.isPending || deleteMutation.isPending || exportingId != null

  const handleDelete = async (sessionId: string) => {
    if (!confirm('确定要删除这条咨询记录吗？')) return
    if (actionBusy) return
    deleteMutation.mutate(sessionId)
  }

  const handleShare = async (sessionId: string) => {
    if (actionBusy) return
    shareMutation.mutate(sessionId, {
      onSuccess: async (data) => {
        const sharePath = String(data?.share_path || '').trim()
        const url = sharePath.startsWith('http')
          ? sharePath
          : `${window.location.origin}${sharePath}`

        try {
          await navigator.clipboard.writeText(url)
          toast.success('已复制分享链接')
        } catch {
          window.prompt('复制分享链接', url)
        }
      },
    })
  }

  const handleExport = async (consultation: ConsultationItem) => {
    if (actionBusy) return
    setExportingId(consultation.session_id)
    try {
      const res = await api.get(`/ai/consultations/${consultation.session_id}/report`, {
        responseType: 'blob' as any,
      })

       const disposition =
         (res as any)?.headers?.['content-disposition'] ??
         (res as any)?.headers?.['Content-Disposition'] ??
         (res as any)?.headers?.['CONTENT-DISPOSITION']
       const serverFilename = parseContentDispositionFilename(disposition)
       const defaultFilename = `法律咨询报告_${consultation.session_id}.pdf`
       const downloadFilename = sanitizeDownloadFilename(serverFilename || defaultFilename) || defaultFilename

      const blob = new Blob([res.data], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = downloadFilename
      a.click()
      URL.revokeObjectURL(url)

      toast.success('导出成功')
    } catch {
      try {
        const res = await api.get(`/ai/consultations/${consultation.session_id}/export`)
        const data = res.data as ExportData
        
        // 生成HTML内容用于打印/导出PDF
        const htmlContent = generateExportHTML(data)
        
        // 创建新窗口用于打印
        const printWindow = window.open('', '_blank')
        if (!printWindow) {
          const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' })
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `咨询记录_${consultation.session_id}.html`
          a.click()
          URL.revokeObjectURL(url)
          toast.success('已下载HTML报告，可打开后打印为PDF')
          return
        }

        printWindow.document.write(htmlContent)
        printWindow.document.close()
        printWindow.onload = () => {
          printWindow.print()
        }

        toast.success('已打开打印预览，可保存为PDF')
      } catch {
        // 降级为简单文本导出
        const content = `咨询记录导出\n\n标题: ${consultation.title}\n时间: ${new Date(consultation.created_at).toLocaleString()}\n消息数: ${consultation.message_count}\n\n（完整对话内容需在详情页查看）`
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `咨询记录_${consultation.session_id}.txt`
        a.click()
        URL.revokeObjectURL(url)
        toast.error('导出失败，请稍后重试')
      }
    } finally {
      setExportingId((prev) => (prev === consultation.session_id ? null : prev))
    }
  }

  const generateExportHTML = (data: ExportData): string => {
    const messagesHTML = data.messages.map(msg => {
      const roleLabel = msg.role === 'user' ? '👤 用户' : '🤖 AI助手'
      const roleColor = msg.role === 'user' ? '#3b82f6' : '#f59e0b'
      const time = msg.created_at ? new Date(msg.created_at).toLocaleString() : ''
      
      let refsHTML = ''
      if (msg.references && msg.references.length > 0) {
        refsHTML = `
          <div style="margin-top: 12px; padding: 12px; background: #f8fafc; border-radius: 8px; border-left: 3px solid #f59e0b;">
            <p style="font-weight: 600; margin-bottom: 8px; color: #64748b;">📚 相关法条：</p>
            ${msg.references
              .map(
                (ref) => `
              <div style="margin-bottom: 8px;">
                <p style="font-weight: 500; color: #1e293b;">${ref.law_name} ${ref.article}</p>
                <p style="color: #475569; font-size: 14px;">${ref.content}</p>
              </div>
            `
              )
              .join('')}
          </div>
        `
      }
      
      return `
        <div style="margin-bottom: 20px; padding: 16px; background: ${msg.role === 'user' ? '#eff6ff' : '#fffbeb'}; border-radius: 12px;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span style="font-weight: 600; color: ${roleColor};">${roleLabel}</span>
            <span style="color: #94a3b8; font-size: 12px;">${time}</span>
          </div>
          <div style="color: #1e293b; line-height: 1.6; white-space: pre-wrap;">${msg.content}</div>
          ${refsHTML}
        </div>
      `
    }).join('')

    return `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <title>法律咨询记录 - ${data.title}</title>
        <style>
          @media print {
            body { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
          }
          body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 40px; background: #fff; }
        </style>
      </head>
      <body>
        <div style="text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 2px solid #e2e8f0;">
          <h1 style="color: #1e293b; margin-bottom: 8px;">⚖️ 法律咨询记录</h1>
          <p style="color: #64748b; margin: 0;">${data.title}</p>
          <p style="color: #94a3b8; font-size: 14px; margin-top: 8px;">咨询时间：${new Date(data.created_at).toLocaleString()}</p>
        </div>
        
        <div style="margin-bottom: 40px;">
          ${messagesHTML}
        </div>
        
        <div style="text-align: center; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 12px;">
          <p>本记录由「百姓法律助手」生成</p>
          <p>仅供参考，不构成正式法律意见</p>
        </div>
      </body>
      </html>
    `
  }

  if (!isAuthenticated) {
    const redirect = `${location.pathname}${location.search}`
    return <Navigate to={`/login?return_to=${encodeURIComponent(redirect)}`} replace />
  }

  const isInitialLoading = consultationsQuery.isLoading && consultations.length === 0
  const showFetching = consultationsQuery.isFetching && !isInitialLoading

  return (
    <div className="space-y-12">
      <PageHeader
        eyebrow="咨询记录"
        title="历史咨询"
        description="查看您的AI法律咨询历史记录"
        tone={actualTheme}
        right={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              icon={RotateCcw}
              isLoading={consultationsQuery.isFetching}
              loadingText="刷新中..."
              onClick={() => {
                if (actionBusy) return
                consultationsQuery.refetch()
              }}
              className="px-4"
              disabled={consultationsQuery.isFetching || actionBusy}
            >
              刷新
            </Button>
            <Link to="/chat">
              <Button icon={MessageSquare} className="px-6 bg-emerald-600 hover:bg-emerald-700 text-white focus-visible:ring-emerald-500/25">
                新建咨询
              </Button>
            </Link>
          </div>
        }
      />

      <Card variant="surface" padding="lg">
        <div className="space-y-4">
          <div className="max-w-2xl">
            <Input
              icon={Search}
              value={q}
              onChange={(e) => {
                if (actionBusy) return
                setQ(e.target.value)
              }}
              placeholder="搜索咨询记录（标题/内容）..."
              disabled={actionBusy}
              right={
                qTrimmed ? (
                  <button
                    type="button"
                    onClick={() => {
                      if (actionBusy) return
                      setQ('')
                    }}
                    className="p-1 rounded-md text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors dark:text-white/60 dark:hover:text-white dark:hover:bg-slate-800 disabled:opacity-60 disabled:cursor-not-allowed"
                    aria-label="清空搜索"
                    disabled={actionBusy}
                  >
                    <X className="h-4 w-4" />
                  </button>
                ) : null
              }
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Button
                variant={rangeDays === 0 ? 'primary' : 'outline'}
                size="sm"
                onClick={() => {
                  if (actionBusy) return
                  setRangeDays(0)
                  setFromDate('')
                  setToDate('')
                }}
                disabled={actionBusy}
              >
                全部
              </Button>
              <Button
                variant={rangeDays === 7 ? 'primary' : 'outline'}
                size="sm"
                onClick={() => {
                  if (actionBusy) return
                  setRangeDays(7)
                  setFromDate('')
                  setToDate('')
                }}
                disabled={actionBusy}
              >
                近7天
              </Button>
              <Button
                variant={rangeDays === 30 ? 'primary' : 'outline'}
                size="sm"
                onClick={() => {
                  if (actionBusy) return
                  setRangeDays(30)
                  setFromDate('')
                  setToDate('')
                }}
                disabled={actionBusy}
              >
                近30天
              </Button>
            </div>

            <div className="text-sm text-slate-600 dark:text-white/60">
              {showFetching ? '更新中…' : null}
              <span className={showFetching ? 'ml-2' : ''}>
                {visibleConsultations.length} 条
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="w-full sm:w-48">
              <Input
                label="开始日期"
                type="date"
                value={fromDate}
                onChange={(e) => {
                  if (actionBusy) return
                  setFromDate(e.target.value)
                  setRangeDays(0)
                }}
                disabled={actionBusy}
              />
            </div>
            <div className="w-full sm:w-48">
              <Input
                label="结束日期"
                type="date"
                value={toDate}
                onChange={(e) => {
                  if (actionBusy) return
                  setToDate(e.target.value)
                  setRangeDays(0)
                }}
                disabled={actionBusy}
              />
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant={sortOrder === 'desc' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => {
                  if (actionBusy) return
                  setSortOrder('desc')
                }}
                disabled={actionBusy}
              >
                最新
              </Button>
              <Button
                variant={sortOrder === 'asc' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => {
                  if (actionBusy) return
                  setSortOrder('asc')
                }}
                disabled={actionBusy}
              >
                最早
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (actionBusy) return
                  clearAllFilters()
                }}
                disabled={actionBusy}
              >
                清空筛选
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {isInitialLoading ? (
        <Card variant="surface" padding="lg">
          <ListSkeleton count={6} />
        </Card>
      ) : visibleConsultations.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title={
            qTrimmed
              ? '未找到匹配记录'
              : !hasTimeFilter
              ? '暂无咨询记录'
              : '该时间范围内暂无记录'
          }
          description={
            hasAnyFilter
              ? '请尝试调整筛选条件或清空筛选'
              : '开始一次新的AI法律咨询，您的对话将被保存在这里'
          }
          tone={actualTheme}
          action={
            hasAnyFilter ? (
              <Button
                icon={X}
                className="bg-slate-900 hover:bg-slate-950 text-white focus-visible:ring-slate-900/25"
                onClick={clearAllFilters}
              >
                清空筛选
              </Button>
            ) : (
              <Link to="/chat" className="mt-6 inline-block">
                <Button icon={ArrowRight} className="bg-emerald-600 hover:bg-emerald-700 text-white focus-visible:ring-emerald-500/25">开始咨询</Button>
              </Link>
            )
          }
        />
      ) : (
        <div className="grid gap-4">
          {visibleConsultations.map((item) => (
            <Card
              key={item.session_id}
              variant="surface"
              hover
              padding="none"
              className="p-6"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-medium text-slate-900 dark:text-white truncate">
                    {item.title}
                  </h3>
                  <div className="flex items-center gap-4 mt-2 text-sm text-slate-600 dark:text-white/60">
                    <span className="flex items-center gap-1.5">
                      <Clock className="h-4 w-4" />
                      {new Date(item.created_at).toLocaleString()}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <MessageSquare className="h-4 w-4" />
                      {item.message_count} 条消息
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {(() => {
                    const shareLoading = shareMutation.isPending && activeShareId === item.session_id
                    const deleteLoading = deleteMutation.isPending && activeDeleteId === item.session_id
                    const exportLoading = exportingId === item.session_id
                    const actionBusy = shareMutation.isPending || deleteMutation.isPending || exportingId != null

                    return (
                      <>
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => openPreview(item)}
                    className="p-2 hover:text-slate-900 dark:hover:text-white"
                    aria-label="查看摘要"
                  >
                    <FileText className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => handleExport(item)}
                    isLoading={exportLoading}
                    loadingText="导出中..."
                    disabled={actionBusy && !exportLoading}
                    className={`hover:text-slate-900 dark:hover:text-white ${exportLoading ? 'px-3 py-2' : 'p-2'}`}
                    aria-label="导出报告"
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => handleShare(item.session_id)}
                    isLoading={shareLoading}
                    loadingText="生成中..."
                    disabled={actionBusy && !shareLoading}
                    className={`hover:text-slate-900 dark:hover:text-white ${shareLoading ? 'px-3 py-2' : 'p-2'}`}
                    aria-label="分享链接"
                  >
                    <Share2 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => handleDelete(item.session_id)}
                    isLoading={deleteLoading}
                    loadingText="删除中..."
                    disabled={actionBusy && !deleteLoading}
                    className={`hover:text-red-600 dark:hover:text-red-400 ${deleteLoading ? 'px-3 py-2' : 'p-2'}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                  <Link to={`/chat?session=${item.session_id}`}>
                    <Button
                      variant="outline"
                      size="sm"
                      className="px-4"
                    >
                      查看详情
                    </Button>
                  </Link>
                      </>
                    )
                  })()}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={previewOpen}
        onClose={() => {
          if (previewLoading) return
          closePreview()
        }}
        title={String(previewTarget?.title || previewData?.title || '咨询摘要')}
        description={
          previewTarget?.created_at
            ? `咨询时间：${new Date(previewTarget.created_at).toLocaleString()}`
            : previewData?.created_at
            ? `咨询时间：${new Date(previewData.created_at).toLocaleString()}`
            : undefined
        }
        size="lg"
      >
        {previewLoading ? (
          <ListSkeleton count={4} />
        ) : previewData && previewSummary ? (
          <div className="space-y-6">
            <div>
              <div className="text-sm font-semibold text-slate-900 dark:text-white">用户首问</div>
              <div className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-700 dark:text-white/70">
                {previewSummary.firstUser || '（无）'}
              </div>
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900 dark:text-white">AI首答</div>
              <div className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-700 dark:text-white/70">
                {previewSummary.firstAssistant || '（无）'}
              </div>
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900 dark:text-white">引用法条</div>
              {previewSummary.laws.length === 0 ? (
                <div className="mt-2 text-sm text-slate-600 dark:text-white/60">（无）</div>
              ) : (
                <div className="mt-2 space-y-3">
                  {previewSummary.laws.map((l) => (
                    <div key={l.title} className="rounded-xl border border-slate-200/70 p-4 dark:border-white/10">
                      <div className="text-sm font-medium text-slate-900 dark:text-white">{l.title}</div>
                      {l.content ? (
                        <div className="mt-2 whitespace-pre-wrap break-words text-xs text-slate-600 dark:text-white/60">
                          {l.content}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">律师复核</div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={reviewTaskQuery.isFetching}
                  onClick={() => {
                    reviewTaskQuery.refetch()
                  }}
                >
                  刷新
                </Button>
              </div>

              {reviewTaskQuery.isLoading ? (
                <div className="mt-3 text-sm text-slate-600 dark:text-white/60">加载中…</div>
              ) : reviewTaskQuery.isError ? (
                <div className="mt-3 text-sm text-slate-600 dark:text-white/60">加载失败</div>
              ) : (() => {
                const task = reviewTaskQuery.data?.task ?? null
                const reviewPrice = Number(pricingQuery.data?.services?.light_consult_review?.price || 19.9)
                if (!task) {
                  return (
                    <div className="mt-3 rounded-xl border border-slate-200/70 p-4 dark:border-white/10">
                      <div className="text-sm text-slate-700 dark:text-white/70">暂无律师复核记录</div>
                      <div className="mt-3">
                        <Button
                          onClick={() => {
                            if (!previewTarget) return
                            openReviewPurchase(previewTarget)
                          }}
                        >
                          购买律师复核（¥{reviewPrice.toFixed(2)}）
                        </Button>
                      </div>
                    </div>
                  )
                }

                const status = String(task.status || '')
                const s = status.toLowerCase()
                const statusLabel =
                  s === 'pending' ? '待领取' : s === 'claimed' ? '处理中' : s === 'submitted' ? '已复核' : status
                const statusVariant: 'success' | 'info' | 'warning' | 'default' =
                  s === 'submitted' ? 'success' : s === 'claimed' ? 'info' : s === 'pending' ? 'warning' : 'default'

                return (
                  <div className="mt-3 space-y-3">
                    <div className="flex items-center gap-2">
                      <Badge variant={statusVariant} size="sm">
                        {statusLabel}
                      </Badge>
                      <div className="text-xs text-slate-500 dark:text-white/45">订单号：{task.order_no}</div>
                    </div>

                    {s === 'submitted' && task.result_markdown ? (
                      <div className="rounded-xl border border-slate-200/70 p-4 dark:border-white/10">
                        <MarkdownContent content={String(task.result_markdown)} className="text-sm" />
                      </div>
                    ) : (
                      <div className="text-sm text-slate-600 dark:text-white/60">复核结果生成后会在此展示</div>
                    )}
                  </div>
                )
              })()}
            </div>

            <ModalActions>
              <Button variant="outline" onClick={closePreview}>
                关闭
              </Button>
              <Button icon={Copy} onClick={copyPreview}>
                复制摘要
              </Button>
            </ModalActions>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="text-sm text-slate-600 dark:text-white/60">暂无可展示的摘要内容</div>
            <ModalActions>
              <Button variant="outline" onClick={closePreview}>
                关闭
              </Button>
            </ModalActions>
          </div>
        )}
      </Modal>

      <SideBySideModal
        isOpen={reviewPurchaseOpen}
        onClose={() => {
          if (buyReviewMutation.isPending) return
          closeReviewPurchase()
        }}
        leftTitle="律师复核"
        leftDescription="为本次 AI 咨询购买律师复核服务"
        left={
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-200/70 bg-slate-900/5 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/70">
              <div>咨询：{String(reviewPurchaseTarget?.title || '').trim() || 'AI咨询'}</div>
              <div className="mt-1">
                价格：¥
                {Number(pricingQuery.data?.services?.light_consult_review?.price || 19.9).toFixed(2)}
              </div>
            </div>

            <Button
              type="button"
              fullWidth
              disabled={buyReviewMutation.isPending}
              onClick={() => {
                setShowReviewPaymentPanel(true)
              }}
            >
              去支付
            </Button>

            <Button
              type="button"
              variant="secondary"
              fullWidth
              disabled={buyReviewMutation.isPending}
              onClick={() => {
                closeReviewPurchase()
              }}
            >
              取消
            </Button>
          </div>
        }
        rightTitle={showReviewPaymentPanel ? '选择支付方式' : undefined}
        rightDescription={
          showReviewPaymentPanel
            ? `支付 ¥${Number(pricingQuery.data?.services?.light_consult_review?.price || 19.9).toFixed(2)}`
            : undefined
        }
        right={
          showReviewPaymentPanel && reviewPurchaseTarget ? (
            <PaymentMethodPicker
              busy={buyReviewMutation.isPending}
              options={(() => {
                const loadingChannels = !channelStatusQuery.data && channelStatusQuery.isLoading
                const canAlipay = channelStatusQuery.data?.alipay_configured === true
                const canIkunpay = channelStatusQuery.data?.ikunpay_configured === true
                const thirdPartyDisabledReason = loadingChannels ? '加载中' : '未配置'

                return [
                  {
                    method: 'balance' as PaymentMethod,
                    label: '余额支付',
                    description: '即时生效',
                    enabled: true,
                  },
                  {
                    method: 'alipay' as PaymentMethod,
                    label: '支付宝',
                    description: '跳转到支付宝完成支付',
                    enabled: canAlipay,
                    disabledReason: thirdPartyDisabledReason,
                  },
                  {
                    method: 'ikunpay' as PaymentMethod,
                    label: '爱坤支付',
                    description: '跳转到爱坤支付完成支付',
                    enabled: canIkunpay,
                    disabledReason: thirdPartyDisabledReason,
                  },
                ]
              })()}
              onBack={() => {
                if (buyReviewMutation.isPending) return
                setShowReviewPaymentPanel(false)
              }}
              onCancel={() => {
                if (buyReviewMutation.isPending) return
                closeReviewPurchase()
              }}
              onSelect={(method) => {
                const target = reviewPurchaseTarget
                if (!target) return

                closeReviewPurchase()

                buyReviewMutation.mutate(
                  { consultation_id: intOrZero(target.id), payment_method: method },
                  {
                    onSuccess: async (data) => {
                      const orderNo = String((data as any)?.order_no || '').trim()
                      if (!orderNo) {
                        toast.success('下单成功')
                        return
                      }

                      if (method !== 'balance') {
                        const url = String((data as any)?.pay_url || '').trim()
                        if (url) {
                          window.open(url, '_blank', 'noopener,noreferrer')
                          toast.success('已打开支付页面')
                          openPaymentGuide(orderNo, target.id)
                        } else {
                          toast.error('未获取到支付链接')
                        }
                        return
                      }

                      toast.success('购买成功')
                      queryClient.invalidateQueries({
                        queryKey: queryKeys.consultationReviewTask(target.id) as any,
                      })
                    },
                    onError: (err) => {
                      const msg = getApiErrorMessage(err, '购买失败')
                      if (String(msg).includes('余额不足')) {
                        toast.warning('余额不足，请先充值')
                        navigate('/profile?recharge=1')
                        return
                      }
                      toast.error(msg)
                    },
                  }
                )
              }}
            />
          ) : undefined
        }
        onRightClose={() => {
          if (buyReviewMutation.isPending) return
          setShowReviewPaymentPanel(false)
        }}
        zIndexClass="z-[80]"
      />

      <Modal
        isOpen={paymentGuideOpen}
        onClose={() => setPaymentGuideOpen(false)}
        title="支付提示"
        description="支付完成后请返回本站刷新复核状态"
        size="sm"
        zIndexClass="z-[90]"
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200/70 bg-slate-900/5 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/70">
            <div>1) 在新打开的支付页面完成支付</div>
            <div className="mt-1">2) 回到本页点击“我已支付，刷新状态”</div>
          </div>

          <Button
            fullWidth
            onClick={async () => {
              setPaymentGuideOpen(false)
              const cid = paymentGuideConsultationId
              if (cid) {
                await queryClient.invalidateQueries({
                  queryKey: queryKeys.consultationReviewTask(cid) as any,
                })
              }
              toast.success('已刷新状态')
            }}
          >
            我已支付，刷新状态
          </Button>

          {paymentGuideOrderNo ? (
            <Link
              to={`/payment/return?order_no=${encodeURIComponent(paymentGuideOrderNo)}`}
              className="block"
            >
              <Button variant="outline" fullWidth>
                去支付结果页查看状态
              </Button>
            </Link>
          ) : null}

          {paymentGuideOrderNo ? (
            <div className="text-xs text-slate-500 dark:text-white/45">订单号：{paymentGuideOrderNo}</div>
          ) : null}
        </div>
      </Modal>
    </div>
  )
}

function intOrZero(value: unknown): number {
  const n = Number(value)
  if (!Number.isFinite(n) || Number.isNaN(n)) return 0
  return Math.trunc(n)
}
