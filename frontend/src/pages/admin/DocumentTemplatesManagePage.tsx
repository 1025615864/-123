import { useMemo, useState } from 'react'
import { Plus, RotateCcw, UploadCloud, History } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import api from '../../api/client'
import { Card, Button, Input, Modal, Textarea, Badge, ListSkeleton } from '../../components/ui'
import { useAppMutation } from '../../hooks'
import { getApiErrorMessage } from '../../utils'

interface DocumentTemplate {
  id: number
  key: string
  title: string
  description: string | null
  is_active: boolean
  published_version: number | null
  created_at: string
  updated_at: string
}

interface DocumentTemplateVersion {
  id: number
  template_id: number
  version: number
  is_published: boolean
  content: string
  created_at: string
}

export default function DocumentTemplatesManagePage() {
  const templatesQueryKey = useMemo(() => ['admin-document-templates'] as const, [])

  const [showCreateTemplate, setShowCreateTemplate] = useState(false)
  const [createTemplateForm, setCreateTemplateForm] = useState({ key: '', title: '', description: '' })

  const [activeTemplate, setActiveTemplate] = useState<DocumentTemplate | null>(null)
  const [versionsOpen, setVersionsOpen] = useState(false)
  const [showCreateVersion, setShowCreateVersion] = useState(false)
  const [createVersionForm, setCreateVersionForm] = useState({ content: '', publish: true })

  const templatesQuery = useQuery({
    queryKey: templatesQueryKey,
    queryFn: async () => {
      const res = await api.get('/admin/document-templates')
      return (Array.isArray(res.data) ? res.data : []) as DocumentTemplate[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const templates = templatesQuery.data ?? []
  const loading = templatesQuery.isLoading
  const loadError = templatesQuery.isError ? getApiErrorMessage(templatesQuery.error, '模板列表加载失败') : null

  const versionsQueryKey = useMemo(
    () => (activeTemplate ? (['admin-document-template-versions', activeTemplate.id] as const) : null),
    [activeTemplate]
  )

  const versionsQuery = useQuery({
    queryKey: versionsQueryKey as any,
    queryFn: async () => {
      if (!activeTemplate) return [] as DocumentTemplateVersion[]
      const res = await api.get(`/admin/document-templates/${activeTemplate.id}/versions`)
      return (Array.isArray(res.data) ? res.data : []) as DocumentTemplateVersion[]
    },
    enabled: !!activeTemplate && versionsOpen,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const versions = versionsQuery.data ?? []

  const createTemplateMutation = useAppMutation<void, any>({
    mutationFn: async (payload) => {
      await api.post('/admin/document-templates', payload)
    },
    errorMessageFallback: '创建失败，请稍后重试',
    invalidateQueryKeys: [templatesQueryKey as any],
    onSuccess: () => {
      setShowCreateTemplate(false)
      setCreateTemplateForm({ key: '', title: '', description: '' })
    },
  })

  const createVersionMutation = useAppMutation<void, any>({
    mutationFn: async (payload) => {
      if (!activeTemplate) throw new Error('NO_TEMPLATE')
      await api.post(`/admin/document-templates/${activeTemplate.id}/versions`, payload)
    },
    errorMessageFallback: '创建版本失败，请稍后重试',
    invalidateQueryKeys: [templatesQueryKey as any, versionsQueryKey as any].filter(Boolean),
    onSuccess: () => {
      setShowCreateVersion(false)
      setCreateVersionForm({ content: '', publish: true })
    },
  })

  const publishMutation = useAppMutation<void, { templateId: number; versionId: number }>({
    mutationFn: async ({ templateId, versionId }) => {
      await api.post(`/admin/document-templates/${templateId}/versions/${versionId}/publish`)
    },
    errorMessageFallback: '发布失败，请稍后重试',
    invalidateQueryKeys: [templatesQueryKey as any, versionsQueryKey as any].filter(Boolean),
  })

  const openVersions = (tpl: DocumentTemplate) => {
    setActiveTemplate(tpl)
    setVersionsOpen(true)
  }

  const handleCreateTemplate = () => {
    if (createTemplateMutation.isPending) return
    createTemplateMutation.mutate({
      key: createTemplateForm.key,
      title: createTemplateForm.title,
      description: createTemplateForm.description || null,
      is_active: true,
    })
  }

  const handleCreateVersion = () => {
    if (createVersionMutation.isPending) return
    createVersionMutation.mutate({
      content: createVersionForm.content,
      publish: !!createVersionForm.publish,
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">文书模板管理</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">管理文书模板与版本，支持发布与回滚</p>
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
          <Button icon={Plus} onClick={() => setShowCreateTemplate(true)}>
            新建模板
          </Button>
        </div>
      </div>

      {loading && templates.length === 0 ? (
        <ListSkeleton count={6} />
      ) : loadError ? (
        <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
          <div>{loadError}</div>
          <Button variant="outline" onClick={() => templatesQuery.refetch()}>
            重试
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {templates.map((tpl) => (
            <Card key={tpl.id} variant="surface" padding="md" className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-slate-900 font-medium truncate dark:text-white">{tpl.title}</h3>
                    {!tpl.is_active ? <Badge variant="warning" size="sm">禁用</Badge> : null}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-white/40 mt-1">key: {tpl.key}</p>
                  {tpl.description ? (
                    <p className="text-sm text-slate-600 dark:text-white/50 mt-2 line-clamp-2">{tpl.description}</p>
                  ) : null}
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="text-xs text-slate-500 dark:text-white/40">
                  已发布版本：{typeof tpl.published_version === 'number' ? `v${tpl.published_version}` : '无'}
                </div>
                <Button variant="outline" icon={History} onClick={() => openVersions(tpl)}>
                  版本
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={showCreateTemplate}
        onClose={() => setShowCreateTemplate(false)}
        title="新建文书模板"
      >
        <div className="space-y-4">
          <Input
            label="模板 Key"
            placeholder="例如 complaint"
            value={createTemplateForm.key}
            onChange={(e) => setCreateTemplateForm((p) => ({ ...p, key: e.target.value }))}
          />
          <Input
            label="标题"
            placeholder="例如 民事起诉状"
            value={createTemplateForm.title}
            onChange={(e) => setCreateTemplateForm((p) => ({ ...p, title: e.target.value }))}
          />
          <Textarea
            label="描述"
            placeholder="可选"
            value={createTemplateForm.description}
            onChange={(e) => setCreateTemplateForm((p) => ({ ...p, description: e.target.value }))}
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowCreateTemplate(false)}>
              取消
            </Button>
            <Button isLoading={createTemplateMutation.isPending} onClick={handleCreateTemplate}>
              创建
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={versionsOpen}
        onClose={() => setVersionsOpen(false)}
        title={activeTemplate ? `版本管理：${activeTemplate.title}` : '版本管理'}
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-600 dark:text-white/50">
              {activeTemplate ? `key: ${activeTemplate.key}` : ''}
            </div>
            <Button icon={UploadCloud} onClick={() => setShowCreateVersion(true)}>
              新建版本
            </Button>
          </div>

          {versionsQuery.isLoading ? (
            <ListSkeleton count={4} />
          ) : versionsQuery.isError ? (
            <div className="text-sm text-red-600 dark:text-red-200">{getApiErrorMessage(versionsQuery.error)}</div>
          ) : versions.length === 0 ? (
            <div className="text-sm text-slate-600 dark:text-white/50">暂无版本</div>
          ) : (
            <div className="space-y-3">
              {versions.map((v) => (
                <Card key={v.id} variant="surface" padding="md" className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="text-slate-900 font-medium dark:text-white">v{v.version}</div>
                        {v.is_published ? <Badge variant="success" size="sm">已发布</Badge> : null}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-white/40 mt-1">{new Date(v.created_at).toLocaleString()}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        disabled={v.is_published || publishMutation.isPending}
                        onClick={() => {
                          if (!activeTemplate) return
                          publishMutation.mutate({ templateId: activeTemplate.id, versionId: v.id })
                        }}
                      >
                        发布
                      </Button>
                    </div>
                  </div>
                  <pre className="max-h-40 overflow-auto rounded-lg bg-slate-900 text-slate-100 text-xs p-3 whitespace-pre-wrap">
                    {v.content}
                  </pre>
                </Card>
              ))}
            </div>
          )}
        </div>
      </Modal>

      <Modal
        isOpen={showCreateVersion}
        onClose={() => setShowCreateVersion(false)}
        title="新建模板版本"
      >
        <div className="space-y-4">
          <Textarea
            label="模板内容"
            placeholder="填写模板内容，支持 {plaintiff_name}/{defendant_name}/{case_type}/{facts}/{claims}/{evidence_section}/{evidence_count}/{court_name}/{date}"
            value={createVersionForm.content}
            onChange={(e) => setCreateVersionForm((p) => ({ ...p, content: e.target.value }))}
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowCreateVersion(false)}>
              取消
            </Button>
            <Button isLoading={createVersionMutation.isPending} onClick={handleCreateVersion}>
              创建并发布
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
