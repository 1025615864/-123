import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { CreditCard, ExternalLink, Eye, FileText, RefreshCw, XCircle } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { Badge, Button, Card, EmptyState, ListSkeleton, Modal, Pagination, Skeleton } from '../components/ui'
import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useAppMutation, useToast } from '../hooks'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'
import type { PaymentOrder } from '../types'

type OrdersListResponse = {
  items: PaymentOrder[]
  total: number
}

type ThirdPartyPayResponse = {
  pay_url?: string
}

function orderStatusToBadgeVariant(status: string): 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  const s = String(status || '').toLowerCase()
  if (s === 'paid') return 'success'
  if (s === 'pending') return 'warning'
  if (s === 'cancelled') return 'danger'
  if (s === 'refunded') return 'info'
  if (s === 'failed') return 'danger'
  return 'default'
}

function orderStatusToLabel(status: string): string {
  const s = String(status || '').toLowerCase()
  if (s === 'paid') return '已支付'
  if (s === 'pending') return '待支付'
  if (s === 'cancelled') return '已取消'
  if (s === 'refunded') return '已退款'
  if (s === 'failed') return '失败'
  return status || '未知'
}

function paymentMethodToLabel(value: string | null | undefined): string {
  const s = String(value || '').toLowerCase()
  if (!s) return '—'
  if (s === 'balance') return '余额'
  if (s === 'alipay') return '支付宝'
  if (s === 'ikunpay') return '爱坤支付'
  if (s === 'wechat') return '微信'
  return value || '—'
}

function orderTypeToNextStep(orderType: string | null | undefined): { label: string; to: string } | null {
  const t = String(orderType || '').trim().toLowerCase()
  if (!t) return null
  if (t === 'vip' || t === 'ai_pack' || t === 'recharge') {
    return { label: '去个人中心查看权益', to: '/profile' }
  }
  if (t === 'consultation') {
    return { label: '查看我的预约', to: '/orders?tab=consultations' }
  }
  if (t === 'service') {
    return { label: '去律所服务', to: '/lawfirm' }
  }
  return null
}

function orderStatusToHint(status: string): { title: string; description: string } {
  const s = String(status || '').toLowerCase()
  if (s === 'pending') {
    return {
      title: '待支付',
      description: '请完成支付。支付完成后可点击“刷新状态”确认结果。',
    }
  }
  if (s === 'paid') {
    return {
      title: '已支付',
      description: '订单已支付成功，可前往对应功能查看权益或服务进度。',
    }
  }
  if (s === 'cancelled') {
    return {
      title: '已取消',
      description: '该订单已取消。如需继续购买，请重新下单。',
    }
  }
  if (s === 'refunded') {
    return {
      title: '已退款',
      description: '退款通常原路返回，到账时间以支付渠道为准。',
    }
  }
  if (s === 'failed') {
    return {
      title: '支付失败',
      description: '可尝试重新支付或更换支付方式。',
    }
  }
  return { title: '状态未知', description: '如状态异常，请刷新或联系管理员。' }
}

function fmtMoney(amount: number | null | undefined): string {
  if (typeof amount !== 'number' || Number.isNaN(amount)) return ''
  return `¥${amount.toFixed(2)}`
}

export default function OrdersPage({ embedded = false }: { embedded?: boolean }) {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()
  const navigate = useNavigate()

  const [page, setPage] = useState(1)
  const pageSize = 20
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [refreshingTarget, setRefreshingTarget] = useState<string | null>(null)
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null)
  const [activeCancelOrderNo, setActiveCancelOrderNo] = useState<string | null>(null)
  const [activeBalancePayOrderNo, setActiveBalancePayOrderNo] = useState<string | null>(null)
  const [activeAlipayOrderNo, setActiveAlipayOrderNo] = useState<string | null>(null)

  const [paymentGuideOpen, setPaymentGuideOpen] = useState(false)
  const [paymentGuideOrderNo, setPaymentGuideOrderNo] = useState<string | null>(null)

  const queryKey = queryKeys.paymentOrders(page, pageSize, statusFilter)

  const listQuery = useQuery({
    queryKey,
    queryFn: async () => {
      const res = await api.get('/payment/orders', {
        params: {
          page,
          page_size: pageSize,
          status_filter: statusFilter || undefined,
        },
      })
      const data = res.data || {}
      const items = Array.isArray(data?.items) ? (data.items as PaymentOrder[]) : ([] as PaymentOrder[])
      return {
        items,
        total: Number(data?.total || 0),
      } satisfies OrdersListResponse
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
    toast.error(getApiErrorMessage(listQuery.error, '订单列表加载失败，请稍后重试'))
  }, [listQuery.error, toast])

  const cancelMutation = useAppMutation<unknown, string>({
    mutationFn: async (orderNo) => {
      await api.post(`/payment/orders/${encodeURIComponent(orderNo)}/cancel`)
    },
    successMessage: '订单已取消',
    errorMessageFallback: '取消失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.paymentOrdersBase()],
    onMutate: async (orderNo) => {
      setActiveCancelOrderNo(orderNo)
    },
    onSettled: (_data, _err, orderNo) => {
      setActiveCancelOrderNo((prev) => (prev === orderNo ? null : prev))
    },
  })

  const balancePayMutation = useAppMutation<unknown, string>({
    mutationFn: async (orderNo) => {
      await api.post(`/payment/orders/${encodeURIComponent(orderNo)}/pay`, {
        payment_method: 'balance',
      })
    },
    successMessage: '支付成功',
    errorMessageFallback: '支付失败，请稍后重试',
    disableErrorToast: true,
    invalidateQueryKeys: [queryKeys.paymentOrdersBase()],
    onMutate: async (orderNo) => {
      setActiveBalancePayOrderNo(orderNo)
    },
    onError: (err) => {
      const msg = getApiErrorMessage(err, '支付失败，请稍后重试')
      if (String(msg).includes('余额不足')) {
        toast.warning('余额不足，请先充值')
        navigate('/profile?recharge=1')
        return
      }
      toast.error(msg)
    },
    onSettled: (_data, _err, orderNo) => {
      setActiveBalancePayOrderNo((prev) => (prev === orderNo ? null : prev))
    },
  })

  const alipayMutation = useAppMutation<ThirdPartyPayResponse, string>({
    mutationFn: async (orderNo) => {
      const res = await api.post(`/payment/orders/${encodeURIComponent(orderNo)}/pay`, {
        payment_method: 'alipay',
      })
      return (res.data || {}) as ThirdPartyPayResponse
    },
    errorMessageFallback: '获取支付链接失败，请稍后重试',
    disableErrorToast: true,
    onMutate: async (orderNo) => {
      setActiveAlipayOrderNo(orderNo)
    },
    onSuccess: (data, orderNo) => {
      const url = String(data?.pay_url || '').trim()
      if (!url) {
        toast.error('未获取到支付链接')
        return
      }
      window.open(url, '_blank', 'noopener,noreferrer')
      toast.success('已打开支付页面')
      setPaymentGuideOrderNo(String(orderNo || '').trim() || null)
      setPaymentGuideOpen(true)
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, '获取支付链接失败，请稍后重试'))
    },
    onSettled: (_data, _err, orderNo) => {
      setActiveAlipayOrderNo((prev) => (prev === orderNo ? null : prev))
    },
  })

  const actionBusy = cancelMutation.isPending || balancePayMutation.isPending || alipayMutation.isPending

  const [detailOpen, setDetailOpen] = useState(false)
  const [detailOrderNo, setDetailOrderNo] = useState<string | null>(null)

  const detailQuery = useQuery({
    queryKey: queryKeys.paymentOrderDetail(detailOrderNo),
    queryFn: async () => {
      const res = await api.get(`/payment/orders/${encodeURIComponent(String(detailOrderNo))}`)
      return (res.data || null) as PaymentOrder | null
    },
    enabled: isAuthenticated && !!detailOrderNo,
    retry: 1,
    refetchOnWindowFocus: false,
  })

  const items = listQuery.data?.items ?? []
  const total = listQuery.data?.total ?? 0
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total])

  const handleCancel = (orderNo: string) => {
    if (!confirm('确定要取消该订单吗？')) return
    if (cancelMutation.isPending) return
    cancelMutation.mutate(orderNo)
  }

  const handleBalancePay = (orderNo: string) => {
    if (!confirm('确定使用余额支付该订单吗？')) return
    if (balancePayMutation.isPending) return
    balancePayMutation.mutate(orderNo)
  }

  const handleAlipayPay = (orderNo: string) => {
    if (alipayMutation.isPending) return
    alipayMutation.mutate(orderNo)
  }

  const handleRefreshStatus = async () => {
    setRefreshingTarget('__all__')
    const res = await listQuery.refetch()
    if (res.error) {
      toast.error(getApiErrorMessage(res.error, '刷新失败，请稍后重试'))
      setRefreshingTarget(null)
      return
    }

    if (detailOrderNo) {
      const detailRes = await detailQuery.refetch()
      if (detailRes.error) {
        toast.error(getApiErrorMessage(detailRes.error, '订单详情刷新失败'))
      }
    }

    setLastRefreshedAt(new Date().toLocaleString())
    toast.success('已刷新订单状态')
    setRefreshingTarget(null)
  }

  const handleRefreshOne = async (orderNo: string) => {
    const target = String(orderNo || '').trim()
    if (!target) return
    setRefreshingTarget(target)
    const res = await listQuery.refetch()
    if (res.error) {
      toast.error(getApiErrorMessage(res.error, '刷新失败，请稍后重试'))
      setRefreshingTarget(null)
      return
    }
    if (detailOrderNo && detailOrderNo === target) {
      const detailRes = await detailQuery.refetch()
      if (detailRes.error) {
        toast.error(getApiErrorMessage(detailRes.error, '订单详情刷新失败'))
      }
    }
    setLastRefreshedAt(new Date().toLocaleString())
    toast.success('已刷新订单状态')
    setRefreshingTarget(null)
  }

  const openDetail = (orderNo: string) => {
    setDetailOrderNo(orderNo)
    setDetailOpen(true)
  }

  const closeDetail = () => {
    setDetailOpen(false)
    setDetailOrderNo(null)
  }

  const setFilter = (next: string | null) => {
    setPage(1)
    setStatusFilter(next)
  }

  if (!isAuthenticated) {
    return (
      <div className={embedded ? 'space-y-6' : 'space-y-10'}>
        {embedded ? null : (
          <PageHeader
            eyebrow="订单"
            title="我的订单"
            description="登录后可查看与管理你的支付订单"
            layout="mdStart"
            tone={actualTheme}
          />
        )}
        <EmptyState
          icon={FileText}
          title="请先登录"
          description="登录后即可查看你的订单记录"
          tone={actualTheme}
        />
      </div>
    )
  }

  return (
    <div className={embedded ? 'space-y-6' : 'space-y-10'}>
      {embedded ? null : (
        <PageHeader
          eyebrow="订单"
          title="我的订单"
          description={
            lastRefreshedAt
              ? `查看订单状态、支付或取消 · 最近更新 ${lastRefreshedAt}`
              : '查看订单状态、支付或取消'
          }
          layout="mdStart"
          tone={actualTheme}
          right={
            <Button
              variant="outline"
              icon={RefreshCw}
              isLoading={refreshingTarget === '__all__'}
              loadingText="刷新中..."
              onClick={() => void handleRefreshStatus()}
              disabled={listQuery.isFetching || refreshingTarget != null}
            >
              刷新
            </Button>
          }
        />
      )}

      <Card variant="surface" padding="lg">
        {embedded ? (
          <div className="flex justify-end mb-4">
            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              isLoading={refreshingTarget === '__all__'}
              loadingText="刷新中..."
              onClick={() => void handleRefreshStatus()}
              disabled={listQuery.isFetching || refreshingTarget != null}
            >
              刷新
            </Button>
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <Button variant={statusFilter === null ? 'primary' : 'outline'} size="sm" onClick={() => setFilter(null)}>
            全部
          </Button>
          <Button variant={statusFilter === 'pending' ? 'primary' : 'outline'} size="sm" onClick={() => setFilter('pending')}>
            待支付
          </Button>
          <Button variant={statusFilter === 'paid' ? 'primary' : 'outline'} size="sm" onClick={() => setFilter('paid')}>
            已支付
          </Button>
          <Button variant={statusFilter === 'cancelled' ? 'primary' : 'outline'} size="sm" onClick={() => setFilter('cancelled')}>
            已取消
          </Button>
        </div>

        {listQuery.isLoading && items.length === 0 ? (
          <ListSkeleton count={4} />
        ) : items.length === 0 ? (
          <EmptyState icon={FileText} title="暂无订单" description="你的订单会显示在这里" tone={actualTheme} />
        ) : (
          <div className="space-y-4">
            {items.map((o) => {
              const status = String(o.status || '')
              const statusLower = status.toLowerCase()
              const canPay = statusLower === 'pending' || statusLower === 'failed'
              const canCancel = statusLower === 'pending'
              const hint = orderStatusToHint(status)
              const nextStep = orderTypeToNextStep(o.order_type)
              const balancePayLoading = balancePayMutation.isPending && activeBalancePayOrderNo === o.order_no
              const alipayLoading = alipayMutation.isPending && activeAlipayOrderNo === o.order_no
              const cancelLoading = cancelMutation.isPending && activeCancelOrderNo === o.order_no
              const rowBusy = actionBusy && !(balancePayLoading || alipayLoading || cancelLoading)
              return (
                <Card key={o.order_no} variant="surface" padding="md" className="border border-slate-200/70 dark:border-white/10">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-base font-semibold text-slate-900 dark:text-white truncate">{o.title}</h3>
                        <Badge variant={orderStatusToBadgeVariant(status)} size="sm">
                          {orderStatusToLabel(status)}
                        </Badge>
                      </div>
                      <div className="mt-1 text-xs text-slate-500 dark:text-white/50">{hint.description}</div>
                      <div className="mt-2 space-y-1 text-sm text-slate-600 dark:text-white/60">
                        <div>订单号：{o.order_no}</div>
                        <div>金额：{fmtMoney(o.actual_amount)}</div>
                        <div>支付方式：{paymentMethodToLabel(o.payment_method)}</div>
                        <div>创建时间：{new Date(o.created_at).toLocaleString()}</div>
                        {o.paid_at ? <div>支付时间：{new Date(o.paid_at).toLocaleString()}</div> : null}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 sm:flex-col sm:items-end sm:justify-start">
                      <Button variant="outline" size="sm" icon={Eye} onClick={() => openDetail(o.order_no)}>
                        详情
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        icon={RefreshCw}
                        isLoading={refreshingTarget === o.order_no}
                        loadingText="刷新中..."
                        disabled={refreshingTarget != null}
                        onClick={() => void handleRefreshOne(o.order_no)}
                      >
                        刷新状态
                      </Button>
                      {canPay ? (
                        <>
                          <Button
                            variant="primary"
                            size="sm"
                            icon={CreditCard}
                            isLoading={balancePayLoading}
                            loadingText="支付中..."
                            disabled={rowBusy || balancePayLoading}
                            onClick={() => handleBalancePay(o.order_no)}
                          >
                            {statusLower === 'failed' ? '重新余额支付' : '余额支付'}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            icon={ExternalLink}
                            isLoading={alipayLoading}
                            loadingText="获取中..."
                            disabled={rowBusy || alipayLoading}
                            onClick={() => handleAlipayPay(o.order_no)}
                          >
                            {statusLower === 'failed' ? '重新支付宝支付' : '支付宝支付'}
                          </Button>
                        </>
                      ) : null}
                      {canCancel ? (
                        <Button
                          variant="danger"
                          size="sm"
                          icon={XCircle}
                          isLoading={cancelLoading}
                          loadingText="取消中..."
                          disabled={rowBusy || cancelLoading}
                          onClick={() => handleCancel(o.order_no)}
                        >
                          取消
                        </Button>
                      ) : null}

                      {statusLower === 'paid' && nextStep ? (
                        <Link to={nextStep.to} className="w-full sm:w-auto">
                          <Button variant="primary" size="sm" icon={ExternalLink}>
                            {nextStep.label}
                          </Button>
                        </Link>
                      ) : null}

                      {(statusLower === 'cancelled' || statusLower === 'refunded') && nextStep ? (
                        <Link to={nextStep.to} className="w-full sm:w-auto">
                          <Button variant="outline" size="sm" icon={ExternalLink}>
                            去重新下单
                          </Button>
                        </Link>
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

      <Modal
        isOpen={detailOpen}
        onClose={() => {
          if (actionBusy) return
          closeDetail()
        }}
        title="订单详情"
        description={detailOrderNo ? `订单号：${detailOrderNo}` : undefined}
        size="lg"
      >
        {detailQuery.isLoading ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <Skeleton width="56px" height="22px" />
              <Skeleton width="220px" height="14px" />
            </div>

            <Card variant="surface" padding="md" className="border border-slate-200/70 dark:border-white/10">
              <div className="space-y-2">
                <Skeleton width="100%" height="14px" />
                <Skeleton width="92%" height="14px" />
                <Skeleton width="86%" height="14px" />
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Skeleton width="88px" height="32px" />
                <Skeleton width="112px" height="32px" />
              </div>
            </Card>
          </div>
        ) : detailQuery.isError ? (
          <EmptyState
            icon={FileText}
            title="加载失败"
            description={getApiErrorMessage(detailQuery.error, '订单详情加载失败')}
            tone={actualTheme}
          />
        ) : detailQuery.data ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant={orderStatusToBadgeVariant(String(detailQuery.data.status || ''))} size="sm">
                {orderStatusToLabel(String(detailQuery.data.status || ''))}
              </Badge>
              <span className="text-sm text-slate-600 dark:text-white/60">{detailQuery.data.title}</span>
            </div>

            <Card variant="surface" padding="md" className="border border-slate-200/70 dark:border-white/10">
              <div className="text-sm text-slate-700 dark:text-white/70">
                {orderStatusToHint(String(detailQuery.data.status || '')).description}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  icon={RefreshCw}
                  isLoading={detailQuery.isFetching}
                  loadingText="刷新中..."
                  disabled={detailQuery.isFetching}
                  onClick={() => void handleRefreshStatus()}
                >
                  刷新状态
                </Button>

                {(() => {
                  const detail = detailQuery.data
                  if (!detail) return null
                  const s = String(detail.status || '').toLowerCase()
                  const canPay = s === 'pending' || s === 'failed'
                  const canCancel = s === 'pending'
                  const next = orderTypeToNextStep(detail.order_type)

                  return (
                    <>
                      {canPay ? (
                        <>
                          <Button
                            variant="primary"
                            size="sm"
                            icon={CreditCard}
                            isLoading={balancePayMutation.isPending && activeBalancePayOrderNo === detail.order_no}
                            loadingText="支付中..."
                            disabled={
                              (actionBusy && activeBalancePayOrderNo !== detail.order_no) ||
                              balancePayMutation.isPending
                            }
                            onClick={() => handleBalancePay(detail.order_no)}
                          >
                            {s === 'failed' ? '重新余额支付' : '余额支付'}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            icon={ExternalLink}
                            isLoading={alipayMutation.isPending && activeAlipayOrderNo === detail.order_no}
                            loadingText="获取中..."
                            disabled={
                              (actionBusy && activeAlipayOrderNo !== detail.order_no) ||
                              alipayMutation.isPending
                            }
                            onClick={() => handleAlipayPay(detail.order_no)}
                          >
                            {s === 'failed' ? '重新支付宝支付' : '支付宝支付'}
                          </Button>
                        </>
                      ) : null}
                      {canCancel ? (
                        <Button
                          variant="danger"
                          size="sm"
                          icon={XCircle}
                          isLoading={cancelMutation.isPending && activeCancelOrderNo === detail.order_no}
                          loadingText="取消中..."
                          disabled={
                            (actionBusy && activeCancelOrderNo !== detail.order_no) || cancelMutation.isPending
                          }
                          onClick={() => handleCancel(detail.order_no)}
                        >
                          取消订单
                        </Button>
                      ) : null}
                      {s === 'paid' && next ? (
                        <Link to={next.to}>
                          <Button variant="primary" size="sm" icon={ExternalLink}>
                            {next.label}
                          </Button>
                        </Link>
                      ) : null}
                    </>
                  )
                })()}
              </div>
            </Card>

            <Card variant="surface" padding="md" className="border border-slate-200/70 dark:border-white/10">
              <div className="space-y-2 text-sm text-slate-700 dark:text-white/70">
                <div>订单号：{detailQuery.data.order_no}</div>
                <div>类型：{detailQuery.data.order_type}</div>
                <div>金额：{fmtMoney(detailQuery.data.actual_amount)}</div>
                <div>支付方式：{paymentMethodToLabel(detailQuery.data.payment_method)}</div>
                <div>创建时间：{new Date(detailQuery.data.created_at).toLocaleString()}</div>
                {detailQuery.data.paid_at ? <div>支付时间：{new Date(detailQuery.data.paid_at).toLocaleString()}</div> : null}
              </div>
            </Card>
          </div>
        ) : (
          <EmptyState icon={FileText} title="无数据" description="未获取到订单详情" tone={actualTheme} />
        )}
      </Modal>

      <Modal
        isOpen={paymentGuideOpen}
        onClose={() => setPaymentGuideOpen(false)}
        title="支付提示"
        description="支付完成后请返回本站刷新订单状态"
        size="sm"
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200/70 bg-slate-900/5 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/70">
            <div>1) 在新打开的支付页面完成支付</div>
            <div className="mt-1">2) 回到本站点击“我已支付，刷新状态”确认结果</div>
          </div>

          <Button
            fullWidth
            icon={RefreshCw}
            onClick={() => {
              setPaymentGuideOpen(false)
              if (paymentGuideOrderNo) {
                void handleRefreshOne(paymentGuideOrderNo)
              } else {
                void handleRefreshStatus()
              }
            }}
          >
            我已支付，刷新状态
          </Button>

          <Button
            fullWidth
            variant="outline"
            icon={CreditCard}
            onClick={() => {
              setPaymentGuideOpen(false)
              navigate('/profile')
            }}
          >
            去个人中心查看余额/权益
          </Button>
        </div>
      </Modal>
    </div>
  )
}
