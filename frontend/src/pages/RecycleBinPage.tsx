import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Eye, RotateCcw, Search, Trash2 } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import api from '../api/client'
import PageHeader from '../components/PageHeader'
import { Button, Card, EmptyState, Input, Loading, Modal, ModalActions, Pagination } from '../components/ui'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useAppMutation, useToast } from '../hooks'
import type { Post } from '../types'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'

interface PostsListResponse {
  items: Post[]
  total: number
  page?: number
  page_size?: number
}

type BatchFailedItem = { id: number; reason: string }

type BatchResult = {
  title: string
  successIds: number[]
  failed: BatchFailedItem[]
}

function getExcerpt(content: string, maxLen: number): string {
  const withoutImages = content.replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
  const withoutLinks = withoutImages.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
  const withoutMd = withoutLinks
    .replace(/[`*_>#]/g, ' ')
    .replace(/\r\n/g, '\n')
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (withoutMd.length <= maxLen) return withoutMd
  return withoutMd.slice(0, maxLen) + '...'
}

export default function RecycleBinPage() {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [urlParams, setUrlParams] = useSearchParams()
  const didInitFromUrlRef = useRef(false)
  const lastKeywordRef = useRef<string | null>(null)

  const [page, setPage] = useState(1)
  const pageSize = 20
  const [keyword, setKeyword] = useState('')
  const [debouncedKeyword, setDebouncedKeyword] = useState('')

  const [confirmRestore, setConfirmRestore] = useState<Post | null>(null)
  const [confirmPurge, setConfirmPurge] = useState<Post | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [confirmBatchRestore, setConfirmBatchRestore] = useState(false)
  const [confirmBatchPurge, setConfirmBatchPurge] = useState(false)
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedKeyword(keyword), 300)
    return () => window.clearTimeout(timer)
  }, [keyword])

  useEffect(() => {
    if (!didInitFromUrlRef.current) return
    if (lastKeywordRef.current === null) {
      lastKeywordRef.current = keyword
      return
    }
    if (lastKeywordRef.current === keyword) return
    lastKeywordRef.current = keyword
    setPage(1)
  }, [keyword])

  useEffect(() => {
    if (didInitFromUrlRef.current) return

    const rawPage = Number(String(urlParams.get('page') ?? '1'))
    const nextPage = Number.isFinite(rawPage) && rawPage >= 1 ? Math.floor(rawPage) : 1

    const nextKeyword = String(urlParams.get('kw') ?? '')

    setPage(nextPage)
    setKeyword(nextKeyword)
    lastKeywordRef.current = nextKeyword
    didInitFromUrlRef.current = true
  }, [urlParams])

  useEffect(() => {
    if (!didInitFromUrlRef.current) return
    setUrlParams(
      (prev) => {
        const next = new URLSearchParams(prev)

        if (page > 1) next.set('page', String(page))
        else next.delete('page')

        const kw = keyword.trim()
        if (kw) next.set('kw', kw)
        else next.delete('kw')

        return next
      },
      { replace: true }
    )
  }, [keyword, page, setUrlParams])

  const queryKey = useMemo(
    () => ['forum-recycle-bin', { page, pageSize, keyword: debouncedKeyword.trim() }] as const,
    [page, pageSize, debouncedKeyword]
  )

  const postsQuery = useQuery({
    queryKey,
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('page', String(page))
      params.set('page_size', String(pageSize))
      if (debouncedKeyword.trim()) {
        params.set('keyword', debouncedKeyword.trim())
      }
      const res = await api.get(`/forum/me/posts/deleted?${params.toString()}`)
      const data = res.data as PostsListResponse
      return {
        items: Array.isArray(data?.items) ? data.items : [],
        total: Number(data?.total || 0),
        page: Number((data as any)?.page || page),
        page_size: Number((data as any)?.page_size || pageSize),
      } as PostsListResponse
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const batchRestoreMutation = useAppMutation<{ success_ids: number[]; failed: BatchFailedItem[] }, { ids: number[] }>({
    mutationFn: async (payload) => {
      const res = await api.post('/forum/posts/batch/restore', payload)
      return res.data as { success_ids: number[]; failed: BatchFailedItem[] }
    },
    errorMessageFallback: '批量恢复失败，请稍后重试',
    onSuccess: async (data) => {
      setConfirmBatchRestore(false)
      setSelectedIds(new Set())
      setBatchResult({
        title: '批量恢复结果',
        successIds: Array.isArray(data?.success_ids) ? data.success_ids : [],
        failed: Array.isArray(data?.failed) ? data.failed : [],
      })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey }),
        queryClient.invalidateQueries({ queryKey: queryKeys.forumPostsRoot() }),
      ])
      toast.success(`已恢复 ${Array.isArray(data?.success_ids) ? data.success_ids.length : 0} 条`)
    },
  })

  useEffect(() => {
    if (!postsQuery.error) return
    toast.error(getApiErrorMessage(postsQuery.error))
  }, [postsQuery.error, toast])

  const restoreMutation = useAppMutation<{ message: string }, number>({
    mutationFn: async (postId: number) => {
      const res = await api.post(`/forum/posts/${postId}/restore`)
      return res.data as { message: string }
    },
    errorMessageFallback: '恢复失败，请稍后重试',
    onSuccess: async () => {
      setConfirmRestore(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey }),
        queryClient.invalidateQueries({ queryKey: queryKeys.forumPostsRoot() }),
      ])
      toast.success('已恢复')
    },
  })

  const purgeMutation = useAppMutation<{ message: string }, number>({
    mutationFn: async (postId: number) => {
      const res = await api.delete(`/forum/posts/${postId}/purge`)
      return res.data as { message: string }
    },
    errorMessageFallback: '永久删除失败，请稍后重试',
    onSuccess: async () => {
      setConfirmPurge(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey }),
        queryClient.invalidateQueries({ queryKey: queryKeys.forumPostsRoot() }),
      ])
      toast.success('已永久删除')
    },
  })

  const batchPurgeMutation = useAppMutation<{ success_ids: number[]; failed: BatchFailedItem[] }, { ids: number[] }>({
    mutationFn: async (payload) => {
      const res = await api.post('/forum/posts/batch/purge', payload)
      return res.data as { success_ids: number[]; failed: BatchFailedItem[] }
    },
    errorMessageFallback: '批量永久删除失败，请稍后重试',
    onSuccess: async (data) => {
      setConfirmBatchPurge(false)
      setSelectedIds(new Set())
      setBatchResult({
        title: '批量永久删除结果',
        successIds: Array.isArray(data?.success_ids) ? data.success_ids : [],
        failed: Array.isArray(data?.failed) ? data.failed : [],
      })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey }),
        queryClient.invalidateQueries({ queryKey: queryKeys.forumPostsRoot() }),
      ])
      toast.success(`已永久删除 ${Array.isArray(data?.success_ids) ? data.success_ids.length : 0} 条`)
    },
  })

  if (!isAuthenticated) {
    return (
      <div className="text-center py-20">
        <p className="text-slate-600 dark:text-white/50">登录后可查看回收站</p>
        <Link to="/login" className="text-amber-600 hover:underline mt-4 inline-block dark:text-amber-400">
          去登录
        </Link>
      </div>
    )
  }

  const items = postsQuery.data?.items ?? []
  const total = postsQuery.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const currentPageIds = useMemo(() => items.map((p) => p.id), [items])
  const isAllCurrentPageSelected = useMemo(
    () => currentPageIds.length > 0 && currentPageIds.every((id) => selectedIds.has(id)),
    [currentPageIds, selectedIds]
  )

  if (postsQuery.isLoading && items.length === 0) {
    return <Loading text="加载中..." tone={actualTheme} />
  }

  return (
    <div className="space-y-10">
      <Link
        to="/forum"
        className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors dark:text-white/60 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        返回论坛
      </Link>

      <PageHeader
        eyebrow="社区交流"
        title="回收站"
        description="删除的帖子会暂存在这里，可恢复或永久删除"
        tone={actualTheme}
        layout="lgEnd"
        right={
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="w-full sm:w-64">
              <Input
                icon={Search}
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="搜索回收站..."
                className="py-2.5"
              />
            </div>
            <div className="flex items-center text-sm text-slate-600 px-2 dark:text-white/60">
              已选 {selectedIds.size} 条
            </div>
            <Button
              variant="outline"
              onClick={() => {
                if (currentPageIds.length === 0) return
                setSelectedIds((prev) => {
                  const next = new Set(prev)
                  if (isAllCurrentPageSelected) {
                    currentPageIds.forEach((id) => next.delete(id))
                    return next
                  }
                  currentPageIds.forEach((id) => next.add(id))
                  return next
                })
              }}
              disabled={currentPageIds.length === 0}
            >
              {isAllCurrentPageSelected ? '取消本页' : '全选本页'}
            </Button>
            <Button
              variant="outline"
              onClick={() => setSelectedIds(new Set())}
              disabled={selectedIds.size === 0}
            >
              清空选择
            </Button>
            <Button
              variant="outline"
              icon={RotateCcw}
              onClick={() => setConfirmBatchRestore(true)}
              disabled={
                selectedIds.size === 0 ||
                restoreMutation.isPending ||
                purgeMutation.isPending ||
                batchRestoreMutation.isPending ||
                batchPurgeMutation.isPending
              }
            >
              批量恢复
            </Button>
            <Button
              variant="danger"
              icon={Trash2}
              onClick={() => setConfirmBatchPurge(true)}
              disabled={
                selectedIds.size === 0 ||
                restoreMutation.isPending ||
                purgeMutation.isPending ||
                batchRestoreMutation.isPending ||
                batchPurgeMutation.isPending
              }
            >
              批量永久删除
            </Button>
            <Button variant="outline" onClick={() => navigate('/forum')}>
              返回列表
            </Button>
          </div>
        }
      />

      {items.length === 0 ? (
        <EmptyState
          icon={Trash2}
          title="回收站为空"
          description="删除的帖子会在这里显示"
          size="lg"
        />
      ) : (
        <div className="space-y-5">
          {items.map((post) => {
            const excerpt = getExcerpt(post.content ?? '', 140)
            const checked = selectedIds.has(post.id)
            return (
              <Card key={post.id} variant="surface" padding="lg" className="rounded-3xl">
                <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5">
                  <div className="min-w-0">
                    <label className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-white/60">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          setSelectedIds((prev) => {
                            const next = new Set(prev)
                            if (next.has(post.id)) next.delete(post.id)
                            else next.add(post.id)
                            return next
                          })
                        }}
                      />
                      选择
                    </label>
                    <p className="text-xs text-slate-500 dark:text-white/40">{post.category}</p>
                    <h3 className="text-lg font-semibold text-slate-900 mt-1 line-clamp-1 dark:text-white">{post.title}</h3>
                    <p className="text-sm text-slate-600 mt-2 line-clamp-2 dark:text-white/50">{excerpt}</p>
                    <p className="text-xs text-slate-400 mt-3 dark:text-white/30">
                      删除时间：{new Date(post.updated_at || post.created_at).toLocaleString()}
                    </p>
                  </div>

                  <div className="flex gap-3 flex-shrink-0">
                    <Button
                      variant="outline"
                      icon={Eye}
                      onClick={() => navigate(`/forum/post/${post.id}?deleted=1`)}
                      disabled={restoreMutation.isPending || purgeMutation.isPending}
                    >
                      查看
                    </Button>
                    <Button
                      variant="outline"
                      icon={RotateCcw}
                      onClick={() => setConfirmRestore(post)}
                      disabled={restoreMutation.isPending || purgeMutation.isPending}
                    >
                      恢复
                    </Button>
                    <Button
                      variant="danger"
                      icon={Trash2}
                      onClick={() => setConfirmPurge(post)}
                      disabled={restoreMutation.isPending || purgeMutation.isPending}
                    >
                      永久删除
                    </Button>
                  </div>
                </div>
              </Card>
            )
          })}

          <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} className="pt-4" />
        </div>
      )}

      <Modal
        isOpen={!!confirmRestore}
        onClose={() => setConfirmRestore(null)}
        title="恢复帖子"
        description="恢复后帖子将重新出现在论坛列表中"
        size="sm"
      >
        <ModalActions>
          <Button variant="ghost" onClick={() => setConfirmRestore(null)}>
            取消
          </Button>
          <Button
            icon={RotateCcw}
            onClick={() => {
              if (!confirmRestore) return
              if (restoreMutation.isPending) return
              restoreMutation.mutate(confirmRestore.id)
            }}
            isLoading={restoreMutation.isPending}
          >
            恢复
          </Button>
        </ModalActions>
      </Modal>

      <Modal
        isOpen={!!confirmPurge}
        onClose={() => setConfirmPurge(null)}
        title="永久删除"
        description="永久删除后将无法恢复，且会清理相关点赞/收藏/评论数据"
        size="sm"
      >
        <ModalActions>
          <Button variant="ghost" onClick={() => setConfirmPurge(null)}>
            取消
          </Button>
          <Button
            variant="danger"
            icon={Trash2}
            onClick={() => {
              if (!confirmPurge) return
              if (purgeMutation.isPending) return
              purgeMutation.mutate(confirmPurge.id)
            }}
            isLoading={purgeMutation.isPending}
          >
            确认永久删除
          </Button>
        </ModalActions>
      </Modal>

      <Modal
        isOpen={confirmBatchRestore}
        onClose={() => setConfirmBatchRestore(false)}
        title="批量恢复"
        description={`将恢复已选择的 ${selectedIds.size} 条帖子`}
        size="sm"
      >
        <ModalActions>
          <Button variant="ghost" onClick={() => setConfirmBatchRestore(false)}>
            取消
          </Button>
          <Button
            icon={RotateCcw}
            onClick={() => {
              if (batchRestoreMutation.isPending) return
              batchRestoreMutation.mutate({ ids: Array.from(selectedIds) })
            }}
            isLoading={batchRestoreMutation.isPending}
            disabled={selectedIds.size === 0}
          >
            确认恢复
          </Button>
        </ModalActions>
      </Modal>

      <Modal
        isOpen={confirmBatchPurge}
        onClose={() => setConfirmBatchPurge(false)}
        title="批量永久删除"
        description={`将永久删除已选择的 ${selectedIds.size} 条帖子（不可恢复）`}
        size="sm"
      >
        <ModalActions>
          <Button variant="ghost" onClick={() => setConfirmBatchPurge(false)}>
            取消
          </Button>
          <Button
            variant="danger"
            icon={Trash2}
            onClick={() => {
              if (batchPurgeMutation.isPending) return
              batchPurgeMutation.mutate({ ids: Array.from(selectedIds) })
            }}
            isLoading={batchPurgeMutation.isPending}
            disabled={selectedIds.size === 0}
          >
            确认永久删除
          </Button>
        </ModalActions>
      </Modal>

      <Modal
        isOpen={!!batchResult}
        onClose={() => setBatchResult(null)}
        title={batchResult?.title}
        size="md"
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200/70 bg-slate-900/5 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-white/80">
            成功：{batchResult?.successIds.length || 0} 条
            {batchResult && batchResult.failed.length > 0 ? `，失败：${batchResult.failed.length} 条` : ''}
          </div>

          {batchResult && batchResult.failed.length > 0 ? (
            <div className="rounded-xl border border-slate-200/70 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
              <p className="text-sm font-semibold text-slate-900 mb-3 dark:text-white">失败明细</p>
              <div className="space-y-2 max-h-64 overflow-auto">
                {batchResult.failed.map((x) => (
                  <div
                    key={`${x.id}-${x.reason}`}
                    className="flex items-center justify-between gap-3 text-sm text-slate-700 dark:text-white/80"
                  >
                    <span className="font-mono">#{x.id}</span>
                    <span className="text-slate-500 dark:text-white/50">{x.reason}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-600 dark:text-white/60">全部操作成功。</p>
          )}

          <ModalActions>
            <Button onClick={() => setBatchResult(null)}>知道了</Button>
          </ModalActions>
        </div>
      </Modal>
    </div>
  )
}
