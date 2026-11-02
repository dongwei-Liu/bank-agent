import { HttpResponse, delay, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { API_AGENT_TIMEOUT_MS, ApiError, api, apiRequest, shouldRetryQuery, storeTokens, type AgentRun, type AgentStreamEvent } from './api'
import { server } from '@/test/server'

function eventFrame(event: AgentStreamEvent, sseId = event.event_id) {
  return `id: ${sseId}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`
}

function completedEventStream(events: AgentStreamEvent[]) {
  return new HttpResponse(`${events.map((event) => eventFrame(event)).join('')}event: stream.complete\ndata: {}\n\n`, {
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

function agentEvent(eventId: string, runId: string, type: string, data: Record<string, unknown>, conversationId = 'chat-1'): AgentStreamEvent {
  return {
    event_id: eventId, conversation_id: conversationId, run_id: runId, trace_id: `trace-${runId}`,
    type, created_at: '2026-11-01T00:00:00Z', data,
  }
}

function agentRun(overrides: Partial<AgentRun> = {}): AgentRun {
  return {
    id: 'run-current', conversation_id: 'chat-1', trace_id: 'trace-current', status: 'SUCCEEDED', attempts: 1,
    error_code: null, error_message: null, created_at: '2026-11-01T00:00:00Z',
    started_at: '2026-11-01T00:00:00Z', completed_at: '2026-11-01T00:00:01Z',
    assistant_message: { id: 'assistant-current', role: 'assistant', content: '当前 Run 持久化回复', sequence: 2, created_at: '2026-11-01T00:00:01Z' },
    ...overrides,
  }
}

describe('API client', () => {
  it('adds the bearer token', async () => {
    storeTokens({ access_token: 'access', refresh_token: 'refresh-token-value-long', token_type: 'bearer', expires_in: 60 })
    server.use(http.get('/api/me', ({ request }) => { expect(request.headers.get('authorization')).toBe('Bearer access'); return HttpResponse.json({ id: 'u1', username: 'alice', client_id: 2, is_admin: false }) }))
    await expect(api.me()).resolves.toMatchObject({ username: 'alice' })
  })
  it('uses one refresh request for concurrent 401 responses', async () => {
    let refreshes = 0
    storeTokens({ access_token: 'expired', refresh_token: 'refresh-token-value-long', token_type: 'bearer', expires_in: 60 })
    server.use(http.get('/api/accounts', ({ request }) => request.headers.get('authorization') === 'Bearer renewed' ? HttpResponse.json([]) : new HttpResponse(null, { status: 401 })), http.post('/api/auth/refresh', () => { refreshes += 1; return HttpResponse.json({ access_token: 'renewed', refresh_token: 'rotated-refresh-token', token_type: 'bearer', expires_in: 60 }) }))
    await Promise.all([api.accounts(), api.accounts()]); expect(refreshes).toBe(1)
  })
  it('maps structured backend errors', async () => {
    server.use(http.get('/api/health', () => HttpResponse.json({ error: { code: 'UPSTREAM_UNAVAILABLE', message: '核心银行不可用', retryable: true } }, { status: 503 })))
    await expect(api.health()).rejects.toMatchObject({ status: 503, code: 'UPSTREAM_UNAVAILABLE', retryable: true })
  })
  it('marks query timeouts as retryable', async () => {
    server.use(http.get('/api/slow-query', async () => { await delay(50); return HttpResponse.json({ ok: true }) }))
    await expect(apiRequest('/slow-query', { auth: false, timeoutMs: 5 })).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT', retryable: true })
  })
  it('does not invite a timed-out write to be submitted again', async () => {
    server.use(http.post('/api/slow-write', async () => { await delay(50); return HttpResponse.json({ ok: true }) }))
    await expect(apiRequest('/slow-write', { method: 'POST', auth: false, timeoutMs: 5 })).rejects.toMatchObject({ code: 'WRITE_RESULT_UNKNOWN', retryable: false })
  })
  it('only retries retryable query failures once', () => {
    expect(shouldRetryQuery(0, new ApiError(503, { retryable: true }))).toBe(true)
    expect(shouldRetryQuery(1, new ApiError(503, { retryable: true }))).toBe(false)
    expect(shouldRetryQuery(0, new ApiError(404, { retryable: false }))).toBe(false)
  })
  it('allows slow Agent POSTs and reports an unknown write result without retry', async () => {
    vi.useFakeTimers()
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    }))
    try {
      const result = api.sendAgentMessage('分析我上个月的消费情况')
      let settled = false
      const checked = expect(result.finally(() => { settled = true })).rejects.toMatchObject({ code: 'WRITE_RESULT_UNKNOWN', retryable: false })
      await vi.advanceTimersByTimeAsync(30_001)
      expect(settled).toBe(false)
      await vi.advanceTimersByTimeAsync(API_AGENT_TIMEOUT_MS)
      await checked
      expect(fetchSpy).toHaveBeenCalledTimes(1)
    } finally {
      fetchSpy.mockRestore()
      vi.useRealTimers()
    }
  })

  it('collects only this Run text and cards when the conversation stream replays older runs', async () => {
    const eventLog = [
      agentEvent('1', 'run-old', 'TEXT_COMPLETE', { text: '旧余额回复', message_id: 'assistant-old' }),
      agentEvent('2', 'run-old', 'ANALYSIS_READY', { analysis_id: 'shared-result', kind: 'balance' }),
      agentEvent('3', 'run-current', 'TEXT_COMPLETE', { text: '本轮统计回复', message_id: 'assistant-current' }),
      agentEvent('4', 'run-current', 'ANALYSIS_READY', { analysis_id: 'shared-result', kind: 'balance' }),
    ]
    server.use(
      http.post('/api/agent/conversations/chat-1/messages', () => HttpResponse.json(agentRun({ status: 'QUEUED', assistant_message: null }), { status: 202 })),
      http.get('/api/agent/conversations/chat-1/events', () => completedEventStream(eventLog)),
      http.get('/api/agent/runs/run-current', () => HttpResponse.json(agentRun({ assistant_message: { id: 'assistant-current', role: 'assistant', content: '本轮统计回复', sequence: 2, created_at: '2026-11-01T00:00:01Z' } }))),
    )

    const response = await api.sendConversationAgentMessage('chat-1', '第二轮问题')

    expect(response.message).toBe('本轮统计回复')
    expect(response.events).toEqual([{ type: 'ANALYSIS_READY', data: { analysis_id: 'shared-result', kind: 'balance' } }])
  })

  it('reconnects from the last event id and ignores a duplicate event id', async () => {
    const completion = agentEvent('10', 'run-current', 'TEXT_COMPLETE', { text: '恢复后的回复', message_id: 'assistant-current' })
    const result = agentEvent('11', 'run-current', 'ANALYSIS_READY', { analysis_id: 'current-result', kind: 'statistics' })
    const requestedCursors: Array<string | null> = []
    let eventConnections = 0
    let runReads = 0
    server.use(
      http.post('/api/agent/conversations/chat-1/messages', () => HttpResponse.json(agentRun({ status: 'QUEUED', assistant_message: null }), { status: 202 })),
      http.get('/api/agent/conversations/chat-1/events', ({ request }) => {
        requestedCursors.push(request.headers.get('Last-Event-ID'))
        eventConnections += 1
        if (eventConnections === 1) {
          return new HttpResponse(`${eventFrame(completion)}event: stream.timeout\ndata: {}\n\n`, {
            headers: { 'Content-Type': 'text/event-stream' },
          })
        }
        return new HttpResponse(`${eventFrame(completion)}${eventFrame(result)}event: stream.complete\ndata: {}\n\n`, {
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }),
      http.get('/api/agent/runs/run-current', () => {
        runReads += 1
        return HttpResponse.json(runReads === 1
          ? agentRun({ status: 'RUNNING', assistant_message: null })
          : agentRun({ assistant_message: { id: 'assistant-current', role: 'assistant', content: '恢复后的持久化回复', sequence: 2, created_at: '2026-11-01T00:00:01Z' } }))
      }),
    )

    const response = await api.resumeAgentRun('chat-1', agentRun({ status: 'RUNNING', assistant_message: null }))

    expect(requestedCursors).toEqual([null, '10'])
    expect(response.message).toBe('恢复后的回复')
    expect(response.events).toEqual([{ type: 'ANALYSIS_READY', data: { analysis_id: 'current-result', kind: 'statistics' } }])
  })

  it('retries an event connection that fails before delivering any events', async () => {
    let eventConnections = 0
    const completion = agentEvent('1', 'run-current', 'TEXT_COMPLETE', { text: '重连回复', message_id: 'assistant-current' })
    server.use(
      http.post('/api/agent/conversations/chat-1/messages', () => HttpResponse.json(agentRun({ status: 'QUEUED', assistant_message: null }), { status: 202 })),
      http.get('/api/agent/conversations/chat-1/events', () => {
        eventConnections += 1
        return eventConnections === 1 ? HttpResponse.error() : completedEventStream([completion])
      }),
      http.get('/api/agent/runs/run-current', () => HttpResponse.json(agentRun({ assistant_message: { id: 'assistant-current', role: 'assistant', content: '重连持久化回复', sequence: 2, created_at: '2026-11-01T00:00:01Z' } }))),
    )

    await expect(api.sendConversationAgentMessage('chat-1', '网络恢复后继续')).resolves.toMatchObject({ message: '重连回复', events: [] })
    expect(eventConnections).toBe(2)
  })

  it('uses the persisted current reply when this Run has no TEXT_COMPLETE and rejects failed Runs', async () => {
    const eventLog = [agentEvent('1', 'run-old', 'TEXT_COMPLETE', { text: '旧回复', message_id: 'assistant-old' })]
    let status: AgentRun['status'] = 'SUCCEEDED'
    server.use(
      http.post('/api/agent/conversations/chat-1/messages', () => HttpResponse.json(agentRun({ status: 'QUEUED', assistant_message: null }), { status: 202 })),
      http.get('/api/agent/conversations/chat-1/events', () => completedEventStream(eventLog)),
      http.get('/api/agent/runs/run-current', () => HttpResponse.json(agentRun({
        status,
        error_code: status === 'FAILED' ? 'AGENT_FAILED' : null,
        error_message: status === 'FAILED' ? '当前请求失败' : null,
      }))),
    )
    await expect(api.sendConversationAgentMessage('chat-1', '只要文字回复')).resolves.toMatchObject({
      message: '当前 Run 持久化回复', events: [],
    })

    status = 'FAILED'
    await expect(api.sendConversationAgentMessage('chat-1', '失败的查询')).rejects.toMatchObject({ code: 'AGENT_FAILED' })
  })
})
