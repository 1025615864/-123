import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, AlertTriangle, CheckCircle, Info, ArrowRight } from 'lucide-react'
import { Card, Button, Input } from '../components/ui'
import PageHeader from '../components/PageHeader'
import { useTheme } from '../contexts/ThemeContext'

type Period = { years?: number; months?: number }

interface LimitationRule {
  id: string
  name: string
  category: string
  period: Period
  description: string
  legalBasis: string
  notes?: string
}

const LIMITATION_RULES: LimitationRule[] = [
  {
    id: 'general',
    name: '一般诉讼时效',
    category: '民事',
    period: { years: 3 },
    description: '向人民法院请求保护民事权利的诉讼时效期间',
    legalBasis: '《民法典》第一百八十八条',
  },
  {
    id: 'labor_dispute',
    name: '劳动争议仲裁',
    category: '劳动',
    period: { years: 1 },
    description: '劳动争议申请仲裁的时效期间',
    legalBasis: '《劳动争议调解仲裁法》第二十七条',
    notes: '特殊情况：拖欠劳动报酬争议，劳动关系存续期间不受限制',
  },
  {
    id: 'contract_quality',
    name: '产品质量瑕疵',
    category: '合同',
    period: { years: 2 },
    description: '出卖人交付标的物不符合质量要求的',
    legalBasis: '《民法典》第六百二十一条',
  },
  {
    id: 'inheritance',
    name: '继承权纠纷',
    category: '继承',
    period: { years: 3 },
    description: '继承权纠纷提起诉讼的期限',
    legalBasis: '《民法典》第一百八十八条',
    notes: '自继承开始之日起超过二十年的，不得再提起诉讼',
  },
]

function parseLocalDate(input: string): Date | null {
  const s = String(input || '').trim()
  if (!s) return null
  const parts = s.split('-').map((v) => Number(v))
  if (parts.length !== 3) return null
  const [y, m, d] = parts
  if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) return null
  if (y <= 0 || m <= 0 || d <= 0) return null
  return new Date(y, m - 1, d)
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function addPeriod(date: Date, period: Period): Date {
  const years = Number(period.years || 0)
  const months = Number(period.months || 0)
  return new Date(date.getFullYear() + years, date.getMonth() + months, date.getDate())
}

function formatPeriod(period: Period): string {
  const years = period.years ? `${period.years}年` : ''
  const months = period.months ? `${period.months}个月` : ''
  return `${years}${months}` || '—'
}

export default function LimitationsCalculatorPage() {
  const { actualTheme } = useTheme()
  const [selectedRuleId, setSelectedRuleId] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [result, setResult] = useState<{
    deadline: Date
    daysRemaining: number
    isExpired: boolean
  } | null>(null)

  const selectedRule = useMemo(() => {
    return LIMITATION_RULES.find((r) => r.id === selectedRuleId) || null
  }, [selectedRuleId])

  const rulesByCategory = useMemo(() => {
    const map = new Map<string, LimitationRule[]>()
    for (const rule of LIMITATION_RULES) {
      const arr = map.get(rule.category) || []
      arr.push(rule)
      map.set(rule.category, arr)
    }
    return Array.from(map.entries())
  }, [])

  const handleCalculate = () => {
    const start = parseLocalDate(startDate)
    if (!selectedRule || !start) return

    const deadline = startOfDay(addPeriod(start, selectedRule.period))
    const today = startOfDay(new Date())
    const msPerDay = 24 * 60 * 60 * 1000
    const daysRemaining = Math.round((deadline.getTime() - today.getTime()) / msPerDay)
    const isExpired = deadline.getTime() < today.getTime()

    setResult({ deadline, daysRemaining, isExpired })
  }

  const chatDraft = useMemo(() => {
    if (!selectedRule || !result) return ''
    const deadlineText = result.deadline.toLocaleDateString('zh-CN')
    const startText = parseLocalDate(startDate)?.toLocaleDateString('zh-CN') || startDate
    const periodText = formatPeriod(selectedRule.period)
    return `我想咨询诉讼时效问题：类型为「${selectedRule.name}」（${periodText}），起算日为 ${startText}。按 ${selectedRule.legalBasis} 粗略计算，截止日约为 ${deadlineText}。请问该时效是否可能因中止/中断而变化？我现在应该如何处理更稳妥？`
  }, [result, selectedRule, startDate])

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="实用工具"
        title="诉讼时效计算器"
        description="快速估算诉讼/仲裁时效截止日期与剩余天数（仅供参考）"
        tone={actualTheme}
      />

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card variant="surface" padding="lg">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center">
                <Calendar className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">时效计算</h2>
                <p className="text-slate-600 text-sm dark:text-white/50">选择类型并填写起算日期</p>
              </div>
            </div>

            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-3 dark:text-white/70">时效类型</label>
                <select
                  value={selectedRuleId}
                  onChange={(e) => {
                    setSelectedRuleId(e.target.value)
                    setResult(null)
                  }}
                  className="w-full px-4 py-3 rounded-lg border bg-white text-slate-900 outline-none transition hover:border-slate-300 focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white border-slate-200 dark:bg-slate-800 dark:text-white dark:border-slate-700 dark:hover:border-slate-600 dark:focus-visible:ring-offset-slate-900"
                >
                  <option value="">请选择...</option>
                  {rulesByCategory.map(([category, rules]) => (
                    <optgroup key={category} label={category}>
                      {rules.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name}（{formatPeriod(r.period)}）
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>

              {selectedRule && (
                <div className="p-4 rounded-xl bg-blue-50 border border-blue-200/60 text-sm dark:bg-blue-500/10 dark:border-blue-500/20">
                  <p className="text-slate-700 dark:text-white/70">{selectedRule.description}</p>
                  <p className="text-slate-500 mt-2 dark:text-white/45">法律依据：{selectedRule.legalBasis}</p>
                  {selectedRule.notes && (
                    <p className="text-amber-700 mt-2 flex items-start gap-2 dark:text-amber-300">
                      <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
                      {selectedRule.notes}
                    </p>
                  )}
                </div>
              )}

              <Input
                label="起算日期（知道或应当知道权利被侵害之日）"
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value)
                  setResult(null)
                }}
              />

              <Button
                onClick={handleCalculate}
                icon={Calendar}
                disabled={!selectedRuleId || !String(startDate).trim()}
                className="w-full py-3"
              >
                计算时效
              </Button>
            </div>
          </Card>

          {result && selectedRule && (
            <Card
              variant="surface"
              padding="lg"
              className={
                result.isExpired
                  ? 'border-red-500/30'
                  : result.daysRemaining <= 30
                    ? 'border-amber-500/30'
                    : 'border-emerald-500/25'
              }
            >
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
                {result.isExpired ? (
                  <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
                ) : (
                  <CheckCircle
                    className={
                      result.daysRemaining <= 30
                        ? 'h-5 w-5 text-amber-600 dark:text-amber-400'
                        : 'h-5 w-5 text-emerald-600 dark:text-emerald-400'
                    }
                  />
                )}
                计算结果
              </h3>

              <div className="space-y-3">
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 dark:bg-white/5 dark:border-white/10">
                  <p className="text-sm text-slate-600 dark:text-white/60">截止日期</p>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white">
                    {result.deadline.toLocaleDateString('zh-CN')}
                  </p>
                  {result.isExpired ? (
                    <p className="text-sm text-red-600 mt-2 dark:text-red-300">
                      已过期 {Math.abs(result.daysRemaining)} 天
                    </p>
                  ) : (
                    <p
                      className={
                        result.daysRemaining <= 30
                          ? 'text-sm text-amber-700 mt-2 dark:text-amber-300'
                          : 'text-sm text-emerald-700 mt-2 dark:text-emerald-300'
                      }
                    >
                      距离届满还有 <span className="font-semibold">{result.daysRemaining}</span> 天
                      {result.daysRemaining <= 30 ? '，建议尽快处理' : ''}
                    </p>
                  )}
                </div>

                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-600 dark:bg-white/5 dark:border-white/10 dark:text-white/55">
                  <p className="flex items-start gap-2">
                    <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
                    以上结果仅供参考。实际时效可能受中止、中断、特别法规定等影响，建议结合案情向律师确认。
                  </p>
                </div>

                <Link to={`/chat?draft=${encodeURIComponent(chatDraft)}`} className="inline-block">
                  <Button icon={ArrowRight} className="bg-emerald-600 hover:bg-emerald-700 text-white focus-visible:ring-emerald-500/25">
                    用这个结果去咨询 AI
                  </Button>
                </Link>
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card variant="surface" padding="lg">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">使用建议</h3>
            <div className="space-y-3 text-sm text-slate-600 dark:text-white/60">
              <p>1. 起算日通常是“知道或应当知道权利被侵害之日”。</p>
              <p>2. 部分争议存在特别规则（如劳动报酬、产品质量等）。</p>
              <p>3. 若接近届满，建议尽快保存证据并咨询专业律师。</p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
