import { useState } from 'react'
import { Calculator, Scale, Banknote, HelpCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { Card, Button, Input } from '../components/ui'
import PageHeader from '../components/PageHeader'
import { useTheme } from '../contexts/ThemeContext'

// 诉讼费计算规则（根据《诉讼费用交纳办法》）
const calculateLitigationFee = (amount: number, caseType: string): number => {
  if (caseType === 'property') {
    // 财产案件
    if (amount <= 10000) return 50
    if (amount <= 100000) return 50 + (amount - 10000) * 0.025
    if (amount <= 200000) return 2300 + (amount - 100000) * 0.02
    if (amount <= 500000) return 4300 + (amount - 200000) * 0.015
    if (amount <= 1000000) return 8800 + (amount - 500000) * 0.01
    if (amount <= 2000000) return 13800 + (amount - 1000000) * 0.009
    if (amount <= 5000000) return 22800 + (amount - 2000000) * 0.008
    if (amount <= 10000000) return 46800 + (amount - 5000000) * 0.007
    if (amount <= 20000000) return 81800 + (amount - 10000000) * 0.006
    return 141800 + (amount - 20000000) * 0.005
  } else if (caseType === 'divorce') {
    // 离婚案件：每件交纳50-300元
    return 200
  } else if (caseType === 'labor') {
    // 劳动争议：每件10元
    return 10
  } else if (caseType === 'admin') {
    // 行政案件：每件100元
    return 100
  } else if (caseType === 'intellectual') {
    // 知识产权案件
    if (amount <= 0) return 500
    if (amount <= 10000) return 500
    if (amount <= 100000) return 500 + (amount - 10000) * 0.04
    return 4100 + (amount - 100000) * 0.02
  }
  return 0
}

// 律师费参考标准（根据各地指导价）
const calculateLawyerFee = (amount: number, caseType: string, stage: string): { min: number; max: number } => {
  let baseMin = 3000
  let baseMax = 10000
  let percentMin = 0.03
  let percentMax = 0.08

  if (caseType === 'criminal') {
    // 刑事案件
    if (stage === 'investigation') return { min: 5000, max: 30000 }
    if (stage === 'prosecution') return { min: 5000, max: 30000 }
    if (stage === 'trial') return { min: 10000, max: 80000 }
    return { min: 10000, max: 50000 }
  }

  if (caseType === 'labor') {
    baseMin = 2000
    baseMax = 8000
    percentMin = 0.02
    percentMax = 0.05
  } else if (caseType === 'divorce') {
    baseMin = 3000
    baseMax = 15000
    percentMin = 0.02
    percentMax = 0.05
  }

  if (amount <= 0) {
    return { min: baseMin, max: baseMax }
  }

  const min = Math.max(baseMin, amount * percentMin)
  const max = Math.max(baseMax, amount * percentMax)
  return { min: Math.round(min), max: Math.round(max) }
}

interface FaqItem {
  question: string
  answer: string
}

const faqs: FaqItem[] = [
  {
    question: '诉讼费由谁承担？',
    answer: '诉讼费用一般由败诉方承担。如果双方都有责任，法院会根据责任比例分担。'
  },
  {
    question: '可以申请减免诉讼费吗？',
    answer: '符合条件的当事人可以申请缓交、减交或免交诉讼费用。如：享受最低生活保障的人、福利机构等。'
  },
  {
    question: '律师费可以要求对方赔偿吗？',
    answer: '一般情况下律师费由各方自行承担。但在知识产权侵权、不正当竞争等案件中，可以要求败诉方承担合理的律师费。'
  },
  {
    question: '风险代理是什么？',
    answer: '风险代理是指律师在接案时不收取或少收取前期费用，待案件胜诉后按约定比例收取律师费的收费方式。一般收取胜诉金额的10%-30%。'
  }
]

export default function FeeCalculatorPage() {
  const [caseType, setCaseType] = useState('property')
  const [amount, setAmount] = useState('')
  const [stage, setStage] = useState('trial')
  const [result, setResult] = useState<{
    litigationFee: number
    lawyerFeeMin: number
    lawyerFeeMax: number
  } | null>(null)
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null)
  const { actualTheme } = useTheme()

  const caseTypes = [
    { value: 'property', label: '财产纠纷', desc: '合同、债务、房产等' },
    { value: 'divorce', label: '离婚纠纷', desc: '离婚、财产分割、抚养权' },
    { value: 'labor', label: '劳动争议', desc: '工资、赔偿、工伤等' },
    { value: 'admin', label: '行政诉讼', desc: '行政处罚、行政强制等' },
    { value: 'intellectual', label: '知识产权', desc: '专利、商标、著作权' },
    { value: 'criminal', label: '刑事案件', desc: '刑事辩护、取保候审' },
  ]

  const stages = [
    { value: 'investigation', label: '侦查阶段' },
    { value: 'prosecution', label: '审查起诉' },
    { value: 'trial', label: '审判阶段' },
    { value: 'appeal', label: '二审/再审' },
  ]

  const handleCalculate = () => {
    const amountNum = parseFloat(amount) || 0
    const litigationFee = calculateLitigationFee(amountNum, caseType)
    const lawyerFee = calculateLawyerFee(amountNum, caseType, stage)
    
    setResult({
      litigationFee: Math.round(litigationFee),
      lawyerFeeMin: lawyerFee.min,
      lawyerFeeMax: lawyerFee.max,
    })
  }

  const formatMoney = (value: number) => {
    return value.toLocaleString('zh-CN', { style: 'currency', currency: 'CNY', minimumFractionDigits: 0 })
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="实用工具"
        title="诉讼费用计算器"
        description="快速估算诉讼费和律师费参考范围，帮您做好预算规划"
        tone={actualTheme}
      />

      <div className="grid lg:grid-cols-3 gap-6">
        {/* 左侧：计算器 */}
        <div className="lg:col-span-2 space-y-6">
          <Card variant="surface" padding="lg">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center">
                <Calculator className="h-6 w-6 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">费用计算</h2>
                <p className="text-slate-600 text-sm dark:text-white/50">选择案件类型，输入标的金额</p>
              </div>
            </div>

            <div className="space-y-6">
              {/* 案件类型选择 */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-3 dark:text-white/70">案件类型</label>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {caseTypes.map((type) => (
                    <button
                      key={type.value}
                      onClick={() => setCaseType(type.value)}
                      className={`p-4 rounded-xl border text-left transition-all ${
                        caseType === type.value
                          ? 'border-amber-300 bg-amber-50 dark:border-amber-500/50 dark:bg-amber-500/10'
                          : 'border-slate-200 bg-white hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10'
                      }`}
                    >
                      <p className={`font-medium ${caseType === type.value ? 'text-amber-700 dark:text-amber-400' : 'text-slate-900 dark:text-white'}`}>
                        {type.label}
                      </p>
                      <p className="text-xs text-slate-500 mt-1 dark:text-white/40">{type.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* 刑事案件阶段选择 */}
              {caseType === 'criminal' && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-3 dark:text-white/70">诉讼阶段</label>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {stages.map((s) => (
                      <button
                        key={s.value}
                        onClick={() => setStage(s.value)}
                        className={`p-3 rounded-xl border text-center transition-all ${
                          stage === s.value
                            ? 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/50 dark:bg-amber-500/10 dark:text-amber-400'
                            : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-700 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10 dark:text-white/70'
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* 标的金额 */}
              {caseType !== 'criminal' && (
                <div>
                  <Input
                    label="标的金额（元）"
                    icon={Banknote}
                    type="number"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="请输入诉讼标的金额"
                  />
                  <p className="text-xs text-slate-500 mt-2 dark:text-white/40">
                    如：合同金额、索赔金额、财产分割金额等
                  </p>
                </div>
              )}

              <Button onClick={handleCalculate} icon={Calculator} className="w-full py-3">
                计算费用
              </Button>
            </div>
          </Card>

          {/* 计算结果 */}
          {result && (
            <Card variant="surface" padding="lg" className="border-amber-500/20">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
                <Scale className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                费用估算结果
              </h3>

              <div className="grid md:grid-cols-2 gap-6">
                <div className="p-5 rounded-xl bg-gradient-to-br from-blue-500/10 to-blue-600/5 border border-blue-500/20">
                  <p className="text-blue-700 text-sm mb-2 dark:text-blue-400">诉讼费（预交）</p>
                  <p className="text-3xl font-bold text-slate-900 dark:text-white">{formatMoney(result.litigationFee)}</p>
                  <p className="text-xs text-slate-500 mt-2 dark:text-white/40">由败诉方承担</p>
                </div>

                <div className="p-5 rounded-xl bg-gradient-to-br from-amber-500/10 to-orange-500/5 border border-amber-500/20">
                  <p className="text-amber-700 text-sm mb-2 dark:text-amber-400">律师费参考</p>
                  <p className="text-3xl font-bold text-slate-900 dark:text-white">
                    {formatMoney(result.lawyerFeeMin)} - {formatMoney(result.lawyerFeeMax)}
                  </p>
                  <p className="text-xs text-slate-500 mt-2 dark:text-white/40">具体以律师报价为准</p>
                </div>
              </div>

              <div className="mt-6 p-4 rounded-xl bg-slate-50 border border-slate-200 dark:bg-white/5 dark:border-white/10">
                <p className="text-sm text-slate-600 dark:text-white/60">
                  💡 <span className="text-slate-800 font-medium dark:text-white/80">温馨提示：</span>
                  以上费用仅供参考。实际诉讼费以法院收费为准，律师费可与律师协商确定。
                  复杂案件建议咨询专业律师获取准确报价。
                </p>
              </div>
            </Card>
          )}
        </div>

        {/* 右侧：常见问题 */}
        <div className="space-y-6">
          <Card variant="surface" padding="lg">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <HelpCircle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              常见问题
            </h3>

            <div className="space-y-3">
              {faqs.map((faq, index) => (
                <div
                  key={index}
                  className="rounded-xl border border-slate-200 overflow-hidden dark:border-white/10"
                >
                  <button
                    onClick={() => setExpandedFaq(expandedFaq === index ? null : index)}
                    className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50 transition-colors dark:hover:bg-white/5"
                  >
                    <span className="text-slate-900 dark:text-white text-sm font-medium pr-4">{faq.question}</span>
                    {expandedFaq === index ? (
                      <ChevronUp className="h-4 w-4 text-slate-400 dark:text-white/40 flex-shrink-0" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-slate-400 dark:text-white/40 flex-shrink-0" />
                    )}
                  </button>
                  {expandedFaq === index && (
                    <div className="px-4 pb-4">
                      <p className="text-sm text-slate-600 leading-relaxed dark:text-white/60">{faq.answer}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>

          <Card variant="surface" padding="md">
            <p className="text-sm text-slate-600 leading-relaxed dark:text-white/50">
              📋 <span className="text-slate-800 dark:text-white/70">法律依据：</span>
              本计算器依据《诉讼费用交纳办法》和各地律师收费指导标准制定，仅供参考。
            </p>
          </Card>
        </div>
      </div>
    </div>
  )
}
