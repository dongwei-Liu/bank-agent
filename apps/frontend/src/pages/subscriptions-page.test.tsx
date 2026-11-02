import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { expect, it } from 'vitest'

import { server } from '@/test/server'
import { SubscriptionsPage } from './subscriptions-page'

it('creates a reminder, evaluates a budget, and marks an inbox item read through the API', async () => {
  const requests: { method: string; path: string; body?: Record<string, unknown> }[] = []
  let notificationRead = false
  const rule = {
    id: 'rule-1', scope: 'ALL_VERIFIED', subscription_id: null, amount_gt: null,
    month: null, lead_days: [1], status: 'ACTIVE', created_at: '2026-10-27T00:00:00Z', updated_at: '2026-10-27T00:00:00Z',
  }
  server.use(
    http.get('/api/subscriptions', () => HttpResponse.json([])),
    http.get('/api/subscriptions/renewals', () => HttpResponse.json({ as_of: '2026-10-27', timezone: 'Asia/Shanghai', days: 3, from_date: '2026-10-27', to_date: '2026-10-30', last_scan_at: null, upcoming: [], needs_review: [] })),
    http.get('/api/subscriptions/forecast', () => HttpResponse.json({ as_of: '2026-10-27', timezone: 'Asia/Shanghai', from_date: '2026-10-01', to_date: '2026-10-31', last_scan_at: null, items: [], projected_total: '0.00', needs_review: [], complete: true, status: 'complete' })),
    http.get('/api/subscriptions/reminder-rules', () => HttpResponse.json(requests.some((item) => item.path === '/api/subscriptions/reminder-rules' && item.method === 'POST') ? [rule] : [])),
    http.get('/api/subscriptions/budget-rules', () => HttpResponse.json([])),
    http.get('/api/notifications', () => HttpResponse.json([{
      id: 'notice-1', kind: 'REMINDER', status: 'ACTIVE', payload: { title: 'Stream Box预计续费提醒', message: '预计于2026-11-01扣费，金额68.00元。' },
      read_at: notificationRead ? '2026-10-27T01:00:00Z' : null, created_at: '2026-10-27T00:00:00Z', invalidated_at: null,
    }])),
    http.post('/api/notifications/notice-1/read', () => { notificationRead = true; requests.push({ method: 'POST', path: '/api/notifications/notice-1/read' }); return HttpResponse.json({ id: 'notice-1', read: true }) }),
    http.post('/api/subscriptions/reminder-rules', async ({ request }) => {
      const body = await request.json() as Record<string, unknown>
      requests.push({ method: 'POST', path: '/api/subscriptions/reminder-rules', body })
      expect(request.headers.get('Idempotency-Key')).toBeTruthy()
      return HttpResponse.json({ ...rule, reused: false }, { status: 201 })
    }),
    http.post('/api/subscriptions/budget-rules', async ({ request }) => {
      const body = await request.json() as Record<string, unknown>
      requests.push({ method: 'POST', path: '/api/subscriptions/budget-rules', body })
      return HttpResponse.json({ rule: { id: 'budget-1', month: body.month, amount: body.amount, status: 'ACTIVE' }, reused: false, evaluation: {
        month: body.month, budget: body.amount, actual_total: '80.00', projected_remaining: '0.00', known_total: '80.00',
        over_budget: true, under_budget_confirmed: false, complete: true, previous_actual_total: '60.00', suggestions: [],
      } }, { status: 201 })
    }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><SubscriptionsPage /></MemoryRouter></QueryClientProvider>)

  await screen.findByLabelText('站内提醒')
  await userEvent.click(screen.getByRole('checkbox', { name: '提前1天' }))
  await userEvent.click(screen.getByRole('button', { name: '保存提醒规则' }))
  expect(await screen.findByText('提醒规则已保存。')).toBeInTheDocument()
  expect(requests.find((item) => item.path === '/api/subscriptions/reminder-rules' && item.method === 'POST')?.body).toMatchObject({ scope: 'ALL_VERIFIED', lead_days: [1], month: null })

  await userEvent.click(screen.getByRole('button', { name: '标为已读' }))
  expect(requests.some((item) => item.path === '/api/notifications/notice-1/read')).toBe(true)

  await userEvent.type(screen.getByLabelText('预算金额'), '50')
  await userEvent.click(screen.getByRole('button', { name: '保存并立即评估' }))
  expect(await screen.findByLabelText('订阅预算评估')).toHaveTextContent('已知金额已超过预算')
  expect(screen.getByLabelText('订阅预算评估')).toHaveTextContent('上月实际订阅扣费')
  expect(requests.find((item) => item.path === '/api/subscriptions/budget-rules')?.body).toMatchObject({ amount: '50' })
})
