import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { Card } from '@/lib/api'
import { server } from '@/test/server'
import { CardDetailPage } from './cards-page'

const baseCard: Card = {
  id: 'card-1',
  account_id: 7,
  product_name: '智汇借记卡',
  alias: '日常消费',
  masked_number: '**** **** **** 1234',
  last4: '1234',
  status: 'ACTIVE',
  currency: 'CNY',
  available_balance: '1000.00',
  single_limit: '5000.00',
  daily_limit: '20000.00',
  online_enabled: true,
  pos_enabled: true,
  atm_enabled: true,
  international_enabled: false,
  replaces_card_id: null,
  created_at: '2026-10-16T00:00:00+00:00',
  updated_at: '2026-10-16T00:00:00+00:00',
}

function renderCard(status: Card['status']) {
  server.use(
    http.get('/api/cards/card-1', () => HttpResponse.json({ ...baseCard, status })),
    http.get('/api/cards/card-1/transactions', () => HttpResponse.json([])),
  )
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/cards/card-1']}>
        <Routes><Route path="/cards/:cardId" element={<CardDetailPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('CardDetailPage state actions', () => {
  it.each([
    ['PENDING_ACTIVATION', ['使用 OTP 激活'], ['安全查看卡号', '锁卡', 'OTP 解锁', 'OTP 补卡']],
    ['ACTIVE', ['安全查看卡号', '锁卡', '挂失'], ['使用 OTP 激活', 'OTP 解锁', 'OTP 补卡']],
    ['LOCKED', ['OTP 解锁', '挂失'], ['使用 OTP 激活', '安全查看卡号', '锁卡', 'OTP 补卡']],
    ['LOST', ['OTP 补卡'], ['使用 OTP 激活', '安全查看卡号', '锁卡', 'OTP 解锁']],
    ['REPLACED', [], ['使用 OTP 激活', '安全查看卡号', '锁卡', 'OTP 解锁', 'OTP 补卡', '挂失']],
  ] satisfies Array<[Card['status'], string[], string[]]>)('shows only valid actions for %s', async (status, shown, hidden) => {
    renderCard(status)
    expect(await screen.findByText('日常消费')).toBeInTheDocument()
    for (const name of shown) expect(screen.getByRole('button', { name })).toBeInTheDocument()
    for (const name of hidden) expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
    if (status === 'LOST' || status === 'REPLACED') expect(screen.queryByText('限额与交易渠道')).not.toBeInTheDocument()
    else expect(screen.getByText('限额与交易渠道')).toBeInTheDocument()
  })
})
