import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import { Card, Button } from '../components/ui'
import { useTheme } from '../contexts/ThemeContext'

export default function PrivacyPolicyPage() {
  const { actualTheme } = useTheme()

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="合规与服务"
        title="隐私政策"
        description="我们会以最小必要原则处理你的个人信息。"
        tone={actualTheme}
        right={
          <Link to="/register">
            <Button variant="outline">返回注册</Button>
          </Link>
        }
      />

      <Card variant="surface" padding="lg">
        <div className="space-y-4 text-sm text-slate-700 leading-relaxed dark:text-white/70">
          <div className="text-slate-900 font-semibold dark:text-white">1. 我们收集的信息</div>
          <div>
            账号信息（用户名、邮箱）、你主动提交的资料、以及为提供服务所需的日志信息（如 IP、设备信息、访问时间）。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">2. 我们如何使用信息</div>
          <div>
            用于账号注册与登录、服务提供与改进、风险控制与安全审计、以及必要的客服支持。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">3. 信息共享与披露</div>
          <div>
            除法律法规要求或经你明确授权外，我们不会向第三方共享你的个人信息。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">4. 你的权利</div>
          <div>
            你可在合理范围内查询、更正或删除你的个人资料；也可通过平台反馈渠道提出隐私相关诉求。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">5. 安全措施</div>
          <div>
            我们采用访问控制、加密与审计等措施保护你的数据安全，但也请你妥善保管账号密码。
          </div>

          <div className="pt-4 text-xs text-slate-500 dark:text-white/40">最后更新：v1</div>
        </div>
      </Card>
    </div>
  )
}
