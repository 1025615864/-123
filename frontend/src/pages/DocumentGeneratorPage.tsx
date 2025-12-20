import { useEffect, useState } from 'react'
import { FileText, Download, Copy, Check, ChevronRight } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { useAppMutation, useToast } from '../hooks'
import PageHeader from '../components/PageHeader'
import { useTheme } from '../contexts/ThemeContext'
import { Card, Button, Input } from '../components/ui'
import { getApiErrorMessage } from '../utils'
import { queryKeys } from '../queryKeys'

interface DocumentType {
  type: string
  name: string
  description: string
}

const DOCUMENT_TYPES: DocumentType[] = [
  { type: 'complaint', name: '民事起诉状', description: '向法院提起民事诉讼的文书' },
  { type: 'defense', name: '民事答辩状', description: '被告针对原告诉讼请求的答辩文书' },
  { type: 'agreement', name: '和解协议书', description: '双方达成和解的协议文书' },
  { type: 'letter', name: '律师函', description: '以律师名义发出的法律文书' },
]

const CASE_TYPES = [
  '劳动纠纷', '合同纠纷', '婚姻家庭', '房产纠纷', 
  '消费维权', '交通事故', '借贷纠纷', '其他'
]

export default function DocumentGeneratorPage() {
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
  const [generatedDocument, setGeneratedDocument] = useState<{title: string; content: string} | null>(null)
  const [copied, setCopied] = useState(false)
  const toast = useToast()
  const { actualTheme } = useTheme()

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

  const documentTypes = Array.isArray(typesQuery.data) && typesQuery.data.length > 0 ? typesQuery.data : DOCUMENT_TYPES

  const generateMutation = useAppMutation<{ title: string; content: string }, void>({
    mutationFn: async (_: void) => {
      const res = await api.post('/documents/generate', {
        document_type: selectedType?.type,
        ...formData,
      })
      return res.data as { title: string; content: string }
    },
    errorMessageFallback: '生成失败，请稍后重试',
    onSuccess: (response) => {
      setGeneratedDocument({ title: response.title, content: response.content })
      setStep(3)
    },
  })

  const handleSelectType = (type: DocumentType) => {
    setSelectedType(type)
    setStep(2)
  }

  const handleGenerate = async () => {
    if (!selectedType) return

    if (generateMutation.isPending) return
    generateMutation.mutate()
  }

  const handleCopy = async () => {
    if (!generatedDocument) return
    try {
      await navigator.clipboard.writeText(generatedDocument.content)
      setCopied(true)
      toast.success('已复制到剪贴板')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('复制失败')
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
    toast.success('文件已下载')
  }

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
    <div className="w-full space-y-12">
      <PageHeader
        eyebrow="智能工具"
        title="法律文书生成"
        description="快速生成常用法律文书模板，仅供参考，正式使用前请咨询专业律师。"
        layout="mdStart"
        tone={actualTheme}
      />

      {/* 步骤指示器 */}
      <div className="flex items-center justify-center gap-4">
        {['选择类型', '填写信息', '生成文书'].map((label, idx) => (
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
            填写{selectedType.name}信息
          </h3>
          
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">案件类型</label>
              <div className="flex flex-wrap gap-2">
                {CASE_TYPES.map((caseType) => (
                  <button
                    key={caseType}
                    onClick={() => setFormData({ ...formData, case_type: caseType })}
                    className={`px-4 py-2 rounded-full text-sm transition-all ${
                      formData.case_type === caseType
                        ? 'bg-amber-500 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-white/5 dark:text-white/70 dark:hover:bg-white/10'
                    }`}
                  >
                    {caseType}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <Input
                label={selectedType.type === 'agreement' ? '甲方姓名' : '原告姓名'}
                value={formData.plaintiff_name}
                onChange={(e) => setFormData({ ...formData, plaintiff_name: e.target.value })}
                placeholder="请输入姓名"
              />
              <Input
                label={selectedType.type === 'agreement' ? '乙方姓名' : '被告姓名'}
                value={formData.defendant_name}
                onChange={(e) => setFormData({ ...formData, defendant_name: e.target.value })}
                placeholder="请输入姓名"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">案件事实</label>
              <textarea
                value={formData.facts}
                onChange={(e) => setFormData({ ...formData, facts: e.target.value })}
                rows={4}
                className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 outline-none resize-none focus:border-amber-500/50 focus:ring-2 focus:ring-amber-500/10 dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:placeholder:text-white/40"
                placeholder="请详细描述案件事实经过..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                {selectedType.type === 'complaint' ? '诉讼请求' : 
                 selectedType.type === 'defense' ? '答辩意见' :
                 selectedType.type === 'agreement' ? '协议内容' : '法律要求'}
              </label>
              <textarea
                value={formData.claims}
                onChange={(e) => setFormData({ ...formData, claims: e.target.value })}
                rows={3}
                className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 outline-none resize-none focus:border-amber-500/50 focus:ring-2 focus:ring-amber-500/10 dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:placeholder:text-white/40"
                placeholder="请输入具体请求或要求..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">证据说明（选填）</label>
              <textarea
                value={formData.evidence}
                onChange={(e) => setFormData({ ...formData, evidence: e.target.value })}
                rows={2}
                className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 outline-none resize-none focus:border-amber-500/50 focus:ring-2 focus:ring-amber-500/10 dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:placeholder:text-white/40"
                placeholder="列举相关证据材料..."
              />
            </div>

            <div className="flex gap-4 pt-4">
              <Button variant="outline" onClick={() => setStep(1)}>
                返回
              </Button>
              <Button 
                onClick={handleGenerate} 
                disabled={!formData.case_type || !formData.plaintiff_name || !formData.defendant_name || !formData.facts || !formData.claims || generateMutation.isPending}
                isLoading={generateMutation.isPending}
                className="flex-1"
              >
                生成文书
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 步骤3: 显示生成的文书 */}
      {step === 3 && generatedDocument && (
        <Card variant="surface" padding="lg" className="max-w-3xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-slate-900 dark:text-white">{generatedDocument.title}</h3>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleCopy}>
                {copied ? <Check className="h-4 w-4 mr-2" /> : <Copy className="h-4 w-4 mr-2" />}
                {copied ? '已复制' : '复制'}
              </Button>
              <Button variant="outline" size="sm" onClick={handleDownload}>
                <Download className="h-4 w-4 mr-2" />
                下载
              </Button>
            </div>
          </div>
          
          <div className="bg-slate-50 rounded-xl p-6 border border-slate-200 dark:bg-white/5 dark:border-white/10">
            <pre className="text-slate-800 whitespace-pre-wrap font-sans text-sm leading-relaxed dark:text-white/90">
              {generatedDocument.content}
            </pre>
          </div>

          <div className="mt-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
            <p className="text-amber-700 text-sm dark:text-amber-400">
              ⚠️ 免责声明：本文书由AI自动生成，仅供参考。正式使用前，请务必咨询专业律师进行审核和修改。
            </p>
          </div>

          <div className="flex gap-4 mt-6">
            <Button variant="outline" onClick={handleReset}>
              重新生成
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}
