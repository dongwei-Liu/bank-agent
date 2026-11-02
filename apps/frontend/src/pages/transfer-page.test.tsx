import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { server } from '@/test/server'
import { TransferPage } from './transfer-page'

const accounts = [
  { id: 1, account_no: '000000001', client_id: 1, client_name: 'Alice', product_id: 2, product_name: '日常账户', deposit_type: 'savings', currency: 'CNY', status: 'ACTIVE', available_balance: '100.00' },
  { id: 2, account_no: '000000002', client_id: 1, client_name: 'Alice', product_id: 2, product_name: '备用账户', deposit_type: 'savings', currency: 'CNY', status: 'ACTIVE', available_balance: '50.00' },
]

function renderInternalTransfer() {
  server.use(http.get('/api/accounts', () => HttpResponse.json(accounts)))
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/payments/internal']}>
        <Routes><Route path="/payments/internal" element={<TransferPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TransferPage validation', () => {
  it('rejects an incomplete transfer and an amount above the available balance before any write request', async () => {
    const user = userEvent.setup()
    renderInternalTransfer()

    await screen.findByRole('heading', { name: '本人账户互转' })
    await user.click(screen.getByRole('button', { name: '下一步：确认转账' }))
    expect(screen.getByRole('alert')).toHaveTextContent('请选择付款账户、转入账户并填写有效金额')

    await user.selectOptions(screen.getByLabelText('付款账户'), '1')
    await user.selectOptions(screen.getByLabelText('转入账户'), '2')
    await user.type(screen.getByLabelText('金额（元）'), '100.01')
    await user.click(screen.getByRole('button', { name: '下一步：确认转账' }))

    expect(screen.getByRole('alert')).toHaveTextContent('转账金额不能超过可用余额')
  })
})
