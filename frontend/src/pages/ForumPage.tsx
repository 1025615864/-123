import { useMemo, useState, useEffect, useCallback } from 'react'
import { MessageSquare, Plus, Search } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Modal, Input, Button, Chip, EmptyState, LinkButton, ModalActions, PostCardSkeleton, VirtualWindowList } from '../components/ui'
import PageHeader from '../components/PageHeader'
import PostCard from '../components/PostCard'
import RichTextEditor from '../components/RichTextEditor'
import api from '../api/client'
import { usePrefetchLimiter, useToast, useAppMutation } from '../hooks'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import type { Post } from '../types'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'

interface PostsListResponse {
  items: Post[]
  total: number
}

export default function ForumPage() {
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newPost, setNewPost] = useState({ title: '', content: '', category: '法律咨询', images: [] as string[] })
  const [activeCategory, setActiveCategory] = useState('全部')
  const [keyword, setKeyword] = useState('')
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()
  const queryClient = useQueryClient()

  const { prefetch } = usePrefetchLimiter()

  const [debouncedKeyword, setDebouncedKeyword] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedKeyword(keyword), 300)
    return () => window.clearTimeout(timer)
  }, [keyword])

  const isFavoritesMode = isAuthenticated && activeCategory === '我的收藏'

  const postsQueryKey = useMemo(
    () =>
      queryKeys.forumPosts(page, pageSize, activeCategory, debouncedKeyword.trim(), isFavoritesMode),
    [activeCategory, debouncedKeyword, isFavoritesMode, page, pageSize]
  )

  const postsQuery = useQuery({
    queryKey: postsQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('page', String(page))
      params.set('page_size', String(pageSize))

      if (!isFavoritesMode && activeCategory && activeCategory !== '全部') {
        params.set('category', activeCategory)
      }
      if (debouncedKeyword.trim()) {
        params.set('keyword', debouncedKeyword.trim())
      }

      const endpoint = isFavoritesMode ? '/forum/favorites' : '/forum/posts'
      const res = await api.get(`${endpoint}?${params.toString()}`)
      const data = res.data as PostsListResponse
      return {
        items: Array.isArray(data?.items) ? data.items : [],
        total: Number(data?.total || 0),
      } as PostsListResponse
    },
    placeholderData: (prev) => prev,
    retry: 1,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (!postsQuery.error) return
    toast.error(getApiErrorMessage(postsQuery.error))
  }, [postsQuery.error, toast])

  useEffect(() => {
    setPage(1)
  }, [activeCategory, keyword])

  const toggleFavoriteMutation = useMutation({
    mutationFn: async (postId: number) => {
      const res = await api.post(`/forum/posts/${postId}/favorite`)
      return res.data as { favorited: boolean; favorite_count: number }
    },
    onMutate: async (postId) => {
      if (!isAuthenticated) return
      await queryClient.cancelQueries({ queryKey: postsQueryKey })

      const previous = queryClient.getQueryData<PostsListResponse>(postsQueryKey)

      queryClient.setQueryData<PostsListResponse>(postsQueryKey, (old) => {
        if (!old) return old as any
        const nextItems = old.items.map((p) => {
          if (p.id !== postId) return p
          const nextFavorited = !p.is_favorited
          const nextCount = Math.max(0, (p.favorite_count ?? 0) + (nextFavorited ? 1 : -1))
          return { ...p, is_favorited: nextFavorited, favorite_count: nextCount }
        })

        if (isFavoritesMode) {
          return {
            ...old,
            items: nextItems.filter((p) => p.is_favorited),
            total: nextItems.filter((p) => p.is_favorited).length,
          }
        }

        return { ...old, items: nextItems }
      })

      return { previous }
    },
    onError: (err, _postId, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(postsQueryKey, ctx.previous)
      }
      toast.error(getApiErrorMessage(err))
    },
    onSuccess: (result, postId) => {
      queryClient.setQueryData<PostsListResponse>(postsQueryKey, (old) => {
        if (!old) return old as any
        const nextItems = old.items
          .map((p) =>
            p.id === postId
              ? { ...p, is_favorited: !!result.favorited, favorite_count: Number(result.favorite_count ?? 0) }
              : p
          )
          .filter((p) => (isFavoritesMode ? p.is_favorited : true))
        return { ...old, items: nextItems, total: isFavoritesMode ? nextItems.length : old.total }
      })
    },
  })

  const handleToggleFavorite = useCallback(
    async (postId: number) => {
      if (!isAuthenticated) return
      toggleFavoriteMutation.mutate(postId)
    },
    [isAuthenticated, toggleFavoriteMutation]
  )

  const createPostMutation = useAppMutation({
    mutationFn: async (_: void) => {
      const res = await api.post('/forum/posts', newPost)
      return res.data
    },
    errorMessageFallback: '发布失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.forumPostsRoot()],
    onSuccess: () => {
      setShowCreateModal(false)
      setNewPost({ title: '', content: '', category: '法律咨询', images: [] })
      setPage(1)
    },
  })

  const createPost = async () => {
    if (!newPost.title.trim() || !newPost.content.trim()) return
    createPostMutation.mutate()
  }

  const postCategories = ['法律咨询', '经验分享', '案例讨论', '政策解读', '其他']
  const categories = isAuthenticated ? ['我的收藏', '全部', ...postCategories] : ['全部', ...postCategories]

  const posts = postsQuery.data?.items ?? []
  const total = postsQuery.data?.total ?? 0

  if (postsQuery.isLoading && posts.length === 0) {
    return (
      <div className="space-y-6">
        {Array.from({ length: 5 }).map((_, i) => (
          <PostCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const prefetchPostDetail = (id: number) => {
    const postId = String(id)
    prefetch({
      queryKey: queryKeys.forumPost(postId),
      queryFn: async () => {
        const res = await api.get(`/forum/posts/${postId}`)
        return res.data
      },
    })
    prefetch({
      queryKey: queryKeys.forumPostComments(postId),
      queryFn: async () => {
        const res = await api.get(`/forum/posts/${postId}/comments`)
        const items = res.data?.items ?? []
        return Array.isArray(items) ? items : []
      },
    })
  }

  return (
    <div className="w-full space-y-14">
      <PageHeader
        eyebrow="社区交流"
        title="法律论坛"
        description="与律师和法律爱好者交流讨论，分享经验与观点"
        layout="lgEnd"
        tone={actualTheme}
        right={
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="w-full sm:w-64">
              <Input
                icon={Search}
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="搜索帖子..."
                className="py-2.5"
              />
            </div>
            {isAuthenticated ? (
              <Button
                onClick={() => setShowCreateModal(true)}
                icon={Plus}
                className="py-2.5"
              >
                发布
              </Button>
            ) : (
              <LinkButton
                to="/login"
                variant="outline"
                size="md"
                className="px-5 py-2.5"
              >
                登录后发帖
              </LinkButton>
            )}
          </div>
        }
      />

      <div className="flex flex-wrap gap-3">
        {categories.map((cat) => (
          <Chip key={cat} active={activeCategory === cat} onClick={() => setActiveCategory(cat)}>
            {cat}
          </Chip>
        ))}
      </div>

      <div>
        {posts.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="暂无符合条件的帖子"
            description="试试切换分类或修改搜索关键词"
            size="lg"
            action={
              isAuthenticated ? (
                <div className="mt-6">
                  <Button
                    onClick={() => setShowCreateModal(true)}
                    icon={Plus}
                    className="py-2.5"
                  >
                    发布第一个帖子
                  </Button>
                </div>
              ) : null
            }
          />
        ) : (
          <VirtualWindowList
            items={posts}
            estimateItemHeight={220}
            overscan={8}
            getItemKey={(post: Post) => post.id}
            itemClassName="pb-6"
            renderItem={(post) => (
              <PostCard
                post={post}
                onToggleFavorite={handleToggleFavorite}
                favoriteDisabled={!isAuthenticated}
                onPrefetch={prefetchPostDetail}
              />
            )}
          />
        )}
      </div>

      {totalPages > 1 ? (
        <div className="flex items-center justify-center gap-4 pt-2">
          <Button
            variant="outline"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-5"
          >
            上一页
          </Button>
          <div className="text-sm text-slate-600 dark:text-white/60">
            第 {page} / {totalPages} 页
          </div>
          <Button
            variant="outline"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="px-5"
          >
            下一页
          </Button>
        </div>
      ) : null}

      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="发布新帖子"
        description="请尽量描述清楚问题，方便他人回复"
      >
        <div className="space-y-4">
          <Input
            label="标题"
            value={newPost.title}
            onChange={(e) => setNewPost({ ...newPost, title: e.target.value })}
            placeholder="请输入标题"
          />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">分类</label>
            <select
              value={newPost.category}
              onChange={(e) => setNewPost({ ...newPost, category: e.target.value })}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition focus-visible:border-amber-500/50 focus-visible:ring-2 focus-visible:ring-amber-500/20 dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            >
              {postCategories.map((cat) => (
                <option key={cat} value={cat} className="bg-white text-slate-900 dark:bg-[#0f0a1e] dark:text-white">
                  {cat}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">内容</label>
            <RichTextEditor
              value={newPost.content}
              onChange={(content) => setNewPost({ ...newPost, content })}
              images={newPost.images}
              onImagesChange={(images) => setNewPost({ ...newPost, images })}
              placeholder="请输入内容，支持表情、图片和链接..."
              minHeight="180px"
            />
          </div>
        </div>

        <ModalActions className="mt-7">
          <Button
            variant="outline"
            onClick={() => setShowCreateModal(false)}
          >
            取消
          </Button>
          <Button
            onClick={createPost}
            disabled={!newPost.title.trim() || !newPost.content.trim()}
            isLoading={createPostMutation.isPending}
          >
            发布
          </Button>
        </ModalActions>
      </Modal>
    </div>
  )
}
