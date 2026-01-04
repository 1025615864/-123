import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, MapPin, Phone, Mail, Star, Users, BadgeCheck } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Card, Button, Loading, Badge, EmptyState } from '../components/ui'
// import { useAuth } from '../contexts/AuthContext'
import api from '../api/client'
import { useToast } from '../hooks'
import { useTheme } from '../contexts/ThemeContext'
import LawyerBookingModal from '../components/LawyerBookingModal'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'

interface LawFirmDetail {
  id: number
  name: string
  description: string | null
  address: string
  city: string
  province: string
  phone: string | null
  email: string | null
  website: string | null
  rating: number
  review_count: number
  lawyer_count: number
  is_verified: boolean
  specialties: string[]
  created_at: string
}

interface LawyerItem {
  id: number
  name: string
  title?: string | null
  specialties?: string | null
  consultation_fee?: number | null
  rating?: number
  review_count?: number
}

 export default function LawFirmDetailPage() {
  const { firmId } = useParams<{ firmId: string }>()
  // const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()
  
  const [bookingLawyer, setBookingLawyer] = useState<LawyerItem | null>(null)

  const firmQuery = useQuery({
    queryKey: queryKeys.lawFirm(firmId),
    queryFn: async () => {
      const res = await api.get(`/lawfirm/firms/${firmId}`)
      return (res.data || null) as LawFirmDetail | null
    },
    enabled: !!firmId,
    retry: 1,
    refetchOnWindowFocus: false,
  })

  const lawyersQuery = useQuery({
    queryKey: queryKeys.lawFirmLawyers(firmId),
    queryFn: async () => {
      const res = await api.get('/lawfirm/lawyers', {
        params: {
          firm_id: firmId,
          page: 1,
          page_size: 50,
        },
      })
      return (res.data?.items ?? []) as LawyerItem[]
    },
    enabled: !!firmId,
    placeholderData: (prev) => prev,
    retry: 1,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (!firmQuery.error) return
    toast.error(getApiErrorMessage(firmQuery.error, '律所信息加载失败，请稍后重试'))
  }, [firmQuery.error, toast])

  useEffect(() => {
    if (!lawyersQuery.error) return
    toast.error(getApiErrorMessage(lawyersQuery.error, '律师列表加载失败，请稍后重试'))
  }, [lawyersQuery.error, toast])

  if (firmQuery.isLoading) {
    return <Loading text="加载中..." tone={actualTheme} />
  }

  const firm = firmQuery.data ?? null
  const loadError = firmQuery.isError ? getApiErrorMessage(firmQuery.error, '律所信息加载失败，请稍后重试') : null

  if (!firm) {
    return (
      <EmptyState
        icon={Users}
        title={loadError ? '加载失败' : '律所不存在或已被删除'}
        description={loadError || '请返回列表重新选择，或稍后再试'}
        tone={actualTheme}
        action={
          <div className="flex flex-col sm:flex-row gap-3">
            <Link to="/lawfirm">
              <Button variant="outline">返回律所列表</Button>
            </Link>
            {loadError && (
              <Button onClick={() => {
                firmQuery.refetch()
                lawyersQuery.refetch()
              }}>
                重试
              </Button>
            )}
          </div>
        }
      />
    )
  }

  return (
    <div className="space-y-8">
      {/* 返回按钮 */}
      <Link 
        to="/lawfirm" 
        className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors dark:text-white/60 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        返回律所列表
      </Link>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* 左侧：律所信息 */}
        <div className="lg:col-span-2 space-y-6">
          <Card variant="surface" padding="lg">
            <div className="flex items-start justify-between gap-4 mb-6">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{firm.name}</h1>
                  {firm.is_verified && (
                    <Badge variant="success" size="sm" icon={BadgeCheck}>
                      已认证
                    </Badge>
                  )}
                </div>
                <p className="text-slate-600 dark:text-white/50">{firm.province} · {firm.city}</p>
              </div>
              <div className="text-right">
                <div className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                  <Star className="h-5 w-5 fill-amber-600 dark:fill-amber-400" />
                  <span className="text-xl font-semibold">{firm.rating.toFixed(1)}</span>
                </div>
                <p className="text-slate-500 text-sm dark:text-white/40">{firm.review_count} 条评价</p>
              </div>
            </div>

            {/* 标签 */}
            {firm.specialties && firm.specialties.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-6">
                {firm.specialties.map((specialty, index) => (
                  <Badge key={index} variant="info" size="sm">
                    {specialty}
                  </Badge>
                ))}
              </div>
            )}

            {/* 描述 */}
            {firm.description && (
              <div className="mb-6">
                <h3 className="text-lg font-medium text-slate-900 mb-3 dark:text-white">律所简介</h3>
                <p className="text-slate-700 leading-relaxed dark:text-white/70">{firm.description}</p>
              </div>
            )}

            {/* 联系信息 */}
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                <MapPin className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                <div>
                  <p className="text-slate-500 text-sm dark:text-white/40">地址</p>
                  <p className="text-slate-900 dark:text-white">{firm.address}</p>
                </div>
              </div>
              {firm.phone && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                  <Phone className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  <div>
                    <p className="text-slate-500 text-sm dark:text-white/40">电话</p>
                    <p className="text-slate-900 dark:text-white">{firm.phone}</p>
                  </div>
                </div>
              )}
              {firm.email && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                  <Mail className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  <div>
                    <p className="text-slate-500 text-sm dark:text-white/40">邮箱</p>
                    <p className="text-slate-900 dark:text-white">{firm.email}</p>
                  </div>
                </div>
              )}
              <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                <Users className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                <div>
                  <p className="text-slate-500 text-sm dark:text-white/40">律师团队</p>
                  <p className="text-slate-900 dark:text-white">{firm.lawyer_count} 位律师</p>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* 右侧：预约咨询 */}
        <div className="lg:col-span-1">
          <Card variant="surface" padding="lg" className="sticky top-24">
            <h3 className="text-lg font-semibold text-slate-900 mb-4 dark:text-white">律师团队</h3>

            {lawyersQuery.isLoading ? (
              <div className="text-slate-500 text-sm dark:text-white/50">加载中...</div>
            ) : lawyersQuery.isError ? (
              <div className="space-y-4">
                <p className="text-slate-600 text-sm dark:text-white/60">{getApiErrorMessage(lawyersQuery.error, '律师列表加载失败，请稍后重试')}</p>
                <Button
                  variant="outline"
                  onClick={() => {
                    lawyersQuery.refetch()
                  }}
                >
                  重试
                </Button>
              </div>
            ) : (lawyersQuery.data ?? []).length === 0 ? (
              <div className="space-y-4">
                <p className="text-slate-600 text-sm dark:text-white/50">暂无可预约律师</p>
                {firm.phone && (
                  <a href={`tel:${firm.phone}`} className="block">
                    <Button variant="outline" icon={Phone} className="w-full">
                      电话咨询
                    </Button>
                  </a>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {(lawyersQuery.data ?? []).slice(0, 8).map((lawyer) => (
                  <div key={lawyer.id} className="p-3 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-slate-900 font-medium truncate dark:text-white">{lawyer.name}</p>
                        <p className="text-slate-600 text-sm truncate dark:text-white/50">
                          {lawyer.title || '律师'}
                        </p>
                        {lawyer.specialties && (
                          <p className="text-slate-500 text-xs mt-1 truncate dark:text-white/40">{lawyer.specialties}</p>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span className="text-amber-600 text-sm dark:text-amber-400">
                          {typeof lawyer.consultation_fee === 'number' && lawyer.consultation_fee > 0
                            ? `¥${lawyer.consultation_fee}/次`
                            : '免费'}
                        </span>
                        <Link to={`/lawfirm/lawyers/${lawyer.id}`} className="block">
                          <Button variant="outline" size="sm" className="px-4">
                            详情
                          </Button>
                        </Link>
                        <Button
                          size="sm"
                          onClick={() => setBookingLawyer(lawyer)}
                          className="px-4"
                        >
                          预约
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}

                {firm.phone && (
                  <a href={`tel:${firm.phone}`} className="block pt-2">
                    <Button variant="outline" icon={Phone} className="w-full">
                      电话咨询
                    </Button>
                  </a>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>

      {bookingLawyer && (
        <LawyerBookingModal
          lawyer={{
            id: bookingLawyer.id,
            name: bookingLawyer.name,
            title: bookingLawyer.title || undefined,
            specialties: bookingLawyer.specialties || undefined,
            consultation_fee: bookingLawyer.consultation_fee || undefined,
          }}
          onClose={() => setBookingLawyer(null)}
          onSuccess={() => toast.success('预约已提交')}
        />
      )}
    </div>
  )
}
