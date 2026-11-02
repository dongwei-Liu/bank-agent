import type { JsonObject } from './api'
import { formatMoney } from './format'

export const EMPTY_ANOMALIES_TEXT = '本次查询未返回异常候选。未返回候选不代表全部交易安全。'

export function anomalyTitle(row: JsonObject): string {
  if (row.rule === 'LARGE_V1') return '大额消费候选'
  if (row.rule === 'DUPLICATE_V1') return '重复扣款候选'
  if (row.rule === 'IFOREST_V1') return '个人消费行为偏离候选'
  const types = Array.isArray(row.anomaly_types) ? row.anomaly_types : [row.rule]
  return types.map((t) => anomalyNames[String(t)] ?? '异常交易候选').join('、')
}

export function anomalyStatusLabel(status: unknown): string {
  if (status === 'verified') return '已确认'
  if (status === 'ignored') return '已忽略'
  return '待核实'
}

export function anomalyEvidenceText(row: JsonObject): string {
  const base = ruleEvidenceText(row)
  const findings = Array.isArray(row.findings) ? row.findings as JsonObject[] : []
  const details = findings.filter((f) => f.type !== 'IFOREST_V1').map(findingText).join(' ' )
  const ml = (row.ml_evidence ?? (row.rule === 'IFOREST_V1' ? row.evidence : undefined)) as JsonObject | undefined
  if (!ml) return `${base} ${details}`.trim()
  const reasons: Record<string, string> = {
    PERSONAL_BEHAVIOR_DEVIATION: '个人消费模式偏离', AMOUNT_DEVIATION: '金额偏离历史', UNCOMMON_CATEGORY: '历史少见类别',
  }
  const codes = Array.isArray(ml.reason_codes) ? ml.reason_codes : []
  return `${base} ${details} ${codes.map((code) => reasons[String(code)] ?? '消费模式偏离个人历史').join('、')}`.trim()
}

function ruleEvidenceText(row: JsonObject): string {
  const evidence = (row.evidence ?? {}) as JsonObject
  if (row.rule === 'LARGE_V1') {
    return `本笔金额 ${formatMoney(String(evidence.amount ?? '0'), 'CNY')}，过去 ${String(evidence.samples ?? 0)} 笔同类交易中位数为 ${formatMoney(String(evidence.median ?? '0'), 'CNY')}`
  }
  if (row.rule === 'DUPLICATE_V1') {
    return `商户 ${String(evidence.merchant ?? '未知')} 在 ${String(evidence.date ?? '—')} 出现重复金额 ${formatMoney(String(evidence.amount ?? '0'), 'CNY')}`
  }
  if (row.rule === 'IFOREST_V1') {
    return `本笔金额 ${formatMoney(String(evidence.amount ?? '0'), 'CNY')}，消费模式偏离个人历史。`
  }
  return '系统发现需要人工核实的交易模式，请结合账户流水确认。'
}

export function subscriptionEvidenceLines(evidence: JsonObject): string[] {
  const lines: string[] = []
  const occurrences = Array.isArray(evidence.occurrences) ? evidence.occurrences : []
  const gaps = Array.isArray(evidence.observed_gaps_days) ? evidence.observed_gaps_days : []
  const range = Array.isArray(evidence.gap_range_days) ? evidence.gap_range_days : []
  const cadence = evidence.cadence === 'YEARLY' ? '年度' : evidence.cadence === 'MONTHLY' ? '月度' : '周期性'

  lines.push(`系统依据 ${occurrences.length} 笔历史扣款识别为${cadence}订阅。`)
  if (gaps.length) lines.push(`相邻扣款间隔为 ${gaps.map(String).join('、')} 天。`)
  if (range.length >= 2) lines.push(`当前规则接受 ${String(range[0])}～${String(range[1])} 天的周期范围。`)

  const tolerance = Number(evidence.amount_tolerance)
  if (Number.isFinite(tolerance)) lines.push(`历史扣款金额允许上下浮动 ${Math.round(tolerance * 100)}%。`)
  return lines
}


const anomalyNames: Record<string, string> = {
  SPENDING_SURGE_V1: '累计消费突增', DAILY_CONCENTRATION_V1: '日级集中消费',
  MERCHANT_DEVIATION_V1: '商户维度异常', CATEGORY_MIX_SHIFT_V1: '消费类别结构突变',
  SUBSCRIPTION_DEVIATION_V1: '订阅涨价或周期异常', ACCOUNT_HABIT_SHIFT_V1: '账户使用习惯异常',
}
const findingReasons: Record<string, string> = {
  PRICE_INCREASE: '订阅价格增加', EARLY_OR_DENSE_CHARGE: '提前或过密扣费', LATE_CHARGE: '延迟扣费',
  EXPECTED_CHARGE_NOT_OBSERVED: '截至查询截止未匹配到预期扣费',
  FAMILIAR_MERCHANT_AMOUNT: '熟悉商户金额偏离', RARE_MERCHANT_AMOUNT: '新或少见商户金额偏离',
  DORMANT_ACCOUNT_RESUMED: '休眠账户恢复消费', ACCOUNT_SHARE_SHIFT: '账户消费份额变化',
}
function findingText(f: JsonObject): string {
  const e = (f.evidence ?? {}) as JsonObject
  const w = (f.window ?? {}) as JsonObject
  const parts = [`${anomalyNames[String(f.type)] ?? '消费偏离'}${f.provisional ? '（当日临时提示）' : ''}`, `窗口 ${String(w.from_date)} 至 ${String(w.to_date)}`]
  if (Array.isArray(e.reason_codes)) parts.push(e.reason_codes.map((r) => findingReasons[String(r)] ?? '行为偏离').join('、'))
  if (e.merchant) parts.push(`商户 ${String(e.merchant)}`)
  if (e.amount !== undefined) parts.push(`金额 ${formatMoney(String(e.amount), 'CNY')}`)
  if (e.baseline_amount !== undefined || e.baseline_median !== undefined) parts.push(`历史中位数 ${f.type === 'DAILY_CONCENTRATION_V1' ? String(e.baseline_median) + ' 笔' : formatMoney(String(e.baseline_amount ?? e.baseline_median), 'CNY')}`)
  if (e.count !== undefined) parts.push(`消费 ${String(e.count)} 笔`)
  if (e.gap_days !== undefined) parts.push(`间隔 ${String(e.gap_days)} 天`)
  if (e.interval_days !== undefined) parts.push(`扣费间隔 ${String(e.interval_days)} 天`)
  if (e.js_divergence !== undefined) parts.push(`类别分布差异 ${Number(e.js_divergence).toFixed(3)}`)
  if (e.share !== undefined) parts.push(`账户消费份额 ${(Number(e.share) * 100).toFixed(1)}%，历史 ${(Number(e.baseline_share) * 100).toFixed(1)}%`)
  if (e.expected_date) parts.push(`预期日期 ${String(e.expected_date)}`)
  if (e.cutoff_date) parts.push(`查询截止 ${String(e.cutoff_date)}；仅为未见付款观测`)
  return parts.join('；') + '。'
}
