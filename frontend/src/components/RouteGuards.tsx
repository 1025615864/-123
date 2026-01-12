import { type ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { Mail, Phone, Scale, Shield } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'

import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { Button, EmptyState } from './ui'

function buildRedirect(location: { pathname: string; search: string }) {
  return `${location.pathname}${location.search}`
}

function toLoginUrl(redirect: string) {
  return `/login?return_to=${encodeURIComponent(redirect)}`
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  if (isAuthenticated) return <>{children}</>

  const redirect = buildRedirect(location)
  return <Navigate to={toLoginUrl(redirect)} replace />
}

type VerificationStatusResponse = {
  status: string
  reject_reason?: string | null
}

export function RequireLawyer({ children }: { children: ReactNode }) {
  const { isAuthenticated, user } = useAuth()
  const location = useLocation()
  const { actualTheme } = useTheme()

  const redirect = buildRedirect(location)

  const statusQuery = useQuery({
    queryKey: ['lawyer-verification-status'] as const,
    queryFn: async () => {
      const res = await api.get('/lawfirm/verification/status')
      return (res.data || {}) as VerificationStatusResponse
    },
    enabled: isAuthenticated && !!user && String(user.role || '').toLowerCase() !== 'lawyer',
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  if (!isAuthenticated) {
    return <Navigate to={toLoginUrl(redirect)} replace />
  }

  if (!user) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
          <p className="text-slate-600 dark:text-white/50 text-sm">加载中...</p>
        </div>
      </div>
    )
  }

  const role = String(user.role || '').toLowerCase()

  const lawyerCheckQuery = useQuery({
    queryKey: ['lawyer-access-check'] as const,
    queryFn: async () => {
      await api.get('/lawfirm/lawyer/consultations', { params: { page: 1, page_size: 1 } })
      return { ok: true } as const
    },
    enabled: isAuthenticated && !!user && role === 'lawyer',
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  if (role !== 'lawyer') {
    const vStatus = String(statusQuery.data?.status || '').toLowerCase()
    const rejectReason = String(statusQuery.data?.reject_reason || '').trim()

    let title = '需要律师权限'
    let description = '请先完成律师认证并通过审核后再进入律师工作台'

    if (role === 'admin' || role === 'super_admin') {
      title = '管理员不支持使用律师工作台'
      description = '请切换到律师账号登录'
    } else if (vStatus === 'pending') {
      title = '认证审核中'
      description = '你的律师认证申请正在审核，请耐心等待'
    } else if (vStatus === 'rejected') {
      title = '认证已驳回'
      description = rejectReason ? `驳回原因：${rejectReason}` : '请前往认证页面查看原因并重新提交'
    }

    return (
      <EmptyState
        icon={Shield}
        title={title}
        description={description}
        tone={actualTheme}
        action={
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link to={`/lawyer/verification`}>
              <Button icon={Scale}>去律师认证</Button>
            </Link>
            <Link to={`/`}>
              <Button variant="outline">返回首页</Button>
            </Link>
          </div>
        }
      />
    )
  }

  if (user.phone_verified === false) {
    return (
      <EmptyState
        icon={Phone}
        title="请先完成手机号验证"
        description="律师相关功能需要完成手机号验证"
        tone={actualTheme}
        action={
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link to={`/profile?phoneVerify=1`}>
              <Button>去验证手机号</Button>
            </Link>
            <Link to={`/lawyer`}>
              <Button variant="outline">验证后返回工作台</Button>
            </Link>
          </div>
        }
      />
    )
  }

  if (user.email_verified === false) {
    return (
      <EmptyState
        icon={Mail}
        title="请先完成邮箱验证"
        description="律师相关功能需要完成邮箱验证"
        tone={actualTheme}
        action={
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link to={`/profile?emailVerify=1`}>
              <Button>去验证邮箱</Button>
            </Link>
            <Link to={`/lawyer`}>
              <Button variant="outline">验证后返回工作台</Button>
            </Link>
          </div>
        }
      />
    )
  }

  if (role === 'lawyer') {
    const status = (lawyerCheckQuery.error as any)?.response?.status
    const detail = String((lawyerCheckQuery.error as any)?.response?.data?.detail || '')

    if (lawyerCheckQuery.isLoading && !lawyerCheckQuery.data) {
      return (
        <div className="min-h-[50vh] flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <div className="w-10 h-10 border-4 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
            <p className="text-slate-600 dark:text-white/50 text-sm">加载中...</p>
          </div>
        </div>
      )
    }

    if (status === 403) {
      let title = '暂无权限'
      let description = '请先完成律师认证并通过审核'
      if (detail.includes('未绑定律师资料')) {
        title = '律师资料未绑定'
        description = '请先完成律师认证，审核通过后会自动绑定律师资料'
      } else if (detail.includes('律师认证未通过')) {
        title = '律师认证未通过'
        description = '请前往律师认证页面补充资料并等待审核通过'
      }

      return (
        <EmptyState
          icon={Shield}
          title={title}
          description={description}
          tone={actualTheme}
          action={
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link to={`/lawyer/verification`}>
                <Button icon={Scale}>去律师认证</Button>
              </Link>
              <Link to={`/`}>
                <Button variant="outline">返回首页</Button>
              </Link>
            </div>
          }
        />
      )
    }
  }

  return <>{children}</>
}
