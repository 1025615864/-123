import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Eye, Save, RefreshCw } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import api from '../api/client'
import { Button, Card, Input, ListSkeleton } from '../components/ui'
import MarkdownContent from '../components/MarkdownContent'
import PageHeader from '../components/PageHeader'
import RichTextEditor from '../components/RichTextEditor'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useAppMutation, useToast } from '../hooks'
import { queryKeys } from '../queryKeys'
import { getApiErrorMessage } from '../utils'

type Attachment = { name: string; url: string }

interface PostDetail {
  id: number
  title: string
  content: string
  category: string
  user_id: number
  images?: string[]
  attachments?: Attachment[]
  created_at: string
  updated_at: string
}

export default function EditPostPage() {
  const { postId } = useParams<{ postId: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const queryClient = useQueryClient()
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()

  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('法律咨询')
  const [content, setContent] = useState('')
  const [images, setImages] = useState<string[]>([])
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [preview, setPreview] = useState(false)

  const [dirty, setDirty] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null)

  const postCategories = useMemo(() => ['法律咨询', '经验分享', '案例讨论', '政策解读', '其他'], [])

  const postQueryKey = queryKeys.forumPost(postId)

  const postQuery = useQuery({
    queryKey: postQueryKey,
    queryFn: async () => {
      const res = await api.get(`/forum/posts/${postId}`)
      return res.data as PostDetail
    },
    enabled: !!postId,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!postQuery.error) return
    toast.error(getApiErrorMessage(postQuery.error))
  }, [postQuery.error, toast])

  useEffect(() => {
    if (!postQuery.data) return
    const data = postQuery.data
    setTitle(data.title || '')
    setCategory(data.category || '法律咨询')
    setContent(data.content || '')
    setImages(Array.isArray(data.images) ? data.images : [])
    setAttachments(Array.isArray(data.attachments) ? data.attachments : [])
    const t = new Date(data.updated_at || data.created_at).getTime()
    setLastSavedAt(Number.isNaN(t) ? null : t)
    setDirty(false)
  }, [postQuery.data])

  const handleTitleChange = (v: string) => {
    setTitle(v)
    setDirty(true)
  }

  const handleCategoryChange = (v: string) => {
    setCategory(v)
    setDirty(true)
  }

  const handleContentChange = (v: string) => {
    setContent(v)
    setDirty(true)
  }

  const handleImagesChange = (v: string[]) => {
    setImages(v)
    setDirty(true)
  }

  const handleAttachmentsChange = (v: Attachment[]) => {
    setAttachments(v)
    setDirty(true)
  }

  const updateMutation = useAppMutation<{ id: number }, void>({
    mutationFn: async () => {
      const res = await api.put(`/forum/posts/${postId}`, {
        title,
        category,
        content,
        images,
        attachments,
      })
      return res.data as { id: number }
    },
    errorMessageFallback: '保存失败，请稍后重试',
    onSuccess: async () => {
      if (!postId) return
      setDirty(false)
      setLastSavedAt(Date.now())
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: postQueryKey }),
        queryClient.invalidateQueries({ queryKey: queryKeys.forumPostsRoot() }),
      ])
      toast.success('已保存')
      navigate(`/forum/post/${postId}`)
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, '保存失败，请稍后重试'))
    },
  })

  const actionBusy = updateMutation.isPending

  const saveStatusText = useMemo(() => {
    if (updateMutation.isPending) return '保存中...'
    if (dirty) return '未保存'
    if (lastSavedAt) return `已保存 ${new Date(lastSavedAt).toLocaleTimeString()}`
    return '已保存'
  }, [dirty, lastSavedAt, updateMutation.isPending])

  const handleSave = () => {
    if (!isAuthenticated) {
      toast.error('请先登录')
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
    if (!dirty) {
      toast.info('内容未修改')
      return
    }
    if (actionBusy) return
    updateMutation.mutate()
  }

  if (postQuery.isLoading && !postQuery.data) {
    return (
      <div className="space-y-8">
        <ListSkeleton count={4} />
      </div>
    )
  }

  if (!postQuery.data) {
    return (
      <div className="text-center py-20">
        <p className="text-slate-600 dark:text-white/50">帖子不存在或已被删除</p>
        <Link to="/forum" className="text-amber-600 hover:underline mt-4 inline-block dark:text-amber-400">
          返回论坛
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <Link
        to={`/forum/post/${postId}`}
        onClick={(e) => {
          if (actionBusy) e.preventDefault()
        }}
        aria-disabled={actionBusy}
        className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors dark:text-white/60 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        返回帖子
      </Link>

      <PageHeader
        eyebrow="社区交流"
        title="编辑帖子"
        description="支持 Markdown、图片和附件"
        tone={actualTheme}
        layout="mdCenter"
        right={
          <div className="flex flex-wrap gap-3">
            <div className="flex items-center text-xs text-slate-500 px-2 dark:text-white/45">
              {saveStatusText}
            </div>
            <Button
              variant={preview ? 'secondary' : 'outline'}
              icon={Eye}
              onClick={() => {
                if (actionBusy) return
                setPreview((p) => !p)
              }}
              disabled={actionBusy}
            >
              {preview ? '编辑' : '预览'}
            </Button>
            <Button
              variant="outline"
              icon={RefreshCw}
              onClick={() => postQuery.refetch()}
              isLoading={postQuery.isFetching}
              loadingText="刷新中..."
              disabled={postQuery.isFetching || actionBusy}
            >
              刷新
            </Button>
            <Button
              icon={Save}
              onClick={handleSave}
              isLoading={updateMutation.isPending}
              loadingText="保存中..."
              disabled={updateMutation.isPending || !dirty}
            >
              保存
            </Button>
          </div>
        }
      />

      <Card variant="surface" padding="lg">
        <div className={`space-y-5 ${actionBusy ? 'opacity-60 pointer-events-none' : ''}`}>
          <Input
            label="标题"
            value={title}
            onChange={(e) => handleTitleChange(e.target.value)}
            placeholder="请用一句话描述你的问题/观点"
            disabled={actionBusy}
          />

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">分类</label>
            <select
              value={category}
              onChange={(e) => handleCategoryChange(e.target.value)}
              disabled={actionBusy}
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
                onChange={handleContentChange}
                images={images}
                onImagesChange={handleImagesChange}
                attachments={attachments}
                onAttachmentsChange={handleAttachmentsChange}
                placeholder="请输入内容，支持 Markdown、表情、图片和附件链接..."
                minHeight="260px"
              />
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
