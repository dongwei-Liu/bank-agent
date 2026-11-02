import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { expect, it } from 'vitest'
import type { ClassificationRule } from '@/lib/api'
import { server } from '@/test/server'
import { InsightsPage } from './insights-page'

const statistics = { account_ids: [1], complete: true, totals: { income: '0', expense: '0' }, categories: {}, monthly: {}, transaction_count: 0, data_cutoff: '2026-10-28T00:00:00+08:00', rule_version: 'billing-v1', snapshot_atomic: false }
const renewals = { as_of: '2026-10-28', timezone: 'Asia/Shanghai', days: 3, from_date: '2026-10-28', to_date: '2026-10-31', last_scan_at: null, upcoming: [], needs_review: [] }

function renderPage(client: QueryClient) {
  return render(<QueryClientProvider client={client}><MemoryRouter><InsightsPage /></MemoryRouter></QueryClientProvider>)
}

function setupCommon() {
  let accountReads = 0
  server.use(
    http.get('/api/accounts', () => { accountReads += 1; return HttpResponse.json([{ id: 1, account_no: '000000001', currency: 'CNY', product_name: '日常账户' }]) }),
    http.get('/api/billing/statistics', () => HttpResponse.json(statistics)),
    http.get('/api/billing/anomalies', () => HttpResponse.json({ items: [] })),
    http.get('/api/subscriptions/renewals', () => HttpResponse.json(renewals)),
  )
  return () => accountReads
}

it('edits category and rule definitions and reports referenced-category errors', async () => {
  const accountReads = setupCommon()
  let categories = [{ id: 'c1', name: '餐饮' }]
  let rules: ClassificationRule[] = [{ id: 'r1', category_id: 'c1', field: 'merchant', contains: 'Cafe', priority: 100 }]
  let updatePayload: Record<string, unknown> | undefined
  let rulePayload: Record<string, unknown> | undefined
  server.use(
    http.get('/api/categories', () => HttpResponse.json(categories)),
    http.put('/api/categories/c1', async ({ request }) => {
      updatePayload = await request.json() as Record<string, unknown>
      categories = [{ id: 'c1', name: String(updatePayload.name) }]
      return HttpResponse.json(categories[0])
    }),
    http.delete('/api/categories/c1', () => HttpResponse.json({ error: { code: 'CATEGORY_IN_USE', message: '类别仍被引用' } }, { status: 409 })),
    http.get('/api/classification-rules', () => HttpResponse.json(rules)),
    http.put('/api/classification-rules/r1', async ({ request }) => {
      rulePayload = await request.json() as Record<string, unknown>
      rules = [{ id: 'r1', category_id: String(rulePayload.category_id), field: rulePayload.field as 'merchant' | 'note' | 'type', contains: String(rulePayload.contains), priority: Number(rulePayload.priority) }]
      return HttpResponse.json(rules[0])
    }),
    http.delete('/api/classification-rules/r1', () => { rules = []; return HttpResponse.json({ deleted: true }) }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  client.setQueryData(['billing-statistics', 'invalidation-sentinel'], statistics)
  renderPage(client)
  expect(await screen.findByRole('heading', { name: '财务洞察' })).toBeInTheDocument()
  expect(accountReads()).toBeGreaterThan(0)

  const user = userEvent.setup()
  const categorySection = (await screen.findByRole('heading', { name: '个人分类' })).closest('section')!
  await user.click(within(categorySection).getByRole('button', { name: '编辑分类' }))
  await user.clear(screen.getByRole('textbox', { name: '编辑分类名称' }))
  await user.type(screen.getByRole('textbox', { name: '编辑分类名称' }), '餐饮新版')
  await user.click(within(categorySection).getByRole('button', { name: '保存' }))
  expect(await screen.findByRole('status')).toHaveTextContent('实时统计已刷新')
  expect(updatePayload).toEqual({ name: '餐饮新版' })
  await waitFor(() => expect(client.getQueryState(['billing-statistics', 'invalidation-sentinel'])?.isInvalidated).toBe(true))

  const rulesSection = screen.getByRole('heading', { name: '个人分类规则' }).closest('section')!
  await user.click(within(rulesSection).getByRole('button', { name: '编辑规则' }))
  await user.selectOptions(screen.getByRole('combobox', { name: '规则匹配字段' }), 'note')
  await user.clear(screen.getByRole('textbox', { name: '规则匹配文字' }))
  await user.type(screen.getByRole('textbox', { name: '规则匹配文字' }), '午餐')
  await user.clear(screen.getByRole('spinbutton', { name: '规则优先级' }))
  await user.type(screen.getByRole('spinbutton', { name: '规则优先级' }), '250')
  await user.click(within(rulesSection).getByRole('button', { name: '保存规则' }))
  await screen.findByText(/优先级 250/)
  expect(rulePayload).toEqual({ category_id: 'c1', field: 'note', contains: '午餐', priority: 250 })
  await user.click(within(rulesSection).getByRole('button', { name: '删除规则' }))
  expect(await within(rulesSection).findByText('暂无分类规则')).toBeInTheDocument()

  await user.click(within(categorySection).getByRole('button', { name: '删除分类' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('类别仍被引用')
})

it('keeps the category draft and avoids resubmission when the write result is unknown', async () => {
  setupCommon()
  let creates = 0
  server.use(
    http.get('/api/categories', () => HttpResponse.json([])),
    http.get('/api/classification-rules', () => HttpResponse.json([])),
    http.post('/api/categories', () => {
      creates += 1
      return HttpResponse.json({ error: { code: 'WRITE_RESULT_UNKNOWN', message: '请求超时，结果待核对' } }, { status: 503 })
    }),
  )
  renderPage(new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }))
  const user = userEvent.setup()
  const field = await screen.findByRole('textbox', { name: '新分类名称' })
  await user.type(field, '餐饮')
  await user.click(screen.getByRole('button', { name: '添加' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('操作结果尚未确认')
  expect(screen.getByRole('textbox', { name: '新分类名称' })).toHaveValue('餐饮')
  expect(creates).toBe(1)
})

it('shows anomaly review success/failure and refreshes candidate queries on success', async () => {
  setupCommon()
  let fail = true
  let anomalyReads = 0
  server.use(
    http.get('/api/categories', () => HttpResponse.json([])),
    http.get('/api/classification-rules', () => HttpResponse.json([])),
    http.get('/api/billing/anomalies', () => {
      anomalyReads += 1
      return HttpResponse.json({ items: [{ anomaly_key: 'review-1', rule: 'DUPLICATE_V1', status: 'unreviewed', evidence: { merchant: 'Cafe', amount: '20.00', date: '2026-10-28' }, transaction_ids: [1, 2] }] })
    }),
    http.post('/api/billing/anomaly-reviews', () => fail
      ? HttpResponse.json({ error: { code: 'UPSTREAM_ERROR', message: '核实暂不可用' } }, { status: 503 })
      : HttpResponse.json({ anomaly_key: 'review-1', status: 'verified' })),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  renderPage(client)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '确认异常' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('核实暂不可用')
  expect(anomalyReads).toBe(1)

  fail = false
  await user.click(screen.getByRole('button', { name: '确认异常' }))
  expect(await screen.findByRole('status')).toHaveTextContent('异常候选已确认')
  expect(anomalyReads).toBeGreaterThan(1)
})
