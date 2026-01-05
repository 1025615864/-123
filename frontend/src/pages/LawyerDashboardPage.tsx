import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Calendar, CheckCircle2, FileText, Handshake, MessageSquareText, XCircle } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { Badge, Button, Card, EmptyState, Loading, Pagination } from '../components/ui'
import api from '../api/client'
import LawyerConsultationMessagesModal from '../components/LawyerConsultationMessagesModal'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useAppMutation, useToast } from '../hooks'
import { getApiErrorMessage } from '../utils'

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
  created_at: string
  updated_at: string
  payment_order_no?: string | null
  payment_status?: string | null
  payment_amount?: number | null
}

type ConsultationListResponse = {
  items: ConsultationItem[]
  total: number
  page: number
  page_size: number
}

function statusToBadgeVariant(status: string): 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  const s = String(status || '').toLowerCase()
  if (s === 'pending') return 'warning'
  if (s === 'confirmed') return 'info'
  if (s === 'completed') return 'success'
  if (s === 'cancelled') return 'danger'
  return 'default'
}

function statusToLabel(status: string): string {
  const s = String(status || '').toLowerCase()
  if (s === 'pending') return '待处理'
  if (s === 'confirmed') return '已确认'
  if (s === 'completed') return '已完成'
  if (s === 'cancelled') return '已取消'
  return status || '未知'
}

function paymentStatusToLabel(status: string): string {
  const s = String(status || '').toLowerCase()
  if (s === 'paid') return '已支付'
  if (s === 'pending') return '待支付'
  if (s === 'cancelled') return '已取消'
  if (s === 'refunded') return '已退款'
  if (s === 'failed') return '失败'
  return status || '未知'
}

export default function LawyerDashboardPage() {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()

  const [messagesOpen, setMessagesOpen] = useState(false)
  const [messagesConsultationId, setMessagesConsultationId] = useState<number | null>(null)
  const [messagesTitle, setMessagesTitle] = useState<string>('')

  const [page, setPage] = useState(1)
  const pageSize = 20

  const listQuery = useQuery({
    queryKey: ['lawyer-consultations', { page, pageSize }] as const,
    queryFn: async () => {
      const res = await api.get('/lawfirm/lawyer/consultations', {
        params: { page, page_size: pageSize },
      })
      const data = res.data || {}
      return {
        items: Array.isArray(data?.items) ? (data.items as ConsultationItem[]) : ([] as ConsultationItem[]),
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
    if (status === 403) return
    toast.error(getApiErrorMessage(listQuery.error, '加载失败，请稍后重试'))
  }, [listQuery.error, toast])

  const acceptMutation = useAppMutation<unknown, number>({
    mutationFn: async (id) => {
      await api.post(`/lawfirm/lawyer/consultations/${id}/accept`)
    },
    successMessage: '已接单',
    errorMessageFallback: '接单失败，请稍后重试',
    onSuccess: async () => {
      await listQuery.refetch()
    },
  })

  const rejectMutation = useAppMutation<unknown, number>({
    mutationFn: async (id) => {
      await api.post(`/lawfirm/lawyer/consultations/${id}/reject`)
    },
    successMessage: '已拒单',
    errorMessageFallback: '拒单失败，请稍后重试',
    onSuccess: async () => {
      await listQuery.refetch()
    },
  })

  const completeMutation = useAppMutation<unknown, number>({
    mutationFn: async (id) => {
      await api.post(`/lawfirm/lawyer/consultations/${id}/complete`)
    },
    successMessage: '已标记完成',
    errorMessageFallback: '操作失败，请稍后重试',
    onSuccess: async () => {
      await listQuery.refetch()
    },
  })

  const items = listQuery.data?.items ?? []
  const total = listQuery.data?.total ?? 0
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total])

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律师"
          title="律师工作台"
          description="登录后可处理用户预约"
          layout="mdStart"
          tone={actualTheme}
        />
        <EmptyState icon={Handshake} title="请先登录" description="登录后即可进入律师工作台" tone={actualTheme} />
      </div>
    )
  }

  const listErrorStatus = (listQuery.error as any)?.response?.status
  if (listQuery.isError && listErrorStatus === 403) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律师"
          title="律师工作台"
          description="你当前没有律师权限"
          layout="mdStart"
          tone={actualTheme}
        />
        <EmptyState
          icon={Handshake}
          title="暂无权限"
          description="请先完成律师认证并通过审核"
          tone={actualTheme}
          action={
            <Button onClick={() => (window.location.href = '/lawyer/verification')}>
              去申请认证
            </Button>
          }
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
        eyebrow="律师"
        title="律师工作台"
        description="处理用户预约：接单 / 拒单 / 标记完成"
        layout="mdStart"
        tone={actualTheme}
        right={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => (window.location.href = '/lawyer/income')}>
              收入
            </Button>
            <Button variant="outline" onClick={() => (window.location.href = '/lawyer/withdraw')}>
              提现
            </Button>
            <Button variant="outline" onClick={() => listQuery.refetch()} disabled={listQuery.isFetching}>
              刷新
            </Button>
          </div>
        }
      />

      <Card variant="surface" padding="lg">
        {items.length === 0 ? (
          <EmptyState icon={Calendar} title="暂无预约" description="当前没有待处理的咨询预约" tone={actualTheme} />
        ) : (
          <div className="space-y-4">
            {items.map((c) => {
              const status = String(c.status || '')
              const s = status.toLowerCase()
              const canAcceptOrReject = s === 'pending'
              const canComplete = s === 'confirmed'

              const orderNo = String(c.payment_order_no || '').trim()
              const payStatus = String(c.payment_status || '').trim().toLowerCase()
              const paid = !orderNo || payStatus === 'paid'

              return (
                <Card key={c.id} variant="surface" padding="md" className="border border-slate-200/70 dark:border-white/10">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-base font-semibold text-slate-900 dark:text-white truncate">{c.subject}</h3>
                        <Badge variant={statusToBadgeVariant(status)} size="sm">
                          {statusToLabel(status)}
                        </Badge>
                      </div>

                      <div className="mt-2 space-y-1 text-sm text-slate-600 dark:text-white/60">
                        <div>用户：#{c.user_id}</div>
                        {c.category ? <div>类型：{c.category}</div> : null}
                        {c.contact_phone ? <div>联系电话：{c.contact_phone}</div> : null}
                        {c.preferred_time ? <div>期望时间：{new Date(c.preferred_time).toLocaleString()}</div> : null}
                        {orderNo ? (
                          <div className="flex flex-wrap items-center gap-2">
                            <span>支付：{paymentStatusToLabel(String(c.payment_status || ''))}</span>
                            {typeof c.payment_amount === 'number' ? <span>¥{c.payment_amount}</span> : null}
                          </div>
                        ) : null}
                        {!paid ? (
                          <div className="text-amber-700 dark:text-amber-400">用户未支付，无法接单</div>
                        ) : null}
                        {c.description ? (
                          <div className="pt-1 text-slate-700 dark:text-white/70">{c.description}</div>
                        ) : null}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 sm:flex-col sm:items-end sm:justify-start">
                      <Button
                        variant="outline"
                        size="sm"
                        icon={MessageSquareText}
                        onClick={() => {
                          setMessagesConsultationId(c.id)
                          setMessagesTitle(`沟通：${c.subject}`)
                          setMessagesOpen(true)
                        }}
                      >
                        沟通
                      </Button>
                      {canAcceptOrReject ? (
                        <>
                          <Button
                            variant="primary"
                            size="sm"
                            icon={Handshake}
                            isLoading={acceptMutation.isPending}
                            disabled={!paid}
                            onClick={() => {
                              if (!confirm('确定接单吗？')) return
                              acceptMutation.mutate(c.id)
                            }}
                          >
                            接单
                          </Button>
                          <Button
                            variant="danger"
                            size="sm"
                            icon={XCircle}
                            isLoading={rejectMutation.isPending}
                            onClick={() => {
                              if (!confirm('确定拒单吗？')) return
                              rejectMutation.mutate(c.id)
                            }}
                          >
                            拒单
                          </Button>
                        </>
                      ) : null}

                      {canComplete ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={CheckCircle2}
                          isLoading={completeMutation.isPending}
                          onClick={() => {
                            if (!confirm('确定标记完成吗？')) return
                            completeMutation.mutate(c.id)
                          }}
                        >
                          标记完成
                        </Button>
                      ) : null}

                      <Button
                        variant="outline"
                        size="sm"
                        icon={FileText}
                        onClick={() => {
                          alert(`咨询ID: ${c.id}`)
                        }}
                      >
                        详情
                      </Button>
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

      <LawyerConsultationMessagesModal
        isOpen={messagesOpen}
        onClose={() => setMessagesOpen(false)}
        consultationId={messagesConsultationId}
        title={messagesTitle}
      />
    </div>
  )
}
