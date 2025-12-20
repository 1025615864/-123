import { HTMLAttributes, forwardRef } from 'react'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'glass' | 'bordered' | 'surface'
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    {
      children,
      variant = 'default',
      hover = false,
      padding = 'md',
      className = '',
      ...props
    },
    ref
  ) => {
    const baseStyles = 'rounded-xl'
    
    const variantStyles = {
      default: 'bg-white border border-slate-200 shadow-sm hover:shadow-md dark:bg-slate-800 dark:border-slate-700 dark:shadow-slate-900/10',
      glass: 'glass',
      bordered: 'bg-white border border-slate-200 shadow-sm dark:bg-slate-800 dark:border-slate-700',
      surface: 'bg-white border border-slate-200 shadow-sm dark:bg-slate-800 dark:border-slate-700'
    }
    
    const paddingStyles = {
      none: '',
      sm: 'p-4',
      md: 'p-6',
      lg: 'p-8'
    }
    
    const hoverStyles = hover
      ? 'card-hover cursor-pointer transition-all duration-300 hover:shadow-lg hover:-translate-y-1 hover:border-blue-200 dark:hover:border-slate-600'
      : 'transition-shadow duration-300'
    
    const combinedClassName = `${baseStyles} ${variantStyles[variant]} ${paddingStyles[padding]} ${hoverStyles} ${className}`
    
    return (
      <div ref={ref} className={combinedClassName} {...props}>
        {children}
      </div>
    )
  }
)

Card.displayName = 'Card'

export default Card
