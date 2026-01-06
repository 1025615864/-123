import { useEffect, useState } from 'react'
import { Bell, Send, Users, Clock, MessageSquare, RotateCcw } from 'lucide-react'
import { Card, Input, Button, Modal, Textarea, ListSkeleton } from '../../components/ui'
import api from '../../api/client'
import { useAppMutation, useToast } from '../../hooks'
import { getApiErrorMessage } from '../../utils'
import { queryKeys } from '../../queryKeys'
import { useAdminSystemNotificationsQuery } from '../../queries/notifications'

export default function NotificationsPage() {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newNotification, setNewNotification] = useState({
    title: '',
    content: '',
    link: ''
  })
  const toast = useToast()

  const { query: listQuery } = useAdminSystemNotificationsQuery()

  useEffect(() => {
    if (!listQuery.error) return
    toast.error(getApiErrorMessage(listQuery.error))
  }, [listQuery.error, toast])

  const notifications = listQuery.data ?? []

  const sendMutation = useAppMutation<{ target_count: number }, void>({
    mutationFn: async (_: void) => {
      const res = await api.post('/notifications/admin/broadcast', {
        title: newNotification.title,
        content: newNotification.content,
        link: newNotification.link || null,
      })
      return res.data as { target_count: number }
    },
    errorMessageFallback: '发送失败，请稍后重试',
    invalidateQueryKeys: [queryKeys.adminSystemNotifications()],
    onSuccess: (result) => {
      toast.success(`通知已发送给 ${result.target_count} 位用户`)
      setShowCreateModal(false)
      setNewNotification({ title: '', content: '', link: '' })
    },
  })

  const handleSend = async () => {
    if (!newNotification.title.trim() || !newNotification.content.trim()) {
      toast.error('请填写标题和内容')
      return
    }

    sendMutation.mutate()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">通知管理</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">发布和管理系统通知</p>
        </div>
        <Button
          icon={Send}
          onClick={() => setShowCreateModal(true)}
          disabled={sendMutation.isPending}
        >
          发布通知
        </Button>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card variant="surface" padding="md">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-500/20">
              <Bell className="h-6 w-6 text-blue-400" />
            </div>
            <div>
              <p className="text-slate-600 text-sm dark:text-white/50">已发送通知</p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">{notifications.length}</p>
            </div>
          </div>
        </Card>
        <Card variant="surface" padding="md">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-green-500/20">
              <Users className="h-6 w-6 text-green-400" />
            </div>
            <div>
              <p className="text-slate-600 text-sm dark:text-white/50">覆盖用户</p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">全部活跃用户</p>
            </div>
          </div>
        </Card>
        <Card variant="surface" padding="md">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-purple-500/20">
              <MessageSquare className="h-6 w-6 text-purple-400" />
            </div>
            <div>
              <p className="text-slate-600 text-sm dark:text-white/50">通知类型</p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">系统公告</p>
            </div>
          </div>
        </Card>
      </div>

      {/* 通知历史列表 */}
      <Card variant="surface" padding="md">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">发送历史</h2>
          <Button
            variant="outline"
            size="sm"
            icon={RotateCcw}
            onClick={() => listQuery.refetch()}
            isLoading={listQuery.isFetching}
            loadingText="刷新中..."
            disabled={listQuery.isFetching}
          >
            刷新
          </Button>
        </div>
        
        {listQuery.isLoading ? (
          <ListSkeleton count={4} />
        ) : notifications.length === 0 ? (
          <div className="text-center py-8 text-slate-500 dark:text-white/50">
            <Bell className="h-12 w-12 mx-auto mb-2 opacity-50" />
            <p>暂无发送记录</p>
          </div>
        ) : (
          <div className="space-y-4">
            {notifications.map((item) => (
              <div
                key={item.id}
                className="p-4 rounded-lg bg-slate-900/5 border border-slate-200/70 transition-all hover:bg-slate-900/10 hover:border-slate-300 hover:shadow-sm dark:bg-white/5 dark:border-white/10 dark:hover:bg-white/[0.07] dark:hover:border-white/20 dark:hover:shadow-none"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-medium text-slate-900 dark:text-white">{item.title}</h3>
                    <p className="text-slate-700 text-sm mt-1 line-clamp-2 dark:text-white/70">
                      {item.content}
                    </p>
                    {item.link && (
                      <a
                        href={item.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-700 text-sm mt-1 outline-none rounded-md transition-all hover:underline hover:text-blue-800 active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:text-blue-400 dark:hover:text-blue-300 dark:focus-visible:ring-offset-slate-900"
                      >
                        {item.link}
                      </a>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-slate-500 text-sm dark:text-white/50">
                    <Clock className="h-4 w-4" />
                    {new Date(item.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 发布通知弹窗 */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          if (sendMutation.isPending) return
          setShowCreateModal(false)
        }}
        title="发布系统通知"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              通知标题 <span className="text-red-400">*</span>
            </label>
            <Input
              value={newNotification.title}
              onChange={(e) => setNewNotification({ ...newNotification, title: e.target.value })}
              placeholder="请输入通知标题"
              disabled={sendMutation.isPending}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              通知内容 <span className="text-red-400">*</span>
            </label>
            <Textarea
              value={newNotification.content}
              onChange={(e) => setNewNotification({ ...newNotification, content: e.target.value })}
              placeholder="请输入通知内容"
              rows={4}
              disabled={sendMutation.isPending}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              跳转链接（可选）
            </label>
            <Input
              value={newNotification.link}
              onChange={(e) => setNewNotification({ ...newNotification, link: e.target.value })}
              placeholder="https://baixinghelper.cn/page"
              disabled={sendMutation.isPending}
            />
          </div>
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
            <p className="text-yellow-700 text-sm dark:text-yellow-400">
              ⚠️ 此通知将发送给所有活跃用户，请确认内容无误后再发送。
            </p>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="ghost"
              onClick={() => setShowCreateModal(false)}
              disabled={sendMutation.isPending}
            >
              取消
            </Button>
            <Button
              icon={Send}
              onClick={handleSend}
              isLoading={sendMutation.isPending}
              loadingText="发送中..."
              disabled={
                sendMutation.isPending ||
                !newNotification.title ||
                !newNotification.content
              }
            >
              发送通知
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
