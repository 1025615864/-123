import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CreditCard, ExternalLink, Eye, FileText, RefreshCw, XCircle } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { Badge, Button, Card, EmptyState, Loading, Modal, Pagination } from '../components/ui'
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
  if (s === 'wechat') return '微信'
  return value || '—'
}

function fmtMoney(amount: number | null | undefined): string {
  if (typeof amount !== 'number' || Number.isNaN(amount)) return ''
  return `¥${amount.toFixed(2)}`
}

export default function OrdersPage({ embedded = false }: { embedded?: boolean }) {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()

  const [page, setPage] = useState(1)
  const pageSize = 20
  const [statusFilter, setStatusFilter] = useState<string | null>(null)

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
  })

  const balancePayMutation = useAppMutation<unknown, string>({
    mutationFn: async (orderNo) => {
      await api.post(`/payment/orders/${encodeURIComponent(orderNo)}/pay`, {
        payment_method: 'balance',
      })
    },
    successMessage: '支付成功',
    errorMessageFallback: '支付失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.paymentOrdersBase()],
  })

  const alipayMutation = useAppMutation<ThirdPartyPayResponse, string>({
    mutationFn: async (orderNo) => {
      const res = await api.post(`/payment/orders/${encodeURIComponent(orderNo)}/pay`, {
        payment_method: 'alipay',
      })
      return (res.data || {}) as ThirdPartyPayResponse
    },
    errorMessageFallback: '获取支付链接失败，请稍后重试',
    onSuccess: (data) => {
      const url = String(data?.pay_url || '').trim()
      if (!url) {
        toast.error('未获取到支付链接')
        return
      }
      window.open(url, '_blank', 'noopener,noreferrer')
      toast.success('已打开支付宝支付页面')
    },
  })

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
    cancelMutation.mutate(orderNo)
  }

  const handleBalancePay = (orderNo: string) => {
    if (!confirm('确定使用余额支付该订单吗？')) return
    balancePayMutation.mutate(orderNo)
  }

  const handleAlipayPay = (orderNo: string) => {
    alipayMutation.mutate(orderNo)
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

  if (listQuery.isLoading && items.length === 0) {
    return <Loading text="加载中..." tone={actualTheme} />
  }

  return (
    <div className={embedded ? 'space-y-6' : 'space-y-10'}>
      {embedded ? null : (
        <PageHeader
          eyebrow="订单"
          title="我的订单"
          description="查看订单状态、支付或取消"
          layout="mdStart"
          tone={actualTheme}
          right={
            <Button
              variant="outline"
              onClick={() => listQuery.refetch()}
              disabled={listQuery.isFetching}
            >
              <RefreshCw
                className={`h-4 w-4 mr-2 ${listQuery.isFetching ? 'animate-spin' : ''}`}
              />
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
              onClick={() => listQuery.refetch()}
              disabled={listQuery.isFetching}
            >
              <RefreshCw
                className={`h-4 w-4 mr-2 ${listQuery.isFetching ? 'animate-spin' : ''}`}
              />
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

        {items.length === 0 ? (
          <EmptyState icon={FileText} title="暂无订单" description="你的订单会显示在这里" tone={actualTheme} />
        ) : (
          <div className="space-y-4">
            {items.map((o) => {
              const status = String(o.status || '')
              const canPay = status.toLowerCase() === 'pending'
              const canCancel = status.toLowerCase() === 'pending'
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
                      {canPay ? (
                        <>
                          <Button
                            variant="primary"
                            size="sm"
                            icon={CreditCard}
                            isLoading={balancePayMutation.isPending}
                            onClick={() => handleBalancePay(o.order_no)}
                          >
                            余额支付
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            icon={ExternalLink}
                            isLoading={alipayMutation.isPending}
                            onClick={() => handleAlipayPay(o.order_no)}
                          >
                            支付宝支付
                          </Button>
                        </>
                      ) : null}
                      {canCancel ? (
                        <Button
                          variant="danger"
                          size="sm"
                          icon={XCircle}
                          isLoading={cancelMutation.isPending}
                          onClick={() => handleCancel(o.order_no)}
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

      <Modal
        isOpen={detailOpen}
        onClose={closeDetail}
        title="订单详情"
        description={detailOrderNo ? `订单号：${detailOrderNo}` : undefined}
        size="lg"
      >
        {detailQuery.isLoading ? (
          <Loading text="加载中..." tone={actualTheme} />
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
    </div>
  )
}
