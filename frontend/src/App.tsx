import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import AdminLayout from "./components/AdminLayout";
import ErrorBoundary from "./components/ErrorBoundary";
import { RequireAuth, RequireLawyer } from "./components/RouteGuards";
import { AuthProvider } from "./contexts/AuthContext";
import { ToastProvider } from "./hooks";
import { useTranslation } from "./contexts/LanguageContext";

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
const OrdersHubPage = lazy(() => import("./pages/OrdersHubPage"));
const FeedbackPage = lazy(() => import("./pages/FeedbackPage"));
const LawyerIncomePage = lazy(() => import("./pages/LawyerIncomePage"));
const LawyerWithdrawPage = lazy(() => import("./pages/LawyerWithdrawPage"));
const LawyerWithdrawalsPage = lazy(() => import("./pages/LawyerWithdrawalsPage"));
const LawyerBankAccountsPage = lazy(() => import("./pages/LawyerBankAccountsPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const TermsPage = lazy(() => import("./pages/TermsPage"));
const PrivacyPolicyPage = lazy(() => import("./pages/PrivacyPolicyPage"));
const AiDisclaimerPage = lazy(() => import("./pages/AiDisclaimerPage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const PostDetailPage = lazy(() => import("./pages/PostDetailPage"));
const ChatHistoryPage = lazy(() => import("./pages/ChatHistoryPage"));
const NewsDetailPage = lazy(() => import("./pages/NewsDetailPage"));
const NewsTopicsPage = lazy(() => import("./pages/NewsTopicsPage"));
const NewsTopicDetailPage = lazy(() => import("./pages/NewsTopicDetailPage"));
const LawFirmDetailPage = lazy(() => import("./pages/LawFirmDetailPage"));
const LawyerDetailPage = lazy(() => import("./pages/LawyerDetailPage"));
const LawyerVerificationPage = lazy(() => import("./pages/LawyerVerificationPage"));
const LawyerDashboardPage = lazy(() => import("./pages/LawyerDashboardPage"));
const FeeCalculatorPage = lazy(() => import("./pages/FeeCalculatorPage"));
const LimitationsCalculatorPage = lazy(() => import("./pages/LimitationsCalculatorPage"));
const CalendarPage = lazy(() => import("./pages/CalendarPage"));
const DocumentGeneratorPage = lazy(() => import("./pages/DocumentGeneratorPage"));
const ContractReviewPage = lazy(() => import("./pages/ContractReviewPage"));
const FaqPage = lazy(() => import("./pages/FaqPage"));
const SharePage = lazy(() => import("./pages/SharePage"));
const VerifyEmailPage = lazy(() => import("./pages/VerifyEmailPage"));
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage"));
const PaymentReturnPage = lazy(() => import("./pages/PaymentReturnPage"));
const VipPage = lazy(() => import("./pages/VipPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

// 懒加载管理后台页面
const DashboardPage = lazy(() => import("./pages/admin/DashboardPage"));
const UsersPage = lazy(() => import("./pages/admin/UsersPage"));
const NewsManagePage = lazy(() => import("./pages/admin/NewsManagePage"));
const NewsSourcesManagePage = lazy(() => import("./pages/admin/NewsSourcesManagePage"));
const NewsTopicsManagePage = lazy(() => import("./pages/admin/NewsTopicsManagePage"));
const NewsCommentsManagePage = lazy(() => import("./pages/admin/NewsCommentsManagePage"));
const NewsIngestRunsPage = lazy(() => import("./pages/admin/NewsIngestRunsPage"));
const LawFirmsManagePage = lazy(() => import("./pages/admin/LawFirmsManagePage"));
const SettingsPage = lazy(() => import("./pages/admin/SettingsPage"));
const KnowledgeManagePage = lazy(() => import("./pages/admin/KnowledgeManagePage"));
const TemplatesManagePage = lazy(() => import("./pages/admin/TemplatesManagePage"));
const DocumentTemplatesManagePage = lazy(() => import("./pages/admin/DocumentTemplatesManagePage"));
const ForumManagePage = lazy(() => import("./pages/admin/ForumManagePage"));
const LawyerVerificationsPage = lazy(() => import("./pages/admin/LawyerVerificationsPage"));
const LogsPage = lazy(() => import("./pages/admin/LogsPage"));
const NotificationsPage = lazy(() => import("./pages/admin/NotificationsPage"));
const PaymentCallbacksPage = lazy(() => import("./pages/admin/PaymentCallbacksPage"));
const FeedbackTicketsPage = lazy(() => import("./pages/admin/FeedbackTicketsPage"));
const WithdrawalsPage = lazy(() => import("./pages/admin/WithdrawalsPage"));
const SettlementStatsPage = lazy(() => import("./pages/admin/SettlementStatsPage"));

// 加载中组件
function PageLoading() {
  const { t } = useTranslation();
  return (
    <div className="min-h-[50vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 border-4 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
        <p className="text-slate-600 dark:text-white/50 text-sm">{t('common.loading')}</p>
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
                <Route path="lawyer-verifications" element={<LawyerVerificationsPage />} />
                <Route path="knowledge" element={<KnowledgeManagePage />} />
                <Route path="templates" element={<TemplatesManagePage />} />
                <Route path="document-templates" element={<DocumentTemplatesManagePage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="logs" element={<LogsPage />} />
                <Route path="notifications" element={<NotificationsPage />} />
                <Route path="payment-callbacks" element={<PaymentCallbacksPage />} />
                <Route path="feedback" element={<FeedbackTicketsPage />} />
                <Route path="withdrawals" element={<WithdrawalsPage />} />
                <Route path="settlement-stats" element={<SettlementStatsPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>

              {/* 前台路由 */}
              <Route path="/" element={<Layout />}>
                <Route index element={<HomePage />} />
                <Route path="chat" element={<ChatPage />} />
                <Route
                  path="chat/history"
                  element={
                    <RequireAuth>
                      <ChatHistoryPage />
                    </RequireAuth>
                  }
                />
                <Route path="forum" element={<ForumPage />} />
                <Route
                  path="forum/new"
                  element={
                    <RequireAuth>
                      <NewPostPage />
                    </RequireAuth>
                  }
                />
                <Route
                  path="forum/drafts"
                  element={
                    <RequireAuth>
                      <DraftsPage />
                    </RequireAuth>
                  }
                />
                <Route
                  path="forum/recycle-bin"
                  element={
                    <RequireAuth>
                      <RecycleBinPage />
                    </RequireAuth>
                  }
                />
                <Route
                  path="forum/my-comments"
                  element={
                    <RequireAuth>
                      <MyCommentsPage />
                    </RequireAuth>
                  }
                />
                <Route path="forum/post/:postId" element={<PostDetailPage />} />
                <Route
                  path="forum/post/:postId/edit"
                  element={
                    <RequireAuth>
                      <EditPostPage />
                    </RequireAuth>
                  }
                />
                <Route path="search" element={<SearchPage />} />
                <Route
                  path="notifications"
                  element={
                    <RequireAuth>
                      <NotificationsFrontPage />
                    </RequireAuth>
                  }
                />
                <Route
                  path="feedback"
                  element={
                    <RequireAuth>
                      <FeedbackPage />
                    </RequireAuth>
                  }
                />
                <Route
                  path="orders"
                  element={
                    <RequireAuth>
                      <OrdersHubPage />
                    </RequireAuth>
                  }
                />
                <Route path="payment/return" element={<PaymentReturnPage />} />
                <Route path="news" element={<NewsPage />} />
                <Route
                  path="news/subscriptions"
                  element={
                    <RequireAuth>
                      <NewsSubscriptionsPage />
                    </RequireAuth>
                  }
                />
                <Route path="news/topics" element={<NewsTopicsPage />} />
                <Route path="news/topics/:topicId" element={<NewsTopicDetailPage />} />
                <Route path="news/:newsId" element={<NewsDetailPage />} />
                <Route path="lawfirm" element={<LawFirmPage />} />
                <Route
                  path="lawyer/verification"
                  element={
                    <RequireAuth>
                      <LawyerVerificationPage />
                    </RequireAuth>
                  }
                />
                <Route
                  path="lawyer"
                  element={
                    <RequireLawyer>
                      <LawyerDashboardPage />
                    </RequireLawyer>
                  }
                />
                <Route
                  path="lawyer/income"
                  element={
                    <RequireLawyer>
                      <LawyerIncomePage />
                    </RequireLawyer>
                  }
                />
                <Route
                  path="lawyer/withdraw"
                  element={
                    <RequireLawyer>
                      <LawyerWithdrawPage />
                    </RequireLawyer>
                  }
                />
                <Route
                  path="lawyer/withdrawals"
                  element={
                    <RequireLawyer>
                      <LawyerWithdrawalsPage />
                    </RequireLawyer>
                  }
                />
                <Route
                  path="lawyer/bank-accounts"
                  element={
                    <RequireLawyer>
                      <LawyerBankAccountsPage />
                    </RequireLawyer>
                  }
                />
                <Route
                  path="lawfirm/consultations"
                  element={<Navigate to="/orders?tab=consultations" replace />}
                />
                <Route path="lawfirm/lawyers/:lawyerId" element={<LawyerDetailPage />} />
                <Route path="lawfirm/:firmId" element={<LawFirmDetailPage />} />
                <Route path="calculator" element={<FeeCalculatorPage />} />
                <Route path="limitations" element={<LimitationsCalculatorPage />} />
                <Route
                  path="calendar"
                  element={
                    <RequireAuth>
                      <CalendarPage />
                    </RequireAuth>
                  }
                />
                <Route path="documents" element={<DocumentGeneratorPage />} />
                <Route path="contracts" element={<ContractReviewPage />} />
                <Route path="faq" element={<FaqPage />} />
                <Route path="share/:token" element={<SharePage />} />
                <Route path="verify-email" element={<VerifyEmailPage />} />
                <Route path="login" element={<LoginPage />} />
                <Route path="register" element={<RegisterPage />} />
                <Route path="forgot-password" element={<ForgotPasswordPage />} />
                <Route path="reset-password" element={<ResetPasswordPage />} />
                <Route path="terms" element={<TermsPage />} />
                <Route path="privacy" element={<PrivacyPolicyPage />} />
                <Route path="ai-disclaimer" element={<AiDisclaimerPage />} />
                <Route path="vip" element={<VipPage />} />
                <Route
                  path="profile"
                  element={
                    <RequireAuth>
                      <ProfilePage />
                    </RequireAuth>
                  }
                />
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
