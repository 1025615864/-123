import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  Newspaper,
  Building2,
  Settings,
  LogOut,
  Scale,
  ChevronRight,
  Database,
  FileQuestion,
  Flame,
  FileText,
  Bell,
  Layers,
  MessageSquare,
  Rss,
  Activity,
  Shield,
  CreditCard,
  BarChart3,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { Button, EmptyState } from './ui'

type SidebarLeafItem = {
  icon: typeof LayoutDashboard
  label: string
  path: string
}

type SidebarGroupItem = {
  icon: typeof LayoutDashboard
  label: string
  path: string
  children: SidebarLeafItem[]
}

type SidebarItem = SidebarLeafItem | SidebarGroupItem

function isGroup(item: SidebarItem): item is SidebarGroupItem {
  return Array.isArray((item as SidebarGroupItem).children)
}

const sidebarItems: SidebarItem[] = [
  { icon: LayoutDashboard, label: '仪表盘', path: '/admin' },
  { icon: Users, label: '用户管理', path: '/admin/users' },
  {
    icon: Newspaper,
    label: '内容运营',
    path: '/admin/news',
    children: [
      { icon: Newspaper, label: '新闻列表', path: '/admin/news' },
      { icon: Rss, label: 'RSS 来源', path: '/admin/news/sources' },
      { icon: Activity, label: '采集运行记录', path: '/admin/news/ingest-runs' },
      { icon: Layers, label: '新闻专题', path: '/admin/news/topics' },
      { icon: MessageSquare, label: '新闻评论', path: '/admin/news/comments' },
      { icon: Flame, label: '论坛管理', path: '/admin/forum' },
    ],
  },
  {
    icon: Building2,
    label: '律所与律师',
    path: '/admin/lawfirms',
    children: [
      { icon: Building2, label: '律所管理', path: '/admin/lawfirms' },
      { icon: Shield, label: '律师认证', path: '/admin/lawyer-verifications' },
    ],
  },
  {
    icon: Database,
    label: '知识与模板',
    path: '/admin/knowledge',
    children: [
      { icon: Database, label: '知识库管理', path: '/admin/knowledge' },
      { icon: FileQuestion, label: '咨询模板', path: '/admin/templates' },
      { icon: FileText, label: '文书模板', path: '/admin/document-templates' },
    ],
  },
  {
    icon: CreditCard,
    label: '财务与支付',
    path: '/admin/withdrawals',
    children: [
      { icon: CreditCard, label: '提现审核', path: '/admin/withdrawals' },
      { icon: BarChart3, label: '结算统计', path: '/admin/settlement-stats' },
      { icon: CreditCard, label: '支付回调', path: '/admin/payment-callbacks' },
    ],
  },
  {
    icon: Settings,
    label: '系统与审计',
    path: '/admin/settings',
    children: [
      { icon: Settings, label: '系统设置', path: '/admin/settings' },
      { icon: FileText, label: '操作日志', path: '/admin/logs' },
      { icon: Bell, label: '通知管理', path: '/admin/notifications' },
      { icon: MessageSquare, label: '客服反馈', path: '/admin/feedback' },
    ],
  },
]

export default function AdminLayout() {
  const location = useLocation()
  const { user, logout, isAuthenticated } = useAuth()

  const leafItems = useMemo(() => {
    const out: SidebarLeafItem[] = []
    for (const item of sidebarItems) {
      if (isGroup(item)) {
        out.push(...item.children)
      } else {
        out.push(item)
      }
    }
    return out
  }, [])

  const activePath = (
    leafItems
      .filter(
        (i) =>
          location.pathname === i.path ||
          (i.path !== '/admin' && location.pathname.startsWith(i.path + '/'))
      )
      .sort((a, b) => b.path.length - a.path.length)[0]?.path ?? '/admin'
  )

  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const groupPathsToOpen: string[] = []
    for (const item of sidebarItems) {
      if (!isGroup(item)) continue
      const groupActive = item.children.some((c) => c.path === activePath)
      if (groupActive) groupPathsToOpen.push(item.path)
    }
    if (!groupPathsToOpen.length) return
    setOpenGroups((prev) => {
      const next = { ...prev }
      for (const p of groupPathsToOpen) next[p] = true
      return next
    })
  }, [activePath])

  // 权限检查：必须登录且为管理员
  if (!isAuthenticated) {
    const redirect = `${location.pathname}${location.search}`
    return <Navigate to={`/login?return_to=${encodeURIComponent(redirect)}`} replace />
  }

  if (user?.role !== 'admin' && user?.role !== 'super_admin') {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-[#0a0618] flex items-center justify-center px-6">
        <div className="w-full max-w-lg">
          <EmptyState
            icon={Shield}
            title="需要管理员权限"
            description="当前账号无权访问管理后台，请切换管理员账号登录"
            tone="dark"
            action={
              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                <Button
                  variant="outline"
                  onClick={async () => {
                    try {
                      await logout()
                    } finally {
                      // noop
                    }
                  }}
                >
                  退出登录
                </Button>
                <Link to="/">
                  <Button>返回首页</Button>
                </Link>
              </div>
            }
          />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0a0618] flex">
      {/* 侧边栏 */}
      <aside className="w-64 bg-white border-r border-slate-200/70 flex flex-col dark:bg-[#0f0a1e] dark:border-white/5">
        {/* Logo */}
        <div className="p-6 border-b border-slate-200/70 dark:border-white/5">
          <Link to="/admin" className="flex items-center gap-3">
            <div className="bg-gradient-to-r from-amber-500 to-orange-500 p-2 rounded-xl">
              <Scale className="h-5 w-5 text-white" />
            </div>
            <div>
              <span className="text-slate-900 font-semibold dark:text-white">百姓法律助手</span>
              <span className="block text-xs text-slate-500 dark:text-white/40">管理后台</span>
            </div>
          </Link>
        </div>

        {/* 导航菜单 */}
        <nav className="flex-1 p-4 space-y-1">
          {sidebarItems.map((item) => {
            if (isGroup(item)) {
              const Icon = item.icon
              const groupActive = item.children.some((c) => c.path === activePath)
              const isOpen = openGroups[item.path] ?? groupActive
              return (
                <div key={item.path} className="space-y-1">
                  <div
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                      groupActive
                        ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-white/60 dark:hover:bg-white/5 dark:hover:text-white'
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    <Link to={item.path} className="text-sm font-medium flex-1">
                      {item.label}
                    </Link>
                    <button
                      type="button"
                      onClick={() =>
                        setOpenGroups((prev) => ({
                          ...prev,
                          [item.path]: !(prev[item.path] ?? false),
                        }))
                      }
                      className="p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/10"
                      aria-label={isOpen ? `折叠${item.label}` : `展开${item.label}`}
                      aria-expanded={isOpen}
                    >
                      <ChevronRight
                        className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-90' : ''}`}
                      />
                    </button>
                  </div>

                  {isOpen ? (
                    <div className="pl-4">
                      {item.children.map(({ icon: ChildIcon, label, path }) => {
                        const isActive = activePath === path
                        return (
                          <Link
                            key={path}
                            to={path}
                            className={`flex items-center gap-3 px-4 py-2 rounded-xl transition-all ${
                              isActive
                                ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
                                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-white/60 dark:hover:bg-white/5 dark:hover:text-white'
                            }`}
                          >
                            <ChildIcon className="h-4 w-4" />
                            <span className="text-sm font-medium">{label}</span>
                            {isActive && <ChevronRight className="h-4 w-4 ml-auto" />}
                          </Link>
                        )
                      })}
                    </div>
                  ) : null}
                </div>
              )
            }

            const Icon = item.icon
            const { label, path } = item
            const isActive = activePath === path

            return (
              <Link
                key={path}
                to={path}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                  isActive
                    ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-white/60 dark:hover:bg-white/5 dark:hover:text-white'
                }`}
              >
                <Icon className="h-5 w-5" />
                <span className="text-sm font-medium">{label}</span>
                {isActive && <ChevronRight className="h-4 w-4 ml-auto" />}
              </Link>
            )
          })}
        </nav>

        {/* 用户信息 */}
        <div className="p-4 border-t border-slate-200/70 dark:border-white/5">
          <div className="flex items-center gap-3 px-4 py-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 flex items-center justify-center">
              <span className="text-white font-semibold">
                {user?.username?.[0]?.toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-slate-900 dark:text-white text-sm font-medium truncate">
                {user?.nickname || user?.username}
              </p>
              <p className="text-slate-500 dark:text-white/40 text-xs">管理员</p>
            </div>
            <button
              onClick={logout}
              className="p-2 text-slate-500 hover:text-slate-900 transition-colors dark:text-white/40 dark:hover:text-white"
              title="退出登录"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
