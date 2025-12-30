import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Calendar, CheckCircle2, Pencil, Plus, Trash2 } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { Button, Card, Chip, EmptyState, Input, Loading, Modal, Pagination, Textarea } from '../components/ui'
import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useAppMutation, useToast } from '../hooks'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'

type Reminder = {
  id: number
  user_id: number
  title: string
  note: string | null
  due_at: string
  remind_at: string | null
  is_done: boolean
  done_at: string | null
  created_at: string
  updated_at: string
}

type ReminderListResponse = {
  items: Reminder[]
  total: number
}

type ReminderFormState = {
  title: string
  note: string
  dueAtLocal: string
  remindAtLocal: string
}

function toLocalInputValue(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  const yyyy = d.getFullYear()
  const mm = pad(d.getMonth() + 1)
  const dd = pad(d.getDate())
  const hh = pad(d.getHours())
  const mi = pad(d.getMinutes())
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}`
}

function localInputToIso(value: string): string | null {
  const s = String(value || '').trim()
  if (!s) return null
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

export default function CalendarPage() {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()

  const [page, setPage] = useState(1)
  const pageSize = 20

  const [doneFilter, setDoneFilter] = useState<'all' | 'todo' | 'done'>('todo')

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Reminder | null>(null)
  const [form, setForm] = useState<ReminderFormState>(() => ({
    title: '',
    note: '',
    dueAtLocal: '',
    remindAtLocal: '',
  }))

  const doneParam: boolean | null = useMemo(() => {
    if (doneFilter === 'all') return null
    return doneFilter === 'done'
  }, [doneFilter])

  const remindersQueryKey = queryKeys.calendarReminders(page, pageSize, doneParam)

  const remindersQuery = useQuery({
    queryKey: remindersQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('page', String(page))
      params.append('page_size', String(pageSize))
      if (doneParam !== null) params.append('done', doneParam ? 'true' : 'false')
      const res = await api.get(`/calendar/reminders?${params.toString()}`)
      const data = res.data
      return {
        items: Array.isArray(data?.items) ? (data.items as Reminder[]) : ([] as Reminder[]),
        total: Number(data?.total || 0),
      } satisfies ReminderListResponse
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!remindersQuery.error) return
    toast.error(getApiErrorMessage(remindersQuery.error, '提醒列表加载失败，请稍后重试'))
  }, [remindersQuery.error, toast])

  const items = remindersQuery.data?.items ?? []
  const total = remindersQuery.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  useEffect(() => {
    setPage(1)
  }, [doneFilter])

  const openCreate = () => {
    setEditing(null)
    setForm({
      title: '',
      note: '',
      dueAtLocal: '',
      remindAtLocal: '',
    })
    setModalOpen(true)
  }

  const openEdit = (r: Reminder) => {
    setEditing(r)
    setForm({
      title: String(r.title ?? ''),
      note: String(r.note ?? ''),
      dueAtLocal: toLocalInputValue(r.due_at),
      remindAtLocal: toLocalInputValue(r.remind_at),
    })
    setModalOpen(true)
  }

  const closeModal = () => {
    setModalOpen(false)
  }

  const createMutation = useAppMutation<unknown, ReminderFormState>({
    mutationFn: async (payload) => {
      const due_at = localInputToIso(payload.dueAtLocal)
      if (!due_at) throw new Error('INVALID_DUE_AT')
      const remind_at = localInputToIso(payload.remindAtLocal)
      await api.post('/calendar/reminders', {
        title: payload.title,
        note: payload.note || null,
        due_at,
        remind_at,
      })
    },
    errorMessageFallback: '创建失败，请稍后重试',
    invalidateQueryKeys: [remindersQueryKey as any],
    onSuccess: () => {
      toast.success('已创建提醒')
      closeModal()
    },
    onError: (err) => {
      const msg = String(err instanceof Error ? err.message : '')
      if (msg === 'INVALID_DUE_AT') {
        toast.error('请选择到期时间')
      }
    },
  })

  const updateMutation = useAppMutation<unknown, { id: number; payload: ReminderFormState }>({
    mutationFn: async ({ id, payload }) => {
      const due_at = localInputToIso(payload.dueAtLocal)
      if (!due_at) throw new Error('INVALID_DUE_AT')
      const remind_at = localInputToIso(payload.remindAtLocal)
      await api.put(`/calendar/reminders/${id}`, {
        title: payload.title,
        note: payload.note || null,
        due_at,
        remind_at,
      })
    },
    errorMessageFallback: '更新失败，请稍后重试',
    invalidateQueryKeys: [remindersQueryKey as any],
    onSuccess: () => {
      toast.success('已更新提醒')
      closeModal()
    },
    onError: (err) => {
      const msg = String(err instanceof Error ? err.message : '')
      if (msg === 'INVALID_DUE_AT') {
        toast.error('请选择到期时间')
      }
    },
  })

  const deleteMutation = useAppMutation<unknown, number>({
    mutationFn: async (id) => {
      await api.delete(`/calendar/reminders/${id}`)
    },
    errorMessageFallback: '删除失败，请稍后重试',
    invalidateQueryKeys: [remindersQueryKey as any],
    onSuccess: () => {
      toast.success('已删除')
    },
  })

  const toggleDoneMutation = useAppMutation<unknown, { id: number; nextDone: boolean }>({
    mutationFn: async ({ id, nextDone }) => {
      await api.put(`/calendar/reminders/${id}`, { is_done: nextDone })
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [remindersQueryKey as any],
    onSuccess: (_res, vars) => {
      toast.success(vars.nextDone ? '已标记完成' : '已标记未完成')
    },
  })

  const handleSubmit = () => {
    const title = form.title.trim()
    if (!title) {
      toast.error('请输入标题')
      return
    }

    if (editing) {
      updateMutation.mutate({ id: editing.id, payload: { ...form, title } })
    } else {
      createMutation.mutate({ ...form, title })
    }
  }

  const isBusy =
    remindersQuery.isFetching ||
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending ||
    toggleDoneMutation.isPending

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="日历"
          title="法律日历"
          description="登录后可创建提醒并管理你的法律事项"
          layout="mdStart"
          tone={actualTheme}
        />

        <EmptyState
          icon={Calendar}
          title="请先登录"
          description="登录后即可使用日历提醒功能"
          tone={actualTheme}
        />
      </div>
    )
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="日历"
        title="法律日历"
        description="管理你的法律事项提醒"
        layout="mdStart"
        tone={actualTheme}
        right={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => remindersQuery.refetch()} disabled={remindersQuery.isFetching}>
              刷新
            </Button>
            <Button onClick={openCreate} icon={Plus} disabled={isBusy}>
              新建提醒
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Chip active={doneFilter === 'todo'} onClick={() => setDoneFilter('todo')}>
          未完成
        </Chip>
        <Chip active={doneFilter === 'done'} onClick={() => setDoneFilter('done')}>
          已完成
        </Chip>
        <Chip active={doneFilter === 'all'} onClick={() => setDoneFilter('all')}>
          全部
        </Chip>
      </div>

      {remindersQuery.isLoading && items.length === 0 ? (
        <Loading text="加载中..." tone={actualTheme} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Calendar}
          title="暂无提醒"
          description="点击右上角新建提醒开始使用"
          tone={actualTheme}
          action={<Button onClick={openCreate}>新建提醒</Button>}
        />
      ) : (
        <Card variant="surface" padding="none">
          <div className="divide-y divide-slate-200/70 dark:divide-white/10">
            {items.map((r) => {
              const dueText = new Date(r.due_at).toLocaleString()
              const remindText = r.remind_at ? new Date(r.remind_at).toLocaleString() : ''

              return (
                <div key={r.id} className="p-5 flex flex-col gap-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p
                          className={`text-sm font-semibold truncate ${
                            r.is_done
                              ? 'text-slate-400 line-through dark:text-white/40'
                              : 'text-slate-900 dark:text-white'
                          }`}
                        >
                          {r.title}
                        </p>
                        {r.is_done ? (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 border border-emerald-500/20 dark:text-emerald-300">
                            已完成
                          </span>
                        ) : (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-700 border border-amber-500/20 dark:text-amber-300">
                            未完成
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 dark:text-white/45 mt-1">
                        到期：{dueText}
                        {remindText ? ` · 提醒：${remindText}` : ''}
                      </p>
                      {r.note ? (
                        <p className="text-sm text-slate-600 dark:text-white/60 whitespace-pre-wrap mt-2">
                          {r.note}
                        </p>
                      ) : null}
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={CheckCircle2}
                        disabled={isBusy}
                        onClick={() => toggleDoneMutation.mutate({ id: r.id, nextDone: !r.is_done })}
                      >
                        {r.is_done ? '未完成' : '完成'}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={Pencil}
                        disabled={isBusy}
                        onClick={() => openEdit(r)}
                      >
                        编辑
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={Trash2}
                        disabled={isBusy}
                        onClick={() => deleteMutation.mutate(r.id)}
                        className="text-red-600"
                      >
                        删除
                      </Button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />

      <Modal
        isOpen={modalOpen}
        onClose={closeModal}
        title={editing ? '编辑提醒' : '新建提醒'}
        size="md"
      >
        <div className="space-y-5">
          <Input
            label="标题"
            value={form.title}
            onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
            placeholder="例如：提交仲裁材料"
          />

          <Input
            label="到期时间"
            type="datetime-local"
            value={form.dueAtLocal}
            onChange={(e) => setForm((prev) => ({ ...prev, dueAtLocal: e.target.value }))}
          />

          <Input
            label="提醒时间（可选）"
            type="datetime-local"
            value={form.remindAtLocal}
            onChange={(e) => setForm((prev) => ({ ...prev, remindAtLocal: e.target.value }))}
          />

          <Textarea
            label="备注（可选）"
            value={form.note}
            onChange={(e) => setForm((prev) => ({ ...prev, note: e.target.value }))}
            placeholder="可填写关键材料、截止节点、联系人等"
            rows={5}
          />

          <div className="flex items-center justify-end gap-3">
            <Button variant="outline" onClick={closeModal} disabled={isBusy}>
              取消
            </Button>
            <Button onClick={handleSubmit} isLoading={createMutation.isPending || updateMutation.isPending}>
              保存
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
