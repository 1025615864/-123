import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Calendar, XCircle } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { Badge, Button, Card, EmptyState, Loading, Pagination } from '../components/ui'
import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useAppMutation, useToast } from '../hooks'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'

type ConsultationItem = {
  id: number
  user_id: number
  lawyer_id: number
  subject: string
  description: string | null
  category: string | null
  contact_phone: string | null
  preferred_time: string | null
  status: string
  admin_note: string | null
  created_at: string
  updated_at: string
  lawyer_name: string | null
}

type ConsultationListResponse = {
  items: ConsultationItem[]
  total: number
  page: number
  page_size: number
}

function statusToBadgeVariant(status: string): 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  const s = String(status || '').toLowerCase()
  if (s === 'confirmed') return 'info'
  if (s === 'completed') return 'success'
  if (s === 'cancelled') return 'danger'
  return 'warning'
}

function statusToLabel(status: string): string {
  const s = String(status || '').toLowerCase()
  if (s === 'pending') return '待处理'
  if (s === 'confirmed') return '已确认'
  if (s === 'completed') return '已完成'
  if (s === 'cancelled') return '已取消'
  return status || '未知'
}

function fmtMaybeDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString()
}

export default function LawFirmConsultationsPage() {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()

  const [page, setPage] = useState(1)
  const pageSize = 20

  const queryKey = queryKeys.lawFirmConsultations(page, pageSize)

  const listQuery = useQuery({
    queryKey,
    queryFn: async () => {
      const res = await api.get('/lawfirm/consultations', {
        params: { page, page_size: pageSize },
      })
      const data = res.data || {}
      const items = Array.isArray(data?.items) ? (data.items as ConsultationItem[]) : ([] as ConsultationItem[])
      return {
        items,
        total: Number(data?.total || 0),
        page: Number(data?.page || page),
        page_size: Number(data?.page_size || pageSize),
      } satisfies ConsultationListResponse
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!listQuery.error) return
    const status = (listQuery.error as any)?.response?.status
    if (status === 401) return
    toast.error(getApiErrorMessage(listQuery.error, '预约列表加载失败，请稍后重试'))
  }, [listQuery.error, toast])

  const cancelMutation = useAppMutation<unknown, number>({
    mutationFn: async (id) => {
      await api.post(`/lawfirm/consultations/${id}/cancel`)
    },
    successMessage: '已取消预约',
    errorMessageFallback: '取消失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.lawFirmConsultationsBase()],
  })

  const handleCancel = (id: number) => {
    if (!confirm('确定要取消这条预约吗？')) return
    cancelMutation.mutate(id)
  }

  const items = listQuery.data?.items ?? []
  const total = listQuery.data?.total ?? 0
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize])

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律所"
          title="我的律师预约"
          description="登录后可查看与管理你的律师预约"
          layout="mdStart"
          tone={actualTheme}
        />
        <EmptyState
          icon={Calendar}
          title="请先登录"
          description="登录后即可查看你的预约记录"
          tone={actualTheme}
        />
      </div>
    )
  }

  if (listQuery.isLoading && items.length === 0) {
    return <Loading text="加载中..." tone={actualTheme} />
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="律所"
        title="我的律师预约"
        description="查看预约状态、取消未完成的预约"
        layout="mdStart"
        tone={actualTheme}
      />

      <Card variant="surface" padding="lg">
        {items.length === 0 ? (
          <EmptyState
            icon={Calendar}
            title="暂无预约"
            description="你还没有提交过律师预约"
            tone={actualTheme}
          />
        ) : (
          <div className="space-y-4">
            {items.map((c) => {
              const status = String(c.status || '')
              const canCancel = status !== 'cancelled' && status !== 'completed'
              return (
                <Card key={c.id} variant="surface" padding="md" className="border border-slate-200/70 dark:border-white/10">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-base font-semibold text-slate-900 dark:text-white truncate">
                          {c.subject}
                        </h3>
                        <Badge variant={statusToBadgeVariant(status)} size="sm">
                          {statusToLabel(status)}
                        </Badge>
                      </div>

                      <div className="mt-2 space-y-1 text-sm text-slate-600 dark:text-white/60">
                        <div>
                          律师：{c.lawyer_name ? c.lawyer_name : `#${c.lawyer_id}`}
                        </div>
                        {c.category ? <div>类型：{c.category}</div> : null}
                        {c.contact_phone ? <div>联系电话：{c.contact_phone}</div> : null}
                        {c.preferred_time ? <div>期望时间：{fmtMaybeDate(c.preferred_time)}</div> : null}
                        {c.description ? <div className="pt-1 text-slate-700 dark:text-white/70">{c.description}</div> : null}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 sm:flex-col sm:items-end sm:justify-start">
                      {canCancel ? (
                        <Button
                          variant="danger"
                          size="sm"
                          icon={XCircle}
                          isLoading={cancelMutation.isPending}
                          onClick={() => handleCancel(c.id)}
                        >
                          取消
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </Card>
              )
            })}

            <div className="pt-4">
              <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
