import { useEffect, useState } from 'react'
import { Search, Ban, CheckCircle, Shield, User as UserIcon, Mail, Phone, Calendar, Eye, MessageSquare, Heart } from 'lucide-react'
import { Card, Input, Button, Badge, Modal, Loading, FadeInImage } from '../../components/ui'
import { useQuery } from '@tanstack/react-query'
import api from '../../api/client'
import { useAppMutation, useToast } from '../../hooks'
import { useTheme } from '../../contexts/ThemeContext'
import { getApiErrorMessage } from '../../utils'
import { queryKeys } from '../../queryKeys'

interface User {
  id: number
  username: string
  email: string
  nickname: string | null
  avatar: string | null
  phone: string | null
  role: string
  is_active: boolean
  created_at: string
}

interface UserStats {
  post_count: number
  favorite_count: number
  comment_count: number
}

export default function UsersPage() {
  const { actualTheme } = useTheme()
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [userStats, setUserStats] = useState<UserStats | null>(null)
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [showRoleModal, setShowRoleModal] = useState(false)
  const [newRole, setNewRole] = useState('')
  const pageSize = 20
  
  const toast = useToast()

  const usersQueryKey = queryKeys.adminUsers(page, pageSize, keyword.trim())

  const usersQuery = useQuery({
    queryKey: usersQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('page', page.toString())
      params.append('page_size', pageSize.toString())
      if (keyword.trim()) params.append('keyword', keyword.trim())

      const res = await api.get(`/user/admin/list?${params.toString()}`)
      const data = res.data
      return {
        items: Array.isArray(data?.items) ? (data.items as User[]) : ([] as User[]),
        total: Number(data?.total || 0),
      }
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  const users = usersQuery.data?.items ?? []
  const total = usersQuery.data?.total ?? 0

  const userStatsQuery = useQuery({
    queryKey: queryKeys.adminUserStats(selectedUser?.id),
    queryFn: async () => {
      const res = await api.get(`/user/${selectedUser?.id}/stats`)
      return res.data as UserStats
    },
    enabled: !!selectedUser?.id && showDetailModal,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  })

  useEffect(() => {
    if (!showDetailModal) return
    if (userStatsQuery.isError) {
      setUserStats(null)
      return
    }
    if (userStatsQuery.data) {
      setUserStats(userStatsQuery.data)
    }
  }, [showDetailModal, userStatsQuery.data, userStatsQuery.isError])

  useEffect(() => {
    if (!usersQuery.error) return
    toast.error(getApiErrorMessage(usersQuery.error, '用户列表加载失败，请稍后重试'))
  }, [toast, usersQuery.error])

  const toggleActiveMutation = useAppMutation<void, User>({
    mutationFn: async (u) => {
      await api.put(`/user/admin/${u.id}/toggle-active`, {})
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [usersQueryKey as any],
    onSuccess: (_res, u) => {
      toast.success(u.is_active ? '已禁用用户' : '已启用用户')
    },
  })

  const saveRoleMutation = useAppMutation<void, { userId: number; role: string }>({
    mutationFn: async (payload) => {
      await api.put(`/user/admin/${payload.userId}/role?role=${payload.role}`, {})
    },
    errorMessageFallback: '操作失败，请稍后重试',
    invalidateQueryKeys: [usersQueryKey as any],
    onSuccess: () => {
      toast.success('角色修改成功')
      setShowRoleModal(false)
    },
  })

  const handleViewUser = async (user: User) => {
    setSelectedUser(user)
    setShowDetailModal(true)
    setUserStats(null)
  }

  const handleEditRole = (user: User) => {
    setSelectedUser(user)
    setNewRole(user.role)
    setShowRoleModal(true)
  }

  const handleToggleActive = async (user: User) => {
    if (!confirm(user.is_active ? `确定要禁用用户 ${user.username} 吗？` : `确定要启用用户 ${user.username} 吗？`)) {
      return
    }
    if (toggleActiveMutation.isPending) return
    toggleActiveMutation.mutate(user)
  }

  const handleSaveRole = async () => {
    if (!selectedUser || !newRole) return
    if (saveRoleMutation.isPending) return
    saveRoleMutation.mutate({ userId: selectedUser.id, role: newRole })
  }

  const totalPages = Math.ceil(total / pageSize)

  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'admin':
        return <Badge variant="warning" size="sm">管理员</Badge>
      case 'lawyer':
        return <Badge variant="success" size="sm">律师</Badge>
      default:
        return <Badge variant="info" size="sm">用户</Badge>
    }
  }

  const loadError = usersQuery.isError ? getApiErrorMessage(usersQuery.error, '用户列表加载失败，请稍后重试') : null
  const loading = usersQuery.isLoading

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">用户管理</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">管理平台用户账户</p>
        </div>
      </div>

      <Card variant="surface" padding="md">
        <div className="flex gap-4 mb-6">
          <div className="flex-1 max-w-md">
            <Input
              icon={Search}
              value={keyword}
              onChange={(e) => {
                setKeyword(e.target.value)
                setPage(1)
              }}
              placeholder="搜索用户名、邮箱或昵称..."
            />
          </div>
        </div>

        {loading ? (
          <Loading text="加载中..." tone={actualTheme} />
        ) : loadError ? (
          <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
            <div>{loadError}</div>
            <Button variant="outline" onClick={() => usersQuery.refetch()}>重试</Button>
          </div>
        ) : (
          <>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200/70 dark:border-white/10">
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">用户</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">邮箱</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">角色</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">状态</th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">注册时间</th>
                <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5">
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 flex items-center justify-center">
                        <span className="text-white font-semibold">
                          {user.username[0].toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <p className="text-slate-900 font-medium dark:text-white">{user.nickname || user.username}</p>
                        <p className="text-slate-500 text-sm dark:text-white/40">@{user.username}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-slate-700 dark:text-white/70">{user.email}</td>
                  <td className="py-4 px-4">{getRoleBadge(user.role)}</td>
                  <td className="py-4 px-4">
                    {user.is_active ? (
                      <span className="flex items-center gap-1 text-emerald-400 text-sm">
                        <CheckCircle className="h-4 w-4" />
                        正常
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-red-400 text-sm">
                        <Ban className="h-4 w-4" />
                        已禁用
                      </span>
                    )}
                  </td>
                  <td className="py-4 px-4 text-slate-500 text-sm dark:text-white/50">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-4 px-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="p-2"
                        onClick={() => handleViewUser(user)}
                        title="查看详情"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="p-2"
                        onClick={() => handleEditRole(user)}
                        title="修改角色"
                      >
                        <Shield className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className={`p-2 ${user.is_active ? 'text-red-400 hover:text-red-300' : 'text-green-400 hover:text-green-300'}`}
                        onClick={() => handleToggleActive(user)}
                        title={user.is_active ? '禁用账户' : '启用账户'}
                      >
                        {user.is_active ? <Ban className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {users.length === 0 && (
          <div className="text-center py-12 text-slate-500 dark:text-white/40">暂无符合条件的用户</div>
        )}

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-4 mt-6">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              上一页
            </Button>
            <span className="text-slate-600 text-sm dark:text-white/60">
              第 {page} / {totalPages} 页
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

          </>
        )}
      </Card>

      {/* 用户详情弹窗 */}
      <Modal
        isOpen={showDetailModal}
        onClose={() => setShowDetailModal(false)}
        title="用户详情"
        size="md"
      >
        {selectedUser && (
          <div className="space-y-6">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 flex items-center justify-center">
                {selectedUser.avatar ? (
                  <FadeInImage
                    src={selectedUser.avatar}
                    alt=""
                    wrapperClassName="w-full h-full rounded-full"
                    className="h-full w-full rounded-full object-cover"
                  />
                ) : (
                  <span className="text-2xl text-white font-bold">{selectedUser.username[0].toUpperCase()}</span>
                )}
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">{selectedUser.nickname || selectedUser.username}</h3>
                <p className="text-slate-600 dark:text-white/50">@{selectedUser.username}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                <div className="flex items-center gap-2 text-slate-500 text-sm mb-1 dark:text-white/50">
                  <Mail className="h-4 w-4" />
                  邮箱
                </div>
                <p className="text-slate-900 dark:text-white">{selectedUser.email}</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                <div className="flex items-center gap-2 text-slate-500 text-sm mb-1 dark:text-white/50">
                  <Phone className="h-4 w-4" />
                  手机
                </div>
                <p className="text-slate-900 dark:text-white">{selectedUser.phone || '未绑定'}</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                <div className="flex items-center gap-2 text-slate-500 text-sm mb-1 dark:text-white/50">
                  <Shield className="h-4 w-4" />
                  角色
                </div>
                <p className="text-slate-900 dark:text-white">{getRoleBadge(selectedUser.role)}</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/5 dark:border-white/10">
                <div className="flex items-center gap-2 text-slate-500 text-sm mb-1 dark:text-white/50">
                  <Calendar className="h-4 w-4" />
                  注册时间
                </div>
                <p className="text-slate-900 dark:text-white">{new Date(selectedUser.created_at).toLocaleDateString()}</p>
              </div>
            </div>

            {userStats && (
              <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-200/70 dark:border-white/10">
                <div className="text-center">
                  <p className="text-2xl font-bold text-slate-900 dark:text-white">{userStats.post_count}</p>
                  <p className="text-slate-600 text-sm flex items-center justify-center gap-1 dark:text-white/50">
                    <MessageSquare className="h-4 w-4" />
                    帖子
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-slate-900 dark:text-white">{userStats.favorite_count}</p>
                  <p className="text-slate-600 text-sm flex items-center justify-center gap-1 dark:text-white/50">
                    <Heart className="h-4 w-4" />
                    收藏
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-slate-900 dark:text-white">{userStats.comment_count}</p>
                  <p className="text-slate-600 text-sm flex items-center justify-center gap-1 dark:text-white/50">
                    <UserIcon className="h-4 w-4" />
                    评论
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 修改角色弹窗 */}
      <Modal
        isOpen={showRoleModal}
        onClose={() => setShowRoleModal(false)}
        title="修改用户角色"
        size="sm"
      >
        {selectedUser && (
          <div className="space-y-4">
            <p className="text-slate-700 dark:text-white/70">
              正在修改用户 <span className="text-slate-900 font-medium dark:text-white">{selectedUser.nickname || selectedUser.username}</span> 的角色
            </p>
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
            >
              <option value="user">普通用户</option>
              <option value="lawyer">认证律师</option>
              <option value="admin">管理员</option>
            </select>
            <div className="flex gap-3 pt-2">
              <Button variant="secondary" onClick={() => setShowRoleModal(false)} className="flex-1">
                取消
              </Button>
              <Button onClick={handleSaveRole} isLoading={saveRoleMutation.isPending} className="flex-1">
                保存
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
