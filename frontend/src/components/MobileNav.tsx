// 移动端底部导航组件
import { Link, useLocation } from 'react-router-dom';
import { useMemo, useState } from 'react';
import { Calendar, Home, MessageSquare, MoreHorizontal, Newspaper, Scale, User, Search } from 'lucide-react';
import { Modal } from './ui';

interface NavItem {
  path: string;
  label: string;
  icon: typeof Home;
}

const primaryNavItems: NavItem[] = [
  { path: '/', label: '首页', icon: Home },
  { path: '/news', label: '资讯', icon: Newspaper },
  { path: '/chat', label: '咨询', icon: Scale },
  { path: '/search', label: '搜索', icon: Search },
  { path: '/profile', label: '我的', icon: User },
];

const moreNavItems: NavItem[] = [
  { path: '/forum', label: '论坛', icon: MessageSquare },
  { path: '/calendar', label: '日历', icon: Calendar },
];

export function MobileNav() {
  const location = useLocation();
  const [moreOpen, setMoreOpen] = useState(false);

  const isMoreActive = useMemo(() => {
    return moreNavItems.some(
      (item) => location.pathname === item.path || location.pathname.startsWith(item.path)
    );
  }, [location.pathname]);

  const linkClassName = (active: boolean) =>
    `group flex flex-col items-center justify-center flex-1 h-full select-none outline-none transition-all duration-200 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 ${
      active
        ? 'text-blue-600 dark:text-blue-400'
        : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
    }`;

  const iconWrapClassName = (active: boolean) =>
    `relative flex items-center justify-center w-10 h-8 rounded-xl transition-all duration-200 group-active:scale-95 ${
      active
        ? 'bg-blue-50 group-hover:bg-blue-100/70 dark:bg-blue-900/20 dark:group-hover:bg-blue-900/30'
        : 'bg-transparent group-hover:bg-slate-100/70 dark:group-hover:bg-white/5'
    }`;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden pb-[env(safe-area-inset-bottom)] bg-white/95 dark:bg-slate-900/90 backdrop-blur-xl border-t border-slate-200/70 dark:border-white/10 shadow-[0_-12px_30px_-20px_rgba(15,23,42,0.22)] dark:shadow-[0_-12px_30px_-20px_rgba(0,0,0,0.65)]">
      <div className="flex justify-around items-center h-14">
        {primaryNavItems.map(({ path, label, icon: Icon }) => {
          const isActive = location.pathname === path || 
            (path !== '/' && location.pathname.startsWith(path));
          
          return (
            <Link
              key={path}
              to={path}
              aria-label={label}
              aria-current={isActive ? 'page' : undefined}
              className={linkClassName(isActive)}
            >
              <div
                className={iconWrapClassName(isActive)}
              >
                <Icon className="w-5 h-5" />
                {isActive ? (
                  <span className="absolute -bottom-1 w-1.5 h-1.5 rounded-full bg-blue-600 dark:bg-blue-400" />
                ) : null}
              </div>
              <span className="text-[11px] mt-1 leading-none">{label}</span>
            </Link>
          );
        })}

        <button
          type="button"
          onClick={() => setMoreOpen(true)}
          aria-label="更多"
          aria-current={isMoreActive ? 'page' : undefined}
          className={linkClassName(isMoreActive)}
        >
          <div className={iconWrapClassName(isMoreActive)}>
            <MoreHorizontal className="w-5 h-5" />
            {isMoreActive ? (
              <span className="absolute -bottom-1 w-1.5 h-1.5 rounded-full bg-blue-600 dark:bg-blue-400" />
            ) : null}
          </div>
          <span className="text-[11px] mt-1 leading-none">更多</span>
        </button>
      </div>

      <Modal
        isOpen={moreOpen}
        onClose={() => setMoreOpen(false)}
        title="更多"
        description="快速进入其它功能"
        size="sm"
        zIndexClass="z-[60]"
      >
        <div className="grid grid-cols-2 gap-3">
          {moreNavItems.map(({ path, label, icon: Icon }) => {
            const isActive =
              location.pathname === path ||
              (path !== '/' && location.pathname.startsWith(path));
            return (
              <Link
                key={path}
                to={path}
                onClick={() => setMoreOpen(false)}
                className={`group flex items-center gap-3 rounded-2xl border px-4 py-4 outline-none transition-all duration-200 active:scale-[0.99] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 ${
                  isActive
                    ? 'border-blue-200 bg-blue-50 text-blue-700 shadow-sm dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-200 dark:shadow-none'
                    : 'border-slate-200/70 bg-white text-slate-700 hover:bg-slate-50 hover:border-slate-300 hover:shadow-sm dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-200 dark:hover:bg-white/[0.05] dark:hover:border-white/20 dark:hover:shadow-none'
                } focus-visible:border-blue-500 dark:focus-visible:border-blue-400`}
              >
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 group-hover:scale-[1.02] ${
                    isActive
                      ? 'bg-blue-600 text-white dark:bg-blue-500'
                      : 'bg-slate-100 text-slate-700 group-hover:bg-slate-200/80 dark:bg-slate-800 dark:text-slate-200 dark:group-hover:bg-slate-700'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold truncate">{label}</div>
                  <div className="text-xs opacity-70 truncate">{path}</div>
                </div>
              </Link>
            );
          })}
        </div>
      </Modal>
    </nav>
  );
}

// 移动端抽屉菜单
interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

export function MobileDrawer({ isOpen, onClose, children }: MobileDrawerProps) {
  if (!isOpen) return null;

  return (
    <>
      {/* 遮罩层 */}
      <div
        className="fixed inset-0 z-40 md:hidden bg-black/40 backdrop-blur-sm transition-opacity duration-200 dark:bg-black/70"
        onClick={onClose}
      />
      {/* 抽屉 */}
      <div
        className={`fixed top-0 left-0 h-full w-64 bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl border-r border-slate-200/70 dark:border-white/10 z-50 shadow-xl shadow-slate-900/10 dark:shadow-black/40 transform transition-transform duration-300 md:hidden overflow-y-auto ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {children}
      </div>
    </>
  );
}

// 移动端头部
interface MobileHeaderProps {
  title?: string;
  onMenuClick?: () => void;
  showBack?: boolean;
  onBackClick?: () => void;
  rightAction?: React.ReactNode;
}

export function MobileHeader({
  title = '',
  onMenuClick,
  showBack = false,
  onBackClick,
  rightAction,
}: MobileHeaderProps) {
  return (
    <header className="fixed top-0 left-0 right-0 h-12 z-40 flex items-center justify-between px-4 md:hidden bg-white/85 dark:bg-slate-900/85 backdrop-blur-xl border-b border-slate-200/70 dark:border-white/10">
      <div className="w-10">
        {showBack && onBackClick && (
          <button
            onClick={onBackClick}
            className="-ml-2 p-2 rounded-lg text-slate-700 outline-none transition-all hover:bg-slate-900/5 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:text-slate-200 dark:hover:bg-white/5 dark:focus-visible:ring-offset-slate-900"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        )}
        {!showBack && onMenuClick && (
          <button
            onClick={onMenuClick}
            className="-ml-2 p-2 rounded-lg text-slate-700 outline-none transition-all hover:bg-slate-900/5 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:text-slate-200 dark:hover:bg-white/5 dark:focus-visible:ring-offset-slate-900"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}
      </div>
      <h1 className="text-lg font-medium truncate text-slate-900 dark:text-white">{title}</h1>
      <div className="w-10 flex justify-end">
        {rightAction}
      </div>
    </header>
  );
}
