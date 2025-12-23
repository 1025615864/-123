import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, FileText, Plus, Trash2 } from 'lucide-react'

import { Button, Card, EmptyState } from '../components/ui'
import PageHeader from '../components/PageHeader'
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

  const [drafts, setDrafts] = useState<DraftItem[]>([])

  useEffect(() => {
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
  }, [])

  const total = drafts.length

  const cards = useMemo(() => {
    return drafts.map((d) => ({
      ...d,
      excerpt: getExcerpt(d.content || '', 120),
    }))
  }, [drafts])

  const handleDelete = (id: string) => {
    const next = drafts.filter((d) => d.id !== id)
    storage.set(DRAFTS_KEY, next)
    setDrafts(next)
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
          <Button icon={Plus} onClick={() => navigate('/forum/new')}>
            新建草稿
          </Button>
        }
      />

      {total === 0 ? (
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
                  <p className="text-xs text-slate-400 mt-3 dark:text-white/30">
                    最近编辑：{new Date(d.updatedAt || d.createdAt).toLocaleString()}
                  </p>
                </div>

                <div className="flex gap-3 flex-shrink-0">
                  <Button variant="outline" onClick={() => navigate(`/forum/new?draft=${encodeURIComponent(d.id)}`)}>
                    继续编辑
                  </Button>
                  <Button variant="outline" onClick={() => handleDelete(d.id)} icon={Trash2}>
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
