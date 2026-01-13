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
import { useLanguage } from '../contexts/LanguageContext'
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
  const { t } = useLanguage()
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
    typeof n === 'number' ? (n >= UNLIMITED_THRESHOLD ? t('common.unlimited') : n) : '-'
  const totalDocumentRemaining =
    (typeof documentRemaining === 'number' ? documentRemaining : 0) +
    (typeof documentPackRemaining === 'number' ? documentPackRemaining : 0)
  const isDocQuotaExhausted = isAuthenticated && !!quotasQuery.data && totalDocumentRemaining <= 0

  const markdown = useMemo(() => {
    const raw = safeText(result?.report_markdown)
    return raw.trim() ? raw : ''
  }, [result?.report_markdown])

  const normalizedTitle = useMemo(() => {
    const base = contractType
      ? `${t('contractReviewPage.reportTitle')}-${contractType}`
      : t('contractReviewPage.reportTitle')
    return base.replace(/[\\/:*?"<>|]/g, '_')
  }, [contractType, t])

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
      errorMessageFallback: t('contractReviewPage.reviewFailedRetry'),
      onSuccess: (data) => {
        setResult(data)
        toast.success(t('contractReviewPage.reviewCompleted'))
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
        toast.success(t('contractReviewPage.copiedToClipboard'))
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
      if (ok) toast.success(t('contractReviewPage.copiedToClipboard'))
      else toast.error(t('contractReviewPage.copyFailed'))
    } catch {
      toast.error(t('contractReviewPage.copyFailed'))
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
      toast.error(getApiErrorMessage(err, t('contractReviewPage.pdfPreviewFailed')))
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
      toast.success(t('contractReviewPage.pdfDownloaded'))
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('contractReviewPage.pdfExportFailed')))
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
      toast.error(t('contractReviewPage.pleaseChooseFile'))
      return
    }
    if (isDocQuotaExhausted) {
      toast.info(t('contractReviewPage.quotaExhaustedHint'))
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
        eyebrow={t('contractReviewPage.eyebrow')}
        title={t('contractReviewPage.title')}
        description={t('contractReviewPage.description')}
        tone={actualTheme}
      />

      <Card variant="surface" padding="lg">
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-slate-700 dark:text-white/80">
              <FileText className="h-4 w-4" />
              <span className="font-medium">{t('contractReviewPage.selectFile')}</span>
              <span className="text-slate-400 dark:text-white/40">{t('contractReviewPage.supportedTypes')}</span>
            </div>

            <div className="flex flex-wrap items-center gap-2">
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
                {t('contractReviewPage.chooseFile')}
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleStartReview}
                isLoading={reviewMutation.isPending}
                loadingText={t('contractReviewPage.reviewing')}
                disabled={reviewMutation.isPending || (isAuthenticated && isDocQuotaExhausted)}
              >
                {t('contractReviewPage.startReview')}
              </Button>
              <Button variant="outline" size="sm" icon={RefreshCcw} onClick={handleReset}>
                {t('contractReviewPage.reset')}
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
              <span>{t('contractReviewPage.noFileSelected')}</span>
            )}
          </div>

          {isAuthenticated ? (
            <div className="flex flex-col items-start gap-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-white/70">
                <Badge variant={isVipActive ? 'success' : 'default'} size="sm">
                  {isVipActive ? t('common.vip') : t('common.nonVip')}
                </Badge>
                <span>
                  {t('contractReviewPage.todayAvailablePrefix')}{' '}
                  <span className="font-semibold text-slate-900 dark:text-white">
                    {formatQuotaNumber(documentRemaining)}
                  </span>{' '}
                  / {formatQuotaNumber(documentLimit)}
                  {typeof documentPackRemaining === 'number' && documentPackRemaining > 0 && (
                    <>
                      <span className="text-slate-500 dark:text-white/50">{t('contractReviewPage.packPrefix')}{documentPackRemaining}{t('contractReviewPage.packSuffix')}</span>
                    </>
                  )}
                </span>
                {!isVipActive && isDocQuotaExhausted && (
                  <Link
                    to="/vip"
                    className="font-medium text-amber-700 hover:text-amber-800 dark:text-amber-300 dark:hover:text-amber-200"
                  >
                    {t('contractReviewPage.openVip')}
                  </Link>
                )}
                {isDocQuotaExhausted && (
                  <Link
                    to="/profile?buyPack=document_generate"
                    className="font-medium text-blue-600 hover:text-blue-700 dark:text-blue-300 dark:hover:text-blue-200"
                  >
                    {t('contractReviewPage.buyPack')}
                  </Link>
                )}
              </div>

              <Button
                variant="outline"
                size="sm"
                icon={RefreshCcw}
                disabled={quotasQuery.isFetching}
                isLoading={quotasQuery.isFetching}
                loadingText={t('common.refreshing')}
                onClick={() => quotasQuery.refetch()}
              >
                {t('contractReviewPage.refreshQuota')}
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-start gap-3">
              <div className="text-xs text-slate-500 dark:text-white/50">
                {t('contractReviewPage.guestHint')}
              </div>
              <div className="flex items-center gap-2">
                <Link to="/login">
                  <Button variant="outline" size="sm">
                    {t('contractReviewPage.goLogin')}
                  </Button>
                </Link>
                <Link to="/vip">
                  <Button variant="outline" size="sm">
                    {t('contractReviewPage.viewVip')}
                  </Button>
                </Link>
              </div>
            </div>
          )}

          {reviewMutation.error ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900 dark:border-rose-900/40 dark:bg-rose-900/20 dark:text-rose-100">
              {getApiErrorMessage(reviewMutation.error, t('contractReviewPage.reviewFailed'))}
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
                  <div className="text-base font-semibold text-slate-900 dark:text-white">{t('contractReviewPage.resultTitle')}</div>
                  {riskLevel ? (
                    <Badge variant={riskBadgeVariant(riskLevel)} size="sm">
                      {t('contractReviewPage.riskPrefix')}{riskLevel}
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
                  {result?.request_id ? ` · ${t('contractReviewPage.requestIdPrefix')}${result.request_id}` : ''}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  icon={Copy}
                  onClick={() => copyTextToClipboard(markdown || JSON.stringify(reportJson, null, 2))}
                >
                  {t('contractReviewPage.copyReport')}
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
                    toast.success(t('contractReviewPage.mdDownloaded'))
                  }}
                >
                  {t('contractReviewPage.downloadMd')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  icon={Eye}
                  disabled={pdfPreviewBusy}
                  onClick={handlePreviewPdf}
                >
                  {t('contractReviewPage.previewPdf')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  icon={Download}
                  disabled={pdfPreviewBusy}
                  onClick={handleDownloadPdf}
                >
                  {t('contractReviewPage.downloadPdf')}
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
        title={
          pdfPreviewTitle
            ? `${t('contractReviewPage.pdfPreviewTitlePrefix')}${pdfPreviewTitle}`
            : t('contractReviewPage.pdfPreviewTitle')
        }
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
          <div className="text-sm text-slate-500 dark:text-white/50">{t('contractReviewPage.pdfLoading')}</div>
        )}
      </Modal>
    </div>
  )
}
