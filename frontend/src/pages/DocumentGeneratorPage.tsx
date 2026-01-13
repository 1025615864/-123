import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Download, Copy, Check, ChevronRight, History, Trash2, Eye, RotateCcw } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { useAppMutation, useToast } from '../hooks'
import PageHeader from '../components/PageHeader'
import { useTheme } from '../contexts/ThemeContext'
import { useLanguage } from '../contexts/LanguageContext'
import { Card, Button, Input, Modal, Pagination, EmptyState, Badge, ListSkeleton, Skeleton } from '../components/ui'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'
import { useAuth } from '../contexts/AuthContext'
import { translate } from '../i18n'

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

interface DocumentType {
  type: string
  name: string
  description: string
}

type DocumentTypeFallback = { type: string; nameKey: string; descriptionKey: string }

const DOCUMENT_TYPE_FALLBACKS: DocumentTypeFallback[] = [
  {
    type: 'complaint',
    nameKey: 'documentGeneratorPage.documentTypes.complaint',
    descriptionKey: 'documentGeneratorPage.documentTypes.complaintDescription',
  },
  {
    type: 'defense',
    nameKey: 'documentGeneratorPage.documentTypes.defense',
    descriptionKey: 'documentGeneratorPage.documentTypes.defenseDescription',
  },
  {
    type: 'agreement',
    nameKey: 'documentGeneratorPage.documentTypes.agreement',
    descriptionKey: 'documentGeneratorPage.documentTypes.agreementDescription',
  },
  {
    type: 'letter',
    nameKey: 'documentGeneratorPage.documentTypes.letter',
    descriptionKey: 'documentGeneratorPage.documentTypes.letterDescription',
  },
]

type CaseTypeOption = { key: string; labelKey: string }

const CASE_TYPE_OPTIONS: CaseTypeOption[] = [
  { key: 'laborDispute', labelKey: 'documentGeneratorPage.caseTypes.laborDispute' },
  { key: 'contractDispute', labelKey: 'documentGeneratorPage.caseTypes.contractDispute' },
  { key: 'marriageFamily', labelKey: 'documentGeneratorPage.caseTypes.marriageFamily' },
  { key: 'propertyDispute', labelKey: 'documentGeneratorPage.caseTypes.propertyDispute' },
  { key: 'consumerRights', labelKey: 'documentGeneratorPage.caseTypes.consumerRights' },
  { key: 'trafficAccident', labelKey: 'documentGeneratorPage.caseTypes.trafficAccident' },
  { key: 'loanDispute', labelKey: 'documentGeneratorPage.caseTypes.loanDispute' },
  { key: 'other', labelKey: 'documentGeneratorPage.caseTypes.other' },
]

export default function DocumentGeneratorPage() {
  const { isAuthenticated } = useAuth()
  const [step, setStep] = useState(1)
  const [selectedType, setSelectedType] = useState<DocumentType | null>(null)
  const [formData, setFormData] = useState({
    case_type: '',
    plaintiff_name: '',
    defendant_name: '',
    facts: '',
    claims: '',
    evidence: '',
  })
  const [generatedDocument, setGeneratedDocument] = useState<
    { title: string; content: string; template_key?: string | null; template_version?: number | null } | null
  >(null)
  const [copied, setCopied] = useState(false)
  const toast = useToast()
  const queryClient = useQueryClient()
  const { actualTheme } = useTheme()
  const { t, language } = useLanguage()
  const locale = language === 'en' ? 'en-US' : 'zh-CN'

  const [pdfPreviewOpen, setPdfPreviewOpen] = useState(false)
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null)
  const [pdfPreviewTitle, setPdfPreviewTitle] = useState<string>('')
  const [pdfPreviewBusy, setPdfPreviewBusy] = useState(false)

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

  const aiChatRemaining = quotasQuery.data?.ai_chat_remaining
  const aiChatLimit = quotasQuery.data?.ai_chat_limit
  const documentRemaining = quotasQuery.data?.document_generate_remaining
  const documentLimit = quotasQuery.data?.document_generate_limit
  const aiChatPackRemaining = quotasQuery.data?.ai_chat_pack_remaining
  const documentPackRemaining = quotasQuery.data?.document_generate_pack_remaining
  const isVipActive = quotasQuery.data?.is_vip_active === true

  const UNLIMITED_THRESHOLD = 1_000_000
  const formatQuotaNumber = (n: unknown) =>
    typeof n === 'number' ? (n >= UNLIMITED_THRESHOLD ? t('common.unlimited') : n) : '-'
  const totalDocumentRemaining =
    (typeof documentRemaining === 'number' ? documentRemaining : 0) +
    (typeof documentPackRemaining === 'number' ? documentPackRemaining : 0)
  const isDocQuotaExhausted =
    isAuthenticated && !!quotasQuery.data && totalDocumentRemaining <= 0

  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyPage, setHistoryPage] = useState(1)
  const historyPageSize = 10
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null)
  const [activeDeleteId, setActiveDeleteId] = useState<number | null>(null)

  type MyDocItem = { id: number; document_type: string; title: string; created_at: string }
  type MyDocListResponse = { items: MyDocItem[]; total: number }
  type MyDocDetail = {
    id: number
    user_id: number
    document_type: string
    title: string
    content: string
    payload_json: string | null
    created_at: string
    updated_at: string
  }

  const typesQuery = useQuery({
    queryKey: queryKeys.documentTypes(),
    queryFn: async () => {
      const res = await api.get('/documents/types')
      return res.data as DocumentType[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!typesQuery.error) return
    toast.error(getApiErrorMessage(typesQuery.error))
  }, [typesQuery.error, toast])

  const fallbackDocumentTypes = useMemo(() => {
    return DOCUMENT_TYPE_FALLBACKS.map((it) => ({
      type: it.type,
      name: t(it.nameKey),
      description: t(it.descriptionKey),
    }))
  }, [t])

  const documentTypes =
    Array.isArray(typesQuery.data) && typesQuery.data.length > 0
      ? typesQuery.data
      : fallbackDocumentTypes

  const caseTypeOptions = useMemo(() => {
    return CASE_TYPE_OPTIONS.map((opt) => {
      const value = translate('zh', opt.labelKey)
      return { value, label: t(opt.labelKey) }
    })
  }, [t])

  const myDocsQueryKey = useMemo(
    () => queryKeys.myDocuments(historyPage, historyPageSize),
    [historyPage, historyPageSize]
  )

  const myDocsQuery = useQuery<MyDocListResponse>({
    queryKey: myDocsQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('page', String(historyPage))
      params.append('page_size', String(historyPageSize))
      const res = await api.get(`/documents/my?${params.toString()}`)
      return res.data as MyDocListResponse
    },
    enabled: isAuthenticated && historyOpen,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev ?? ({ items: [], total: 0 } satisfies MyDocListResponse),
  })

  const myDocDetailQuery = useQuery<MyDocDetail>({
    queryKey: useMemo(() => queryKeys.myDocumentDetail(selectedDocId), [selectedDocId]),
    queryFn: async () => {
      const res = await api.get(`/documents/my/${selectedDocId}`)
      return res.data as MyDocDetail
    },
    enabled: isAuthenticated && historyOpen && typeof selectedDocId === 'number' && selectedDocId > 0,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!myDocsQuery.error) return
    toast.error(getApiErrorMessage(myDocsQuery.error, t('documentGeneratorPage.historyLoadFailed')))
  }, [myDocsQuery.error, toast])

  useEffect(() => {
    if (!myDocDetailQuery.error) return
    toast.error(getApiErrorMessage(myDocDetailQuery.error, t('documentGeneratorPage.detailLoadFailed')))
  }, [myDocDetailQuery.error, toast])

  const myDocsData: MyDocListResponse = myDocsQuery.data ?? ({ items: [], total: 0 } satisfies MyDocListResponse)
  const myDocsItems = myDocsData.items ?? []

  const generateMutation = useAppMutation<
    { title: string; content: string; template_key?: string | null; template_version?: number | null },
    void
  >({
    mutationFn: async (_: void) => {
      const res = await api.post('/documents/generate', {
        document_type: selectedType?.type,
        ...formData,
      })
      return res.data as { title: string; content: string; template_key?: string | null; template_version?: number | null }
    },
    errorMessageFallback: t('documentGeneratorPage.generateFailedRetry'),
    onSuccess: (response) => {
      setGeneratedDocument({
        title: response.title,
        content: response.content,
        template_key: response.template_key,
        template_version: response.template_version,
      })
      setStep(3)

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
  })

  const handleSelectType = (type: DocumentType) => {
    setSelectedType(type)
    setStep(2)
  }

  const saveMutation = useAppMutation<{ id: number; message?: string }, void>({
    mutationFn: async (_: void) => {
      if (!selectedType || !generatedDocument) {
        throw new Error('NO_DOCUMENT')
      }
      const res = await api.post('/documents/save', {
        document_type: selectedType.type,
        title: generatedDocument.title,
        content: generatedDocument.content,
        template_key: generatedDocument.template_key ?? selectedType.type,
        template_version: generatedDocument.template_version ?? null,
        payload: {
          case_type: formData.case_type,
          plaintiff_name: formData.plaintiff_name,
          defendant_name: formData.defendant_name,
          facts: formData.facts,
          claims: formData.claims,
          evidence: formData.evidence,
        },
      })
      return res.data as { id: number; message?: string }
    },
    errorMessageFallback: t('documentGeneratorPage.saveFailedRetry'),
    invalidateQueryKeys: [myDocsQueryKey as any],
    onSuccess: (res) => {
      toast.success(res?.message ?? t('documentGeneratorPage.savedToMyDocuments'))
    },
    onError: (err) => {
      const msg = String(err instanceof Error ? err.message : '')
      if (msg === 'NO_DOCUMENT') {
        toast.error(t('documentGeneratorPage.pleaseGenerateFirst'))
      }
    },
  })

  const deleteMutation = useAppMutation<unknown, number>({
    mutationFn: async (id) => {
      await api.delete(`/documents/my/${id}`)
    },
    errorMessageFallback: t('documentGeneratorPage.deleteFailedRetry'),
    invalidateQueryKeys: [myDocsQueryKey as any],
    onMutate: async (id) => {
      setActiveDeleteId(id)
      const previous = queryClient.getQueryData<MyDocListResponse>(myDocsQueryKey as any)
      queryClient.setQueryData<MyDocListResponse>(myDocsQueryKey as any, (old) => {
        if (!old) return old
        return {
          ...old,
          items: (old.items ?? []).filter((it) => it.id !== id),
          total: Math.max(0, Number(old.total || 0) - 1),
        }
      })
      if (selectedDocId === id) {
        setSelectedDocId(null)
      }
      return { previous }
    },
    onSuccess: () => {
      toast.success(t('documentGeneratorPage.deleted'))
    },
    onError: (err, _id, ctx) => {
      if (ctx && typeof ctx === 'object') {
        const anyCtx = ctx as any
        if (anyCtx.previous !== undefined) {
          queryClient.setQueryData(myDocsQueryKey as any, anyCtx.previous)
        }
      }
      return err as any
    },
    onSettled: (_data, _err, id) => {
      setActiveDeleteId((prev) => (prev === id ? null : prev))
    },
  })

  const historyBusy = deleteMutation.isPending

  const handleGenerate = async () => {
    if (!selectedType) return

    if (isDocQuotaExhausted) {
      toast.info(t('documentGeneratorPage.quotaExhaustedHint'))
      return
    }

    if (generateMutation.isPending) return
    generateMutation.mutate()
  }

  const handleCopy = async () => {
    if (!generatedDocument) return
    try {
      await navigator.clipboard.writeText(generatedDocument.content)
      setCopied(true)
      toast.success(t('documentGeneratorPage.copiedToClipboard'))
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error(t('documentGeneratorPage.copyFailed'))
    }
  }

  const handleDownload = () => {
    if (!generatedDocument) return
    const blob = new Blob([generatedDocument.content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${generatedDocument.title}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.success(t('documentGeneratorPage.fileDownloaded'))
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

  const fetchPdfBlobByDocId = async (docId: number): Promise<Blob> => {
    const res = await api.get(`/documents/my/${docId}/export`, {
      params: { format: 'pdf' },
      responseType: 'blob',
      headers: { Accept: 'application/pdf' },
    })
    return res.data as Blob
  }

  const handleDownloadPdfForGenerated = async () => {
    if (!generatedDocument) return
    try {
      const blob = await fetchPdfBlobByContent(generatedDocument.title, generatedDocument.content)
      downloadBlobAsFile(blob, `${generatedDocument.title}.pdf`)
      toast.success(t('documentGeneratorPage.pdfDownloaded'))
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('documentGeneratorPage.pdfExportFailed')))
    }
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

  const handlePreviewPdfForGenerated = async () => {
    if (!generatedDocument) return
    if (pdfPreviewBusy) return
    try {
      setPdfPreviewBusy(true)
      const blob = await fetchPdfBlobByContent(generatedDocument.title, generatedDocument.content)
      openPdfPreviewWithBlob(blob, generatedDocument.title)
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('documentGeneratorPage.pdfPreviewFailed')))
    } finally {
      setPdfPreviewBusy(false)
    }
  }

  const handleDownloadPdfForMyDoc = async () => {
    const docId = selectedDocId
    if (typeof docId !== 'number' || docId <= 0) return
    const title = String(myDocDetailQuery.data?.title ?? t('documentGeneratorPage.documentTitleFallback'))
    try {
      const blob = await fetchPdfBlobByDocId(docId)
      downloadBlobAsFile(blob, `${title}.pdf`)
      toast.success(t('documentGeneratorPage.pdfDownloaded'))
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('documentGeneratorPage.pdfExportFailed')))
    }
  }

  const handlePreviewPdfForMyDoc = async () => {
    const docId = selectedDocId
    if (typeof docId !== 'number' || docId <= 0) return
    if (pdfPreviewBusy) return
    const title = String(myDocDetailQuery.data?.title ?? t('documentGeneratorPage.documentTitleFallback'))
    try {
      setPdfPreviewBusy(true)
      const blob = await fetchPdfBlobByDocId(docId)
      openPdfPreviewWithBlob(blob, title)
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('documentGeneratorPage.pdfPreviewFailed')))
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

  const handleReset = () => {
    setStep(1)
    setSelectedType(null)
    setFormData({
      case_type: '',
      plaintiff_name: '',
      defendant_name: '',
      facts: '',
      claims: '',
      evidence: '',
    })
    setGeneratedDocument(null)
  }

  return (
    <div className="w-full space-y-10">
      <PageHeader
        eyebrow={t('documentGeneratorPage.eyebrow')}
        title={t('documentGeneratorPage.title')}
        description={t('documentGeneratorPage.description')}
        layout="mdStart"
        tone={actualTheme}
        right={
          isAuthenticated ? (
            <div className="flex flex-col items-start gap-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-white/70">
                <Badge variant={isVipActive ? 'success' : 'default'} size="sm">
                  {isVipActive ? t('common.vip') : t('common.nonVip')}
                </Badge>
                <span>
                  {t('documentGeneratorPage.todayDocumentsRemainingPrefix')}{' '}
                  <span className="font-semibold text-slate-900 dark:text-white">
                    {formatQuotaNumber(documentRemaining)}
                  </span>{' '}
                  / {formatQuotaNumber(documentLimit)} {t('documentGeneratorPage.times')}
                  {typeof documentPackRemaining === 'number' && documentPackRemaining > 0 && (
                    <>
                      <span className="text-slate-500 dark:text-white/50">{t('documentGeneratorPage.packPrefix')}{documentPackRemaining}{t('documentGeneratorPage.packSuffix')}</span>
                    </>
                  )}
                  <span className="text-slate-500 dark:text-white/50"> · </span>
                  {t('documentGeneratorPage.todayAiRemainingPrefix')}{' '}
                  <span className="font-semibold text-slate-900 dark:text-white">
                    {formatQuotaNumber(aiChatRemaining)}
                  </span>{' '}
                  / {formatQuotaNumber(aiChatLimit)} {t('documentGeneratorPage.times')}
                  {typeof aiChatPackRemaining === 'number' && aiChatPackRemaining > 0 && (
                    <>
                      <span className="text-slate-500 dark:text-white/50">{t('documentGeneratorPage.packPrefix')}{aiChatPackRemaining}{t('documentGeneratorPage.packSuffix')}</span>
                    </>
                  )}
                </span>
                {!isVipActive && isDocQuotaExhausted && (
                  <Link
                    to="/profile"
                    className="font-medium text-amber-700 hover:text-amber-800 dark:text-amber-300 dark:hover:text-amber-200"
                  >
                    {t('documentGeneratorPage.openVip')}
                  </Link>
                )}
                {isDocQuotaExhausted && (
                  <Link
                    to="/profile"
                    className="font-medium text-blue-600 hover:text-blue-700 dark:text-blue-300 dark:hover:text-blue-200"
                  >
                    {t('documentGeneratorPage.buyPack')}
                  </Link>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  icon={RotateCcw}
                  isLoading={quotasQuery.isFetching}
                  loadingText={t('common.refreshing')}
                  onClick={() => quotasQuery.refetch()}
                >
                  {t('documentGeneratorPage.refreshQuota')}
                </Button>
                <Link to="/profile">
                  <Button variant="outline" size="sm">
                    {t('documentGeneratorPage.profile')}
                  </Button>
                </Link>
                <Button variant="outline" size="sm" onClick={() => setHistoryOpen(true)} icon={History}>
                  {t('documentGeneratorPage.myDocuments')}
                </Button>
              </div>
            </div>
          ) : undefined
        }
      />

      {/* 步骤指示器 */}
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-3">
        {[t('documentGeneratorPage.stepSelectType'), t('documentGeneratorPage.stepFillInfo'), t('documentGeneratorPage.stepGenerate')].map((label, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step > idx + 1 
                ? 'bg-green-500 text-white' 
                : step === idx + 1 
                  ? 'bg-amber-500 text-white' 
                  : 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-white/50'
            }`}>
              {step > idx + 1 ? <Check className="h-4 w-4" /> : idx + 1}
            </div>
            <span className={`text-sm ${step >= idx + 1 ? 'text-slate-700 dark:text-white' : 'text-slate-400 dark:text-white/40'}`}>
              {label}
            </span>
            {idx < 2 && <ChevronRight className="h-4 w-4 text-slate-300 dark:text-white/30" />}
          </div>
        ))}
      </div>

      {/* 步骤1: 选择文书类型 */}
      {step === 1 && (
        <div className="grid md:grid-cols-2 gap-6">
          {documentTypes.map((type) => (
            <button
              key={type.type}
              onClick={() => handleSelectType(type)}
              className="text-left p-6 rounded-2xl bg-white border border-slate-200 hover:border-amber-300 hover:bg-amber-50/40 transition-all group dark:bg-white/5 dark:border-white/10 dark:hover:border-amber-500/50 dark:hover:bg-white/10"
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center flex-shrink-0">
                  <FileText className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 group-hover:text-amber-700 transition-colors dark:text-white dark:group-hover:text-amber-400">
                    {type.name}
                  </h3>
                  <p className="text-sm text-slate-600 mt-1 dark:text-white/50">{type.description}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* 步骤2: 填写信息 */}
      {step === 2 && selectedType && (
        <Card variant="surface" padding="lg" className="max-w-2xl mx-auto">
          <h3 className="text-xl font-semibold text-slate-900 mb-6 dark:text-white">
            {`${t('documentGeneratorPage.fillInfoTitlePrefix')}${selectedType.name}${t('documentGeneratorPage.fillInfoTitleSuffix')}`}
          </h3>
          
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">{t('documentGeneratorPage.caseType')}</label>
              <div className="flex flex-wrap gap-2">
                {caseTypeOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setFormData({ ...formData, case_type: opt.value })}
                    className={`px-4 py-2 rounded-full text-sm transition-all ${
                      formData.case_type === opt.value
                        ? 'bg-amber-500 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-white/5 dark:text-white/70 dark:hover:bg-white/10'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <Input
                label={
                  selectedType.type === 'agreement'
                    ? t('documentGeneratorPage.partyAName')
                    : t('documentGeneratorPage.plaintiffName')
                }
                value={formData.plaintiff_name}
                onChange={(e) => setFormData({ ...formData, plaintiff_name: e.target.value })}
                placeholder={t('documentGeneratorPage.namePlaceholder')}
              />
              <Input
                label={
                  selectedType.type === 'agreement'
                    ? t('documentGeneratorPage.partyBName')
                    : t('documentGeneratorPage.defendantName')
                }
                value={formData.defendant_name}
                onChange={(e) => setFormData({ ...formData, defendant_name: e.target.value })}
                placeholder={t('documentGeneratorPage.namePlaceholder')}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">{t('documentGeneratorPage.facts')}</label>
              <textarea
                value={formData.facts}
                onChange={(e) => setFormData({ ...formData, facts: e.target.value })}
                rows={4}
                className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 outline-none resize-none focus:border-amber-500/50 focus:ring-2 focus:ring-amber-500/10 dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:placeholder:text-white/40"
                placeholder={t('documentGeneratorPage.factsPlaceholder')}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                {selectedType.type === 'complaint'
                  ? t('documentGeneratorPage.claimsComplaint')
                  : selectedType.type === 'defense'
                  ? t('documentGeneratorPage.claimsDefense')
                  : selectedType.type === 'agreement'
                  ? t('documentGeneratorPage.claimsAgreement')
                  : t('documentGeneratorPage.claimsLegalDemand')}
              </label>
              <textarea
                value={formData.claims}
                onChange={(e) => setFormData({ ...formData, claims: e.target.value })}
                rows={3}
                className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 outline-none resize-none focus:border-amber-500/50 focus:ring-2 focus:ring-amber-500/10 dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:placeholder:text-white/40"
                placeholder={t('documentGeneratorPage.claimsPlaceholder')}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">{t('documentGeneratorPage.evidenceOptional')}</label>
              <textarea
                value={formData.evidence}
                onChange={(e) => setFormData({ ...formData, evidence: e.target.value })}
                rows={2}
                className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 outline-none resize-none focus:border-amber-500/50 focus:ring-2 focus:ring-amber-500/10 dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:placeholder:text-white/40"
                placeholder={t('documentGeneratorPage.evidencePlaceholder')}
              />
            </div>

            <div className="flex gap-4 pt-4">
              <Button variant="outline" onClick={() => setStep(1)}>
                {t('common.back')}
              </Button>
              <Button 
                onClick={handleGenerate} 
                disabled={!formData.case_type || !formData.plaintiff_name || !formData.defendant_name || !formData.facts || !formData.claims || generateMutation.isPending || isDocQuotaExhausted}
                isLoading={generateMutation.isPending}
                loadingText={t('documentGeneratorPage.generating')}
                className="flex-1"
              >
                {t('documentGeneratorPage.generateDocument')}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 步骤3: 显示生成的文书 */}
      {step === 3 && generatedDocument && (
        <Card variant="surface" padding="lg" className="max-w-3xl mx-auto">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
            <h3 className="text-xl font-semibold text-slate-900 dark:text-white">{generatedDocument.title}</h3>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleCopy} icon={copied ? Check : Copy}>
                {copied ? t('documentGeneratorPage.copied') : t('documentGeneratorPage.copy')}
              </Button>
              <Button variant="outline" size="sm" onClick={handleDownload} icon={Download}>
                {t('documentGeneratorPage.downloadTxt')}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handlePreviewPdfForGenerated}
                disabled={pdfPreviewBusy}
                icon={Eye}
              >
                {t('documentGeneratorPage.previewPdf')}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadPdfForGenerated}
                disabled={pdfPreviewBusy}
                icon={Download}
              >
                {t('documentGeneratorPage.downloadPdf')}
              </Button>
              {isAuthenticated ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (saveMutation.isPending) return
                    saveMutation.mutate()
                  }}
                  disabled={saveMutation.isPending}
                  isLoading={saveMutation.isPending}
                  loadingText={t('documentGeneratorPage.saving')}
                >
                  {t('common.save')}
                </Button>
              ) : null}
            </div>
          </div>
          
          <div className="bg-slate-50 rounded-xl p-6 border border-slate-200 dark:bg-white/5 dark:border-white/10">
            <pre className="text-slate-800 whitespace-pre-wrap font-sans text-sm leading-relaxed dark:text-white/90">
              {generatedDocument.content}
            </pre>
          </div>

          <div className="mt-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
            <p className="text-amber-700 text-sm dark:text-amber-400">
              {t('documentGeneratorPage.disclaimer')}
            </p>
          </div>

          <div className="flex gap-4 mt-6">
            <Button variant="outline" onClick={handleReset}>
              {t('documentGeneratorPage.regenerate')}
            </Button>
          </div>
        </Card>
      )}

      <Modal
        isOpen={historyOpen}
        onClose={() => {
          if (historyBusy) return
          setHistoryOpen(false)
          setSelectedDocId(null)
        }}
        title={t('documentGeneratorPage.myDocuments')}
        size="lg"
      >
        <div className="flex items-center justify-end mb-3">
          <Button
            variant="outline"
            size="sm"
            icon={RotateCcw}
            isLoading={myDocsQuery.isFetching}
            loadingText={t('common.refreshing')}
            disabled={myDocsQuery.isFetching || historyBusy}
            onClick={() => myDocsQuery.refetch()}
          >
            {t('common.refresh')}
          </Button>
        </div>

        {myDocsQuery.isLoading && myDocsItems.length === 0 ? (
          <ListSkeleton count={3} />
        ) : myDocsItems.length === 0 ? (
          <EmptyState
            icon={FileText}
            title={t('documentGeneratorPage.noSavedTitle')}
            description={t('documentGeneratorPage.noSavedDescription')}
            tone={actualTheme}
          />
        ) : (
          <div className="space-y-4">
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {myDocsItems.map((item) => {
                const deleteLoading = deleteMutation.isPending && activeDeleteId === item.id
                const disableOther = historyBusy && !deleteLoading
                return (
                  <div key={item.id} className="py-3 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-slate-900 dark:text-white truncate">
                        {item.title}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-white/45 mt-1">
                        {new Date(item.created_at).toLocaleString(locale)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={Eye}
                        onClick={() => {
                          if (historyBusy) return
                          setSelectedDocId(item.id)
                        }}
                        disabled={disableOther}
                      >
                        {t('common.view')}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={Trash2}
                        className="text-red-600"
                        onClick={() => {
                          if (historyBusy) return
                          if (!confirm(t('documentGeneratorPage.deleteConfirm'))) return
                          deleteMutation.mutate(item.id)
                        }}
                        isLoading={deleteLoading}
                        loadingText={t('documentGeneratorPage.deleting')}
                        disabled={disableOther || deleteLoading}
                      >
                        {t('common.delete')}
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>

            <Pagination
              currentPage={historyPage}
              totalPages={Math.max(1, Math.ceil(Number(myDocsQuery.data?.total ?? 0) / historyPageSize))}
              onPageChange={(p) => {
                if (historyBusy) return
                setHistoryPage(p)
              }}
            />

            {selectedDocId != null ? (
              <Card variant="surface" padding="md">
                {myDocDetailQuery.isFetching && !myDocDetailQuery.data ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <Skeleton width="60%" height="16px" />
                      <Skeleton width="72px" height="32px" />
                    </div>
                    <Skeleton width="100%" height="14px" />
                    <Skeleton width="92%" height="14px" />
                    <Skeleton width="86%" height="14px" />
                  </div>
                ) : myDocDetailQuery.data ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-semibold text-slate-900 dark:text-white truncate">
                        {myDocDetailQuery.data.title}
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          icon={Download}
                          onClick={() => {
                            const blob = new Blob([myDocDetailQuery.data?.content ?? ''], { type: 'text/plain;charset=utf-8' })
                            downloadBlobAsFile(blob, `${myDocDetailQuery.data.title}.txt`)
                            toast.success(t('documentGeneratorPage.fileDownloaded'))
                          }}
                        >
                          {t('documentGeneratorPage.downloadTxt')}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          icon={Eye}
                          onClick={handlePreviewPdfForMyDoc}
                          disabled={pdfPreviewBusy}
                        >
                          {t('documentGeneratorPage.previewPdf')}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          icon={Download}
                          onClick={handleDownloadPdfForMyDoc}
                          disabled={pdfPreviewBusy}
                        >
                          {t('documentGeneratorPage.downloadPdf')}
                        </Button>
                      </div>
                    </div>
                    <pre className="whitespace-pre-wrap text-sm text-slate-800 dark:text-white/90">{myDocDetailQuery.data.content}</pre>
                  </div>
                ) : (
                  <div className="text-sm text-slate-500 dark:text-white/50">{t('documentGeneratorPage.detailNotFound')}</div>
                )}
              </Card>
            ) : null}
          </div>
        )}
      </Modal>

      <Modal
        isOpen={pdfPreviewOpen}
        onClose={() => {
          if (pdfPreviewBusy) return
          setPdfPreviewOpen(false)
        }}
        title={pdfPreviewTitle ? `${t('documentGeneratorPage.pdfPreviewTitlePrefix')}${pdfPreviewTitle}` : t('documentGeneratorPage.pdfPreviewTitle')}
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
          <div className="text-sm text-slate-500 dark:text-white/50">{t('documentGeneratorPage.pdfLoading')}</div>
        )}
      </Modal>
    </div>
  )
}
