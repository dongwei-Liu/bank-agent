const API_BASE = '/api'
const ACCESS_KEY = 'bank-agent.access-token'
const REFRESH_KEY = 'bank-agent.refresh-token'
export const API_QUERY_TIMEOUT_MS = 10_000
export const API_WRITE_TIMEOUT_MS = 30_000
export const API_AGENT_TIMEOUT_MS = 300_000

export type ApiErrorBody = { code?: string; message?: string; retryable?: boolean }

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly retryable: boolean

  constructor(status: number, body?: ApiErrorBody) {
    super(body?.message || `请求失败（HTTP ${status}）`)
    this.name = 'ApiError'
    this.status = status
    this.code = body?.code || `HTTP_${status}`
    this.retryable = Boolean(body?.retryable)
  }
}

export type Tokens = { access_token: string; refresh_token: string; token_type: string; expires_in: number }
export type CurrentUser = { id: string; username: string; client_id: number; is_admin: boolean }
export type AccountSummary = {
  id: number; account_no: string; client_id: number; client_name: string; product_id: number
  product_name: string; deposit_type: string; currency: string; status: string; available_balance: string
}
export type AccountDetail = AccountSummary & {
  external_id: string | null; submitted_on: string | null; approved_on: string | null
  activated_on: string | null; nominal_annual_interest_rate: string; allow_overdraft: boolean
}
export type BalanceResponse = {
  account_id: number; account_no: string; client_id: number; client_name: string; balance: string; currency: string
}
export type AccountSummaryResponse = { currency: string; total: string; account_count: number; complete: boolean }
export type Transaction = {
  transaction_id: number; account_id: number; date: string; submitted_date: string | null; amount: string
  currency: string; direction: 'credit' | 'debit' | 'unknown'; kind: string; type: string; reversed: boolean
  transfer_reference: number | null; category_id: string | null; category: string; merchant: string | null; note: string
}
export type TransactionPage = { items: Transaction[]; total: number; page: number; page_size: number }
export type Category = { id: string; user_id?: string; name: string }
export type ClassificationRule = {
  id: string; user_id?: string; category_id: string
  field: 'merchant' | 'note' | 'type'; contains: string; priority: number
}
export type TransactionAnnotation = {
  id: string; user_id?: string; account_id: number; transaction_id: number
  category_id: string | null; merchant: string | null; note: string
}
export type Recipient = { id: string; name: string; phone: string; alias: string; account_id: number; participant_user_id?: string }
export type ActionStatus = 'WAITING_CONFIRMATION' | 'WAITING_VERIFICATION' | 'AUTHORIZED' | 'EXECUTING' | 'RECONCILING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'
export type BankingAction = {
  id: string; kind: string; request_hash: string; status: ActionStatus; amount: string
  payload: Record<string, unknown>; result: Record<string, unknown>; steps: Record<string, unknown>
  error_code: string | null; created_at: string; confirmed_at: string | null; executed_at: string | null
  risk_level?: 'UNKNOWN' | 'YELLOW' | 'RED'; source?: string; expires_at?: string | null
  updated_at?: string; version?: number
}
export type ActionAuditEntry = {
  id: string; event: string; summary: string; status: ActionStatus
  failure_reason: string | null; trace_id: string; resource_type: string
  resource_id: string; created_at: string; data: Record<string, never>
}
export type HealthResponse = { status: string; service: string; message: string }
export type JsonObject = Record<string, unknown>
export type Card = {
  id: string; account_id: number; product_name: string; alias: string; masked_number: string; last4: string
  status: 'PENDING_ACTIVATION' | 'ACTIVE' | 'LOCKED' | 'LOST' | 'REPLACED'; currency: string
  available_balance: string; single_limit: string; daily_limit: string; online_enabled: boolean
  pos_enabled: boolean; atm_enabled: boolean; international_enabled: boolean; replaces_card_id: string | null
  created_at: string; updated_at: string
}
export type CardNumberReveal = { number: string; expires_at: string }
export type DemoMerchant = { id: string; name: string; category: string }
export type CardAuthorization = {
  id: string; card_id: string; merchant_id: string; merchant_name: string; merchant_category: string
  amount: string; currency: string; channel: 'ONLINE' | 'POS' | 'ATM'; country_code: string
  status: 'PENDING' | 'EXECUTING' | 'APPROVED' | 'DECLINED'; decline_code: string | null
  action_id: string | null; fineract_transfer_id: number | null; from_transaction_id: number | null
  to_transaction_id: number | null; created_at: string; updated_at: string
}
export type Subscription = {
  id: string; merchant: string; merchant_category: string; demo_adapter: boolean
  status: 'CANDIDATE' | 'VERIFIED' | 'IGNORED' | 'CANCELLED'; cadence: 'MONTHLY' | 'YEARLY'
  expected_amount: string; amount_tolerance: string; next_charge_at: string | null
  occurrence_count?: number; occurrences?: JsonObject[]; evidence: JsonObject; action_id: string | null
}
export type SubscriptionScanResult = {
  created: number; updated: number; found: number; matched_candidates: number
  from_date: string; to_date: string; scanned_at: string; items: Subscription[]
}
export type SubscriptionRenewals = {
  as_of: string; timezone: 'Asia/Shanghai'; days: number; from_date: string; to_date: string
  last_scan_at: string | null; upcoming: Subscription[]; needs_review: Subscription[]
}
export type SubscriptionForecast = {
  as_of: string; timezone: 'Asia/Shanghai'; from_date: string; to_date: string
  last_scan_at: string | null
  items: { subscription_id: string; merchant: string; cadence: 'MONTHLY' | 'YEARLY'; amount: string; charge_date: string; label: '预计' }[]
  projected_total: string
  needs_review: (Subscription & { reason: string })[]
  complete: boolean; status: 'complete' | 'incomplete'
  filters?: { amount_gt: string | null }
}
export type SubscriptionReminderRule = {
  id: string; scope: 'ALL_VERIFIED' | 'SUBSCRIPTION' | 'AMOUNT_GT'
  subscription_id: string | null; amount_gt: string | null; month: string | null
  lead_days: number[]; status: 'ACTIVE' | 'PAUSED' | 'DELETED' | 'EXPIRED'
  created_at: string; updated_at: string
}
export type SubscriptionBudgetRule = {
  id: string; month: string; amount: string; status: 'ACTIVE' | 'PAUSED' | 'DELETED'
  last_evaluated_on: string | null; created_at?: string; updated_at?: string
}
export type SubscriptionNotification = {
  id: string; kind: 'REMINDER' | 'BUDGET'; status: 'ACTIVE' | 'RESOLVED' | 'INVALIDATED'
  payload: { title?: string; message?: string; budget?: JsonObject; planned_at?: string; original_planned_times?: string[]; catch_up?: boolean }
  read_at: string | null; created_at: string; invalidated_at: string | null
}
export type SubscriptionAgentResult = {
  id: string; kind: 'forecast' | 'budget' | 'rules' | 'subscriptions' | 'subscription_detail'; created_at: string; expires_at: string
  data: SubscriptionForecast | (JsonObject & { items?: Subscription[]; reminder_rules?: SubscriptionReminderRule[]; budget_rules?: SubscriptionBudgetRule[] })
}
export type OrchestrationTaskStatus = 'WAITING_AUTHORIZATION' | 'ACTIVE' | 'PAUSED' | 'CANCELLING'
  | 'WAITING_USER' | 'PARTIAL' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'
export type OrchestrationNodeStatus = 'PENDING' | 'WAITING_AUTHORIZATION' | 'RUNNING'
  | 'RECONCILING' | 'WAITING_USER' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED' | 'SKIPPED'
export type PersonalEvent = {
  id: string; kind: 'BIRTHDAY'; label: string; event_date: string; status: string
  created_at: string; updated_at: string
}
export type OrchestrationNode = {
  id: string; task_id: string; node_key: string; kind: string; label: string
  status: OrchestrationNodeStatus; risk_level: 'GREEN' | 'YELLOW' | 'RED'
  scheduled_at: string | null; amount: string; merchant_id: string | null
  attempts: number; error_code: string | null; result: JsonObject
  created_at: string; updated_at: string
}
export type OrchestrationEdge = { from: string; to: string }
export type FundReservation = {
  id: string; task_id: string; node_id: string; user_id: string; purpose: 'FLOWER' | 'CAKE'
  account_id: number; amount: string; currency: string; status: string
  hold_transaction_id: number | null; release_transaction_id: number | null
  error_code: string | null; created_at: string; updated_at: string
}
export type DemoOrder = {
  id: string; task_id: string; node_id: string; user_id: string; merchant_id: string
  reservation_id: string; amount: string; currency: string; status: string
  fineract_transfer_id: number | null; from_transaction_id: number | null
  to_transaction_id: number | null; error_code: string | null
  created_at: string; updated_at: string
}
export type OrchestrationTaskEvent = {
  id: number; task_id: string; node_id: string | null; type: string
  data: JsonObject; created_at: string
}
export type OrchestrationTask = {
  id: string; event_id: string; template: 'BIRTHDAY_GIFTS_V1'; status: OrchestrationTaskStatus
  from_account_id: number; total_amount: string; currency: 'CNY'
  authorization_action_id: string | null; plan_hash: string; next_run_at: string | null
  error_code: string | null; version: number; created_at: string; updated_at: string
  event: PersonalEvent
  authorization: { action_id: string; status: ActionStatus; risk_level: 'RED'; request_hash: string } | null
  nodes: OrchestrationNode[]; edges: OrchestrationEdge[]
  reservations: FundReservation[]; orders: DemoOrder[]; events: OrchestrationTaskEvent[]
  allowed_commands: Array<'pause' | 'resume' | 'cancel' | 'takeover'>
}
export type BalanceResultEvent = {
  type: 'BALANCE_RESULT'
  data: { currency: string; total: string; account_count: number; complete: boolean }
}
export type AgentAnalysisKind = 'balance' | 'transactions' | 'statistics' | 'anomalies'
  | 'wealth_products' | 'wealth_recommend' | 'wealth_holdings'
export type AnalysisReadyEvent = { type: 'ANALYSIS_READY'; data: { analysis_id: string; kind: AgentAnalysisKind } }
export type BillReportReadyEvent = { type: 'BILL_REPORT_READY'; data: { report_id: string; status: 'queued'; period: string } }
export type BillReportOpenedEvent = { type: 'BILL_REPORT_OPENED'; data: { report_id: string; period: string; status: 'queued' | 'running' | 'complete' | 'partial' | 'failed'; generated: boolean } }
export type SubscriptionScanCompletedEvent = {
  type: 'SUBSCRIPTION_SCAN_COMPLETED'
  data: Omit<SubscriptionScanResult, 'items'> & { timezone: 'Asia/Shanghai' }
}
export type SubscriptionCancelRequestedEvent = {
  type: 'SUBSCRIPTION_CANCEL_REQUESTED'
  data: {
    action_id: string
    status: 'WAITING_CONFIRMATION' | 'WAITING_VERIFICATION' | 'AUTHORIZED' | 'EXECUTING'
      | 'RECONCILING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'
  }
}
export type SubscriptionForecastReadyEvent = { type: 'SUBSCRIPTION_FORECAST_READY'; data: { result_id: string; from_date: string; to_date: string; complete: boolean; item_count: number } }
export type SubscriptionReminderRuleSavedEvent = { type: 'SUBSCRIPTION_REMINDER_RULE_SAVED'; data: { rule_id: string; scope: string; month: string | null; lead_days: number[]; amount_gt: string | null; reused: boolean } }
export type SubscriptionBudgetReadyEvent = { type: 'SUBSCRIPTION_BUDGET_READY'; data: { rule_id: string; month: string; amount: string; result_id: string; reused: boolean; over_budget: boolean; complete: boolean } }
export type SubscriptionClarificationEvent = { type: 'SUBSCRIPTION_CLARIFICATION_REQUIRED'; data: { clarification_id: string; question: string; options: number[] } }
export type SubscriptionRulesReadyEvent = { type: 'SUBSCRIPTION_RULES_READY'; data: { result_id: string } }
export type SubscriptionQueryRequestedEvent = { type: 'SUBSCRIPTION_QUERY_REQUESTED'; data: {
  action_id: string; query_type: 'FORECAST' | 'RULES' | 'LIST' | 'DETAIL'; summary: string
  conditions: string[]; risk_level: 'YELLOW'; status: ActionStatus; expires_at: string
} }
export type SubscriptionQueryCompletedEvent = { type: 'SUBSCRIPTION_QUERY_COMPLETED'; data: { action_id: string; result_id: string; result_kind: SubscriptionAgentResult['kind'] } }
export type SubscriptionQueryCancelledEvent = { type: 'SUBSCRIPTION_QUERY_CANCELLED'; data: { action_id: string } }
export type SubscriptionQueryFailedEvent = { type: 'SUBSCRIPTION_QUERY_FAILED'; data: { action_id: string; error_code: string } }
export type TransferActionCreatedEvent = { type: 'TRANSFER_ACTION_CREATED'; data: { action_id: string; recipient_name: string; from_account_suffix: string; amount: string; currency: 'CNY'; status: 'WAITING_CONFIRMATION' } }
export type InternalTransferActionCreatedEvent = { type: 'INTERNAL_TRANSFER_ACTION_CREATED'; data: { action_id: string; from_account_suffix: string; to_account_suffix: string; amount: string; currency: 'CNY'; status: 'WAITING_CONFIRMATION' } }
export type CardActionCreatedEvent = { type: 'CARD_ACTION_CREATED'; data: { action_id: string; operation: string; card_last4: string | null; status: 'WAITING_CONFIRMATION' } }
export type ScheduleAuthorizationCreatedEvent = { type: 'SCHEDULE_AUTHORIZATION_CREATED'; data: { action_id: string; recipient_name: string; from_account_suffix: string; amount: string; recurrence: 'once' | 'daily' | 'weekly' | 'monthly'; execute_at: string; daily_limit: string; valid_until: string; status: 'WAITING_CONFIRMATION' } }
export type AAPaymentActionCreatedEvent = { type: 'AA_PAYMENT_ACTION_CREATED'; data: { action_id: string; title: string; from_account_suffix: string; amount: string; status: 'WAITING_CONFIRMATION' } }
export type WealthRiskAssessmentRequiredEvent = { type: 'WEALTH_RISK_ASSESSMENT_REQUIRED'; data: { reason: 'recommendation' | 'subscription'; route: '/wealth/risk-assessment' } }
export type WealthActionCreatedEvent = { type: 'WEALTH_ACTION_CREATED'; data: { action_id: string; operation: 'subscription' | 'redemption'; status: ActionStatus } }
export type OrchestrationTaskCreatedEvent = {
  type: 'ORCHESTRATION_TASK_CREATED'
  data: { task_id: string; action_id: string; task_status: OrchestrationTaskStatus; authorization_status: ActionStatus; route: string }
}
export type OrchestrationTasksReadyEvent = {
  type: 'ORCHESTRATION_TASKS_READY'
  data: { items: Array<{ task_id: string; label: string; event_date: string; status: OrchestrationTaskStatus; route: string }>; has_more: boolean }
}
export type ClarificationRequiredEvent = {
  type: 'CLARIFICATION_REQUIRED'
  data: {
    kind: 'recipient' | 'account' | 'card' | 'schedule' | 'aa' | 'product' | 'holding' | 'orchestration_account'
    question: string
    options: { option_ref: string; label: string; description: string }[]
  }
}
export type AgentEvent = BalanceResultEvent | AnalysisReadyEvent | BillReportReadyEvent | BillReportOpenedEvent
  | SubscriptionScanCompletedEvent | SubscriptionCancelRequestedEvent
  | SubscriptionForecastReadyEvent | SubscriptionReminderRuleSavedEvent
  | SubscriptionBudgetReadyEvent | SubscriptionClarificationEvent | SubscriptionRulesReadyEvent
  | SubscriptionQueryRequestedEvent | SubscriptionQueryCompletedEvent
  | SubscriptionQueryCancelledEvent | SubscriptionQueryFailedEvent
  | TransferActionCreatedEvent | InternalTransferActionCreatedEvent | CardActionCreatedEvent
  | ScheduleAuthorizationCreatedEvent | AAPaymentActionCreatedEvent
  | WealthRiskAssessmentRequiredEvent | WealthActionCreatedEvent
  | OrchestrationTaskCreatedEvent | OrchestrationTasksReadyEvent | ClarificationRequiredEvent
export type AgentMessageResponse = { trace_id: string; message: string; events: AgentEvent[] }
export type AgentQueryContext = { account_id?: number; period?: string }
export type AgentRunStatus = 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'
export type AgentStoredMessage = { id: string; role: 'user' | 'assistant'; content: string; sequence: number; created_at: string }
export type AgentStreamEvent = {
  event_id: string; conversation_id: string; run_id: string; trace_id: string
  type: string; created_at: string; data: Record<string, unknown>
}
export type AgentRun = {
  id: string; conversation_id: string; trace_id: string; status: AgentRunStatus; attempts: number
  error_code: string | null; error_message: string | null; created_at: string
  started_at: string | null; completed_at: string | null; assistant_message: AgentStoredMessage | null
}
export type AgentConversationSummary = {
  id: string; title: string; status: 'ACTIVE'; created_at: string; updated_at: string
  expires_at: string; latest_run_status: AgentRunStatus | null
}
export type AgentConversationDetail = AgentConversationSummary & {
  messages: AgentStoredMessage[]; events: AgentStreamEvent[]; current_run: AgentRun | null
}
export type BillingAnomalyResponse = JsonObject[] | {
  account_id: number | null; account_ids: number[]; complete: boolean
  from_date: string; to_date: string; data_cutoff: string; items: JsonObject[]
  detection?: { status: string; mode: string; score_is_fraud_probability: boolean; capabilities?: JsonObject; partial?: boolean; provisional?: boolean }
}
export type AnomalyReviewStatus = 'verified' | 'ignored'
export type AnomalyReviewResponse = { id: string; anomaly_key: string; status: AnomalyReviewStatus }
export type AgentAnalysis = { analysis_id: string; created_at: string; expires_at: string } & (
  { kind: 'balance'; data: AccountSummaryResponse & { account_ids: number[] } } |
  { kind: 'transactions'; data: { currency: string; items: Transaction[]; transaction_count: number; complete: boolean; from_date: string | null; to_date: string | null; account_ids: number[] } } |
  { kind: 'statistics'; data: BillingStatistics } |
  { kind: 'anomalies'; data: Exclude<BillingAnomalyResponse, JsonObject[]> } |
  { kind: 'wealth_products'; data: { items: WealthProductResult[] } } |
  { kind: 'wealth_recommend'; data: { criteria: { amount: string; term_months: number; needs_liquidity: boolean }; items: WealthRecommendationResult[] } } |
  { kind: 'wealth_holdings'; data: { items: WealthHoldingResult[] } }
)
export type WealthProductResult = {
  product_id: number; name: string; currency: string
  min_deposit_amount: string; max_deposit_amount: string
  min_term: { value: number | null; unit: string }; max_term: { value: number | null; unit: string }
  annual_interest_rates: string[]; risk_level: number | null
  allows_premature: boolean; enabled: boolean
}
export type WealthRecommendationResult = {
  product: WealthProductResult; term_months: number; annual_interest_rate: string
  estimated_interest: string; estimate_only: boolean; reason: string
}
export type WealthHoldingResult = {
  holding_id: number; product_id: number; product_name: string; account_suffix: string
  principal: string; currency: string; annual_interest_rate: string
  maturity_date: string; status: string
}
export type BillingStatistics = {
  account_id: number | null; account_ids: number[]; complete: boolean
  from_date: string; to_date: string; currency: string
  totals: Record<string, string>; direction_totals: Record<string, Record<string, string>>
  categories: Record<string, string>; monthly: Record<string, Record<string, string>>
  transaction_count: number; data_cutoff: string; rule_version: string
  configuration_hash: string; snapshot_atomic: boolean
}

export function getAccessToken() { return sessionStorage.getItem(ACCESS_KEY) }
export function hasStoredSession() { return Boolean(sessionStorage.getItem(ACCESS_KEY) || sessionStorage.getItem(REFRESH_KEY)) }
export function storeTokens(tokens: Tokens) {
  sessionStorage.setItem(ACCESS_KEY, tokens.access_token)
  sessionStorage.setItem(REFRESH_KEY, tokens.refresh_token)
}
export function clearTokens() {
  sessionStorage.removeItem(ACCESS_KEY)
  sessionStorage.removeItem(REFRESH_KEY)
}

let refreshPromise: Promise<Tokens> | null = null

async function parseError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as { error?: ApiErrorBody }
    return new ApiError(response.status, payload.error)
  } catch { return new ApiError(response.status) }
}

async function fetchWithTimeout(
  input: string,
  init: RequestInit,
  timeoutMs: number,
  resultUnknownOnTimeout: boolean,
): Promise<Response> {
  const controller = new AbortController()
  const callerSignal = init.signal
  let timedOut = false
  const abortFromCaller = () => controller.abort(callerSignal?.reason)
  if (callerSignal?.aborted) abortFromCaller()
  else callerSignal?.addEventListener('abort', abortFromCaller, { once: true })
  const timeoutId = globalThis.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, Math.max(1, timeoutMs))

  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } catch (error) {
    if (timedOut) {
      throw new ApiError(0, resultUnknownOnTimeout
        ? { code: 'WRITE_RESULT_UNKNOWN', message: '请求超时，操作可能仍在处理中。请勿重复提交，请到操作记录中核对结果。', retryable: false }
        : { code: 'REQUEST_TIMEOUT', message: '请求超时，请稍后重试。', retryable: true })
    }
    if (callerSignal?.aborted) {
      throw new ApiError(0, { code: 'REQUEST_CANCELLED', message: '请求已取消', retryable: false })
    }
    if (error instanceof ApiError) throw error
    throw new ApiError(0, { code: 'NETWORK_ERROR', message: '无法连接中端，请检查服务是否启动', retryable: true })
  } finally {
    globalThis.clearTimeout(timeoutId)
    callerSignal?.removeEventListener('abort', abortFromCaller)
  }
}

async function rotateTokens(): Promise<Tokens> {
  const refreshToken = sessionStorage.getItem(REFRESH_KEY)
  if (!refreshToken) throw new ApiError(401, { code: 'UNAUTHENTICATED', message: '请重新登录' })
  const response = await fetchWithTimeout(`${API_BASE}/auth/refresh`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refreshToken }),
  }, API_QUERY_TIMEOUT_MS, false)
  if (!response.ok) throw await parseError(response)
  const tokens = (await response.json()) as Tokens
  storeTokens(tokens)
  return tokens
}

async function refreshOnce() {
  refreshPromise ??= rotateTokens().finally(() => { refreshPromise = null })
  return refreshPromise
}

type RequestOptions = RequestInit & {
  auth?: boolean
  retryAuth?: boolean
  idempotencyKey?: string
  timeoutMs?: number
  resultUnknownOnTimeout?: boolean
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { auth = true, retryAuth = true, idempotencyKey, timeoutMs, resultUnknownOnTimeout, ...init } = options
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (idempotencyKey) headers.set('Idempotency-Key', idempotencyKey)
  const access = getAccessToken()
  if (auth && access) headers.set('Authorization', `Bearer ${access}`)
  const method = (init.method ?? 'GET').toUpperCase()
  const isQuery = method === 'GET' || method === 'HEAD' || method === 'OPTIONS'
  let response: Response
  response = await fetchWithTimeout(
    `${API_BASE}${path}`,
    { ...init, headers },
    timeoutMs ?? (isQuery ? API_QUERY_TIMEOUT_MS : API_WRITE_TIMEOUT_MS),
    resultUnknownOnTimeout ?? !isQuery,
  )

  if (response.status === 401 && auth && retryAuth) {
    try {
      await refreshOnce()
      return apiRequest<T>(path, { ...options, retryAuth: false })
    } catch (error) {
      clearTokens()
      window.dispatchEvent(new Event('bank-agent-auth-lost'))
      throw error
    }
  }
  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

type AgentStreamBatch = {
  lastEventId?: string
  boundary: 'complete' | 'timeout' | 'closed'
}

async function openAgentEventStream(
  conversationId: string,
  lastEventId: string | undefined,
  onEvent: (event: AgentStreamEvent) => void,
  signal?: AbortSignal,
  retryAuth = true,
): Promise<AgentStreamBatch> {
  const headers = new Headers({ Accept: 'text/event-stream' })
  const access = getAccessToken()
  if (access) headers.set('Authorization', `Bearer ${access}`)
  if (lastEventId) headers.set('Last-Event-ID', lastEventId)
  let response: Response
  try {
    response = await fetch(`${API_BASE}/agent/conversations/${encodeURIComponent(conversationId)}/events`, { headers, signal })
  } catch {
    if (signal?.aborted) throw new ApiError(0, { code: 'REQUEST_CANCELLED', message: '请求已取消' })
    throw new ApiError(0, { code: 'NETWORK_ERROR', message: 'Agent 事件连接中断', retryable: true })
  }
  if (response.status === 401 && retryAuth) {
    try {
      await refreshOnce()
      return openAgentEventStream(conversationId, lastEventId, onEvent, signal, false)
    } catch (error) {
      clearTokens()
      window.dispatchEvent(new Event('bank-agent-auth-lost'))
      throw error
    }
  }
  if (!response.ok) throw await parseError(response)
  if (!response.body) throw new ApiError(503, { code: 'AGENT_STREAM_UNAVAILABLE', message: '浏览器无法读取 Agent 事件流', retryable: true })

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let cursor = lastEventId
  let boundary: AgentStreamBatch['boundary'] = 'closed'
  while (true) {
    let chunk: ReadableStreamReadResult<Uint8Array>
    try {
      chunk = await reader.read()
    } catch {
      if (signal?.aborted) throw new ApiError(0, { code: 'REQUEST_CANCELLED', message: '请求已取消' })
      throw new ApiError(0, { code: 'NETWORK_ERROR', message: 'Agent 事件连接中断', retryable: true })
    }
    const { value, done } = chunk
    buffer += decoder.decode(value, { stream: !done })
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      let eventType = 'message'
      let eventId: string | undefined
      const dataLines: string[] = []
      for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim()
        else if (line.startsWith('id:')) eventId = line.slice(3).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
      }
      if (eventId) cursor = eventId
      if (eventType === 'stream.complete') boundary = 'complete'
      else if (eventType === 'stream.timeout') boundary = 'timeout'
      else if (dataLines.length) {
        const parsed = JSON.parse(dataLines.join('\n')) as AgentStreamEvent
        onEvent(parsed)
      }
    }
    if (done) break
  }
  return { lastEventId: cursor, boundary }
}

const agentDomainEventTypes = new Set([
  'BALANCE_RESULT', 'ANALYSIS_READY', 'BILL_REPORT_READY', 'BILL_REPORT_OPENED',
  'SUBSCRIPTION_SCAN_COMPLETED', 'SUBSCRIPTION_CANCEL_REQUESTED',
  'SUBSCRIPTION_FORECAST_READY', 'SUBSCRIPTION_REMINDER_RULE_SAVED',
  'SUBSCRIPTION_BUDGET_READY', 'SUBSCRIPTION_CLARIFICATION_REQUIRED',
  'SUBSCRIPTION_RULES_READY', 'SUBSCRIPTION_QUERY_REQUESTED',
  'SUBSCRIPTION_QUERY_COMPLETED', 'SUBSCRIPTION_QUERY_CANCELLED',
  'SUBSCRIPTION_QUERY_FAILED', 'TRANSFER_ACTION_CREATED',
  'INTERNAL_TRANSFER_ACTION_CREATED', 'CARD_ACTION_CREATED',
  'SCHEDULE_AUTHORIZATION_CREATED', 'AA_PAYMENT_ACTION_CREATED', 'CLARIFICATION_REQUIRED',
  'WEALTH_RISK_ASSESSMENT_REQUIRED', 'WEALTH_ACTION_CREATED',
  'ORCHESTRATION_TASK_CREATED', 'ORCHESTRATION_TASKS_READY',
])

async function awaitAgentRun(
  conversationId: string,
  run: AgentRun,
  signal?: AbortSignal,
): Promise<AgentMessageResponse> {
  const started = Date.now()
  let cursor: string | undefined
  let text = ''
  const events: AgentEvent[] = []
  const seenEvents = new Set<string>()
  let reconnectAttempts = 0
  while (Date.now() - started < API_AGENT_TIMEOUT_MS) {
    let batch: AgentStreamBatch
    try {
      batch = await openAgentEventStream(conversationId, cursor, (event) => {
        // The durable stream replays the whole conversation. Advance through it,
        // but only collect the text and cards produced by this Run.
        cursor = event.event_id || cursor
        if (event.event_id) {
          if (seenEvents.has(event.event_id)) return
          seenEvents.add(event.event_id)
        }
        if (event.conversation_id !== conversationId || event.run_id !== run.id) return
        if (event.type === 'TEXT_COMPLETE') text = String(event.data.text ?? '')
        if (agentDomainEventTypes.has(event.type)) {
          events.push({ type: event.type, data: event.data } as AgentEvent)
        }
      }, signal)
      cursor = batch.lastEventId ?? cursor
      reconnectAttempts = 0
    } catch (error) {
      if (!(error instanceof ApiError) || error.code !== 'NETWORK_ERROR' || !error.retryable || signal?.aborted) throw error
      const backoff = Math.min(250 * (2 ** reconnectAttempts), 2_000)
      reconnectAttempts += 1
      await new Promise<void>((resolve, reject) => {
        const onAbort = () => {
          window.clearTimeout(timer)
          reject(new ApiError(0, { code: 'REQUEST_CANCELLED', message: '请求已取消' }))
        }
        const timer = window.setTimeout(() => {
          signal?.removeEventListener('abort', onAbort)
          resolve()
        }, backoff)
        signal?.addEventListener('abort', onAbort, { once: true })
      })
      continue
    }
    const current = await apiRequest<AgentRun>(`/agent/runs/${encodeURIComponent(run.id)}`)
    if (current.status === 'SUCCEEDED') {
      const message = text || current.assistant_message?.content
      if (!message) throw new ApiError(502, { code: 'AGENT_NO_RESPONSE', message: 'Agent 未生成可用回复' })
      return { trace_id: current.trace_id, message, events }
    }
    if (current.status === 'FAILED' || current.status === 'CANCELLED') {
      throw new ApiError(503, {
        code: current.error_code ?? `AGENT_${current.status}`,
        message: current.error_message ?? (current.status === 'CANCELLED' ? 'Agent 请求已取消' : 'Agent 请求失败'),
        retryable: false,
      })
    }
  }
  throw new ApiError(0, { code: 'WRITE_RESULT_UNKNOWN', message: 'Agent 请求仍在处理中。请勿重复提交，稍后恢复会话查看结果。', retryable: false })
}

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false
  return !(error instanceof ApiError) || error.retryable
}

function qs(values: Record<string, string | number | boolean | undefined | null>) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== '') params.set(key, String(value)) })
  const value = params.toString()
  return value ? `?${value}` : ''
}

export const api = {
  health: () => apiRequest<HealthResponse>('/health', { auth: false }),
  login: (username: string, password: string) => apiRequest<Tokens>('/auth/login', { method: 'POST', auth: false, body: JSON.stringify({ username, password }), resultUnknownOnTimeout: false }),
  logout: () => apiRequest<{ status: string }>('/auth/logout', { method: 'POST' }),
  me: () => apiRequest<CurrentUser>('/me'),
  sendAgentMessage: (message: string, query_context?: AgentQueryContext, history: string[] = [], continuation_ref?: string) => apiRequest<AgentMessageResponse>('/agent/messages', { method: 'POST', body: JSON.stringify({ message, history, query_context, continuation_ref }), timeoutMs: API_AGENT_TIMEOUT_MS, resultUnknownOnTimeout: true }),
  agentConversations: () => apiRequest<AgentConversationSummary[]>('/agent/conversations'),
  createAgentConversation: (title = '新对话') => apiRequest<AgentConversationSummary>('/agent/conversations', { method: 'POST', body: JSON.stringify({ title }) }),
  agentConversation: (id: string) => apiRequest<AgentConversationDetail>(`/agent/conversations/${encodeURIComponent(id)}`),
  deleteAgentConversation: (id: string) => apiRequest<void>(`/agent/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  enqueueAgentMessage: (id: string, message: string, query_context?: AgentQueryContext, continuation_ref?: string, option_ref?: string, idempotencyKey = crypto.randomUUID()) => apiRequest<AgentRun>(`/agent/conversations/${encodeURIComponent(id)}/messages`, { method: 'POST', idempotencyKey, body: JSON.stringify({ message, query_context, continuation_ref, option_ref }), resultUnknownOnTimeout: true }),
  agentRun: (id: string) => apiRequest<AgentRun>(`/agent/runs/${encodeURIComponent(id)}`),
  resumeAgentRun: (conversationId: string, run: AgentRun, signal?: AbortSignal) => awaitAgentRun(conversationId, run, signal),
  sendConversationAgentMessage: async (conversationId: string, message: string, query_context?: AgentQueryContext, continuation_ref?: string, option_ref?: string, signal?: AbortSignal) => {
    const key = crypto.randomUUID()
    const run = await apiRequest<AgentRun>(`/agent/conversations/${encodeURIComponent(conversationId)}/messages`, { method: 'POST', idempotencyKey: key, body: JSON.stringify({ message, query_context, continuation_ref, option_ref }), resultUnknownOnTimeout: true, signal })
    return awaitAgentRun(conversationId, run, signal)
  },
  agentAnalysis: (id: string) => apiRequest<AgentAnalysis>(`/agent/analyses/${encodeURIComponent(id)}`),
  accounts: () => apiRequest<AccountSummary[]>('/accounts'),
  accountSummary: () => apiRequest<AccountSummaryResponse>('/accounts/summary'),
  account: (id: number) => apiRequest<AccountDetail>(`/accounts/${id}`),
  balance: (id: number) => apiRequest<BalanceResponse>(`/accounts/${id}/balance`),
  transactions: (id: number, filters: Record<string, string | number | undefined>) => apiRequest<TransactionPage>(`/accounts/${id}/transactions${qs(filters)}`),
  transaction: (accountId: number, transactionId: number) => apiRequest<Transaction>(`/accounts/${accountId}/transactions/${transactionId}`),
  recipients: (field?: string, query?: string) => apiRequest<Recipient[]>(`/recipients${qs({ field, query })}`),
  saveRecipient: (body: Omit<Recipient, 'id' | 'participant_user_id'>, id?: string) => apiRequest<Recipient>(id ? `/recipients/${id}` : '/recipients', { method: id ? 'PUT' : 'POST', body: JSON.stringify(body) }),
  deleteRecipient: (id: string) => apiRequest<{ deleted: boolean }>(`/recipients/${id}`, { method: 'DELETE' }),
  transfers: () => apiRequest<BankingAction[]>('/transfers'),
  createTransfer: (body: JsonObject, key: string) => apiRequest<BankingAction>('/transfers', { method: 'POST', body: JSON.stringify(body), idempotencyKey: key }),
  createInternalTransfer: (body: JsonObject, key: string) => apiRequest<BankingAction>('/internal-transfers', { method: 'POST', body: JSON.stringify(body), idempotencyKey: key }),
  actions: () => apiRequest<BankingAction[]>('/actions'),
  action: (id: string) => apiRequest<BankingAction>(`/actions/${id}`),
  confirmAction: (id: string, requestHash: string) => apiRequest<BankingAction>(`/actions/${id}/confirm`, { method: 'POST', body: JSON.stringify({ request_hash: requestHash }) }),
  sendOtp: (id: string) => apiRequest<{ expires_in: number; delivery: string }>(`/actions/${id}/otp`, { method: 'POST' }),
  verifyAction: (id: string, code: string) => apiRequest<BankingAction>(`/actions/${id}/verify`, { method: 'POST', body: JSON.stringify({ code }) }),
  cancelAction: (id: string) => apiRequest<BankingAction>(`/actions/${id}/cancel`, { method: 'POST' }),
  reconcileAction: (id: string) => apiRequest<BankingAction>(`/actions/${id}/reconcile`, { method: 'POST' }),
  resumeAction: (id: string) => apiRequest<BankingAction>(`/actions/${id}/resume`, { method: 'POST' }),
  actionAudit: (id: string) => apiRequest<ActionAuditEntry[]>(`/actions/${id}/audit`),
  devOtp: (id: string) => apiRequest<{ code: string; expires_at: string }>(`/dev/otp-inbox/${id}`),
  schedules: () => apiRequest<JsonObject[]>('/transfer-schedules'),
  createSchedule: (body: JsonObject) => apiRequest<JsonObject>('/transfer-schedules', { method: 'POST', body: JSON.stringify(body) }),
  scheduleCommand: (id: string, command: 'authorize' | 'pause' | 'resume', key?: string) => apiRequest<JsonObject>(`/transfer-schedules/${id}/${command}`, { method: 'POST', idempotencyKey: key }),
  cancelSchedule: (id: string) => apiRequest<JsonObject>(`/transfer-schedules/${id}`, { method: 'DELETE' }),
  aaCollections: () => apiRequest<JsonObject[]>('/aa-collections'),
  createAa: (body: JsonObject) => apiRequest<JsonObject>('/aa-collections', { method: 'POST', body: JSON.stringify(body) }),
  categories: () => apiRequest<Category[]>('/categories'),
  createCategory: (name: string) => apiRequest<Category>('/categories', { method: 'POST', body: JSON.stringify({ name }) }),
  updateCategory: (id: string, name: string) => apiRequest<Category>(`/categories/${id}`, { method: 'PUT', body: JSON.stringify({ name }) }),
  deleteCategory: (id: string) => apiRequest<{ deleted: boolean }>(`/categories/${id}`, { method: 'DELETE' }),
  classificationRules: () => apiRequest<ClassificationRule[]>('/classification-rules'),
  createClassificationRule: (body: Omit<ClassificationRule, 'id' | 'user_id'>) => apiRequest<ClassificationRule>('/classification-rules', { method: 'POST', body: JSON.stringify(body) }),
  updateClassificationRule: (id: string, body: Omit<ClassificationRule, 'id' | 'user_id'>) => apiRequest<ClassificationRule>(`/classification-rules/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteClassificationRule: (id: string) => apiRequest<{ deleted: boolean }>(`/classification-rules/${id}`, { method: 'DELETE' }),
  transactionAnnotations: (accountId?: number, transactionId?: number) => apiRequest<TransactionAnnotation[]>(`/transaction-annotations${qs({ account_id: accountId, transaction_id: transactionId })}`),
  saveTransactionAnnotation: (body: Omit<TransactionAnnotation, 'id' | 'user_id'>) => apiRequest<TransactionAnnotation>('/transaction-annotations', { method: 'POST', body: JSON.stringify(body) }),
  updateTransactionAnnotation: (id: string, body: Omit<TransactionAnnotation, 'id' | 'user_id'>) => apiRequest<TransactionAnnotation>(`/transaction-annotations/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteTransactionAnnotation: (id: string) => apiRequest<{ deleted: boolean }>(`/transaction-annotations/${id}`, { method: 'DELETE' }),
  billingStatistics: (accountId: number | undefined, fromDate: string, toDate: string) => apiRequest<BillingStatistics>(`/billing/statistics${qs({ account_id: accountId, from_date: fromDate, to_date: toDate })}`),
  billingAnomalies: (accountId: number | undefined, fromDate: string, toDate: string) => apiRequest<BillingAnomalyResponse>(`/billing/anomalies${qs({ account_id: accountId, from_date: fromDate, to_date: toDate, include_metadata: true })}`),
  reviewAnomaly: (anomalyKey: string, status: AnomalyReviewStatus) => apiRequest<AnomalyReviewResponse>('/billing/anomaly-reviews', { method: 'POST', body: JSON.stringify({ anomaly_key: anomalyKey, status }) }),
  reports: () => apiRequest<JsonObject[]>('/bill-reports'),
  createReport: (accountId: number, period: string) => apiRequest<JsonObject>('/bill-reports', { method: 'POST', body: JSON.stringify({ account_id: accountId, period }) }),
  generateBillReport: (accountId: number | null, period: string, key: string) => apiRequest<{ report_id: string; status: string; period: string }>('/bill-report-generations', { method: 'POST', body: JSON.stringify({ account_id: accountId, period }), idempotencyKey: key, timeoutMs: 15_000 }),
  billReportStatus: (id: string) => apiRequest<{ report_id: string; status: string; progress: number; period: string; error?: string }>(`/bill-report-generations/${id}/status`),
  billReportSummaries: (filters: { period?: string; period_from?: string; period_to?: string; status?: string; account_id?: number; page?: number } = {}) => apiRequest<{ items: JsonObject[]; total: number; page: number; page_size: number }>(`/bill-report-summaries${qs({ ...filters, page: filters.page ?? 1, page_size: 20 })}`),
  billReport: (id: string) => apiRequest<JsonObject>(`/bill-reports/${id}`),
  billReportTransactions: (id: string, page = 1, pageSize = 50, filters: { direction?: string; category?: string; from_date?: string; to_date?: string } = {}) => apiRequest<{ items: JsonObject[]; total: number; page: number; page_size: number }>(`/bill-reports/${id}/transactions${qs({ page, page_size: pageSize, ...filters })}`),
  deleteBillReport: (id: string) => apiRequest<{ deleted: boolean }>(`/bill-reports/${id}`, { method: 'DELETE' }),
  questionnaire: () => apiRequest<JsonObject>('/risk-assessments/questionnaire'),
  assessments: () => apiRequest<JsonObject[]>('/risk-assessments'),
  assess: (answers: number[]) => apiRequest<JsonObject>('/risk-assessments', { method: 'POST', body: JSON.stringify({ answers }) }),
  products: () => apiRequest<JsonObject[]>('/investments/products'),
  compareProducts: (ids: number[]) => apiRequest<JsonObject[]>(`/investments/products/compare?${ids.map((id) => `ids=${encodeURIComponent(id)}`).join('&')}`),
  recommendations: (amount: string, termMonths: number, needsLiquidity: boolean) => apiRequest<JsonObject[]>(`/investments/recommendations${qs({ amount, term_months: termMonths, needs_liquidity: needsLiquidity })}`),
  holdings: () => apiRequest<JsonObject[]>('/investments/holdings'),
  subscribe: (body: JsonObject, key: string) => apiRequest<BankingAction>('/investments/subscriptions', { method: 'POST', body: JSON.stringify(body), idempotencyKey: key }),
  redemptionQuote: (holdingId: number, accountId: number) => apiRequest<JsonObject>(`/investments/redemption-quotes${qs({ holding_id: holdingId, to_account_id: accountId })}`),
  redeem: (body: JsonObject, key: string) => apiRequest<BankingAction>('/investments/redemptions', { method: 'POST', body: JSON.stringify(body), idempotencyKey: key }),
  cards: () => apiRequest<Card[]>('/cards'),
  card: (id: string) => apiRequest<Card>(`/cards/${id}`),
  createCard: (body: JsonObject, key: string) => apiRequest<BankingAction>('/cards', { method: 'POST', body: JSON.stringify(body), idempotencyKey: key }),
  renameCard: (id: string, alias: string) => apiRequest<Card>(`/cards/${id}`, { method: 'PATCH', body: JSON.stringify({ alias }) }),
  cardCommand: (id: string, command: 'activate' | 'reveal' | 'limits' | 'lock' | 'unlock' | 'report-lost' | 'replace', body: JsonObject, key: string) => apiRequest<BankingAction>(`/cards/${id}/${command}`, { method: 'POST', body: JSON.stringify(body), idempotencyKey: key }),
  revealCardNumber: (id: string, actionId: string) => apiRequest<CardNumberReveal>(`/cards/${id}/reveal?action_id=${encodeURIComponent(actionId)}`),
  demoMerchants: () => apiRequest<DemoMerchant[]>('/demo/merchants'),
  createDemoCardTransaction: (body: JsonObject, key: string) => apiRequest<BankingAction>('/demo/card-transactions', { method: 'POST', body: JSON.stringify(body), idempotencyKey: key }),
  cardTransactions: (id: string) => apiRequest<CardAuthorization[]>(`/cards/${id}/transactions`),
  subscriptions: () => apiRequest<Subscription[]>('/subscriptions'),
  subscription: (id: string) => apiRequest<Subscription>(`/subscriptions/${id}`),
  scanSubscriptions: () => apiRequest<SubscriptionScanResult>('/subscriptions/scan', { method: 'POST' }),
  subscriptionRenewals: (days = 3) => apiRequest<SubscriptionRenewals>(`/subscriptions/renewals?days=${days}`),
  subscriptionForecast: (params: { month?: string; from_date?: string; to_date?: string } = {}) => apiRequest<SubscriptionForecast>(`/subscriptions/forecast${qs(params)}`),
  subscriptionAgentResult: (id: string) => apiRequest<SubscriptionAgentResult>(`/agent/subscription-results/${encodeURIComponent(id)}`),
  subscriptionReminderRules: () => apiRequest<SubscriptionReminderRule[]>('/subscriptions/reminder-rules'),
  subscriptionReminderRule: (id: string) => apiRequest<SubscriptionReminderRule>(`/subscriptions/reminder-rules/${encodeURIComponent(id)}`),
  createSubscriptionReminderRule: (body: JsonObject, key: string) => apiRequest<SubscriptionReminderRule & { reused: boolean }>('/subscriptions/reminder-rules', { method: 'POST', body: JSON.stringify(body), idempotencyKey: key }),
  updateSubscriptionReminderRule: (id: string, body: JsonObject, key: string) => apiRequest<SubscriptionReminderRule & { replayed: boolean }>(`/subscriptions/reminder-rules/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(body), idempotencyKey: key }),
  subscriptionReminderCommand: (id: string, command: 'pause' | 'resume' | 'delete', key: string) => apiRequest<SubscriptionReminderRule>(`/subscriptions/reminder-rules/${encodeURIComponent(id)}/${command}`, { method: 'POST', idempotencyKey: key }),
  subscriptionBudgetRules: () => apiRequest<SubscriptionBudgetRule[]>('/subscriptions/budget-rules'),
  subscriptionBudgetRule: (id: string) => apiRequest<SubscriptionBudgetRule>(`/subscriptions/budget-rules/${encodeURIComponent(id)}`),
  saveSubscriptionBudget: (month: string, amount: string, key: string) => apiRequest<{ rule: SubscriptionBudgetRule; reused: boolean; evaluation: JsonObject }>('/subscriptions/budget-rules', { method: 'POST', body: JSON.stringify({ month, amount }), idempotencyKey: key }),
  updateSubscriptionBudget: (id: string, month: string, amount: string, key: string) => apiRequest<{ rule: SubscriptionBudgetRule; replayed: boolean; evaluation: JsonObject }>(`/subscriptions/budget-rules/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify({ month, amount }), idempotencyKey: key }),
  subscriptionBudgetCommand: (id: string, command: 'pause' | 'resume' | 'delete', key: string) => apiRequest<SubscriptionBudgetRule>(`/subscriptions/budget-rules/${encodeURIComponent(id)}/${command}`, { method: 'POST', idempotencyKey: key }),
  notifications: (unread_only = false) => apiRequest<SubscriptionNotification[]>(`/notifications${qs({ unread_only })}`),
  unreadNotificationCount: () => apiRequest<{ count: number }>('/notifications/unread-count'),
  markNotificationRead: (id: string) => apiRequest<{ id: string; read: boolean }>(`/notifications/${encodeURIComponent(id)}/read`, { method: 'POST' }),
  subscriptionCommand: (id: string, command: 'verify' | 'ignore' | 'cancel', key: string) => apiRequest<Subscription | BankingAction>(`/subscriptions/${id}/${command}`, { method: 'POST', idempotencyKey: key }),
  demoSubscriptionCharge: (id: string, key: string) => apiRequest<JsonObject>(`/demo/subscriptions/${id}/charge`, { method: 'POST', idempotencyKey: key }),
  personalEvents: () => apiRequest<PersonalEvent[]>('/personal-events'),
  createPersonalEvent: (body: { label: string; event_date: string }, key: string) => apiRequest<PersonalEvent>('/personal-events', { method: 'POST', body: JSON.stringify(body), idempotencyKey: key }),
  tasks: () => apiRequest<OrchestrationTask[]>('/tasks'),
  createBirthdayTask: (body: { label: string; event_date: string; from_account_id: number; flower_amount: string; cake_amount: string; currency?: 'CNY' }, key: string) => apiRequest<OrchestrationTask>('/tasks/birthday', { method: 'POST', body: JSON.stringify(body), idempotencyKey: key }),
  task: (id: string) => apiRequest<OrchestrationTask>(`/tasks/${id}`),
  taskCommand: (id: string, command: 'pause' | 'resume' | 'cancel' | 'takeover', key: string) => apiRequest<OrchestrationTask>(`/tasks/${id}/${command}`, { method: 'POST', idempotencyKey: key }),
  retryTaskNode: (taskId: string, nodeId: string, key: string) => apiRequest<OrchestrationTask>(`/tasks/${encodeURIComponent(taskId)}/nodes/${encodeURIComponent(nodeId)}/retry`, { method: 'POST', idempotencyKey: key }),
  reconcileTaskNode: (taskId: string, nodeId: string, key: string) => apiRequest<OrchestrationTask>(`/tasks/${encodeURIComponent(taskId)}/nodes/${encodeURIComponent(nodeId)}/reconcile`, { method: 'POST', idempotencyKey: key }),
}

export const fetchHealth = api.health
export const fetchBalance = api.balance
