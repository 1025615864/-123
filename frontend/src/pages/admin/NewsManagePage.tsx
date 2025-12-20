import { useMemo, useState } from 'react'
import { Search, Plus, Edit, Trash2, Eye, EyeOff } from 'lucide-react'
import { Card, Input, Button, Badge, Modal, Loading } from '../../components/ui'
import { useQuery } from '@tanstack/react-query'
import api from '../../api/client'
import { useAppMutation, useToast } from '../../hooks'
import { useTheme } from '../../contexts/ThemeContext'
import { getApiErrorMessage } from '../../utils'

interface NewsItem {
  id: number
  title: string
  category: string
  is_published: boolean
  view_count: number
  created_at: string
}

export default function NewsManagePage() {
  const { actualTheme } = useTheme()
  const [keyword, setKeyword] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const toast = useToast()

  const [createForm, setCreateForm] = useState({
    title: '',
    category: '法律动态',
    content: '',
    is_published: true,
  })

  const [editForm, setEditForm] = useState({
    title: '',
    category: '法律动态',
    content: '',
    is_published: true,
  })

  const newsQueryKey = useMemo(() => ['admin-news', { keyword: keyword.trim() }] as const, [keyword])

  const newsQuery = useQuery({
    queryKey: newsQueryKey,
    queryFn: async () => {
      const trimmed = keyword.trim()
      const res = await api.get('/news/admin/all', { params: trimmed ? { keyword: trimmed } : {} })
      const items = res.data?.items ?? []
      return (Array.isArray(items) ? items : []) as NewsItem[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const news = newsQuery.data ?? []
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

  const createMutation = useAppMutation<void, { title: string; category: string; content: string; is_published: boolean }>({
    mutationFn: async (payload) => {
      await api.post('/news', payload)
    },
    successMessage: '发布成功',
    errorMessageFallback: '发布失败，请稍后重试',
    invalidateQueryKeys: [newsQueryKey as any],
    onSuccess: () => {
      setShowCreateModal(false)
      setCreateForm({ title: '', category: '法律动态', content: '', is_published: true })
    },
  })

  const editMutation = useAppMutation<void, { id: number; payload: { title: string; category: string; content: string; is_published: boolean } }>({
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

  const handleCreate = async () => {
    if (!createForm.title.trim() || !createForm.content.trim()) return
    if (createMutation.isPending) return
    createMutation.mutate({
      title: createForm.title.trim(),
      category: createForm.category,
      content: createForm.content.trim(),
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
        content: detail.content || '',
        is_published: !!detail.is_published,
      })
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
        content: editForm.content.trim(),
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
              onChange={(e) => setKeyword(e.target.value)}
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
                  <td className="py-4 px-4 text-slate-700 dark:text-white/70">{item.view_count.toLocaleString()}</td>
                  <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                    {new Date(item.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center justify-end gap-2">
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

          </>
        )}
      </Card>

      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="发布新闻"
        description="填写新闻内容"
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
            <textarea 
              rows={6}
              placeholder="请输入新闻内容"
              value={createForm.content}
              onChange={(e) => setCreateForm(prev => ({ ...prev, content: e.target.value }))}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none resize-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" onClick={() => setShowCreateModal(false)}>取消</Button>
            <Button onClick={handleCreate} disabled={!createForm.title.trim() || !createForm.content.trim()}>发布</Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false)
          setEditingId(null)
        }}
        title="编辑新闻"
        description="修改新闻内容"
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
            <textarea
              rows={6}
              placeholder="请输入新闻内容"
              value={editForm.content}
              onChange={(e) => setEditForm(prev => ({ ...prev, content: e.target.value }))}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none resize-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowEditModal(false)
                setEditingId(null)
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
