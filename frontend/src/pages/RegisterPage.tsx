import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Lock, Mail, ShieldCheck, User } from 'lucide-react'
import { useToast } from '../hooks'
import { useAuth } from '../contexts/AuthContext'
import { Button, Input } from '../components/ui'
import { getApiErrorMessage } from '../utils'

export default function RegisterPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [agreeTerms, setAgreeTerms] = useState(false)
  const [agreePrivacy, setAgreePrivacy] = useState(false)
  const [agreeAiDisclaimer, setAgreeAiDisclaimer] = useState(false)
  const [loading, setLoading] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (password !== confirmPassword) {
      toast.error('两次输入的密码不一致')
      return
    }

    if (password.length < 6) {
      toast.error('密码长度至少6位')
      return
    }

    if (!agreeTerms || !agreePrivacy || !agreeAiDisclaimer) {
      toast.error('请阅读并同意用户协议、隐私政策及AI咨询免责声明')
      return
    }

    setLoading(true)

    try {
      await register(username, email, password, agreeTerms, agreePrivacy, agreeAiDisclaimer)
      toast.success('注册成功！请登录')
      navigate('/login')
    } catch (err: any) {
      toast.error(getApiErrorMessage(err, '注册失败，请稍后重试'))
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
                创建账户
              </p>
              <h1 className="text-4xl font-bold text-slate-900 dark:text-white leading-tight">
                开始使用
                <span className="block mt-2 bg-gradient-to-r from-amber-400 via-orange-400 to-amber-500 bg-clip-text text-transparent">
                  百姓法律助手
                </span>
              </h1>
              <p className="text-slate-600 dark:text-white/60 leading-relaxed">
                注册后即可使用 AI 咨询、法律资讯、论坛交流与律所查询等功能。
              </p>

              <div className="space-y-4">
                <div className="flex items-center gap-3 text-slate-600 dark:text-white/70">
                  <div className="h-10 w-10 rounded-2xl bg-slate-900/5 border border-slate-200/70 flex items-center justify-center dark:bg-white/[0.03] dark:border-white/[0.08]">
                    <ShieldCheck className="h-5 w-5 text-amber-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-900 dark:text-white/80">安全登录</p>
                    <p className="text-sm text-slate-600 dark:text-white/50">Token 鉴权，自动保持登录状态</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 text-slate-600 dark:text-white/70">
                  <div className="h-10 w-10 rounded-2xl bg-slate-900/5 border border-slate-200/70 flex items-center justify-center dark:bg-white/[0.03] dark:border-white/[0.08]">
                    <Mail className="h-5 w-5 text-amber-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-900 dark:text-white/80">找回更方便</p>
                    <p className="text-sm text-slate-600 dark:text-white/50">绑定邮箱以便后续服务通知</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-3xl bg-white border border-slate-200/70 backdrop-blur-xl shadow-2xl shadow-black/10 p-8 md:p-10 dark:bg-white/[0.03] dark:border-white/[0.08] dark:shadow-black/30">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-slate-900 dark:text-white">创建账户</h2>
              <p className="text-slate-600 dark:text-white/50 mt-2">注册并开始使用法律助手</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <Input
                label="用户名"
                icon={User}
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="请输入用户名"
                autoComplete="username"
                disabled={loading}
                required
                className="py-3.5"
              />

              <Input
                label="邮箱"
                icon={Mail}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="请输入邮箱"
                autoComplete="email"
                disabled={loading}
                required
                className="py-3.5"
              />

              <div>
                <Input
                  label="密码"
                  icon={Lock}
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码（至少6位）"
                  autoComplete="new-password"
                  minLength={6}
                  disabled={loading}
                  required
                  className="py-3.5"
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
                <p className="mt-2 text-xs text-slate-500 dark:text-white/40">建议使用字母+数字组合提升安全性</p>
              </div>

              <Input
                label="确认密码"
                icon={Lock}
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="请再次输入密码"
                autoComplete="new-password"
                minLength={6}
                disabled={loading}
                required
                className="py-3.5"
              />

              <div className="space-y-3 rounded-2xl border border-slate-200/70 bg-slate-50 px-4 py-4 text-sm text-slate-700 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/70">
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4"
                    checked={agreeTerms}
                    onChange={(e) => setAgreeTerms(e.target.checked)}
                    disabled={loading}
                  />
                  <span>
                    我已阅读并同意
                    <Link to="/terms" className="mx-1 text-blue-600 hover:underline dark:text-blue-400">
                      《用户协议》
                    </Link>
                  </span>
                </label>
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4"
                    checked={agreePrivacy}
                    onChange={(e) => setAgreePrivacy(e.target.checked)}
                    disabled={loading}
                  />
                  <span>
                    我已阅读并同意
                    <Link to="/privacy" className="mx-1 text-blue-600 hover:underline dark:text-blue-400">
                      《隐私政策》
                    </Link>
                  </span>
                </label>
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4"
                    checked={agreeAiDisclaimer}
                    onChange={(e) => setAgreeAiDisclaimer(e.target.checked)}
                    disabled={loading}
                  />
                  <span>
                    我已阅读并同意
                    <Link to="/ai-disclaimer" className="mx-1 text-blue-600 hover:underline dark:text-blue-400">
                      《AI 咨询免责声明》
                    </Link>
                  </span>
                </label>
              </div>

              <Button
                type="submit"
                fullWidth
                isLoading={loading}
                loadingText="注册中..."
                disabled={!agreeTerms || !agreePrivacy || !agreeAiDisclaimer}
                className="py-3.5"
              >
                注册
              </Button>
            </form>

            <p className="text-center text-slate-600 dark:text-white/50 mt-8">
              已有账户？{' '}
              <Link to="/login" className="text-amber-700 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-300">
                立即登录
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
