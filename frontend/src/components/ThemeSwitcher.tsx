// 主题切换组件
import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme, Theme } from '../contexts/ThemeContext';

interface ThemeSwitcherProps {
  className?: string;
  showLabel?: boolean;
}

export function ThemeSwitcher({ className = '', showLabel = false }: ThemeSwitcherProps) {
  const { actualTheme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={`flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${className}`}
      title={actualTheme === 'dark' ? '切换到亮色模式' : '切换到暗黑模式'}
    >
      {actualTheme === 'dark' ? (
        <Sun className="w-4 h-4" />
      ) : (
        <Moon className="w-4 h-4" />
      )}
      {showLabel && (
        <span className="text-sm">
          {actualTheme === 'dark' ? '亮色' : '暗黑'}
        </span>
      )}
    </button>
  );
}

// 完整版本：包含系统选项
export function ThemeSelector({ className = '' }: ThemeSwitcherProps) {
  const { theme, setTheme } = useTheme();

  const options: { value: Theme; label: string; icon: typeof Sun }[] = [
    { value: 'light', label: '亮色', icon: Sun },
    { value: 'dark', label: '暗黑', icon: Moon },
    { value: 'system', label: '系统', icon: Monitor },
  ];

  return (
    <div className={`flex items-center gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg ${className}`}>
      {options.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          onClick={() => setTheme(value)}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-md text-sm transition-colors ${
            theme === value
              ? 'bg-white dark:bg-gray-700 shadow-sm text-blue-600 dark:text-blue-400'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
          }`}
        >
          <Icon className="w-4 h-4" />
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}

// 下拉选择版本
export function ThemeDropdown({ className = '' }: ThemeSwitcherProps) {
  const { theme, setTheme } = useTheme();

  return (
    <select
      value={theme}
      onChange={(e) => setTheme(e.target.value as Theme)}
      className={`px-2 py-1 rounded border border-gray-300 bg-white text-sm text-slate-900 outline-none transition hover:border-gray-400 focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:border-gray-500 dark:focus-visible:ring-offset-slate-900 ${className}`}
    >
      <option value="light">亮色模式</option>
      <option value="dark">暗黑模式</option>
      <option value="system">跟随系统</option>
    </select>
  );
}
