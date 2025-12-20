import { useEffect } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { MessageSquare, Clock, Trash2, Download, ArrowRight } from 'lucide-react'
import api from '../api/client'
import { useAppMutation, useToast } from '../hooks'
import { Card, Button, Loading, EmptyState } from '../components/ui'
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

interface ExportData {
  title: string
  session_id: string
  created_at: string
  messages: ExportMessage[]
}

export default function ChatHistoryPage() {
  const toast = useToast()
  const { actualTheme } = useTheme()
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  const { query: consultationsQuery } = useAiConsultationsQuery(isAuthenticated)

  useEffect(() => {
    if (!consultationsQuery.error) return
    const status = (consultationsQuery.error as any)?.response?.status
    if (status === 401) return
    toast.error(getApiErrorMessage(consultationsQuery.error))
  }, [consultationsQuery.error, toast])

  const consultations = consultationsQuery.data ?? []

  const deleteMutation = useAppMutation<void, string>({
    mutationFn: async (sid: string) => {
      await api.delete(`/ai/consultations/${sid}`)
    },
    successMessage: '删除成功',
    errorMessageFallback: '删除失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.aiConsultations()],
  })

  const handleDelete = async (sessionId: string) => {
    if (!confirm('确定要删除这条咨询记录吗？')) return
    deleteMutation.mutate(sessionId)
  }

  const handleExport = async (consultation: ConsultationItem) => {
    try {
      const res = await api.get(`/ai/consultations/${consultation.session_id}/export`)
      const data = res.data as ExportData
      
      // 生成HTML内容用于打印/导出PDF
      const htmlContent = generateExportHTML(data)
      
      // 创建新窗口用于打印
      const printWindow = window.open('', '_blank')
      if (printWindow) {
        printWindow.document.write(htmlContent)
        printWindow.document.close()
        printWindow.onload = () => {
          printWindow.print()
        }
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

      {consultations.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="暂无咨询记录"
          description="开始一次新的AI法律咨询，您的对话将被保存在这里"
          tone={actualTheme}
          action={
            <Link to="/chat" className="mt-6 inline-block">
              <Button icon={ArrowRight} className="bg-emerald-600 hover:bg-emerald-700 text-white focus-visible:ring-emerald-500/25">开始咨询</Button>
            </Link>
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
                    onClick={() => handleExport(item)}
                    className="p-2 hover:text-slate-900 dark:hover:text-white"
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
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
