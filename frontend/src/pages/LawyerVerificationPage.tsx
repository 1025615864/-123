import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BadgeCheck, FileText, Shield, User as UserIcon } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { Badge, Button, Card, EmptyState, Input, Loading } from '../components/ui'
import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useAppMutation, useToast } from '../hooks'
import { getApiErrorMessage } from '../utils'

type VerificationStatusResponse = {
  status: string
  verification_id?: number
  created_at?: string
  reviewed_at?: string | null
  reject_reason?: string | null
  message?: string
}

type ApplyResponse = {
  message?: string
  verification_id?: number
}

type ApplyPayload = {
  real_name: string
  id_card_no: string
  license_no: string
  firm_name: string
  specialties?: string | null
  introduction?: string | null
  experience_years: number
}

function statusToBadgeVariant(status: string): 'default' | 'warning' | 'success' | 'danger' | 'info' {
  const s = String(status || '').toLowerCase()
  if (s === 'approved') return 'success'
  if (s === 'rejected') return 'danger'
  if (s === 'pending') return 'warning'
  if (s === 'none') return 'info'
  return 'default'
}

function statusToLabel(status: string): string {
  const s = String(status || '').toLowerCase()
  if (s === 'approved') return '已通过'
  if (s === 'rejected') return '已驳回'
  if (s === 'pending') return '审核中'
  if (s === 'none') return '未申请'
  return status || '未知'
}

export default function LawyerVerificationPage() {
  const { user, isAuthenticated, refreshUser } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()

  const [form, setForm] = useState<ApplyPayload>({
    real_name: '',
    id_card_no: '',
    license_no: '',
    firm_name: '',
    specialties: '',
    introduction: '',
    experience_years: 0,
  })

  const statusQuery = useQuery({
    queryKey: ['lawyer-verification-status'] as const,
    queryFn: async () => {
      const res = await api.get('/lawfirm/verification/status')
      return (res.data || {}) as VerificationStatusResponse
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!statusQuery.error) return
    const code = (statusQuery.error as any)?.response?.status
    if (code === 401) return
    toast.error(getApiErrorMessage(statusQuery.error, '认证状态加载失败'))
  }, [statusQuery.error, toast])

  const applyMutation = useAppMutation<ApplyResponse, ApplyPayload>({
    mutationFn: async (payload) => {
      const res = await api.post('/lawfirm/verification/apply', {
        real_name: payload.real_name,
        id_card_no: payload.id_card_no,
        license_no: payload.license_no,
        firm_name: payload.firm_name,
        specialties: payload.specialties || null,
        introduction: payload.introduction || null,
        experience_years: payload.experience_years,
      })
      return (res.data || {}) as ApplyResponse
    },
    successMessage: '申请已提交，请等待审核',
    errorMessageFallback: '提交失败，请稍后重试',
    onSuccess: async () => {
      await statusQuery.refetch()
    },
  })

  const canApply = useMemo(() => {
    if (!isAuthenticated) return false
    const s = String(statusQuery.data?.status || '').toLowerCase()
    if (s === 'pending' || s === 'approved') return false
    return true
  }, [isAuthenticated, statusQuery.data?.status])

  const handleSubmit = async () => {
    if (!isAuthenticated) {
      toast.error('请先登录')
      return
    }

    if (!form.real_name.trim() || !form.id_card_no.trim() || !form.license_no.trim() || !form.firm_name.trim()) {
      toast.error('请填写必填项')
      return
    }

    if (applyMutation.isPending) return
    applyMutation.mutate({
      real_name: form.real_name.trim(),
      id_card_no: form.id_card_no.trim(),
      license_no: form.license_no.trim(),
      firm_name: form.firm_name.trim(),
      specialties: form.specialties?.trim() || null,
      introduction: form.introduction?.trim() || null,
      experience_years: Number(form.experience_years || 0),
    })
  }

  const roleLabel = user?.role === 'lawyer' ? '律师' : user?.role === 'admin' || user?.role === 'super_admin' ? '管理员' : '用户'

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="律所服务"
          title="律师认证"
          description="登录后可提交律师认证申请"
          layout="mdStart"
          tone={actualTheme}
        />
        <EmptyState icon={Shield} title="请先登录" description="登录后即可提交律师认证申请" tone={actualTheme} />
      </div>
    )
  }

  if (statusQuery.isLoading && !statusQuery.data) {
    return <Loading text="加载中..." tone={actualTheme} />
  }

  const status = String(statusQuery.data?.status || 'none')

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="律所服务"
        title="律师认证"
        description="提交资质信息，审核通过后可进入律师工作台"
        layout="mdStart"
        tone={actualTheme}
        right={
          <Button variant="outline" onClick={async () => {
            await statusQuery.refetch()
            await refreshUser()
          }}>
            刷新
          </Button>
        }
      />

      <Card variant="surface" padding="lg">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant={statusToBadgeVariant(status)} size="sm">
                {statusToLabel(status)}
              </Badge>
              <span className="text-sm text-slate-600 dark:text-white/60">当前身份：{roleLabel}</span>
            </div>
            {statusQuery.data?.reject_reason ? (
              <div className="text-sm text-red-600 dark:text-red-300">驳回原因：{statusQuery.data.reject_reason}</div>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {String(user?.role || '').toLowerCase() === 'lawyer' ? (
              <Badge variant="success" size="sm" icon={BadgeCheck}>
                已是认证律师
              </Badge>
            ) : null}
          </div>
        </div>
      </Card>

      <Card variant="surface" padding="lg">
        <div className="grid gap-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <Input
              label="真实姓名 *"
              icon={UserIcon}
              value={form.real_name}
              onChange={(e) => setForm((p) => ({ ...p, real_name: e.target.value }))}
              placeholder="请输入真实姓名"
              disabled={!canApply || applyMutation.isPending}
            />
            <Input
              label="身份证号 *"
              icon={FileText}
              value={form.id_card_no}
              onChange={(e) => setForm((p) => ({ ...p, id_card_no: e.target.value }))}
              placeholder="请输入身份证号"
              disabled={!canApply || applyMutation.isPending}
            />
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <Input
              label="执业证号 *"
              icon={BadgeCheck}
              value={form.license_no}
              onChange={(e) => setForm((p) => ({ ...p, license_no: e.target.value }))}
              placeholder="请输入执业证号"
              disabled={!canApply || applyMutation.isPending}
            />
            <Input
              label="执业律所名称 *"
              icon={Shield}
              value={form.firm_name}
              onChange={(e) => setForm((p) => ({ ...p, firm_name: e.target.value }))}
              placeholder="请输入律所名称"
              disabled={!canApply || applyMutation.isPending}
            />
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <Input
              label="擅长领域"
              value={String(form.specialties ?? '')}
              onChange={(e) => setForm((p) => ({ ...p, specialties: e.target.value }))}
              placeholder="如：劳动纠纷, 合同纠纷"
              disabled={!canApply || applyMutation.isPending}
            />
            <Input
              label="从业年限"
              type="number"
              value={String(form.experience_years ?? 0)}
              onChange={(e) => setForm((p) => ({ ...p, experience_years: Number(e.target.value || 0) }))}
              placeholder="0"
              disabled={!canApply || applyMutation.isPending}
            />
          </div>

          <Input
            label="个人简介"
            value={String(form.introduction ?? '')}
            onChange={(e) => setForm((p) => ({ ...p, introduction: e.target.value }))}
            placeholder="简要描述您的执业经历、擅长领域等"
            disabled={!canApply || applyMutation.isPending}
          />

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button
              onClick={handleSubmit}
              disabled={!canApply}
              isLoading={applyMutation.isPending}
            >
              提交申请
            </Button>
          </div>

          {!canApply ? (
            <div className="text-xs text-slate-500 dark:text-white/40">
              若你已提交申请或已通过认证，将无法重复提交。
            </div>
          ) : null}
        </div>
      </Card>
    </div>
  )
}
