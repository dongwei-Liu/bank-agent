import type { Page, Route } from '@playwright/test'

type AgentDomainEvent = { type: string; data: Record<string, unknown> }
export type LegacyAgentResponse = {
  trace_id?: string
  message?: string
  events?: AgentDomainEvent[]
  error?: unknown
}

export type DurableAgentResponder = (
  body: Record<string, unknown>,
  headers: Record<string, string>,
) => LegacyAgentResponse | Promise<LegacyAgentResponse>

type PendingRun = {
  id: string
  traceId: string
  message: string
  events: AgentDomainEvent[]
}
type StoredAgentMessage = { id: string; role: 'user' | 'assistant'; content: string; sequence: number; created_at: string }
type StoredAgentEvent = {
  event_id: string
  conversation_id: string
  run_id: string
  trace_id: string
  type: string
  created_at: string
  data: Record<string, unknown>
}

/**
 * Adapts the E2E specs' existing synchronous Agent fixtures to the durable
 * conversation protocol used by production. Register this after the spec's
 * broad API route so unhandled legacy requests fall through to it.
 */
export async function installDurableAgentBridge(page: Page, respond: DurableAgentResponder) {
  const conversationId = 'e2e-conversation'
  const timestamp = '2026-10-31T00:00:00Z'
  let runSequence = 0
  let eventSequence = 0
  let latestRunStatus: string | null = null
  const runs = new Map<string, PendingRun>()
  const messages: StoredAgentMessage[] = []
  const events: StoredAgentEvent[] = []
  const summary = {
    id: conversationId,
    title: 'E2E 测试会话',
    status: 'ACTIVE',
    created_at: timestamp,
    updated_at: timestamp,
    expires_at: '2099-01-01T00:00:00Z',
    latest_run_status: null,
  }

  const runPayload = (run: PendingRun, status: 'QUEUED' | 'SUCCEEDED') => ({
    id: run.id,
    conversation_id: conversationId,
    trace_id: run.traceId,
    status,
    attempts: status === 'SUCCEEDED' ? 1 : 0,
    error_code: null,
    error_message: null,
    created_at: timestamp,
    started_at: status === 'SUCCEEDED' ? timestamp : null,
    completed_at: status === 'SUCCEEDED' ? timestamp : null,
    assistant_message: status === 'SUCCEEDED' ? {
      id: `assistant-${run.id}`,
      role: 'assistant',
      content: run.message,
      sequence: runSequence * 2,
      created_at: timestamp,
    } : null,
  })

  async function handle(route: Route) {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (path === '/api/agent/conversations' && method === 'GET') {
      return route.fulfill({ json: [{ ...summary, latest_run_status: latestRunStatus }] })
    }
    if (path === '/api/agent/conversations' && method === 'POST') {
      return route.fulfill({ status: 201, json: summary })
    }
    if (path === `/api/agent/conversations/${conversationId}` && method === 'GET') {
      return route.fulfill({ json: { ...summary, latest_run_status: latestRunStatus, messages, events, current_run: null } })
    }
    if (path === `/api/agent/conversations/${conversationId}` && method === 'DELETE') {
      return route.fulfill({ status: 204, body: '' })
    }
    if (path === `/api/agent/conversations/${conversationId}/messages` && method === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>
      const payload = await respond(body, request.headers())
      runSequence += 1
      const run: PendingRun = {
        id: `e2e-run-${runSequence}`,
        traceId: payload.trace_id ?? `e2e-trace-${runSequence}`,
        message: payload.message ?? '',
        events: payload.events ?? [],
      }
      runs.set(run.id, run)
      latestRunStatus = 'SUCCEEDED'
      messages.push({ id: `user-${run.id}`, role: 'user', content: String(body.message ?? ''), sequence: messages.length + 1, created_at: timestamp })
      messages.push({ id: `assistant-${run.id}`, role: 'assistant', content: run.message, sequence: messages.length + 1, created_at: timestamp })
      const appendEvent = (type: string, data: Record<string, unknown>) => {
        eventSequence += 1
        events.push({ event_id: String(eventSequence), conversation_id: conversationId, run_id: run.id, trace_id: run.traceId, type, created_at: timestamp, data })
      }
      appendEvent('EXECUTING', { attempt: 1 })
      appendEvent('TEXT_COMPLETE', { text: run.message, message_id: `assistant-${run.id}` })
      for (const event of run.events) appendEvent(event.type, event.data)
      appendEvent('SUCCESS', { message_id: `assistant-${run.id}` })
      return route.fulfill({ status: 202, json: runPayload(run, 'QUEUED') })
    }
    if (path === `/api/agent/conversations/${conversationId}/events` && method === 'GET') {
      const lastEventId = Number(request.headers()['last-event-id'] ?? 0)
      const frames = events.filter((event) => Number(event.event_id) > lastEventId).map((event) =>
        `id: ${event.event_id}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`,
      ).join('')
      return route.fulfill({
        body: `${frames}event: stream.complete\ndata: {}\n\n`,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    }
    if (path.startsWith('/api/agent/runs/') && method === 'GET') {
      const run = runs.get(path.split('/').at(-1) ?? '')
      if (run) return route.fulfill({ json: runPayload(run, 'SUCCEEDED') })
      return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: '运行不存在' } } })
    }
    return route.fallback()
  }

  await page.route('**/api/**', handle)
}
