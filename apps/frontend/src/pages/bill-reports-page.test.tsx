import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { server } from '@/test/server'
import { BillReportsPage } from './bill-reports-page'

const account = { id: 1, account_no: '000000001', client_id: 1, client_name: 'Alice', product_id: 2, product_name: '储蓄账户', deposit_type: 'savings', currency: 'CNY', status: 'ACTIVE', available_balance: '100.00' }
const report = {
  id: 'report-1', schema_version: 1, status: 'partial', period: '2026-09', from_date: '2026-09-01', to_date: '2026-09-30',
  cutoff_date: '2026-09-30', partial_period: false, account_ids: [1], snapshot_atomic: false,
  historical_coverage: { status: 'observed', observed_days: 800, read_complete: true }, recurring_coverage_days: 800,
  sections: { summary: 'complete', trends: 'complete', transactions: 'complete', comparison: 'complete', anomalies: 'complete', recurring: 'complete', narrative: 'complete' },
  summary: { transaction_count: 1, expense_count: 1, average_expense: '12.50', totals: { income: '0.00', expense: '12.50', fees: '0.00', external_transfer: '0.00', principal_flow: '0.00', net_cash_flow: '-12.50' }, categories: [{ name: '餐饮', amount: '12.50', share: '1.00' }], daily: { '2026-09-03': { expense: '12.50' } }, monthly: {}, habits: { top_category: '餐饮', top_three_category_share: '1.00', weekday_weekend_expense_count: { weekday: 1, weekend: 0 } } },
  comparison: { previous_period: { from_date: '2026-08-01', to_date: '2026-08-31', metrics: { expense: { delta: '12.50', change_ratio: null, unavailable_reason: 'baseline_zero' } } } },
  anomalies: [{ anomaly_key: 'a1', rule: 'IFOREST_V1', status: 'unreviewed', evidence: { amount: '12.50', merchant: 'Cafe' }, score: 0.99, sources: ['ml'] }],
  recurring: [{ merchant: 'Video', cadence: 'MONTHLY', status: 'VERIFIED', verified_at: '2026-09-20T00:00:00+08:00', average_amount: '12.50', occurrences: [{ date: '2026-09-20', amount: '12.50' }] }],
  narrative: { items: [{ code: 'SPENDING_UP', text: '本期消费高于可比期间。' }], source: 'complete' },
}

function renderPage(initialEntry: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[initialEntry]}><Routes>
    <Route path="/insights/reports" element={<BillReportsPage />} />
    <Route path="/insights/reports/:reportId" element={<BillReportsPage />} />
  </Routes></MemoryRouter></QueryClientProvider>)
}

describe('BillReportsPage', () => {
  it('creates a saved report and renders facts, evidence, and paged snapshot rows without model metadata', async () => {
    server.use(
      http.get('/api/accounts', () => HttpResponse.json([account])),
      http.get('/api/bill-report-summaries', () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 })),
      http.post('/api/bill-report-generations', () => HttpResponse.json({ report_id: 'report-1', status: 'queued', period: '2026-09' }, { status: 202 })),
      http.get('/api/bill-report-generations/report-1/status', () => HttpResponse.json({ report_id: 'report-1', status: 'complete', progress: 100, period: '2026-09' })),
      http.get('/api/bill-reports/report-1', () => HttpResponse.json(report)),
      http.get('/api/bill-reports/report-1/transactions', () => HttpResponse.json({ items: [{ account_id: 1, transaction_id: 18, date: '2026-09-03', direction: 'debit', kind: 'expense', amount: '12.50', category: '餐饮', merchant: 'Cafe', reversed: false }], total: 1, page: 1, page_size: 50 })),
    )
    renderPage('/insights/reports')
    fireEvent.click(await screen.findByRole('button', { name: '生成并保存' }))
    expect(await screen.findByText('2026 年 09 月度报告')).toBeInTheDocument()
    expect(await screen.findByText(/本期消费高于可比期间/)).toBeInTheDocument()
    expect(screen.getByText(/Video · 月度 · 已核实/)).toBeInTheDocument()
    expect(screen.getByText(/当前核实时间/)).toBeInTheDocument()
    expect(await screen.findByText(/Cafe · 餐饮/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看 #18' })).toHaveAttribute('href', '/accounts/1?transaction=18')
    expect(document.body.textContent).not.toMatch(/0\.99|IFOREST_V1|\bml\b/)
  })

  it('states that an empty period does not prove zero income or spending', async () => {
    const empty = { ...report, summary: { ...report.summary, transaction_count: 0, expense_count: 0, average_expense: null, totals: { income: null, expense: null, fees: null, external_transfer: null, principal_flow: null, net_cash_flow: null }, categories: [], daily: {}, habits: {} }, recurring: [], recurring_coverage_days: 0, historical_coverage: { status: 'no_transactions', observed_days: 0, read_complete: true }, sections: { ...report.sections, recurring: 'insufficient_history' } }
    server.use(
      http.get('/api/accounts', () => HttpResponse.json([account])),
      http.get('/api/bill-report-summaries', () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 })),
      http.get('/api/bill-report-generations/report-1/status', () => HttpResponse.json({ report_id: 'report-1', status: 'partial', progress: 100, period: '2026-09' })),
      http.get('/api/bill-reports/report-1', () => HttpResponse.json(empty)),
      http.get('/api/bill-reports/report-1/transactions', () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50 })),
    )
    renderPage('/insights/reports/report-1')
    expect(await screen.findByText(/无法据此确认收入、消费或净收支金额为零/)).toBeInTheDocument()
    expect(screen.getAllByText('无法确认').length).toBeGreaterThan(0)
    expect(screen.getByText(/历史不足以判断年度周期支出/)).toBeInTheDocument()
  })
})
