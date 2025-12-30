import { useEffect, useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Share2, User, Bot } from 'lucide-react'
import { Card, Button, Loading, EmptyState } from '../components/ui'
import PageHeader from '../components/PageHeader'
import api from '../api/client'
import { queryKeys } from '../queryKeys'
import { useTheme } from '../contexts/ThemeContext'
import { getApiErrorMessage } from '../utils'

interface SharedMessage {
  role: string
  content: string
  references: string | null
  created_at: string
}

interface SharedConsultationResponse {
  session_id: string
  title: string | null
  created_at: string
  messages: SharedMessage[]
}

export default function SharePage() {
  const { actualTheme } = useTheme()
  const params = useParams()
  const token = String(params.token || '').trim()

  const sharedQuery = useQuery({
    queryKey: queryKeys.sharedConsultation(token),
    queryFn: async () => {
      const res = await api.get(`/ai/share/${encodeURIComponent(token)}`)
      return res.data as SharedConsultationResponse
    },
    enabled: Boolean(token),
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!sharedQuery.error) return
  }, [sharedQuery.error])

  const data = sharedQuery.data ?? null

  const pageTitle = useMemo(() => {
    const t = String(data?.title || '').trim()
    return t || '分享的对话'
  }, [data?.title])

  const createdAtText = useMemo(() => {
    const raw = String(data?.created_at || '').trim()
    if (!raw) return ''
    const ts = new Date(raw).getTime()
    if (Number.isNaN(ts)) return raw
    return new Date(ts).toLocaleString('zh-CN')
  }, [data?.created_at])

  const handleCopyLink = async () => {
    const url = `${window.location.origin}/share/${token}`
    try {
      await navigator.clipboard.writeText(url)
      window.alert('已复制分享链接')
    } catch {
      window.prompt('复制分享链接', url)
    }
  }

  if (!token) {
    return (
      <EmptyState
        icon={Share2}
        title="分享链接无效"
        description="缺少分享 token"
        tone={actualTheme}
        action={
          <Link to="/">
            <Button icon={ArrowRight}>返回首页</Button>
          </Link>
        }
      />
    )
  }

  if (sharedQuery.isLoading && !data) {
    return <Loading text="加载中..." tone={actualTheme} />
  }

  const errText = sharedQuery.isError ? getApiErrorMessage(sharedQuery.error, '加载分享内容失败') : null

  if (errText) {
    return (
      <EmptyState
        icon={Share2}
        title="无法打开分享内容"
        description={errText}
        tone={actualTheme}
        action={
          <Button variant="outline" onClick={() => sharedQuery.refetch()}>
            重试
          </Button>
        }
      />
    )
  }

  if (!data) {
    return (
      <EmptyState
        icon={Share2}
        title="暂无数据"
        description="分享内容为空"
        tone={actualTheme}
      />
    )
  }

  const messages = Array.isArray(data.messages) ? data.messages : []

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="分享"
        title={pageTitle}
        description={createdAtText ? `创建时间：${createdAtText}` : '只读分享内容'}
        tone={actualTheme}
        right={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={handleCopyLink} icon={Share2}>
              复制链接
            </Button>
            <Link to="/chat">
              <Button icon={ArrowRight} className="bg-emerald-600 hover:bg-emerald-700 text-white focus-visible:ring-emerald-500/25">
                去咨询
              </Button>
            </Link>
          </div>
        }
      />

      {messages.length === 0 ? (
        <EmptyState
          icon={Share2}
          title="暂无消息"
          description="该会话没有可展示的消息"
          tone={actualTheme}
        />
      ) : (
        <div className="space-y-4">
          {messages.map((m, idx) => {
            const role = String(m.role || '').trim()
            const isUser = role === 'user'
            const Icon = isUser ? User : Bot
            const label = isUser ? '用户' : 'AI'
            const atRaw = String(m.created_at || '').trim()
            const atText = atRaw ? new Date(atRaw).toLocaleString('zh-CN') : ''

            return (
              <Card
                key={`${idx}-${role}`}
                variant="surface"
                padding="lg"
                className={isUser ? 'border border-blue-500/10' : 'border border-amber-500/10'}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-white">
                    <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-slate-900/5 dark:bg-white/5">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span>{label}</span>
                  </div>
                  <div className="text-xs text-slate-500 dark:text-white/40">{atText}</div>
                </div>
                <div className="mt-3 text-sm text-slate-700 whitespace-pre-wrap leading-relaxed dark:text-white/70">
                  {String(m.content || '')}
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
