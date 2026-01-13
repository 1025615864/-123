import { ReactNode } from 'react'

type PageHeaderLayout = 'mdStart' | 'mdCenter' | 'lgEnd'

export interface PageHeaderProps {
  eyebrow?: string
  title: string
  description?: string
  right?: ReactNode
  layout?: PageHeaderLayout
  tone?: 'dark' | 'light'
  className?: string
}

export default function PageHeader({
  eyebrow,
  title,
  description,
  right,
  layout = 'mdStart',
  tone = 'dark',
  className = ''
}: PageHeaderProps) {
  const layoutStyles: Record<PageHeaderLayout, string> = {
    mdStart: 'flex flex-col md:flex-row md:items-start md:justify-between gap-6',
    mdCenter: 'flex flex-col md:flex-row md:items-center md:justify-between gap-4',
    lgEnd: 'flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6'
  }

  return (
    <div className={`${layoutStyles[layout]} ${className}`}>
      <div className="min-w-0">
        {eyebrow && (
          <p
            className={`${
              tone === 'light' ? 'text-amber-700' : 'text-amber-400'
            } text-xs font-semibold tracking-widest uppercase mb-2`}
          >
            {eyebrow}
          </p>
        )}
        <h1
          className={`text-3xl md:text-4xl font-bold mb-3 leading-tight tracking-tight ${
            tone === 'light' ? 'text-slate-900' : 'text-white'
          }`}
        >
          {title}
        </h1>
        {description && (
          <p
            className={`${tone === 'light' ? 'text-slate-600' : 'text-white/50'} max-w-xl text-sm md:text-base leading-relaxed`}
          >
            {description}
          </p>
        )}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  )
}
