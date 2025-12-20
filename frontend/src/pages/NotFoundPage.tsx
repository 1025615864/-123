import { Link } from 'react-router-dom'
import { Home, ArrowLeft } from 'lucide-react'
import { Button } from '../components/ui'

export default function NotFoundPage() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-8xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-orange-500 mb-4">
          404
        </h1>
        <h2 className="text-2xl font-semibold text-slate-900 dark:text-white mb-4">
          页面未找到
        </h2>
        <p className="text-slate-600 dark:text-white/50 mb-8 max-w-md mx-auto">
          您访问的页面不存在或已被移除，请检查链接是否正确
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link to="/">
            <Button icon={Home}>返回首页</Button>
          </Link>
          <Button variant="outline" icon={ArrowLeft} onClick={() => window.history.back()}>
            返回上页
          </Button>
        </div>
      </div>
    </div>
  )
}
