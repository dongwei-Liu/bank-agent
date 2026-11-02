import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { OrchestrationTask } from '@/lib/api'
import { server } from '@/test/server'
import { TaskPage } from './future-service-page'

const task: OrchestrationTask = {
  id: 'task-1', event_id: 'event-1', template: 'BIRTHDAY_GIFTS_V1', status: 'ACTIVE',
  from_account_id: 1, total_amount: '300.00', currency: 'CNY',
  authorization_action_id: 'action-1', plan_hash: 'internal-plan-hash',
  next_run_at: '2026-12-01T09:00:00+08:00', error_code: 'NODE_NEEDS_ATTENTION', version: 1,
  created_at: '2026-10-29T01:00:00Z', updated_at: '2026-10-29T01:00:00Z',
  event: {
    id: 'event-1', kind: 'BIRTHDAY', label: '爱人生日', event_date: '2026-12-20',
    status: 'ACTIVE', created_at: '2026-10-29T01:00:00Z', updated_at: '2026-10-29T01:00:00Z',
  },
  authorization: { action_id: 'action-1', status: 'SUCCEEDED', risk_level: 'RED', request_hash: 'request-hash' },
  nodes: [
    {
      id: 'node-ok', task_id: 'task-1', node_key: 'confirm_event', kind: 'CONFIRM_EVENT', label: '核对生日计划',
      status: 'SUCCEEDED', risk_level: 'GREEN', scheduled_at: null, amount: '0.00', merchant_id: null,
      attempts: 1, error_code: null, result: {}, created_at: '2026-10-29T01:00:00Z', updated_at: '2026-10-29T01:00:00Z',
    },
    {
      id: 'node-failed', task_id: 'task-1', node_key: 'reserve_flower', kind: 'RESERVE_FUNDS', label: '预留鲜花资金',
      status: 'FAILED', risk_level: 'YELLOW', scheduled_at: '2026-12-01T09:00:00+08:00', amount: '100.00', merchant_id: null,
      attempts: 1, error_code: 'UPSTREAM_FAILED', result: {}, created_at: '2026-10-29T01:00:00Z', updated_at: '2026-10-29T01:00:00Z',
    },
    {
      id: 'node-unknown', task_id: 'task-1', node_key: 'purchase_cake', kind: 'PURCHASE', label: '购买生日蛋糕',
      status: 'RECONCILING', risk_level: 'RED', scheduled_at: '2026-12-18T09:00:00+08:00', amount: '200.00', merchant_id: 'merchant-cake',
      attempts: 1, error_code: 'WRITE_RESULT_UNKNOWN', result: {}, created_at: '2026-10-29T01:00:00Z', updated_at: '2026-10-29T01:00:00Z',
    },
  ],
  edges: [{ from: 'confirm_event', to: 'reserve_flower' }],
  reservations: [
    {
      id: 'reservation-1', task_id: 'task-1', node_id: 'node-failed', user_id: 'user-1', purpose: 'FLOWER',
      account_id: 1, amount: '100.00', currency: 'CNY', status: 'PENDING', hold_transaction_id: null,
      release_transaction_id: null, error_code: null, created_at: '2026-10-29T01:00:00Z', updated_at: '2026-10-29T01:00:00Z',
    },
  ],
  orders: [
    {
      id: 'order-1', task_id: 'task-1', node_id: 'node-unknown', user_id: 'user-1', merchant_id: 'merchant-cake',
      reservation_id: 'reservation-2', amount: '200.00', currency: 'CNY', status: 'RECONCILING',
      fineract_transfer_id: null, from_transaction_id: null, to_transaction_id: null, error_code: 'WRITE_RESULT_UNKNOWN',
      created_at: '2026-10-29T01:00:00Z', updated_at: '2026-10-29T01:00:00Z',
    },
  ],
  events: [{ id: 1, task_id: 'task-1', node_id: null, type: 'TASK_CREATED', data: {}, created_at: '2026-10-29T01:00:00Z' }],
  allowed_commands: ['pause', 'cancel'],
}

function renderTask() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/tasks/task-1']}>
        <Routes><Route path="/tasks/:taskId" element={<TaskPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TaskPage', () => {
  it('renders the fixed DAG as a readable timeline and only exposes server-approved recovery actions', async () => {
    let commandKey = ''
    server.use(
      http.get('/api/tasks/task-1', () => HttpResponse.json(task)),
      http.get('/api/accounts', () => HttpResponse.json([{
        id: 1, account_no: '000000001', client_id: 1, client_name: 'Alice', product_id: 2,
        product_name: 'BANK_AGENT_SAVINGS', deposit_type: 'SAVINGS', currency: 'CNY', status: 'ACTIVE', available_balance: '9700.00',
      }])),
      http.post('/api/tasks/task-1/pause', ({ request }) => {
        commandKey = request.headers.get('Idempotency-Key') ?? ''
        return HttpResponse.json({ ...task, status: 'PAUSED', allowed_commands: ['resume', 'cancel'] })
      }),
    )
    renderTask()

    expect(await screen.findByRole('heading', { name: '爱人生日' })).toBeInTheDocument()
    expect(screen.getByText('固定生日计划已创建')).toBeInTheDocument()
    expect(screen.getByText('**** 0001', { exact: false })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '核对并完成确认 / OTP' })).toHaveAttribute('href', '/actions/action-1')
    expect(screen.getByRole('button', { name: '暂停计划' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '取消剩余任务' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '恢复计划' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '转为人工处理' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重试此步骤' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '只读核对结果' })).toBeInTheDocument()
    expect(screen.queryByText('internal-plan-hash')).not.toBeInTheDocument()
    expect(screen.queryByText('WRITE_RESULT_UNKNOWN')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '暂停计划' }))
    await waitFor(() => expect(commandKey).not.toBe(''))
    expect(await screen.findByRole('button', { name: '恢复计划' })).toBeInTheDocument()
  })
})
