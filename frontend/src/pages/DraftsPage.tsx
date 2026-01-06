import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, FileText, Plus, Trash2, RefreshCw, Image as ImageIcon, Paperclip } from 'lucide-react'

import { Button, Card, EmptyState, ListSkeleton } from '../components/ui'
import PageHeader from '../components/PageHeader'
import { useToast } from '../hooks'
import { storage } from '../utils'
import { useTheme } from '../contexts/ThemeContext'

type Attachment = { name: string; url: string }

interface DraftItem {
  id: string
  title: string
  category: string
  content: string
  images: string[]
  attachments: Attachment[]
  createdAt: number
  updatedAt: number
}

const DRAFTS_KEY = 'forum:postDrafts'

function safeArray<T>(v: unknown): T[] {
  return Array.isArray(v) ? (v as T[]) : []
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

export default function DraftsPage() {
  const navigate = useNavigate()
  const { actualTheme } = useTheme()
  const toast = useToast()

  const [drafts, setDrafts] = useState<DraftItem[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<Record<string, boolean>>({})
  const [undoState, setUndoState] = useState<{
    previous: DraftItem[]
    title: string
    expiresAt: number
  } | null>(null)
  const undoTimerRef = useRef<number | null>(null)

  const loadDrafts = () => {
    const raw = storage.get<unknown>(DRAFTS_KEY, [])
    const list = safeArray<DraftItem>(raw)
      .filter((d) => d && typeof d.id === 'string')
      .filter((d) => {
        const hasTitle = !!d.title?.trim()
        const hasContent = !!d.content?.trim()
        const hasImages = (d.images?.length ?? 0) > 0
        const hasAttachments = (d.attachments?.length ?? 0) > 0
        return hasTitle || hasContent || hasImages || hasAttachments
      })
      .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
    setDrafts(list)
  }

  useEffect(() => {
    setLoading(true)
    const id = window.requestAnimationFrame(() => {
      loadDrafts()
      setLoading(false)
    })
    return () => {
      window.cancelAnimationFrame(id)
    }
  }, [])

  useEffect(() => {
    return () => {
      if (undoTimerRef.current != null) {
        window.clearTimeout(undoTimerRef.current)
        undoTimerRef.current = null
      }
    }
  }, [])

  const total = drafts.length

  const cards = useMemo(() => {
    return drafts.map((d) => ({
      ...d,
      excerpt: getExcerpt(d.content || '', 120),
    }))
  }, [drafts])

  const totalImages = useMemo(
    () => drafts.reduce((acc, d) => acc + (Array.isArray(d.images) ? d.images.length : 0), 0),
    [drafts]
  )

  const totalAttachments = useMemo(
    () => drafts.reduce((acc, d) => acc + (Array.isArray(d.attachments) ? d.attachments.length : 0), 0),
    [drafts]
  )

  const handleRefresh = () => {
    if (refreshing) return
    setRefreshing(true)
    try {
      loadDrafts()
      toast.success('已刷新草稿箱')
    } finally {
      setRefreshing(false)
    }
  }

  const scheduleUndoClear = (expiresAt: number) => {
    if (undoTimerRef.current != null) {
      window.clearTimeout(undoTimerRef.current)
      undoTimerRef.current = null
    }
    undoTimerRef.current = window.setTimeout(() => {
      setUndoState((prev) => {
        if (!prev) return null
        if (prev.expiresAt !== expiresAt) return prev
        return null
      })
    }, Math.max(0, expiresAt - Date.now()))
  }

  const handleUndoDelete = () => {
    if (!undoState) return
    try {
      storage.set(DRAFTS_KEY, undoState.previous)
      setDrafts(undoState.previous)
      toast.success('已撤销删除')
      setUndoState(null)
    } catch {
      toast.error('撤销失败，请稍后重试')
    }
  }

  const handleDelete = (id: string) => {
    if (pendingDelete[id]) return
    setPendingDelete((prev) => ({ ...prev, [id]: true }))

    const previous = drafts
    const next = drafts.filter((d) => d.id !== id)
    const deleted = drafts.find((d) => d.id === id)
    setDrafts(next)

    try {
      storage.set(DRAFTS_KEY, next)
      const expiresAt = Date.now() + 5000
      setUndoState({
        previous,
        title: deleted?.title?.trim() ? deleted.title : '（无标题草稿）',
        expiresAt,
      })
      scheduleUndoClear(expiresAt)
      toast.success('已删除草稿（5 秒内可撤销）')
    } catch (err) {
      setDrafts(previous)
      toast.error('删除失败，请稍后重试')
    } finally {
      setPendingDelete((prev) => {
        const nextMap = { ...prev }
        delete nextMap[id]
        return nextMap
      })
    }
  }

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
        title="草稿箱"
        description="本地保存的草稿列表，可继续编辑或删除"
        tone={actualTheme}
        layout="mdCenter"
        right={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              icon={RefreshCw}
              isLoading={refreshing}
              loadingText="刷新中..."
              onClick={handleRefresh}
              disabled={refreshing}
            >
              刷新
            </Button>
            <Button icon={Plus} onClick={() => navigate('/forum/new')}>
              新建草稿
            </Button>
          </div>
        }
      />

      {undoState ? (
        <Card variant="surface" padding="md" className="rounded-2xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-medium text-slate-900 dark:text-white line-clamp-1">
                已删除：{undoState.title}
              </div>
              <div className="text-xs text-slate-500 mt-1 dark:text-white/45">5 秒内可撤销</div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <Button variant="outline" size="sm" onClick={handleUndoDelete}>
                撤销
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setUndoState(null)}>
                关闭
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {loading ? (
        <ListSkeleton count={4} />
      ) : total === 0 ? (
        <EmptyState
          icon={FileText}
          title="暂无草稿"
          description="去发布一个新帖子，草稿会自动保存到这里"
          size="lg"
          action={
            <div className="mt-6">
              <Button icon={Plus} onClick={() => navigate('/forum/new')}>
                去写帖子
              </Button>
            </div>
          }
        />
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-white/45">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200/70 bg-white px-3 py-1 dark:border-white/10 dark:bg-white/5">
              共 {total} 条
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200/70 bg-white px-3 py-1 dark:border-white/10 dark:bg-white/5">
              <ImageIcon className="h-3.5 w-3.5" />
              图片 {totalImages}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200/70 bg-white px-3 py-1 dark:border-white/10 dark:bg-white/5">
              <Paperclip className="h-3.5 w-3.5" />
              附件 {totalAttachments}
            </span>
          </div>
          {cards.map((d) => (
            <Card key={d.id} variant="surface" padding="lg" className="rounded-3xl">
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-5">
                <div className="min-w-0">
                  <p className="text-xs text-slate-500 dark:text-white/40">{d.category || '未分类'}</p>
                  <h3 className="text-lg font-semibold text-slate-900 mt-1 line-clamp-1 dark:text-white">
                    {d.title?.trim() ? d.title : '（无标题草稿）'}
                  </h3>
                  <p className="text-sm text-slate-600 mt-2 line-clamp-2 dark:text-white/50">
                    {d.excerpt || '（暂无内容）'}
                  </p>
                  <div className="mt-3 space-y-1 text-xs text-slate-400 dark:text-white/30">
                    <div>最近编辑：{new Date(d.updatedAt || d.createdAt).toLocaleString()}</div>
                    <div>
                      {Array.isArray(d.images) && d.images.length > 0 ? `图片：${d.images.length}` : '图片：0'}
                      {' · '}
                      {Array.isArray(d.attachments) && d.attachments.length > 0
                        ? `附件：${d.attachments.length}`
                        : '附件：0'}
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 flex-shrink-0">
                  <Button variant="outline" onClick={() => navigate(`/forum/new?draft=${encodeURIComponent(d.id)}`)}>
                    继续编辑
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => handleDelete(d.id)}
                    icon={Trash2}
                    isLoading={Boolean(pendingDelete[d.id])}
                    loadingText="删除中..."
                    disabled={Boolean(pendingDelete[d.id])}
                  >
                    删除
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
