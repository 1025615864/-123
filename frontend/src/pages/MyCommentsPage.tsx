import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, MessageSquare } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'

import api from '../api/client'
import PageHeader from '../components/PageHeader'
import { Badge, Button, Card, Chip, EmptyState, Loading, Pagination } from '../components/ui'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useToast } from '../hooks'
import { queryKeys } from '../queryKeys'
import { getApiErrorMessage } from '../utils'

interface MyCommentItem {
  id: number
  post_id: number
  post_title: string | null
  content: string
  created_at: string
  review_status: string | null
  review_reason: string | null
}

interface MyCommentsListResponse {
  items: MyCommentItem[]
  total: number
  page: number
  page_size: number
}

function getExcerpt(content: string, maxLen: number): string {
  const withoutImages = content.replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
  const withoutLinks = withoutImages.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
  const withoutMd = withoutLinks
    .replace(/[`*_>#]/g, ' ')
    .replace(/\r\n/g, '\n')
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (withoutMd.length <= maxLen) return withoutMd
  return withoutMd.slice(0, maxLen) + '...'
}

function getStatusLabel(status: string | null): { text: string; variant: 'warning' | 'danger' | 'success' | 'primary' } {
  if (status === 'pending') return { text: '审核中', variant: 'warning' }
  if (status === 'rejected') return { text: '已驳回', variant: 'danger' }
  if (status === 'approved' || status === null) return { text: '已通过', variant: 'success' }
  return { text: status, variant: 'primary' }
}

export default function MyCommentsPage() {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()

  const [page, setPage] = useState(1)
  const pageSize = 20
  const [status, setStatus] = useState<'all' | 'pending' | 'approved' | 'rejected'>('all')

  useEffect(() => {
    setPage(1)
  }, [status])

  const queryKey = useMemo(() => queryKeys.forumMyComments(page, pageSize, status), [page, pageSize, status])

  const commentsQuery = useQuery({
    queryKey,
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('page', String(page))
      params.set('page_size', String(pageSize))
      params.set('status', status)
      const res = await api.get(`/forum/me/comments?${params.toString()}`)
      const data = res.data as MyCommentsListResponse
      return {
        items: Array.isArray(data?.items) ? data.items : [],
        total: Number(data?.total || 0),
        page: Number((data as any)?.page || page),
        page_size: Number((data as any)?.page_size || pageSize),
      } as MyCommentsListResponse
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!commentsQuery.error) return
    toast.error(getApiErrorMessage(commentsQuery.error))
  }, [commentsQuery.error, toast])

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="社区交流"
          title="我的评论"
          description="登录后可查看你发布的评论与审核状态"
          layout="mdStart"
          tone={actualTheme}
        />

        <EmptyState
          icon={MessageSquare}
          title="请先登录"
          description="登录后即可查看你的评论"
          tone={actualTheme}
          action={
            <Link to="/login" className="mt-6 inline-block">
              <Button>去登录</Button>
            </Link>
          }
        />
      </div>
    )
  }

  const items = commentsQuery.data?.items ?? []
  const total = commentsQuery.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="space-y-8">
      <Link
        to="/forum"
        className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors dark:text-white/60 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        返回论坛
      </Link>

      <PageHeader
        eyebrow="社区交流"
        title="我的评论"
        description="查看你发布的评论与审核状态"
        tone={actualTheme}
        layout="mdCenter"
      />

      <div className="flex flex-wrap gap-3">
        {(
          [
            { key: 'all', label: '全部' },
            { key: 'pending', label: '审核中' },
            { key: 'approved', label: '已通过' },
            { key: 'rejected', label: '已驳回' },
          ] as const
        ).map((it) => (
          <Chip key={it.key} active={status === it.key} onClick={() => setStatus(it.key)}>
            {it.label}
          </Chip>
        ))}
      </div>

      {commentsQuery.isLoading && items.length === 0 ? (
        <Loading text="加载中..." tone={actualTheme} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="暂无评论"
          description="你发布的评论会显示在这里"
          tone={actualTheme}
        />
      ) : (
        <Card variant="surface" padding="none">
          <div className="divide-y divide-slate-200/70 dark:divide-white/10">
            {items.map((c) => {
              const statusUi = getStatusLabel(c.review_status)
              const excerpt = getExcerpt(c.content || '', 140)
              const link = `/forum/post/${c.post_id}?commentId=${c.id}#comment-${c.id}`
              return (
                <div key={c.id} className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        to={link}
                        className="text-sm font-medium text-slate-900 hover:underline dark:text-white"
                      >
                        {c.post_title?.trim() ? c.post_title : `帖子 #${c.post_id}`}
                      </Link>
                      <p className="text-xs text-slate-500 mt-1 dark:text-white/40">
                        {new Date(c.created_at).toLocaleString()}
                      </p>
                    </div>

                    <Badge
                      variant={statusUi.variant}
                      size="sm"
                      title={c.review_reason || undefined}
                    >
                      {statusUi.text}
                    </Badge>
                  </div>

                  <Link to={link} className="block mt-3">
                    <p className="text-sm text-slate-700 whitespace-pre-wrap dark:text-white/70">
                      {excerpt}
                    </p>
                    {c.review_reason && c.review_status === 'rejected' ? (
                      <p className="text-xs text-slate-500 mt-2 dark:text-white/40">
                        原因：{c.review_reason}
                      </p>
                    ) : null}
                  </Link>
                </div>
              )
            })}
          </div>

          {totalPages > 1 ? (
            <div className="p-5 border-t border-slate-200/70 dark:border-white/10">
              <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
            </div>
          ) : null}
        </Card>
      )}
    </div>
  )
}
