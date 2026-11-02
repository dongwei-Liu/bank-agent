import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http, delay } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { server } from '@/test/server'
import { resolveBillPeriod } from '@/lib/bill-period'
import { BillPage } from './bill-page'
import { InsightsPage } from './insights-page'

describe('BillPage', () => {
  it('uses the Shanghai date when validating month and year boundaries', () => {
    const afterShanghaiMidnight = new Date('2026-10-31T16:30:00.000Z')
    expect(resolveBillPeriod('2026-11', afterShanghaiMidnight)?.toDate).toBe('2026-11-01')
    expect(resolveBillPeriod('2026-10', afterShanghaiMidnight)?.toDate).toBe('2026-10-31')
    expect(resolveBillPeriod('2026', afterShanghaiMidnight)?.toDate).toBe('2026-11-01')
  })

  it('rejects future billing periods', () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/insights/bills/9999-01']}>
          <Routes><Route path="/insights/bills/:period" element={<BillPage />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(screen.getByText('账单期间无效')).toBeInTheDocument()
  })

  it('renders a realtime all-account bill with cutoff and rule version', async () => {
    server.use(
      http.get('/api/accounts', () => HttpResponse.json([{ id: 1, account_no: '000000001', client_id: 1, client_name: 'Alice', product_id: 2, product_name: '储蓄账户', deposit_type: 'savings', currency: 'CNY', status: 'ACTIVE', available_balance: '100.00' }])),
      http.get('/api/billing/statistics', () => HttpResponse.json({ account_id: null, account_ids: [1], complete: true, from_date: '2025-01-01', to_date: '2025-01-31', currency: 'CNY', totals: { income: '200.00', expense: '80.00' }, direction_totals: {}, categories: { 餐饮: '80.00' }, monthly: { '2025-01': { income: '200.00', expense: '80.00' } }, transaction_count: 3, data_cutoff: '2025-01-31T23:59:00+08:00', rule_version: 'billing-v1', configuration_hash: 'hash', snapshot_atomic: false })),
      http.get('/api/billing/anomalies', () => HttpResponse.json({ account_id: null, account_ids: [1], complete: true, from_date: '2025-01-01', to_date: '2025-01-31', data_cutoff: '2025-01-31T23:59:00+08:00', items: [] })),
    )
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={['/insights/bills/2025-01']}>
          <Routes><Route path="/insights/bills/:period" element={<BillPage />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('2025 年 1 月 · 月度账单')).toBeInTheDocument()
    expect(await screen.findByText(/分类规则：billing-v1/)).toBeInTheDocument()
    expect(screen.getByText(/全部 1 个账户/)).toBeInTheDocument()
    expect(screen.getByText('餐饮')).toBeInTheDocument()
    expect(screen.getByText('本次查询未返回异常候选。未返回候选不代表全部交易安全。')).toBeInTheDocument()
  })
})


it('does not present an anomaly request failure as no candidates in insights', async () => {
  server.use(
    http.get('/api/accounts', () => HttpResponse.json([{ id: 1, account_no: '000000001', currency: 'CNY', product_name: '储蓄' }])),
    http.get('/api/billing/statistics', () => HttpResponse.json({ account_ids: [1], categories: {}, totals: {} })),
    http.get('/api/billing/anomalies', async () => { await delay(150); return HttpResponse.json({ error: { code: 'FINERACT_UNAVAILABLE', message: '异常检测读取失败' } }, { status: 503 }) }),
    http.get('/api/subscriptions/renewals', () => HttpResponse.json({ as_of: '2026-10-26', timezone: 'Asia/Shanghai', days: 3, from_date: '2026-10-26', to_date: '2026-10-29', last_scan_at: null, upcoming: [], needs_review: [] })),
    ...['subscriptions', 'categories', 'classification-rules', 'bill-reports'].map(path => http.get('/api/' + path, () => HttpResponse.json([]))),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><InsightsPage /></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByText('正在检测异常消费…')).toBeInTheDocument()
  expect(screen.queryByText('本次查询未返回异常候选。未返回候选不代表全部交易安全。')).not.toBeInTheDocument()
  expect(await screen.findByText('异常检测读取失败')).toBeInTheDocument()
  expect(screen.queryByText('本次查询未返回异常候选。未返回候选不代表全部交易安全。')).not.toBeInTheDocument()
})

it('does not present a renewal request failure as no upcoming subscriptions in insights', async () => {
  server.use(
    http.get('/api/accounts', () => HttpResponse.json([{ id: 1, account_no: '000000001', currency: 'CNY', product_name: '储蓄' }])),
    http.get('/api/billing/statistics', () => HttpResponse.json({ account_ids: [1], categories: {}, totals: {} })),
    http.get('/api/billing/anomalies', () => HttpResponse.json({ items: [] })),
    http.get('/api/subscriptions/renewals', () => HttpResponse.json({ error: { code: 'UPSTREAM_UNAVAILABLE', message: '续费读取失败' } }, { status: 503 })),
    ...['subscriptions', 'categories', 'classification-rules', 'bill-reports'].map(path => http.get('/api/' + path, () => HttpResponse.json([]))),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><InsightsPage /></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByText('续费读取失败')).toBeInTheDocument()
  expect(screen.queryByText('未来三天没有已核实订阅预计续费。')).not.toBeInTheDocument()
})

it('surfaces an unknown report submission and provides a safe results lookup instead of retrying', async () => {
  let createCount = 0
  server.use(
    http.get('/api/accounts', () => HttpResponse.json([{ id: 1, account_no: '000000001', currency: 'CNY', product_name: '储蓄' }])),
    http.get('/api/billing/statistics', () => HttpResponse.json({ account_ids: [1], totals: {}, categories: {}, monthly: {}, transaction_count: 0, data_cutoff: '2025-01-31T00:00:00Z', snapshot_atomic: true })),
    http.get('/api/billing/anomalies', () => HttpResponse.json({ items: [] })),
    http.post('/api/bill-report-generations', () => {
      createCount += 1
      return HttpResponse.json({ error: { code: 'WRITE_RESULT_UNKNOWN', message: '请求超时，报告结果待核对' } }, { status: 503 })
    }),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter initialEntries={['/insights/bills/2025-01']}><Routes><Route path="/insights/bills/:period" element={<BillPage />} /></Routes></MemoryRouter></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: '生成完整报告' }))
  expect(await screen.findByText('请求超时，报告结果待核对')).toBeInTheDocument()
  expect(screen.getByText(/请先核对报告列表/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '查看报告列表核对处理结果 →' })).toHaveAttribute('href', '/insights/reports')
  expect(createCount).toBe(1)
})

it.each(['bill', 'insights'])('keeps business evidence but hides execution metadata in %s', async (surface) => {
  const reviewStatuses: Record<string, 'verified' | 'ignored'> = {
    model: 'verified', subscription: 'ignored',
  }
  server.use(
    http.get('/api/accounts', () => HttpResponse.json([{ id: 1, account_no: '000000001', currency: 'CNY', product_name: '储蓄' }])),
    http.get('/api/billing/statistics', () => HttpResponse.json({ account_ids: [1], categories: {}, totals: {}, monthly: {}, transaction_count: 0, data_cutoff: '2025-01-31T00:00:00Z', snapshot_atomic: true })),
    http.get('/api/billing/anomalies', () => HttpResponse.json({ items: [
      { anomaly_key: 'model', rule: 'IFOREST_V1', status: reviewStatuses.model, evidence: { amount: '321.12', score: 0.9876 } },
      { anomaly_key: 'subscription', rule: 'SUBSCRIPTION_DEVIATION_V1', status: reviewStatuses.subscription, observation_kind: 'expected_charge_not_observed', findings: [{ type: 'SUBSCRIPTION_DEVIATION_V1', sources: ['rule', 'ml'], provisional: true, window: { from_date: '2025-01-01', to_date: '2025-01-31' }, evidence: { reason_codes: ['EXPECTED_CHARGE_NOT_OBSERVED'], expected_date: '2025-01-25', cutoff_date: '2025-01-31' } }] },
    ], detection: { status: 'no_model', capabilities: { SPENDING_SURGE_V1: { status: 'skipped', skip_reasons: ['insufficient_history'] } } } })),
    http.post('/api/billing/anomaly-reviews', async ({ request }) => {
      const body = await request.json() as { anomaly_key: string; status: 'verified' | 'ignored' }
      reviewStatuses[body.anomaly_key] = body.status
      return HttpResponse.json({ id: body.anomaly_key, ...body })
    }),
    http.get('/api/subscriptions/renewals', () => HttpResponse.json({ as_of: '2026-10-26', timezone: 'Asia/Shanghai', days: 3, from_date: '2026-10-26', to_date: '2026-10-29', last_scan_at: null, upcoming: [], needs_review: [] })),
    ...['subscriptions', 'categories', 'classification-rules', 'bill-reports'].map(path => http.get('/api/' + path, () => HttpResponse.json([]))),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/insights/bills/2025-01']}><Routes><Route path="*" element={surface === 'bill' ? <BillPage /> : <InsightsPage />} /><Route path="/insights/bills/:period" element={surface === 'bill' ? <BillPage /> : <InsightsPage />} /></Routes></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByText(/消费模式偏离个人历史/)).toHaveTextContent('321.12')
  expect(screen.getByText(/个人消费行为偏离候选 · 已确认/)).toBeInTheDocument()
  expect(screen.getByText(/订阅涨价或周期异常 · 已忽略/)).toBeInTheDocument()
  expect(screen.getByText(/截至查询截止未匹配到预期扣费/)).toHaveTextContent('当日临时提示')
  const card = screen.getByText(/个人消费行为偏离候选 · 已确认/).closest('article')!
  expect(within(card).getByRole('button', { name: '已确认' })).toBeDisabled()
  expect(within(card).getByRole('button', { name: '忽略' })).toBeEnabled()
  await userEvent.click(within(card).getByRole('button', { name: '忽略' }))
  expect(await within(card).findByRole('button', { name: '已忽略' })).toBeDisabled()
  expect(within(card).getByRole('button', { name: '确认异常' })).toBeEnabled()
  expect(document.body.textContent).not.toMatch(/0.9876|本次仅规则检测|执行覆盖|模型评分|insufficient_history/)
})
