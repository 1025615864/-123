import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle, Clock, Shield, XCircle } from 'lucide-react'
import { Card, Button, Badge, Loading, Input, Modal } from '../../components/ui'
import api from '../../api/client'
import { useTheme } from '../../contexts/ThemeContext'
import { useAppMutation, useToast } from '../../hooks'
import { getApiErrorMessage } from '../../utils'

type VerificationItem = {
  id: number
  user_id: number
  username: string | null
  real_name: string
  id_card_no: string
  license_no: string
  firm_name: string
  specialties: string | null
  experience_years: number
  status: string
  created_at: string
  reviewed_at: string | null
}

type VerificationListResponse = {
  items: VerificationItem[]
  total: number
}

type ReviewPayload = {
  approved: boolean
  reject_reason?: string | null
}

function statusToBadgeVariant(status: string): 'default' | 'warning' | 'success' | 'danger' | 'info' {
  const s = String(status || '').toLowerCase()
  if (s === 'approved') return 'success'
  if (s === 'rejected') return 'danger'
  if (s === 'pending') return 'warning'
  return 'default'
}

function statusToLabel(status: string): string {
  const s = String(status || '').toLowerCase()
  if (s === 'approved') return '已通过'
  if (s === 'rejected') return '已驳回'
  if (s === 'pending') return '待审核'
  return status || '未知'
}

export default function LawyerVerificationsPage() {
  const { actualTheme } = useTheme()
  const toast = useToast()

  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const queryKey = useMemo(
    () => ['admin-lawyer-verifications', { statusFilter, keyword: keyword.trim(), page, pageSize }] as const,
    [keyword, page, pageSize, statusFilter]
  )

  const listQuery = useQuery({
    queryKey,
    queryFn: async () => {
      const res = await api.get('/lawfirm/admin/verifications', {
        params: {
          page,
          page_size: pageSize,
          ...(statusFilter ? { status_filter: statusFilter } : {}),
        },
      })
      const data = res.data || {}
      return {
        items: Array.isArray(data?.items) ? (data.items as VerificationItem[]) : ([] as VerificationItem[]),
        total: Number(data?.total || 0),
      } satisfies VerificationListResponse
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!listQuery.error) return
    toast.error(getApiErrorMessage(listQuery.error, '加载失败，请稍后重试'))
  }, [listQuery.error, toast])

  const [reviewOpen, setReviewOpen] = useState(false)
  const [reviewTarget, setReviewTarget] = useState<VerificationItem | null>(null)
  const [rejectReason, setRejectReason] = useState('')

  const reviewMutation = useAppMutation<unknown, { id: number; payload: ReviewPayload }>({
    mutationFn: async ({ id, payload }) => {
      await api.post(`/lawfirm/admin/verifications/${id}/review`, payload)
    },
    errorMessageFallback: '操作失败，请稍后重试',
    onSuccess: async () => {
      toast.success('已处理')
      setReviewOpen(false)
      setReviewTarget(null)
      setRejectReason('')
      await listQuery.refetch()
    },
  })

  const items = listQuery.data?.items ?? []
  const total = listQuery.data?.total ?? 0
  const filtered = useMemo(() => {
    const q = keyword.trim().toLowerCase()
    if (!q) return items
    return items.filter((it) => {
      return (
        String(it.username || '').toLowerCase().includes(q) ||
        String(it.real_name || '').toLowerCase().includes(q) ||
        String(it.firm_name || '').toLowerCase().includes(q) ||
        String(it.license_no || '').toLowerCase().includes(q)
      )
    })
  }, [items, keyword])

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total])

  const openApprove = (it: VerificationItem) => {
    setReviewTarget(it)
    setRejectReason('')
    setReviewOpen(true)
  }

  const submitApprove = () => {
    if (!reviewTarget) return
    if (!confirm('确定通过该认证申请吗？')) return
    reviewMutation.mutate({ id: reviewTarget.id, payload: { approved: true } })
  }

  const submitReject = () => {
    if (!reviewTarget) return
    if (!confirm('确定驳回该认证申请吗？')) return
    reviewMutation.mutate({ id: reviewTarget.id, payload: { approved: false, reject_reason: rejectReason.trim() || null } })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">律师认证审核</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">审核用户提交的律师认证申请</p>
        </div>
        <Button variant="outline" onClick={() => listQuery.refetch()} disabled={listQuery.isFetching}>
          刷新
        </Button>
      </div>

      <Card variant="surface" padding="md">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={statusFilter === 'pending' ? 'primary' : 'outline'}
              onClick={() => {
                setPage(1)
                setStatusFilter('pending')
              }}
              icon={Clock}
            >
              待审核
            </Button>
            <Button
              size="sm"
              variant={statusFilter === 'approved' ? 'primary' : 'outline'}
              onClick={() => {
                setPage(1)
                setStatusFilter('approved')
              }}
              icon={CheckCircle}
            >
              已通过
            </Button>
            <Button
              size="sm"
              variant={statusFilter === 'rejected' ? 'primary' : 'outline'}
              onClick={() => {
                setPage(1)
                setStatusFilter('rejected')
              }}
              icon={XCircle}
            >
              已驳回
            </Button>
          </div>

          <div className="w-full md:max-w-sm">
            <Input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜索用户名/姓名/律所/证号..." />
          </div>
        </div>
      </Card>

      <Card variant="surface" padding="lg">
        {listQuery.isLoading ? (
          <Loading text="加载中..." tone={actualTheme} />
        ) : (
          <div className="space-y-4">
            {filtered.length === 0 ? (
              <div className="text-center py-12 text-slate-500 dark:text-white/40">暂无数据</div>
            ) : (
              filtered.map((it) => {
                const canReview = String(it.status || '').toLowerCase() === 'pending'
                return (
                  <Card key={it.id} variant="surface" padding="md" className="border border-slate-200/70 dark:border-white/10">
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-slate-900 dark:text-white">{it.real_name}</span>
                          <Badge variant={statusToBadgeVariant(it.status)} size="sm">
                            {statusToLabel(it.status)}
                          </Badge>
                          <span className="text-sm text-slate-600 dark:text-white/60">用户：{it.username || `#${it.user_id}`}</span>
                        </div>
                        <div className="mt-2 space-y-1 text-sm text-slate-600 dark:text-white/60">
                          <div>律所：{it.firm_name}</div>
                          <div>执业证号：{it.license_no}</div>
                          <div>身份证：{it.id_card_no}</div>
                          <div>擅长：{it.specialties || '—'} / 年限：{it.experience_years}</div>
                          <div>提交时间：{new Date(it.created_at).toLocaleString()}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 md:flex-col md:items-end">
                        {canReview ? (
                          <>
                            <Button size="sm" icon={Shield} onClick={() => openApprove(it)}>
                              审核
                            </Button>
                          </>
                        ) : null}
                      </div>
                    </div>
                  </Card>
                )
              })
            )}

            <div className="pt-2 flex items-center justify-between text-sm text-slate-500 dark:text-white/40">
              <div>
                总数：{total}，页码：{page}/{totalPages}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  上一页
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  下一页
                </Button>
              </div>
            </div>
          </div>
        )}
      </Card>

      <Modal
        isOpen={reviewOpen}
        onClose={() => {
          setReviewOpen(false)
          setReviewTarget(null)
          setRejectReason('')
        }}
        title="审核认证申请"
        description={reviewTarget ? `${reviewTarget.real_name}（${reviewTarget.username || reviewTarget.user_id}）` : undefined}
        size="lg"
      >
        {reviewTarget ? (
          <div className="space-y-4">
            <Card variant="surface" padding="md" className="border border-slate-200/70 dark:border-white/10">
              <div className="space-y-1 text-sm text-slate-700 dark:text-white/70">
                <div>律所：{reviewTarget.firm_name}</div>
                <div>执业证号：{reviewTarget.license_no}</div>
                <div>身份证：{reviewTarget.id_card_no}</div>
                <div>擅长：{reviewTarget.specialties || '—'} / 年限：{reviewTarget.experience_years}</div>
              </div>
            </Card>

            <Input
              label="驳回原因（可选）"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="填写驳回原因（如资料不全/证号不一致等）"
              disabled={reviewMutation.isPending}
            />

            <div className="flex items-center justify-end gap-3">
              <Button
                variant="danger"
                icon={XCircle}
                isLoading={reviewMutation.isPending}
                onClick={submitReject}
              >
                驳回
              </Button>
              <Button
                variant="primary"
                icon={CheckCircle}
                isLoading={reviewMutation.isPending}
                onClick={submitApprove}
              >
                通过
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
