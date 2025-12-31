import { ButtonHTMLAttributes, forwardRef } from 'react'

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean
  size?: 'sm' | 'md'
}

const Chip = forwardRef<HTMLButtonElement, ChipProps>(
  (
    {
      children,
      active = false,
      size = 'md',
      className = '',
      type = 'button',
      disabled,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium transition-all outline-none focus-visible:ring-2 focus-visible:ring-amber-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 active:scale-[0.99]'

    const sizeStyles = {
      sm: 'px-3 py-1.5 rounded-full text-sm',
      md: 'px-4 py-2 rounded-full text-sm'
    }

    const stateStyles = active
      ? 'bg-amber-500/15 text-amber-700 border border-amber-500/30 dark:bg-amber-500/20 dark:text-amber-300'
      : 'bg-white border border-slate-200/70 text-slate-600 hover:text-slate-900 hover:bg-slate-50 dark:bg-white/5 dark:border-white/10 dark:text-white/60 dark:hover:text-white dark:hover:bg-white/10 dark:hover:border-white/20'

    const disabledStyles = disabled ? 'opacity-50 cursor-not-allowed' : ''

    const combinedClassName = `${baseStyles} ${sizeStyles[size]} ${stateStyles} ${disabledStyles} ${className}`

    return (
      <button ref={ref} type={type} disabled={disabled} className={combinedClassName} {...props}>
        {children}
      </button>
    )
  }
)

Chip.displayName = 'Chip'

export default Chip
