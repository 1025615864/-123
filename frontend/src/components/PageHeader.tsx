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
    mdStart: 'flex flex-col md:flex-row md:items-start md:justify-between gap-8',
    mdCenter: 'flex flex-col md:flex-row md:items-center md:justify-between gap-4',
    lgEnd: 'flex flex-col lg:flex-row lg:items-end lg:justify-between gap-8'
  }

  return (
    <div className={`${layoutStyles[layout]} ${className}`}>
      <div>
        {eyebrow && (
          <p
            className={`${
              tone === 'light' ? 'text-emerald-700' : 'text-amber-400'
            } text-sm font-medium tracking-wider uppercase mb-3`}
          >
            {eyebrow}
          </p>
        )}
        <h1
          className={`text-3xl md:text-4xl font-bold mb-4 ${
            tone === 'light' ? 'text-gray-900' : 'text-white'
          }`}
        >
          {title}
        </h1>
        {description && (
          <p className={`${tone === 'light' ? 'text-gray-600' : 'text-white/50'} max-w-md`}>
            {description}
          </p>
        )}
      </div>
      {right && <div>{right}</div>}
    </div>
  )
}
