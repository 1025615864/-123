import { useEffect, useMemo, useState } from 'react'
import { FileText, User, Calendar, Filter, RefreshCw } from 'lucide-react'
import { Card, Button, Badge } from '../../components/ui'
import { useQuery } from '@tanstack/react-query'
import api from '../../api/client'
import { useToast } from '../../hooks'
import { getApiErrorMessage } from '../../utils'

interface LogItem {
  id: number
  user_id: number
  user_name: string | null
  action: string
  module: string
  target_id: number | null
  description: string | null
  ip_address: string | null
  created_at: string
}

const actionLabels: Record<string, { label: string; color: 'success' | 'warning' | 'danger' | 'info' }> = {
  create: { label: '创建', color: 'success' },
  update: { label: '更新', color: 'warning' },
  delete: { label: '删除', color: 'danger' },
  login: { label: '登录', color: 'info' },
  logout: { label: '登出', color: 'info' },
  enable: { label: '启用', color: 'success' },
  disable: { label: '禁用', color: 'danger' },
  config: { label: '配置', color: 'warning' },
  export: { label: '导出', color: 'info' },
}

const moduleLabels: Record<string, string> = {
  user: '用户',
  post: '帖子',
  comment: '评论',
  news: '新闻',
  lawfirm: '律所',
  lawyer: '律师',
  knowledge: '知识库',
  template: '模板',
  system: '系统',
  auth: '认证',
}

export default function LogsPage() {
  const [page, setPage] = useState(1)
  const [module, setModule] = useState('')
  const [action, setAction] = useState('')
  const toast = useToast()
  const pageSize = 20

  const logsQueryKey = useMemo(
    () => ['admin-logs', { page, pageSize, module, action }] as const,
    [page, pageSize, module, action]
  )

  const logsQuery = useQuery({
    queryKey: logsQueryKey,
    queryFn: async () => {
      const res = await api.get('/system/logs', {
        params: {
          page,
          page_size: pageSize,
          ...(module ? { module } : {}),
          ...(action ? { action } : {}),
        },
      })
      const data = res.data
      return {
        items: Array.isArray(data?.items) ? (data.items as LogItem[]) : ([] as LogItem[]),
        total: Number(data?.total || 0),
      }
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!logsQuery.error) return
    toast.error(getApiErrorMessage(logsQuery.error))
  }, [logsQuery.error, toast])

  const logs = logsQuery.data?.items ?? []
  const total = logsQuery.data?.total ?? 0
  const loading = logsQuery.isFetching

  const totalPages = Math.ceil(total / pageSize)

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">操作日志</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">查看管理员操作记录</p>
        </div>
        <Button variant="outline" onClick={() => logsQuery.refetch()} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </Button>
      </div>

      {/* 筛选器 */}
      <Card variant="surface" padding="md">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-slate-500 dark:text-white/50" />
            <span className="text-slate-700 text-sm dark:text-white/70">筛选：</span>
          </div>
          <select
            value={module}
            onChange={(e) => { setModule(e.target.value); setPage(1) }}
            className="px-3 py-2 rounded-lg border border-slate-200/70 bg-white text-slate-900 text-sm outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
          >
            <option value="">全部模块</option>
            {Object.entries(moduleLabels).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          <select
            value={action}
            onChange={(e) => { setAction(e.target.value); setPage(1) }}
            className="px-3 py-2 rounded-lg border border-slate-200/70 bg-white text-slate-900 text-sm outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
          >
            <option value="">全部操作</option>
            {Object.entries(actionLabels).map(([key, { label }]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          {(module || action) && (
            <Button variant="ghost" size="sm" onClick={() => { setModule(''); setAction(''); setPage(1) }}>
              清除筛选
            </Button>
          )}
        </div>
      </Card>

      {/* 日志列表 */}
      <Card variant="surface" padding="none">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200/70 dark:border-white/10">
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">时间</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">操作员</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">模块</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">操作</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">描述</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">IP地址</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5">
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2 text-slate-600 text-sm dark:text-white/60">
                      <Calendar className="h-4 w-4" />
                      {formatTime(log.created_at)}
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 flex items-center justify-center">
                        <User className="h-4 w-4 text-white" />
                      </div>
                      <span className="text-slate-900 text-sm dark:text-white">{log.user_name || `用户#${log.user_id}`}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-slate-700 text-sm dark:text-white/70">
                      {moduleLabels[log.module] || log.module}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <Badge 
                      variant={actionLabels[log.action]?.color || 'info'} 
                      size="sm"
                    >
                      {actionLabels[log.action]?.label || log.action}
                    </Badge>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-slate-600 text-sm max-w-xs truncate block dark:text-white/60">
                      {log.description || '-'}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-slate-500 text-sm font-mono dark:text-white/40">
                      {log.ip_address || '-'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {logs.length === 0 && !loading && (
          <div className="text-center py-12 text-slate-500 dark:text-white/40">
            <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>暂无操作日志</p>
          </div>
        )}

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-4 p-4 border-t border-slate-200/70 dark:border-white/10">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              上一页
            </Button>
            <span className="text-slate-600 text-sm dark:text-white/60">
              第 {page} / {totalPages} 页（共 {total} 条）
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => p + 1)}
              disabled={page >= totalPages}
            >
              下一页
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}
