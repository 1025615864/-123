import { useMemo, useState } from 'react'
import { Plus, Edit, Trash2, MessageSquare, Briefcase, Heart, Car, FileText, HelpCircle, RotateCcw } from 'lucide-react'
import { Card, Input, Button, Badge, Modal, Textarea, ListSkeleton } from '../../components/ui'
import { useQuery } from '@tanstack/react-query'
import api from '../../api/client'
import { useAppMutation } from '../../hooks'
import { useTheme } from '../../contexts/ThemeContext'
import { getApiErrorMessage } from '../../utils'

interface TemplateQuestion {
  question: string
  hint: string | null
}

interface ConsultationTemplate {
  id: number
  name: string
  description: string | null
  category: string
  icon: string
  questions: TemplateQuestion[]
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

const CATEGORIES = [
  '劳动纠纷', '婚姻家庭', '合同纠纷', '交通事故', 
  '借贷纠纷', '房产纠纷', '消费维权', '其他'
]

const ICONS = [
  { value: 'MessageSquare', label: '消息', icon: MessageSquare },
  { value: 'Briefcase', label: '工作', icon: Briefcase },
  { value: 'Heart', label: '家庭', icon: Heart },
  { value: 'Car', label: '交通', icon: Car },
  { value: 'FileText', label: '合同', icon: FileText },
  { value: 'HelpCircle', label: '帮助', icon: HelpCircle },
]

export default function TemplatesManagePage() {
  const { actualTheme } = useTheme()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingItem, setEditingItem] = useState<ConsultationTemplate | null>(null)
  const [activeDeleteId, setActiveDeleteId] = useState<number | null>(null)

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    category: '劳动纠纷',
    icon: 'MessageSquare',
    questions: [{ question: '', hint: '' }] as Array<{ question: string; hint: string }>,
    sort_order: 0,
    is_active: true,
  })

  const templatesQueryKey = useMemo(() => ['admin-knowledge-templates'] as const, [])

  const templatesQuery = useQuery({
    queryKey: templatesQueryKey,
    queryFn: async () => {
      const res = await api.get('/knowledge/templates', { params: { is_active: '' } })
      return (Array.isArray(res.data) ? res.data : []) as ConsultationTemplate[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const templates = templatesQuery.data ?? []
  const loading = templatesQuery.isLoading
  const loadError = templatesQuery.isError ? getApiErrorMessage(templatesQuery.error, '模板列表加载失败，请稍后重试') : null

  const createMutation = useAppMutation<void, any>({
    mutationFn: async (payload) => {
      await api.post('/knowledge/templates', payload)
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [templatesQueryKey as any],
    onSuccess: () => {
      setShowCreateModal(false)
      resetForm()
    },
  })

  const editMutation = useAppMutation<void, { id: number; payload: any }>({
    mutationFn: async ({ id, payload }) => {
      await api.put(`/knowledge/templates/${id}`, payload)
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [templatesQueryKey as any],
    onSuccess: () => {
      setShowEditModal(false)
      setEditingItem(null)
      resetForm()
    },
  })

  const deleteMutation = useAppMutation<void, number>({
    mutationFn: async (id) => {
      await api.delete(`/knowledge/templates/${id}`)
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [templatesQueryKey as any],
    onMutate: async (id) => {
      setActiveDeleteId(id)
    },
    onSettled: (_data, _err, id) => {
      setActiveDeleteId((prev) => (prev === id ? null : prev))
    },
  })

  const handleCreate = async () => {
    const payload = {
      ...formData,
      questions: formData.questions.filter(q => q.question.trim()).map(q => ({
        question: q.question,
        hint: q.hint || null,
      })),
    }
    if (createMutation.isPending) return
    createMutation.mutate(payload)
  }

  const handleEdit = async () => {
    if (!editingItem) return
    const payload = {
      ...formData,
      questions: formData.questions.filter(q => q.question.trim()).map(q => ({
        question: q.question,
        hint: q.hint || null,
      })),
    }
    if (editMutation.isPending) return
    editMutation.mutate({ id: editingItem.id, payload })
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除这个模板吗？')) return
    if (deleteMutation.isPending) return
    deleteMutation.mutate(id)
  }

  const openEditModal = (item: ConsultationTemplate) => {
    setEditingItem(item)
    setFormData({
      name: item.name,
      description: item.description || '',
      category: item.category,
      icon: item.icon,
      questions: item.questions.length > 0 
        ? item.questions.map(q => ({ question: q.question, hint: q.hint || '' }))
        : [{ question: '', hint: '' }],
      sort_order: item.sort_order,
      is_active: item.is_active,
    })
    setShowEditModal(true)
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      category: '劳动纠纷',
      icon: 'MessageSquare',
      questions: [{ question: '', hint: '' }],
      sort_order: 0,
      is_active: true,
    })
  }

  const addQuestion = () => {
    setFormData(prev => ({
      ...prev,
      questions: [...prev.questions, { question: '', hint: '' }],
    }))
  }

  const removeQuestion = (index: number) => {
    setFormData(prev => ({
      ...prev,
      questions: prev.questions.filter((_, i) => i !== index),
    }))
  }

  const updateQuestion = (index: number, field: 'question' | 'hint', value: string) => {
    setFormData(prev => ({
      ...prev,
      questions: prev.questions.map((q, i) => 
        i === index ? { ...q, [field]: value } : q
      ),
    }))
  }

  const getIconComponent = (iconName: string) => {
    const found = ICONS.find(i => i.value === iconName)
    return found ? found.icon : MessageSquare
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">咨询模板管理</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">管理AI咨询的预设问题模板</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            icon={RotateCcw}
            isLoading={templatesQuery.isFetching}
            loadingText="刷新中..."
            disabled={templatesQuery.isFetching}
            onClick={() => templatesQuery.refetch()}
          >
            刷新
          </Button>
          <Button icon={Plus} onClick={() => setShowCreateModal(true)}>
            添加模板
          </Button>
        </div>
      </div>

      {/* 模板列表 */}
      {loading && templates.length === 0 ? (
        <ListSkeleton count={6} />
      ) : loadError ? (
        <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
          <div>{loadError}</div>
          <Button variant="outline" onClick={() => templatesQuery.refetch()}>重试</Button>
        </div>
      ) : (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {templates.map((template) => {
          const IconComponent = getIconComponent(template.icon)
          return (
            <Card key={template.id} variant="surface" padding="md" className="relative">
              <div className="flex items-start gap-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-blue-500/20 to-purple-500/20">
                  <IconComponent className="h-6 w-6 text-blue-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className={`text-slate-900 font-medium truncate ${actualTheme === 'dark' ? 'dark:text-white' : ''}`}>{template.name}</h3>
                    {!template.is_active && (
                      <Badge variant="warning" size="sm">禁用</Badge>
                    )}
                  </div>
                  <Badge variant="info" size="sm">{template.category}</Badge>
                  {template.description && (
                    <p className={`text-slate-600 text-sm mt-2 line-clamp-2 ${actualTheme === 'dark' ? 'dark:text-white/50' : ''}`}>{template.description}</p>
                  )}
                  <p className={`text-slate-500 text-xs mt-2 ${actualTheme === 'dark' ? 'dark:text-white/30' : ''}`}>
                    {template.questions.length} 个预设问题
                  </p>
                </div>
              </div>
              
              <div className="absolute top-4 right-4 flex gap-1">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="p-2" 
                  title="编辑"
                  onClick={() => openEditModal(template)}
                >
                  <Edit className="h-4 w-4" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className={`${deleteMutation.isPending && activeDeleteId === template.id ? 'px-3 py-2' : 'p-2'} text-red-400 hover:text-red-300`}
                  onClick={() => handleDelete(template.id)}
                  title="删除"
                  isLoading={deleteMutation.isPending && activeDeleteId === template.id}
                  loadingText="删除中..."
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          )
        })}
      </div>
      )}

      {templates.length === 0 && !loading && !loadError && (
        <Card variant="surface" padding="lg">
          <div className="text-center py-8 text-slate-500 dark:text-white/40">
            <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>暂无咨询模板</p>
            <p className="text-sm mt-1">点击上方按钮添加第一个模板</p>
          </div>
        </Card>
      )}

      {/* 创建弹窗 */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          if (createMutation.isPending) return
          setShowCreateModal(false)
          resetForm()
        }}
        title="添加咨询模板"
        description="创建AI咨询的预设问题模板"
      >
        <TemplateForm
          formData={formData}
          setFormData={setFormData}
          addQuestion={addQuestion}
          removeQuestion={removeQuestion}
          updateQuestion={updateQuestion}
          onSubmit={handleCreate}
          onCancel={() => {
            if (createMutation.isPending) return
            setShowCreateModal(false)
            resetForm()
          }}
          submitLabel="添加"
          submitLoading={createMutation.isPending}
        />
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        isOpen={showEditModal}
        onClose={() => {
          if (editMutation.isPending) return
          setShowEditModal(false)
          setEditingItem(null)
          resetForm()
        }}
        title="编辑咨询模板"
        description="修改咨询模板"
      >
        <TemplateForm
          formData={formData}
          setFormData={setFormData}
          addQuestion={addQuestion}
          removeQuestion={removeQuestion}
          updateQuestion={updateQuestion}
          onSubmit={handleEdit}
          onCancel={() => {
            if (editMutation.isPending) return
            setShowEditModal(false)
            setEditingItem(null)
            resetForm()
          }}
          submitLabel="保存"
          submitLoading={editMutation.isPending}
        />
      </Modal>
    </div>
  )
}

// 表单组件
interface FormData {
  name: string
  description: string
  category: string
  icon: string
  questions: Array<{ question: string; hint: string }>
  sort_order: number
  is_active: boolean
}

interface TemplateFormProps {
  formData: FormData
  setFormData: React.Dispatch<React.SetStateAction<FormData>>
  addQuestion: () => void
  removeQuestion: (index: number) => void
  updateQuestion: (index: number, field: 'question' | 'hint', value: string) => void
  onSubmit: () => void
  onCancel: () => void
  submitLabel: string
  submitLoading: boolean
}

function TemplateForm({ 
  formData, 
  setFormData, 
  addQuestion, 
  removeQuestion, 
  updateQuestion, 
  onSubmit, 
  onCancel, 
  submitLabel,
  submitLoading,
}: TemplateFormProps) {
  return (
    <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
      <Input
        label="模板名称"
        value={formData.name}
        onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
        placeholder="如：劳动仲裁咨询"
        disabled={submitLoading}
      />

      <Textarea
        label="描述（可选）"
        value={formData.description}
        onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
        placeholder="简要描述此模板的用途..."
        rows={2}
        disabled={submitLoading}
      />

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">分类</label>
          <select
            value={formData.category}
            onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
            disabled={submitLoading}
            className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
          >
            {CATEGORIES.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">图标</label>
          <select
            value={formData.icon}
            onChange={(e) => setFormData(prev => ({ ...prev, icon: e.target.value }))}
            disabled={submitLoading}
            className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
          >
            {ICONS.map(i => (
              <option key={i.value} value={i.value}>{i.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-slate-700 dark:text-white/70">预设问题</label>
          <Button variant="ghost" size="sm" onClick={addQuestion} disabled={submitLoading}>+ 添加问题</Button>
        </div>
        <div className="space-y-3">
          {formData.questions.map((q, index) => (
            <div key={index} className="p-3 rounded-lg bg-slate-900/5 border border-slate-200/70 space-y-2 dark:bg-white/5 dark:border-white/10">
              <div className="flex items-start gap-2">
                <span className="text-slate-500 text-sm mt-2 dark:text-white/30">{index + 1}.</span>
                <div className="flex-1">
                  <Input
                    value={q.question}
                    onChange={(e) => updateQuestion(index, 'question', e.target.value)}
                    placeholder="输入问题内容..."
                    disabled={submitLoading}
                  />
                </div>
                {formData.questions.length > 1 && (
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="p-2 text-red-400"
                    onClick={() => removeQuestion(index)}
                    disabled={submitLoading}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
              <Input
                value={q.hint}
                onChange={(e) => updateQuestion(index, 'hint', e.target.value)}
                placeholder="提示信息（可选）..."
                className="ml-6"
                disabled={submitLoading}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="template_is_active"
            checked={formData.is_active}
            onChange={(e) => setFormData(prev => ({ ...prev, is_active: e.target.checked }))}
            disabled={submitLoading}
            className="rounded"
          />
          <label htmlFor="template_is_active" className="text-sm text-slate-700 dark:text-white/70">启用</label>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-700 dark:text-white/70">排序：</label>
          <input
            type="number"
            min="0"
            value={formData.sort_order}
            onChange={(e) => setFormData(prev => ({ ...prev, sort_order: parseInt(e.target.value) || 0 }))}
            disabled={submitLoading}
            className="w-20 px-3 py-1 rounded-lg border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
          />
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-slate-200/70 dark:border-white/10">
        <Button variant="outline" onClick={onCancel} disabled={submitLoading}>取消</Button>
        <Button onClick={onSubmit} isLoading={submitLoading} loadingText={`${submitLabel}中...`}>{submitLabel}</Button>
      </div>
    </div>
  )
}
