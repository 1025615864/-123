import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Eye, FileText, Send } from 'lucide-react'

import { Button, Card, Input, Loading } from '../components/ui'
import RichTextEditor from '../components/RichTextEditor'
import MarkdownContent from '../components/MarkdownContent'
import PageHeader from '../components/PageHeader'

import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useAppMutation, useToast } from '../hooks'
import { getApiErrorMessage, storage } from '../utils'
import { queryKeys } from '../queryKeys'

const DRAFTS_KEY = 'forum:postDrafts'
const LEGACY_DRAFT_KEY = 'forum:newPostDraft'

type Attachment = { name: string; url: string }

interface DraftPayload {
  id: string
  title: string
  category: string
  content: string
  images: string[]
  attachments: Attachment[]
  createdAt: number
  updatedAt: number
}

function safeArray<T>(v: unknown): T[] {
  return Array.isArray(v) ? (v as T[]) : []
}

function createDraftId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

export default function NewPostPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const toast = useToast()
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()

  const draftParam = searchParams.get('draft')

  const [draftId, setDraftId] = useState<string | null>(null)
  const [draftCreatedAt, setDraftCreatedAt] = useState<number>(Date.now())

  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('法律咨询')
  const [content, setContent] = useState('')
  const [images, setImages] = useState<string[]>([])
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [preview, setPreview] = useState(false)
  const [hydrated, setHydrated] = useState(false)

  const postCategories = useMemo(() => ['法律咨询', '经验分享', '案例讨论', '政策解读', '其他'], [])

  useEffect(() => {
    const raw = storage.get<unknown>(DRAFTS_KEY, [])
    const drafts = safeArray<DraftPayload>(raw)

    if (draftParam) {
      const existing = drafts.find((d) => d && d.id === draftParam)
      if (existing) {
        setDraftId(existing.id)
        setDraftCreatedAt(existing.createdAt || Date.now())
        setTitle(existing.title || '')
        setCategory(existing.category || '法律咨询')
        setContent(existing.content || '')
        setImages(Array.isArray(existing.images) ? existing.images : [])
        setAttachments(Array.isArray(existing.attachments) ? existing.attachments : [])
        setHydrated(true)
        return
      }
    }

    const legacy = storage.get<Omit<DraftPayload, 'id' | 'createdAt'>>(LEGACY_DRAFT_KEY)
    if (legacy && (legacy.title || legacy.content || (legacy.images?.length ?? 0) > 0 || (legacy.attachments?.length ?? 0) > 0)) {
      const id = createDraftId()
      const now = Date.now()
      const payload: DraftPayload = {
        id,
        title: legacy.title || '',
        category: legacy.category || '法律咨询',
        content: legacy.content || '',
        images: Array.isArray(legacy.images) ? legacy.images : [],
        attachments: Array.isArray(legacy.attachments) ? legacy.attachments : [],
        createdAt: now,
        updatedAt: legacy.updatedAt || now,
      }
      storage.remove(LEGACY_DRAFT_KEY)
      storage.set(DRAFTS_KEY, [payload, ...drafts])
      setDraftId(id)
      setDraftCreatedAt(payload.createdAt)
      setTitle(payload.title)
      setCategory(payload.category)
      setContent(payload.content)
      setImages(payload.images)
      setAttachments(payload.attachments)
      setHydrated(true)
      return
    }

    const id = createDraftId()
    setDraftId(id)
    setDraftCreatedAt(Date.now())
    setTitle('')
    setCategory('法律咨询')
    setContent('')
    setImages([])
    setAttachments([])
    setPreview(false)
    setHydrated(true)
  }, [draftParam])

  useEffect(() => {
    if (!hydrated) return
    if (!draftId) return
    const timer = window.setTimeout(() => {
      const isEmpty =
        !title.trim() &&
        !content.trim() &&
        (images?.length ?? 0) === 0 &&
        (attachments?.length ?? 0) === 0

      const payload: DraftPayload = {
        id: draftId,
        title,
        category,
        content,
        images,
        attachments,
        createdAt: draftCreatedAt,
        updatedAt: Date.now(),
      }

      const raw = storage.get<unknown>(DRAFTS_KEY, [])
      const drafts = safeArray<DraftPayload>(raw)
      const idx = drafts.findIndex((d) => d && d.id === draftId)

      if (isEmpty) {
        if (idx >= 0) {
          storage.set(
            DRAFTS_KEY,
            drafts.filter((d) => d && d.id !== draftId)
          )
        }
        return
      }

      const next = [...drafts]
      if (idx >= 0) {
        next[idx] = payload
      } else {
        next.unshift(payload)
      }
      storage.set(DRAFTS_KEY, next)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [title, category, content, images, attachments, hydrated, draftId, draftCreatedAt])

  const clearDraft = () => {
    if (draftId) {
      const raw = storage.get<unknown>(DRAFTS_KEY, [])
      const drafts = safeArray<DraftPayload>(raw)
      storage.set(
        DRAFTS_KEY,
        drafts.filter((d) => d && d.id !== draftId)
      )
    }
    setTitle('')
    setCategory('法律咨询')
    setContent('')
    setImages([])
    setAttachments([])
    const nextId = createDraftId()
    setDraftId(nextId)
    setDraftCreatedAt(Date.now())
    navigate('/forum/new', { replace: true })
    toast.success('草稿已清空')
  }

  const publishMutation = useAppMutation<{ id: number; review_status?: string | null }, void>({
    mutationFn: async () => {
      const res = await api.post('/forum/posts', {
        title,
        category,
        content,
        images,
        attachments,
      })
      return res.data as { id: number; review_status?: string | null }
    },
    errorMessageFallback: '发布失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.forumPostsRoot()],
    onSuccess: (data) => {
      if (draftId) {
        const raw = storage.get<unknown>(DRAFTS_KEY, [])
        const drafts = safeArray<DraftPayload>(raw)
        storage.set(
          DRAFTS_KEY,
          drafts.filter((d) => d && d.id !== draftId)
        )
      }
      toast.success('发布成功')
      if (data?.review_status === 'pending') {
        toast.info('帖子已提交审核，通过后将展示')
      }
      const id = (data as any)?.id
      if (id) {
        navigate(`/forum/post/${id}`)
        return
      }
      navigate('/forum')
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, '发布失败，请稍后重试'))
    },
  })

  const handlePublish = () => {
    if (!isAuthenticated) {
      toast.error('请先登录后再发帖')
      navigate('/login')
      return
    }
    if (!title.trim()) {
      toast.error('请填写标题')
      return
    }
    if (!content.trim()) {
      toast.error('请填写内容')
      return
    }
    if (publishMutation.isPending) return
    publishMutation.mutate()
  }

  if (!hydrated) {
    return <Loading text="加载中..." tone={actualTheme} />
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
        title="发布帖子"
        description="支持图片内嵌、附件插入，并自动保存草稿"
        tone={actualTheme}
        layout="mdCenter"
        right={
          <div className="flex flex-wrap gap-3">
            <Button
              variant={preview ? 'secondary' : 'outline'}
              icon={Eye}
              onClick={() => setPreview((p) => !p)}
            >
              {preview ? '编辑' : '预览'}
            </Button>
            <Button
              variant="outline"
              icon={FileText}
              onClick={() => navigate('/forum/drafts')}
            >
              草稿箱
            </Button>
            <Button variant="outline" onClick={clearDraft}>
              清空草稿
            </Button>
            <Button icon={Send} onClick={handlePublish} isLoading={publishMutation.isPending}>
              发布
            </Button>
          </div>
        }
      />

      <Card variant="surface" padding="lg">
        <div className="space-y-5">
          <Input
            label="标题"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="请用一句话描述你的问题/观点"
          />

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">分类</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition hover:border-slate-300 focus-visible:border-amber-500/50 focus-visible:ring-2 focus-visible:ring-amber-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-900"
            >
              {postCategories.map((cat) => (
                <option key={cat} value={cat} className="bg-white text-slate-900 dark:bg-[#0f0a1e] dark:text-white">
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {preview ? (
            <div className="rounded-2xl border border-slate-200/70 bg-white p-5 dark:border-white/10 dark:bg-[#0f0a1e]/60">
              <MarkdownContent content={content || '（暂无内容）'} />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">内容</label>
              <RichTextEditor
                value={content}
                onChange={setContent}
                images={images}
                onImagesChange={setImages}
                attachments={attachments}
                onAttachmentsChange={setAttachments}
                placeholder="请输入内容，支持 Markdown、表情、图片和附件链接..."
                minHeight="260px"
              />
              <p className="text-xs text-slate-500 mt-2 dark:text-white/40">
                已自动保存草稿（本地）。图片会以 Markdown 形式插入到正文中。
              </p>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
