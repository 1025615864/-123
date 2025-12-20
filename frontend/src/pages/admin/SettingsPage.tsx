import { useState, useEffect } from 'react'
import { Save, Key, Globe, Bell, Shield } from 'lucide-react'
import { Card, Input, Button } from '../../components/ui'
import { useQuery } from '@tanstack/react-query'
import api from '../../api/client'
import { useAppMutation, useToast } from '../../hooks'
import { getApiErrorMessage } from '../../utils'
import { queryKeys } from '../../queryKeys'

interface ConfigItem {
  key: string
  value: string | null
  description: string | null
  category: string
}

export default function SettingsPage() {
  const toast = useToast()
  const [settings, setSettings] = useState({
    siteName: '百姓法律助手',
    siteDescription: '为普通百姓提供专业法律咨询服务',
    contactEmail: 'contact@example.com',
    contactPhone: '400-123-4567',
    openaiApiKey: '',
    enableAI: true,
    enableNotifications: true,
    maintenanceMode: false,
  })

  const configsQuery = useQuery({
    queryKey: queryKeys.systemConfigs(),
    queryFn: async () => {
      const res = await api.get('/system/configs')
      return (Array.isArray(res.data) ? res.data : []) as ConfigItem[]
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!configsQuery.error) return
    toast.error(getApiErrorMessage(configsQuery.error, '配置加载失败'))
  }, [configsQuery.error, toast])

  useEffect(() => {
    const configs = configsQuery.data
    if (!configs || configs.length === 0) return

    const configMap: Record<string, string> = {}
    configs.forEach((c) => {
      if (c.value) configMap[c.key] = c.value
    })

    setSettings((prev) => ({
      ...prev,
      siteName: configMap['site_name'] || prev.siteName,
      siteDescription: configMap['site_description'] || prev.siteDescription,
      contactEmail: configMap['contact_email'] || prev.contactEmail,
      contactPhone: configMap['contact_phone'] || prev.contactPhone,
      openaiApiKey: configMap['openai_api_key'] ? '••••••••••••••••' : '',
      enableAI: configMap['enable_ai'] !== 'false',
      enableNotifications: configMap['enable_notifications'] !== 'false',
      maintenanceMode: configMap['maintenance_mode'] === 'true',
    }))
  }, [configsQuery.data])

  const saveMutation = useAppMutation<void, { configs: Array<{ key: string; value: string; category: string }> }>({
    mutationFn: async (payload) => {
      await api.post('/system/configs/batch', payload)
    },
    successMessage: '设置保存成功',
    errorMessageFallback: '保存失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.systemConfigs()],
  })

  const handleSave = async () => {
    try {
      const configs = [
        { key: 'site_name', value: settings.siteName, category: 'general' },
        { key: 'site_description', value: settings.siteDescription, category: 'general' },
        { key: 'contact_email', value: settings.contactEmail, category: 'general' },
        { key: 'contact_phone', value: settings.contactPhone, category: 'general' },
        { key: 'enable_ai', value: String(settings.enableAI), category: 'ai' },
        { key: 'enable_notifications', value: String(settings.enableNotifications), category: 'notification' },
        { key: 'maintenance_mode', value: String(settings.maintenanceMode), category: 'security' },
      ]

      const maskedPlaceholder = '••••••••••••••••'
      if (settings.openaiApiKey && settings.openaiApiKey !== maskedPlaceholder) {
        configs.push({ key: 'openai_api_key', value: settings.openaiApiKey, category: 'ai' })
      }

      if (saveMutation.isPending) return
      saveMutation.mutate({ configs })
    } catch {
      // 错误已处理
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">系统设置</h1>
        <p className="text-slate-600 mt-1 dark:text-white/50">配置系统参数和功能开关</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* 基本设置 */}
        <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <Globe className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">基本设置</h3>
              <p className="text-slate-600 text-sm dark:text-white/40">网站基本信息配置</p>
            </div>
          </div>
          
          <div className="space-y-4">
            <Input
              label="网站名称"
              value={settings.siteName}
              onChange={(e) => setSettings({ ...settings, siteName: e.target.value })}
            />
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">网站描述</label>
              <textarea
                value={settings.siteDescription}
                onChange={(e) => setSettings({ ...settings, siteDescription: e.target.value })}
                rows={3}
                className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none resize-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
              />
            </div>
            <Input
              label="联系邮箱"
              value={settings.contactEmail}
              onChange={(e) => setSettings({ ...settings, contactEmail: e.target.value })}
            />
            <Input
              label="联系电话"
              value={settings.contactPhone}
              onChange={(e) => setSettings({ ...settings, contactPhone: e.target.value })}
            />
          </div>
        </Card>

        {/* AI设置 */}
        <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
              <Key className="h-5 w-5 text-purple-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">AI配置</h3>
              <p className="text-slate-600 text-sm dark:text-white/40">AI助手相关配置</p>
            </div>
          </div>
          
          <div className="space-y-4">
            <Input
              label="OpenAI API Key"
              type="password"
              value={settings.openaiApiKey}
              onChange={(e) => setSettings({ ...settings, openaiApiKey: e.target.value })}
            />
            <div className="flex items-center justify-between py-3 border-b border-slate-200/70 dark:border-white/5">
              <div>
                <p className="text-slate-900 font-medium dark:text-white">启用AI助手</p>
                <p className="text-slate-600 text-sm dark:text-white/40">开启后用户可使用AI法律咨询</p>
              </div>
              <button
                onClick={() => setSettings({ ...settings, enableAI: !settings.enableAI })}
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings.enableAI ? 'bg-amber-500' : 'bg-slate-200 dark:bg-white/20'
                }`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${
                  settings.enableAI ? 'translate-x-6' : 'translate-x-0.5'
                }`} />
              </button>
            </div>
          </div>
        </Card>

        {/* 通知设置 */}
        <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
              <Bell className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">通知设置</h3>
              <p className="text-slate-600 text-sm dark:text-white/40">系统通知配置</p>
            </div>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-slate-200/70 dark:border-white/5">
              <div>
                <p className="text-slate-900 font-medium dark:text-white">启用通知</p>
                <p className="text-slate-600 text-sm dark:text-white/40">发送系统通知给用户</p>
              </div>
              <button
                onClick={() => setSettings({ ...settings, enableNotifications: !settings.enableNotifications })}
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings.enableNotifications ? 'bg-amber-500' : 'bg-slate-200 dark:bg-white/20'
                }`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${
                  settings.enableNotifications ? 'translate-x-6' : 'translate-x-0.5'
                }`} />
              </button>
            </div>
          </div>
        </Card>

        {/* 维护模式 */}
        <Card variant="surface" padding="lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
              <Shield className="h-5 w-5 text-red-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">维护模式</h3>
              <p className="text-slate-600 text-sm dark:text-white/40">系统维护设置</p>
            </div>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-slate-200/70 dark:border-white/5">
              <div>
                <p className="text-slate-900 font-medium dark:text-white">开启维护模式</p>
                <p className="text-slate-600 text-sm dark:text-white/40">开启后普通用户无法访问网站</p>
              </div>
              <button
                onClick={() => setSettings({ ...settings, maintenanceMode: !settings.maintenanceMode })}
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings.maintenanceMode ? 'bg-red-500' : 'bg-slate-200 dark:bg-white/20'
                }`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${
                  settings.maintenanceMode ? 'translate-x-6' : 'translate-x-0.5'
                }`} />
              </button>
            </div>
          </div>
        </Card>
      </div>

      <div className="flex justify-end">
        <Button icon={Save} onClick={handleSave} isLoading={saveMutation.isPending} className="px-8">
          保存设置
        </Button>
      </div>
    </div>
  )
}
