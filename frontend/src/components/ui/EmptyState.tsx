import { HTMLAttributes, ReactNode } from 'react'
import { LucideIcon } from 'lucide-react'
import Card from './Card'

export interface EmptyStateProps extends HTMLAttributes<HTMLDivElement> {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
  size?: 'md' | 'lg'
  tone?: 'dark' | 'light'
  animated?: boolean
}

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  size = 'md',
  tone = 'dark',
  animated = true,
  className = '',
  ...props
}: EmptyStateProps) {
  const isLight = tone === 'light'
  const paddingStyles = {
    md: 'py-16 px-8',
    lg: 'py-20 px-12'
  }

  const iconWrapStyles = {
    md: 'w-20 h-20 rounded-3xl',
    lg: 'w-24 h-24 rounded-3xl'
  }

  const iconSizeStyles = {
    md: 'h-10 w-10',
    lg: 'h-12 w-12'
  }

  return (
    <Card
      variant="surface"
      padding="none"
      className={`${paddingStyles[size]} text-center ${isLight ? 'bg-white border border-slate-200/70' : ''} ${className}`}
      {...props}
    >
      <div className={`inline-flex items-center justify-center ${iconWrapStyles[size]} mb-6 ${
          isLight
            ? 'bg-gradient-to-br from-slate-100 to-slate-50 border border-slate-200/70'
            : 'bg-gradient-to-br from-amber-500/15 to-orange-500/10 border border-amber-500/20'
        } ${animated ? 'animate-fade-in' : ''}`}
      >
        <Icon className={`${iconSizeStyles[size]} ${
          isLight ? 'text-slate-400' : 'text-amber-400/90'
        } ${animated ? 'animate-pulse-slow' : ''}`} />
      </div>
      <h3 className={`text-xl font-semibold mb-3 ${
        isLight ? 'text-slate-900' : 'text-slate-900 dark:text-white'
      }`}>{title}</h3>
      {description && (
        <p className={`text-base leading-relaxed max-w-md mx-auto ${
          isLight ? 'text-slate-600' : 'text-slate-600 dark:text-white/50'
        }`}>{description}</p>
      )}
      {action && (
        <div className="mt-8">{action}</div>
      )}
    </Card>
  )
}
