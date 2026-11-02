import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'
import { server } from '@/test/server'
import { AccountDetailPage } from './account-detail-page'

it('opens a report-linked transaction through the authenticated core detail endpoint', async () => {
  let detailReads = 0
  server.use(
    http.get('/api/accounts/1', () => HttpResponse.json({ id: 1, account_no: '000000001', currency: 'CNY', product_name: '储蓄账户', status: 'ACTIVE', available_balance: '100.00' })),
    http.get('/api/accounts/1/transactions', () => HttpResponse.json({ items: [], total: 0, page: 0, page_size: 20 })),
    http.get('/api/accounts/1/transactions/18', () => {
      detailReads += 1
      return HttpResponse.json({ transaction_id: 18, account_id: 1, date: '2026-09-03', amount: '12.50', currency: 'CNY', direction: 'debit', kind: 'expense', type: 'withdrawal', reversed: false, transfer_reference: null, category_id: null, category: '餐饮', merchant: 'Cafe', note: '' })
    }),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}>
    <MemoryRouter initialEntries={['/accounts/1?transaction=18']}>
      <Routes><Route path="/accounts/:accountId" element={<AccountDetailPage />} /></Routes>
    </MemoryRouter>
  </QueryClientProvider>)
  expect(await screen.findByText('单笔流水详情')).toBeInTheDocument()
  expect(await screen.findByText('餐饮')).toBeInTheDocument()
  expect(detailReads).toBe(1)
})

it('saves a personal annotation, refreshes billing data, and clears it to restore automatic classification', async () => {
  let annotation: { id: string; account_id: number; transaction_id: number; category_id: string | null; merchant: string | null; note: string } | null = null
  let savedBody: Record<string, unknown> | undefined
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } })
  client.setQueryData(['billing-statistics', 'invalidation-sentinel'], { totals: { expense: '12.50' } })
  server.use(
    http.get('/api/accounts/1', () => HttpResponse.json({ id: 1, account_no: '000000001', currency: 'CNY', product_name: '储蓄账户', status: 'ACTIVE', available_balance: '100.00' })),
    http.get('/api/accounts/1/transactions', () => HttpResponse.json({ items: [], total: 0, page: 0, page_size: 20 })),
    http.get('/api/accounts/1/transactions/18', () => HttpResponse.json({ transaction_id: 18, account_id: 1, date: '2026-09-03', amount: '12.50', currency: 'CNY', direction: 'debit', kind: 'expense', type: 'withdrawal', reversed: false, transfer_reference: null, category_id: annotation?.category_id ?? null, category: annotation ? '个人餐饮' : '自动分类', merchant: annotation?.merchant ?? 'Cafe', note: annotation?.note ?? 'bank note' })),
    http.get('/api/transaction-annotations', () => HttpResponse.json(annotation ? [annotation] : [])),
    http.get('/api/categories', () => HttpResponse.json([{ id: 'food', name: '个人餐饮' }])),
    http.post('/api/transaction-annotations', async ({ request }) => {
      savedBody = await request.json() as Record<string, unknown>
      annotation = { id: 'annotation-1', ...savedBody } as typeof annotation
      return HttpResponse.json(annotation, { status: 201 })
    }),
    http.delete('/api/transaction-annotations/annotation-1', () => { annotation = null; return HttpResponse.json({ deleted: true }) }),
  )
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/accounts/1?transaction=18']}><Routes><Route path="/accounts/:accountId" element={<AccountDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '修正分类与备注' }))
  await user.selectOptions(await screen.findByRole('combobox', { name: '个人分类' }), 'food')
  await user.click(screen.getByRole('button', { name: '保存标注' }))
  expect(await screen.findByRole('status')).toHaveTextContent('个人标注已保存')
  expect(savedBody).toEqual({ account_id: 1, transaction_id: 18, category_id: 'food', merchant: 'Cafe', note: 'bank note' })
  await waitFor(() => expect(client.getQueryState(['billing-statistics', 'invalidation-sentinel'])?.isInvalidated).toBe(true))
  expect(screen.getByText('个人餐饮')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: '清除全部个人标注' }))
  expect(await screen.findByRole('status')).toHaveTextContent('已恢复自动分类')
  expect(await screen.findByText('自动分类')).toBeInTheDocument()
  expect(annotation).toBeNull()
})
