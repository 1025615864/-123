import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Calendar, CheckCircle2, Pencil, Plus, Trash2, RefreshCw } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { Button, Card, Chip, EmptyState, Input, ListSkeleton, Modal, Pagination, Textarea } from '../components/ui'
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
  const queryClient = useQueryClient()

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

  const [pendingToggle, setPendingToggle] = useState<Record<number, boolean>>({})
  const [pendingDelete, setPendingDelete] = useState<Record<number, boolean>>({})

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

  const createMutation = useAppMutation<Reminder, ReminderFormState, { previous?: ReminderListResponse; tempId?: number }>({
    mutationFn: async (payload) => {
      const due_at = localInputToIso(payload.dueAtLocal)
      if (!due_at) throw new Error('请选择到期时间')
      const remind_at = localInputToIso(payload.remindAtLocal)
      const res = await api.post('/calendar/reminders', {
        title: payload.title,
        note: payload.note || null,
        due_at,
        remind_at,
      })
      return res.data as Reminder
    },
    errorMessageFallback: '创建失败，请稍后重试',
    invalidateQueryKeys: [remindersQueryKey as any],
    onMutate: async (payload) => {
      const due_at = localInputToIso(payload.dueAtLocal)
      if (!due_at) return {}

      const shouldShow = doneParam !== true
      if (!shouldShow) return {}

      await queryClient.cancelQueries({ queryKey: remindersQueryKey })
      const previous = queryClient.getQueryData<ReminderListResponse>(remindersQueryKey)

      const nowIso = new Date().toISOString()
      const tempId = -Math.trunc(Date.now())
      const optimistic: Reminder = {
        id: tempId,
        user_id: 0,
        title: payload.title,
        note: payload.note || null,
        due_at,
        remind_at: localInputToIso(payload.remindAtLocal),
        is_done: false,
        done_at: null,
        created_at: nowIso,
        updated_at: nowIso,
      }

      queryClient.setQueryData<ReminderListResponse>(remindersQueryKey, (old) => {
        if (!old) return old as any
        const items = Array.isArray(old.items) ? old.items : []
        const nextItems = [...items, optimistic]
          .sort((a, b) => {
            const ta = new Date(a.due_at).getTime()
            const tb = new Date(b.due_at).getTime()
            if (ta !== tb) return ta - tb
            return a.id - b.id
          })
          .slice(0, pageSize)
        return { ...old, items: nextItems, total: Math.max(0, Number(old.total || 0) + 1) }
      })

      return { previous, tempId }
    },
    onSuccess: () => {
      toast.success('已创建提醒')
      closeModal()
    },
    onError: (err, _vars, ctx) => {
      const anyCtx = ctx as any
      if (anyCtx?.previous) {
        queryClient.setQueryData(remindersQueryKey, anyCtx.previous)
      }
      return err as any
    },
    onSettled: (data, _err, _vars, ctx) => {
      const anyCtx = ctx as any
      const tempId = Number(anyCtx?.tempId)
      if (!data || !Number.isFinite(tempId) || tempId >= 0) return
      queryClient.setQueryData<ReminderListResponse>(remindersQueryKey, (old) => {
        if (!old) return old as any
        const items = Array.isArray(old.items) ? old.items : []
        const idx = items.findIndex((x) => x.id === tempId)
        if (idx < 0) return old
        const nextItems = [...items]
        nextItems[idx] = data
        return { ...old, items: nextItems }
      })
    },
  })

  const updateMutation = useAppMutation<
    Reminder,
    { id: number; payload: ReminderFormState },
    { previous?: ReminderListResponse }
  >({
    mutationFn: async ({ id, payload }) => {
      const due_at = localInputToIso(payload.dueAtLocal)
      if (!due_at) throw new Error('请选择到期时间')
      const remind_at = localInputToIso(payload.remindAtLocal)
      const res = await api.put(`/calendar/reminders/${id}`, {
        title: payload.title,
        note: payload.note || null,
        due_at,
        remind_at,
      })
      return res.data as Reminder
    },
    errorMessageFallback: '更新失败，请稍后重试',
    invalidateQueryKeys: [remindersQueryKey as any],
    onMutate: async ({ id, payload }) => {
      const due_at = localInputToIso(payload.dueAtLocal)
      if (!due_at) return {}

      await queryClient.cancelQueries({ queryKey: remindersQueryKey })
      const previous = queryClient.getQueryData<ReminderListResponse>(remindersQueryKey)

      queryClient.setQueryData<ReminderListResponse>(remindersQueryKey, (old) => {
        if (!old) return old as any
        const items = Array.isArray(old.items) ? old.items : []
        const nextItems = items.map((r) => {
          if (r.id !== id) return r
          return {
            ...r,
            title: payload.title,
            note: payload.note || null,
            due_at,
            remind_at: localInputToIso(payload.remindAtLocal),
            updated_at: new Date().toISOString(),
          }
        })
        return { ...old, items: nextItems }
      })

      return { previous }
    },
    onSuccess: () => {
      toast.success('已更新提醒')
      closeModal()
    },
    onSettled: (data, _err, vars, ctx) => {
      if (!data) {
        const anyCtx = ctx as any
        if (anyCtx?.previous) queryClient.setQueryData(remindersQueryKey, anyCtx.previous)
        return
      }
      queryClient.setQueryData<ReminderListResponse>(remindersQueryKey, (old) => {
        if (!old) return old as any
        const items = Array.isArray(old.items) ? old.items : []
        const nextItems = items.map((r) => (r.id === vars.id ? data : r))
        return { ...old, items: nextItems }
      })
    },
  })

  const deleteMutation = useAppMutation<unknown, number, { previous?: ReminderListResponse }>({
    mutationFn: async (id) => {
      await api.delete(`/calendar/reminders/${id}`)
    },
    errorMessageFallback: '删除失败，请稍后重试',
    invalidateQueryKeys: [remindersQueryKey as any],
    onMutate: async (id) => {
      setPendingDelete((prev) => ({ ...prev, [id]: true }))
      await queryClient.cancelQueries({ queryKey: remindersQueryKey })
      const previous = queryClient.getQueryData<ReminderListResponse>(remindersQueryKey)
      queryClient.setQueryData<ReminderListResponse>(remindersQueryKey, (old) => {
        if (!old) return old as any
        const items = Array.isArray(old.items) ? old.items : []
        const nextItems = items.filter((r) => r.id !== id)
        return { ...old, items: nextItems, total: Math.max(0, Number(old.total || 0) - 1) }
      })
      return { previous }
    },
    onSuccess: () => {
      toast.success('已删除')
    },
    onError: (err, id, ctx) => {
      setPendingDelete((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      const anyCtx = ctx as any
      if (anyCtx?.previous) queryClient.setQueryData(remindersQueryKey, anyCtx.previous)
      return err as any
    },
    onSettled: (_data, _err, id) => {
      setPendingDelete((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
    },
  })

  const toggleDoneMutation = useAppMutation<
    Reminder,
    { id: number; nextDone: boolean },
    { previous?: ReminderListResponse }
  >({
    mutationFn: async ({ id, nextDone }) => {
      const res = await api.put(`/calendar/reminders/${id}`, { is_done: nextDone })
      return res.data as Reminder
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [remindersQueryKey as any],
    onMutate: async ({ id, nextDone }) => {
      setPendingToggle((prev) => ({ ...prev, [id]: true }))
      await queryClient.cancelQueries({ queryKey: remindersQueryKey })
      const previous = queryClient.getQueryData<ReminderListResponse>(remindersQueryKey)

      queryClient.setQueryData<ReminderListResponse>(remindersQueryKey, (old) => {
        if (!old) return old as any
        const items = Array.isArray(old.items) ? old.items : []
        const nextItems = items
          .map((r) => {
            if (r.id !== id) return r
            return {
              ...r,
              is_done: nextDone,
              done_at: nextDone ? new Date().toISOString() : null,
              updated_at: new Date().toISOString(),
            }
          })
          .filter((r) => {
            if (doneParam === null) return true
            return doneParam ? Boolean(r.is_done) : !r.is_done
          })
        return { ...old, items: nextItems }
      })

      return { previous }
    },
    onSuccess: (_res, vars) => {
      toast.success(vars.nextDone ? '已标记完成' : '已标记未完成')
    },
    onError: (err, vars, ctx) => {
      setPendingToggle((prev) => {
        const next = { ...prev }
        delete next[vars.id]
        return next
      })
      const anyCtx = ctx as any
      if (anyCtx?.previous) queryClient.setQueryData(remindersQueryKey, anyCtx.previous)
      return err as any
    },
    onSettled: (_data, _err, vars) => {
      setPendingToggle((prev) => {
        const next = { ...prev }
        delete next[vars.id]
        return next
      })
    },
  })

  const handleSubmit = () => {
    if (createMutation.isPending || updateMutation.isPending) return

    const title = form.title.trim()
    if (!title) {
      toast.error('请输入标题')
      return
    }

    const due_at = localInputToIso(form.dueAtLocal)
    if (!due_at) {
      toast.error('请选择到期时间')
      return
    }

    if (editing) {
      updateMutation.mutate({ id: editing.id, payload: { ...form, title } })
    } else {
      createMutation.mutate({ ...form, title })
    }
  }

  const isBusy = createMutation.isPending || updateMutation.isPending
  const actionBusy = isBusy || toggleDoneMutation.isPending || deleteMutation.isPending

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
            <Button
              variant="outline"
              icon={RefreshCw}
              isLoading={remindersQuery.isFetching}
              loadingText="刷新中..."
              onClick={() => remindersQuery.refetch()}
              disabled={remindersQuery.isFetching || actionBusy}
            >
              刷新
            </Button>
            <Button onClick={openCreate} icon={Plus} disabled={actionBusy}>
              新建提醒
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Chip
          active={doneFilter === 'todo'}
          onClick={() => {
            if (actionBusy) return
            setDoneFilter('todo')
          }}
        >
          未完成
        </Chip>
        <Chip
          active={doneFilter === 'done'}
          onClick={() => {
            if (actionBusy) return
            setDoneFilter('done')
          }}
        >
          已完成
        </Chip>
        <Chip
          active={doneFilter === 'all'}
          onClick={() => {
            if (actionBusy) return
            setDoneFilter('all')
          }}
        >
          全部
        </Chip>
      </div>

      {remindersQuery.isLoading && items.length === 0 ? (
        <ListSkeleton count={4} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Calendar}
          title="暂无提醒"
          description="点击右上角新建提醒开始使用"
          tone={actualTheme}
          action={
            <Button onClick={openCreate} disabled={actionBusy}>
              新建提醒
            </Button>
          }
        />
      ) : (
        <Card variant="surface" padding="none">
          <div className="divide-y divide-slate-200/70 dark:divide-white/10">
            {items.map((r) => {
              const dueText = new Date(r.due_at).toLocaleString()
              const remindText = r.remind_at ? new Date(r.remind_at).toLocaleString() : ''
              const toggleLoading = Boolean(pendingToggle[r.id])
              const deleteLoading = Boolean(pendingDelete[r.id])
              const rowPending = Boolean(toggleLoading || deleteLoading)

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
                        isLoading={toggleLoading}
                        loadingText="处理中..."
                        disabled={rowPending || actionBusy}
                        onClick={() => {
                          if (actionBusy) return
                          toggleDoneMutation.mutate({ id: r.id, nextDone: !r.is_done })
                        }}
                      >
                        {r.is_done ? '未完成' : '完成'}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={Pencil}
                        disabled={rowPending || actionBusy}
                        onClick={() => {
                          if (actionBusy) return
                          openEdit(r)
                        }}
                      >
                        编辑
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={Trash2}
                        isLoading={deleteLoading}
                        loadingText="删除中..."
                        disabled={rowPending || actionBusy}
                        onClick={() => {
                          if (actionBusy) return
                          deleteMutation.mutate(r.id)
                        }}
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

      <Pagination
        currentPage={page}
        totalPages={totalPages}
        onPageChange={(p) => {
          if (actionBusy) return
          setPage(p)
        }}
      />

      <Modal
        isOpen={modalOpen}
        onClose={() => {
          if (isBusy) return
          closeModal()
        }}
        title={editing ? '编辑提醒' : '新建提醒'}
        size="md"
      >
        <div className="space-y-5">
          <Input
            label="标题"
            value={form.title}
            onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
            placeholder="例如：提交仲裁材料"
            disabled={isBusy}
          />

          <Input
            label="到期时间"
            type="datetime-local"
            value={form.dueAtLocal}
            onChange={(e) => setForm((prev) => ({ ...prev, dueAtLocal: e.target.value }))}
            disabled={isBusy}
          />

          <Input
            label="提醒时间（可选）"
            type="datetime-local"
            value={form.remindAtLocal}
            onChange={(e) => setForm((prev) => ({ ...prev, remindAtLocal: e.target.value }))}
            disabled={isBusy}
          />

          <Textarea
            label="备注（可选）"
            value={form.note}
            onChange={(e) => setForm((prev) => ({ ...prev, note: e.target.value }))}
            placeholder="可填写关键材料、截止节点、联系人等"
            rows={5}
            disabled={isBusy}
          />

          <div className="flex items-center justify-end gap-3">
            <Button variant="outline" onClick={closeModal} disabled={isBusy}>
              取消
            </Button>
            <Button
              onClick={handleSubmit}
              isLoading={createMutation.isPending || updateMutation.isPending}
              loadingText="保存中..."
              disabled={isBusy}
            >
              保存
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
