import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileText, Handshake, MessageSquareText, RotateCcw, XCircle } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { Badge, Button, Card, EmptyState, ListSkeleton, Modal, ModalActions, Pagination, Skeleton, Textarea } from '../components/ui'
import api from '../api/client'
import LawyerConsultationMessagesModal from '../components/LawyerConsultationMessagesModal'
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

type VerificationStatusResponse = {
  status: string
  reject_reason?: string | null
  message?: string
}

type ReviewTaskItem = {
  id: number
  consultation_id: number
  user_id: number
  order_no: string
  status: string
  lawyer_id: number | null
  result_markdown: string | null
  claimed_at: string | null
  submitted_at: string | null
  created_at: string
  updated_at: string
}

type ReviewTaskListResponse = {
  items: ReviewTaskItem[]
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

function reviewStatusToBadgeVariant(status: string): 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  const s = String(status || '').toLowerCase()
  if (s === 'pending') return 'warning'
  if (s === 'claimed') return 'info'
  if (s === 'submitted') return 'success'
  return 'default'
}

function reviewStatusToLabel(status: string): string {
  const s = String(status || '').toLowerCase()
  if (s === 'pending') return '待领取'
  if (s === 'claimed') return '处理中'
  if (s === 'submitted') return '已提交'
  return status || '未知'
}

export default function LawyerDashboardPage() {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()
  const queryClient = useQueryClient()

  const [activeTab, setActiveTab] = useState<'consultations' | 'reviews'>('consultations')

  const [messagesOpen, setMessagesOpen] = useState(false)
  const [messagesConsultationId, setMessagesConsultationId] = useState<number | null>(null)
  const [messagesTitle, setMessagesTitle] = useState<string>('')

  const [page, setPage] = useState(1)
  const pageSize = 20

  const queryKey = ['lawyer-consultations', { page, pageSize }] as const

  const listQuery = useQuery({
    queryKey,
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

  const [activeActionId, setActiveActionId] = useState<number | null>(null)

  const acceptMutation = useAppMutation<unknown, number, { previous?: ConsultationListResponse }>({
    mutationFn: async (id) => {
      await api.post(`/lawfirm/lawyer/consultations/${id}/accept`)
    },
    successMessage: '已接单',
    errorMessageFallback: '接单失败，请稍后重试',
    onMutate: async (id) => {
      setActiveActionId(id)
      const previous = queryClient.getQueryData<ConsultationListResponse>(queryKey)
      queryClient.setQueryData<ConsultationListResponse>(queryKey, (old) => {
        if (!old) return old
        return {
          ...old,
          items: (old.items ?? []).map((c) => (c.id === id ? { ...c, status: 'confirmed' } : c)),
        }
      })
      return { previous }
    },
    onError: (err, _id, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(queryKey, ctx.previous)
      }
      return err as any
    },
    onSettled: async () => {
      setActiveActionId(null)
      await listQuery.refetch()
    },
  })

  const rejectMutation = useAppMutation<unknown, number, { previous?: ConsultationListResponse }>({
    mutationFn: async (id) => {
      await api.post(`/lawfirm/lawyer/consultations/${id}/reject`)
    },
    successMessage: '已拒单',
    errorMessageFallback: '拒单失败，请稍后重试',
    onMutate: async (id) => {
      setActiveActionId(id)
      const previous = queryClient.getQueryData<ConsultationListResponse>(queryKey)
      queryClient.setQueryData<ConsultationListResponse>(queryKey, (old) => {
        if (!old) return old
        return {
          ...old,
          items: (old.items ?? []).map((c) => (c.id === id ? { ...c, status: 'cancelled' } : c)),
        }
      })
      return { previous }
    },
    onError: (err, _id, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(queryKey, ctx.previous)
      }
      return err as any
    },
    onSettled: async () => {
      setActiveActionId(null)
      await listQuery.refetch()
    },
  })

  const completeMutation = useAppMutation<unknown, number, { previous?: ConsultationListResponse }>({
    mutationFn: async (id) => {
      await api.post(`/lawfirm/lawyer/consultations/${id}/complete`)
    },
    successMessage: '已标记完成',
    errorMessageFallback: '操作失败，请稍后重试',
    onMutate: async (id) => {
      setActiveActionId(id)
      const previous = queryClient.getQueryData<ConsultationListResponse>(queryKey)
      queryClient.setQueryData<ConsultationListResponse>(queryKey, (old) => {
        if (!old) return old
        return {
          ...old,
          items: (old.items ?? []).map((c) => (c.id === id ? { ...c, status: 'completed' } : c)),
        }
      })
      return { previous }
    },
    onError: (err, _id, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(queryKey, ctx.previous)
      }
      return err as any
    },
    onSettled: async () => {
      setActiveActionId(null)
      await listQuery.refetch()
    },
  })

  const items = listQuery.data?.items ?? []
  const total = listQuery.data?.total ?? 0
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total])

  const [reviewPage, setReviewPage] = useState(1)
  const reviewPageSize = 20
  const [reviewStatusFilter, setReviewStatusFilter] = useState<string | null>(null)

  const reviewQueryKey = queryKeys.lawyerReviewTasks(reviewPage, reviewPageSize, reviewStatusFilter)
  const reviewListQuery = useQuery<ReviewTaskListResponse>({
    queryKey: reviewQueryKey,
    queryFn: async () => {
      const res = await api.get('/reviews/lawyer/tasks', {
        params: {
          status: reviewStatusFilter || undefined,
          page: reviewPage,
          page_size: reviewPageSize,
        },
      })
      const data = res.data || {}
      return {
        items: Array.isArray(data?.items) ? (data.items as ReviewTaskItem[]) : ([] as ReviewTaskItem[]),
        total: Number(data?.total || 0),
        page: Number(data?.page || reviewPage),
        page_size: Number(data?.page_size || reviewPageSize),
      } satisfies ReviewTaskListResponse
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) =>
      prev ?? ({ items: [], total: 0, page: reviewPage, page_size: reviewPageSize } satisfies ReviewTaskListResponse),
  })

  useEffect(() => {
    if (!reviewListQuery.error) return
    const status = (reviewListQuery.error as any)?.response?.status
    if (status === 401) return
    if (status === 403) return
    toast.error(getApiErrorMessage(reviewListQuery.error, '加载失败，请稍后重试'))
  }, [reviewListQuery.error, toast])

  const [activeReviewActionId, setActiveReviewActionId] = useState<number | null>(null)
  const [submitOpen, setSubmitOpen] = useState(false)
  const [submitTarget, setSubmitTarget] = useState<ReviewTaskItem | null>(null)
  const [submitContent, setSubmitContent] = useState('')

  const reviewData = reviewListQuery.data as ReviewTaskListResponse | undefined
  const reviewItems = reviewData?.items ?? ([] as ReviewTaskItem[])
  const reviewTotal = Number(reviewData?.total || 0)

  const claimReviewMutation = useAppMutation<unknown, number, { previous?: ReviewTaskListResponse }>({
    mutationFn: async (taskId) => {
      await api.post(`/reviews/lawyer/tasks/${taskId}/claim`)
    },
    successMessage: '已领取',
    errorMessageFallback: '领取失败，请稍后重试',
    onMutate: async (taskId) => {
      setActiveReviewActionId(taskId)
      const previous = queryClient.getQueryData<ReviewTaskListResponse>(reviewQueryKey)
      queryClient.setQueryData<ReviewTaskListResponse>(reviewQueryKey, (old) => {
        if (!old) return old
        return {
          ...old,
          items: (old.items ?? []).map((t) => (t.id === taskId ? { ...t, status: 'claimed' } : t)),
        }
      })
      return { previous }
    },
    onError: (err, _id, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(reviewQueryKey, ctx.previous)
      }
      return err as any
    },
    onSettled: async () => {
      setActiveReviewActionId(null)
      await reviewListQuery.refetch()
    },
  })

  const submitReviewMutation = useAppMutation<unknown, { taskId: number; content: string }>({
    mutationFn: async ({ taskId, content }) => {
      await api.post(`/reviews/lawyer/tasks/${taskId}/submit`, {
        content_markdown: content,
      })
    },
    successMessage: '已提交',
    errorMessageFallback: '提交失败，请稍后重试',
    onMutate: async ({ taskId }) => {
      setActiveReviewActionId(taskId)
    },
    onSettled: async () => {
      setActiveReviewActionId(null)
      setSubmitOpen(false)
      setSubmitTarget(null)
      setSubmitContent('')
      await reviewListQuery.refetch()
    },
  })

  const actionBusy = acceptMutation.isPending || rejectMutation.isPending || completeMutation.isPending
  const reviewBusy = claimReviewMutation.isPending || submitReviewMutation.isPending

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
  const listErrorDetail = String((listQuery.error as any)?.response?.data?.detail || '')

  const verificationQuery = useQuery({
    queryKey: ['lawyer-verification-status'] as const,
    queryFn: async () => {
      const res = await api.get('/lawfirm/verification/status')
      return (res.data || {}) as VerificationStatusResponse
    },
    enabled: isAuthenticated && listQuery.isError && listErrorStatus === 403,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  if (listQuery.isError && listErrorStatus === 403) {
    const vStatus = String(verificationQuery.data?.status || '').toLowerCase()
    const rejectReason = String(verificationQuery.data?.reject_reason || '').trim()

    let title = '暂无权限'
    let description = '请先完成律师认证并通过审核'

    if (listErrorDetail.includes('管理员不支持')) {
      title = '该账号无法使用律师工作台'
      description = '当前账号为管理员，请切换到律师账号登录'
    } else if (listErrorDetail.includes('律师认证审核中') || vStatus === 'pending') {
      title = '认证审核中'
      description = '你的律师认证申请正在审核，请耐心等待'
    } else if (listErrorDetail.includes('律师认证已驳回') || vStatus === 'rejected') {
      title = '认证已驳回'
      description = rejectReason ? `驳回原因：${rejectReason}` : '请前往认证页面查看原因并重新提交'
    } else if (listErrorDetail.includes('未绑定律师资料')) {
      title = '律师资料未绑定'
      description = '请先完成律师认证，审核通过后会自动绑定律师资料'
    } else if (listErrorDetail.includes('律师认证未通过')) {
      title = '律师认证未通过'
      description = '请先完成律师认证并通过审核'
    } else if (listErrorDetail.includes('需要律师权限')) {
      title = '需要律师权限'
      description = '请先完成律师认证并通过审核'
    }

    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律师"
          title="律师工作台"
          description={description}
          layout="mdStart"
          tone={actualTheme}
        />
        <EmptyState
          icon={Handshake}
          title={title}
          description={description}
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
              <Skeleton width="64px" height="36px" />
              <Skeleton width="64px" height="36px" />
              <Skeleton width="72px" height="36px" />
            </div>
          }
        />

        <Card variant="surface" padding="lg">
          <ListSkeleton count={3} />
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="律师"
        title="律师工作台"
        description={activeTab === 'consultations' ? '处理用户预约：接单 / 拒单 / 标记完成' : '处理律师复核任务：领取 / 提交'}
        layout="mdStart"
        tone={actualTheme}
        right={
          <div className="flex items-center gap-2">
            <Button
              variant={activeTab === 'consultations' ? 'primary' : 'outline'}
              size="sm"
              disabled={actionBusy || reviewBusy}
              onClick={() => {
                if (actionBusy || reviewBusy) return
                setActiveTab('consultations')
              }}
            >
              预约
            </Button>
            <Button
              variant={activeTab === 'reviews' ? 'primary' : 'outline'}
              size="sm"
              disabled={actionBusy || reviewBusy}
              onClick={() => {
                if (actionBusy || reviewBusy) return
                setActiveTab('reviews')
              }}
            >
              复核任务
            </Button>
            <Button
              variant="outline"
              icon={RotateCcw}
              isLoading={activeTab === 'consultations' ? listQuery.isFetching : reviewListQuery.isFetching}
              loadingText="刷新中..."
              onClick={() => {
                if (activeTab === 'consultations') {
                  if (actionBusy) return
                  listQuery.refetch()
                  return
                }
                if (reviewBusy) return
                reviewListQuery.refetch()
              }}
              disabled={
                activeTab === 'consultations'
                  ? listQuery.isFetching || actionBusy
                  : reviewListQuery.isFetching || reviewBusy
              }
            >
              刷新
            </Button>
          </div>
        }
      />

      <Card variant="surface" padding="lg">
        {activeTab === 'consultations' ? (
          items.length === 0 ? (
            <EmptyState
              icon={Handshake}
              title="暂无预约"
              description="暂时没有用户预约需要处理"
              tone={actualTheme}
            />
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

                const isActive = activeActionId === c.id
                const rowBusy = actionBusy && isActive
                const disableOther = actionBusy && !isActive
                const acceptLoading = acceptMutation.isPending && isActive
                const rejectLoading = rejectMutation.isPending && isActive
                const completeLoading = completeMutation.isPending && isActive
                const acceptDisabled = !paid || (rowBusy && !acceptLoading) || disableOther
                const rejectDisabled = (rowBusy && !rejectLoading) || disableOther
                const completeDisabled = (rowBusy && !completeLoading) || disableOther

                return (
                  <Card
                    key={c.id}
                    variant="surface"
                    padding="md"
                    className="border border-slate-200/70 dark:border-white/10"
                  >
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
                          disabled={actionBusy || disableOther}
                          onClick={() => {
                            if (actionBusy) return
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
                              isLoading={acceptLoading}
                              loadingText="接单中..."
                              disabled={acceptDisabled}
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
                              isLoading={rejectLoading}
                              loadingText="拒单中..."
                              disabled={rejectDisabled}
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
                            isLoading={completeLoading}
                            loadingText="处理中..."
                            disabled={completeDisabled}
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
                          disabled={actionBusy || disableOther}
                          onClick={() => {
                            if (actionBusy) return
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
                <Pagination
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={(p) => {
                    if (actionBusy) return
                    setPage(p)
                  }}
                />
              </div>
            </div>
          )
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant={reviewStatusFilter === null ? 'primary' : 'outline'}
                size="sm"
                disabled={reviewBusy}
                onClick={() => {
                  if (reviewBusy) return
                  setReviewPage(1)
                  setReviewStatusFilter(null)
                }}
              >
                全部
              </Button>
              <Button
                variant={reviewStatusFilter === 'pending' ? 'primary' : 'outline'}
                size="sm"
                disabled={reviewBusy}
                onClick={() => {
                  if (reviewBusy) return
                  setReviewPage(1)
                  setReviewStatusFilter('pending')
                }}
              >
                待领取
              </Button>
              <Button
                variant={reviewStatusFilter === 'claimed' ? 'primary' : 'outline'}
                size="sm"
                disabled={reviewBusy}
                onClick={() => {
                  if (reviewBusy) return
                  setReviewPage(1)
                  setReviewStatusFilter('claimed')
                }}
              >
                处理中
              </Button>
              <Button
                variant={reviewStatusFilter === 'submitted' ? 'primary' : 'outline'}
                size="sm"
                disabled={reviewBusy}
                onClick={() => {
                  if (reviewBusy) return
                  setReviewPage(1)
                  setReviewStatusFilter('submitted')
                }}
              >
                已提交
              </Button>
            </div>

            {reviewListQuery.isLoading && reviewItems.length === 0 ? (
              <ListSkeleton count={3} />
            ) : reviewItems.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="暂无复核任务"
                description="当前没有待处理的律师复核任务"
                tone={actualTheme}
              />
            ) : (
              <div className="space-y-4">
                {reviewItems.map((t) => {
                  const status = String(t.status || '')
                  const s = status.toLowerCase()
                  const canClaim = s === 'pending' && (t.lawyer_id == null)
                  const canSubmit = s === 'claimed'

                  const isActive = activeReviewActionId === t.id
                  const rowBusy = reviewBusy && isActive
                  const disableOther = reviewBusy && !isActive
                  const claimLoading = claimReviewMutation.isPending && isActive
                  const submitLoading = submitReviewMutation.isPending && isActive

                  return (
                    <Card
                      key={t.id}
                      variant="surface"
                      padding="md"
                      className="border border-slate-200/70 dark:border-white/10"
                    >
                      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <div className="text-base font-semibold text-slate-900 dark:text-white">
                              复核任务 #{t.id}
                            </div>
                            <Badge variant={reviewStatusToBadgeVariant(status)} size="sm">
                              {reviewStatusToLabel(status)}
                            </Badge>
                          </div>

                          <div className="mt-2 space-y-1 text-sm text-slate-600 dark:text-white/60">
                            <div>咨询ID：{t.consultation_id}</div>
                            <div>用户ID：{t.user_id}</div>
                            <div>订单号：{t.order_no}</div>
                            {t.submitted_at ? <div>提交时间：{new Date(t.submitted_at).toLocaleString()}</div> : null}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 sm:flex-col sm:items-end sm:justify-start">
                          {canClaim ? (
                            <Button
                              variant="primary"
                              size="sm"
                              icon={Handshake}
                              isLoading={claimLoading}
                              loadingText="领取中..."
                              disabled={(rowBusy && !claimLoading) || disableOther}
                              onClick={() => {
                                if (!confirm('确定领取该任务吗？')) return
                                claimReviewMutation.mutate(t.id)
                              }}
                            >
                              领取
                            </Button>
                          ) : null}

                          {canSubmit ? (
                            <Button
                              variant="secondary"
                              size="sm"
                              icon={CheckCircle2}
                              disabled={(rowBusy && !submitLoading) || disableOther}
                              onClick={() => {
                                if (reviewBusy) return
                                setSubmitTarget(t)
                                setSubmitContent(String(t.result_markdown || '').trim())
                                setSubmitOpen(true)
                              }}
                            >
                              编辑提交
                            </Button>
                          ) : null}

                          <Button
                            variant="outline"
                            size="sm"
                            icon={FileText}
                            disabled={reviewBusy || disableOther}
                            onClick={() => {
                              alert(`咨询ID: ${t.consultation_id}`)
                            }}
                          >
                            关联咨询
                          </Button>
                        </div>
                      </div>
                    </Card>
                  )
                })}

                <div className="pt-4">
                  <Pagination
                    currentPage={reviewPage}
                    totalPages={Math.max(1, Math.ceil(reviewTotal / reviewPageSize))}
                    onPageChange={(p) => {
                      if (reviewBusy) return
                      setReviewPage(p)
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      <Modal
        isOpen={submitOpen}
        onClose={() => {
          if (submitReviewMutation.isPending) return
          setSubmitOpen(false)
          setSubmitTarget(null)
          setSubmitContent('')
        }}
        title="提交复核结果"
        description={submitTarget ? `任务 #${submitTarget.id} · 咨询ID ${submitTarget.consultation_id}` : undefined}
        size="lg"
      >
        <div className="space-y-4">
          <Textarea
            label="复核稿（Markdown）"
            value={submitContent}
            onChange={(e) => setSubmitContent(e.target.value)}
            className="min-h-[260px]"
            disabled={submitReviewMutation.isPending}
            placeholder="请输入复核意见（支持 Markdown）"
          />

          <ModalActions>
            <Button
              variant="secondary"
              onClick={() => {
                if (submitReviewMutation.isPending) return
                setSubmitOpen(false)
                setSubmitTarget(null)
                setSubmitContent('')
              }}
              disabled={submitReviewMutation.isPending}
            >
              取消
            </Button>
            <Button
              isLoading={submitReviewMutation.isPending}
              loadingText="提交中..."
              disabled={submitReviewMutation.isPending}
              onClick={() => {
                const t = submitTarget
                const content = String(submitContent || '').trim()
                if (!t) return
                if (!content) {
                  toast.error('请输入复核内容')
                  return
                }
                if (!confirm('确定提交复核结果吗？提交后将生成收入记录。')) return
                submitReviewMutation.mutate({ taskId: t.id, content })
              }}
            >
              提交
            </Button>
          </ModalActions>
        </div>
      </Modal>

      <LawyerConsultationMessagesModal
        isOpen={messagesOpen}
        onClose={() => setMessagesOpen(false)}
        consultationId={messagesConsultationId}
        title={messagesTitle}
      />
    </div>
  )
}
