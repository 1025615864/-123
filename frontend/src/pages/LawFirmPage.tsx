import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MapPin, Phone, Star, Users, Search, Building2, BadgeCheck } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Loading, Card, Input, Badge, EmptyState, Button } from '../components/ui'
import PageHeader from '../components/PageHeader'
import api from '../api/client'
import { usePrefetchLimiter, useToast } from '../hooks'
import { useTheme } from '../contexts/ThemeContext'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'

interface LawFirm {
  id: number
  name: string
  description: string | null
  address: string
  city: string
  province: string
  phone: string | null
  rating: number
  review_count: number
  lawyer_count: number
  is_verified: boolean
}

export default function LawFirmPage() {
  const { actualTheme } = useTheme()
  const toast = useToast()
  const { prefetch } = usePrefetchLimiter()

  const [keyword, setKeyword] = useState('')
  const [city, setCity] = useState('')

  const [submittedKeyword, setSubmittedKeyword] = useState('')
  const [submittedCity, setSubmittedCity] = useState('')

  const firmsQuery = useQuery({
    queryKey: queryKeys.lawFirms(submittedKeyword.trim(), submittedCity.trim()),
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (submittedKeyword.trim()) params.keyword = submittedKeyword.trim()
      if (submittedCity.trim()) params.city = submittedCity.trim()

      const res = await api.get('/lawfirm/firms', { params })
      return (res.data?.items ?? []) as LawFirm[]
    },
    placeholderData: (prev) => prev,
    retry: 1,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (!firmsQuery.error) return
    toast.error(getApiErrorMessage(firmsQuery.error, '律所列表加载失败，请稍后重试'))
  }, [firmsQuery.error, toast])

  const handleSearch = () => {
    setSubmittedKeyword(keyword)
    setSubmittedCity(city)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearch()
    }
  }

  if (firmsQuery.isLoading && (firmsQuery.data ?? []).length === 0) {
    return <Loading text="加载中..." tone={actualTheme} />
  }

  const firms = firmsQuery.data ?? []
  const loadError = firmsQuery.isError ? getApiErrorMessage(firmsQuery.error, '律所列表加载失败，请稍后重试') : null

  const prefetchFirmDetail = (firmId: number) => {
    const id = String(firmId)
    prefetch({
      queryKey: queryKeys.lawFirm(id),
      queryFn: async () => {
        const res = await api.get(`/lawfirm/firms/${id}`)
        return res.data || null
      },
    })
    prefetch({
      queryKey: queryKeys.lawFirmLawyers(id),
      queryFn: async () => {
        const res = await api.get('/lawfirm/lawyers', {
          params: {
            firm_id: id,
            page: 1,
            page_size: 50,
          },
        })
        return (res.data?.items ?? []) as any[]
      },
    })
  }

  return (
    <div className="space-y-12">
      <Card variant="surface" padding="md">
        <PageHeader
          eyebrow="律所查询"
          title="律师事务所"
          description="查找附近律师事务所，预约专业法律咨询"
          layout="mdCenter"
          tone={actualTheme}
          right={
            <div className="w-full md:w-auto">
              <Card variant="surface" padding="sm">
                <div className="flex flex-col sm:flex-row gap-3">
                  <div className="flex-1 min-w-0">
                    <Input
                      icon={Search}
                      type="text"
                      value={keyword}
                      onChange={(e) => setKeyword(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="搜索律所名称或专长领域"
                      className="py-2.5"
                    />
                  </div>
                  <div className="sm:w-44">
                    <Input
                      type="text"
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="城市"
                      className="py-2.5"
                    />
                  </div>
                  <Button onClick={handleSearch} icon={Search} className="px-6 py-2.5">
                    搜索
                  </Button>
                </div>
              </Card>
            </div>
          }
        />
      </Card>

      <div className="grid md:grid-cols-2 gap-8">
        {loadError ? (
          <EmptyState
            icon={Building2}
            title="加载失败"
            description={loadError}
            className="col-span-full"
            tone={actualTheme}
            action={
              <Button onClick={() => firmsQuery.refetch()}>
                重试
              </Button>
            }
          />
        ) : firms.length === 0 ? (
          <EmptyState
            icon={Building2}
            title="暂无律所信息"
            description="试试修改关键词或城市条件"
            className="col-span-full"
            tone={actualTheme}
          />
        ) : (
          firms.map((firm) => (
            <Card
              key={firm.id}
              variant="surface"
              hover
              padding="none"
              className="p-6"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-base md:text-lg font-semibold text-slate-900 truncate dark:text-white">
                      {firm.name}
                    </h3>
                    {firm.is_verified && (
                      <Badge variant="success" size="sm" icon={BadgeCheck} className="rounded-lg">
                        已认证
                      </Badge>
                    )}
                  </div>
                  <p className="text-slate-600 text-sm mt-2 line-clamp-2 leading-relaxed dark:text-white/50">
                    {firm.description || '暂无简介'}
                  </p>
                </div>
              </div>

              <div className="space-y-2 text-sm text-slate-600 mt-5 dark:text-white/70">
                <div className="flex items-start gap-2">
                  <MapPin className="h-4 w-4 text-amber-600 mt-0.5 dark:text-amber-400" />
                  <span className="text-slate-700 dark:text-white/70">
                    {firm.province} {firm.city} {firm.address}
                  </span>
                </div>
                {firm.phone && (
                  <div className="flex items-center gap-2">
                    <Phone className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                    <span className="text-slate-700 dark:text-white/70">{firm.phone}</span>
                  </div>
                )}
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mt-6 pt-5 border-t border-slate-200/70 dark:border-white/10">
                <div className="flex items-center gap-4 flex-wrap">
                  <div className="flex items-center gap-2">
                    <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                      <Star className="h-4 w-4 text-amber-600 fill-amber-600 dark:text-amber-400 dark:fill-amber-400" />
                      <span className="font-semibold text-slate-900 dark:text-white">{firm.rating.toFixed(1)}</span>
                      <span className="text-slate-600 text-sm dark:text-white/50">({firm.review_count}评价)</span>
                    </div>
                  </div>
                  <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-slate-900/5 border border-slate-200/70 text-slate-700 dark:bg-white/5 dark:border-white/10 dark:text-white/70">
                    <Users className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                    <span className="text-sm">{firm.lawyer_count}位律师</span>
                  </div>
                </div>
                <Link
                  to={`/lawfirm/${firm.id}`}
                  onMouseEnter={() => prefetchFirmDetail(firm.id)}
                  onFocus={() => prefetchFirmDetail(firm.id)}
                >
                  <Button className="px-5 py-2.5">查看详情</Button>
                </Link>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  )
 }
