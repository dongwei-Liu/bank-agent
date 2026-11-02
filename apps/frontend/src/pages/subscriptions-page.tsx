import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { EmptyState, ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import { api, type BankingAction, type Subscription, type SubscriptionNotification } from '@/lib/api'
import { subscriptionEvidenceLines } from '@/lib/evidence'
import { formatMoney } from '@/lib/format'

const cadenceLabel = { MONTHLY: '每月', YEARLY: '每年' }
const statusLabel = { CANDIDATE: '待核实', VERIFIED: '已核实', IGNORED: '已忽略', CANCELLED: '已取消' }

function shanghaiMonth() {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' }).formatToParts(new Date())
  return `${parts.find((part) => part.type === 'year')?.value}-${parts.find((part) => part.type === 'month')?.value}`
}

function isAction(value: Subscription | BankingAction): value is BankingAction {
  return 'request_hash' in value
}

export function SubscriptionsPage() {
  const client = useQueryClient()
  const navigate = useNavigate()
  const [month, setMonth] = useState(shanghaiMonth)
  const [reminderMonth, setReminderMonth] = useState('')
  const [scope, setScope] = useState<'ALL_VERIFIED' | 'AMOUNT_GT' | 'SUBSCRIPTION'>('ALL_VERIFIED')
  const [subscriptionId, setSubscriptionId] = useState('')
  const [editingReminderId, setEditingReminderId] = useState<string | null>(null)
  const [editingBudgetId, setEditingBudgetId] = useState<string | null>(null)
  const [amountGt, setAmountGt] = useState('')
  const [leads, setLeads] = useState<number[]>([])
  const [budgetAmount, setBudgetAmount] = useState('')
  const query = useQuery({ queryKey: ['subscriptions'], queryFn: api.subscriptions })
  const renewals = useQuery({ queryKey: ['subscription-renewals', 3], queryFn: () => api.subscriptionRenewals(3) })
  const forecast = useQuery({ queryKey: ['subscription-forecast', month], queryFn: () => api.subscriptionForecast({ month }), retry: false })
  const reminderRules = useQuery({ queryKey: ['subscription-reminder-rules'], queryFn: api.subscriptionReminderRules })
  const budgetRules = useQuery({ queryKey: ['subscription-budget-rules'], queryFn: api.subscriptionBudgetRules })
  const notifications = useQuery({ queryKey: ['notifications'], queryFn: () => api.notifications(), refetchInterval: 30_000 })

  async function invalidatePlanning() {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['subscriptions'] }),
      client.invalidateQueries({ queryKey: ['subscription'] }),
      client.invalidateQueries({ queryKey: ['subscription-renewals'] }),
      client.invalidateQueries({ queryKey: ['subscription-forecast'] }),
      client.invalidateQueries({ queryKey: ['subscription-reminder-rules'] }),
      client.invalidateQueries({ queryKey: ['subscription-budget-rules'] }),
      client.invalidateQueries({ queryKey: ['notifications'] }),
      client.invalidateQueries({ queryKey: ['notification-unread-count'] }),
    ])
  }
  const scan = useMutation({
    mutationFn: api.scanSubscriptions,
    onSuccess: invalidatePlanning,
  })
  const reminderCreate = useMutation({
    mutationFn: () => {
      const body = {
        scope,
        amount_gt: scope === 'AMOUNT_GT' ? amountGt : null,
        subscription_id: scope === 'SUBSCRIPTION' ? subscriptionId : null,
        month: reminderMonth || null,
        lead_days: leads,
      }
      const request = editingReminderId
        ? api.updateSubscriptionReminderRule(editingReminderId, body, crypto.randomUUID())
        : api.createSubscriptionReminderRule(body, crypto.randomUUID())
      return request.then((result) => ({ ...result, reused: 'reused' in result ? result.reused : false }))
    },
    onSuccess: async () => { setEditingReminderId(null); await invalidatePlanning() },
  })
  const budgetCreate = useMutation({
    mutationFn: () => {
      const request = editingBudgetId
      ? api.updateSubscriptionBudget(editingBudgetId, month, budgetAmount, crypto.randomUUID())
      : api.saveSubscriptionBudget(month, budgetAmount, crypto.randomUUID())
      return request.then((result) => ({ ...result, reused: 'reused' in result ? result.reused : false }))
    },
    onSuccess: async () => { setEditingBudgetId(null); await invalidatePlanning() },
  })
  const readNotification = useMutation({
    mutationFn: api.markNotificationRead,
    onSuccess: invalidatePlanning,
  })
  if (query.isPending) return <LoadingState label="正在读取订阅候选…" />
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  return <div className="space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-xl font-semibold">订阅管理</h1><p className="mt-1 text-sm text-ink-500">根据真实账单确定性识别；取消只作用于比赛环境的 Demo 商户，不代表取消真实第三方会员。</p></div><Button onClick={() => scan.mutate()} disabled={scan.isPending}>{scan.isPending ? '扫描中…' : '重新扫描账单'}</Button></div>
    <section className="space-y-2 rounded-xl bg-teal-50 p-3 text-sm text-teal-900 ring-1 ring-teal-100">
      <h2 className="font-medium">近期续费</h2>
      {renewals.isPending && <LoadingState label="正在读取续费安排…" />}
      {renewals.error && <ErrorState error={renewals.error} onRetry={() => void renewals.refetch()} />}
      {renewals.data && <p className="text-xs">预计范围 {renewals.data.from_date} 至 {renewals.data.to_date}（{renewals.data.timezone}）· 最近成功扫描：{renewals.data.last_scan_at ? new Date(renewals.data.last_scan_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '尚未扫描'}</p>}
      {renewals.data?.upcoming.map((row) => <Link key={row.id} to={`/subscriptions/${row.id}`} className="block rounded-lg bg-white/70 px-3 py-2 hover:bg-white">{row.merchant} · 预计 {formatMoney(row.expected_amount, 'CNY')} · {row.next_charge_at}</Link>)}
      {renewals.data && renewals.data.upcoming.length === 0 && <p>未来三天没有已核实订阅预计续费。</p>}
      {renewals.data?.needs_review.map((row) => <p key={row.id} className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">{row.merchant} 的预计日期 {row.next_charge_at} 已过，建议重新扫描核对；这不表示实际漏扣。</p>)}
    </section>
    <section className="space-y-3 rounded-xl bg-white p-4 ring-1 ring-slate-200" aria-label="订阅月度预测">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><h2 className="font-semibold">月度预计扣费</h2><p className="text-xs text-ink-500">只纳入已核实订阅；预计金额不是实际扣费。</p></div>
        <label className="text-xs">目标月份<input aria-label="订阅预测月份" className="input ml-2 w-40" type="month" value={month} onChange={(event) => setMonth(event.target.value)} /></label>
      </div>
      {forecast.isPending && <LoadingState label="正在计算预计扣费…" />}
      {forecast.error && <ErrorState error={forecast.error} onRetry={() => void forecast.refetch()} />}
      {forecast.data && <>
        <p className="text-sm">{forecast.data.from_date} 至 {forecast.data.to_date} · 预计合计 {formatMoney(forecast.data.projected_total, 'CNY')}</p>
        {!forecast.data.complete && <p role="status" className="rounded-lg bg-amber-50 p-2 text-sm text-amber-900">预测金额可能不完整。下方待复查项目未计入预计合计，因此不能据此判断预算充足。</p>}
        {forecast.data.items.map((item, index) => <Link key={`${item.subscription_id}-${item.charge_date}-${index}`} to={`/subscriptions/${item.subscription_id}`} className="block rounded-lg bg-slate-50 px-3 py-2 text-sm hover:bg-slate-100">{item.merchant} · {formatMoney(item.amount, 'CNY')} · 预计 {item.charge_date}</Link>)}
        {!forecast.data.items.length && <p className="text-sm text-ink-500">该范围没有可纳入的预计扣费项目。</p>}
        {forecast.data.needs_review.map((item, index) => <p key={`${item.id}-${index}`} className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{item.merchant}：预测日期 {item.next_charge_at ?? '缺失'}，需复查；未将其计入预测金额。</p>)}
        <p className="text-xs text-ink-500">最近成功扫描：{forecast.data.last_scan_at ? new Date(forecast.data.last_scan_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '尚未扫描'}</p>
      </>}
    </section>
    <section id="notifications" className="space-y-3 rounded-xl bg-white p-4 ring-1 ring-slate-200" aria-label="站内提醒">
      <h2 className="font-semibold">站内提醒</h2>
      {notifications.isPending && <LoadingState label="正在读取站内提醒…" />}
      {notifications.error && <ErrorState error={notifications.error} onRetry={() => void notifications.refetch()} />}
      {notifications.data?.length === 0 && <p className="text-sm text-ink-500">暂无站内提醒。</p>}
      {notifications.data?.map((item) => <NotificationRow key={item.id} item={item} onRead={() => readNotification.mutate(item.id)} />)}
    </section>
    <section className="grid gap-4 lg:grid-cols-2">
      <div id="reminder-rules" className="space-y-3 rounded-xl bg-white p-4 ring-1 ring-slate-200">
        <div><h2 className="font-semibold">提醒规则</h2><p className="text-xs text-ink-500">每天上海时间09:00生成站内提醒；自动提醒只覆盖已核实订阅。</p></div>
        <label className="block text-sm">提醒范围<select aria-label="提醒范围" className="input mt-1 w-full" value={scope} onChange={(event) => setScope(event.target.value as typeof scope)}><option value="ALL_VERIFIED">全部已核实订阅</option><option value="AMOUNT_GT">金额严格大于指定金额</option><option value="SUBSCRIPTION">单个已核实订阅</option></select></label>
        {scope === 'AMOUNT_GT' && <label className="block text-sm">金额门槛<input aria-label="提醒金额门槛" className="input mt-1 w-full" type="number" min="0.01" step="0.01" value={amountGt} onChange={(event) => setAmountGt(event.target.value)} placeholder="例如 50" /></label>}
        {scope === 'SUBSCRIPTION' && <label className="block text-sm">订阅<select aria-label="提醒订阅项目" className="input mt-1 w-full" value={subscriptionId} onChange={(event) => setSubscriptionId(event.target.value)}><option value="">选择已核实订阅</option>{query.data?.filter((item) => item.status === 'VERIFIED').map((item) => <option key={item.id} value={item.id}>{item.merchant}</option>)}</select></label>}
        <label className="block text-sm">目标月份（留空表示持续生效）<input aria-label="提醒目标月份" className="input mt-1 w-full" type="month" value={reminderMonth} onChange={(event) => setReminderMonth(event.target.value)} /></label>
        <fieldset><legend className="text-sm">提前提醒</legend><div className="mt-1 flex gap-4">{[1, 3, 7].map((day) => <label key={day} className="flex items-center gap-1 text-sm"><input type="checkbox" checked={leads.includes(day)} onChange={(event) => setLeads((current) => event.target.checked ? [...current, day].sort() : current.filter((item) => item !== day))} />提前{day}天</label>)}</div></fieldset>
        <Button onClick={() => reminderCreate.mutate()} disabled={reminderCreate.isPending || leads.length === 0 || (scope === 'AMOUNT_GT' && !amountGt) || (scope === 'SUBSCRIPTION' && !subscriptionId)}>{reminderCreate.isPending ? '保存中…' : editingReminderId ? '保存规则修改' : '保存提醒规则'}</Button>
        {editingReminderId && <Button variant="outline" onClick={() => setEditingReminderId(null)}>取消编辑</Button>}
        {reminderCreate.error && <p role="alert" className="text-sm text-red-600">{reminderCreate.error.message}</p>}
        {reminderCreate.data && <p role="status" className="text-sm text-emerald-700">提醒规则已保存{reminderCreate.data.reused ? '（已复用现有规则）' : ''}。</p>}
        {reminderRules.error && <ErrorState error={reminderRules.error} onRetry={() => void reminderRules.refetch()} />}
        <div className="space-y-2">{reminderRules.data?.map((rule) => <RuleRow key={rule.id} title={`${rule.scope === 'ALL_VERIFIED' ? '全部已核实订阅' : rule.scope === 'AMOUNT_GT' ? `金额高于 ${rule.amount_gt} 元` : '指定订阅'} · 提前 ${rule.lead_days.join('、')} 天${rule.month ? ` · ${rule.month}` : ' · 持续'}`} status={rule.status} disabled={reminderRules.isFetching} onEdit={() => { setEditingReminderId(rule.id); setScope(rule.scope); setSubscriptionId(rule.subscription_id ?? ''); setAmountGt(rule.amount_gt ?? ''); setReminderMonth(rule.month ?? ''); setLeads(rule.lead_days) }} onCommand={(command) => api.subscriptionReminderCommand(rule.id, command, crypto.randomUUID()).then(invalidatePlanning)} />)}</div>
      </div>
      <div id="budget-rules" className="space-y-3 rounded-xl bg-white p-4 ring-1 ring-slate-200">
        <div><h2 className="font-semibold">订阅预算监测</h2><p className="text-xs text-ink-500">预算只监测，不限制扣费；历史已发生金额与未来预计金额合并评估。</p></div>
        <label className="block text-sm">目标月份<input aria-label="预算月份" className="input mt-1 w-full" type="month" value={month} onChange={(event) => setMonth(event.target.value)} /></label>
        <label className="block text-sm">预算金额<input aria-label="预算金额" className="input mt-1 w-full" type="number" min="0.01" step="0.01" value={budgetAmount} onChange={(event) => setBudgetAmount(event.target.value)} placeholder="例如 200" /></label>
        <Button onClick={() => budgetCreate.mutate()} disabled={budgetCreate.isPending || !budgetAmount}>{budgetCreate.isPending ? '评估中…' : editingBudgetId ? '保存预算修改并评估' : '保存并立即评估'}</Button>
        {editingBudgetId && <Button variant="outline" onClick={() => setEditingBudgetId(null)}>取消编辑</Button>}
        {budgetCreate.error && <p role="alert" className="text-sm text-red-600">{budgetCreate.error.message}</p>}
        {budgetCreate.data && <BudgetEvaluation value={budgetCreate.data.evaluation} onCancel={(id) => { const sub = query.data?.find((row) => row.id === id); if (!sub?.demo_adapter) return; api.subscriptionCommand(id, 'cancel', crypto.randomUUID()).then((action) => { if (isAction(action)) navigate(`/actions/${action.id}`) }) }} />}
        {budgetRules.error && <ErrorState error={budgetRules.error} onRetry={() => void budgetRules.refetch()} />}
        <div className="space-y-2">{budgetRules.data?.map((rule) => <RuleRow key={rule.id} title={`${rule.month} · ${formatMoney(rule.amount, 'CNY')}`} status={rule.status} disabled={budgetRules.isFetching} onEdit={() => { setEditingBudgetId(rule.id); setMonth(rule.month); setBudgetAmount(rule.amount) }} onCommand={(command) => api.subscriptionBudgetCommand(rule.id, command, crypto.randomUUID()).then(invalidatePlanning)} />)}</div>
      </div>
    </section>
    {scan.data && <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">扫描完成：新增 {scan.data.created} 个，更新 {scan.data.updated} 个，本次匹配 {scan.data.matched_candidates} 个候选；保存订阅共 {scan.data.found} 个。范围 {scan.data.from_date} 至 {scan.data.to_date}，扫描时间 {new Date(scan.data.scanned_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}。</p>}
    {scan.error && <ErrorState error={scan.error} onRetry={() => scan.mutate()} />}
    {query.data?.map((row) => <SubscriptionCard key={row.id} subscription={row} />)}
    {query.data?.length === 0 && <EmptyState title="暂无订阅候选" description="点击“重新扫描账单”，系统会查找至少三次且周期、金额都稳定的商户扣款。" />}
  </div>
}

function NotificationRow({ item, onRead }: { item: SubscriptionNotification; onRead: () => void }) {
  const planned = item.payload.original_planned_times ?? (item.payload.planned_at ? [item.payload.planned_at] : [])
  const budget = item.payload.budget as Record<string, unknown> | undefined
  return <article className={`rounded-lg border p-3 ${item.read_at ? 'border-slate-200 bg-slate-50' : 'border-teal-200 bg-teal-50'}`}>
    <div className="flex items-start justify-between gap-2"><div><p className="text-sm font-medium">{item.payload.title ?? (item.kind === 'BUDGET' ? '订阅预算监测' : '续费提醒')}</p><p className="mt-1 text-sm">{item.payload.message ?? (budget?.over_budget ? '已知订阅金额超过预算。' : '监测结果已更新，请查看订阅管理。')}</p>{planned.length > 0 && <p className="mt-1 text-xs text-ink-500">{item.payload.catch_up ? '停机补发；原计划时间：' : '原计划提醒时间：'}{planned.map((value) => new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })).join('、')}</p>}<p className="mt-1 text-xs text-ink-500">{item.status === 'INVALIDATED' ? '规则或订阅状态已变化' : item.status === 'RESOLVED' ? '预算状态已恢复至预算内' : '站内提醒'}</p>{item.kind === 'BUDGET' && <Link to="/subscriptions#budget-rules" className="mt-1 inline-block text-xs text-brand-700 underline">查看预算评估和管理选项</Link>}</div>{!item.read_at && <Button size="sm" variant="outline" onClick={onRead}>标为已读</Button>}</div>
  </article>
}

function RuleRow({ title, status, disabled, onCommand, onEdit }: { title: string; status: string; disabled: boolean; onCommand: (command: 'pause' | 'resume' | 'delete') => Promise<unknown>; onEdit?: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function command(value: 'pause' | 'resume' | 'delete') { setBusy(true); setError(''); try { await onCommand(value) } catch (reason) { setError(reason instanceof Error ? reason.message : '规则操作失败') } finally { setBusy(false) } }
  return <article className="rounded-lg bg-slate-50 p-2 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><div><p>{title}</p><p className="text-xs text-ink-500">{status}</p></div><div className="flex flex-wrap gap-1">{onEdit && status !== 'DELETED' && status !== 'EXPIRED' && <Button size="sm" variant="outline" disabled={busy || disabled} onClick={onEdit}>编辑</Button>}{status === 'ACTIVE' ? <Button size="sm" variant="outline" disabled={busy || disabled} onClick={() => void command('pause')}>暂停</Button> : status === 'PAUSED' ? <Button size="sm" variant="outline" disabled={busy || disabled} onClick={() => void command('resume')}>恢复</Button> : null}{status !== 'DELETED' && status !== 'EXPIRED' && <Button size="sm" variant="outline" disabled={busy || disabled} onClick={() => void command('delete')}>删除</Button>}</div></div>{error && <p role="alert" className="mt-1 text-xs text-red-700">{error}</p>}</article>
}

function BudgetEvaluation({ value, onCancel }: { value: Record<string, unknown>; onCancel: (id: string) => void }) {
  const suggestions = Array.isArray(value.suggestions) ? value.suggestions as { subscription_id: string; merchant: string; amount: string; demo_cancellable: boolean }[] : []
  return <section aria-label="订阅预算评估" className="space-y-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
    <p>{value.over_budget ? '已知金额已超过预算。' : value.under_budget_confirmed ? '当前数据完整，已知金额未超过预算。' : '当前数据不完整，不能确认预算充足。'}</p>
    <p>已发生 {value.actual_total == null ? '不可用' : formatMoney(String(value.actual_total), 'CNY')} · 后续预计 {formatMoney(String(value.projected_remaining ?? '0'), 'CNY')} · 合计 {value.known_total == null ? '暂不可得' : formatMoney(String(value.known_total), 'CNY')}</p>
    {value.previous_actual_total != null && <p className="text-xs">上月实际订阅扣费 {formatMoney(String(value.previous_actual_total), 'CNY')}</p>}
    {value.complete !== true && <p>数据不完整或存在待复查预测；预测金额可能偏低。</p>}
    {suggestions.map((item) => <div key={item.subscription_id} className="flex flex-wrap items-center justify-between gap-2 rounded bg-white p-2"><span>{item.merchant} · 最多可节省预计 {formatMoney(item.amount, 'CNY')}</span>{item.demo_cancellable && <Button size="sm" variant="destructive" onClick={() => onCancel(item.subscription_id)}>申请取消并确认</Button>}</div>)}
    <p className="text-xs">申请取消会进入既有 Demo Action 确认流程；此处不会直接取消第三方会员。</p>
  </section>
}

function SubscriptionCard({ subscription }: { subscription: Subscription }) {
  const navigate = useNavigate()
  const client = useQueryClient()
  const keys = useRef({ verify: crypto.randomUUID(), ignore: crypto.randomUUID(), cancel: crypto.randomUUID() })
  const command = useMutation({
    mutationFn: (name: 'verify' | 'ignore' | 'cancel') => api.subscriptionCommand(subscription.id, name, keys.current[name]),
    onSuccess: async (result) => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['subscriptions'] }),
        client.invalidateQueries({ queryKey: ['subscription', subscription.id] }),
        client.invalidateQueries({ queryKey: ['subscription-renewals'] }),
      ])
      if (isAction(result)) navigate(`/actions/${result.id}`)
    },
  })
  return <article className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><Link to={`/subscriptions/${subscription.id}`} className="font-medium text-brand-700 hover:underline">{subscription.merchant}</Link><p className="mt-1 text-xs text-ink-500">{cadenceLabel[subscription.cadence]} · 预计 {formatMoney(subscription.expected_amount, 'CNY')} · 下次 {subscription.next_charge_at ?? '—'}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs">{statusLabel[subscription.status]}</span></div>
    <p className="mt-3 text-xs text-ink-500">识别证据 {subscription.occurrence_count ?? 0} 笔 · 金额允许上下浮动 10%</p>
    {subscription.status === 'CANDIDATE' && <div className="mt-3 flex gap-2"><Button size="sm" onClick={() => command.mutate('verify')} disabled={command.isPending}>确认是订阅</Button><Button size="sm" variant="outline" onClick={() => command.mutate('ignore')} disabled={command.isPending}>忽略候选</Button></div>}
    {subscription.status === 'VERIFIED' && <Button className="mt-3" size="sm" variant="destructive" onClick={() => command.mutate('cancel')} disabled={command.isPending}>取消 Demo 订阅</Button>}
    {command.error && <p role="alert" className="mt-2 text-sm text-red-600">{command.error.message}</p>}
  </article>
}

export function SubscriptionDetailPage() {
  const { subscriptionId = '' } = useParams()
  const query = useQuery({ queryKey: ['subscription', subscriptionId], queryFn: () => api.subscription(subscriptionId) })
  if (query.isPending) return <LoadingState label="正在读取订阅证据…" />
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const row = query.data!
  const evidenceLines = subscriptionEvidenceLines(row.evidence)
  return <div className="space-y-4"><div><Link to="/subscriptions" className="text-sm text-brand-700">← 返回订阅管理</Link><h1 className="mt-2 text-xl font-semibold">{row.merchant}</h1><p className="mt-1 text-sm text-ink-500">{statusLabel[row.status]} · {cadenceLabel[row.cadence]} · 仅限 Demo 商户适配器</p></div><section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">识别依据</h2><dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3"><div><dt className="text-ink-500">预计金额</dt><dd>{formatMoney(row.expected_amount, 'CNY')}</dd></div><div><dt className="text-ink-500">下次日期</dt><dd>{row.next_charge_at ?? '—'}</dd></div><div><dt className="text-ink-500">关联流水</dt><dd>{row.occurrences?.length ?? 0} 笔</dd></div></dl><ul className="mt-4 space-y-2 rounded-lg bg-slate-50 p-3 text-sm text-ink-600">{evidenceLines.map((line) => <li key={line}>{line}</li>)}</ul>{Boolean(row.occurrences?.length) && <div className="mt-4"><h3 className="text-sm font-medium">历史扣款</h3><div className="mt-2 divide-y rounded-lg border">{row.occurrences?.map((occurrence, index) => <div key={`${String(occurrence.occurred_on)}-${index}`} className="flex justify-between p-3 text-sm"><span>{String(occurrence.occurred_on ?? '—')}</span><span>{formatMoney(String(occurrence.amount ?? '0'), 'CNY')}</span></div>)}</div></div>}</section></div>
}
