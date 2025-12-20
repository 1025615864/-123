import { Link } from 'react-router-dom'
import { Clock, MessageSquare, ThumbsUp, Star, Eye, Flame, Award, Pin, Image as ImageIcon } from 'lucide-react'
import { Card, Badge, FadeInImage } from './ui'
import type { Post } from '../types'

export interface PostCardProps {
  post: Post
  onToggleFavorite?: (postId: number) => void
  favoriteDisabled?: boolean
  showHeatScore?: boolean
  onPrefetch?: (postId: number) => void
}

export default function PostCard({ post, onToggleFavorite, favoriteDisabled, showHeatScore = false, onPrefetch }: PostCardProps) {
  const images = post.images || []
  const hasImages = images.length > 0
  
  return (
    <Link
      to={`/forum/post/${post.id}`}
      className="block"
      onMouseEnter={() => onPrefetch?.(post.id)}
      onFocus={() => onPrefetch?.(post.id)}
    >
      <Card variant="surface" hover padding="none" className="p-6 rounded-3xl group overflow-hidden">
        {/* 标签区域 */}
        <div className="flex items-center gap-2 flex-wrap mb-3">
          {post.is_pinned && (
            <Badge variant="warning" size="sm" className="rounded-full flex items-center gap-1">
              <Pin className="h-3 w-3" />
              置顶
            </Badge>
          )}
          {post.is_essence && (
            <Badge variant="success" size="sm" className="rounded-full flex items-center gap-1">
              <Award className="h-3 w-3" />
              精华
            </Badge>
          )}
          {post.is_hot && (
            <Badge variant="danger" size="sm" className="rounded-full flex items-center gap-1">
              <Flame className="h-3 w-3" />
              热门
            </Badge>
          )}
          <Badge variant="primary" size="sm" className="rounded-full">
            {post.category}
          </Badge>
        </div>

        <div className="flex gap-4">
          {/* 内容区域 */}
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-slate-900 group-hover:text-amber-600 transition-colors line-clamp-2 dark:text-white dark:group-hover:text-amber-400">
              {post.title}
            </h3>
            <p className="text-slate-600 mt-2 line-clamp-2 text-sm leading-relaxed dark:text-white/50">
              {post.content}
            </p>
          </div>

          {/* 封面图 */}
          {(post.cover_image || hasImages) && (
            <div className="flex-shrink-0 w-24 h-24 rounded-xl overflow-hidden bg-slate-900/5 dark:bg-white/5">
              <FadeInImage
                src={post.cover_image || images[0]}
                alt=""
                wrapperClassName="w-full h-full"
                className="h-full w-full object-cover"
              />
            </div>
          )}
        </div>

        {/* 图片预览 */}
        {hasImages && images.length > 1 && (
          <div className="flex items-center gap-2 mt-3">
            <ImageIcon className="h-4 w-4 text-slate-400 dark:text-white/40" />
            <span className="text-xs text-slate-500 dark:text-white/40">{images.length} 张图片</span>
          </div>
        )}

        {/* 底部信息 */}
        <div className="flex flex-wrap items-center justify-between gap-4 mt-5 pt-4 border-t border-slate-200/70 dark:border-white/5">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <span className="text-sm text-slate-700 dark:text-white/70">{post.author?.nickname || post.author?.username || '匿名用户'}</span>
            <span className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-white/40">
              <Clock className="h-3.5 w-3.5" />
              {new Date(post.created_at).toLocaleDateString()}
            </span>
            <span className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-white/40">
              <Eye className="h-3.5 w-3.5" />
              {post.view_count || 0}
            </span>
            <span className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-white/40">
              <ThumbsUp className="h-3.5 w-3.5" />
              {post.like_count}
            </span>
            <span className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-white/40">
              <MessageSquare className="h-3.5 w-3.5" />
              {post.comment_count}
            </span>
            {showHeatScore && (post.heat_score || 0) > 0 && (
              <span className="flex items-center gap-1.5 text-xs text-orange-400">
                <Flame className="h-3.5 w-3.5" />
                {(post.heat_score || 0).toFixed(0)}
              </span>
            )}
          </div>

          <button
            type="button"
            disabled={!onToggleFavorite || favoriteDisabled}
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              onToggleFavorite?.(post.id)
            }}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl transition-colors border border-slate-200/70 bg-slate-900/5 text-slate-600 hover:bg-slate-900/10 hover:text-slate-900 disabled:opacity-50 disabled:cursor-not-allowed dark:border-white/10 dark:bg-white/5 dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white ${
              post.is_favorited ? 'text-amber-600 bg-amber-500/15 border-amber-500/30 dark:text-amber-400' : ''
            }`}
            aria-label={post.is_favorited ? '取消收藏' : '收藏'}
            title={post.is_favorited ? '取消收藏' : '收藏'}
          >
            <Star className={`h-4 w-4 ${post.is_favorited ? 'fill-amber-400' : ''}`} />
            <span className="text-xs">{post.favorite_count ?? 0}</span>
          </button>
        </div>
      </Card>
    </Link>
  )
}
