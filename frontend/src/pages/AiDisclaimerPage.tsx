import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import { Card, Button } from '../components/ui'
import { useTheme } from '../contexts/ThemeContext'

export default function AiDisclaimerPage() {
  const { actualTheme } = useTheme()

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="合规与服务"
        title="AI 咨询免责声明"
        description="AI 输出仅供参考，不构成正式法律意见。"
        tone={actualTheme}
        right={
          <Link to="/register">
            <Button variant="outline">返回注册</Button>
          </Link>
        }
      />

      <Card variant="surface" padding="lg">
        <div className="space-y-4 text-sm text-slate-700 leading-relaxed dark:text-white/70">
          <div className="text-slate-900 font-semibold dark:text-white">1. 输出性质</div>
          <div>
            本平台的 AI 咨询功能基于模型与已有材料生成内容，可能存在遗漏、错误或不完整之处，仅供一般信息参考。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">2. 不构成法律意见</div>
          <div>
            AI 输出不构成律师的正式法律意见或承诺，不应作为你采取或不采取行动的唯一依据。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">3. 风险提示</div>
          <div>
            法律问题具有复杂性，且可能随法规、司法解释与个案事实变化。涉及重大权益事项，请咨询具备执业资格的律师。
          </div>

          <div className="text-slate-900 font-semibold dark:text-white">4. 你的责任</div>
          <div>
            你应对基于 AI 输出做出的决定与行为后果承担相应责任。
          </div>

          <div className="pt-4 text-xs text-slate-500 dark:text-white/40">最后更新：v1</div>
        </div>
      </Card>
    </div>
  )
}
