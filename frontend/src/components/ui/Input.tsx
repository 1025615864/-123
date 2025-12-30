import { InputHTMLAttributes, forwardRef, ReactNode, useId, useMemo } from 'react'
import { LucideIcon } from 'lucide-react'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  icon?: LucideIcon
  iconPosition?: 'left' | 'right'
  right?: ReactNode
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      icon: Icon,
      iconPosition = 'left',
      right,
      className = '',
      ...props
    },
    ref
  ) => {
    const fallbackId = useId()
    const inputId = props.id ?? fallbackId
    const errorId = error ? `${inputId}-error` : undefined

    const ariaDescribedByProp = props['aria-describedby']
    const ariaInvalidProp = props['aria-invalid']
    const describedBy = useMemo(() => {
      const ids: string[] = []
      const raw = ariaDescribedByProp
      if (typeof raw === 'string' && raw.trim()) ids.push(raw.trim())
      if (errorId) ids.push(errorId)
      return ids.length > 0 ? ids.join(' ') : undefined
    }, [ariaDescribedByProp, errorId])

    const baseStyles = 'w-full px-4 py-3 rounded-lg border bg-white text-slate-900 placeholder:text-slate-400 outline-none transition focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 disabled:opacity-60 disabled:cursor-not-allowed dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500'
    const errorStyles = error ? 'border-red-500 focus-visible:border-red-500 focus-visible:ring-red-500/20' : 'border-slate-200 dark:border-slate-700'
    const iconPaddingStyles = Icon ? (iconPosition === 'left' ? 'pl-12' : 'pr-12') : ''
    const rightPaddingStyles = right && (!Icon || iconPosition === 'left') ? 'pr-12' : ''
    
    const combinedClassName = `${baseStyles} ${errorStyles} ${iconPaddingStyles} ${rightPaddingStyles} ${className}`
    
    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-slate-700 dark:text-white/70 mb-2"
          >
            {label}
          </label>
        )}
        <div className="relative">
          {Icon && (
            <div className={`absolute ${iconPosition === 'left' ? 'left-4' : 'right-4'} top-1/2 -translate-y-1/2`}>
              <Icon className="h-5 w-5 text-slate-400 dark:text-white/35" />
            </div>
          )}
          <input
            ref={ref}
            className={combinedClassName}
            {...props}
            id={inputId}
            aria-invalid={error ? true : ariaInvalidProp}
            aria-describedby={describedBy}
          />
          {right && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              {right}
            </div>
          )}
        </div>
        {error && (
          <p id={errorId} className="mt-2 text-sm text-red-400">
            {error}
          </p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'

export default Input
