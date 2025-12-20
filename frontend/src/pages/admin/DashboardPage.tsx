import { useEffect, useMemo } from 'react'
import { Users, Newspaper, MessageSquare, Building2, TrendingUp, Eye, Activity, BarChart3, PieChart } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Card, Button, Loading, EmptyState } from '../../components/ui'
import api from '../../api/client'
import { useToast } from '../../hooks'
import { useTheme } from '../../contexts/ThemeContext'
import { getApiErrorMessage } from '../../utils'
import { queryKeys } from '../../queryKeys'

interface Stats {
  users: number
  news: number
  posts: number
  lawfirms: number
  consultations?: number
  comments?: number
}

interface WeeklyData {
  day: string
  posts: number
  users: number
  consultations: number
}

interface CategoryData {
  category: string
  count: number
  color: string
}

interface ActivityItem {
  text: string
  time: string
}

interface HotContentItem {
  title: string
  views: number
}

// 简单柱状图组件
function SimpleBarChart({ data, maxValue }: { data: WeeklyData[], maxValue: number }) {
  return (
    <div className="flex items-end justify-between gap-2 h-40">
      {data.map((item, idx) => (
        <div key={idx} className="flex-1 flex flex-col items-center gap-2">
          <div className="w-full flex flex-col gap-1" style={{ height: '120px' }}>
            <div 
              className="w-full bg-gradient-to-t from-blue-500 to-blue-400 rounded-t transition-all"
              style={{ height: `${(item.posts / maxValue) * 100}%` }}
              title={`帖子: ${item.posts}`}
            />
          </div>
          <span className="text-xs text-slate-500 dark:text-white/50">{item.day}</span>
        </div>
      ))}
    </div>
  )
}

// 简单环形图组件
function SimplePieChart({ data }: { data: CategoryData[] }) {
  const total = data.reduce((sum, d) => sum + d.count, 0)
  let currentAngle = 0
  
  return (
    <div className="flex items-center gap-6">
      <div className="relative w-32 h-32">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90 text-white dark:text-slate-800">
          {data.map((item, idx) => {
            const angle = (item.count / total) * 360
            const startAngle = currentAngle
            currentAngle += angle
            
            const x1 = 50 + 40 * Math.cos((startAngle * Math.PI) / 180)
            const y1 = 50 + 40 * Math.sin((startAngle * Math.PI) / 180)
            const x2 = 50 + 40 * Math.cos(((startAngle + angle) * Math.PI) / 180)
            const y2 = 50 + 40 * Math.sin(((startAngle + angle) * Math.PI) / 180)
            const largeArc = angle > 180 ? 1 : 0
            
            return (
              <path
                key={idx}
                d={`M 50 50 L ${x1} ${y1} A 40 40 0 ${largeArc} 1 ${x2} ${y2} Z`}
                fill={item.color}
                className="opacity-80 hover:opacity-100 transition-opacity cursor-pointer"
              />
            )
          })}
          <circle cx="50" cy="50" r="25" fill="currentColor" />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold text-slate-900 dark:text-white">{total}</span>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {data.map((item, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
            <span className="text-sm text-slate-700 dark:text-white/70">{item.category}</span>
            <span className="text-sm text-slate-500 dark:text-white/40">({item.count})</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { actualTheme } = useTheme()
  const toast = useToast()

  const weekdayLabels = useMemo(() => ['周日', '周一', '周二', '周三', '周四', '周五', '周六'], [])
  const palette = useMemo(() => ['#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#ef4444', '#06b6d4', '#6b7280'], [])

  const toRelativeTime = (iso: string) => {
    const t = new Date(iso).getTime()
    if (Number.isNaN(t)) return ''
    const diffMs = Date.now() - t
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin}分钟前`
    const diffHour = Math.floor(diffMin / 60)
    if (diffHour < 24) return `${diffHour}小时前`
    const diffDay = Math.floor(diffHour / 24)
    return `${diffDay}天前`
  }

  const statsQuery = useQuery({
    queryKey: queryKeys.adminDashboardStats(),
    queryFn: async () => {
      const res = await api.get('/admin/stats')
      return res.data as Stats
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const trendsQuery = useQuery({
    queryKey: queryKeys.adminDashboardTrends(7),
    queryFn: async () => {
      const res = await api.get('/system/dashboard/trends', { params: { days: 7 } })
      const trends = Array.isArray(res.data?.trends) ? res.data.trends : []
      return (trends as any[]).map((t) => {
        const d = new Date(t.date)
        return {
          day: weekdayLabels[d.getDay()] || t.date,
          posts: Number(t.posts || 0),
          users: Number(t.users || 0),
          consultations: Number(t.consultations || 0),
        } as WeeklyData
      })
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const categoryQuery = useQuery({
    queryKey: queryKeys.adminDashboardCategoryStats(),
    queryFn: async () => {
      const res = await api.get('/system/dashboard/category-stats')
      const postCategories = Array.isArray(res.data?.post_categories) ? res.data.post_categories : []
      return (postCategories as any[]).slice(0, 7).map((c, idx) => ({
        category: String(c.name || ''),
        count: Number(c.value || 0),
        color: palette[idx % palette.length],
      })) as CategoryData[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const activityQuery = useQuery({
    queryKey: queryKeys.adminDashboardRealtime(),
    queryFn: async () => {
      const res = await api.get('/system/dashboard/realtime')
      const recent = Array.isArray(res.data?.recent_consultations) ? res.data.recent_consultations : []
      return (recent as any[]).map((r) => ({
        text: `${String(r.user || '用户')} 发起咨询：${String(r.title || 'AI法律咨询')}`,
        time: toRelativeTime(String(r.time || '')),
      })) as ActivityItem[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const hotQuery = useQuery({
    queryKey: queryKeys.adminDashboardHot(4),
    queryFn: async () => {
      const res = await api.get('/system/dashboard/hot-content', { params: { limit: 4 } })
      const items = Array.isArray(res.data?.items) ? res.data.items : []
      return (items as any[]).map((it) => ({
        title: String(it.title || ''),
        views: Number(it.views || 0),
      })) as HotContentItem[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const stats = statsQuery.data ?? { users: 0, news: 0, posts: 0, lawfirms: 0 }
  const weeklyData = trendsQuery.data ?? []
  const categoryData = categoryQuery.data ?? []
  const recentActivities = activityQuery.data ?? []
  const hotContent = hotQuery.data ?? []

  const statsLoading = statsQuery.isLoading
  const statsError = statsQuery.isError ? getApiErrorMessage(statsQuery.error, '统计数据加载失败') : null

  const weeklyLoading = trendsQuery.isLoading
  const weeklyError = trendsQuery.isError ? getApiErrorMessage(trendsQuery.error, '趋势数据加载失败') : null

  const categoryLoading = categoryQuery.isLoading
  const categoryError = categoryQuery.isError ? getApiErrorMessage(categoryQuery.error, '分类数据加载失败') : null

  const activityLoading = activityQuery.isLoading
  const activityError = activityQuery.isError ? getApiErrorMessage(activityQuery.error, '最近活动加载失败') : null

  const hotLoading = hotQuery.isLoading
  const hotError = hotQuery.isError ? getApiErrorMessage(hotQuery.error, '热门内容加载失败') : null

  // 统一错误 toast（不影响原有错误区域展示）
  useEffect(() => {
    const err = statsQuery.error || trendsQuery.error || categoryQuery.error || activityQuery.error || hotQuery.error
    if (!err) return
    toast.error(getApiErrorMessage(err))
  }, [activityQuery.error, categoryQuery.error, hotQuery.error, statsQuery.error, toast, trendsQuery.error])

  const statCards = [
    { icon: Users, label: '注册用户', value: stats.users, color: 'from-blue-500 to-cyan-500', change: '+12%' },
    { icon: Newspaper, label: '新闻文章', value: stats.news, color: 'from-amber-500 to-orange-500', change: '+5%' },
    { icon: MessageSquare, label: '论坛帖子', value: stats.posts, color: 'from-purple-500 to-pink-500', change: '+23%' },
    { icon: Building2, label: '入驻律所', value: stats.lawfirms, color: 'from-emerald-500 to-teal-500', change: '+8%' },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">仪表盘</h1>
        <p className="text-slate-600 mt-1 dark:text-white/50">欢迎回来，这是系统的整体概览</p>
      </div>

      {/* 统计卡片 */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map(({ icon: Icon, label, value, color, change }) => (
          <Card key={label} variant="surface" padding="lg" className="relative overflow-hidden">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-slate-600 text-sm dark:text-white/50">{label}</p>
                <p className="text-3xl font-bold text-slate-900 mt-2 dark:text-white">{value.toLocaleString()}</p>
                <p className="text-emerald-600 text-sm mt-2 flex items-center gap-1 dark:text-emerald-400">
                  <TrendingUp className="h-4 w-4" />
                  {change} 较上月
                </p>
              </div>
              <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center`}>
                <Icon className="h-6 w-6 text-white" />
              </div>
            </div>
          </Card>
        ))}
      </div>

      {statsLoading ? (
        <Loading text="加载统计中..." tone={actualTheme} />
      ) : statsError ? (
        <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
          <div>{statsError}</div>
          <Button variant="outline" onClick={() => statsQuery.refetch()}>重试</Button>
        </div>
      ) : null}

      {/* 数据可视化图表 */}
      <div className="grid lg:grid-cols-2 gap-6">
        <Card variant="surface" padding="lg">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2 dark:text-white">
              <BarChart3 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              本周发帖趋势
            </h3>
            <span className="text-xs text-slate-500 dark:text-white/40">最近7天</span>
          </div>
          {weeklyLoading ? (
            <Loading text="加载中..." tone={actualTheme} />
          ) : weeklyError ? (
            <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
              <div>{weeklyError}</div>
              <Button variant="outline" onClick={() => trendsQuery.refetch()}>重试</Button>
            </div>
          ) : weeklyData.length === 0 ? (
            <EmptyState
              icon={BarChart3}
              title="暂无趋势数据"
              description="稍后再试或检查数据来源"
              tone={actualTheme}
            />
          ) : (
            <SimpleBarChart
              data={weeklyData}
              maxValue={Math.max(1, ...weeklyData.map((d) => d.posts))}
            />
          )}
        </Card>

        <Card variant="surface" padding="lg">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2 dark:text-white">
              <PieChart className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              帖子分类分布
            </h3>
          </div>
          {categoryLoading ? (
            <Loading text="加载中..." tone={actualTheme} />
          ) : categoryError ? (
            <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
              <div>{categoryError}</div>
              <Button variant="outline" onClick={() => categoryQuery.refetch()}>重试</Button>
            </div>
          ) : categoryData.length === 0 ? (
            <EmptyState
              icon={PieChart}
              title="暂无分类数据"
              description="稍后再试或检查数据来源"
              tone={actualTheme}
            />
          ) : (
            <SimplePieChart data={categoryData} />
          )}
        </Card>
      </div>

      {/* 快捷操作 */}
      <div className="grid lg:grid-cols-2 gap-6">
        <Card variant="surface" padding="lg">
          <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2 dark:text-white">
            <Activity className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            最近活动
          </h3>
          {activityLoading ? (
            <Loading text="加载中..." tone={actualTheme} />
          ) : activityError ? (
            <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
              <div>{activityError}</div>
              <Button variant="outline" onClick={() => activityQuery.refetch()}>重试</Button>
            </div>
          ) : recentActivities.length === 0 ? (
            <EmptyState
              icon={Activity}
              title="暂无活动"
              description="系统还没有记录到最近活动"
              tone={actualTheme}
            />
          ) : (
            <div className="space-y-4">
              {recentActivities.map((activity, index) => (
                <div key={index} className="flex items-center justify-between py-2 border-b border-slate-200/70 last:border-0 dark:border-white/5">
                  <span className="text-slate-700 text-sm dark:text-white/70">{activity.text}</span>
                  <span className="text-slate-500 text-xs dark:text-white/40">{activity.time}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card variant="surface" padding="lg">
          <h3 className="text-lg font-semibold text-slate-900 mb-4 dark:text-white">热门内容</h3>
          {hotLoading ? (
            <Loading text="加载中..." tone={actualTheme} />
          ) : hotError ? (
            <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
              <div>{hotError}</div>
              <Button variant="outline" onClick={() => hotQuery.refetch()}>重试</Button>
            </div>
          ) : hotContent.length === 0 ? (
            <EmptyState
              icon={Eye}
              title="暂无热门内容"
              description="暂时没有统计到热门内容"
              tone={actualTheme}
            />
          ) : (
            <div className="space-y-4">
              {hotContent.map((item, index) => (
                <div key={index} className="flex items-center justify-between py-2 border-b border-slate-200/70 last:border-0 dark:border-white/5">
                  <span className="text-slate-700 text-sm truncate flex-1 dark:text-white/70">{item.title}</span>
                  <span className="text-slate-500 text-xs flex items-center gap-1 ml-4 dark:text-white/40">
                    <Eye className="h-3 w-3" />
                    {item.views.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
