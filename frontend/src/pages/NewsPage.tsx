import { useMemo, useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, Eye, Tag, Search, Newspaper } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Card, Input, Chip, Badge, EmptyState, Pagination, NewsCardSkeleton, FadeInImage } from '../components/ui'
import PageHeader from '../components/PageHeader'
import api from '../api/client'
import { usePrefetchLimiter, useToast } from '../hooks'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'

interface CategoryCount {
  category: string
  count: number
}

interface NewsListItem {
  id: number
  title: string
  summary: string | null
  category: string
  cover_image: string | null
  source: string | null
  author: string | null
  view_count: number
  favorite_count: number
  is_favorited: boolean
  is_top: boolean
  published_at: string | null
  created_at: string
}

interface NewsListResponse {
  items: NewsListItem[]
  total: number
  page: number
  page_size: number
}

export default function NewsPage() {
  const { actualTheme } = useTheme()
  const { isAuthenticated } = useAuth()
  const toast = useToast()
  const { prefetch } = usePrefetchLimiter()

  const [page, setPage] = useState(1)
  const pageSize = 18
  const [category, setCategory] = useState<string | null>(null)
  const [keyword, setKeyword] = useState('')
  const [mode, setMode] = useState<'all' | 'favorites' | 'history'>('all')

  const [debouncedKeyword, setDebouncedKeyword] = useState('')

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedKeyword(keyword), 250)
    return () => window.clearTimeout(t)
  }, [keyword])

  useEffect(() => {
    setPage(1)
  }, [category, keyword, mode])

  const categoriesQuery = useQuery({
    queryKey: queryKeys.newsCategories(),
    queryFn: async () => {
      try {
        const res = await api.get('/news/categories')
        return (Array.isArray(res.data) ? res.data : []) as CategoryCount[]
      } catch {
        return [] as CategoryCount[]
      }
    },
    staleTime: 30 * 60 * 1000,
  })

  const newsQuery = useQuery({
    queryKey:
      mode === 'favorites'
        ? queryKeys.newsFavoritesList(page, pageSize, category, debouncedKeyword.trim())
        : mode === 'history'
          ? queryKeys.newsHistoryList(page, pageSize, category, debouncedKeyword.trim())
          : queryKeys.newsList(page, pageSize, category, debouncedKeyword.trim()),
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('page', String(page))
      params.set('page_size', String(pageSize))
      if (category) params.set('category', category)
      if (debouncedKeyword.trim()) params.set('keyword', debouncedKeyword.trim())

      const endpoint = mode === 'favorites' ? '/news/favorites' : mode === 'history' ? '/news/history' : '/news'
      const res = await api.get(`${endpoint}?${params.toString()}`)
      return res.data as NewsListResponse
    },
    enabled: mode === 'all' ? true : isAuthenticated,
    placeholderData: (prev) => prev,
    retry: 1,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (!newsQuery.error) return
    toast.error(getApiErrorMessage(newsQuery.error))
  }, [newsQuery.error, toast])

  const displayCategories = useMemo(() => {
    const fromApi = (categoriesQuery.data ?? []).map((c) => c.category).filter(Boolean)
    const unique = Array.from(new Set(fromApi))
    return ['全部', ...unique]
  }, [categoriesQuery.data])

  const news = newsQuery.data?.items ?? []
  const total = newsQuery.data?.total ?? 0

  if (newsQuery.isLoading && news.length === 0) {
    return (
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
        {Array.from({ length: 6 }).map((_, i) => (
          <NewsCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const prefetchNewsDetail = (id: number) => {
    const newsId = String(id)
    prefetch({
      queryKey: queryKeys.newsDetail(newsId),
      queryFn: async () => {
        const res = await api.get(`/news/${newsId}`)
        return res.data
      },
    })
  }

  return (
    <div className="space-y-12">
      <Card variant="surface" padding="md">
        <PageHeader
          eyebrow="法律资讯"
          title="法律新闻"
          description="最新法律资讯、政策解读和案例分析"
          layout="mdCenter"
          tone={actualTheme}
          right={
            <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
              <div className="w-full md:w-80">
                <Input
                  icon={Search}
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="搜索标题或摘要"
                  className="py-2.5"
                />
              </div>
            </div>
          }
        />

        <div className="mt-5 flex flex-wrap gap-2">
          {isAuthenticated ? (
            <Chip
              key="__favorites"
              size="sm"
              active={mode === 'favorites'}
              onClick={() => setMode((prev) => (prev === 'favorites' ? 'all' : 'favorites'))}
            >
              我的收藏
            </Chip>
          ) : null}
          {isAuthenticated ? (
            <Chip
              key="__history"
              size="sm"
              active={mode === 'history'}
              onClick={() => setMode((prev) => (prev === 'history' ? 'all' : 'history'))}
            >
              最近浏览
            </Chip>
          ) : null}
          {displayCategories.map((cat) => {
            const active = (cat === '全部' && !category) || cat === category
            return (
              <Chip
                key={cat}
                size="sm"
                active={active}
                onClick={() => setCategory(cat === '全部' ? null : cat)}
              >
                {cat}
              </Chip>
            )
          })}
        </div>
      </Card>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
        {news.length === 0 ? (
          <EmptyState
            icon={Newspaper}
            title="暂无符合条件的新闻"
            description="试试切换分类或修改搜索关键词"
            className="col-span-full"
          />
        ) : (
          news.map((item, index) => (
            <Link
              key={item.id}
              to={`/news/${item.id}`}
              onMouseEnter={() => prefetchNewsDetail(item.id)}
              onFocus={() => prefetchNewsDetail(item.id)}
              className="block opacity-0 animate-fade-in"
              style={{ animationDelay: `${Math.min(18, Math.max(0, index % 18)) * 35}ms` }}
            >
              <Card
                variant="surface"
                hover
                padding="none"
                className="overflow-hidden"
              >
              <div className="aspect-[16/10] bg-slate-900/5 relative dark:bg-white/[0.03]">
                {item.cover_image ? (
                  <FadeInImage
                    src={item.cover_image}
                    alt={item.title}
                    wrapperClassName="w-full h-full"
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Newspaper className="h-10 w-10 text-slate-400 dark:text-white/30" />
                  </div>
                )}
              </div>

              <div className="p-5">
                <div className="flex items-center gap-2 mb-3">
                  <Badge variant="primary" size="sm" icon={Tag}>
                    {item.category}
                  </Badge>
                  {item.is_top ? <Badge variant="warning" size="sm">置顶</Badge> : null}
                </div>

                <h3 className="text-base font-semibold text-slate-900 mb-2 line-clamp-2 leading-snug dark:text-white">{item.title}</h3>
                <p className="text-slate-600 text-sm line-clamp-3 leading-relaxed dark:text-white/50">{item.summary}</p>

                <div className="flex items-center justify-between text-xs text-slate-500 pt-4 mt-4 border-t border-slate-200/70 dark:text-white/55 dark:border-white/10">
                  <span className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                    {new Date(item.published_at || item.created_at).toLocaleDateString()}
                  </span>
                  <span className="flex items-center gap-2">
                    <Eye className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                    {item.view_count} 阅读
                  </span>
                </div>
              </div>
              </Card>
            </Link>
          ))
        )}
      </div>

      {totalPages > 1 ? (
        <Pagination
          currentPage={page}
          totalPages={totalPages}
          onPageChange={(p) => setPage(p)}
        />
      ) : null}
    </div>
  )
}
