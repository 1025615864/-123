import { useMemo, useState } from 'react'
import { Search, Plus, Edit, Trash2, Eye, EyeOff, Pin } from 'lucide-react'
import { Card, Input, Button, Badge, Modal, Loading, Pagination } from '../../components/ui'
import { useQuery } from '@tanstack/react-query'
import api from '../../api/client'
import { useAppMutation, useToast } from '../../hooks'
import { useTheme } from '../../contexts/ThemeContext'
import { getApiErrorMessage } from '../../utils'
import RichTextEditor from '../../components/RichTextEditor'

function extractMarkdownImageUrls(content: string): string[] {
  if (!content) return []
  const urls: string[] = []
  const re = /!\[[^\]]*\]\(([^)]+)\)/g
  let match: RegExpExecArray | null
  while ((match = re.exec(content)) !== null) {
    const url = match?.[1]
    if (typeof url === 'string' && url.trim()) urls.push(url.trim())
  }
  return Array.from(new Set(urls))
}

interface NewsItem {
  id: number
  title: string
  category: string
  summary?: string | null
  cover_image?: string | null
  source?: string | null
  author?: string | null
  is_top: boolean
  is_published: boolean
  view_count: number
  published_at?: string | null
  created_at: string
  updated_at?: string
}

interface NewsAdminListResponse {
  items: NewsItem[]
  total: number
  page: number
  page_size: number
}

export default function NewsManagePage() {
  const { actualTheme } = useTheme()
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const toast = useToast()

  const [createImages, setCreateImages] = useState<string[]>([])
  const [editImages, setEditImages] = useState<string[]>([])

  const [createForm, setCreateForm] = useState({
    title: '',
    category: '法律动态',
    summary: '',
    cover_image: '',
    source: '',
    author: '',
    content: '',
    is_top: false,
    is_published: true,
  })

  const [editForm, setEditForm] = useState({
    title: '',
    category: '法律动态',
    summary: '',
    cover_image: '',
    source: '',
    author: '',
    content: '',
    is_top: false,
    is_published: true,
  })

  const newsQueryKey = useMemo(
    () => ['admin-news', { keyword: keyword.trim(), page, pageSize }] as const,
    [keyword, page, pageSize]
  )

  const newsQuery = useQuery({
    queryKey: newsQueryKey,
    queryFn: async () => {
      const trimmed = keyword.trim()
      const params: any = { page, page_size: pageSize }
      if (trimmed) params.keyword = trimmed
      const res = await api.get('/news/admin/all', { params })
      return res.data as NewsAdminListResponse
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const news = newsQuery.data?.items ?? []
  const total = newsQuery.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const loading = newsQuery.isLoading
  const loadError = newsQuery.isError ? getApiErrorMessage(newsQuery.error, '新闻列表加载失败，请稍后重试') : null

  const deleteMutation = useAppMutation<void, number>({
    mutationFn: async (id) => {
      await api.delete(`/news/${id}`)
    },
    successMessage: '删除成功',
    errorMessageFallback: '删除失败，请稍后重试',
    invalidateQueryKeys: [newsQueryKey as any],
  })

  const togglePublishMutation = useAppMutation<void, { id: number; is_published: boolean }>({
    mutationFn: async (payload) => {
      await api.put(`/news/${payload.id}`, { is_published: payload.is_published })
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: (_res, payload) => {
      toast.success(payload.is_published ? '已发布' : '已取消发布')
    },
  })

  const toggleTopMutation = useAppMutation<void, { id: number; is_top: boolean }>({
    mutationFn: async (payload) => {
      await api.put(`/news/${payload.id}`, { is_top: payload.is_top })
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: (_res, payload) => {
      toast.success(payload.is_top ? '已置顶' : '已取消置顶')
    },
  })

  const createMutation = useAppMutation<
    void,
    {
      title: string
      category: string
      summary?: string | null
      cover_image?: string | null
      source?: string | null
      author?: string | null
      content: string
      is_top: boolean
      is_published: boolean
    }
  >({
    mutationFn: async (payload) => {
      await api.post('/news', payload)
    },
    successMessage: '发布成功',
    errorMessageFallback: '发布失败，请稍后重试',
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: () => {
      setShowCreateModal(false)
      setCreateImages([])
      setCreateForm({
        title: '',
        category: '法律动态',
        summary: '',
        cover_image: '',
        source: '',
        author: '',
        content: '',
        is_top: false,
        is_published: true,
      })
    },
  })

  const editMutation = useAppMutation<
    void,
    {
      id: number
      payload: {
        title: string
        category: string
        summary?: string | null
        cover_image?: string | null
        source?: string | null
        author?: string | null
        content: string
        is_top: boolean
        is_published: boolean
      }
    }
  >({
    mutationFn: async ({ id, payload }) => {
      await api.put(`/news/${id}`, payload)
    },
    successMessage: '保存成功',
    errorMessageFallback: '保存失败，请稍后重试',
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: () => {
      setShowEditModal(false)
      setEditingId(null)
    },
  })

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除这篇新闻吗？')) return
    if (deleteMutation.isPending) return
    deleteMutation.mutate(id)
  }

  const togglePublish = async (id: number, currentStatus: boolean) => {
    if (togglePublishMutation.isPending) return
    togglePublishMutation.mutate({ id, is_published: !currentStatus })
  }

  const toggleTop = async (id: number, currentTop: boolean) => {
    if (toggleTopMutation.isPending) return
    toggleTopMutation.mutate({ id, is_top: !currentTop })
  }

  const handleCreate = async () => {
    if (!createForm.title.trim() || !createForm.content.trim()) return
    if (createMutation.isPending) return
    createMutation.mutate({
      title: createForm.title.trim(),
      category: createForm.category,
      summary: createForm.summary.trim() ? createForm.summary.trim() : null,
      cover_image: createForm.cover_image.trim() ? createForm.cover_image.trim() : null,
      source: createForm.source.trim() ? createForm.source.trim() : null,
      author: createForm.author.trim() ? createForm.author.trim() : null,
      content: createForm.content.trim(),
      is_top: !!createForm.is_top,
      is_published: createForm.is_published,
    })
  }

  const openEdit = async (id: number) => {
    setEditingId(id)
    setShowEditModal(true)
    try {
      const res = await api.get(`/news/admin/${id}`)
      const detail = res.data
      setEditForm({
        title: detail.title || '',
        category: detail.category || '法律动态',
        summary: detail.summary || '',
        cover_image: detail.cover_image || '',
        source: detail.source || '',
        author: detail.author || '',
        content: detail.content || '',
        is_top: !!detail.is_top,
        is_published: !!detail.is_published,
      })
      setEditImages(extractMarkdownImageUrls(String(detail.content || '')))
    } catch (e) {
      toast.error(getApiErrorMessage(e, '加载失败，请稍后重试'))
    }
  }

  const handleEdit = async () => {
    if (!editingId) return
    if (!editForm.title.trim() || !editForm.content.trim()) return
    if (editMutation.isPending) return
    editMutation.mutate({
      id: editingId,
      payload: {
        title: editForm.title.trim(),
        category: editForm.category,
        summary: editForm.summary.trim() ? editForm.summary.trim() : null,
        cover_image: editForm.cover_image.trim() ? editForm.cover_image.trim() : null,
        source: editForm.source.trim() ? editForm.source.trim() : null,
        author: editForm.author.trim() ? editForm.author.trim() : null,
        content: editForm.content.trim(),
        is_top: !!editForm.is_top,
        is_published: editForm.is_published,
      },
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">新闻管理</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">管理法律新闻和资讯</p>
        </div>
        <Button icon={Plus} onClick={() => setShowCreateModal(true)}>
          发布新闻
        </Button>
      </div>

      <Card variant="surface" padding="md">
        <div className="flex gap-4 mb-6">
          <div className="flex-1 max-w-md">
            <Input
              icon={Search}
              value={keyword}
              onChange={(e) => {
                setKeyword(e.target.value)
                setPage(1)
              }}
              placeholder="搜索新闻标题..."
            />
          </div>
        </div>

        {loading ? (
          <Loading text="加载中..." tone={actualTheme} />
        ) : loadError ? (
          <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
            <div>{loadError}</div>
            <Button variant="outline" onClick={() => newsQuery.refetch()}>重试</Button>
          </div>
        ) : (
          <>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200/70 dark:border-white/10">
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">标题</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">分类</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">状态</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">置顶</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">阅读量</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">发布时间</th>
                <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">操作</th>
              </tr>
            </thead>
            <tbody>
              {news.map((item) => (
                <tr key={item.id} className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5">
                  <td className="py-4 px-4">
                    <p className="text-slate-900 font-medium truncate max-w-xs dark:text-white">{item.title}</p>
                  </td>
                  <td className="py-4 px-4">
                    <Badge variant="info" size="sm">{item.category}</Badge>
                  </td>
                  <td className="py-4 px-4">
                    {item.is_published ? (
                      <Badge variant="success" size="sm">已发布</Badge>
                    ) : (
                      <Badge variant="warning" size="sm">草稿</Badge>
                    )}
                  </td>
                  <td className="py-4 px-4">
                    {item.is_top ? <Badge variant="warning" size="sm">置顶</Badge> : <span className="text-slate-400 dark:text-white/30">-</span>}
                  </td>
                  <td className="py-4 px-4 text-slate-700 dark:text-white/70">{item.view_count.toLocaleString()}</td>
                  <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                    {new Date(item.published_at || item.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-2"
                        onClick={() => toggleTop(item.id, !!item.is_top)}
                        title={item.is_top ? '取消置顶' : '置顶'}
                      >
                        <Pin className={`h-4 w-4 ${item.is_top ? '' : 'opacity-60'}`} />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="p-2"
                        onClick={() => togglePublish(item.id, item.is_published)}
                        title={item.is_published ? '取消发布' : '发布'}
                      >
                        {item.is_published ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-2"
                        title="编辑"
                        onClick={() => openEdit(item.id)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="p-2 text-red-400 hover:text-red-300"
                        onClick={() => handleDelete(item.id)}
                        title="删除"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {news.length === 0 && (
          <div className="text-center py-12 text-slate-500 dark:text-white/40">暂无新闻</div>
        )}

        {totalPages > 1 ? (
          <div className="pt-6">
            <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
          </div>
        ) : null}

          </>
        )}
      </Card>

      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false)
          setCreateImages([])
        }}
        title="发布新闻"
        description="填写新闻内容"
        size="xl"
      >
        <div className="space-y-4">
          <Input
            label="标题"
            placeholder="请输入新闻标题"
            value={createForm.title}
            onChange={(e) => setCreateForm(prev => ({ ...prev, title: e.target.value }))}
          />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">分类</label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={createForm.category}
              onChange={(e) => setCreateForm(prev => ({ ...prev, category: e.target.value }))}
            >
              <option value="法律动态">法律动态</option>
              <option value="政策解读">政策解读</option>
              <option value="案例分析">案例分析</option>
              <option value="法律知识">法律知识</option>
            </select>
          </div>
          <Input
            label="摘要"
            placeholder="可选：一句话概括"
            value={createForm.summary}
            onChange={(e) => setCreateForm(prev => ({ ...prev, summary: e.target.value }))}
          />
          <Input
            label="封面图URL"
            placeholder="可选：http(s)://..."
            value={createForm.cover_image}
            onChange={(e) => setCreateForm(prev => ({ ...prev, cover_image: e.target.value }))}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="来源"
              placeholder="可选"
              value={createForm.source}
              onChange={(e) => setCreateForm(prev => ({ ...prev, source: e.target.value }))}
            />
            <Input
              label="作者"
              placeholder="可选"
              value={createForm.author}
              onChange={(e) => setCreateForm(prev => ({ ...prev, author: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">置顶</label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={createForm.is_top ? 'top' : 'normal'}
              onChange={(e) => setCreateForm(prev => ({ ...prev, is_top: e.target.value === 'top' }))}
            >
              <option value="normal">普通</option>
              <option value="top">置顶</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">状态</label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={createForm.is_published ? 'published' : 'draft'}
              onChange={(e) => setCreateForm(prev => ({ ...prev, is_published: e.target.value === 'published' }))}
            >
              <option value="published">发布</option>
              <option value="draft">草稿</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">内容</label>
            <RichTextEditor
              value={createForm.content}
              onChange={(v) => setCreateForm((prev) => ({ ...prev, content: v }))}
              images={createImages}
              onImagesChange={setCreateImages}
              placeholder="请输入内容，支持 Markdown、表情、图片链接..."
              minHeight="260px"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowCreateModal(false)
                setCreateImages([])
              }}
            >
              取消
            </Button>
            <Button onClick={handleCreate} disabled={!createForm.title.trim() || !createForm.content.trim()}>发布</Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false)
          setEditingId(null)
          setEditImages([])
        }}
        title="编辑新闻"
        description="修改新闻内容"
        size="xl"
      >
        <div className="space-y-4">
          <Input
            label="标题"
            placeholder="请输入新闻标题"
            value={editForm.title}
            onChange={(e) => setEditForm(prev => ({ ...prev, title: e.target.value }))}
          />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">分类</label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={editForm.category}
              onChange={(e) => setEditForm(prev => ({ ...prev, category: e.target.value }))}
            >
              <option value="法律动态">法律动态</option>
              <option value="政策解读">政策解读</option>
              <option value="案例分析">案例分析</option>
              <option value="法律知识">法律知识</option>
            </select>
          </div>
          <Input
            label="摘要"
            placeholder="可选：一句话概括"
            value={editForm.summary}
            onChange={(e) => setEditForm(prev => ({ ...prev, summary: e.target.value }))}
          />
          <Input
            label="封面图URL"
            placeholder="可选：http(s)://..."
            value={editForm.cover_image}
            onChange={(e) => setEditForm(prev => ({ ...prev, cover_image: e.target.value }))}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="来源"
              placeholder="可选"
              value={editForm.source}
              onChange={(e) => setEditForm(prev => ({ ...prev, source: e.target.value }))}
            />
            <Input
              label="作者"
              placeholder="可选"
              value={editForm.author}
              onChange={(e) => setEditForm(prev => ({ ...prev, author: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">置顶</label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={editForm.is_top ? 'top' : 'normal'}
              onChange={(e) => setEditForm(prev => ({ ...prev, is_top: e.target.value === 'top' }))}
            >
              <option value="normal">普通</option>
              <option value="top">置顶</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">状态</label>
            <select
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              value={editForm.is_published ? 'published' : 'draft'}
              onChange={(e) => setEditForm(prev => ({ ...prev, is_published: e.target.value === 'published' }))}
            >
              <option value="published">发布</option>
              <option value="draft">草稿</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">内容</label>
            <RichTextEditor
              value={editForm.content}
              onChange={(v) => setEditForm((prev) => ({ ...prev, content: v }))}
              images={editImages}
              onImagesChange={setEditImages}
              placeholder="请输入内容，支持 Markdown、表情、图片链接..."
              minHeight="260px"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowEditModal(false)
                setEditingId(null)
                setEditImages([])
              }}
            >
              取消
            </Button>
            <Button onClick={handleEdit} disabled={!editForm.title.trim() || !editForm.content.trim()}>
              保存
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
