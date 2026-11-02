import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, delay, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { storeTokens } from '@/lib/api'
import { server } from '@/test/server'
import { AgentPanel } from './agent-panel'

function installDurableConversationBridge() {
  type FixtureRun = { runId: string; traceId: string; message: string; events: Array<{ type: string; data: Record<string, unknown> }> }
  const conversationId = 'test-conversation'
  let history: string[] = []
  let eventId = 0
  let pending: FixtureRun | null = null
  const storedMessages: Array<{ id: string; role: 'user' | 'assistant'; content: string; sequence: number; created_at: string }> = []
  const storedEvents: Array<{ event_id: string; conversation_id: string; run_id: string; trace_id: string; type: string; created_at: string; data: Record<string, unknown> }> = []
  const runs = new Map<string, FixtureRun>()
  const timestamp = '2026-10-28T00:00:00Z'
  const summary = { id: conversationId, title: '测试会话', status: 'ACTIVE', created_at: timestamp, updated_at: timestamp, expires_at: '2026-11-27T00:00:00Z', latest_run_status: null }
  function appendEvent(run: FixtureRun, type: string, data: Record<string, unknown>) {
    eventId += 1
    storedEvents.push({ event_id: String(eventId), conversation_id: conversationId, run_id: run.runId, trace_id: run.traceId, type, created_at: timestamp, data })
  }
  server.use(
    http.get('/api/agent/conversations', () => HttpResponse.json([summary])),
    http.post('/api/agent/conversations', () => HttpResponse.json(summary, { status: 201 })),
    http.get('/api/agent/conversations/:id', () => HttpResponse.json({ ...summary, messages: storedMessages, events: storedEvents, current_run: null })),
    http.delete('/api/agent/conversations/:id', () => new HttpResponse(null, { status: 204 })),
    http.post('/api/agent/conversations/:id/messages', async ({ request }) => {
      const body = await request.json() as { message: string; query_context?: unknown; continuation_ref?: string; option_ref?: string }
      let legacy: Response
      try {
        legacy = await fetch(new URL('/api/agent/messages', request.url), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: request.headers.get('Authorization') ?? '' },
          body: JSON.stringify({ message: body.message, history: history.slice(-8), query_context: body.query_context, continuation_ref: body.continuation_ref, option_ref: body.option_ref }),
        })
      } catch {
        return HttpResponse.error()
      }
      const payload = await legacy.json() as { trace_id?: string; message?: string; events?: Array<{ type: string; data: Record<string, unknown> }>; error?: unknown }
      if (!legacy.ok) return HttpResponse.json(payload, { status: legacy.status })
      history = [...history, body.message]
      const runId = `run-${history.length}`
      pending = { runId, traceId: payload.trace_id ?? runId, message: payload.message ?? '', events: payload.events ?? [] }
      runs.set(runId, pending)
      storedMessages.push({ id: `user-${runId}`, role: 'user', content: body.message, sequence: storedMessages.length + 1, created_at: timestamp })
      storedMessages.push({ id: `assistant-${runId}`, role: 'assistant', content: pending.message, sequence: storedMessages.length + 1, created_at: timestamp })
      appendEvent(pending, 'EXECUTING', { attempt: 1 })
      appendEvent(pending, 'TEXT_COMPLETE', { text: pending.message, message_id: `assistant-${pending.runId}` })
      for (const event of pending.events) appendEvent(pending, event.type, event.data)
      appendEvent(pending, 'SUCCESS', { message_id: `assistant-${pending.runId}` })
      return HttpResponse.json({
        id: runId, conversation_id: conversationId, trace_id: pending.traceId, status: 'QUEUED', attempts: 0,
        error_code: null, error_message: null, created_at: timestamp, started_at: null, completed_at: null, assistant_message: null,
      }, { status: 202 })
    }),
    http.get('/api/agent/conversations/:id/events', ({ request }) => {
      const lastEventId = Number(request.headers.get('Last-Event-ID') ?? 0)
      const frames = storedEvents.filter((event) => Number(event.event_id) > lastEventId).map((event) =>
        `id: ${event.event_id}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`,
      ).join('')
      return new HttpResponse(`${frames}event: stream.complete\ndata: {}\n\n`, { headers: { 'Content-Type': 'text/event-stream' } })
    }),
    http.get('/api/agent/runs/:id', ({ params }) => {
      const run = runs.get(String(params.id))
      if (!run) return HttpResponse.json({ error: { code: 'NOT_FOUND', message: '运行不存在' } }, { status: 404 })
      return HttpResponse.json({
        id: run.runId, conversation_id: conversationId, trace_id: run.traceId, status: 'SUCCEEDED', attempts: 1,
        error_code: null, error_message: null, created_at: timestamp, started_at: timestamp, completed_at: timestamp,
        assistant_message: { id: `assistant-${run.runId}`, role: 'assistant', content: run.message, sequence: history.length * 2, created_at: timestamp },
      })
    }),
  )
}

beforeEach(() => {
  installDurableConversationBridge()
  server.use(http.get('/api/accounts', () => HttpResponse.json([
    { id: 7, account_no: '000000007', currency: 'CNY' },
  ])))
})

describe('AgentPanel', () => {
  it('keeps the panel usable when a compatible conversation response omits message collections', async () => {
    server.use(http.get('/api/agent/conversations/:id', () => HttpResponse.json({
      id: 'test-conversation',
      title: '测试会话',
      status: 'ACTIVE',
      created_at: '2026-10-28T00:00:00Z',
      updated_at: '2026-10-28T00:00:00Z',
      expires_at: '2026-11-27T00:00:00Z',
      latest_run_status: null,
      current_run: null,
    })))

    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)

    expect(await screen.findByLabelText('给智能银行助理发送消息')).toBeEnabled()
    expect(screen.getByText(/你好，我可以查询本人余额和流水/)).toBeInTheDocument()
  })

  it('sends the message and selected query context and renders the authenticated response', async () => {
    let requestBody: unknown
    storeTokens({ access_token: 'access', refresh_token: 'refresh-token-value-long', token_type: 'bearer', expires_in: 60 })
    server.use(http.post('/api/agent/messages', async ({ request }) => {
      requestBody = await request.json()
      expect(request.headers.get('Authorization')).toBe('Bearer access')
      return HttpResponse.json({
        trace_id: 'trace-1',
        message: '你目前共有 19,262.64 元。',
        events: [{ type: 'BALANCE_RESULT', data: { currency: 'CNY', total: '19262.640000', account_count: 1, complete: true } }],
      })
    }))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)

    await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '我还有多少钱？')
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))

    expect(await screen.findByText('你目前共有 19,262.64 元。')).toBeInTheDocument()
    expect(screen.getByText('CNY 19262.640000')).toBeInTheDocument()
    expect(requestBody).toEqual({ message: '我还有多少钱？', history: [], query_context: { account_id: 7, period: expect.stringMatching(/^\d{4}-\d{2}$/) } })
  })

  it('keeps each result card on its own reply across three questions', async () => {
    let turn = 0
    const totals: Record<string, string> = { 'result-1': '11.00', 'result-2': '22.00', 'result-3': '33.00' }
    storeTokens({ access_token: 'access', refresh_token: 'refresh-token-value-long', token_type: 'bearer', expires_in: 60 })
    server.use(
      http.post('/api/agent/messages', () => {
        turn += 1
        return HttpResponse.json({
          trace_id: `trace-${turn}`,
          message: `第 ${turn} 轮查询完成。`,
          events: [{ type: 'ANALYSIS_READY', data: { analysis_id: `result-${turn}`, kind: 'balance' } }],
        })
      }),
      http.get('/api/agent/analyses/:id', ({ params }) => HttpResponse.json({
        analysis_id: String(params.id), kind: 'balance', expires_at: '2030-01-01T00:00:00Z',
        data: { account_ids: [7], currency: 'CNY', total: totals[String(params.id)], account_count: 1, complete: true },
      })),
    )
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)

    const input = screen.getByLabelText('给智能银行助理发送消息')
    for (const [index, question] of ['查询余额', '查询消费统计', '查询订阅金额'].entries()) {
      await userEvent.type(input, question)
      await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
      await screen.findByText(`第 ${index + 1} 轮查询完成。`)
      await vi.waitFor(() => expect(screen.getAllByLabelText('授权分析结果')).toHaveLength(index + 1))
    }

    const cards = screen.getAllByLabelText('授权分析结果')
    for (const amount of Object.values(totals)) {
      expect(cards.filter((card) => card.textContent?.includes(amount))).toHaveLength(1)
    }
  })

  it.each([
    ['消费统计', '消费分类统计', '餐饮消费 88 CNY，未分类 12 CNY。'],
    ['异常候选', '异常消费候选', '发现 1 个疑似重复消费候选，需要核实。'],
  ])('sends %s to the same authenticated chat endpoint', async (button, intent, answer) => {
    let requestBody: unknown
    storeTokens({ access_token: 'access', refresh_token: 'refresh-token-value-long', token_type: 'bearer', expires_in: 60 })
    server.use(http.post('/api/agent/messages', async ({ request }) => {
      requestBody = await request.json()
      expect(request.headers.get('Authorization')).toBe('Bearer access')
      await delay(100)
      return HttpResponse.json({ trace_id: 'bill-1', message: answer, events: [] })
    }))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await screen.findByRole('option', { name: '尾号 0007 · CNY' })
    fireEvent.change(screen.getByLabelText('账单月份'), { target: { value: '2026-09' } })
    await userEvent.click(screen.getByRole('button', { name: button }))
    expect(screen.getByRole('button', { name: button })).toBeDisabled()
    expect(await screen.findByText(answer)).toBeInTheDocument()
    expect(requestBody).toEqual({ message: `查询账户 7 在 2026-09 的${intent}`, history: [], query_context: { account_id: 7, period: '2026-09' } })
  })

  it('preserves free text while sending the chosen account and month', async () => {
    let requestBody: unknown
    server.use(http.post('/api/agent/messages', async ({ request }) => {
      requestBody = await request.json()
      return HttpResponse.json({ trace_id: 'free-text', message: '已查询九月份消费。', events: [] })
    }))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await screen.findByRole('option', { name: '尾号 0007 · CNY' })
    fireEvent.change(screen.getByLabelText('账单月份'), { target: { value: '2026-09' } })
    await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '账户id7在9月份的消费情况')
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
    expect(await screen.findByText('已查询九月份消费。')).toBeInTheDocument()
    expect(requestBody).toEqual({ message: '账户id7在9月份的消费情况', history: [], query_context: { account_id: 7, period: '2026-09' } })
  })

  it('does not apply a stale month or selected account to an all-account natural-language statistics request', async () => {
    let requestBody: unknown
    server.use(http.post('/api/agent/messages', async ({ request }) => {
      requestBody = await request.json()
      return HttpResponse.json({ trace_id: 'all-natural', message: '已按本月查询本人全部账户。', events: [] })
    }))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await screen.findByRole('option', { name: '尾号 0007 · CNY' })
    fireEvent.change(screen.getByLabelText('账单月份'), { target: { value: '2026-09' } })
    await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '统计我所有账户的消费分类，按金额从高到低列出。')
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
    expect(await screen.findByText('已按本月查询本人全部账户。')).toBeInTheDocument()
    expect(requestBody).toEqual({ message: '统计我所有账户的消费分类，按金额从高到低列出。', history: [], query_context: {} })
  })

  it.each([
    ['全部账户统计', '消费分类统计'],
    ['全部账户异常', '异常消费候选'],
  ])('sends %s with an explicit all-account scope', async (button, intent) => {
    let requestBody: unknown
    storeTokens({ access_token: 'access', refresh_token: 'refresh-token-value-long', token_type: 'bearer', expires_in: 60 })
    server.use(http.post('/api/agent/messages', async ({ request }) => {
      expect(request.headers.get('Authorization')).toBe('Bearer access')
      requestBody = await request.json()
      return HttpResponse.json({ trace_id: 'all-accounts', message: '已汇总本人全部合格账户。', events: [] })
    }))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await screen.findByRole('option', { name: '尾号 0007 · CNY' })
    fireEvent.change(screen.getByLabelText('账单月份'), { target: { value: '2026-09' } })
    await userEvent.click(screen.getByRole('button', { name: button }))
    expect(await screen.findByText('已汇总本人全部合格账户。')).toBeInTheDocument()
    expect(requestBody).toEqual({ message: `查询我所有账户在 2026-09 的${intent}`, history: [], query_context: { period: '2026-09' } })
  })

  it('shows failures without appending a successful assistant result', async () => {
    server.use(http.post('/api/agent/messages', () => HttpResponse.json({ error: { code: 'AGENT_ROUTING_FAILED', message: '暂时无法识别业务需求' } }, { status: 503 })))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await userEvent.click(screen.getByRole('button', { name: '查余额' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法识别业务需求')
    expect(screen.queryByText('余额查询结果')).not.toBeInTheDocument()
  })

  it('sends only the previous eight user messages as untrusted conversation history', async () => {
    const bodies: Array<{ message: string; history: string[] }> = []
    server.use(http.post('/api/agent/messages', async ({ request }) => {
      bodies.push(await request.json() as { message: string; history: string[] })
      return HttpResponse.json({ trace_id: crypto.randomUUID(), message: '请继续。', events: [] })
    }))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    const input = screen.getByLabelText('给智能银行助理发送消息')
    await userEvent.type(input, '先查联系人')
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
    await screen.findByText('请继续。')
    await userEvent.type(input, '再转账')
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
    await vi.waitFor(() => expect(bodies).toHaveLength(2))
    expect(bodies[0].history).toEqual([])
    expect(bodies[1].history).toEqual(['先查联系人'])
  })

  it('submits the opaque option reference when the user chooses a clarification card', async () => {
    const optionRef = 'a'.repeat(32)
    const requests: Array<{ message: string; option_ref?: string }> = []
    server.use(http.post('/api/agent/messages', async ({ request }) => {
      const body = await request.json() as { message: string; option_ref?: string }
      requests.push(body)
      if (requests.length === 1) {
        return HttpResponse.json({
          trace_id: 'clarify-1',
          message: '找到多个联系人，请选择。',
          events: [{ type: 'CLARIFICATION_REQUIRED', data: { kind: 'recipient', question: '请选择收款人', options: [{ option_ref: optionRef, label: '房租', description: 'Bob' }] } }],
        })
      }
      return HttpResponse.json({ trace_id: 'clarify-2', message: '已使用所选联系人继续处理。', events: [] })
    }))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '给 Bob 转 20 元')
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
    await userEvent.click(await screen.findByRole('button', { name: /房租/ }))
    expect(await screen.findByText('已使用所选联系人继续处理。')).toBeInTheDocument()
    expect(requests[1]).toMatchObject({ message: '我选择“房租”', option_ref: optionRef })
  })

  it('renders a structured Action card without claiming that money moved', async () => {
    server.use(http.post('/api/agent/messages', () => HttpResponse.json({
      trace_id: 'transfer-action',
      message: '请求已创建，尚未执行。',
      events: [{ type: 'TRANSFER_ACTION_CREATED', data: { action_id: 'action-1', recipient_name: 'Bob', from_account_suffix: '0001', amount: '20.00', currency: 'CNY', status: 'WAITING_CONFIRMATION' } }],
    })))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '给 Bob 转 20 元')
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
    expect(await screen.findByText('等待确认的转账请求')).toBeInTheDocument()
    expect(screen.getByText('请求已创建，尚未执行。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '查看并确认' })).toBeInTheDocument()
  })

  it.each(['balance', 'transactions', 'statistics', 'anomalies'] as const)('reads exact %s data only through the authorized analysis endpoint', async (kind) => {
    let privateReads = 0
    const statistics = { account_ids: [7], currency: 'CNY', from_date: '2026-09-01', to_date: '2026-09-30', transaction_count: 6, totals: { expense: '19262.64' }, categories: { 餐饮: '19262.64', 交通: '90.00', 娱乐: '500.00' }, monthly: {}, snapshot_atomic: false, data_cutoff: '2026-10-22T00:00:00Z' }
    server.use(
      http.post('/api/agent/messages', () => HttpResponse.json({ trace_id: 'private', message: '查询已完成，请查看结果卡。', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'result-1', kind } }] })),
      http.get('/api/agent/analyses/result-1', () => {
        privateReads += 1
        const data = kind === 'balance'
          ? { currency: 'CNY', total: '19262.64', account_count: 1, complete: true }
          : kind === 'transactions'
            ? { currency: 'CNY', transaction_count: 1, complete: true, from_date: null, to_date: null, account_ids: [7], items: [{ account_id: 7, transaction_id: 9, date: '2026-09-10', amount: '19262.64', currency: 'CNY', direction: 'debit', category: '餐饮' }] }
            : kind === 'statistics'
              ? statistics
              : { ...statistics, items: [{ anomaly_key: 'a1', rule: 'DUPLICATE_V1', evidence: { merchant: 'Private Cafe', amount: '19262.64', date: '2026-09-10' } }], detection: { status: 'no_model' } }
        return HttpResponse.json({ analysis_id: 'result-1', kind, expires_at: '2026-10-23T00:00:00Z', data })
      }),
    )
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await userEvent.click(screen.getByRole('button', { name: '查余额' }))
    expect(await screen.findByLabelText('授权分析结果')).toHaveTextContent('19,262.64')
    expect(privateReads).toBe(1)
    if (kind === 'statistics') {
      const rows = screen.getByLabelText('授权分析结果').textContent!
      expect(rows.indexOf('餐饮：')).toBeLessThan(rows.indexOf('娱乐：'))
      expect(rows.indexOf('娱乐：')).toBeLessThan(rows.indexOf('交通：'))
    }
    if (kind === 'anomalies') expect(screen.getByLabelText('授权分析结果')).not.toHaveTextContent('本次仅规则检测')
  })

  it.each([
    ['verified', '确认异常', '已确认'],
    ['ignored', '忽略', '已忽略'],
  ] as const)('lets the user review a candidate as %s from the result card', async (status, button, statusLabel) => {
    const submitted: unknown[] = []
    let savedStatus: 'unreviewed' | 'verified' | 'ignored' = 'unreviewed'
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    client.setQueryData(['billing-anomalies'], [])
    server.use(
      http.post('/api/agent/messages', () => HttpResponse.json({ trace_id: 'review', message: '查询完成', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'review-card', kind: 'anomalies' } }] })),
      http.get('/api/agent/analyses/review-card', () => HttpResponse.json({
        analysis_id: 'review-card', kind: 'anomalies', expires_at: '2030-01-01T00:00:00Z',
        data: { account_ids: [7], from_date: '2026-09-01', to_date: '2026-09-30', items: [{ anomaly_key: 'review-key', rule: 'LARGE_V1', status: 'unreviewed', current_review_status: savedStatus, evidence: { amount: '88.00', median: '10.00', samples: 8 } }] },
      })),
      http.post('/api/billing/anomaly-reviews', async ({ request }) => {
        const body = await request.json() as { anomaly_key: string; status: 'verified' | 'ignored' }
        submitted.push(body)
        await delay(100)
        savedStatus = body.status
        return HttpResponse.json({ id: 'review-1', anomaly_key: body.anomaly_key, status: savedStatus })
      }),
    )
    render(<QueryClientProvider client={client}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await userEvent.click(screen.getByRole('button', { name: '查余额' }))
    const card = await screen.findByLabelText('授权分析结果')
    await userEvent.click(within(card).getByRole('button', { name: button }))
    expect(within(card).getByRole('button', { name: status === 'verified' ? '确认中…' : '忽略中…' })).toBeDisabled()
    expect(within(card).getByRole('button', { name: status === 'verified' ? '忽略' : '确认异常' })).toBeDisabled()
    expect(await within(card).findByText(new RegExp(`大额消费候选.*${statusLabel}`))).toBeInTheDocument()
    expect(await screen.findByRole('status')).toHaveTextContent(status === 'verified' ? '异常候选已确认' : '异常候选已忽略')
    expect(within(card).getByRole('button', { name: statusLabel })).toBeDisabled()
    expect(within(card).getByRole('button', { name: status === 'verified' ? '忽略' : '确认异常' })).toBeEnabled()
    expect(submitted).toEqual([{ anomaly_key: 'review-key', status }])
    expect(client.getQueryState(['billing-anomalies'])?.isInvalidated).toBe(true)

    const alternate = status === 'verified' ? '忽略' : '确认异常'
    await userEvent.click(within(card).getByRole('button', { name: alternate }))
    const changedLabel = status === 'verified' ? '已忽略' : '已确认'
    expect(await within(card).findByRole('button', { name: changedLabel })).toBeDisabled()
    expect(submitted).toHaveLength(2)
  })

  it('keeps the prior review state when a change fails', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    server.use(
      http.post('/api/agent/messages', () => HttpResponse.json({ trace_id: 'review-failure', message: '查询完成', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'review-failure-card', kind: 'anomalies' } }] })),
      http.get('/api/agent/analyses/review-failure-card', () => HttpResponse.json({
        analysis_id: 'review-failure-card', kind: 'anomalies', expires_at: '2030-01-01T00:00:00Z',
        data: { account_ids: [7], items: [{ anomaly_key: 'review-key', rule: 'LARGE_V1', status: 'unreviewed', current_review_status: 'ignored', evidence: { amount: '88.00' } }] },
      })),
      http.post('/api/billing/anomaly-reviews', () => HttpResponse.json({ error: { code: 'UPSTREAM_ERROR', message: '核实保存失败' } }, { status: 503 })),
    )
    render(<QueryClientProvider client={client}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await userEvent.click(screen.getByRole('button', { name: '查余额' }))
    const card = await screen.findByLabelText('授权分析结果')
    await userEvent.click(within(card).getByRole('button', { name: '确认异常' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('核实保存失败')
    expect(within(card).getByRole('button', { name: '已忽略' })).toBeDisabled()
    expect(within(card).getByRole('button', { name: '确认异常' })).toBeEnabled()
  })

  it('synchronizes a review change across already loaded cards for the same candidate', async () => {
    let resultCount = 0
    let savedStatus: 'unreviewed' | 'verified' = 'unreviewed'
    server.use(
      http.post('/api/agent/messages', () => {
        resultCount += 1
        return HttpResponse.json({ trace_id: `multi-${resultCount}`, message: '已完成', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: `multi-card-${resultCount}`, kind: 'anomalies' } }] })
      }),
      http.get('/api/agent/analyses/:id', ({ params }) => HttpResponse.json({
        analysis_id: String(params.id), kind: 'anomalies', expires_at: '2030-01-01T00:00:00Z',
        data: { account_ids: [7], items: [{ anomaly_key: 'shared-review-key', rule: 'LARGE_V1', status: 'unreviewed', current_review_status: savedStatus, evidence: { amount: '88.00' } }] },
      })),
      http.post('/api/billing/anomaly-reviews', async ({ request }) => {
        const body = await request.json() as { status: 'verified' }
        savedStatus = body.status
        return HttpResponse.json({ id: 'review-shared', anomaly_key: 'shared-review-key', status: savedStatus })
      }),
    )
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await userEvent.click(screen.getByRole('button', { name: '异常候选' }))
    await screen.findByLabelText('授权分析结果')
    await userEvent.click(screen.getByRole('button', { name: '异常候选' }))
    const cards = await screen.findAllByLabelText('授权分析结果')
    expect(cards).toHaveLength(2)
    await userEvent.click(within(cards[0]).getByRole('button', { name: '确认异常' }))
    for (const card of cards) {
      expect(await within(card).findByRole('button', { name: '已确认' })).toBeDisabled()
      expect(within(card).getByRole('button', { name: '忽略' })).toBeEnabled()
    }
  })

  it('shows an expired analysis instead of stale amounts', async () => {
    server.use(
      http.post('/api/agent/messages', () => HttpResponse.json({ trace_id: 'expired', message: '查询完成', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'expired', kind: 'balance' } }] })),
      http.get('/api/agent/analyses/expired', () => HttpResponse.json({ error: { code: 'ANALYSIS_EXPIRED', message: '分析结果已过期，请重新查询' } }, { status: 410 })),
    )
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await userEvent.click(screen.getByRole('button', { name: '查余额' }))
    expect(await screen.findByText('分析结果已过期，请重新查询')).toBeInTheDocument()
    expect(screen.queryByText('CNY 19262.640000')).not.toBeInTheDocument()
  })

  it.each(['statistics', 'anomalies'] as const)('shows loading then an empty %s result without inventing data', async (kind) => {
    let release!: () => void
    const pending = new Promise<void>((resolve) => { release = resolve })
    server.use(
      http.post('/api/agent/messages', () => HttpResponse.json({ trace_id: 'empty', message: '查询完成', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'empty', kind } }] })),
      http.get('/api/agent/analyses/empty', async () => {
        await pending
        const data = kind === 'statistics' ? { account_ids: [7], currency: 'CNY', transaction_count: 0, totals: {}, categories: {}, monthly: {}, snapshot_atomic: true } : { account_ids: [7], items: [], detection: { status: 'insufficient_history' } }
        return HttpResponse.json({ analysis_id: 'empty', kind, expires_at: '2030-01-01T00:00:00Z', data })
      }),
    )
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await userEvent.click(screen.getByRole('button', { name: '查余额' }))
    expect(await screen.findByText('正在读取授权分析结果…')).toBeInTheDocument()
    release()
    expect(await screen.findByText(kind === 'statistics' ? '查询期间没有可统计流水。' : '本次查询未返回异常候选。未返回候选不代表全部交易安全。')).toBeInTheDocument()
    if (kind === 'anomalies') expect(screen.getByLabelText('授权分析结果')).not.toHaveTextContent('历史样本不足')
  })

  it('retries a failed private read without re-running the model request', async () => {
    let reads = 0
    let queries = 0
    server.use(
      http.post('/api/agent/messages', () => { queries += 1; return HttpResponse.json({ trace_id: 'retry', message: '查询完成', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'retry', kind: 'balance' } }] }) }),
      http.get('/api/agent/analyses/retry', () => {
        reads += 1
        if (reads === 1) return HttpResponse.json({ error: { code: 'UPSTREAM_ERROR', message: '核心银行暂不可用', retryable: true } }, { status: 503 })
        return HttpResponse.json({ analysis_id: 'retry', kind: 'balance', expires_at: '2030-01-01T00:00:00Z', data: { currency: 'CNY', total: '42.01', account_count: 1, complete: true } })
      }),
    )
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
    await userEvent.click(screen.getByRole('button', { name: '查余额' }))
    expect(await screen.findByText('核心银行暂不可用')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^重试$/ }))
    expect(await screen.findByLabelText('授权分析结果')).toHaveTextContent('42.01')
    expect(queries).toBe(1)
    expect(reads).toBe(2)
  })
})

it.each([
  ['2026-09-01', '2026-09-30', '2026 年 9 月 · 消费分类统计', false],
  ['2026-01-01', '2026-12-31', '2026 年 · 年度消费分类统计', true],
  ['2026-01-03', '2026-09-30', '区间消费统计', true],
] as const)('renders period-specific statistics for %s to %s', async (from, to, title, breakdown) => {
  server.use(
    http.get('/api/accounts', () => HttpResponse.json([{ id: 7, account_no: '000000007', currency: 'CNY' }])),
    http.post('/api/agent/messages', () => HttpResponse.json({ message: '查询完成', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'period', kind: 'statistics' } }] })),
    http.get('/api/agent/analyses/period', () => HttpResponse.json({ kind: 'statistics', expires_at: '2030-01-01T00:00:00Z', data: {
      account_ids: [7, 8], currency: 'CNY', from_date: from, to_date: to, transaction_count: 12,
      totals: { income: '900', expense: '300', transfer: '77' }, categories: { 餐饮: '300' },
      monthly: { '2026-09': { income: '600', expense: '200', transfer: '55' }, '2026-01': { income: '300', expense: '100', transfer: '22' } },
      data_cutoff: '2026-10-01T00:00:00Z', snapshot_atomic: true,
    } })),
  )
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.click(screen.getByRole('button', { name: '消费统计' }))
  expect(await screen.findByText(title)).toBeInTheDocument()
  const card = screen.getByLabelText('授权分析结果')
  expect(card).toHaveTextContent('2 个账户')
  expect(card).toHaveTextContent('300.00')
  expect(card).toHaveTextContent(from)
  expect(card).toHaveTextContent(to)
  if (breakdown) {
    const rows = screen.getByLabelText('逐月收支明细').textContent!
    expect(rows.indexOf('2026-01')).toBeLessThan(rows.indexOf('2026-09'))
    expect(rows).toContain('55.00')
    expect(rows).not.toContain('2026-12')
  } else expect(screen.queryByLabelText('逐月收支明细')).not.toBeInTheDocument()
})

it.each([[0, 3], [1, 4]])('separates subscription matches %s from saved records %s', async (matched, found) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const onClose = vi.fn()
  client.setQueryData(['subscriptions'], [])
  client.setQueryData(['subscription', 'old-subscription'], {})
  client.setQueryData(['subscription-renewals', 3], {})
  server.use(
    http.get('/api/accounts', () => HttpResponse.json([])),
    http.post('/api/agent/messages', async ({ request }) => {
      expect((await request.json() as { message: string }).message).toContain('识别')
      return HttpResponse.json({
        trace_id: 'subscription-scan', message: '订阅扣费识别已完成。',
        events: [{ type: 'SUBSCRIPTION_SCAN_COMPLETED', data: {
          created: matched, updated: 0, found, matched_candidates: matched,
          from_date: '2024-08-17', to_date: '2026-10-26',
          scanned_at: '2026-10-26T08:00:00+00:00', timezone: 'Asia/Shanghai',
        } }],
      })
    }),
  )
  render(<QueryClientProvider client={client}><MemoryRouter><AgentPanel onClose={onClose} /></MemoryRouter></QueryClientProvider>)
  await userEvent.click(screen.getByRole('button', { name: '识别订阅扣费' }))
  const card = await screen.findByLabelText('订阅识别结果')
  expect(card).toHaveTextContent(`本次规则匹配 ${matched} 项`)
  expect(card).toHaveTextContent(`全部已保存记录 ${found} 项`)
  if (!matched) expect(card).toHaveTextContent('不代表没有订阅')
  for (const key of [['subscriptions'], ['subscription', 'old-subscription'], ['subscription-renewals', 3]]) {
    expect(client.getQueryState(key)?.isInvalidated).toBe(true)
  }
  const link = screen.getByRole('link', { name: '查看订阅候选与扣费证据' })
  expect(link).toHaveAttribute('href', '/subscriptions')
  await userEvent.click(link)
  expect(onClose).toHaveBeenCalledTimes(1)
})

it('opens an existing bill report from the natural-language result card', async () => {
  const onClose = vi.fn()
  server.use(
    http.post('/api/agent/messages', () => HttpResponse.json({
      trace_id: 'opened-report',
      message: '已找到对应账单报告，结果卡可直接打开。',
      events: [{ type: 'BILL_REPORT_OPENED', data: {
        report_id: 'report-2026', period: '2026', status: 'complete', generated: false,
      } }],
    })),
    http.get('/api/bill-report-generations/report-2026/status', () => HttpResponse.json({
      report_id: 'report-2026', status: 'complete', progress: 100, period: '2026',
    })),
  )
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/chat']}>
        <Routes>
          <Route path="/chat" element={<AgentPanel onClose={onClose} />} />
          <Route path="/insights/reports/:id" element={<p>报告详情页</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '查看我的年度账单报告')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  expect(await screen.findByText('已找到对应账单报告，结果卡可直接打开。')).toBeInTheDocument()
  const card = await screen.findByLabelText('账单报告结果')
  expect(card).toHaveTextContent('账单报告 · 已生成')
  const link = within(card).getByRole('link', { name: '打开报告' })
  expect(link).toHaveAttribute('href', '/insights/reports/report-2026')
  await userEvent.click(link)
  expect(await screen.findByText('报告详情页')).toBeInTheDocument()
  expect(onClose).toHaveBeenCalledTimes(1)
})

it('shows an existing report failure without silently creating another task', async () => {
  let generationPosts = 0
  server.use(
    http.post('/api/agent/messages', () => HttpResponse.json({
      trace_id: 'failed-report', message: '已找到对应账单报告，但生成失败。',
      events: [{ type: 'BILL_REPORT_OPENED', data: {
        report_id: 'failed-report-id', period: '2025', status: 'failed', generated: false,
      } }],
    })),
    http.get('/api/bill-report-generations/failed-report-id/status', () => HttpResponse.json({
      report_id: 'failed-report-id', status: 'failed', progress: 100, period: '2025', error: 'CORE_READ_FAILED',
    })),
    http.post('/api/bill-report-generations', () => {
      generationPosts += 1
      return HttpResponse.json({ report_id: 'unexpected' })
    }),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '查看2025年度账单报告')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  const card = await screen.findByLabelText('账单报告结果')
  expect(await within(card).findByRole('alert')).toHaveTextContent('核心银行流水读取失败')
  expect(within(card).getByRole('link', { name: '查看报告列表并重新生成' })).toHaveAttribute('href', '/insights/reports')
  expect(generationPosts).toBe(0)
})

it('shows a definite Agent failure without misreporting an unknown result', async () => {
  let requests = 0
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: 3 } } })
  client.setQueryData(['subscriptions'], [])
  server.use(
    http.get('/api/accounts', () => HttpResponse.json([])),
    http.post('/api/agent/messages', () => {
      requests += 1
      return HttpResponse.json({ error: { code: 'AGENT_UNAVAILABLE', message: '暂时不可用' } }, { status: 503 })
    }),
  )
  render(<QueryClientProvider client={client}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.click(screen.getByRole('button', { name: '识别订阅扣费' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('暂时不可用')
  expect(screen.getByRole('alert')).not.toHaveTextContent('暂勿重复提交')
  expect(screen.queryByRole('link', { name: '到订阅管理页核对' })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('订阅识别结果')).not.toBeInTheDocument()
  expect(client.getQueryState(['subscriptions'])?.isInvalidated).not.toBe(true)
  expect(requests).toBe(1)
})

it('offers report-list recovery for an uncertain natural-language report request without retrying', async () => {
  let requests = 0
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: 3 } } })
  client.setQueryData(['bill-report-summaries'], { items: [] })
  client.setQueryData(['subscriptions'], [])
  server.use(
    http.get('/api/accounts', () => HttpResponse.json([])),
    http.post('/api/agent/messages', () => {
      requests += 1
      return HttpResponse.json({
        error: { code: 'WRITE_RESULT_UNKNOWN', message: '连接中断，结果未知' },
      }, { status: 503 })
    }),
  )
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AgentPanel onClose={vi.fn()} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '查看我的年度账单报告')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('账单报告请求结果未确认')
  expect(screen.getByRole('link', { name: '核对报告列表' })).toHaveAttribute('href', '/insights/reports')
  expect(screen.queryByRole('link', { name: '到订阅管理页核对' })).not.toBeInTheDocument()
  expect(client.getQueryState(['bill-report-summaries'])?.isInvalidated).toBe(true)
  expect(client.getQueryState(['subscriptions'])?.isInvalidated).not.toBe(true)
  expect(requests).toBe(1)
})

it.each([
  ['WAITING_CONFIRMATION', '请求尚未执行', '核对并确认取消'],
  ['EXECUTING', '处理中', '查看取消请求'],
  ['SUCCEEDED', '已完成', '查看取消请求'],
  ['FAILED', '执行失败', '查看取消请求'],
])('shows cancellation status %s and links to the action', async (status, description, linkText) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  client.setQueryData(['subscriptions'], [])
  const onClose = vi.fn()
  server.use(
    http.get('/api/accounts', () => HttpResponse.json([])),
    http.post('/api/agent/messages', () => HttpResponse.json({
      trace_id: 'cancel-agent', message: '请查看取消请求。',
      events: [{ type: 'SUBSCRIPTION_CANCEL_REQUESTED', data: { action_id: 'action-1', status } }],
    })),
  )
  render(<QueryClientProvider client={client}><MemoryRouter><AgentPanel onClose={onClose} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '取消 Demo Video 订阅')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  expect(await screen.findByLabelText('订阅取消请求')).toHaveTextContent(description)
  expect(client.getQueryState(['subscriptions'])?.isInvalidated).toBe(true)
  const link = screen.getByRole('link', { name: linkText })
  expect(link).toHaveAttribute('href', '/actions/action-1')
  await userEvent.click(link)
  expect(onClose).toHaveBeenCalledOnce()
})

it('requires an in-chat confirmation before fetching and showing a subscription query result', async () => {
  let status = 'WAITING_CONFIRMATION'
  let confirmations = 0
  let resultReads = 0
  const action = () => ({
    id: 'query-action-1', kind: 'subscription_query', request_hash: 'frozen-query-hash', status,
    amount: '0', payload: {}, result: status === 'SUCCEEDED' ? { result_id: 'query-result-1', result_kind: 'forecast' } : {},
    steps: {}, error_code: null, created_at: '2026-11-01T00:00:00Z', confirmed_at: null, executed_at: null,
    risk_level: 'YELLOW', source: 'AGENT', expires_at: '2099-01-01T00:00:00Z',
  })
  server.use(
    http.post('/api/agent/messages', () => HttpResponse.json({ trace_id: 'query-run', message: '请核对查询条件。', events: [
      { type: 'SUBSCRIPTION_QUERY_REQUESTED', data: {
        action_id: 'query-action-1', query_type: 'FORECAST', summary: '续费预测',
        conditions: ['期间：2026-12-01 至 2026-12-31（上海时间）', '金额严格大于 15 元'],
        risk_level: 'YELLOW', status: 'WAITING_CONFIRMATION', expires_at: '2099-01-01T00:00:00Z',
      } },
    ] })),
    http.get('/api/actions/query-action-1', () => HttpResponse.json(action())),
    http.post('/api/actions/query-action-1/confirm', async ({ request }) => {
      expect(await request.json()).toEqual({ request_hash: 'frozen-query-hash' })
      confirmations += 1
      await delay(40)
      status = 'SUCCEEDED'
      return HttpResponse.json(action())
    }),
    http.get('/api/agent/subscription-results/query-result-1', () => {
      resultReads += 1
      return HttpResponse.json({ id: 'query-result-1', kind: 'forecast', created_at: '2026-11-01T00:00:00Z', expires_at: '2026-11-01T00:30:00Z', data: {
        from_date: '2026-12-01', to_date: '2026-12-31', projected_total: '68.00', complete: true,
        items: [{ subscription_id: 'sub-1', merchant: 'Stream Box', amount: '68.00', charge_date: '2026-12-15' }],
      } })
    }),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '告诉我下个月有哪些续费超过15元')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  const card = await screen.findByLabelText('订阅查询确认')
  expect(card).toHaveTextContent('黄色权限')
  expect(card).toHaveTextContent('金额严格大于 15 元')
  expect(resultReads).toBe(0)
  const click = userEvent.click(within(card).getByRole('button', { name: '确认查询' }))
  expect(await within(card).findByRole('button', { name: '正在确认…' })).toBeDisabled()
  await click
  expect(await screen.findByLabelText('预计续费查询结果')).toHaveTextContent('Stream Box')
  expect(confirmations).toBe(1)
  expect(resultReads).toBeGreaterThan(0)
  expect(within(card).queryByRole('button', { name: '确认查询' })).not.toBeInTheDocument()
})

it('cancels a pending subscription query without reading a result', async () => {
  let status = 'WAITING_CONFIRMATION'
  let resultReads = 0
  const action = () => ({ id: 'query-action-2', kind: 'subscription_query', request_hash: 'hash-2', status,
    amount: '0', payload: {}, result: {}, steps: {}, error_code: null, created_at: '2026-11-01T00:00:00Z',
    confirmed_at: null, executed_at: null, risk_level: 'YELLOW', expires_at: '2099-01-01T00:00:00Z' })
  server.use(
    http.post('/api/agent/messages', () => HttpResponse.json({ trace_id: 'query-cancel', message: '请确认。', events: [
      { type: 'SUBSCRIPTION_QUERY_REQUESTED', data: { action_id: 'query-action-2', query_type: 'LIST', summary: '本人订阅列表', conditions: [], risk_level: 'YELLOW', status, expires_at: '2099-01-01T00:00:00Z' } },
    ] })),
    http.get('/api/actions/query-action-2', () => HttpResponse.json(action())),
    http.post('/api/actions/query-action-2/cancel', () => { status = 'CANCELLED'; return HttpResponse.json(action()) }),
    http.get('/api/agent/subscription-results/:id', () => { resultReads += 1; return HttpResponse.json({}) }),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '查询我的订阅列表')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  const card = await screen.findByLabelText('订阅查询确认')
  await userEvent.click(within(card).getByRole('button', { name: '取消' }))
  expect(await within(card).findByText('查询请求已取消。')).toBeInTheDocument()
  expect(within(card).queryByRole('button', { name: '确认查询' })).not.toBeInTheDocument()
  expect(resultReads).toBe(0)
})

it('restores the durable query event and reads the completed Action after reopening a chat', async () => {
  let resultReads = 0
  server.use(
    http.get('/api/agent/conversations', () => HttpResponse.json([{
      id: 'restored-query-chat', title: '订阅查询', status: 'ACTIVE',
      created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:01:00Z',
      expires_at: '2099-01-01T00:00:00Z', latest_run_status: 'SUCCEEDED',
    }])),
    http.get('/api/agent/conversations/restored-query-chat', () => HttpResponse.json({
      id: 'restored-query-chat', title: '订阅查询', status: 'ACTIVE',
      created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:01:00Z',
      expires_at: '2099-01-01T00:00:00Z', current_run: null,
      messages: [
        { id: 'user-query', role: 'user', content: '查询下个月预计续费', sequence: 1, created_at: '2026-11-01T00:00:00Z' },
        { id: 'assistant-query', role: 'assistant', content: '请确认查询条件。', sequence: 2, created_at: '2026-11-01T00:00:01Z' },
      ],
      events: [
        { event_id: '1', conversation_id: 'restored-query-chat', run_id: 'query-run', trace_id: 'query-trace', type: 'TEXT_COMPLETE', data: { message_id: 'assistant-query' }, created_at: '2026-11-01T00:00:01Z' },
        { event_id: '2', conversation_id: 'restored-query-chat', run_id: 'query-run', trace_id: 'query-trace', type: 'SUBSCRIPTION_QUERY_REQUESTED', data: {
          action_id: 'restored-query-action', query_type: 'FORECAST', summary: '续费预测', conditions: ['期间：2026-12-01 至 2026-12-31（上海时间）'],
          risk_level: 'YELLOW', status: 'WAITING_CONFIRMATION', expires_at: '2099-01-01T00:00:00Z',
        }, created_at: '2026-11-01T00:00:01Z' },
        { event_id: '3', conversation_id: 'restored-query-chat', run_id: 'query-run', trace_id: 'query-trace', type: 'SUCCESS', data: { message_id: 'assistant-query' }, created_at: '2026-11-01T00:00:01Z' },
      ],
    })),
    http.get('/api/actions/restored-query-action', () => HttpResponse.json({
      id: 'restored-query-action', kind: 'subscription_query', request_hash: 'restored-hash', status: 'SUCCEEDED',
      amount: '0', payload: {}, result: { result_id: 'restored-result', result_kind: 'forecast' }, steps: {}, error_code: null,
      created_at: '2026-11-01T00:00:00Z', confirmed_at: '2026-11-01T00:00:01Z', executed_at: '2026-11-01T00:00:02Z',
      risk_level: 'YELLOW', source: 'AGENT', expires_at: '2099-01-01T00:00:00Z',
    })),
    http.get('/api/agent/subscription-results/restored-result', () => {
      resultReads += 1
      return HttpResponse.json({ id: 'restored-result', kind: 'forecast', created_at: '2026-11-01T00:00:02Z', expires_at: '2026-11-01T00:30:02Z', data: {
        from_date: '2026-12-01', to_date: '2026-12-31', projected_total: '68.00', complete: true,
        items: [{ subscription_id: 'sub-1', merchant: 'Stream Box', amount: '68.00', charge_date: '2026-12-15' }],
      } })
    }),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  const card = await screen.findByLabelText('订阅查询确认')
  expect(await screen.findByLabelText('预计续费查询结果')).toHaveTextContent('Stream Box')
  expect(card).toHaveTextContent('预计续费安排')
  expect(within(card).queryByRole('button', { name: '确认查询' })).not.toBeInTheDocument()
  expect(resultReads).toBeGreaterThan(0)
})

it('prompts the user to reissue a query after its private result expires', async () => {
  server.use(
    http.post('/api/agent/messages', () => HttpResponse.json({ trace_id: 'expired-query', message: '请确认。', events: [
      { type: 'SUBSCRIPTION_QUERY_REQUESTED', data: { action_id: 'expired-query-action', query_type: 'LIST', summary: '本人订阅列表', conditions: [], risk_level: 'YELLOW', status: 'WAITING_CONFIRMATION', expires_at: '2099-01-01T00:00:00Z' } },
    ] })),
    http.get('/api/actions/expired-query-action', () => HttpResponse.json({
      id: 'expired-query-action', kind: 'subscription_query', request_hash: 'expired-hash', status: 'SUCCEEDED',
      amount: '0', payload: {}, result: { result_id: 'expired-query-result', result_kind: 'subscriptions' }, steps: {}, error_code: null,
      created_at: '2026-11-01T00:00:00Z', confirmed_at: '2026-11-01T00:00:01Z', executed_at: '2026-11-01T00:00:02Z',
      risk_level: 'YELLOW', source: 'AGENT', expires_at: '2099-01-01T00:00:00Z',
    })),
    http.get('/api/agent/subscription-results/expired-query-result', () => HttpResponse.json({
      error: { code: 'SUBSCRIPTION_RESULT_EXPIRED', message: '订阅结果已过期，请重新发起查询' },
    }, { status: 410 })),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '查询我的订阅列表')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  expect(await screen.findByText('订阅结果已过期，请重新发起查询')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '确认查询' })).not.toBeInTheDocument()
})

it('sends only the clarification reference when the user chooses a reminder lead', async () => {
  const requests: { message: string; continuation_ref?: string }[] = []
  let calls = 0
  server.use(
    http.get('/api/accounts', () => HttpResponse.json([])),
    http.post('/api/agent/messages', async ({ request }) => {
      requests.push(await request.json() as { message: string; continuation_ref?: string })
      calls += 1
      if (calls === 1) return HttpResponse.json({ trace_id: 'reminder-query', message: '请补充提前量。', events: [
        { type: 'SUBSCRIPTION_FORECAST_READY', data: { result_id: 'forecast-result', from_date: '2026-11-01', to_date: '2026-11-30', complete: true, item_count: 1 } },
        { type: 'SUBSCRIPTION_CLARIFICATION_REQUIRED', data: { clarification_id: 'clarification-ref', question: '你希望提前几天收到提醒？', options: [1, 3, 7] } },
      ] })
      return HttpResponse.json({ trace_id: 'reminder-saved', message: '提醒已保存。', events: [
        { type: 'SUBSCRIPTION_REMINDER_RULE_SAVED', data: { rule_id: 'rule-1', scope: 'AMOUNT_GT', month: '2026-11', lead_days: [3], amount_gt: '50', reused: false } },
      ] })
    }),
    http.get('/api/actions/forecast-action', () => HttpResponse.json({ id: 'forecast-action', kind: 'subscription_query', request_hash: 'forecast-hash', status: 'WAITING_CONFIRMATION', amount: '0', payload: {}, result: {}, steps: {}, error_code: null, created_at: '2026-10-27T01:00:00Z', confirmed_at: null, executed_at: null, risk_level: 'YELLOW', expires_at: '2099-01-01T00:00:00Z' })),
    http.get('/api/agent/subscription-results/forecast-result', () => HttpResponse.json({
      id: 'forecast-result', kind: 'forecast', created_at: '2026-10-27T01:00:00Z', expires_at: '2026-10-27T01:30:00Z',
      data: { from_date: '2026-11-01', to_date: '2026-11-30', timezone: 'Asia/Shanghai', projected_total: '68.00', complete: true, filters: { amount_gt: '50' }, needs_review: [], items: [{ subscription_id: 'sub-1', merchant: 'Stream Box', amount: '68.00', charge_date: '2026-11-15' }] },
    })),
  )
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '帮我看看下个月有哪些自动扣费，超过50元的都提醒我')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  expect(await screen.findByLabelText('预计续费查询结果')).toHaveTextContent('Stream Box')
  expect(screen.getByLabelText('预计续费查询结果')).toHaveTextContent('金额严格大于 50 元')
  expect(screen.getByLabelText('提醒时间补充')).toHaveTextContent('提前几天')
  await userEvent.click(screen.getByRole('button', { name: '提前3天' }))
  expect(await screen.findByLabelText('提醒规则已保存')).toHaveTextContent('适用于2026-11')
  expect(requests).toHaveLength(2)
  expect(requests[1]).toMatchObject({ message: '提前3天', continuation_ref: 'clarification-ref' })
})

it('renders the structured wealth assessment navigation without accepting chat answers', async () => {
  server.use(http.post('/api/agent/messages', () => HttpResponse.json({
    trace_id: 'wealth-risk',
    message: '需要你本人完成本次五题风险测评。',
    events: [{ type: 'WEALTH_RISK_ASSESSMENT_REQUIRED', data: { reason: 'subscription', route: '/wealth/risk-assessment' } }],
  })))
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '申购定存')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  const card = await screen.findByLabelText('需要风险测评')
  expect(card).toHaveTextContent('答案只能由你在结构化页面填写')
  expect(within(card).getByRole('link', { name: '开始本次五题测评' })).toHaveAttribute('href', '/wealth/risk-assessment')
})

it('renders a wealth RED Action card without claiming funds moved', async () => {
  server.use(http.post('/api/agent/messages', () => HttpResponse.json({
    trace_id: 'wealth-action',
    message: '定存申购请求已准备好，资金尚未变更。',
    events: [{ type: 'WEALTH_ACTION_CREATED', data: { action_id: 'wealth-action-1', operation: 'subscription', status: 'WAITING_CONFIRMATION' } }],
  })))
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '申购 Fixed Demo 100 元')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  expect(await screen.findByText('定存申购安全请求')).toBeInTheDocument()
  expect(screen.getByText('资金尚未变更，需要核对、确认并完成 OTP。')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '打开确认与验证页面' })).toBeInTheDocument()
})

it('renders a birthday task card with separate task review and RED authorization paths', async () => {
  server.use(http.post('/api/agent/messages', () => HttpResponse.json({
    trace_id: 'birthday-task',
    message: '生日任务已准备好，资金尚未冻结或转出。',
    events: [{ type: 'ORCHESTRATION_TASK_CREATED', data: {
      task_id: 'task-1', action_id: 'action-1', task_status: 'WAITING_AUTHORIZATION',
      authorization_status: 'WAITING_CONFIRMATION', route: '/tasks/task-1',
    } }],
  })))
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '创建爱人生日任务')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  const card = await screen.findByLabelText('生日任务已创建')
  expect(card).toHaveTextContent('资金尚未冻结或转出')
  expect(within(card).getByRole('link', { name: '核对完整任务' })).toHaveAttribute('href', '/tasks/task-1')
  expect(within(card).getByRole('button', { name: '打开确认与验证' })).toBeInTheDocument()
})

it('renders only authenticated birthday task summaries returned as structured events', async () => {
  server.use(http.post('/api/agent/messages', () => HttpResponse.json({
    trace_id: 'birthday-list', message: '已读取本人生日任务。', events: [{
      type: 'ORCHESTRATION_TASKS_READY', data: { has_more: false, items: [{
        task_id: 'task-1', label: '爱人生日', event_date: '2026-12-20', status: 'ACTIVE', route: '/tasks/task-1',
      }] },
    }],
  })))
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '查看我的生日任务')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  const card = await screen.findByLabelText('生日任务查询结果')
  expect(card).toHaveTextContent('爱人生日')
  expect(within(card).getByRole('link', { name: /爱人生日/ })).toHaveAttribute('href', '/tasks/task-1')
})

it.each([
  ['wealth_products', '定存产品目录', {
    items: [{ product_id: 10, name: 'Fixed Demo', currency: 'CNY', min_deposit_amount: '100.00', max_deposit_amount: '100000.00', min_term: { value: 1, unit: 'months' }, max_term: { value: 36, unit: 'months' }, annual_interest_rates: ['2.0'], risk_level: 2, allows_premature: true, enabled: true }],
  }],
  ['wealth_recommend', '定存适配推荐', {
    criteria: { amount: '1000.00', term_months: 3, needs_liquidity: true },
    items: [{ product: { product_id: 10, name: 'Fixed Demo', currency: 'CNY', min_deposit_amount: '100.00', max_deposit_amount: '100000.00', min_term: { value: 1, unit: 'months' }, max_term: { value: 36, unit: 'months' }, annual_interest_rates: ['2.0'], risk_level: 2, allows_premature: true, enabled: true }, term_months: 3, annual_interest_rate: '2.0', estimated_interest: '5.00', estimate_only: true, reason: '适配条件匹配' }],
  }],
  ['wealth_holdings', '我的定存持有', {
    items: [{ holding_id: 100, product_id: 10, product_name: 'Fixed Demo', account_suffix: '0100', principal: '800.00', currency: 'CNY', annual_interest_rate: '2.0', maturity_date: '2099-01-01', status: 'ACTIVE' }],
  }],
] as const)('reads exact %s facts only from the authenticated private endpoint', async (kind, title, data) => {
  let privateReads = 0
  server.use(
    http.post('/api/agent/messages', () => HttpResponse.json({ trace_id: 'wealth-private', message: '精确结果请查看结果卡。', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'wealth-result', kind } }] })),
    http.get('/api/agent/analyses/wealth-result', () => {
      privateReads += 1
      return HttpResponse.json({ analysis_id: 'wealth-result', kind, created_at: '2026-10-29T00:00:00Z', expires_at: '2030-01-01T00:00:00Z', data })
    }),
  )
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AgentPanel onClose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('给智能银行助理发送消息'), '查询定存')
  await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
  const card = await screen.findByLabelText('授权分析结果')
  expect(card).toHaveTextContent(title)
  expect(card).toHaveTextContent('Fixed Demo')
  expect(privateReads).toBe(1)
})
