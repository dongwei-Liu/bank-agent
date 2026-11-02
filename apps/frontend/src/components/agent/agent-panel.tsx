import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, ExternalLink, LoaderCircle, Plus, RefreshCw, Send, Trash2, WalletCards, X } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError, type AgentConversationDetail, type AgentEvent, type AgentQueryContext, type BankingAction, type Subscription, type SubscriptionAgentResult } from '@/lib/api'
import { ErrorState, LoadingState } from '@/components/page-state'
import { anomalyEvidenceText, anomalyTitle, anomalyStatusLabel, EMPTY_ANOMALIES_TEXT } from '@/lib/evidence'
import { billPresentation, formatMoney } from '@/lib/format'
import { AnomalyReviewControls } from '@/components/anomaly-review-controls'

const destinations = [
  ['账户', '/accounts'], ['转账', '/payments/new'], ['账单洞察', '/insights'],
  ['定存与财富', '/wealth'],
]

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  text: string
  events?: AgentEvent[]
}

const welcome: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  text: '你好，我可以查询本人余额和流水、发起转账、管理借记卡、定时转账和 AA 收款。需要授权的操作请在确认页继续。',
}

const durableControlEvents = new Set([
  'EXECUTING', 'TEXT_DELTA', 'TEXT_COMPLETE', 'SUCCESS', 'ERROR', 'CANCELLED',
  'SUBSCRIPTION_QUERY_COMPLETED', 'SUBSCRIPTION_QUERY_CANCELLED', 'SUBSCRIPTION_QUERY_FAILED',
])

function restoredMessages(conversation?: AgentConversationDetail): ChatMessage[] {
  if (!conversation) return []
  const messages = conversation.messages ?? []
  const events = conversation.events ?? []
  return messages.map((message) => {
    if (message.role === 'user') return { id: message.id, role: message.role, text: message.content }
    const completion = events.find((event) => event.type === 'TEXT_COMPLETE' && event.data.message_id === message.id)
    const messageEvents = completion
      ? events
          .filter((event) => event.run_id === completion.run_id && !durableControlEvents.has(event.type))
          .map((event) => ({ type: event.type, data: event.data }) as AgentEvent)
      : []
    return { id: message.id, role: message.role, text: message.content, events: messageEvents }
  })
}

function currentMonth() {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' }).formatToParts(new Date())
  const year = Number(parts.find((part) => part.type === 'year')?.value)
  const month = Number(parts.find((part) => part.type === 'month')?.value)
  return `${year}-${String(month).padStart(2, '0')}`
}

function compareMoneyDescending(left: string, right: string) {
  function scaledParts(value: string) {
    const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(value.trim())
    if (!match) return null
    return { negative: match[1] === '-', whole: match[2], fraction: match[3] ?? '' }
  }
  const a = scaledParts(left)
  const b = scaledParts(right)
  if (!a || !b) return right.localeCompare(left)
  const scale = Math.max(a.fraction.length, b.fraction.length)
  const toInteger = (part: NonNullable<typeof a>) => {
    const magnitude = BigInt(`${part.whole}${part.fraction.padEnd(scale, '0')}`)
    return part.negative ? -magnitude : magnitude
  }
  const leftValue = toInteger(a)
  const rightValue = toInteger(b)
  return leftValue > rightValue ? -1 : leftValue < rightValue ? 1 : 0
}

function termText(term: { value: number | null; unit: string }) {
  if (term.value == null) return '未限定'
  const labels: Record<string, string> = { days: '天', weeks: '周', months: '个月', years: '年' }
  return `${term.value}${labels[term.unit] ?? term.unit}`
}

function EventCard({ event, onNavigate, onClarify, onSelectOption, onOpenAction }: {
  event: AgentEvent
  onNavigate: () => void
  onClarify: (ref: string, days: number) => void
  onSelectOption: (ref: string, label: string) => void
  onOpenAction: (id: string) => void
}) {
  if (event.type === 'ANALYSIS_READY') return <AnalysisCard id={event.data.analysis_id} />
  if (event.type === 'BILL_REPORT_READY') return <BillReportStatusCard
    reportId={event.data.report_id} period={event.data.period} initialStatus="queued" generated onNavigate={onNavigate}
  />
  if (event.type === 'BILL_REPORT_OPENED') return <BillReportStatusCard
    reportId={event.data.report_id} period={event.data.period} initialStatus={event.data.status} generated={event.data.generated} onNavigate={onNavigate}
  />
  if (event.type === 'SUBSCRIPTION_SCAN_COMPLETED') {
    const data = event.data
    return <section aria-label="订阅识别结果" className="mt-2 min-w-0 space-y-2 break-words rounded-lg border border-brand-200 bg-white p-3 text-slate-900">
      <p className="font-medium">订阅扣费识别完成</p>
      <p className="text-xs text-slate-500">{data.from_date} 至 {data.to_date} · 本人全部合格账户</p>
      <p className="text-xs text-slate-500">扫描时间：{new Date(data.scanned_at).toLocaleString('zh-CN', { timeZone: data.timezone })}（上海时间）</p>
      <p>本次规则匹配 {data.matched_candidates} 项</p>
      <p>新增 {data.created} 项，更新 {data.updated} 项</p>
      <p>全部已保存记录 {data.found} 项</p>
      {data.matched_candidates === 0 && <p className="text-xs text-slate-500">本次没有匹配到满足当前规则的扣费模式，不代表没有订阅。</p>}
      <p className="text-xs text-slate-500">本次匹配可能包含已有记录；新候选仍需人工核实。</p>
      <Link to="/subscriptions" onClick={onNavigate} className="inline-block text-sm text-brand-700 underline">查看订阅候选与扣费证据</Link>
    </section>
  }
  if (event.type === 'SUBSCRIPTION_CANCEL_REQUESTED') {
    const waitingForConfirmation = event.data.status === 'WAITING_CONFIRMATION'
    const statusLabel: Record<typeof event.data.status, string> = {
      WAITING_CONFIRMATION: '等待你确认',
      WAITING_VERIFICATION: '等待安全验证',
      AUTHORIZED: '已授权',
      EXECUTING: '处理中',
      RECONCILING: '正在核对结果',
      SUCCEEDED: '已完成',
      FAILED: '执行失败',
      CANCELLED: '已取消或过期',
    }
    return <section aria-label="订阅取消请求" className="mt-2 min-w-0 space-y-2 break-words rounded-lg border border-amber-200 bg-white p-3 text-slate-900">
      <p className="font-medium">订阅取消请求 · {statusLabel[event.data.status]}</p>
      <p className="text-xs text-slate-600">{waitingForConfirmation
        ? '请求尚未执行。请在操作页核对商户、金额和周期，再由你点击确认。'
        : '操作页会从中端重新读取请求详情和当前状态。'}</p>
      <Link to={`/actions/${encodeURIComponent(event.data.action_id)}`} onClick={onNavigate} className="inline-block text-sm text-brand-700 underline">
        {waitingForConfirmation ? '核对并确认取消' : '查看取消请求'}
      </Link>
    </section>
  }
  if (event.type === 'SUBSCRIPTION_FORECAST_READY') return <SubscriptionResultCard resultId={event.data.result_id} onNavigate={onNavigate} />
  if (event.type === 'SUBSCRIPTION_BUDGET_READY') return <SubscriptionResultCard resultId={event.data.result_id} onNavigate={onNavigate} />
  if (event.type === 'SUBSCRIPTION_RULES_READY') return <SubscriptionResultCard resultId={event.data.result_id} onNavigate={onNavigate} />
  if (event.type === 'SUBSCRIPTION_QUERY_REQUESTED') return <SubscriptionQueryCard event={event} onNavigate={onNavigate} />
  if (event.type === 'SUBSCRIPTION_QUERY_COMPLETED' || event.type === 'SUBSCRIPTION_QUERY_CANCELLED' || event.type === 'SUBSCRIPTION_QUERY_FAILED') return null
  if (event.type === 'SUBSCRIPTION_REMINDER_RULE_SAVED') return <section aria-label="提醒规则已保存" className="mt-2 space-y-2 rounded-lg border border-teal-200 bg-white p-3 text-slate-900">
    <p className="font-medium">续费提醒规则已保存</p>
    <p className="text-sm">{event.data.month ? `适用于${event.data.month}` : '持续生效'} · 提前{event.data.lead_days.join('、')}天 · {event.data.scope === 'AMOUNT_GT' ? `金额严格大于${event.data.amount_gt}元` : event.data.scope === 'SUBSCRIPTION' ? '指定订阅' : '全部已核实订阅'}</p>
    {event.data.reused && <p className="text-xs text-slate-500">已复用相同的有效规则。</p>}
    <Link to="/subscriptions#reminder-rules" onClick={onNavigate} className="inline-block text-sm text-brand-700 underline">管理提醒规则</Link>
  </section>
  if (event.type === 'SUBSCRIPTION_CLARIFICATION_REQUIRED') return <section aria-label="提醒时间补充" className="mt-2 space-y-2 rounded-lg border border-amber-200 bg-white p-3 text-slate-900">
    <p className="font-medium">还需要确认提醒时间</p><p className="text-sm">{event.data.question}</p>
    <div className="flex flex-wrap gap-2">{event.data.options.map((day) => <button key={day} type="button" onClick={() => onClarify(event.data.clarification_id, day)} className="rounded-md border border-brand-300 px-3 py-1.5 text-sm text-brand-700">提前{day}天</button>)}</div>
  </section>
  if (event.type === 'WEALTH_RISK_ASSESSMENT_REQUIRED') return <section aria-label="需要风险测评" className="mt-2 space-y-2 rounded-lg border border-amber-200 bg-white p-3 text-slate-900">
    <p className="font-medium">需要你本人完成本次风险测评</p>
    <p className="text-sm">五题答案只能由你在结构化页面填写；本次测评有效 15 分钟，申购一次后即失效。</p>
    <Link to={event.data.route} onClick={onNavigate} className="inline-block text-sm text-brand-700 underline">开始本次五题测评</Link>
  </section>
  if (event.type === 'CLARIFICATION_REQUIRED') return <section aria-label="需要补充选择" className="mt-2 space-y-2 rounded-lg border border-amber-200 bg-white p-3 text-slate-900">
    <p className="font-medium">还需要你选择</p><p className="text-sm">{event.data.question}</p>
    <div className="grid gap-2">{event.data.options.map((option) => <button key={option.option_ref} type="button" onClick={() => onSelectOption(option.option_ref, option.label)} className="rounded-md border border-brand-300 px-3 py-2 text-left text-sm text-brand-700"><span className="font-medium">{option.label}</span>{option.description && <span className="ml-2 text-xs text-slate-500">{option.description}</span>}</button>)}</div>
  </section>
  if (event.type === 'TRANSFER_ACTION_CREATED') return <ActionEventCard title="等待确认的转账请求" lines={[`收款人：${event.data.recipient_name}`, `付款账户：尾号 ${event.data.from_account_suffix}`, `${event.data.currency} ${event.data.amount}`]} actionId={event.data.action_id} label="查看并确认" onOpen={onOpenAction} />
  if (event.type === 'INTERNAL_TRANSFER_ACTION_CREATED') return <ActionEventCard title="等待确认的本人账户互转" lines={[`转出账户：尾号 ${event.data.from_account_suffix}`, `转入账户：尾号 ${event.data.to_account_suffix}`, `${event.data.currency} ${event.data.amount}`]} actionId={event.data.action_id} label="查看并确认" onOpen={onOpenAction} />
  if (event.type === 'CARD_ACTION_CREATED') return <ActionEventCard title="待处理的卡片请求" lines={[`${event.data.operation}${event.data.card_last4 ? ` · 卡片尾号 ${event.data.card_last4}` : ''}`]} actionId={event.data.action_id} label="打开确认与验证页面" onOpen={onOpenAction} />
  if (event.type === 'SCHEDULE_AUTHORIZATION_CREATED') return <ActionEventCard title="待授权的定时转账" lines={[`收款人：${event.data.recipient_name} · 账户尾号 ${event.data.from_account_suffix}`, `${event.data.recurrence} · 首次执行 ${event.data.execute_at}`, `CNY ${event.data.amount} · 每日上限 ${event.data.daily_limit}`]} actionId={event.data.action_id} label="确认并授权" onOpen={onOpenAction} />
  if (event.type === 'AA_PAYMENT_ACTION_CREATED') return <ActionEventCard title="待确认的 AA 份额付款" lines={[`${event.data.title} · 账户尾号 ${event.data.from_account_suffix}`, `CNY ${event.data.amount}`]} actionId={event.data.action_id} label="查看并确认付款" onOpen={onOpenAction} />
  if (event.type === 'WEALTH_ACTION_CREATED') return <ActionEventCard
    title={event.data.operation === 'subscription' ? '定存申购安全请求' : '定存赎回安全请求'}
    lines={[event.data.status === 'WAITING_CONFIRMATION' ? '资金尚未变更，需要核对、确认并完成 OTP。' : `当前状态：${event.data.status}`]}
    actionId={event.data.action_id}
    label="打开确认与验证页面"
    onOpen={onOpenAction}
  />
  if (event.type === 'ORCHESTRATION_TASK_CREATED') {
    const taskStatus: Record<typeof event.data.task_status, string> = {
      WAITING_AUTHORIZATION: '等待完整计划授权', ACTIVE: '计划已启用', PAUSED: '已暂停',
      CANCELLING: '正在安全取消', WAITING_USER: '等待人工处理', PARTIAL: '部分完成',
      SUCCEEDED: '已完成', FAILED: '执行失败', CANCELLED: '已取消',
    }
    return <section aria-label="生日任务已创建" className="mt-2 space-y-2 rounded-lg border border-amber-200 bg-white p-3 text-slate-900">
      <p className="font-medium">生日鲜花与蛋糕任务 · {taskStatus[event.data.task_status]}</p>
      <p className="text-xs text-slate-600">当前只保存了固定计划和 RED 授权请求，资金尚未冻结或转出。请先核对任务，再完成确认与 OTP。</p>
      <div className="flex flex-wrap gap-3 text-sm">
        <Link to={event.data.route} onClick={onNavigate} className="text-brand-700 underline">核对完整任务</Link>
        <button type="button" onClick={() => onOpenAction(event.data.action_id)} className="text-brand-700 underline">打开确认与验证</button>
      </div>
    </section>
  }
  if (event.type === 'ORCHESTRATION_TASKS_READY') return <section aria-label="生日任务查询结果" className="mt-2 space-y-2 rounded-lg border border-brand-200 bg-white p-3 text-slate-900">
    <p className="font-medium">我的生日任务</p>
    {!event.data.items.length && <p className="text-sm text-slate-600">当前没有生日任务。</p>}
    {event.data.items.map((item) => <Link key={item.task_id} to={item.route} onClick={onNavigate} className="block rounded-lg bg-slate-50 p-2 text-sm text-brand-800">
      <span className="font-medium">{item.label}</span><span className="ml-2 text-slate-500">{item.event_date} · {item.status}</span>
    </Link>)}
    {event.data.has_more && <p className="text-xs text-slate-500">这里只展示最近 20 项，请在任务页继续查看。</p>}
  </section>
  return <div className="mt-2 rounded-lg border border-brand-200 bg-white p-3 text-slate-900">
    <div className="flex items-center gap-2 text-xs text-slate-500"><WalletCards className="size-4" />余额查询结果</div>
    <p className="mt-1 text-lg font-semibold">{event.data.currency} {event.data.total}</p>
    <p className="text-xs text-slate-500">{event.data.account_count} 个账户{event.data.complete ? '' : '，结果可能不完整'}</p>
  </div>
}

function SubscriptionResultCard({ resultId, onNavigate }: { resultId: string; onNavigate: () => void }) {
  const result = useQuery({ queryKey: ['subscription-agent-result', resultId], queryFn: () => api.subscriptionAgentResult(resultId), staleTime: 0, gcTime: 0, retry: false })
  const navigate = useNavigate()
  if (result.isPending) return <LoadingState label="正在读取本人订阅结果…" />
  if (result.error) return <ErrorState error={result.error} onRetry={() => void result.refetch()} />
  if (!result.data) return null
  if (result.data.kind === 'forecast') {
    const data = result.data.data as SubscriptionAgentResult['data'] & { items?: { subscription_id: string; merchant: string; amount: string; charge_date: string }[]; projected_total?: string; from_date?: string; to_date?: string; complete?: boolean; filters?: { amount_gt: string | null }; needs_review?: { id: string; merchant: string; next_charge_at: string | null }[] }
    return <section aria-label="预计续费查询结果" className="mt-2 space-y-2 rounded-lg border border-brand-200 bg-white p-3 text-slate-900">
      <p className="font-medium">预计续费安排</p><p className="text-xs text-slate-500">{data.from_date} 至 {data.to_date} · 预计合计 {formatMoney(String(data.projected_total ?? '0'), 'CNY')}</p>
      {data.filters?.amount_gt != null && <p className="text-xs text-slate-500">筛选条件：金额严格大于 {data.filters.amount_gt} 元</p>}
      {data.items?.map((item) => <Link key={`${item.subscription_id}-${item.charge_date}`} to={`/subscriptions/${item.subscription_id}`} onClick={onNavigate} className="block rounded bg-slate-50 p-2 text-sm">{item.merchant} · {formatMoney(item.amount, 'CNY')} · 预计 {item.charge_date}</Link>)}
      {!data.items?.length && <p className="text-sm">该范围没有可纳入的预计扣费项目。</p>}
      {data.needs_review?.map((item, index) => <p key={`${item.id}-${index}`} className="rounded bg-amber-50 p-2 text-xs">{item.merchant} 的预测需复查，未计入合计；数据可能不完整。</p>)}
      {!data.complete && <p className="text-xs text-amber-800">结果不完整，不能据此判断预算充足。</p>}
      <Link to="/subscriptions" onClick={onNavigate} className="inline-block text-sm text-brand-700 underline">进入订阅管理</Link>
    </section>
  }
  if (result.data.kind === 'budget') {
    const data = result.data.data as Record<string, unknown>
    const suggestions = Array.isArray(data.suggestions) ? data.suggestions as { subscription_id: string; merchant: string; amount: string; demo_cancellable: boolean }[] : []
    return <section aria-label="订阅预算结果" className="mt-2 space-y-2 rounded-lg border border-amber-200 bg-white p-3 text-slate-900">
      <p className="font-medium">{data.over_budget ? '已知订阅金额超过预算' : data.under_budget_confirmed ? '预算内' : '预算暂无法确认'}</p>
      <p className="text-sm">已发生 {data.actual_total == null ? '不可用' : formatMoney(String(data.actual_total), 'CNY')} · 之后预计 {formatMoney(String(data.projected_remaining ?? '0'), 'CNY')} · 合计 {data.known_total == null ? '暂不可得' : formatMoney(String(data.known_total), 'CNY')}</p>
      {data.previous_actual_total != null && <p className="text-xs text-slate-500">上月实际订阅扣费 {formatMoney(String(data.previous_actual_total), 'CNY')}</p>}
      {!data.complete && <p className="text-xs text-amber-800">数据不完整或有预测待复查，已知金额可能偏低。</p>}
      {suggestions.map((item) => <div key={item.subscription_id} className="flex flex-wrap items-center justify-between gap-2 rounded bg-slate-50 p-2 text-sm"><span>{item.merchant} · 预计 {formatMoney(item.amount, 'CNY')}</span>{item.demo_cancellable && <button type="button" onClick={() => api.subscriptionCommand(item.subscription_id, 'cancel', crypto.randomUUID()).then((action) => { if ('request_hash' in action) { navigate(`/actions/${action.id}`); onNavigate() } })} className="rounded border border-red-300 px-2 py-1 text-xs text-red-700">申请取消并前往确认</button>}</div>)}
      <Link to="/subscriptions#budget-rules" onClick={onNavigate} className="inline-block text-sm text-brand-700 underline">管理预算规则</Link>
    </section>
  }
  if (result.data.kind === 'rules') {
    const data = result.data.data as { reminder_rules?: { id: string; scope: string; month: string | null; lead_days: number[]; status: string }[]; budget_rules?: { id: string; month: string; amount: string; status: string }[] }
    return <section aria-label="订阅规则查询结果" className="mt-2 space-y-2 rounded-lg border border-brand-200 bg-white p-3 text-slate-900"><p className="font-medium">本人订阅规则</p><p className="text-sm">提醒规则 {data.reminder_rules?.length ?? 0} 条；预算规则 {data.budget_rules?.length ?? 0} 条。</p>{data.reminder_rules?.slice(0, 5).map((rule) => <p key={rule.id} className="rounded bg-slate-50 p-2 text-xs">提醒 · {rule.scope === 'AMOUNT_GT' ? '金额筛选' : rule.scope === 'SUBSCRIPTION' ? '单个订阅' : '全部已核实订阅'} · {rule.month ?? '持续'} · 提前 {rule.lead_days.join('、')} 天 · {rule.status}</p>)}{data.budget_rules?.slice(0, 5).map((rule) => <p key={rule.id} className="rounded bg-slate-50 p-2 text-xs">预算 · {rule.month} · {formatMoney(rule.amount, 'CNY')} · {rule.status}</p>)}<Link to="/subscriptions#reminder-rules" onClick={onNavigate} className="text-sm text-brand-700 underline">查看并管理规则</Link></section>
  }
  if (result.data.kind === 'subscriptions' || result.data.kind === 'subscription_detail') {
    const data = result.data.data as { status?: string; items?: Subscription[] }
    const items = Array.isArray(data.items) ? data.items : []
    const detail = result.data.kind === 'subscription_detail'
    const ambiguous = detail && data.status === 'AMBIGUOUS'
    const title = detail ? (ambiguous ? '找到多个同名订阅' : '订阅详情') : '本人订阅列表'
    return <section aria-label={title} className="mt-2 min-w-0 space-y-2 break-words rounded-lg border border-brand-200 bg-white p-3 text-slate-900">
      <p className="font-medium">{title}</p>
      {data.status === 'NOT_FOUND' && <p className="text-sm">没有找到名称完全匹配的订阅。</p>}
      {ambiguous && <p className="text-xs text-amber-800">请从匹配项中选择一条，进入订阅页面查看完整扣费证据。</p>}
      {!detail && items.length === 0 && <p className="text-sm">当前没有订阅记录。</p>}
      {items.map((item) => <article key={item.id} className="rounded bg-slate-50 p-2 text-sm">
        <Link to={`/subscriptions/${encodeURIComponent(item.id)}`} onClick={onNavigate} className="font-medium text-brand-700 underline">{item.merchant}</Link>
        <p className="text-xs text-slate-600">{item.cadence === 'YEARLY' ? '年度' : '月度'} · {item.status} · {formatMoney(item.expected_amount, 'CNY')}</p>
        <p className="text-xs text-slate-600">下次预计扣费：{item.next_charge_at ?? '待确认'}</p>
        {detail && !ambiguous && item.occurrences?.map((occurrence, index) => <p key={`${item.id}-occurrence-${index}`} className="mt-1 text-xs text-slate-600">历史扣费：{String(occurrence.occurred_on ?? '日期未知')} · {formatMoney(String(occurrence.amount ?? '0'), 'CNY')}</p>)}
      </article>)}
      <Link to="/subscriptions" onClick={onNavigate} className="inline-block text-sm text-brand-700 underline">进入订阅管理</Link>
    </section>
  }
  return null
}

function SubscriptionQueryCard({ event, onNavigate }: {
  event: Extract<AgentEvent, { type: 'SUBSCRIPTION_QUERY_REQUESTED' }>
  onNavigate: () => void
}) {
  const client = useQueryClient()
  const actionId = event.data.action_id
  const action = useQuery({
    queryKey: ['action', actionId],
    queryFn: () => api.action(actionId),
    staleTime: 0,
    retry: false,
    refetchInterval: (query) => ['AUTHORIZED', 'EXECUTING', 'RECONCILING'].includes(query.state.data?.status ?? '') ? 1500 : false,
  })
  const refresh = async (next: BankingAction) => {
    client.setQueryData(['action', actionId], next)
    await client.invalidateQueries({ queryKey: ['action', actionId] })
  }
  const confirm = useMutation({
    mutationFn: () => {
      if (!action.data) throw new Error('正在读取查询请求，请稍后重试。')
      return api.confirmAction(actionId, action.data.request_hash)
    },
    onSuccess: refresh,
    onError: () => { void action.refetch() },
  })
  const cancel = useMutation({
    mutationFn: () => api.cancelAction(actionId),
    onSuccess: refresh,
    onError: () => { void action.refetch() },
  })
  const current = action.data
  const expired = confirm.error instanceof ApiError && confirm.error.code === 'ACTION_EXPIRED'
  const pending = current?.status === 'WAITING_CONFIRMATION' && !expired
  const retryable = current?.status === 'AUTHORIZED' && !expired
  const succeeded = current?.status === 'SUCCEEDED'
  const busy = confirm.isPending || cancel.isPending || current?.status === 'EXECUTING' || current?.status === 'RECONCILING'
  const labels: Record<typeof event.data.query_type, string> = {
    FORECAST: '续费预测', RULES: '提醒与预算规则', LIST: '本人订阅列表', DETAIL: '订阅详情',
  }
  return <section aria-label="订阅查询确认" className="mt-2 min-w-0 space-y-2 break-words rounded-lg border border-amber-300 bg-white p-3 text-slate-900">
    <div className="flex flex-wrap items-center gap-2"><p className="font-medium">{event.data.summary || labels[event.data.query_type]}</p><span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">黄色权限</span></div>
    <p className="text-xs text-slate-600">查询类型：{labels[event.data.query_type]}</p>
    <ul className="list-inside list-disc space-y-0.5 text-xs text-slate-600">
      {(event.data.conditions.length ? event.data.conditions : [
        event.data.query_type === 'RULES' ? '读取本人已保存的提醒与预算规则' : event.data.query_type === 'LIST' ? '读取本人订阅记录' : '按确认的商户名称精确查询',
      ]).map((condition) => <li key={condition}>{condition}</li>)}
    </ul>
    {action.isPending && <p className="text-xs text-slate-500">正在读取请求状态…</p>}
    {action.isError && <p role="alert" className="text-xs text-red-700">无法读取请求状态，请重试；确认前不会执行查询。</p>}
    {expired && <p role="status" className="text-xs text-amber-800">查询请求已过期，请重新发起。</p>}
    {retryable && <p className="text-xs text-amber-800">上次查询未完成（{current.error_code ?? '读取失败'}），可重新确认查询。</p>}
    {busy && <p role="status" className="flex items-center gap-2 text-xs text-slate-600"><LoaderCircle className="size-3 animate-spin" />正在查询本人订阅…</p>}
    {current?.status === 'CANCELLED' && <p className="text-xs text-slate-600">查询请求已取消。</p>}
    {current?.status === 'FAILED' && <p role="alert" className="text-xs text-red-700">查询未完成，请重新发起。</p>}
    {succeeded && current.result?.result_id && typeof current.result.result_id === 'string'
      ? <SubscriptionResultCard resultId={current.result.result_id} onNavigate={onNavigate}
        />
      : null}
    {(pending || retryable) && <div className="flex flex-wrap gap-2">
      <button type="button" onClick={() => confirm.mutate()} disabled={busy || action.isPending} className="rounded-md bg-brand-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">{confirm.isPending ? '正在确认…' : retryable ? '重试查询' : '确认查询'}</button>
      <button type="button" onClick={() => cancel.mutate()} disabled={busy || cancel.isPending} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs disabled:opacity-50">{cancel.isPending ? '正在取消…' : '取消'}</button>
    </div>}
    {confirm.isError && <p role="alert" className="text-xs text-red-700">{confirm.error instanceof Error ? confirm.error.message : '确认查询失败，请核对请求状态。'}</p>}
    {cancel.isError && <p role="alert" className="text-xs text-red-700">{cancel.error instanceof Error ? cancel.error.message : '取消失败，请核对请求状态。'}</p>}
    {action.isError && <button type="button" onClick={() => void action.refetch()} className="text-xs text-brand-700 underline">重新读取状态</button>}
  </section>
}

function BillReportStatusCard({ reportId, period, initialStatus, generated, onNavigate }: {
  reportId: string; period: string; initialStatus: string; generated: boolean; onNavigate: () => void
}) {
  const status = useQuery({
    queryKey: ['bill-report-status', reportId],
    queryFn: () => api.billReportStatus(reportId),
    staleTime: 0,
    gcTime: 0,
    retry: false,
    refetchInterval: (query) => ['queued', 'running'].includes(String(query.state.data?.status)) ? 1500 : false,
  })
  const current = status.data?.status ?? initialStatus
  const failureMessages: Record<string, string> = {
    CORE_READ_FAILED: '核心银行流水读取失败。你可以查看报告列表并手动重新生成。',
    REPORT_GENERATION_FAILED: '报告生成失败。你可以查看报告列表并手动重新生成。',
  }
  const label = current === 'complete' ? '已生成' : current === 'partial' ? '已生成，部分章节不可用'
    : current === 'failed' ? '生成失败' : current === 'running' ? '正在生成' : '等待生成'
  return <section aria-label="账单报告结果" className="mt-2 space-y-2 rounded-lg border border-brand-200 bg-white p-3 text-slate-900">
    <p className="font-medium">{generated && current === 'queued' ? '未找到对应报告，已开始生成' : `账单报告 · ${label}`}</p>
    <p className="text-xs text-slate-500">{period}{status.data?.progress ? ` · 进度 ${status.data.progress}%` : ''}</p>
    {current === 'failed' && status.data?.error && <p role="alert" className="rounded bg-red-50 p-2 text-xs text-red-700">{failureMessages[status.data.error] ?? `报告生成失败（${status.data.error}）。请查看报告列表后决定是否重新生成。`}</p>}
    {status.error && <p role="alert" className="text-xs text-red-700">暂时无法读取报告状态，请进入报告页核对。</p>}
    <div className="flex flex-wrap gap-3 text-sm">
      <Link to={`/insights/reports/${encodeURIComponent(reportId)}`} onClick={onNavigate} className="text-brand-700 underline">
        {current === 'complete' || current === 'partial' ? '打开报告' : '查看报告进度'}
      </Link>
      {current === 'failed' && <Link to="/insights/reports" onClick={onNavigate} className="text-brand-700 underline">查看报告列表并重新生成</Link>}
      {status.isError && <button type="button" onClick={() => void status.refetch()} className="text-brand-700 underline">重新读取状态</button>}
    </div>
  </section>
}

function ActionEventCard({ title, lines, actionId, label, onOpen }: { title: string; lines: string[]; actionId: string; label: string; onOpen: (id: string) => void }) {
  return <div className="mt-2 rounded-lg border border-amber-200 bg-white p-3 text-slate-900">
    <div className="flex items-center gap-2 text-xs text-amber-700"><WalletCards className="size-4" />{title}</div>
    <div className="mt-2 space-y-1">{lines.map((line) => <p key={line} className="text-sm">{line}</p>)}</div>
    <button onClick={() => onOpen(actionId)} className="mt-2 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700">{label}</button>
  </div>
}

function AnalysisCard({ id }: { id: string }) {
  const result = useQuery({ queryKey: ['private-analysis', id], queryFn: () => api.agentAnalysis(id), staleTime: 0, gcTime: 0, retry: false })
  if (result.isPending) return <LoadingState label="正在读取授权分析结果…" />
  if (result.error) return <ErrorState error={result.error} onRetry={() => void result.refetch()} />
  const value = result.data
  if (!value) return null
  const bill = value.kind === 'statistics' ? billPresentation(value.data.from_date, value.data.to_date) : null
  const title = value.kind === 'balance' ? '余额查询结果'
    : value.kind === 'transactions' ? '本人流水查询结果'
      : value.kind === 'statistics' ? bill?.title
        : value.kind === 'anomalies' ? '异常消费候选'
          : value.kind === 'wealth_products' ? '定存产品目录'
            : value.kind === 'wealth_recommend' ? '定存适配推荐'
              : '我的定存持有'
  return <section className="mt-2 min-w-0 space-y-2 break-words rounded-lg border border-brand-200 bg-white p-3 text-slate-900" aria-label="授权分析结果">
    <p className="font-medium">{title}</p>
    {value.kind === 'balance' && <><p>{formatMoney(value.data.total, value.data.currency)}</p><p>{value.data.account_count} 个合格账户</p></>}
    {value.kind === 'transactions' && <>
      {!value.data.items.length && <p>查询范围内没有流水。</p>}
      {value.data.items.map((row) => <article key={`${row.account_id}-${row.transaction_id}`} className="rounded bg-slate-50 p-2 text-xs">
        <p>{row.date} · {row.direction === 'credit' ? '收入' : row.direction === 'debit' ? '支出' : '其他'} · {row.category}</p>
        <p className="font-medium">{formatMoney(row.amount, row.currency)}</p>
      </article>)}
    </>}
    {value.kind === 'statistics' && <>
      <p className="text-xs">{value.data.from_date} 至 {value.data.to_date} · {value.data.account_ids.length} 个账户 · {value.data.transaction_count} 笔流水</p>
      {!value.data.transaction_count && <p>查询期间没有可统计流水。</p>}
      <p>收入 {formatMoney(value.data.totals.income ?? '0', value.data.currency)}</p><p>消费 {formatMoney(value.data.totals.expense ?? '0', value.data.currency)}</p>
      <p>对外转账 {formatMoney(value.data.totals.transfer ?? '0', value.data.currency)}</p>
      {Object.entries(value.data.categories).sort(([, left], [, right]) => compareMoneyDescending(left, right)).map(([name, amount]) => <p key={name}>{name}：{formatMoney(amount, value.data.currency)}</p>)}
      {bill?.kind !== 'month' && <div aria-label="逐月收支明细">
        <p className="font-medium">逐月收支明细</p>
        {Object.entries(value.data.monthly).sort(([a], [b]) => a.localeCompare(b)).map(([month, totals]) => <p key={month} className="text-xs">{month} · 收入 {formatMoney(totals.income ?? '0', value.data.currency)} · 消费 {formatMoney(totals.expense ?? '0', value.data.currency)} · 对外转账 {formatMoney(totals.transfer ?? '0', value.data.currency)}</p>)}
      </div>}
      <p className="text-xs text-slate-500">数据截止 {new Date(value.data.data_cutoff).toLocaleString()}。{!value.data.snapshot_atomic && '核心数据为非原子快照。'}</p>
    </>}
    {value.kind === 'anomalies' && <>
      <p className="text-xs">{value.data.from_date} 至 {value.data.to_date} · {value.data.account_ids.length} 个账户</p>
      {value.data.items.map((row) => <article key={String(row.anomaly_key)} className="rounded bg-amber-50 p-2"><p>{anomalyTitle(row)} · {anomalyStatusLabel(row.current_review_status ?? row.status)}</p><p>{anomalyEvidenceText(row)}</p><AnomalyReviewControls row={row} /></article>)}
      {!value.data.items.length && <p>{EMPTY_ANOMALIES_TEXT}</p>}
    </>}
    {value.kind === 'wealth_products' && <>
      {!value.data.items.length && <p>当前没有可展示的合格定存产品。</p>}
      {value.data.items.map((product) => <article key={product.product_id} className="rounded bg-slate-50 p-2 text-sm">
        <p className="font-medium">{product.name}</p>
        <p>{product.currency} · 风险等级 {product.risk_level ?? '未配置'} · {product.allows_premature ? '允许提前赎回' : '不允许提前赎回'}</p>
        <p>起存 {formatMoney(product.min_deposit_amount || '0', product.currency)} · 上限 {product.max_deposit_amount ? formatMoney(product.max_deposit_amount, product.currency) : '未限定'}</p>
        <p>期限 {termText(product.min_term)} 至 {termText(product.max_term)} · 年利率 {product.annual_interest_rates.length ? `${product.annual_interest_rates.join(' / ')}%` : '按核心银行条款'}</p>
      </article>)}
      <Link to="/wealth" className="text-sm text-brand-700 underline">进入定存与财富页面</Link>
    </>}
    {value.kind === 'wealth_recommend' && <>
      <p className="text-xs text-slate-500">按 {formatMoney(value.data.criteria.amount, 'CNY')}、{value.data.criteria.term_months} 个月{value.data.criteria.needs_liquidity ? '、需要流动性' : ''}筛选；不构成投资建议。</p>
      {!value.data.items.length && <p>当前没有同时满足风险、金额、期限和流动性条件的产品。</p>}
      {value.data.items.map((item) => <article key={item.product.product_id} className="rounded bg-slate-50 p-2 text-sm">
        <p className="font-medium">{item.product.name}</p>
        <p>年利率 {item.annual_interest_rate}% · 估算收益 {formatMoney(item.estimated_interest, item.product.currency)}</p>
        <p className="text-xs text-slate-500">{item.reason}；收益为估算值。</p>
      </article>)}
      <Link to="/wealth" className="text-sm text-brand-700 underline">查看产品并办理</Link>
    </>}
    {value.kind === 'wealth_holdings' && <>
      {!value.data.items.length && <p>当前没有定存持有。</p>}
      {value.data.items.map((holding) => <article key={holding.holding_id} className="rounded bg-slate-50 p-2 text-sm">
        <p className="font-medium">{holding.product_name}{holding.account_suffix ? ` · 尾号 ${holding.account_suffix}` : ''}</p>
        <p>本金 {formatMoney(holding.principal, holding.currency)} · 年利率 {holding.annual_interest_rate}%</p>
        <p>到期日 {holding.maturity_date || '暂不可得'} · {holding.status}</p>
      </article>)}
      <Link to="/wealth" className="text-sm text-brand-700 underline">管理本人定存</Link>
    </>}
    <p className="text-xs text-slate-500">精确数据仅经本人授权接口展示，不进入模型上下文。有效至 {new Date(value.expires_at).toLocaleString()}。</p>
  </section>
}

export function AgentPanel({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const client = useQueryClient()
  function invalidateSubscriptions() {
    void client.invalidateQueries({ queryKey: ['subscriptions'] })
    void client.invalidateQueries({ queryKey: ['subscription'] })
    void client.invalidateQueries({ queryKey: ['subscription-renewals'] })
    void client.invalidateQueries({ queryKey: ['subscription-forecast'] })
    void client.invalidateQueries({ queryKey: ['subscription-reminder-rules'] })
    void client.invalidateQueries({ queryKey: ['subscription-budget-rules'] })
    void client.invalidateQueries({ queryKey: ['notifications'] })
    void client.invalidateQueries({ queryKey: ['notification-unread-count'] })
  }
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [pendingClarification, setPendingClarification] = useState<string | null>(null)
  const [recoveryTarget, setRecoveryTarget] = useState<'report' | 'subscription' | 'other' | null>(null)
  const [accountId, setAccountId] = useState('')
  const [period, setPeriod] = useState(currentMonth)
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts, staleTime: 30_000, retry: false })
  async function loadActiveConversation() {
    const existing = await api.agentConversations()
    const selected = existing[0] ?? await api.createAgentConversation()
    return api.agentConversation(selected.id)
  }
  const conversation = useQuery({
    queryKey: ['agent-conversation-active'],
    queryFn: loadActiveConversation,
    staleTime: Infinity,
    retry: false,
  })
  const conversationId = conversation.data?.id
  const resumedRuns = useRef(new Set<string>())
  useEffect(() => {
    const run = conversation.data?.current_run
    if (!conversationId || !run || !['QUEUED', 'RUNNING'].includes(run.status) || resumedRuns.current.has(run.id)) return
    resumedRuns.current.add(run.id)
    const controller = new AbortController()
    void api.resumeAgentRun(conversationId, run, controller.signal).then((response) => {
      setMessages((current) => [...current, { id: response.trace_id, role: 'assistant', text: response.message, events: response.events }])
    }).catch(() => {
      resumedRuns.current.delete(run.id)
    })
    return () => controller.abort()
  }, [conversation.data?.current_run, conversationId])
  const selectedAccount = accountId || (accounts.data?.length === 1 ? String(accounts.data[0].id) : '')
  const mutation = useMutation({
    mutationFn: async ({ message, queryContext, continuationRef, optionRef }: { message: string; queryContext: AgentQueryContext; continuationRef?: string; optionRef?: string }) => {
      const active = conversation.data ?? await client.fetchQuery({ queryKey: ['agent-conversation-active'], queryFn: loadActiveConversation, staleTime: Infinity })
      if (!active) throw new ApiError(503, { code: 'AGENT_CONVERSATION_UNAVAILABLE', message: '无法建立 Agent 对话，请稍后重试', retryable: true })
      return api.sendConversationAgentMessage(active.id, message, queryContext, continuationRef, optionRef)
    },
    retry: false,
    onSuccess: (response) => {
      if (response.events.some((event) => event.type.startsWith('SUBSCRIPTION_'))) invalidateSubscriptions()
    },
    onError: (error, variables) => {
      const isUncertain = error instanceof ApiError
        && ['WRITE_RESULT_UNKNOWN', 'NETWORK_ERROR'].includes(error.code)
      if (!isUncertain) return

      if (/(?:报告|报表)/.test(variables.message)) {
        setRecoveryTarget('report')
        void client.invalidateQueries({ queryKey: ['bill-report-summaries'] })
      } else if (/(?:订阅|续费)/.test(variables.message)) {
        setRecoveryTarget('subscription')
        invalidateSubscriptions()
      } else {
        setRecoveryTarget('other')
      }
    },
  })
  const endOfMessages = useRef<HTMLDivElement>(null)
  const conversationMessageCount = conversation.data?.messages?.length ?? 0
  useEffect(() => {
    endOfMessages.current?.scrollIntoView?.({ block: 'nearest' })
  }, [conversationMessageCount, messages.length, mutation.isPending])

  async function startNewConversation() {
    if (mutation.isPending) return
    const created = await api.createAgentConversation()
    const detail = await api.agentConversation(created.id)
    client.setQueryData(['agent-conversation-active'], detail)
    setMessages([])
    setPendingClarification(null)
    mutation.reset()
  }

  async function removeConversation() {
    if (!conversationId || mutation.isPending || !window.confirm('删除这段对话记录？此操作不可恢复。')) return
    await api.deleteAgentConversation(conversationId)
    await startNewConversation()
  }

  function send(text: string, clarificationRef?: string, optionRef?: string) {
    const message = text.trim()
    if (!message || mutation.isPending) return
    const continuationRef = clarificationRef
      ?? (pendingClarification && message.startsWith('提前') ? pendingClarification : undefined)
    if (pendingClarification) setPendingClarification(null)
    mutation.reset()
    setRecoveryTarget(null)
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'user', text: message }])
    setInput('')
    const allAccounts = /(?:所有|全部|各个|每个)\s*账户/.test(message)
    const insightRequest = /消费分类|消费统计|消费情况|消费分析|月度账单|年度账单|账单统计|异常消费|异常交易|异常候选/.test(message)
    const explicitPeriod = /(?:20\d{2}\s*年\s*\d{1,2}\s*月|20\d{2}-\d{2}|\d{1,2}\s*月份?|本月|这个月|当月|上个月|上月|下个月|下月|今年|本年|去年|上一年|最近\s*\d+\s*天)/.test(message)
    const queryContext: AgentQueryContext = {
      ...(!allAccounts && selectedAccount ? { account_id: Number(selectedAccount) } : {}),
      ...(period && (!insightRequest || explicitPeriod) ? { period } : {}),
    }
    mutation.mutate({ message, queryContext, continuationRef, optionRef }, {
      onSuccess: (response) => {
        const clarification = response.events.find((event) => event.type === 'SUBSCRIPTION_CLARIFICATION_REQUIRED')
        if (clarification?.type === 'SUBSCRIPTION_CLARIFICATION_REQUIRED') setPendingClarification(clarification.data.clarification_id)
        setMessages((current) => [...current, {
          id: response.trace_id,
          role: 'assistant',
          text: response.message,
          events: response.events,
        }])
      },
    })
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    send(input)
  }

  function queryBill(kind: 'statistics' | 'anomalies') {
    if (!selectedAccount || !/^\d{4}-(0[1-9]|1[0-2])$/.test(period)) return
    send(`查询账户 ${selectedAccount} 在 ${period} 的${kind === 'statistics' ? '消费分类统计' : '异常消费候选'}`)
  }

  function queryAllAccounts(kind: 'statistics' | 'anomalies') {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(period)) return
    send(`查询我所有账户在 ${period} 的${kind === 'statistics' ? '消费分类统计' : '异常消费候选'}`)
  }

  const resultUncertain = mutation.error instanceof ApiError
    && ['WRITE_RESULT_UNKNOWN', 'NETWORK_ERROR'].includes(mutation.error.code)
  const visibleMessages = [welcome, ...restoredMessages(conversation.data), ...messages]

  return <div role="dialog" aria-label="智能银行助理" className="fixed inset-0 z-50 flex flex-col bg-white shadow-2xl sm:inset-auto sm:right-6 sm:bottom-24 sm:h-[680px] sm:max-h-[calc(100dvh-7rem)] sm:w-[420px] sm:overflow-hidden sm:rounded-lg sm:border sm:border-slate-200">
    <header className="flex items-center justify-between bg-gradient-to-r from-brand-700 to-brand-500 px-4 py-3 text-white">
      <div className="flex items-center gap-2"><Bot className="size-5" /><div><p className="text-sm font-semibold">智能银行助理</p><p className="text-xs text-white/80">账户 · 支付 · 卡片 · 洞察 · 订阅</p></div></div>
      <div className="flex items-center"><button onClick={() => void startNewConversation()} disabled={mutation.isPending || conversation.isPending} aria-label="新建对话" title="新建对话" className="p-2 disabled:opacity-50"><Plus className="size-4" /></button><button onClick={() => void removeConversation()} disabled={!conversationId || mutation.isPending} aria-label="删除当前对话" title="删除当前对话" className="p-2 disabled:opacity-50"><Trash2 className="size-4" /></button><button onClick={onClose} aria-label="关闭助手" className="p-2"><X className="size-4" /></button></div>
    </header>
    <div className="space-y-2 border-b px-3 py-3">
      <div className="grid grid-cols-2 gap-2">
        <label className="min-w-0 text-xs text-slate-600">账单账户<select aria-label="账单账户" className="input mt-1 w-full min-w-0" value={selectedAccount} onChange={(event) => setAccountId(event.target.value)} disabled={accounts.isPending || mutation.isPending}>
          <option value="">{accounts.isPending ? '正在读取账户' : '选择本人账户'}</option>
          {accounts.data?.map((account) => <option key={account.id} value={account.id}>尾号 {account.account_no.slice(-4)} · {account.currency}</option>)}
        </select></label>
        <label className="min-w-0 text-xs text-slate-600">月份<input aria-label="账单月份" type="month" className="input mt-1 w-full min-w-0" value={period} onChange={(event) => setPeriod(event.target.value)} disabled={mutation.isPending} /></label>
      </div>
      {accounts.isError && <div className="flex items-center justify-between text-xs text-red-700"><span>账单账户暂时无法读取</span><button title="重新读取账户" aria-label="重新读取账户" onClick={() => void accounts.refetch()}><RefreshCw className="size-4" /></button></div>}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => send('帮我识别本人全部合格账户中的订阅扣费')} disabled={mutation.isPending} className="rounded-md border px-3 py-1.5 text-xs disabled:opacity-50">识别订阅扣费</button>
        <button onClick={() => send('我还有多少钱？')} disabled={mutation.isPending} className="rounded-md border px-3 py-1.5 text-xs disabled:opacity-50">查余额</button>
        <button onClick={() => queryBill('statistics')} disabled={!selectedAccount || !period || mutation.isPending} className="rounded-md border px-3 py-1.5 text-xs disabled:opacity-50">消费统计</button>
        <button onClick={() => queryBill('anomalies')} disabled={!selectedAccount || !period || mutation.isPending} className="rounded-md border px-3 py-1.5 text-xs disabled:opacity-50">异常候选</button>
        <button onClick={() => queryAllAccounts('statistics')} disabled={accounts.isPending || accounts.isError || !accounts.data?.length || !/^\d{4}-(0[1-9]|1[0-2])$/.test(period) || mutation.isPending} className="rounded-md border px-3 py-1.5 text-xs disabled:opacity-50">全部账户统计</button>
        <button onClick={() => queryAllAccounts('anomalies')} disabled={accounts.isPending || accounts.isError || !accounts.data?.length || !/^\d{4}-(0[1-9]|1[0-2])$/.test(period) || mutation.isPending} className="rounded-md border px-3 py-1.5 text-xs disabled:opacity-50">全部账户异常</button>
      </div>
    </div>
    <p className="px-3 py-1 text-xs text-slate-500">订阅识别固定扫描本人全部合格账户最近800天流水，不使用上方账单账户和月份选择。</p>
    <div className="min-h-0 flex-1 overflow-y-auto bg-page-50 p-4" aria-live="polite">
      <div className="space-y-3">
        {visibleMessages.map((message) => <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`max-w-[86%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${message.role === 'user' ? 'bg-brand-600 text-white' : 'border border-slate-200 bg-white text-slate-800'}`}>
            <p className="whitespace-pre-wrap break-words">{message.text}</p>
            {message.events?.map((agentEvent, index) => <EventCard
              key={`${agentEvent.type}-${index}`}
              event={agentEvent}
              onNavigate={onClose}
              onClarify={(ref, days) => send(`提前${days}天`, ref)}
              onSelectOption={(ref, label) => send(`我选择“${label}”`, undefined, ref)}
              onOpenAction={(id) => { navigate(`/actions/${id}`); onClose() }}
            />)}
          </div>
        </div>)}
        {mutation.isPending && <div className="flex items-center gap-2 text-sm text-slate-500"><LoaderCircle className="size-4 animate-spin" />正在识别需求并处理…</div>}
        {mutation.isError && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"><p>{resultUncertain
          ? recoveryTarget === 'report'
            ? '账单报告请求结果未确认。请先核对报告列表，暂勿重复提交；如果已开始生成，可从列表打开任务。'
            : recoveryTarget === 'subscription'
              ? '订阅请求结果未确认，请先查看最近扫描时间、候选或提醒规则，暂勿重复提交。'
              : '本次请求结果未确认，请先到相关功能页核对，暂勿重复提交。'
          : mutation.error instanceof Error ? mutation.error.message : 'Agent 请求失败'}</p>
          {resultUncertain && recoveryTarget === 'report' && <Link to="/insights/reports" onClick={onClose} className="mt-2 inline-block underline">核对报告列表</Link>}
          {resultUncertain && recoveryTarget === 'subscription' && <Link to="/subscriptions" onClick={onClose} className="mt-2 inline-block underline">到订阅管理页核对</Link>}</div>}
        <div ref={endOfMessages} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">{destinations.map(([label, path]) => <button key={path} onClick={() => { navigate(path); onClose() }} className="flex items-center gap-1 rounded-full bg-white px-3 py-1.5 text-xs ring-1 ring-slate-200 hover:ring-brand-300"><span>{label}</span><ExternalLink className="size-3 text-brand-600" /></button>)}</div>
    </div>
    <form onSubmit={submit} className="flex gap-2 border-t bg-white p-3">
      <input value={input} onChange={(event) => setInput(event.target.value)} className="input" maxLength={2000} aria-label="给智能银行助理发送消息" placeholder="试试问：我还有多少钱？" />
      <button type="submit" aria-label="发送消息" disabled={!input.trim() || mutation.isPending} className="rounded-xl bg-brand-600 px-3 text-white disabled:cursor-not-allowed disabled:opacity-50"><Send className="size-4" /></button>
    </form>
  </div>
}
