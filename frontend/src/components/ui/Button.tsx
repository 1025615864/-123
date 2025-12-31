import { ButtonHTMLAttributes, forwardRef, MouseEvent, useCallback, useState } from 'react'
import { LucideIcon } from 'lucide-react'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  icon?: LucideIcon
  iconPosition?: 'left' | 'right'
  isLoading?: boolean
  loadingText?: string
  fullWidth?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      icon: Icon,
      iconPosition = 'left',
      isLoading = false,
      loadingText = '加载中...',
      fullWidth = false,
      className = '',
      disabled,
      ...props
    },
    ref
  ) => {
    const { onMouseDown, ...restProps } = props

    const [ripples, setRipples] = useState<Array<{ id: string; x: number; y: number; size: number }>>([])

    const createRipple = useCallback(
      (e: MouseEvent<HTMLButtonElement>) => {
        if (disabled || isLoading) return
        const rect = e.currentTarget.getBoundingClientRect()
        const size = Math.max(rect.width, rect.height)
        const x = e.clientX - rect.left - size / 2
        const y = e.clientY - rect.top - size / 2
        const id = Math.random().toString(36).slice(2)
        setRipples((prev) => [...prev, { id, x, y, size }])
        window.setTimeout(() => {
          setRipples((prev) => prev.filter((r) => r.id !== id))
        }, 650)
      },
      [disabled, isLoading]
    )

    const baseStyles = 'inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all outline-none focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed'
    
    const variantStyles = {
      primary: 'btn-primary text-white',
      secondary: 'bg-slate-100 text-slate-900 hover:bg-slate-200 border border-slate-200 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700 dark:border-slate-700',
      outline: 'btn-outline',
      ghost: 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
      danger: 'bg-red-600 text-white hover:bg-red-700 dark:bg-red-500/20 dark:text-red-300 dark:border dark:border-red-500/30 dark:hover:bg-red-500/30'
    }
    
    const sizeStyles = {
      sm: 'px-3 py-2 text-sm',
      md: 'px-5 py-3 text-sm',
      lg: 'px-6 py-4 text-base'
    }
    
    const widthStyles = fullWidth ? 'w-full' : ''
    
    const combinedClassName = `${baseStyles} relative overflow-hidden ${variantStyles[variant]} ${sizeStyles[size]} ${widthStyles} ${className}`
    
    return (
      <button
        ref={ref}
        className={combinedClassName}
        disabled={disabled || isLoading}
        {...restProps}
        onMouseDown={(e) => {
          createRipple(e)
          onMouseDown?.(e)
        }}
      >
        {ripples.map((r) => (
          <span
            key={r.id}
            className="ripple-effect bg-white/40 dark:bg-white/25"
            style={{ width: r.size, height: r.size, left: r.x, top: r.y }}
          />
        ))}

        <span className="relative z-10 inline-flex items-center justify-center gap-2">
          {isLoading ? (
            <>
              <div className="h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
              {loadingText ? <span>{loadingText}</span> : null}
            </>
          ) : (
            <>
              {Icon && iconPosition === 'left' && <Icon className="h-5 w-5" />}
              {children}
              {Icon && iconPosition === 'right' && <Icon className="h-5 w-5" />}
            </>
          )}
        </span>
      </button>
    )
  }
)

Button.displayName = 'Button'

export default Button
