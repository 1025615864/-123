import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { MessageSquare, Clock, Trash2, Download, ArrowRight, Search, X, Share2, Star } from 'lucide-react'
import api from '../api/client'
import { useAppMutation, useToast } from '../hooks'
import { Card, Button, Loading, EmptyState, Input, Chip, Modal, ModalActions } from '../components/ui'
import PageHeader from '../components/PageHeader'
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

  const [q, setQ] = useState('')
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [shareModalOpen, setShareModalOpen] = useState(false)
  const [shareModalSessionId, setShareModalSessionId] = useState<string | null>(null)
  const [shareModalUrl, setShareModalUrl] = useState('')
  const [shareModalExpiresAt, setShareModalExpiresAt] = useState('')

  const debouncedQ = useDebouncedValue(q, 300)
  const { query: consultationsQuery } = useAiConsultationsQuery(isAuthenticated, debouncedQ, favoritesOnly)

  useEffect(() => {
    if (!consultationsQuery.error) return
    const status = (consultationsQuery.error as any)?.response?.status
    if (status === 401) return
    toast.error(getApiErrorMessage(consultationsQuery.error))
  }, [consultationsQuery.error, toast])

  const consultations = consultationsQuery.data ?? []

  const qTrimmed = useMemo(() => String(q ?? '').trim(), [q])

  const deleteMutation = useAppMutation<void, string>({
    mutationFn: async (sid: string) => {
      await api.delete(`/ai/consultations/${sid}`)
    },
    successMessage: '删除成功',
    errorMessageFallback: '删除失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.aiConsultationsBase()],
  })

  const favoriteMutation = useAppMutation<{ is_favorite: boolean }, string>({
    mutationFn: async (sid: string) => {
      const res = await api.post(`/ai/consultations/${sid}/favorite`)
      return (res.data ?? {}) as { is_favorite: boolean }
    },
    errorMessageFallback: '收藏失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.aiConsultationsBase()],
  })

  const shareMutation = useAppMutation<ShareLinkResponse, string>({
    mutationFn: async (sid: string) => {
      const res = await api.post(`/ai/consultations/${sid}/share`, null, {
        params: { expires_days: 7 },
      })
      return res.data as ShareLinkResponse
    },
    errorMessageFallback: '生成分享链接失败，请稍后重试',
  })

  const revokeShareMutation = useAppMutation<{ revoked: boolean }, string>({
    mutationFn: async (sid: string) => {
      const res = await api.post(`/ai/consultations/${sid}/share/revoke`)
      return (res.data ?? {}) as { revoked: boolean }
    },
    errorMessageFallback: '撤销分享失败，请稍后重试',
  })

  const handleDelete = async (sessionId: string) => {
    if (!confirm('确定要删除这条咨询记录吗？')) return
    deleteMutation.mutate(sessionId)
  }

  const closeShareModal = () => {
    setShareModalOpen(false)
    setShareModalSessionId(null)
    setShareModalUrl('')
    setShareModalExpiresAt('')
  }

  const copyShareUrl = async (url: string) => {
    const u = String(url || '').trim()
    if (!u) return
    try {
      await navigator.clipboard.writeText(u)
      toast.success('已复制分享链接')
    } catch {
      window.prompt('复制分享链接', u)
    }
  }

  const handleShare = async (sessionId: string) => {
    if (shareMutation.isPending) return
    shareMutation.mutate(sessionId, {
      onSuccess: async (data) => {
        const sharePath = String(data?.share_path || '').trim()
        const url = sharePath.startsWith('http')
          ? sharePath
          : `${window.location.origin}${sharePath}`

        setShareModalSessionId(sessionId)
        setShareModalUrl(url)
        setShareModalExpiresAt(String(data?.expires_at || '').trim())
        setShareModalOpen(true)
      },
    })
  }

  const handleExport = async (consultation: ConsultationItem) => {
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
        toast.success('导出成功')
      }
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
            ${msg.references.map(ref => `
              <div style="margin-bottom: 8px;">
                <p style="font-weight: 500; color: #1e293b;">${ref.law_name} ${ref.article}</p>
                <p style="color: #475569; font-size: 14px;">${ref.content}</p>
              </div>
            `).join('')}
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
    return <Navigate to={`/login?redirect=${encodeURIComponent(redirect)}`} replace />
  }

  if (consultationsQuery.isLoading && consultations.length === 0) {
    return <Loading text="加载中..." tone={actualTheme} />
  }

  return (
    <div className="space-y-12">
      <Modal
        isOpen={shareModalOpen}
        onClose={closeShareModal}
        title="分享咨询记录"
        description="链接默认有效期 7 天，请注意隐私。"
        size="lg"
      >
        <div className="space-y-4">
          <Input
            label="分享链接"
            value={shareModalUrl}
            readOnly
            onChange={() => {}}
            right={
              <Button
                variant="outline"
                size="sm"
                type="button"
                disabled={!shareModalUrl}
                onClick={() => void copyShareUrl(shareModalUrl)}
              >
                复制
              </Button>
            }
          />
          {shareModalExpiresAt ? (
            <div className="text-sm text-slate-600 dark:text-white/60">
              过期时间：{new Date(shareModalExpiresAt).toLocaleString('zh-CN')}
            </div>
          ) : null}
          <div className="rounded-xl border border-slate-200/70 bg-white/60 p-4 text-sm text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-white/60">
            该链接可公开访问此咨询记录内容。若包含敏感信息，建议先删除或不要分享。
          </div>
          <ModalActions>
            <Button variant="outline" type="button" onClick={closeShareModal}>
              关闭
            </Button>
            <Button
              variant="danger"
              type="button"
              disabled={!shareModalSessionId || revokeShareMutation.isPending}
              isLoading={revokeShareMutation.isPending}
              onClick={() => {
                if (!shareModalSessionId) return
                const ok = confirm('撤销后，之前已分享的链接将立即失效。确定要撤销吗？')
                if (!ok) return
                revokeShareMutation.mutate(shareModalSessionId, {
                  onSuccess: () => {
                    setShareModalUrl('')
                    setShareModalExpiresAt('')
                    toast.success('已撤销分享链接')
                  },
                })
              }}
            >
              撤销分享
            </Button>
            <Button
              variant="primary"
              type="button"
              disabled={!shareModalSessionId || shareMutation.isPending}
              isLoading={shareMutation.isPending}
              onClick={() => {
                if (!shareModalSessionId) return
                shareMutation.mutate(shareModalSessionId, {
                  onSuccess: (data) => {
                    const sharePath = String(data?.share_path || '').trim()
                    const url = sharePath.startsWith('http')
                      ? sharePath
                      : `${window.location.origin}${sharePath}`
                    setShareModalUrl(url)
                    setShareModalExpiresAt(String(data?.expires_at || '').trim())
                    toast.success('已生成新的分享链接')
                  },
                })
              }}
            >
              重新生成
            </Button>
          </ModalActions>
        </div>
      </Modal>

      <PageHeader
        eyebrow="咨询记录"
        title="历史咨询"
        description="查看您的AI法律咨询历史记录"
        tone={actualTheme}
        right={
          <Link to="/chat">
            <Button icon={MessageSquare} className="px-6 bg-emerald-600 hover:bg-emerald-700 text-white focus-visible:ring-emerald-500/25">
              新建咨询
            </Button>
          </Link>
        }
      />

      <Card variant="surface" padding="lg">
        <div className="max-w-2xl">
          <Input
            icon={Search}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索咨询记录（标题/内容）..."
            right={
              qTrimmed ? (
                <button
                  type="button"
                  onClick={() => setQ('')}
                  className="p-1 rounded-md text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors dark:text-white/60 dark:hover:text-white dark:hover:bg-slate-800"
                  aria-label="清空搜索"
                >
                  <X className="h-4 w-4" />
                </button>
              ) : null
            }
          />
          <div className="mt-4 flex flex-wrap gap-2">
            <Chip
              active={!favoritesOnly}
              onClick={() => setFavoritesOnly(false)}
              disabled={consultationsQuery.isLoading}
            >
              全部
            </Chip>
            <Chip
              active={favoritesOnly}
              onClick={() => setFavoritesOnly(true)}
              disabled={consultationsQuery.isLoading}
              className="inline-flex items-center gap-1.5"
            >
              <Star className="h-4 w-4" />
              只看收藏
            </Chip>
          </div>
        </div>
      </Card>

      {consultations.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title={qTrimmed ? '未找到匹配记录' : '暂无咨询记录'}
          description={
            qTrimmed
              ? '请尝试更换关键词或清空搜索条件'
              : '开始一次新的AI法律咨询，您的对话将被保存在这里'
          }
          tone={actualTheme}
          action={
            qTrimmed ? (
              <Button
                icon={X}
                className="bg-slate-900 hover:bg-slate-950 text-white focus-visible:ring-slate-900/25"
                onClick={() => setQ('')}
              >
                清空搜索
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
          {consultations.map((item) => (
            <Card
              key={item.id}
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
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => favoriteMutation.mutate(item.session_id)}
                    disabled={favoriteMutation.isPending}
                    className={`p-2 hover:text-slate-900 dark:hover:text-white ${
                      item.is_favorite ? 'text-amber-600 dark:text-amber-400' : ''
                    }`}
                    aria-label={item.is_favorite ? '取消收藏' : '收藏'}
                  >
                    <Star className="h-4 w-4" fill={item.is_favorite ? 'currentColor' : 'none'} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => handleExport(item)}
                    className="p-2 hover:text-slate-900 dark:hover:text-white"
                    aria-label="导出报告"
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => handleShare(item.session_id)}
                    className="p-2 hover:text-slate-900 dark:hover:text-white"
                    aria-label="分享"
                  >
                    <Share2 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => handleDelete(item.session_id)}
                    className="p-2 hover:text-red-600 dark:hover:text-red-400"
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
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
