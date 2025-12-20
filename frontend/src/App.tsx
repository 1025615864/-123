import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import AdminLayout from './components/AdminLayout'
import ErrorBoundary from './components/ErrorBoundary'
import { AuthProvider } from './contexts/AuthContext'
import { ToastProvider } from './hooks'

// 懒加载前台页面
const HomePage = lazy(() => import('./pages/HomePage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const ForumPage = lazy(() => import('./pages/ForumPage'))
const NewsPage = lazy(() => import('./pages/NewsPage'))
const LawFirmPage = lazy(() => import('./pages/LawFirmPage'))
const SearchPage = lazy(() => import('./pages/SearchPage'))
const NotificationsFrontPage = lazy(() => import('./pages/NotificationsPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const PostDetailPage = lazy(() => import('./pages/PostDetailPage'))
const ChatHistoryPage = lazy(() => import('./pages/ChatHistoryPage'))
const NewsDetailPage = lazy(() => import('./pages/NewsDetailPage'))
const LawFirmDetailPage = lazy(() => import('./pages/LawFirmDetailPage'))
const FeeCalculatorPage = lazy(() => import('./pages/FeeCalculatorPage'))
const DocumentGeneratorPage = lazy(() => import('./pages/DocumentGeneratorPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

// 懒加载管理后台页面
const DashboardPage = lazy(() => import('./pages/admin/DashboardPage'))
const UsersPage = lazy(() => import('./pages/admin/UsersPage'))
const NewsManagePage = lazy(() => import('./pages/admin/NewsManagePage'))
const PostsManagePage = lazy(() => import('./pages/admin/PostsManagePage'))
const LawFirmsManagePage = lazy(() => import('./pages/admin/LawFirmsManagePage'))
const SettingsPage = lazy(() => import('./pages/admin/SettingsPage'))
const KnowledgeManagePage = lazy(() => import('./pages/admin/KnowledgeManagePage'))
const TemplatesManagePage = lazy(() => import('./pages/admin/TemplatesManagePage'))
const ForumManagePage = lazy(() => import('./pages/admin/ForumManagePage'))
const LogsPage = lazy(() => import('./pages/admin/LogsPage'))
const NotificationsPage = lazy(() => import('./pages/admin/NotificationsPage'))

// 加载中组件
function PageLoading() {
  return (
    <div className="min-h-[50vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 border-4 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
        <p className="text-slate-600 dark:text-white/50 text-sm">加载中...</p>
      </div>
    </div>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AuthProvider>
          <Suspense fallback={<PageLoading />}>
          <Routes>
            {/* 管理后台路由 */}
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<DashboardPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="news" element={<NewsManagePage />} />
            <Route path="posts" element={<PostsManagePage />} />
            <Route path="forum" element={<ForumManagePage />} />
            <Route path="lawfirms" element={<LawFirmsManagePage />} />
            <Route path="knowledge" element={<KnowledgeManagePage />} />
            <Route path="templates" element={<TemplatesManagePage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
          </Route>
          
          {/* 前台路由 */}
          <Route path="/" element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="chat/history" element={<ChatHistoryPage />} />
            <Route path="forum" element={<ForumPage />} />
            <Route path="forum/post/:postId" element={<PostDetailPage />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="notifications" element={<NotificationsFrontPage />} />
            <Route path="news" element={<NewsPage />} />
            <Route path="news/:newsId" element={<NewsDetailPage />} />
            <Route path="lawfirm" element={<LawFirmPage />} />
            <Route path="lawfirm/:firmId" element={<LawFirmDetailPage />} />
            <Route path="calculator" element={<FeeCalculatorPage />} />
            <Route path="documents" element={<DocumentGeneratorPage />} />
            <Route path="login" element={<LoginPage />} />
            <Route path="register" element={<RegisterPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
          </Suspense>
        </AuthProvider>
      </ToastProvider>
    </ErrorBoundary>
  )
}

export default App
