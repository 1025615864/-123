// 移动端底部导航组件
import { Link, useLocation } from 'react-router-dom';
import { Home, MessageSquare, Newspaper, Scale, User, Search, Calendar } from 'lucide-react';

interface NavItem {
  path: string;
  label: string;
  icon: typeof Home;
}

const navItems: NavItem[] = [
  { path: '/', label: '首页', icon: Home },
  { path: '/forum', label: '论坛', icon: MessageSquare },
  { path: '/search', label: '搜索', icon: Search },
  { path: '/news', label: '资讯', icon: Newspaper },
  { path: '/chat', label: '咨询', icon: Scale },
  { path: '/calendar', label: '日历', icon: Calendar },
  { path: '/profile', label: '我的', icon: User },
];

export function MobileNav() {
  const location = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 z-50 md:hidden">
      <div className="flex justify-around items-center h-14">
        {navItems.map(({ path, label, icon: Icon }) => {
          const isActive = location.pathname === path || 
            (path !== '/' && location.pathname.startsWith(path));
          
          return (
            <Link
              key={path}
              to={path}
              aria-label={label}
              aria-current={isActive ? 'page' : undefined}
              className={`flex flex-col items-center justify-center flex-1 h-full transition-colors ${
                isActive
                  ? 'text-blue-600 dark:text-blue-400'
                  : 'text-gray-500 dark:text-gray-400'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="text-xs mt-1">{label}</span>
            </Link>
          );
        })}
      </div>
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
        className="fixed inset-0 bg-black/50 z-40 md:hidden"
        onClick={onClose}
      />
      {/* 抽屉 */}
      <div
        className={`fixed top-0 left-0 h-full w-64 bg-white dark:bg-gray-900 z-50 transform transition-transform duration-300 md:hidden ${
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
    <header className="fixed top-0 left-0 right-0 h-12 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 z-40 flex items-center justify-between px-4 md:hidden">
      <div className="w-10">
        {showBack && onBackClick && (
          <button onClick={onBackClick} className="p-2 -ml-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        )}
        {!showBack && onMenuClick && (
          <button onClick={onMenuClick} className="p-2 -ml-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}
      </div>
      <h1 className="text-lg font-medium truncate">{title}</h1>
      <div className="w-10 flex justify-end">
        {rightAction}
      </div>
    </header>
  );
}
