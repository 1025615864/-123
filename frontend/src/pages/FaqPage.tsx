import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { HelpCircle, ChevronDown, ChevronUp, ArrowRight, MessageSquare } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Card, Button, EmptyState, Input, ListSkeleton } from '../components/ui'
import PageHeader from '../components/PageHeader'
import api from '../api/client'
import { queryKeys } from '../queryKeys'
import { useTheme } from '../contexts/ThemeContext'
import { getApiErrorMessage } from '../utils'

interface FaqItem {
  question: string
  answer: string
}

interface FaqPublicResponse {
  items: FaqItem[]
  updated_at: string | null
}

export default function FaqPage() {
  const { actualTheme } = useTheme()
  const [expanded, setExpanded] = useState<number | null>(null)
  const [keyword, setKeyword] = useState('')

  useEffect(() => {
    setExpanded(null)
  }, [keyword])

  const faqQuery = useQuery({
    queryKey: queryKeys.publicFaq(),
    queryFn: async () => {
      const res = await api.get('/system/public/faq')
      return res.data as FaqPublicResponse
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const items = useMemo(() => {
    const data = faqQuery.data
    if (!data || !Array.isArray(data.items)) return []
    return data.items
      .map((it) => ({
        question: String((it as any)?.question || '').trim(),
        answer: String((it as any)?.answer || '').trim(),
      }))
      .filter((it) => it.question && it.answer)
  }, [faqQuery.data])

  const filteredItems = useMemo(() => {
    const kw = String(keyword || '').trim().toLowerCase()
    if (!kw) return items
    return items.filter((it) => {
      const q = String(it.question || '').toLowerCase()
      const a = String(it.answer || '').toLowerCase()
      return q.includes(kw) || a.includes(kw)
    })
  }, [items, keyword])

  const updatedAtText = useMemo(() => {
    const raw = String(faqQuery.data?.updated_at || '').trim()
    if (!raw) return ''
    const t = new Date(raw).getTime()
    if (Number.isNaN(t)) return raw
    return new Date(t).toLocaleString('zh-CN')
  }, [faqQuery.data?.updated_at])

  const errorText = faqQuery.isError ? getApiErrorMessage(faqQuery.error, 'FAQ 加载失败') : null

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="帮助中心"
        title="常见问题（FAQ）"
        description="来自真实咨询反馈的高频问答，帮助你更快了解常见法律问题"
        tone={actualTheme}
        right={
          <div className="flex items-center gap-2">
            <Link to="/feedback">
              <Button variant="outline" icon={MessageSquare}>
                提交工单
              </Button>
            </Link>
            <Link to="/chat">
              <Button icon={ArrowRight} className="bg-emerald-600 hover:bg-emerald-700 text-white focus-visible:ring-emerald-500/25">
                去咨询 AI
              </Button>
            </Link>
          </div>
        }
      />

      {faqQuery.isLoading ? (
        <ListSkeleton count={4} />
      ) : errorText ? (
        <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
          <div>{errorText}</div>
          <Button variant="outline" onClick={() => faqQuery.refetch()} isLoading={faqQuery.isFetching}>
            重试
          </Button>
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={HelpCircle}
          title="暂无 FAQ"
          description="管理员尚未生成 FAQ。你可以直接使用 AI 咨询获取帮助。"
          tone={actualTheme}
        />
      ) : (
        <div className="space-y-6">
          <Card variant="surface" padding="lg">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-lg font-semibold text-slate-900 dark:text-white">FAQ 列表</div>
                <div className="text-sm text-slate-600 mt-1 dark:text-white/50">
                  {updatedAtText ? `更新时间：${updatedAtText}` : '更新时间：—'}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" onClick={() => faqQuery.refetch()} isLoading={faqQuery.isFetching}>
                  刷新
                </Button>
              </div>
            </div>

            <div className="mt-4 flex flex-col sm:flex-row gap-3">
              <div className="flex-1">
                <Input
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="搜索问题/答案关键词..."
                  className="py-2.5"
                />
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setKeyword('')
                  setExpanded(null)
                }}
                disabled={!keyword.trim()}
              >
                清空
              </Button>
            </div>
          </Card>

          {filteredItems.length === 0 ? (
            <EmptyState
              icon={HelpCircle}
              title="未找到匹配的 FAQ"
              description="试试更换关键词，或清空筛选后查看全部"
              tone={actualTheme}
              action={
                <div className="mt-6">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setKeyword('')
                      setExpanded(null)
                    }}
                  >
                    清空筛选
                  </Button>
                </div>
              }
            />
          ) : (
            <div className="space-y-3">
              {filteredItems.map((faq, idx) => (
              <div
                key={`${idx}-${faq.question}`}
                className="rounded-xl border border-slate-200 overflow-hidden dark:border-white/10"
              >
                <button
                  type="button"
                  onClick={() => setExpanded(expanded === idx ? null : idx)}
                  aria-expanded={expanded === idx}
                  aria-controls={`faq-panel-${idx}`}
                  className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50 transition-colors dark:hover:bg-white/5"
                >
                  <span className="text-slate-900 dark:text-white text-sm font-medium pr-4">
                    {faq.question}
                  </span>
                  {expanded === idx ? (
                    <ChevronUp className="h-4 w-4 text-slate-400 dark:text-white/40 flex-shrink-0" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-slate-400 dark:text-white/40 flex-shrink-0" />
                  )}
                </button>
                {expanded === idx && (
                  <div id={`faq-panel-${idx}`} className="px-4 pb-4">
                    <div className="text-sm text-slate-600 leading-relaxed dark:text-white/60">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ children }: { children?: ReactNode }) => (
                            <p className="mt-2 first:mt-0">{children}</p>
                          ),
                          h1: ({ children }: { children?: ReactNode }) => (
                            <div className="text-base font-semibold mt-3 first:mt-0 text-slate-900 dark:text-white">{children}</div>
                          ),
                          h2: ({ children }: { children?: ReactNode }) => (
                            <div className="text-base font-semibold mt-3 first:mt-0 text-slate-900 dark:text-white">{children}</div>
                          ),
                          h3: ({ children }: { children?: ReactNode }) => (
                            <div className="text-sm font-semibold mt-3 first:mt-0 text-slate-900 dark:text-white">{children}</div>
                          ),
                          ul: ({ children }: { children?: ReactNode }) => (
                            <ul className="list-disc pl-5 mt-2 space-y-1">{children}</ul>
                          ),
                          ol: ({ children }: { children?: ReactNode }) => (
                            <ol className="list-decimal pl-5 mt-2 space-y-1">{children}</ol>
                          ),
                          li: ({ children }: { children?: ReactNode }) => (
                            <li className="">{children}</li>
                          ),
                          a: ({
                            children,
                            href,
                          }: {
                            children?: ReactNode
                            href?: string
                          }) => (
                            <a
                              href={href}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-600 hover:underline dark:text-blue-400"
                            >
                              {children}
                            </a>
                          ),
                        }}
                      >
                        {faq.answer}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}
              </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
