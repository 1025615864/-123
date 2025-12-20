import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Clock, ThumbsUp, MessageSquare, Send, User, Star, Eye, Flame, Award, Pin, ChevronLeft, ChevronRight } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { useAppMutation, useToast } from '../hooks'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { Card, Button, Loading, Badge, Textarea, FadeInImage } from '../components/ui'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'

interface Author {
  id: number
  username: string
  nickname?: string
  avatar?: string
}

interface Comment {
  id: number
  content: string
  post_id: number
  user_id: number
  parent_id: number | null
  like_count: number
  images?: string[]
  created_at: string
  author: Author | null
  is_liked: boolean
  replies: Comment[]
}

interface ReactionCount {
  emoji: string
  count: number
}

interface PostDetail {
  id: number
  title: string
  content: string
  category: string
  user_id: number
  view_count: number
  like_count: number
  comment_count: number
  share_count: number
  favorite_count: number
  is_pinned: boolean
  is_hot: boolean
  is_essence: boolean
  heat_score: number
  cover_image?: string
  images?: string[]
  attachments?: Array<{ name: string; url: string }>
  reactions?: ReactionCount[]
  created_at: string
  updated_at: string
  author: Author | null
  is_liked: boolean
  is_favorited: boolean
}

// 常用表情
const QUICK_REACTIONS = ['👍', '❤️', '😀', '🎉', '🤔', '😢']

// 图片展示组件
function ImageGallery({ images }: { images: string[] }) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [showLightbox, setShowLightbox] = useState(false)

  if (images.length === 0) return null

  const handlePrev = () => setCurrentIndex(i => (i > 0 ? i - 1 : images.length - 1))
  const handleNext = () => setCurrentIndex(i => (i < images.length - 1 ? i + 1 : 0))

  return (
    <>
      <div className="grid gap-2" style={{ gridTemplateColumns: images.length === 1 ? '1fr' : images.length === 2 ? 'repeat(2, 1fr)' : 'repeat(3, 1fr)' }}>
        {images.slice(0, 9).map((img, idx) => (
          <div
            key={idx}
            className={`relative cursor-pointer rounded-xl overflow-hidden bg-slate-900/5 dark:bg-white/5 ${images.length === 1 ? 'max-h-96' : 'aspect-square'}`}
            onClick={() => { setCurrentIndex(idx); setShowLightbox(true) }}
          >
            <FadeInImage
              src={img}
              alt=""
              wrapperClassName="w-full h-full"
              className="h-full w-full object-cover hover:scale-105 transition-transform duration-300"
            />
            {idx === 8 && images.length > 9 && (
              <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                <span className="text-white text-2xl font-bold">+{images.length - 9}</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {showLightbox && (
        <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center" onClick={() => setShowLightbox(false)}>
          <button
            className="absolute left-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-white/10 hover:bg-white/20 text-white"
            onClick={(e) => { e.stopPropagation(); handlePrev() }}
          >
            <ChevronLeft className="h-6 w-6" />
          </button>
          <img
            src={images[currentIndex]}
            alt=""
            className="max-h-[90vh] max-w-[90vw] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          <button
            className="absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-white/10 hover:bg-white/20 text-white"
            onClick={(e) => { e.stopPropagation(); handleNext() }}
          >
            <ChevronRight className="h-6 w-6" />
          </button>
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-white/70 text-sm">
            {currentIndex + 1} / {images.length}
          </div>
        </div>
      )}
    </>
  )
}

export default function PostDetailPage() {
  const { postId } = useParams<{ postId: string }>()
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()
  const queryClient = useQueryClient()
  
  const [postDetail, setPostDetail] = useState<PostDetail | null>(null)
  const [comments, setComments] = useState<Comment[]>([])
  const [newComment, setNewComment] = useState('')

  const postQueryKey = queryKeys.forumPost(postId)
  const commentsQueryKey = queryKeys.forumPostComments(postId)

  const postQuery = useQuery({
    queryKey: postQueryKey,
    queryFn: async () => {
      const res = await api.get(`/forum/posts/${postId}`)
      return res.data as PostDetail
    },
    enabled: !!postId,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const commentsQuery = useQuery({
    queryKey: commentsQueryKey,
    queryFn: async () => {
      const res = await api.get(`/forum/posts/${postId}/comments`)
      const items = res.data?.items ?? []
      return (Array.isArray(items) ? items : []) as Comment[]
    },
    enabled: !!postId,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!postQuery.error) return
    toast.error(getApiErrorMessage(postQuery.error))
  }, [postQuery.error, toast])

  useEffect(() => {
    if (!commentsQuery.error) return
    toast.error(getApiErrorMessage(commentsQuery.error))
  }, [commentsQuery.error, toast])

  useEffect(() => {
    if (postQuery.data) setPostDetail(postQuery.data)
  }, [postQuery.data])

  useEffect(() => {
    setComments(commentsQuery.data ?? [])
  }, [commentsQuery.data])

  const likeMutation = useAppMutation<{ liked: boolean; like_count: number }, void>({
    mutationFn: async (_: void) => {
      const res = await api.post(`/forum/posts/${postId}/like`)
      return res.data as { liked: boolean; like_count: number }
    },
    errorMessageFallback: '操作失败，请稍后重试',
    onSuccess: (result) => {
      setPostDetail((prev) => (prev ? { ...prev, is_liked: result.liked, like_count: result.like_count } : prev))
      if (!postId) return
      queryClient.setQueryData<PostDetail>(postQueryKey, (old) =>
        old ? { ...old, is_liked: result.liked, like_count: result.like_count } : old
      )
    },
  })

  const favoriteMutation = useAppMutation<{ favorited: boolean; favorite_count: number }, void>({
    mutationFn: async (_: void) => {
      const res = await api.post(`/forum/posts/${postId}/favorite`)
      return res.data as { favorited: boolean; favorite_count: number }
    },
    errorMessageFallback: '操作失败，请稍后重试',
    onSuccess: (result) => {
      setPostDetail((prev) =>
        prev ? { ...prev, is_favorited: result.favorited, favorite_count: result.favorite_count } : prev
      )
      if (!postId) return
      queryClient.setQueryData<PostDetail>(postQueryKey, (old) =>
        old ? { ...old, is_favorited: result.favorited, favorite_count: result.favorite_count } : old
      )
    },
  })

  const reactionMutation = useAppMutation<{ reactions: ReactionCount[] }, string>({
    mutationFn: async (emoji: string) => {
      const res = await api.post(`/forum/posts/${postId}/reaction`, { emoji })
      return res.data as { reactions: ReactionCount[] }
    },
    errorMessageFallback: '操作失败，请稍后重试',
    onSuccess: (result) => {
      setPostDetail((prev) => (prev ? { ...prev, reactions: result.reactions } : prev))
      if (!postId) return
      queryClient.setQueryData<PostDetail>(postQueryKey, (old) => (old ? { ...old, reactions: result.reactions } : old))
    },
  })

  const commentMutation = useAppMutation<void, string>({
    mutationFn: async (content: string) => {
      await api.post(`/forum/posts/${postId}/comments`, { content })
    },
    errorMessageFallback: '发表评论失败，请稍后重试',
    onSuccess: () => {
      setNewComment('')
      if (postId) queryClient.invalidateQueries({ queryKey: commentsQueryKey })
      setPostDetail((prev) => (prev ? { ...prev, comment_count: prev.comment_count + 1 } : prev))
      queryClient.setQueryData<PostDetail>(postQueryKey, (old) =>
        old ? { ...old, comment_count: old.comment_count + 1 } : old
      )
    },
  })

  const handleLike = async () => {
    if (!isAuthenticated || !postId) return
    if (likeMutation.isPending) return
    likeMutation.mutate()
  }

  const handleFavorite = async () => {
    if (!isAuthenticated || !postId) return
    if (favoriteMutation.isPending) return
    favoriteMutation.mutate()
  }

  const handleSubmitComment = async () => {
    if (!newComment.trim() || commentMutation.isPending) return
    if (!postId) return
    commentMutation.mutate(newComment.trim())
  }

  const handleReaction = async (emoji: string) => {
    if (!isAuthenticated || !postId) return
    if (reactionMutation.isPending) return
    reactionMutation.mutate(emoji)
  }

  if (postQuery.isLoading && !postDetail) {
    return <Loading text="加载中..." tone={actualTheme} />
  }

  if (!postDetail) {
    return (
      <div className="text-center py-20">
        <p className="text-slate-600 dark:text-white/50">帖子不存在或已被删除</p>
        <Link to="/forum" className="text-amber-600 hover:underline mt-4 inline-block dark:text-amber-400">
          返回论坛
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* 返回按钮 */}
      <Link 
        to="/forum" 
        className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors dark:text-white/60 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        返回论坛
      </Link>

      {/* 帖子内容 */}
      <Card variant="surface" padding="lg">
        <div className="space-y-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              {/* 标签 */}
              <div className="flex items-center gap-2 flex-wrap mb-4">
                {postDetail.is_pinned && (
                  <Badge variant="warning" size="sm" className="flex items-center gap-1">
                    <Pin className="h-3 w-3" />
                    置顶
                  </Badge>
                )}
                {postDetail.is_essence && (
                  <Badge variant="success" size="sm" className="flex items-center gap-1">
                    <Award className="h-3 w-3" />
                    精华
                  </Badge>
                )}
                {postDetail.is_hot && (
                  <Badge variant="danger" size="sm" className="flex items-center gap-1">
                    <Flame className="h-3 w-3" />
                    热门
                  </Badge>
                )}
                <Badge variant="primary" size="sm">
                  {postDetail.category}
                </Badge>
              </div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{postDetail.title}</h1>
            </div>
            {/* 浏览量 */}
            <div className="flex items-center gap-1.5 text-slate-500 text-sm dark:text-white/40">
              <Eye className="h-4 w-4" />
              <span>{postDetail.view_count}</span>
            </div>
          </div>

          {/* 作者信息 */}
          <div className="flex items-center gap-3 pb-6 border-b border-slate-200/70 dark:border-white/5">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-500/20 to-orange-500/10 flex items-center justify-center">
              {postDetail.author?.avatar ? (
                <FadeInImage
                  src={postDetail.author.avatar}
                  alt=""
                  wrapperClassName="w-full h-full rounded-full"
                  className="h-full w-full rounded-full object-cover"
                />
              ) : (
                <User className="h-5 w-5 text-amber-400" />
              )}
            </div>
            <div>
              <p className="text-slate-900 font-medium dark:text-white">
                {postDetail.author?.nickname || postDetail.author?.username || '匿名用户'}
              </p>
              <p className="text-slate-500 text-sm flex items-center gap-2 dark:text-white/40">
                <Clock className="h-3.5 w-3.5" />
                {new Date(postDetail.created_at).toLocaleString()}
              </p>
            </div>
          </div>

          {/* 帖子正文 */}
          <div className="prose max-w-none dark:prose-invert">
            <p className="text-slate-700 leading-relaxed whitespace-pre-wrap dark:text-white/80">
              {postDetail.content}
            </p>
          </div>

          {/* 图片展示 */}
          {postDetail.images && postDetail.images.length > 0 && (
            <ImageGallery images={postDetail.images} />
          )}

          {/* 附件 */}
          {postDetail.attachments && postDetail.attachments.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm text-slate-500 dark:text-white/50">附件</p>
              <div className="flex flex-wrap gap-2">
                {postDetail.attachments.map((att, idx) => (
                  <a
                    key={idx}
                    href={att.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-900/5 hover:bg-slate-900/10 text-slate-700 hover:text-slate-900 text-sm transition-colors dark:bg-white/5 dark:hover:bg-white/10 dark:text-white/70 dark:hover:text-white"
                  >
                    📎 {att.name}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* 表情反应 */}
          {postDetail.reactions && postDetail.reactions.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 pt-4">
              {postDetail.reactions.map((reaction, idx) => (
                <span
                  key={idx}
                  className="flex items-center gap-1 px-2 py-1 rounded-full bg-slate-900/5 text-sm dark:bg-white/5"
                >
                  <span>{reaction.emoji}</span>
                  <span className="text-slate-600 dark:text-white/60">{reaction.count}</span>
                </span>
              ))}
            </div>
          )}

          {/* 快速表情反应 */}
          {isAuthenticated && (
            <div className="flex items-center gap-2 pt-2">
              <span className="text-xs text-slate-500 mr-1 dark:text-white/40">添加反应:</span>
              {QUICK_REACTIONS.map((emoji) => (
                <button
                  key={emoji}
                  onClick={() => handleReaction(emoji)}
                  className="p-1.5 rounded-lg hover:bg-slate-900/10 text-lg transition-colors dark:hover:bg-white/10"
                  title={`添加 ${emoji} 反应`}
                >
                  {emoji}
                </button>
              ))}
            </div>
          )}

          {/* 操作栏 */}
          <div className="flex items-center gap-6 pt-6 border-t border-slate-200/70 dark:border-white/5">
            <button
              onClick={handleLike}
              disabled={!isAuthenticated}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                postDetail.is_liked 
                  ? 'bg-amber-500/15 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400' 
                  : 'bg-slate-900/5 text-slate-600 hover:bg-slate-900/10 hover:text-slate-900 dark:bg-white/5 dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <ThumbsUp className={`h-4 w-4 ${postDetail.is_liked ? 'fill-amber-400' : ''}`} />
              <span>{postDetail.like_count}</span>
            </button>

            <button
              onClick={handleFavorite}
              disabled={!isAuthenticated}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                postDetail.is_favorited
                  ? 'bg-amber-500/15 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
                  : 'bg-slate-900/5 text-slate-600 hover:bg-slate-900/10 hover:text-slate-900 dark:bg-white/5 dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <Star className={`h-4 w-4 ${postDetail.is_favorited ? 'fill-amber-400' : ''}`} />
              <span>{postDetail.favorite_count}</span>
            </button>

            <div className="flex items-center gap-2 text-slate-500 dark:text-white/50">
              <MessageSquare className="h-4 w-4" />
              <span>{postDetail.comment_count} 评论</span>
            </div>
          </div>
        </div>
      </Card>

      {/* 评论区 */}
      <Card variant="surface" padding="lg">
        <h3 className="text-lg font-semibold text-slate-900 mb-6 dark:text-white">
          评论 ({comments.length})
        </h3>

        {/* 发表评论 */}
        {isAuthenticated ? (
          <div className="mb-8">
            <Textarea
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="写下你的评论..."
              rows={3}
            />
            <div className="mt-3 flex justify-end">
              <Button
                onClick={handleSubmitComment}
                disabled={!newComment.trim() || commentMutation.isPending}
                isLoading={commentMutation.isPending}
                icon={Send}
                className="px-6"
              >
                发表评论
              </Button>
            </div>
          </div>
        ) : (
          <div className="mb-8 p-4 rounded-xl bg-slate-900/5 text-center dark:bg-white/5">
            <p className="text-slate-600 dark:text-white/50">
              <Link to="/login" className="text-amber-600 hover:underline dark:text-amber-400">登录</Link>
              后即可发表评论
            </p>
          </div>
        )}

        {/* 评论列表 */}
        <div className="space-y-6">
          {comments.length === 0 ? (
            <p className="text-center text-slate-500 py-8 dark:text-white/40">暂无评论，来发表第一条评论吧</p>
          ) : (
            comments.map((comment) => (
              <div key={comment.id} className="flex gap-3">
                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-amber-500/20 to-orange-500/10 flex items-center justify-center flex-shrink-0">
                  {comment.author?.avatar ? (
                    <FadeInImage
                      src={comment.author.avatar}
                      alt=""
                      wrapperClassName="w-full h-full rounded-full"
                      className="h-full w-full rounded-full object-cover"
                    />
                  ) : (
                    <User className="h-4 w-4 text-amber-400" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-slate-900 font-medium text-sm dark:text-white">
                      {comment.author?.nickname || comment.author?.username || '匿名用户'}
                    </span>
                    <span className="text-slate-400 text-xs dark:text-white/30">
                      {new Date(comment.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-slate-700 text-sm leading-relaxed dark:text-white/70">{comment.content}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  )
}
