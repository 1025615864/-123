import { useMemo, useState } from 'react'
import { Search, Plus, Edit, Trash2, BadgeCheck, Ban, RotateCcw } from 'lucide-react'
import { Card, Input, Button, Badge, Modal, ListSkeleton } from '../../components/ui'
import { useQuery } from '@tanstack/react-query'
import api from '../../api/client'
import { useAppMutation } from '../../hooks'
import { getApiErrorMessage } from '../../utils'

interface LawFirm {
  id: number
  name: string
  city: string | null
  phone: string | null
  is_verified: boolean
  is_active: boolean
  lawyer_count: number
  rating: number
  created_at: string
}

export default function LawFirmsManagePage() {
  const [keyword, setKeyword] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingFirm, setEditingFirm] = useState<LawFirm | null>(null)
  const [activeAction, setActiveAction] = useState<{ id: number; kind: 'verify' | 'active' | 'delete' } | null>(null)

  const [createForm, setCreateForm] = useState({
    name: '',
    city: '',
    phone: '',
    address: '',
    description: '',
  })

  const [editForm, setEditForm] = useState({
    name: '',
    city: '',
    phone: '',
    address: '',
    description: '',
  })

  const firmsQueryKey = useMemo(
    () => ['admin-lawfirms', { keyword: keyword.trim(), include_inactive: true }] as const,
    [keyword]
  )

  const firmsQuery = useQuery({
    queryKey: firmsQueryKey,
    queryFn: async () => {
      const trimmed = keyword.trim()
      const res = await api.get('/lawfirm/admin/firms', {
        params: {
          include_inactive: true,
          ...(trimmed ? { keyword: trimmed } : {}),
        },
      })
      const items = res.data?.items ?? []
      return (Array.isArray(items) ? items : []) as LawFirm[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const firms = firmsQuery.data ?? []
  const loading = firmsQuery.isLoading
  const loadError = firmsQuery.isError ? getApiErrorMessage(firmsQuery.error, '律所列表加载失败，请稍后重试') : null

  const deleteMutation = useAppMutation<void, number>({
    mutationFn: async (id) => {
      await api.delete(`/lawfirm/admin/firms/${id}`)
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [firmsQueryKey as any],
    onMutate: async (id) => {
      setActiveAction({ id, kind: 'delete' })
    },
    onSettled: (_data, _err, id) => {
      setActiveAction((prev) => (prev && prev.id === id && prev.kind === 'delete' ? null : prev))
    },
  })

  const verifyMutation = useAppMutation<void, { id: number; is_verified: boolean }>({
    mutationFn: async (payload) => {
      await api.put(`/lawfirm/admin/firms/${payload.id}`, { is_verified: payload.is_verified })
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [firmsQueryKey as any],
    onMutate: async (payload) => {
      setActiveAction({ id: payload.id, kind: 'verify' })
    },
    onSettled: (_data, _err, payload) => {
      setActiveAction((prev) => (prev && prev.id === payload?.id && prev.kind === 'verify' ? null : prev))
    },
  })

  const activeMutation = useAppMutation<void, { id: number; is_active: boolean }>({
    mutationFn: async (payload) => {
      await api.put(`/lawfirm/admin/firms/${payload.id}`, { is_active: payload.is_active })
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [firmsQueryKey as any],
    onMutate: async (payload) => {
      setActiveAction({ id: payload.id, kind: 'active' })
    },
    onSettled: (_data, _err, payload) => {
      setActiveAction((prev) => (prev && prev.id === payload?.id && prev.kind === 'active' ? null : prev))
    },
  })

  const createMutation = useAppMutation<void, { name: string; city: string | null; phone: string | null; address: string | null; description: string | null }>({
    mutationFn: async (payload) => {
      await api.post('/lawfirm/firms', payload)
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [firmsQueryKey as any],
    onSuccess: () => {
      setShowCreateModal(false)
      setCreateForm({ name: '', city: '', phone: '', address: '', description: '' })
    },
  })

  const editMutation = useAppMutation<void, { id: number; payload: { name: string; city: string | null; phone: string | null; address: string | null; description: string | null } }>({
    mutationFn: async ({ id, payload }) => {
      await api.put(`/lawfirm/admin/firms/${id}`, payload)
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [firmsQueryKey as any],
    onSuccess: () => {
      setShowEditModal(false)
      setEditingFirm(null)
    },
  })

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除这个律所吗？')) return
    if (deleteMutation.isPending) return
    deleteMutation.mutate(id)
  }

  const toggleVerify = async (firm: LawFirm) => {
    if (verifyMutation.isPending) return
    verifyMutation.mutate({ id: firm.id, is_verified: !firm.is_verified })
  }

  const toggleActive = async (firm: LawFirm) => {
    if (activeMutation.isPending) return
    activeMutation.mutate({ id: firm.id, is_active: !firm.is_active })
  }

  const handleCreate = async () => {
    if (!createForm.name.trim()) return
    if (createMutation.isPending) return
    createMutation.mutate({
      name: createForm.name.trim(),
      city: createForm.city.trim() || null,
      phone: createForm.phone.trim() || null,
      address: createForm.address.trim() || null,
      description: createForm.description.trim() || null,
    })
  }

  const openEditModal = (firm: LawFirm) => {
    setEditingFirm(firm)
    setEditForm({
      name: firm.name || '',
      city: firm.city || '',
      phone: firm.phone || '',
      address: '',
      description: '',
    })
    setShowEditModal(true)
  }

  const handleEdit = async () => {
    if (!editingFirm) return
    if (!editForm.name.trim()) return
    if (editMutation.isPending) return
    editMutation.mutate({
      id: editingFirm.id,
      payload: {
        name: editForm.name.trim(),
        city: editForm.city.trim() || null,
        phone: editForm.phone.trim() || null,
        address: editForm.address.trim() || null,
        description: editForm.description.trim() || null,
      },
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">律所管理</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">管理入驻律师事务所</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            icon={RotateCcw}
            isLoading={firmsQuery.isFetching}
            loadingText="刷新中..."
            disabled={firmsQuery.isFetching}
            onClick={() => firmsQuery.refetch()}
          >
            刷新
          </Button>
          <Button icon={Plus} onClick={() => setShowCreateModal(true)}>
            添加律所
          </Button>
        </div>
      </div>

      <Card variant="surface" padding="md">
        <div className="flex gap-4 mb-6">
          <div className="flex-1 max-w-md">
            <Input
              icon={Search}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索律所名称或城市..."
            />
          </div>
        </div>

        {loading && firms.length === 0 ? (
          <ListSkeleton count={6} />
        ) : loadError ? (
          <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
            <div>{loadError}</div>
            <Button variant="outline" onClick={() => firmsQuery.refetch()}>
              重试
            </Button>
          </div>
        ) : (
          <>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200/70 dark:border-white/10">
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">律所名称</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">城市</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">状态</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">律师数</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">评分</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">入驻时间</th>
                <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">操作</th>
              </tr>
            </thead>
            <tbody>
              {firms.map((item) => (
                <tr key={item.id} className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5">
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-2">
                      <p className="text-slate-900 font-medium dark:text-white">{item.name}</p>
                      {item.is_verified && (
                        <BadgeCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                      )}
                    </div>
                  </td>
                  <td className="py-4 px-4 text-slate-700 dark:text-white/70">{item.city}</td>
                  <td className="py-4 px-4">
                    {item.is_active ? (
                      <Badge variant="success" size="sm">正常</Badge>
                    ) : (
                      <Badge variant="danger" size="sm">已禁用</Badge>
                    )}
                  </td>
                  <td className="py-4 px-4 text-slate-700 dark:text-white/70">{item.lawyer_count}</td>
                  <td className="py-4 px-4 text-amber-600 dark:text-amber-400">{item.rating.toFixed(1)}</td>
                  <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                    {new Date(item.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center justify-end gap-2">
                      {(() => {
                        const isActive = activeAction?.id === item.id
                        const actionBusy = deleteMutation.isPending || verifyMutation.isPending || activeMutation.isPending
                        const rowBusy = actionBusy && isActive
                        const disableOther = actionBusy && !isActive
                        const verifyLoading = verifyMutation.isPending && isActive && activeAction?.kind === 'verify'
                        const activeLoading = activeMutation.isPending && isActive && activeAction?.kind === 'active'
                        const deleteLoading = deleteMutation.isPending && isActive && activeAction?.kind === 'delete'

                        return (
                          <>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className={verifyLoading ? "px-3 py-2" : "p-2"}
                        onClick={() => toggleVerify(item)}
                        title={item.is_verified ? '取消认证' : '认证'}
                        isLoading={verifyLoading}
                        loadingText="处理中..."
                        disabled={(rowBusy && !verifyLoading) || disableOther}
                      >
                        <BadgeCheck className={`h-4 w-4 ${item.is_verified ? 'text-emerald-400' : ''}`} />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className={activeLoading ? "px-3 py-2" : "p-2"}
                        onClick={() => toggleActive(item)}
                        title={item.is_active ? '禁用' : '启用'}
                        isLoading={activeLoading}
                        loadingText="处理中..."
                        disabled={(rowBusy && !activeLoading) || disableOther}
                      >
                        <Ban className={`h-4 w-4 ${!item.is_active ? 'text-red-400' : ''}`} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-2"
                        title="编辑"
                        onClick={() => {
                          if (actionBusy) return
                          openEditModal(item)
                        }}
                        disabled={actionBusy}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className={`${deleteLoading ? 'px-3 py-2' : 'p-2'} text-red-400 hover:text-red-300`}
                        onClick={() => handleDelete(item.id)}
                        title="删除"
                        isLoading={deleteLoading}
                        loadingText="删除中..."
                        disabled={(rowBusy && !deleteLoading) || disableOther}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                          </>
                        )
                      })()}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {firms.length === 0 && (
          <div className="text-center py-12 text-slate-500 dark:text-white/40">暂无律所</div>
        )}

          </>
        )}
      </Card>

      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          if (createMutation.isPending) return
          setShowCreateModal(false)
        }}
        title="添加律所"
        description="填写律所信息"
      >
        <div className="space-y-4">
          <Input
            label="律所名称"
            placeholder="请输入律所名称"
            value={createForm.name}
            onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
            disabled={createMutation.isPending}
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="城市"
              placeholder="请输入城市"
              value={createForm.city}
              onChange={(e) => setCreateForm(prev => ({ ...prev, city: e.target.value }))}
              disabled={createMutation.isPending}
            />
            <Input
              label="联系电话"
              placeholder="请输入电话"
              value={createForm.phone}
              onChange={(e) => setCreateForm(prev => ({ ...prev, phone: e.target.value }))}
              disabled={createMutation.isPending}
            />
          </div>
          <Input
            label="地址"
            placeholder="请输入详细地址"
            value={createForm.address}
            onChange={(e) => setCreateForm(prev => ({ ...prev, address: e.target.value }))}
            disabled={createMutation.isPending}
          />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">简介</label>
            <textarea 
              rows={4}
              placeholder="请输入律所简介"
              value={createForm.description}
              onChange={(e) => setCreateForm(prev => ({ ...prev, description: e.target.value }))}
              disabled={createMutation.isPending}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none resize-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowCreateModal(false)}
              disabled={createMutation.isPending}
            >
              取消
            </Button>
            <Button onClick={handleCreate} disabled={!createForm.name.trim() || createMutation.isPending} isLoading={createMutation.isPending} loadingText="添加中...">添加</Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showEditModal}
        onClose={() => {
          if (editMutation.isPending) return
          setShowEditModal(false)
          setEditingFirm(null)
        }}
        title="编辑律所"
        description="修改律所信息"
      >
        <div className="space-y-4">
          <Input
            label="律所名称"
            placeholder="请输入律所名称"
            value={editForm.name}
            onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
            disabled={editMutation.isPending}
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="城市"
              placeholder="请输入城市"
              value={editForm.city}
              onChange={(e) => setEditForm(prev => ({ ...prev, city: e.target.value }))}
              disabled={editMutation.isPending}
            />
            <Input
              label="联系电话"
              placeholder="请输入电话"
              value={editForm.phone}
              onChange={(e) => setEditForm(prev => ({ ...prev, phone: e.target.value }))}
              disabled={editMutation.isPending}
            />
          </div>
          <Input
            label="地址"
            placeholder="请输入详细地址"
            value={editForm.address}
            onChange={(e) => setEditForm(prev => ({ ...prev, address: e.target.value }))}
            disabled={editMutation.isPending}
          />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">简介</label>
            <textarea
              rows={4}
              placeholder="请输入律所简介"
              value={editForm.description}
              onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))}
              disabled={editMutation.isPending}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none resize-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowEditModal(false)
                setEditingFirm(null)
              }}
              disabled={editMutation.isPending}
            >
              取消
            </Button>
            <Button onClick={handleEdit} disabled={!editForm.name.trim() || editMutation.isPending} isLoading={editMutation.isPending} loadingText="保存中...">
              保存
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
