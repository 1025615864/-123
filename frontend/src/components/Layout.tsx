import { useState } from "react";
import { Outlet, Link, useLocation } from "react-router-dom";
import {
  Scale,
  MessageCircle,
  Users,
  Newspaper,
  Search,
  Building2,
  LogOut,
  User,
  Menu,
  X,
  Phone,
  Mail,
  Calculator,
  Clock,
  Calendar,
  FileText,
  HelpCircle,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { Button, LinkButton } from "../components/ui";
import NotificationBell from "./NotificationBell";
import { MobileNav } from "./MobileNav";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { useIsMobile } from "../hooks/useMediaQuery";

export default function Layout() {
  const location = useLocation();
  const { isAuthenticated, user, logout } = useAuth();
  const { actualTheme } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isMobile = useIsMobile();

  const mobileMenuId = "layout-mobile-menu";

  const isChatRoute = location.pathname === "/chat" || location.pathname.startsWith("/chat/");

  const hideFooter =
    location.pathname === "/login" ||
    location.pathname === "/register" ||
    isChatRoute;

  const showMobileBottomNav = isMobile && !hideFooter;

  const navItems = [
    { path: "/", label: "首页", icon: Scale },
    { path: "/chat", label: "AI咨询", icon: MessageCircle },
    { path: "/forum", label: "论坛", icon: Users },
    { path: "/news", label: "新闻", icon: Newspaper },
    { path: "/search", label: "搜索", icon: Search },
    { path: "/lawfirm", label: "律所", icon: Building2 },
    { path: "/calculator", label: "费用计算", icon: Calculator },
    { path: "/limitations", label: "时效计算", icon: Clock },
    { path: "/calendar", label: "日历", icon: Calendar },
    { path: "/documents", label: "文书生成", icon: FileText },
    { path: "/faq", label: "FAQ", icon: HelpCircle },
  ];

  return (
    <div className="min-h-[100dvh] flex flex-col font-sans">
      <header
        className="sticky top-0 z-50 backdrop-blur-xl border-b flex justify-center bg-white/80 border-slate-200/60 dark:bg-slate-900/80 dark:border-white/5"
      >
        <div className="w-full max-w-7xl px-6 sm:px-8 lg:px-12">
          <div className="flex justify-between items-center h-[72px]">
            <Link to="/" className="flex items-center space-x-3 group flex-shrink-0 outline-none rounded-xl transition-all active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900">
              <div className="relative">
                <div className="absolute inset-0 bg-blue-500 rounded-xl blur opacity-20 group-hover:opacity-40 transition-opacity" />
                <div className="relative bg-gradient-to-br from-blue-600 to-indigo-600 p-2 rounded-xl shadow-lg shadow-blue-500/20">
                  <Scale className="h-5 w-5 text-white" />
                </div>
              </div>
              <span className="text-lg font-bold text-slate-900 dark:text-white tracking-tight">
                百姓法律助手
              </span>
            </Link>

            <nav className="hidden lg:flex flex-1 items-center justify-center">
              <div className="flex items-center gap-8">
                {navItems.map(({ path, label }) => (
                  <Link
                    key={path}
                    to={path}
                    aria-current={location.pathname === path ? "page" : undefined}
                    className={`text-sm font-medium transition-colors relative py-1 outline-none rounded-md focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 ${
                      location.pathname === path
                        ? "text-blue-600 dark:text-blue-400"
                        : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
                    }`}
                  >
                    {label}
                    {location.pathname === path && (
                      <span className="absolute bottom-0 left-0 w-full h-0.5 bg-blue-600 rounded-full dark:bg-blue-400" />
                    )}
                  </Link>
                ))}
              </div>
            </nav>

            <div className="flex items-center space-x-4">
              {/* 主题和语言切换 */}
              <div className="hidden sm:flex items-center space-x-2 border-r border-slate-200 pr-4 mr-2 dark:border-slate-700">
                <ThemeSwitcher className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white" />
                <LanguageSwitcher className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white" />
              </div>
              
              {isAuthenticated ? (
                <div className="hidden sm:flex items-center space-x-4">
                  <NotificationBell tone={actualTheme} />
                  {user?.role === 'admin' && (
                    <Link
                      to="/admin"
                      className="px-3 py-1.5 rounded-full text-xs font-medium outline-none transition-all bg-slate-100 text-slate-700 hover:bg-slate-200 active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 dark:focus-visible:ring-offset-slate-900"
                    >
                      管理后台
                    </Link>
                  )}
                  <Link
                    to="/profile"
                    className="flex items-center space-x-2 px-1 py-1 rounded-full outline-none transition-all hover:bg-slate-50 active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:hover:bg-slate-800 dark:focus-visible:ring-offset-slate-900"
                  >
                    <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center border border-white shadow-sm dark:bg-slate-700 dark:border-slate-600">
                      <User className="h-4 w-4 text-slate-500 dark:text-slate-300" />
                    </div>
                  </Link>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={logout}
                    className="text-slate-500 hover:text-red-600"
                  >
                    <LogOut className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <div className="hidden sm:flex items-center space-x-3">
                  <LinkButton
                    to="/login"
                    variant="ghost"
                    size="sm"
                    className="font-medium text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                  >
                    登录
                  </LinkButton>
                  <LinkButton
                    to="/register"
                    size="sm"
                    className="px-5 py-2 rounded-lg text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-md shadow-blue-500/20 hover:shadow-lg hover:shadow-blue-500/30 transition-all"
                  >
                    注册
                  </LinkButton>
                </div>
              )}

              <button
                type="button"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                aria-label={mobileMenuOpen ? "关闭菜单" : "打开菜单"}
                aria-expanded={mobileMenuOpen}
                aria-controls={mobileMenuId}
                className="lg:hidden p-2 rounded-lg text-slate-600 outline-none transition-all hover:bg-slate-50 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:text-slate-300 dark:hover:bg-slate-800 dark:focus-visible:ring-offset-slate-900"
              >
                {mobileMenuOpen ? (
                  <X className="h-6 w-6" />
                ) : (
                  <Menu className="h-6 w-6" />
                )}
              </button>
            </div>
          </div>
        </div>

        {mobileMenuOpen && (
          <div
            id={mobileMenuId}
            className="lg:hidden border-t animate-fade-in border-slate-200 bg-white/95 backdrop-blur-xl dark:border-slate-800 dark:bg-slate-900/95"
          >
            <div className="px-6 py-6 space-y-2">
              {navItems.map(({ path, label, icon: Icon }) => (
                <Link
                  key={path}
                  to={path}
                  onClick={() => setMobileMenuOpen(false)}
                  aria-current={location.pathname === path ? "page" : undefined}
                  className={`flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition-all outline-none active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 ${
                    location.pathname === path
                      ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
                      : 'text-slate-700 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800'
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  <span>{label}</span>
                </Link>
              ))}
              <div className="pt-4 border-t border-slate-200 dark:border-slate-800 mt-4">
                {isAuthenticated ? (
                  <Button
                    variant="danger"
                    fullWidth
                    icon={LogOut}
                    onClick={() => {
                      logout();
                      setMobileMenuOpen(false);
                    }}
                    className="py-3 justify-center"
                  >
                    退出登录
                  </Button>
                ) : (
                  <div className="space-y-3">
                    <LinkButton
                      to="/login"
                      variant="outline"
                      fullWidth
                      onClick={() => setMobileMenuOpen(false)}
                      className="py-3 justify-center"
                    >
                      登录
                    </LinkButton>
                    <LinkButton
                      to="/register"
                      fullWidth
                      onClick={() => setMobileMenuOpen(false)}
                      className="py-3 justify-center bg-blue-600 text-white"
                    >
                      注册账号
                    </LinkButton>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </header>

      <main
        className={`flex-1 flex justify-center min-h-0 ${showMobileBottomNav ? 'pb-[calc(56px+env(safe-area-inset-bottom))]' : ''}`}
      >
        <div
          className={`w-full max-w-7xl px-4 sm:px-6 lg:px-8 ${
            isChatRoute ? "py-4 md:py-6" : "py-8 md:py-12"
          } flex flex-col min-h-0 animate-fade-in`}
        >
          <Outlet />
        </div>
      </main>
      
      {/* 移动端底部导航 */}
      {showMobileBottomNav && <MobileNav />}

      {!hideFooter && (
      <footer className="mt-auto border-t border-slate-200 bg-slate-50 flex justify-center dark:border-slate-800 dark:bg-slate-900/50">
        <div className="w-full max-w-7xl px-6 sm:px-10 lg:px-12 py-12">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-12">
            <div className="md:col-span-2">
              <div className="flex items-center space-x-3 mb-6">
                <div className="bg-blue-600 p-1.5 rounded-lg shadow-sm">
                  <Scale className="h-5 w-5 text-white" />
                </div>
                <span className="text-lg font-bold text-slate-900 dark:text-white">百姓法律助手</span>
              </div>
              <p className="text-slate-500 text-sm leading-relaxed mb-6 max-w-sm dark:text-slate-400">
                致力于让每一位公民都能享受到专业、便捷的法律服务。专业律师团队与先进AI技术相结合，为您保驾护航。
              </p>
              <div className="flex space-x-3">
                <a
                  href="#"
                  className="w-10 h-10 rounded-full bg-white border border-slate-200 flex items-center justify-center outline-none transition-all hover:border-blue-500 hover:text-blue-600 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:bg-slate-800 dark:border-slate-700 dark:hover:border-blue-400 dark:focus-visible:ring-offset-slate-900"
                >
                  <Phone className="h-4 w-4" />
                </a>
                <a
                  href="#"
                  className="w-10 h-10 rounded-full bg-white border border-slate-200 flex items-center justify-center outline-none transition-all hover:border-blue-500 hover:text-blue-600 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:bg-slate-800 dark:border-slate-700 dark:hover:border-blue-400 dark:focus-visible:ring-offset-slate-900"
                >
                  <Mail className="h-4 w-4" />
                </a>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-bold text-slate-900 mb-6 dark:text-white">快速链接</h3>
              <ul className="space-y-3">
                {navItems.slice(0, 5).map(({ path, label }) => (
                  <li key={path}>
                    <Link
                      to={path}
                      className="text-slate-500 hover:text-blue-600 transition-colors text-sm outline-none rounded-md active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 dark:text-slate-400 dark:hover:text-blue-400 dark:focus-visible:ring-offset-slate-900"
                    >
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-bold text-slate-900 mb-6 dark:text-white">联系我们</h3>
              <ul className="space-y-4 text-sm text-slate-500 dark:text-slate-400">
                <li className="flex items-center space-x-3">
                  <Phone className="h-4 w-4 text-blue-500" />
                  <span>400-123-4567</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Mail className="h-4 w-4 text-blue-500" />
                  <span>help@baixing-law.com</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Building2 className="h-4 w-4 text-blue-500" />
                  <span>北京市朝阳区法律大厦A座</span>
                </li>
              </ul>
            </div>
          </div>

          <div className="border-t border-slate-200 mt-12 pt-8 flex flex-col sm:flex-row justify-between items-center dark:border-slate-800">
            <p className="text-slate-400 text-sm">
              © 2024 百姓法律助手. All rights reserved.
            </p>
            <div className="flex space-x-6 mt-4 sm:mt-0">
              <a href="#" className="text-slate-400 hover:text-slate-600 text-sm outline-none rounded-md transition-colors active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 dark:focus-visible:ring-offset-slate-900">
                隐私政策
              </a>
              <a href="#" className="text-slate-400 hover:text-slate-600 text-sm outline-none rounded-md transition-colors active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 dark:focus-visible:ring-offset-slate-900">
                服务条款
              </a>
            </div>
          </div>
        </div>
      </footer>
      )}
    </div>
  );
}
