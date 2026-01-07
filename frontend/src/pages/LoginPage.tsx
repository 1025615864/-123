import { useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Lock, ShieldCheck, User } from 'lucide-react'
import { useToast } from '../hooks'
import { useAuth } from '../contexts/AuthContext'
import { Button, Input } from '../components/ui'
import { getApiErrorMessage } from '../utils'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState<{ username?: string; password?: string; form?: string }>({})
  const usernameRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const toast = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const nextErrors: { username?: string; password?: string; form?: string } = {}
    if (!String(username || '').trim()) {
      nextErrors.username = '请输入用户名'
    }
    if (!String(password || '').trim()) {
      nextErrors.password = '请输入密码'
    }
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      if (nextErrors.username) {
        usernameRef.current?.focus()
      } else if (nextErrors.password) {
        passwordRef.current?.focus()
      }
      return
    }

    setErrors({})
    setLoading(true)

    try {
      await login(username, password)
      toast.success('登录成功！')

      const rawRedirect = searchParams.get('redirect')
      let redirectTo = '/'
      if (rawRedirect) {
        try {
          const decoded = decodeURIComponent(rawRedirect)
          if (decoded.startsWith('/')) redirectTo = decoded
        } catch {
          // ignore invalid redirect
        }
      }

      navigate(redirectTo, { replace: true })
    } catch (err: any) {
      const message = getApiErrorMessage(err, '登录失败，请稍后重试')
      setErrors({ form: message })
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-16">
      <div className="relative w-full max-w-4xl">
        <div className="absolute inset-0 -z-10 blur-3xl opacity-70">
          <div className="absolute -top-24 -left-20 h-72 w-72 rounded-full bg-gradient-to-br from-amber-500/25 via-orange-500/10 to-transparent" />
          <div className="absolute -bottom-24 -right-16 h-80 w-80 rounded-full bg-gradient-to-br from-purple-500/20 via-blue-500/10 to-transparent" />
        </div>

        <div className="grid md:grid-cols-2 gap-16 items-center">
          <div className="hidden md:block">
            <div className="space-y-6">
              <p className="text-amber-700 dark:text-amber-400 text-sm font-medium tracking-wider uppercase">
                欢迎回来
              </p>
              <h1 className="text-4xl font-bold text-slate-900 dark:text-white leading-tight">
                继续你的
                <span className="block mt-2 bg-gradient-to-r from-amber-400 via-orange-400 to-amber-500 bg-clip-text text-transparent">
                  法律咨询之旅
                </span>
              </h1>
              <p className="text-slate-600 dark:text-white/60 leading-relaxed">
                登录后可使用 AI 咨询、收藏记录与个性化服务。
              </p>

              <div className="flex items-center gap-3 text-slate-600 dark:text-white/70">
                <div className="h-10 w-10 rounded-2xl bg-slate-900/5 border border-slate-200/70 flex items-center justify-center dark:bg-white/[0.03] dark:border-white/[0.08]">
                  <ShieldCheck className="h-5 w-5 text-amber-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-white/80">安全与隐私</p>
                  <p className="text-sm text-slate-600 dark:text-white/50">你的会话与数据将被安全保护</p>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-3xl bg-white border border-slate-200/70 backdrop-blur-xl shadow-2xl shadow-black/10 p-8 md:p-10 dark:bg-white/[0.03] dark:border-white/[0.08] dark:shadow-black/30">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-slate-900 dark:text-white">欢迎回来</h2>
              <p className="text-slate-600 dark:text-white/50 mt-2">登录您的账户继续使用</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <Input
                label="用户名"
                icon={User}
                type="text"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value)
                  setErrors((prev) => ({ ...prev, username: undefined, form: undefined }))
                }}
                placeholder="请输入用户名"
                autoComplete="username"
                disabled={loading}
                required
                className="py-3.5"
                error={errors.username}
                ref={usernameRef}
              />

              <Input
                label="密码"
                icon={Lock}
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  setErrors((prev) => ({ ...prev, password: undefined, form: undefined }))
                }}
                placeholder="请输入密码"
                autoComplete="current-password"
                disabled={loading}
                required
                className="py-3.5"
                error={errors.password}
                ref={passwordRef}
                right={
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="p-2 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-900/5 transition disabled:opacity-60 disabled:cursor-not-allowed dark:text-white/40 dark:hover:text-white/70 dark:hover:bg-white/5"
                    aria-label={showPassword ? '隐藏密码' : '显示密码'}
                    disabled={loading}
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                }
              />

              {errors.form ? (
                <p className="text-sm text-red-400">{errors.form}</p>
              ) : null}

              <Button
                type="submit"
                fullWidth
                isLoading={loading}
                loadingText="登录中..."
                className="py-3.5"
              >
                登录
              </Button>
            </form>

            <div className="mt-5 text-center">
              <Link
                to="/forgot-password"
                className="text-sm text-slate-600 hover:text-slate-800 dark:text-white/50 dark:hover:text-white/70"
              >
                忘记密码？
              </Link>
            </div>

            <p className="text-center text-slate-600 dark:text-white/50 mt-8">
              还没有账户？{' '}
              <Link to="/register" className="text-amber-700 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-300">
                立即注册
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
