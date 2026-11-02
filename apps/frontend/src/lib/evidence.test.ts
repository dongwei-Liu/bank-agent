import { describe, expect, it } from 'vitest'
import { anomalyEvidenceText, anomalyStatusLabel, anomalyTitle, subscriptionEvidenceLines } from './evidence'

describe('friendly evidence formatting', () => {
  it('translates anomaly rule and status codes into user-facing text', () => {
    const row = { rule: 'LARGE_V1', evidence: { amount: '1200.00', samples: 10, median: '200.00' } }
    expect(anomalyTitle(row)).toBe('大额消费候选')
    expect(anomalyStatusLabel('unreviewed')).toBe('待核实')
    expect(anomalyEvidenceText(row)).toContain('过去 10 笔同类交易中位数')
    expect(anomalyEvidenceText(row)).not.toContain('LARGE_V1')
  })

  it('summarizes subscription evidence without exposing JSON keys', () => {
    const lines = subscriptionEvidenceLines({
      cadence: 'MONTHLY',
      occurrences: [{}, {}, {}],
      observed_gaps_days: [30, 31],
      gap_range_days: [25, 35],
      amount_tolerance: '0.10',
    })
    expect(lines).toContain('系统依据 3 笔历史扣款识别为月度订阅。')
    expect(lines).toContain('历史扣款金额允许上下浮动 10%。')
    expect(lines.join('')).not.toContain('observed_gaps_days')
  })

  it('shows merged model evidence while retaining the existing rule explanation', () => {
    const text = anomalyEvidenceText({ rule: 'LARGE_V1', evidence: { amount: '1200.00', samples: 10, median: '200.00' }, ml_evidence: { score: 0.73, severity: 'high', reason_codes: ['AMOUNT_DEVIATION'] } })
    expect(text).toContain('过去 10 笔同类交易中位数')
    expect(text).toContain('金额偏离历史')
    expect(text).not.toContain('0.7300')
    expect(text).not.toMatch(/模型|评分|规则来源/)
  })
})

it('renders all six findings, provisional sources and missing-payment observations', () => {
  const kinds = ['SPENDING_SURGE_V1', 'DAILY_CONCENTRATION_V1', 'MERCHANT_DEVIATION_V1', 'CATEGORY_MIX_SHIFT_V1', 'SUBSCRIPTION_DEVIATION_V1', 'ACCOUNT_HABIT_SHIFT_V1']
  const titles = ['累计消费突增', '日级集中消费', '商户维度异常', '消费类别结构突变', '订阅涨价或周期异常', '账户使用习惯异常']
  kinds.forEach((kind, i) => {
    const row = { rule: kind, findings: [{ type: kind, sources: ['rule'], provisional: true, window: { from_date: '2026-09-01', to_date: '2026-09-07' }, evidence: { amount: '123.45', count: 6 } }] }
    expect(anomalyTitle(row)).toContain(titles[i])
    expect(anomalyEvidenceText(row)).toContain('123.45')
    expect(anomalyEvidenceText(row)).toContain('当日临时提示')
  })
  const text = anomalyEvidenceText({ rule: 'SUBSCRIPTION_DEVIATION_V1', observation_kind: 'expected_charge_not_observed', transactions: [], findings: [{ type: 'SUBSCRIPTION_DEVIATION_V1', sources: ['rule'], window: { from_date: '2026-09-01', to_date: '2026-09-07' }, evidence: { expected_date: '2026-09-01', cutoff_date: '2026-09-07', reason_codes: ['EXPECTED_CHARGE_NOT_OBSERVED'] } }] })
  expect(text).toContain('截至查询截止未匹配到预期扣费')
  expect(text).not.toContain('0笔')
  expect(text).not.toContain('扣款失败')
})

it('presents pure model candidates without algorithm, score or threshold', () => {
  const text = anomalyEvidenceText({ rule: 'IFOREST_V1', evidence: { amount: '321.12', score: 0.9876, threshold: 0.7654 } })
  expect(text).toContain('消费模式偏离个人历史')
  expect(text).toContain('321.12')
  expect(text).not.toMatch(/IFOREST|模型|评分|阈值|0.9876|0.7654/)
})
