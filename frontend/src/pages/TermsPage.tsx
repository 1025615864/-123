import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import { Card, Button } from '../components/ui'
import { useTheme } from '../contexts/ThemeContext'

export default function TermsPage() {
  const { actualTheme } = useTheme()

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="合规与服务"
        title="用户协议"
        description="请在使用本产品前仔细阅读。"
        tone={actualTheme}
        right={
          <Link to="/register">
            <Button variant="outline">返回注册</Button>
          </Link>
        }
      />

      <Card variant="surface" padding="lg">
        <div className="space-y-4 text-sm text-slate-700 leading-relaxed dark:text-white/70">
          <div className="text-slate-900 font-semibold dark:text-white">1. 协议范围</div>
          <div>
            本协议适用于你使用“百姓法律助手”提供的各项产品与服务。你在注册、登录或使用任一功能时，即视为已阅读并同意本协议。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">2. 账号与安全</div>
          <div>
            你应妥善保管账号与密码信息。因你自身原因导致的账号泄露、损失或纠纷，由你自行承担相应责任。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">3. 服务内容与变更</div>
          <div>
            我们可能根据产品运营需要对服务内容进行调整或升级。我们将尽力通过站内提示或更新说明告知重要变更。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">4. 免责声明</div>
          <div>
            本产品提供的内容仅供参考，不构成正式法律意见或承诺。你应结合自身情况审慎判断，并在需要时咨询具备执业资质的律师。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">5. 联系我们</div>
          <div>
            如有疑问，请通过平台内反馈渠道联系我们。
          </div>

          <div className="pt-4 text-xs text-slate-500 dark:text-white/40">最后更新：v1</div>
        </div>
      </Card>
    </div>
  )
}
