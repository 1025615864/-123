import { ReactNode } from 'react'
import { Link, LinkProps } from 'react-router-dom'
import { LucideIcon } from 'lucide-react'

export interface LinkButtonProps extends Omit<LinkProps, 'className' | 'children'> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  icon?: LucideIcon
  iconPosition?: 'left' | 'right'
  fullWidth?: boolean
  disabled?: boolean
  className?: string
  children?: ReactNode
}

export default function LinkButton({
  children,
  variant = 'primary',
  size = 'md',
  icon: Icon,
  iconPosition = 'left',
  fullWidth = false,
  disabled = false,
  className = '',
  ...props
}: LinkButtonProps) {
  const baseStyles =
    'inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all outline-none focus-visible:ring-2 focus-visible:ring-amber-500/25'

  const variantStyles = {
    primary: 'btn-primary text-white',
    secondary: 'bg-slate-900/5 text-slate-900 hover:bg-slate-900/10 border border-slate-200/70 dark:bg-white/10 dark:text-white/90 dark:hover:bg-white/15 dark:border-white/10',
    outline: 'btn-outline',
    ghost: 'text-slate-700 hover:bg-slate-900/5 dark:text-white/80 dark:hover:bg-white/5',
    danger: 'bg-red-600 text-white hover:bg-red-700 dark:bg-red-500/15 dark:text-red-300 dark:border dark:border-red-500/25 dark:hover:bg-red-500/20'
  }

  const sizeStyles = {
    sm: 'px-3 py-2 text-sm',
    md: 'px-5 py-3 text-sm',
    lg: 'px-6 py-4 text-base'
  }

  const widthStyles = fullWidth ? 'w-full' : ''
  const disabledStyles = disabled ? 'opacity-50 pointer-events-none cursor-not-allowed' : ''

  const combinedClassName = `${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${widthStyles} ${disabledStyles} ${className}`

  return (
    <Link className={combinedClassName} {...props}>
      {Icon && iconPosition === 'left' && <Icon className="h-5 w-5" />}
      {children}
      {Icon && iconPosition === 'right' && <Icon className="h-5 w-5" />}
    </Link>
  )
}
