import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { server } from '@/test/server'
import { ActionPage } from './action-page'

describe('ActionPage', () => {
  it('shows only confirmation actions in WAITING_CONFIRMATION', async () => {
    server.use(http.get('/api/actions/a1', () => HttpResponse.json({ id: 'a1', kind: 'transfer', request_hash: 'x'.repeat(64), status: 'WAITING_CONFIRMATION', amount: '200.00', payload: {}, result: {}, steps: {}, error_code: null, created_at: '2026-10-11T10:00:00Z', confirmed_at: null, executed_at: null })), http.get('/api/actions/a1/audit', () => HttpResponse.json([])))
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/actions/a1']}><Routes><Route path="/actions/:actionId" element={<ActionPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('等待你确认参数')).toBeInTheDocument(); expect(screen.getByRole('button', { name: '确认并继续' })).toBeInTheDocument(); expect(screen.queryByPlaceholderText('6 位验证码')).not.toBeInTheDocument()
  })

  it('blocks an expired subscription cancellation confirmation and offers a safe return path', async () => {
    server.use(
      http.get('/api/actions/a1', () => HttpResponse.json({
        id: 'a1', kind: 'subscription_cancel', request_hash: 'x'.repeat(64), status: 'WAITING_CONFIRMATION', amount: '0',
        payload: { subscription_id: 's1', subscription_snapshot: { merchant: 'Demo Video', expected_amount: '12.34', cadence: 'MONTHLY', next_charge_at: '2026-11-01' } }, result: {}, steps: {}, error_code: null,
        created_at: '2026-10-11T10:00:00Z', expires_at: '2020-01-01T00:00:00Z', confirmed_at: null, executed_at: null,
      })),
      http.get('/api/actions/a1/audit', () => HttpResponse.json([])),
    )
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/actions/a1']}><Routes><Route path="/actions/:actionId" element={<ActionPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText(/此确认请求已过期/)).toBeInTheDocument()
    expect(screen.getByText('Demo Video')).toBeInTheDocument()
    expect(screen.getByText('2026-11-01')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '确认并继续' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回订阅管理并重新申请' })).toHaveAttribute('href', '/subscriptions')
  })

  it('explains an explicit cancellation failure and returns to a fresh request path', async () => {
    server.use(
      http.get('/api/actions/a1', () => HttpResponse.json({
        id: 'a1', kind: 'subscription_cancel', request_hash: 'x'.repeat(64), status: 'FAILED', amount: '0',
        payload: { subscription_id: 's1', merchant: 'Demo Video', expected_amount: '12.34', cadence: 'MONTHLY', next_charge_at: '2026-11-01' },
        result: {}, steps: {}, error_code: 'DEMO_MERCHANT_UNAVAILABLE',
        created_at: '2026-10-11T10:00:00Z', expires_at: null, confirmed_at: '2026-10-11T10:01:00Z', executed_at: null,
      })),
      http.get('/api/actions/a1/audit', () => HttpResponse.json([])),
    )
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/actions/a1']}><Routes><Route path="/actions/:actionId" element={<ActionPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText(/取消请求已明确失败/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '重新查看订阅并申请' })).toHaveAttribute('href', '/subscriptions')
  })

  it('returns an orchestration authorization to its immutable task review page', async () => {
    server.use(
      http.get('/api/actions/a1', () => HttpResponse.json({
        id: 'a1', kind: 'orchestration_authorization', request_hash: 'x'.repeat(64), status: 'SUCCEEDED', amount: '300.00',
        payload: { task_id: 'task-1' }, result: {}, steps: {}, error_code: null,
        created_at: '2026-10-29T10:00:00Z', confirmed_at: '2026-10-29T10:01:00Z', executed_at: '2026-10-29T10:02:00Z',
      })),
      http.get('/api/actions/a1/audit', () => HttpResponse.json([])),
    )
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/actions/a1']}><Routes><Route path="/actions/:actionId" element={<ActionPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByRole('heading', { name: '授权生日鲜花与蛋糕计划' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回生日任务' })).toHaveAttribute('href', '/tasks/task-1')
  })
})
