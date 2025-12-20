import { HTMLAttributes } from 'react'

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'text' | 'circular' | 'rectangular'
  width?: string
  height?: string
  animation?: 'pulse' | 'wave' | 'none'
}

export default function Skeleton({
  variant = 'text',
  width,
  height,
  animation = 'pulse',
  className = '',
  ...props
}: SkeletonProps) {
  const baseStyles = 'bg-slate-200/60 dark:bg-white/5'
  
  const variantStyles = {
    text: 'rounded-md h-4',
    circular: 'rounded-full',
    rectangular: 'rounded-xl'
  }
  
  const animationStyles = {
    pulse: 'animate-pulse',
    wave: 'animate-shimmer bg-gradient-to-r from-slate-200/60 via-slate-100/80 to-slate-200/60 dark:from-white/5 dark:via-white/10 dark:to-white/5 bg-[length:200%_100%]',
    none: ''
  }
  
  const style = {
    width: width || (variant === 'text' ? '100%' : undefined),
    height: height || (variant === 'text' ? undefined : '100%')
  }
  
  return (
    <div
      className={`${baseStyles} ${variantStyles[variant]} ${animationStyles[animation]} ${className}`}
      style={style}
      {...props}
    />
  )
}

// 预设骨架屏组件
export function PostCardSkeleton() {
  return (
    <div className="p-6 rounded-2xl bg-white border border-slate-200/70 shadow-md dark:bg-white/[0.02] dark:border-white/[0.06]">
      <div className="flex items-start gap-4 mb-4">
        <Skeleton variant="circular" width="40px" height="40px" />
        <div className="flex-1 space-y-2">
          <Skeleton width="30%" height="16px" />
          <Skeleton width="50%" height="14px" />
        </div>
      </div>
      <Skeleton width="80%" height="20px" className="mb-3" />
      <Skeleton width="100%" height="16px" className="mb-2" />
      <Skeleton width="90%" height="16px" className="mb-4" />
      <div className="flex items-center gap-4 mt-4">
        <Skeleton width="60px" height="12px" />
        <Skeleton width="60px" height="12px" />
        <Skeleton width="60px" height="12px" />
      </div>
    </div>
  )
}

export function NewsCardSkeleton() {
  return (
    <div className="rounded-2xl bg-white border border-slate-200/70 shadow-md overflow-hidden dark:bg-white/[0.02] dark:border-white/[0.06]">
      <Skeleton variant="rectangular" height="200px" animation="wave" />
      <div className="p-6 space-y-3">
        <Skeleton width="40%" height="14px" />
        <Skeleton width="90%" height="20px" />
        <Skeleton width="100%" height="16px" />
        <Skeleton width="70%" height="16px" />
        <div className="flex items-center gap-4 mt-4">
          <Skeleton width="80px" height="12px" />
          <Skeleton width="80px" height="12px" />
        </div>
      </div>
    </div>
  )
}

export function ListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="p-6 rounded-2xl bg-white border border-slate-200/70 shadow-md dark:bg-white/[0.02] dark:border-white/[0.06]">
          <div className="flex items-center justify-between mb-3">
            <Skeleton width="60%" height="20px" />
            <Skeleton width="80px" height="24px" />
          </div>
          <Skeleton width="100%" height="16px" className="mb-2" />
          <Skeleton width="85%" height="16px" />
        </div>
      ))}
    </div>
  )
}
