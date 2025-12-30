import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import AdminLayout from "./components/AdminLayout";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider } from "./contexts/AuthContext";
import { ToastProvider } from "./hooks";

// 懒加载前台页面
const HomePage = lazy(() => import("./pages/HomePage"));
const ChatPage = lazy(() => import("./pages/ChatPage"));
const ForumPage = lazy(() => import("./pages/ForumPage"));
const NewPostPage = lazy(() => import("./pages/NewPostPage"));
const DraftsPage = lazy(() => import("./pages/DraftsPage"));
const EditPostPage = lazy(() => import("./pages/EditPostPage"));
const RecycleBinPage = lazy(() => import("./pages/RecycleBinPage"));
const MyCommentsPage = lazy(() => import("./pages/MyCommentsPage"));
const NewsPage = lazy(() => import("./pages/NewsPage"));
const NewsSubscriptionsPage = lazy(
  () => import("./pages/NewsSubscriptionsPage")
);
const LawFirmPage = lazy(() => import("./pages/LawFirmPage"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const NotificationsFrontPage = lazy(() => import("./pages/NotificationsPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const PostDetailPage = lazy(() => import("./pages/PostDetailPage"));
const ChatHistoryPage = lazy(() => import("./pages/ChatHistoryPage"));
const NewsDetailPage = lazy(() => import("./pages/NewsDetailPage"));
const NewsTopicsPage = lazy(() => import("./pages/NewsTopicsPage"));
const NewsTopicDetailPage = lazy(() => import("./pages/NewsTopicDetailPage"));
const LawFirmDetailPage = lazy(() => import("./pages/LawFirmDetailPage"));
const FeeCalculatorPage = lazy(() => import("./pages/FeeCalculatorPage"));
const LimitationsCalculatorPage = lazy(
  () => import("./pages/LimitationsCalculatorPage")
);
const CalendarPage = lazy(() => import("./pages/CalendarPage"));
const DocumentGeneratorPage = lazy(
  () => import("./pages/DocumentGeneratorPage")
);
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

// 懒加载管理后台页面
const DashboardPage = lazy(() => import("./pages/admin/DashboardPage"));
const UsersPage = lazy(() => import("./pages/admin/UsersPage"));
const NewsManagePage = lazy(() => import("./pages/admin/NewsManagePage"));
const NewsSourcesManagePage = lazy(
  () => import("./pages/admin/NewsSourcesManagePage")
);
const NewsTopicsManagePage = lazy(
  () => import("./pages/admin/NewsTopicsManagePage")
);
const NewsCommentsManagePage = lazy(
  () => import("./pages/admin/NewsCommentsManagePage")
);
const NewsIngestRunsPage = lazy(
  () => import("./pages/admin/NewsIngestRunsPage")
);
const LawFirmsManagePage = lazy(
  () => import("./pages/admin/LawFirmsManagePage")
);
const SettingsPage = lazy(() => import("./pages/admin/SettingsPage"));
const KnowledgeManagePage = lazy(
  () => import("./pages/admin/KnowledgeManagePage")
);
const TemplatesManagePage = lazy(
  () => import("./pages/admin/TemplatesManagePage")
);
const ForumManagePage = lazy(() => import("./pages/admin/ForumManagePage"));
const LogsPage = lazy(() => import("./pages/admin/LogsPage"));
const NotificationsPage = lazy(() => import("./pages/admin/NotificationsPage"));

// 加载中组件
function PageLoading() {
  return (
    <div className="min-h-[50vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 border-4 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
        <p className="text-slate-600 dark:text-white/50 text-sm">加载中...</p>
      </div>
    </div>
  );
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
                <Route path="news/sources" element={<NewsSourcesManagePage />} />
                <Route path="news/ingest-runs" element={<NewsIngestRunsPage />} />
                <Route path="news/topics" element={<NewsTopicsManagePage />} />
                <Route path="news/comments" element={<NewsCommentsManagePage />} />
                <Route path="forum" element={<ForumManagePage />} />
                <Route path="lawfirms" element={<LawFirmsManagePage />} />
                <Route path="knowledge" element={<KnowledgeManagePage />} />
                <Route path="templates" element={<TemplatesManagePage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="logs" element={<LogsPage />} />
                <Route path="notifications" element={<NotificationsPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>

              {/* 前台路由 */}
              <Route path="/" element={<Layout />}>
                <Route index element={<HomePage />} />
                <Route path="chat" element={<ChatPage />} />
                <Route path="chat/history" element={<ChatHistoryPage />} />
                <Route path="forum" element={<ForumPage />} />
                <Route path="forum/new" element={<NewPostPage />} />
                <Route path="forum/drafts" element={<DraftsPage />} />
                <Route path="forum/recycle-bin" element={<RecycleBinPage />} />
                <Route path="forum/my-comments" element={<MyCommentsPage />} />
                <Route path="forum/post/:postId" element={<PostDetailPage />} />
                <Route
                  path="forum/post/:postId/edit"
                  element={<EditPostPage />}
                />
                <Route path="search" element={<SearchPage />} />
                <Route
                  path="notifications"
                  element={<NotificationsFrontPage />}
                />
                <Route path="news" element={<NewsPage />} />
                <Route
                  path="news/subscriptions"
                  element={<NewsSubscriptionsPage />}
                />
                <Route path="news/topics" element={<NewsTopicsPage />} />
                <Route path="news/topics/:topicId" element={<NewsTopicDetailPage />} />
                <Route path="news/:newsId" element={<NewsDetailPage />} />
                <Route path="lawfirm" element={<LawFirmPage />} />
                <Route path="lawfirm/:firmId" element={<LawFirmDetailPage />} />
                <Route path="calculator" element={<FeeCalculatorPage />} />
                <Route path="limitations" element={<LimitationsCalculatorPage />} />
                <Route path="calendar" element={<CalendarPage />} />
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
  );
}

export default App;
