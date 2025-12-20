import { TextareaHTMLAttributes, forwardRef } from 'react'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      label,
      error,
      className = '',
      ...props
    },
    ref
  ) => {
    const baseStyles = 'w-full px-4 py-3 rounded-xl border bg-white text-slate-900 placeholder:text-slate-400 outline-none transition resize-none focus-visible:border-amber-500/50 focus-visible:ring-2 focus-visible:ring-amber-500/20 disabled:opacity-60 disabled:cursor-not-allowed dark:bg-white/5 dark:text-white dark:placeholder:text-white/30'
    const errorStyles = error ? 'border-red-500/60 focus-visible:border-red-500/60 focus-visible:ring-red-500/20' : 'border-slate-200/70 dark:border-white/10'
    
    const combinedClassName = `${baseStyles} ${errorStyles} ${className}`
    
    return (
      <div className="w-full">
        {label && (
          <label className="block text-sm font-medium text-slate-700 dark:text-white/70 mb-2">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          className={combinedClassName}
          {...props}
        />
        {error && (
          <p className="mt-2 text-sm text-red-400">{error}</p>
        )}
      </div>
    )
  }
)

Textarea.displayName = 'Textarea'

export default Textarea
