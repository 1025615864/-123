import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Eye, Save, RefreshCw } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import api from '../api/client'
import { Button, Card, Input, ListSkeleton, Textarea } from '../components/ui'
import MarkdownContent from '../components/MarkdownContent'
import PageHeader from '../components/PageHeader'
import RichTextEditor from '../components/RichTextEditor'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useAppMutation, useToast } from '../hooks'
import { queryKeys } from '../queryKeys'
import { getApiErrorMessage } from '../utils'

type Attachment = { name: string; url: string }

type StructuredFields = {
  facts: string
  issues: string
  evidence: string
  claims: string
  progress: string
}

function escapeRegExp(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function upsertSection(base: string, heading: string, body: string): string {
  const src = String(base ?? '')
  const h = String(heading ?? '').trim()
  const safeBody = String(body ?? '').trim()
  if (!h) return src

  const normalized = src.replace(/\r\n/g, '\n')
  const headingRe = new RegExp(`^##\\s+${escapeRegExp(h)}\\s*$`, 'm')
  const m = normalized.match(headingRe)
  const nextChunk = `\n\n## ${h}\n\n${safeBody}\n`

  if (!m || typeof (m as any).index !== 'number') {
    if (!normalized.trim()) return nextChunk.trim() + '\n'
    return normalized.trimEnd() + nextChunk
  }

  const idx = (m as any).index as number
  const afterHeading = normalized.indexOf('\n', idx)
  const start = afterHeading === -1 ? normalized.length : afterHeading + 1

  const rest = normalized.slice(start)
  const nextHeadingRe = /^##\s+.+$/m
  const nextMatch = rest.match(nextHeadingRe)
  const end = nextMatch && typeof (nextMatch as any).index === 'number' ? start + ((nextMatch as any).index as number) : normalized.length

  const prefix = normalized.slice(0, start)
  const suffix = normalized.slice(end)
  const injected = `\n${safeBody}\n`

  return (prefix.trimEnd() + injected + suffix.trimStart()).trim() + '\n'
}

function buildStructuredMarkdown(fields: StructuredFields): string {
  const facts = String(fields.facts || '').trim() || '（请填写：时间、地点、人物、经过）'
  const issues = String(fields.issues || '').trim() || '（请填写：核心争议点/你最关心的问题）'
  const evidence = String(fields.evidence || '').trim() || '（请填写：聊天记录、转账记录、合同、录音等）'
  const claims = String(fields.claims || '').trim() || '（请填写：希望达到的结果/诉求）'
  const progress = String(fields.progress || '').trim() || '（请填写：目前进展、关键时间点、是否已协商/报警/起诉等）'

  return (
    `## 案情经过\n\n${facts}\n\n` +
    `## 争议焦点\n\n${issues}\n\n` +
    `## 证据线索\n\n${evidence}\n\n` +
    `## 诉求/目标\n\n${claims}\n\n` +
    `## 进展与时间线\n\n${progress}\n`
  )
}

function hasStructuredAny(fields: StructuredFields): boolean {
  return Boolean(
    String(fields.facts || '').trim() ||
      String(fields.issues || '').trim() ||
      String(fields.evidence || '').trim() ||
      String(fields.claims || '').trim() ||
      String(fields.progress || '').trim()
  )
}

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

  const [structuredEnabled, setStructuredEnabled] = useState(false)
  const [caseFacts, setCaseFacts] = useState('')
  const [caseIssues, setCaseIssues] = useState('')
  const [caseEvidence, setCaseEvidence] = useState('')
  const [caseClaims, setCaseClaims] = useState('')
  const [caseProgress, setCaseProgress] = useState('')

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
    setStructuredEnabled(false)
    setCaseFacts('')
    setCaseIssues('')
    setCaseEvidence('')
    setCaseClaims('')
    setCaseProgress('')
    const t = new Date(data.updated_at || data.created_at).getTime()
    setLastSavedAt(Number.isNaN(t) ? null : t)
    setDirty(false)
  }, [postQuery.data])

  const currentStructuredFields: StructuredFields = useMemo(
    () => ({
      facts: caseFacts,
      issues: caseIssues,
      evidence: caseEvidence,
      claims: caseClaims,
      progress: caseProgress,
    }),
    [caseClaims, caseEvidence, caseFacts, caseIssues, caseProgress]
  )

  const buildMergedContent = (): string => {
    if (!structuredEnabled || !hasStructuredAny(currentStructuredFields)) {
      return String(content || '')
    }
    let next = String(content || '')
    if (!next.trim()) return buildStructuredMarkdown(currentStructuredFields)
    next = upsertSection(next, '案情经过', String(currentStructuredFields.facts || '').trim() || '（请填写：时间、地点、人物、经过）')
    next = upsertSection(next, '争议焦点', String(currentStructuredFields.issues || '').trim() || '（请填写：核心争议点/你最关心的问题）')
    next = upsertSection(next, '证据线索', String(currentStructuredFields.evidence || '').trim() || '（请填写：聊天记录、转账记录、合同、录音等）')
    next = upsertSection(next, '诉求/目标', String(currentStructuredFields.claims || '').trim() || '（请填写：希望达到的结果/诉求）')
    next = upsertSection(next, '进展与时间线', String(currentStructuredFields.progress || '').trim() || '（请填写：目前进展、关键时间点、是否已协商/报警/起诉等）')
    return next
  }

  const syncStructuredToContent = (mode: 'merge' | 'replace' | 'append') => {
    if (!structuredEnabled) {
      toast.info('请先开启结构化模板')
      return
    }
    const hasAny = hasStructuredAny(currentStructuredFields)
    const template = buildStructuredMarkdown(currentStructuredFields)
    if (!hasAny && mode !== 'replace') {
      toast.info('模板字段为空')
      return
    }

    if (mode === 'replace') {
      setContent(template)
      setDirty(true)
      toast.success('已生成模板到正文')
      return
    }

    if (mode === 'append') {
      const next = (String(content || '').trimEnd() + '\n\n' + template).trim() + '\n'
      setContent(next)
      setDirty(true)
      toast.success('已插入模板到正文')
      return
    }

    const merged = buildMergedContent()
    setContent(merged)
    setDirty(true)
    toast.success('已同步到正文')
  }

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

  const updateMutation = useAppMutation<{ id: number }, { content: string }>({
    mutationFn: async ({ content: finalContent }) => {
      const res = await api.put(`/forum/posts/${postId}`, {
        title,
        category,
        content: finalContent,
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
    const finalContent = buildMergedContent()
    if (!finalContent.trim()) {
      toast.error('请填写内容')
      return
    }
    if (finalContent !== content) {
      setContent(finalContent)
      setDirty(true)
    }
    updateMutation.mutate({ content: finalContent })
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
                if (!preview && structuredEnabled && hasStructuredAny(currentStructuredFields)) {
                  syncStructuredToContent(content.trim() ? 'merge' : 'replace')
                }
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

          <div className="rounded-2xl border border-slate-200/70 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/5">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-900 dark:text-white">结构化发帖模板</div>
                <div className="text-xs text-slate-500 mt-1 dark:text-white/45">
                  可选：用案情要素组织内容，再同步到正文
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant={structuredEnabled ? 'secondary' : 'outline'}
                  onClick={() => {
                    setStructuredEnabled((v) => !v)
                    setDirty(true)
                  }}
                  disabled={actionBusy}
                >
                  {structuredEnabled ? '已开启' : '开启'}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (actionBusy) return
                    syncStructuredToContent(content.trim() ? 'merge' : 'replace')
                  }}
                  disabled={actionBusy || !structuredEnabled}
                >
                  同步到正文
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (actionBusy) return
                    syncStructuredToContent('append')
                  }}
                  disabled={actionBusy || !structuredEnabled}
                >
                  插入模板
                </Button>
              </div>
            </div>

            {structuredEnabled ? (
              <div className="mt-4 grid grid-cols-1 gap-4">
                <Textarea
                  label="案情经过"
                  value={caseFacts}
                  onChange={(e) => {
                    setCaseFacts(e.target.value)
                    setDirty(true)
                  }}
                  rows={4}
                  placeholder="时间、地点、人物、经过..."
                  disabled={actionBusy}
                />
                <Textarea
                  label="争议焦点"
                  value={caseIssues}
                  onChange={(e) => {
                    setCaseIssues(e.target.value)
                    setDirty(true)
                  }}
                  rows={3}
                  placeholder="你最想解决的问题/争议点..."
                  disabled={actionBusy}
                />
                <Textarea
                  label="证据线索"
                  value={caseEvidence}
                  onChange={(e) => {
                    setCaseEvidence(e.target.value)
                    setDirty(true)
                  }}
                  rows={3}
                  placeholder="合同、聊天记录、转账记录、录音、证人..."
                  disabled={actionBusy}
                />
                <Textarea
                  label="诉求/目标"
                  value={caseClaims}
                  onChange={(e) => {
                    setCaseClaims(e.target.value)
                    setDirty(true)
                  }}
                  rows={3}
                  placeholder="希望对方做什么/你希望达到的结果..."
                  disabled={actionBusy}
                />
                <Textarea
                  label="进展与时间线"
                  value={caseProgress}
                  onChange={(e) => {
                    setCaseProgress(e.target.value)
                    setDirty(true)
                  }}
                  rows={3}
                  placeholder="目前进展、关键时间点、是否协商/报警/起诉..."
                  disabled={actionBusy}
                />
              </div>
            ) : null}
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
