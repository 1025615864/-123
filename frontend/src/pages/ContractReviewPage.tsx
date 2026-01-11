import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, FileText, Eye, Copy, RefreshCcw } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import PageHeader from '../components/PageHeader'
import MarkdownContent from '../components/MarkdownContent'
import { Badge, Button, Card, Modal } from '../components/ui'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useToast, useAppMutation } from '../hooks'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'

type ContractReviewResponse = {
  filename: string
  content_type: string | null
  text_chars: number
  text_preview: string
  report_json: Record<string, any>
  report_markdown: string
  request_id: string
}

interface UserQuotaDailyResponse {
  day: string
  ai_chat_limit: number
  ai_chat_used: number
  ai_chat_remaining: number
  document_generate_limit: number
  document_generate_used: number
  document_generate_remaining: number
  ai_chat_pack_remaining: number
  document_generate_pack_remaining: number
  is_vip_active: boolean
}

function safeText(v: unknown): string {
  return typeof v === 'string' ? v : String(v ?? '')
}

function riskBadgeVariant(level: string): 'default' | 'warning' | 'danger' | 'success' {
  const s = level.trim().toLowerCase()
  if (s === 'high') return 'danger'
  if (s === 'medium') return 'warning'
  if (s === 'low') return 'success'
  return 'default'
}

export default function ContractReviewPage() {
  const { isAuthenticated } = useAuth()
  const { actualTheme } = useTheme()
  const toast = useToast()

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<ContractReviewResponse | null>(null)

  const [pdfPreviewOpen, setPdfPreviewOpen] = useState(false)
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null)
  const [pdfPreviewTitle, setPdfPreviewTitle] = useState<string>('')
  const [pdfPreviewBusy, setPdfPreviewBusy] = useState(false)

  const reportJson = result?.report_json ?? {}
  const contractType = safeText(reportJson?.contract_type).trim()
  const riskLevel = safeText(reportJson?.overall_risk_level || reportJson?.risk_level).trim()

  const quotasQuery = useQuery({
    queryKey: queryKeys.userMeQuotas(),
    queryFn: async () => {
      const res = await api.get('/user/me/quotas')
      return res.data as UserQuotaDailyResponse
    },
    enabled: isAuthenticated,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const documentRemaining = quotasQuery.data?.document_generate_remaining
  const documentLimit = quotasQuery.data?.document_generate_limit
  const documentPackRemaining = quotasQuery.data?.document_generate_pack_remaining
  const isVipActive = quotasQuery.data?.is_vip_active === true

  const UNLIMITED_THRESHOLD = 1_000_000
  const formatQuotaNumber = (n: unknown) =>
    typeof n === 'number' ? (n >= UNLIMITED_THRESHOLD ? '不限' : n) : '-'
  const totalDocumentRemaining =
    (typeof documentRemaining === 'number' ? documentRemaining : 0) +
    (typeof documentPackRemaining === 'number' ? documentPackRemaining : 0)
  const isDocQuotaExhausted = isAuthenticated && !!quotasQuery.data && totalDocumentRemaining <= 0

  const markdown = useMemo(() => {
    const raw = safeText(result?.report_markdown)
    return raw.trim() ? raw : ''
  }, [result?.report_markdown])

  const normalizedTitle = useMemo(() => {
    const base = contractType ? `合同审查报告-${contractType}` : '合同审查报告'
    return base.replace(/[\\/:*?"<>|]/g, '_')
  }, [contractType])

  const reviewMutation = useAppMutation<ContractReviewResponse, { file: File }>(
    {
      mutationFn: async (payload) => {
        const form = new FormData()
        form.append('file', payload.file)
        const res = await api.post('/contracts/review', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        return res.data as ContractReviewResponse
      },
      errorMessageFallback: '合同审查失败，请稍后重试',
      onSuccess: (data) => {
        setResult(data)
        toast.success('审查完成')
        if (isAuthenticated) {
          void quotasQuery.refetch()
        }
      },
      onError: (err) => {
        const status = (err as any)?.response?.status
        if (status === 429 && isAuthenticated) {
          void quotasQuery.refetch()
        }
      },
    }
  )

  const copyTextToClipboard = async (text: string) => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
        toast.success('已复制到剪贴板')
        return
      }

      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.left = '-9999px'
      textarea.style.top = '-9999px'
      document.body.appendChild(textarea)
      textarea.focus()
      textarea.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(textarea)
      if (ok) toast.success('已复制到剪贴板')
      else toast.error('复制失败')
    } catch {
      toast.error('复制失败')
    }
  }

  const downloadBlobAsFile = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const fetchPdfBlobByContent = async (title: string, content: string): Promise<Blob> => {
    const res = await api.post(
      '/documents/export/pdf',
      { title, content },
      {
        responseType: 'blob',
        headers: { Accept: 'application/pdf' },
      }
    )
    return res.data as Blob
  }

  const openPdfPreviewWithBlob = (blob: Blob, title: string) => {
    if (pdfPreviewUrl) {
      URL.revokeObjectURL(pdfPreviewUrl)
    }
    const url = URL.createObjectURL(blob)
    setPdfPreviewUrl(url)
    setPdfPreviewTitle(title)
    setPdfPreviewOpen(true)
  }

  const handlePreviewPdf = async () => {
    if (!result) return
    if (pdfPreviewBusy) return
    try {
      setPdfPreviewBusy(true)
      const blob = await fetchPdfBlobByContent(normalizedTitle, markdown || safeText(result.text_preview))
      openPdfPreviewWithBlob(blob, normalizedTitle)
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'PDF 预览失败'))
    } finally {
      setPdfPreviewBusy(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (!result) return
    if (pdfPreviewBusy) return
    try {
      setPdfPreviewBusy(true)
      const blob = await fetchPdfBlobByContent(normalizedTitle, markdown || safeText(result.text_preview))
      downloadBlobAsFile(blob, `${normalizedTitle}.pdf`)
      toast.success('PDF 已下载')
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'PDF 导出失败'))
    } finally {
      setPdfPreviewBusy(false)
    }
  }

  useEffect(() => {
    if (pdfPreviewOpen) return
    if (!pdfPreviewUrl) return
    URL.revokeObjectURL(pdfPreviewUrl)
    setPdfPreviewUrl(null)
  }, [pdfPreviewOpen, pdfPreviewUrl])

  const hasResult = Boolean(result && (markdown || Object.keys(reportJson || {}).length > 0))

  const handleStartReview = () => {
    if (!file) {
      toast.error('请先选择合同文件')
      return
    }
    if (isDocQuotaExhausted) {
      toast.info('今日合同审查次数已用完，可前往个人中心开通 VIP 或购买次数包')
      return
    }
    if (reviewMutation.isPending) return
    setResult(null)
    reviewMutation.mutate({ file })
  }

  const handleReset = () => {
    setFile(null)
    setResult(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="AI 合同审查"
        title="合同风险体检"
        description="上传合同后系统将自动提取文本并生成风险体检报告（结构化 + 可渲染 Markdown）。为保护隐私，身份证/手机号/邮箱等信息会默认脱敏处理后再发送给 AI。"
        tone={actualTheme}
      />

      <Card variant="surface" padding="lg">
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-slate-700 dark:text-white/80">
              <FileText className="h-4 w-4" />
              <span className="font-medium">选择合同文件</span>
              <span className="text-slate-400 dark:text-white/40">（PDF/DOCX/TXT/MD）</span>
            </div>

            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.docx,.txt,.md,.csv,.json,application/pdf,text/plain,text/markdown,text/csv,application/json,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(e) => {
                  const picked = e.target.files?.[0]
                  e.target.value = ''
                  if (!picked) return
                  setFile(picked)
                }}
              />
              <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                选择文件
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleStartReview}
                isLoading={reviewMutation.isPending}
                loadingText="审查中..."
                disabled={reviewMutation.isPending || (isAuthenticated && isDocQuotaExhausted)}
              >
                开始审查
              </Button>
              <Button variant="outline" size="sm" icon={RefreshCcw} onClick={handleReset}>
                重置
              </Button>
            </div>
          </div>

          <div className="text-sm text-slate-600 dark:text-white/60">
            {file ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-slate-900 dark:text-white">{file.name}</span>
                <span>·</span>
                <span>{Math.max(1, Math.round((file.size || 0) / 1024))} KB</span>
              </div>
            ) : (
              <span>尚未选择文件</span>
            )}
          </div>

          {isAuthenticated ? (
            <div className="flex flex-col items-start gap-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-white/70">
                <Badge variant={isVipActive ? 'success' : 'default'} size="sm">
                  {isVipActive ? 'VIP' : '非VIP'}
                </Badge>
                <span>
                  今日可用次数{' '}
                  <span className="font-semibold text-slate-900 dark:text-white">
                    {formatQuotaNumber(documentRemaining)}
                  </span>{' '}
                  / {formatQuotaNumber(documentLimit)}
                  {typeof documentPackRemaining === 'number' && documentPackRemaining > 0 && (
                    <>
                      <span className="text-slate-500 dark:text-white/50">（次数包 {documentPackRemaining}）</span>
                    </>
                  )}
                </span>
                {!isVipActive && isDocQuotaExhausted && (
                  <Link
                    to="/vip"
                    className="font-medium text-amber-700 hover:text-amber-800 dark:text-amber-300 dark:hover:text-amber-200"
                  >
                    开通 VIP
                  </Link>
                )}
                {isDocQuotaExhausted && (
                  <Link
                    to="/profile?buyPack=document_generate"
                    className="font-medium text-blue-600 hover:text-blue-700 dark:text-blue-300 dark:hover:text-blue-200"
                  >
                    购买次数包
                  </Link>
                )}
              </div>

              <Button
                variant="outline"
                size="sm"
                icon={RefreshCcw}
                disabled={quotasQuery.isFetching}
                isLoading={quotasQuery.isFetching}
                loadingText="刷新中..."
                onClick={() => quotasQuery.refetch()}
              >
                刷新配额
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-start gap-3">
              <div className="text-xs text-slate-500 dark:text-white/50">
                登录后可购买次数包或开通 VIP，获取更充足的使用额度
              </div>
              <div className="flex items-center gap-2">
                <Link to="/login">
                  <Button variant="outline" size="sm">
                    去登录
                  </Button>
                </Link>
                <Link to="/vip">
                  <Button variant="outline" size="sm">
                    查看 VIP
                  </Button>
                </Link>
              </div>
            </div>
          )}

          {reviewMutation.error ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900 dark:border-rose-900/40 dark:bg-rose-900/20 dark:text-rose-100">
              {getApiErrorMessage(reviewMutation.error, '合同审查失败')}
            </div>
          ) : null}
        </div>
      </Card>

      {hasResult ? (
        <Card variant="surface" padding="lg">
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-base font-semibold text-slate-900 dark:text-white">审查结果</div>
                  {riskLevel ? (
                    <Badge variant={riskBadgeVariant(riskLevel)} size="sm">
                      风险：{riskLevel}
                    </Badge>
                  ) : null}
                  {contractType ? (
                    <Badge variant="default" size="sm">
                      {contractType}
                    </Badge>
                  ) : null}
                </div>
                <div className="text-xs text-slate-500 dark:text-white/40">
                  {safeText(result?.filename)}
                  {result?.request_id ? ` · 请求ID: ${result.request_id}` : ''}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  icon={Copy}
                  onClick={() => copyTextToClipboard(markdown || JSON.stringify(reportJson, null, 2))}
                >
                  复制报告
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  icon={Download}
                  onClick={() => {
                    const blob = new Blob([markdown || JSON.stringify(reportJson, null, 2)], {
                      type: 'text/markdown;charset=utf-8',
                    })
                    downloadBlobAsFile(blob, `${normalizedTitle}.md`)
                    toast.success('Markdown 已下载')
                  }}
                >
                  下载MD
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  icon={Eye}
                  disabled={pdfPreviewBusy}
                  onClick={handlePreviewPdf}
                >
                  预览PDF
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  icon={Download}
                  disabled={pdfPreviewBusy}
                  onClick={handleDownloadPdf}
                >
                  下载PDF
                </Button>
              </div>
            </div>

            {markdown ? (
              <div className="rounded-2xl border border-slate-200/70 bg-white/60 p-4 text-sm dark:border-white/10 dark:bg-slate-900/30">
                <MarkdownContent content={markdown} className="prose prose-slate max-w-none dark:prose-invert" />
              </div>
            ) : (
              <pre className="rounded-2xl border border-slate-200/70 bg-white/60 p-4 text-xs overflow-auto dark:border-white/10 dark:bg-slate-900/30">
                {JSON.stringify(reportJson, null, 2)}
              </pre>
            )}
          </div>
        </Card>
      ) : null}

      <Modal
        isOpen={pdfPreviewOpen}
        onClose={() => {
          if (pdfPreviewBusy) return
          setPdfPreviewOpen(false)
        }}
        title={pdfPreviewTitle ? `PDF 预览：${pdfPreviewTitle}` : 'PDF 预览'}
        size="xl"
      >
        {pdfPreviewUrl ? (
          <div className="w-full">
            <iframe
              title="pdf-preview"
              src={pdfPreviewUrl}
              className="w-full h-[75vh] rounded-xl border border-slate-200 dark:border-white/10"
            />
          </div>
        ) : (
          <div className="text-sm text-slate-500 dark:text-white/50">PDF 加载中...</div>
        )}
      </Modal>
    </div>
  )
}
