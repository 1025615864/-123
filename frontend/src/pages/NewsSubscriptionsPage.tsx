import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Check, Trash2, Tag, Search, RefreshCw } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import PageHeader from '../components/PageHeader'
import { Button, Card, Chip, EmptyState, Input, ListSkeleton, Badge, LinkButton } from '../components/ui'
import api from '../api/client'
import { useToast } from '../hooks'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { getApiErrorMessage } from '../utils'
import { useNewsSubscriptionsQuery, type NewsSubscriptionItem } from '../queries/newsSubscriptions'

export default function NewsSubscriptionsPage() {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()
  const queryClient = useQueryClient()

  const [subType, setSubType] = useState<'category' | 'keyword'>('category')
  const [value, setValue] = useState('')
  const [pendingDelete, setPendingDelete] = useState<Record<number, boolean>>({})

  const { queryKey: subsQueryKey, query: subsQuery } = useNewsSubscriptionsQuery(isAuthenticated)

  useEffect(() => {
    if (!subsQuery.error) return
    toast.error(getApiErrorMessage(subsQuery.error))
  }, [subsQuery.error, toast])

  const items = (subsQuery.data ?? []) as NewsSubscriptionItem[]

  const canSubmit = useMemo(() => value.trim().length > 0, [value])

  const createMutation = useMutation({
    mutationFn: async () => {
      const payload = { sub_type: subType, value: value.trim() }
      const res = await api.post('/news/subscriptions', payload)
      return res.data as NewsSubscriptionItem
    },
    onMutate: async () => {
      const v = value.trim()
      if (!v) return { previous: undefined as unknown }

      await queryClient.cancelQueries({ queryKey: subsQueryKey })
      const previous = queryClient.getQueryData<NewsSubscriptionItem[]>(subsQueryKey)

      const optimistic: NewsSubscriptionItem = {
        id: -Math.trunc(Date.now()),
        sub_type: subType,
        value: v,
        created_at: new Date().toISOString(),
      }

      queryClient.setQueryData<NewsSubscriptionItem[]>(subsQueryKey, (old) => {
        const list = Array.isArray(old) ? old : []
        const exists = list.some((it) => it.sub_type === optimistic.sub_type && it.value === optimistic.value)
        if (exists) return list
        return [optimistic, ...list]
      })

      return { previous, optimisticId: optimistic.id }
    },
    onSuccess: () => {
      toast.success('已订阅')
      setValue('')
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, '订阅失败'))
    },
    onSettled: (data, err, _vars, ctx) => {
      if (err) {
        const anyCtx = ctx as any
        if (anyCtx?.previous) {
          queryClient.setQueryData(subsQueryKey, anyCtx.previous)
        }
        return
      }
      if (!data) return
      const anyCtx = ctx as any
      const optimisticId = Number(anyCtx?.optimisticId)
      queryClient.setQueryData<NewsSubscriptionItem[]>(subsQueryKey, (old) => {
        const list = Array.isArray(old) ? old : []
        if (Number.isFinite(optimisticId) && optimisticId < 0) {
          const idx = list.findIndex((it) => it.id === optimisticId)
          if (idx >= 0) {
            const next = [...list]
            next[idx] = data
            return next
          }
        }
        const exists = list.some((it) => it.id === data.id)
        return exists ? list : [data, ...list]
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/news/subscriptions/${id}`)
      return id
    },
    onMutate: async (id: number) => {
      setPendingDelete((prev) => ({ ...prev, [id]: true }))
      await queryClient.cancelQueries({ queryKey: subsQueryKey })
      const previous = queryClient.getQueryData<NewsSubscriptionItem[]>(subsQueryKey)
      queryClient.setQueryData<NewsSubscriptionItem[]>(subsQueryKey, (old) => {
        const list = Array.isArray(old) ? old : []
        return list.filter((it) => it.id !== id)
      })
      return { previous }
    },
    onSuccess: () => {
      toast.success('已删除')
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, '删除失败'))
    },
    onSettled: (_data, _err, id, ctx) => {
      setPendingDelete((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })

      const anyCtx = ctx as any
      if (_err && anyCtx?.previous) {
        queryClient.setQueryData(subsQueryKey, anyCtx.previous)
      }
    },
  })

  const actionBusy = createMutation.isPending || deleteMutation.isPending

  const handleCreate = async () => {
    if (!canSubmit || createMutation.isPending) return
    createMutation.mutate()
  }

  const handleDelete = async (id: number) => {
    if (deleteMutation.isPending || pendingDelete[id]) return
    deleteMutation.mutate(id)
  }

  if (!isAuthenticated) {
    return (
      <div className="space-y-10">
        <PageHeader
          eyebrow="新闻"
          title="新闻订阅"
          description="订阅分类或关键词，发布时自动提醒"
          layout="mdStart"
          tone={actualTheme}
        />

        <EmptyState
          icon={Bell}
          title="请先登录"
          description="登录后即可管理你的新闻订阅"
          tone={actualTheme}
          action={
            <Link to="/login" className="mt-6 inline-block">
              <Button>去登录</Button>
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="space-y-10" data-testid="news-subscriptions">
      <PageHeader
        eyebrow="新闻"
        title="新闻订阅"
        description="订阅分类或关键词，发布时自动提醒"
        layout="mdStart"
        tone={actualTheme}
        right={
          <div className="flex gap-2">
            <Button
              variant="outline"
              icon={RefreshCw}
              isLoading={subsQuery.isFetching}
              loadingText="刷新中..."
              onClick={() => subsQuery.refetch()}
              disabled={subsQuery.isFetching || actionBusy}
              className="rounded-full px-6 py-3 text-sm"
            >
              刷新
            </Button>
            <LinkButton to="/news" variant="ghost" className="rounded-full px-6 py-3 text-sm">
              返回新闻
            </LinkButton>
            <LinkButton
              to="/news?mode=subscribed"
              variant="outline"
              className="rounded-full px-6 py-3 text-sm"
              data-testid="news-subscriptions-view-feed"
            >
              查看订阅内容
            </LinkButton>
            <LinkButton to="/notifications" variant="outline" className="rounded-full px-6 py-3 text-sm">
              通知中心
            </LinkButton>
          </div>
        }
      />

      <Card variant="surface" padding="md">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Chip
              size="sm"
              active={subType === 'category'}
              onClick={() => {
                if (actionBusy) return
                setSubType('category')
              }}
            >
              分类订阅
            </Chip>
            <Chip
              size="sm"
              active={subType === 'keyword'}
              onClick={() => {
                if (actionBusy) return
                setSubType('keyword')
              }}
            >
              关键词订阅
            </Chip>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <Input
                icon={subType === 'category' ? Tag : Search}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={subType === 'category' ? '输入分类，例如：法律动态' : '输入关键词，例如：劳动'}
                className="py-2.5"
                data-testid="news-subscription-value"
                disabled={actionBusy}
              />
            </div>
            <Button
              onClick={handleCreate}
              disabled={!canSubmit || actionBusy}
              icon={Check}
              isLoading={createMutation.isPending}
              loadingText="添加中..."
              data-testid="news-subscription-add"
            >
              添加订阅
            </Button>
          </div>

          <div className="text-xs text-slate-500 dark:text-white/45">
            分类订阅会匹配新闻分类；关键词订阅会匹配标题/摘要/正文。
          </div>
        </div>
      </Card>

      {subsQuery.isLoading && items.length === 0 ? (
        <ListSkeleton count={4} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="暂无订阅"
          description="添加订阅后，当有匹配新闻发布时会通知你"
          tone={actualTheme}
        />
      ) : (
        <Card variant="surface" padding="none">
          <div className="divide-y divide-slate-200/70 dark:divide-white/10">
            {items.map((s) => {
              const deleteLoading = Boolean(pendingDelete[s.id])
              const disableOther = actionBusy && !deleteLoading

              return (
                <div key={s.id} className="p-5 flex items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge variant={s.sub_type === 'category' ? 'primary' : 'info'} size="sm">
                        {s.sub_type === 'category' ? '分类' : '关键词'}
                      </Badge>
                      <div className="text-sm font-medium text-slate-900 truncate dark:text-white">{s.value}</div>
                    </div>
                    <div className="mt-2 text-xs text-slate-500 dark:text-white/45">
                      {new Date(s.created_at).toLocaleString()}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className={`hover:text-red-600 dark:hover:text-red-300 ${deleteLoading ? 'px-3 py-2' : 'p-2'}`}
                    title="删除"
                    onClick={() => {
                      if (actionBusy) return
                      handleDelete(s.id)
                    }}
                    isLoading={deleteLoading}
                    loadingText="删除中..."
                    disabled={disableOther || deleteLoading}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              )
            })}
          </div>
        </Card>
      )}
    </div>
  )
}
