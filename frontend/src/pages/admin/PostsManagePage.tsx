import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Trash2, Eye, Pin, PinOff, Flame, Award, RotateCcw } from 'lucide-react'
import { Card, Input, Button, Badge, ListSkeleton } from '../../components/ui'
import { useQuery } from '@tanstack/react-query'
import api from '../../api/client'
import { useAppMutation } from '../../hooks'
import { getApiErrorMessage } from '../../utils'

interface Post {
  id: number
  title: string
  category: string
  is_pinned: boolean
  is_hot?: boolean
  is_essence?: boolean
  view_count: number
  like_count: number
  comment_count: number
  created_at: string
  author?: {
    username?: string
    nickname?: string | null
  } | null
}

export default function PostsManagePage() {
  const [keyword, setKeyword] = useState('')
  const navigate = useNavigate()
  const [activeAction, setActiveAction] = useState<{ id: number; kind: 'pin' | 'hot' | 'essence' | 'delete' } | null>(null)

  const postsQueryKey = useMemo(() => ['admin-posts', { keyword: keyword.trim() }] as const, [keyword])

  const postsQuery = useQuery({
    queryKey: postsQueryKey,
    queryFn: async () => {
      const trimmed = keyword.trim()
      const res = await api.get('/forum/admin/posts', {
        params: trimmed ? { keyword: trimmed } : {},
      })
      const items = res.data?.items ?? []
      return (Array.isArray(items) ? items : []) as Post[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const posts = postsQuery.data ?? []
  const loading = postsQuery.isLoading
  const loadError = postsQuery.isError ? getApiErrorMessage(postsQuery.error, '帖子列表加载失败，请稍后重试') : null

  const deleteMutation = useAppMutation<void, number>({
    mutationFn: async (id) => {
      await api.delete(`/forum/posts/${id}`)
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [postsQueryKey as any],
    onMutate: async (id) => {
      setActiveAction({ id, kind: 'delete' })
    },
    onSettled: (_data, _err, id) => {
      setActiveAction((prev) => (prev && prev.id === id && prev.kind === 'delete' ? null : prev))
    },
  })

  const pinMutation = useAppMutation<void, { id: number; is_pinned: boolean }>({
    mutationFn: async (payload) => {
      await api.post(`/forum/admin/posts/${payload.id}/pin`, { is_pinned: payload.is_pinned })
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [postsQueryKey as any],
    onMutate: async (payload) => {
      setActiveAction({ id: payload.id, kind: 'pin' })
    },
    onSettled: (_data, _err, payload) => {
      setActiveAction((prev) => (prev && prev.id === payload?.id && prev.kind === 'pin' ? null : prev))
    },
  })

  const hotMutation = useAppMutation<void, { id: number; is_hot: boolean }>({
    mutationFn: async (payload) => {
      await api.post(`/forum/admin/posts/${payload.id}/hot`, { is_hot: payload.is_hot })
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [postsQueryKey as any],
    onMutate: async (payload) => {
      setActiveAction({ id: payload.id, kind: 'hot' })
    },
    onSettled: (_data, _err, payload) => {
      setActiveAction((prev) => (prev && prev.id === payload?.id && prev.kind === 'hot' ? null : prev))
    },
  })

  const essenceMutation = useAppMutation<void, { id: number; is_essence: boolean }>({
    mutationFn: async (payload) => {
      await api.post(`/forum/admin/posts/${payload.id}/essence`, { is_essence: payload.is_essence })
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [postsQueryKey as any],
    onMutate: async (payload) => {
      setActiveAction({ id: payload.id, kind: 'essence' })
    },
    onSettled: (_data, _err, payload) => {
      setActiveAction((prev) => (prev && prev.id === payload?.id && prev.kind === 'essence' ? null : prev))
    },
  })

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除这篇帖子吗？')) return
    if (deleteMutation.isPending) return
    deleteMutation.mutate(id)
  }

  const togglePin = async (id: number, isPinned: boolean) => {
    if (pinMutation.isPending) return
    pinMutation.mutate({ id, is_pinned: !isPinned })
  }

  const toggleHot = async (id: number, isHot: boolean) => {
    if (hotMutation.isPending) return
    hotMutation.mutate({ id, is_hot: !isHot })
  }

  const toggleEssence = async (id: number, isEssence: boolean) => {
    if (essenceMutation.isPending) return
    essenceMutation.mutate({ id, is_essence: !isEssence })
  }

  const actionBusy = deleteMutation.isPending || pinMutation.isPending || hotMutation.isPending || essenceMutation.isPending

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">帖子管理</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">管理论坛帖子内容</p>
        </div>
        <Button
          variant="outline"
          icon={RotateCcw}
          isLoading={postsQuery.isFetching}
          loadingText="刷新中..."
          disabled={postsQuery.isFetching}
          onClick={() => postsQuery.refetch()}
        >
          刷新
        </Button>
      </div>

      <Card variant="surface" padding="md">
        <div className="flex gap-4 mb-6">
          <div className="flex-1 max-w-md">
            <Input
              icon={Search}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索帖子标题或作者..."
            />
          </div>
        </div>

        {loading && posts.length === 0 ? (
          <ListSkeleton count={6} />
        ) : loadError ? (
          <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
            <div>{loadError}</div>
            <Button variant="outline" onClick={() => postsQuery.refetch()}>重试</Button>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200/70 dark:border-white/10">
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">标题</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">分类</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">作者</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">互动</th>
                    <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">发布时间</th>
                    <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {posts.map((item) => (
                    <tr key={item.id} className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5">
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-2">
                      {item.is_pinned && (
                        <Badge variant="warning" size="sm">置顶</Badge>
                      )}
                      {item.is_hot && (
                        <Badge variant="danger" size="sm">热门</Badge>
                      )}
                      {item.is_essence && (
                        <Badge variant="success" size="sm">精华</Badge>
                      )}
                      <p className="text-slate-900 font-medium truncate max-w-xs dark:text-white">{item.title}</p>
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <Badge variant="info" size="sm">{item.category}</Badge>
                  </td>
                  <td className="py-4 px-4 text-slate-700 dark:text-white/70">{item.author?.nickname || item.author?.username || '-'}</td>
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-4 text-slate-600 text-sm dark:text-white/50">
                      <span>{item.view_count} 浏览</span>
                      <span>{item.like_count} 赞</span>
                      <span>{item.comment_count} 评论</span>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                    {new Date(item.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center justify-end gap-2">
                      {(() => {
                        const isActive = activeAction?.id === item.id
                        const disableOther = actionBusy && !isActive
                        const pinLoading = pinMutation.isPending && isActive && activeAction?.kind === 'pin'
                        const hotLoading = hotMutation.isPending && isActive && activeAction?.kind === 'hot'
                        const essenceLoading = essenceMutation.isPending && isActive && activeAction?.kind === 'essence'
                        const deleteLoading = deleteMutation.isPending && isActive && activeAction?.kind === 'delete'

                            return (
                              <>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className={`${pinLoading ? 'px-3 py-2' : 'p-2'} ${item.is_pinned ? 'text-amber-400' : ''}`}
                                  onClick={() => togglePin(item.id, item.is_pinned)}
                                  title={item.is_pinned ? '取消置顶' : '置顶'}
                                  isLoading={pinLoading}
                                  loadingText="处理中..."
                                  disabled={disableOther || pinLoading}
                                >
                                  {item.is_pinned ? (
                                    <PinOff className="h-4 w-4" />
                                  ) : (
                                    <Pin className="h-4 w-4" />
                                  )}
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className={`${hotLoading ? 'px-3 py-2' : 'p-2'} ${item.is_hot ? 'text-orange-400' : ''}`}
                                  onClick={() => toggleHot(item.id, !!item.is_hot)}
                                  title={item.is_hot ? '取消热门' : '设为热门'}
                                  isLoading={hotLoading}
                                  loadingText="处理中..."
                                  disabled={disableOther || hotLoading}
                                >
                                  <Flame className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className={`${essenceLoading ? 'px-3 py-2' : 'p-2'} ${item.is_essence ? 'text-green-400' : ''}`}
                                  onClick={() => toggleEssence(item.id, !!item.is_essence)}
                                  title={item.is_essence ? '取消精华' : '设为精华'}
                                  isLoading={essenceLoading}
                                  loadingText="处理中..."
                                  disabled={disableOther || essenceLoading}
                                >
                                  <Award className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="p-2"
                                  title="查看"
                                  onClick={() => navigate(`/forum/post/${item.id}`)}
                                >
                                  <Eye className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className={`${deleteLoading ? 'px-3 py-2' : 'p-2'} text-red-400 hover:text-red-300`}
                                  onClick={() => handleDelete(item.id)}
                                  title="删除"
                                  isLoading={deleteLoading}
                                  loadingText="删除中..."
                                  disabled={disableOther || deleteLoading}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </>
                            )
                          })()}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {posts.length === 0 && (
              <div className="text-center py-12 text-slate-500 dark:text-white/40">暂无帖子</div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
