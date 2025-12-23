import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import FadeInImage from './ui/FadeInImage'

interface MarkdownContentProps {
  content: string
  className?: string
}

export default function MarkdownContent({ content, className = '' }: MarkdownContentProps) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }: any) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-amber-700 hover:underline dark:text-amber-400"
            >
              {children}
            </a>
          ),
          img: ({ src, alt }: any) => {
            const safeSrc = typeof src === 'string' ? src : ''
            if (!safeSrc) return null
            return (
              <div className="my-4">
                <FadeInImage
                  src={safeSrc}
                  alt={typeof alt === 'string' ? alt : ''}
                  wrapperClassName="w-full rounded-2xl bg-slate-900/5 dark:bg-white/5"
                  className="h-auto w-full object-contain"
                />
              </div>
            )
          },
          ul: ({ children }: any) => <ul className="list-disc pl-5 space-y-2 my-3">{children}</ul>,
          ol: ({ children }: any) => <ol className="list-decimal pl-5 space-y-2 my-3">{children}</ol>,
          blockquote: ({ children }: any) => (
            <blockquote className="border-l-4 border-amber-500/40 pl-4 py-1 my-4 text-slate-700 dark:text-white/70">
              {children}
            </blockquote>
          ),
          h1: ({ children }: any) => <h1 className="text-2xl font-bold mt-6 mb-3">{children}</h1>,
          h2: ({ children }: any) => <h2 className="text-xl font-bold mt-6 mb-3">{children}</h2>,
          h3: ({ children }: any) => <h3 className="text-lg font-semibold mt-5 mb-2">{children}</h3>,
          p: ({ children }: any) => <p className="text-slate-700 leading-relaxed my-3 dark:text-white/80">{children}</p>,
          code: ({ children }: any) => (
            <code className="px-1.5 py-0.5 rounded bg-slate-900/5 text-slate-800 dark:bg-white/10 dark:text-white/80">
              {children}
            </code>
          ),
          pre: ({ children }: any) => (
            <pre className="my-4 p-4 rounded-2xl overflow-auto bg-slate-900/5 dark:bg-white/5">
              {children}
            </pre>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
