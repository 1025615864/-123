import { HTMLAttributes } from 'react'
import { LucideIcon } from 'lucide-react'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'
  size?: 'sm' | 'md' | 'lg'
  icon?: LucideIcon
}

export default function Badge({
  children,
  variant = 'default',
  size = 'md',
  icon: Icon,
  className = '',
  ...props
}: BadgeProps) {
  const baseStyles = 'inline-flex items-center gap-2 rounded-xl font-semibold border'
  
  const variantStyles = {
    default: 'bg-slate-900/5 text-slate-700 border-slate-200/70 dark:bg-white/5 dark:text-white/75 dark:border-white/10',
    primary: 'bg-amber-500/10 text-amber-700 border-amber-500/20 dark:text-amber-300',
    success: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20 dark:text-emerald-300',
    warning: 'bg-amber-500/10 text-amber-700 border-amber-500/20 dark:text-amber-300',
    danger: 'bg-red-500/10 text-red-700 border-red-500/20 dark:text-red-300',
    info: 'bg-blue-500/10 text-blue-700 border-blue-500/20 dark:text-blue-300'
  }
  
  const sizeStyles = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1.5 text-sm',
    lg: 'px-4 py-2 text-base'
  }
  
  const iconSizeStyles = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4',
    lg: 'h-5 w-5'
  }
  
  const combinedClassName = `${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`
  
  return (
    <span className={combinedClassName} {...props}>
      {Icon && <Icon className={iconSizeStyles[size]} />}
      {children}
    </span>
  )
}
