import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState, LoadingState } from '@/components/page-state'
import { api, type JsonObject } from '@/lib/api'
import { anomalyEvidenceText, anomalyStatusLabel, anomalyTitle } from '@/lib/evidence'
import { formatAccountNo, formatMoney } from '@/lib/format'

const object = (value: unknown): JsonObject => value && typeof value === 'object' && !Array.isArray(value) ? value as JsonObject : {}
const array = (value: unknown): JsonObject[] => Array.isArray(value) ? value as JsonObject[] : []
const text = (value: unknown, fallback = '—') => value == null ? fallback : String(value)
const entries = (value: unknown) => Object.entries(object(value)).sort(([a], [b]) => a.localeCompare(b))
const amount = (value: unknown) => value == null ? '无法确认' : formatMoney(String(value), 'CNY')
function shanghaiPeriod() {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' }).formatToParts(new Date())
  return `${parts.find(part => part.type === 'year')?.value}-${parts.find(part => part.type === 'month')?.value}`
}

export function BillReportsPage() {
  const { reportId } = useParams()
  const navigate = useNavigate()
  const client = useQueryClient()
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts })
  const [periodKind, setPeriodKind] = useState<'month' | 'year'>('month')
  const [month, setMonth] = useState(shanghaiPeriod)
  const [year, setYear] = useState(() => shanghaiPeriod().slice(0, 4))
  const [accountId, setAccountId] = useState('')
  const period = periodKind === 'month' ? month : year
  const [summaryPage, setSummaryPage] = useState(1)
  const [historyFrom, setHistoryFrom] = useState('')
  const [historyTo, setHistoryTo] = useState('')
  const [historyStatus, setHistoryStatus] = useState('')
  const [historyAccountId, setHistoryAccountId] = useState('')
  const summaries = useQuery({ queryKey: ['bill-report-summaries', historyFrom, historyTo, historyStatus, historyAccountId, summaryPage],
    queryFn: () => api.billReportSummaries({ period_from: historyFrom || undefined, period_to: historyTo || undefined,
      status: historyStatus || undefined, account_id: historyAccountId ? Number(historyAccountId) : undefined, page: summaryPage }),
    refetchInterval: 5000, staleTime: 0, gcTime: 0 })
  const create = useMutation({ mutationFn: () => api.generateBillReport(accountId ? Number(accountId) : null, period, crypto.randomUUID()),
    onSuccess: async (value) => { await client.invalidateQueries({ queryKey: ['bill-report-summaries'] }); navigate(`/insights/reports/${value.report_id}`) } })
  const regenerate = useMutation({
    mutationFn: ({ period, accountId }: { period: string; accountId: number | null }) => api.generateBillReport(accountId, period, crypto.randomUUID()),
    onSuccess: async (value) => { await client.invalidateQueries({ queryKey: ['bill-report-summaries'] }); navigate(`/insights/reports/${value.report_id}`) },
  })
  const status = useQuery({ queryKey: ['bill-report-status', reportId], queryFn: () => api.billReportStatus(reportId!), enabled: Boolean(reportId),
    refetchInterval: query => ['queued', 'running'].includes(String(query.state.data?.status)) ? 1500 : false, staleTime: 0, gcTime: 0 })
  const detail = useQuery({ queryKey: ['bill-report', reportId], queryFn: () => api.billReport(reportId!), enabled: Boolean(reportId && status.data && !['queued', 'running', 'failed'].includes(status.data.status)), staleTime: 0, gcTime: 0 })
  const [transactionPagination, setTransactionPagination] = useState<{ reportId?: string; page: number }>({ page: 1 })
  const [transactionDirection, setTransactionDirection] = useState('')
  const [transactionCategory, setTransactionCategory] = useState('')
  const [transactionFrom, setTransactionFrom] = useState('')
  const [transactionTo, setTransactionTo] = useState('')
  const transactionPage = transactionPagination.reportId === reportId ? transactionPagination.page : 1
  const changeTransactionPage = (update: (page: number) => number) => setTransactionPagination({ reportId, page: update(transactionPage) })
  const resetTransactionPage = () => setTransactionPagination({ reportId, page: 1 })
  const accountNumbers = new Map((accounts.data ?? []).map(account => [account.id, account.account_no]))
  const tx = useQuery({ queryKey: ['bill-report-transactions', reportId, transactionPage, transactionDirection, transactionCategory, transactionFrom, transactionTo],
    queryFn: () => api.billReportTransactions(reportId!, transactionPage, 50, { direction: transactionDirection || undefined,
      category: transactionCategory || undefined, from_date: transactionFrom || undefined, to_date: transactionTo || undefined }),
    enabled: Boolean(reportId && detail.data && object(detail.data.sections).transactions === 'complete'), staleTime: 0, gcTime: 0 })
  const remove = useMutation({ mutationFn: (id: string) => api.deleteBillReport(id), onSuccess: async (_value, id) => { await client.invalidateQueries({ queryKey: ['bill-report-summaries'] }); if (id === reportId) navigate('/insights/reports') } })

  if (accounts.isPending) return <LoadingState label="正在读取账户…" />
  if (accounts.error) return <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
  if (!accounts.data?.length) return <EmptyState title="暂无账户" description="有账户后才能生成账单报告。" />

  const payload = object(detail.data)
  const periodValue = text(payload.period, '')
  const summary = object(payload.summary)
  const totals = object(summary.totals)
  const sections = object(payload.sections)
  const comparisons = object(payload.comparison)
  const categories = array(summary.categories)
  const categoryOptions = Array.from(new Set(['未分类', ...categories.map(row => text(row.name))])).sort()
  const daily = entries(summary.daily)
  const monthly = entries(summary.monthly)
  const rows = tx.data?.items ?? []
  const reportState = status.data?.status

  return <main className="mx-auto max-w-6xl space-y-4 p-4 pb-24">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-xl font-semibold">账单报告</h1><p className="mt-1 text-sm text-ink-500">保存每次生成时的账单事实、趋势和解读。</p></div><Link to="/insights" className="text-sm text-brand-700">返回账单洞察</Link></div>
    <section className="grid gap-4 rounded-xl bg-white p-4 ring-1 ring-slate-200 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
      <div><h2 className="font-semibold">生成新报告</h2><p className="mt-1 text-xs text-ink-500">每次提交都会保留为一个新版本。</p></div>
      <div className="flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-xs text-ink-500">账户<select className="input min-w-40" value={accountId} onChange={event => setAccountId(event.target.value)}><option value="">本人全部合格账户</option>{accounts.data.map(a => <option key={a.id} value={a.id}>{a.product_name} · 尾号 {formatAccountNo(a.account_no)}</option>)}</select></label>
        <label className="grid gap-1 text-xs text-ink-500">报告周期<select className="input" value={periodKind} onChange={event => setPeriodKind(event.target.value as 'month' | 'year')}><option value="month">月度</option><option value="year">年度</option></select></label>
        {periodKind === 'month' ? <input aria-label="报告月份" className="input" type="month" value={month} onChange={event => setMonth(event.target.value)} /> : <input aria-label="报告年份" className="input w-28" type="number" min="1900" max="9998" value={year} onChange={event => setYear(event.target.value)} />}
        <Button disabled={create.isPending || !period} onClick={() => create.mutate()}>{create.isPending ? '正在提交…' : '生成并保存'}</Button>
        {create.error && <p role="alert" className="w-full text-sm text-red-700">{create.error.message}</p>}
      </div>
    </section>
    {reportId && <section className="space-y-4">
      {status.isPending && <LoadingState label="正在读取报告状态…" />}
      {status.error && <ErrorState error={status.error} onRetry={() => void status.refetch()} />}
      {reportState && ['queued', 'running'].includes(reportState) && <section aria-live="polite" className="rounded-xl bg-white p-5 ring-1 ring-slate-200"><p className="font-medium">{reportState === 'queued' ? '报告正在排队' : '报告正在生成'}</p><progress className="mt-3 w-full" value={status.data?.progress ?? 0} max="100" /><p className="mt-1 text-xs text-ink-500">可离开此页；报告会保存在历史列表中。</p></section>}
      {reportState === 'failed' && <div role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">报告生成失败（{status.data?.error ?? 'REPORT_GENERATION_FAILED'}）。可以重新提交生成新版本。</div>}
      {detail.isPending && reportState && ['complete', 'partial'].includes(reportState) && <LoadingState label="正在读取报告快照…" />}
      {detail.error && <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />}
      {detail.data && <>
        <header className="flex flex-wrap items-start justify-between gap-2 rounded-xl bg-white p-4 ring-1 ring-slate-200"><div><h2 className="text-lg font-semibold">{periodValue.length === 4 ? `${periodValue} 年度报告` : `${periodValue.replace('-', ' 年 ')} 月度报告`}</h2><p className="mt-1 text-xs text-ink-500">{text(payload.from_date)} 至 {text(payload.to_date)} · 实际截止 {text(payload.cutoff_date)}{payload.partial_period === true ? ' · 阶段报告（未结期）' : ''} · {array(payload.account_ids).length} 个账户</p><p className="mt-1 text-xs text-ink-500">{payload.snapshot_atomic === false ? '跨账户流水按顺序读取，报告保存生成时的结果。' : ''} 当前报告范围读取完整；历史已观察 {text(object(payload.historical_coverage).observed_days, '0')} 天。</p></div><div className="flex gap-2"><span className="rounded-full bg-teal-50 px-3 py-1 text-xs">{payload.status === 'partial' ? '部分可用' : '已完成'}</span><Button variant="outline" onClick={() => remove.mutate(reportId!)} disabled={remove.isPending}>删除版本</Button></div></header>
        {payload.schema_version !== 1 && <div className="rounded-xl bg-amber-50 p-4 text-sm">旧版本报告不包含新报告结构，历史快照未重新计算。</div>}
        {payload.schema_version === 1 && <>
          {Number(summary.transaction_count ?? 0) === 0 && <div role="status" className="rounded-xl bg-amber-50 p-4 text-sm text-amber-950">本期未观察到有效流水，无法据此确认收入、消费或净收支金额为零。</div>}
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[['收入', totals.income], ['消费', totals.expense], ['费用', totals.fees], ['对外转账', totals.external_transfer], ['本人账户互转', totals.internal_transfer], ['本金流动', totals.principal_flow], ['净现金流', totals.net_cash_flow]].map(([label, value]) => <div key={String(label)} className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><p className="text-xs text-ink-500">{String(label)}</p><p className="mt-2 text-xl font-semibold">{amount(value)}</p></div>)}</section>
          <section className="grid gap-4 lg:grid-cols-2"><Chart title={periodValue.length === 4 ? '逐月收支趋势' : '每日收支趋势'} values={periodValue.length === 4 ? monthly : daily} /><section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">消费分类占比</h2>{categories.length ? <div className="mt-3 space-y-3">{categories.map(row => <div key={text(row.name)}><div className="flex justify-between gap-3 text-sm"><span>{text(row.name)}</span><span>{amount(row.amount)} · {row.share == null ? '无占比' : `${(Number(row.share) * 100).toFixed(1)}%`}</span></div><div className="mt-1 h-2 rounded bg-slate-100"><div className="h-2 rounded bg-brand-600" style={{ width: `${Math.max(0, Math.min(100, Number(row.share ?? 0) * 100))}%` }} /></div></div>)}</div> : <p className="mt-3 text-sm text-ink-500">本期没有消费分类数据。</p>}</section></section>
          <section className="grid gap-4 lg:grid-cols-2"><section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">收支变化</h2>{Object.entries(comparisons).map(([key, raw]) => { const item = object(raw); const metrics = object(item.metrics); return <div key={key} className="mt-3"><h3 className="text-sm font-medium">{key === 'previous_year' ? '同比' : '环比'} · {text(item.from_date)} 至 {text(item.to_date)}</h3><div className="mt-2 grid grid-cols-2 gap-2">{Object.entries(metrics).map(([name, value]) => { const m = object(value); return <p key={name} className="rounded bg-slate-50 p-2 text-xs">{metricName(name)}：{m.delta == null ? '无法比较' : amount(m.delta)}{m.change_ratio == null ? ` · ${comparisonReason(m.unavailable_reason)}` : ` · ${(Number(m.change_ratio) * 100).toFixed(1)}%`}</p> })}</div></div> })}</section><section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">消费习惯与自然语言解读</h2><p className="mt-2 text-sm">消费 {text(summary.expense_count, '0')} 笔，平均每笔 {amount(summary.average_expense)}。</p><p className="mt-1 text-xs text-ink-500">主要类别：{text(object(summary.habits).top_category, '暂无')} · 工作日 {text(object(object(object(summary.habits).weekday_weekend_expense_count)).weekday, '0')} 笔；周末 {text(object(object(object(summary.habits).weekday_weekend_expense_count)).weekend, '0')} 笔 · 前三类占比 {summary.habits && object(summary.habits).top_three_category_share != null ? `${(Number(object(summary.habits).top_three_category_share) * 100).toFixed(1)}%` : '暂无'}</p>{array(object(payload.narrative).items).map(item => <p key={text(item.code)} className="mt-2 rounded bg-teal-50 p-2 text-sm">{text(item.text)}</p>)}{object(payload.narrative).source === 'template_fallback' && <p className="mt-2 text-xs text-ink-500">采用中端受控解读模板。</p>}</section></section>
          <section className="grid gap-4 lg:grid-cols-2"><section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">异常交易</h2>{sections.anomalies === 'unavailable' ? <p className="mt-2 text-sm text-amber-700">异常检测暂不可用，本报告未将其视为空结果。</p> : array(payload.anomalies).length ? array(payload.anomalies).map(item => <article key={text(item.anomaly_key)} className="mt-2 rounded bg-amber-50 p-3"><p className="font-medium">{anomalyTitle(item)} · {anomalyStatusLabel(item.status)}</p><p className="mt-1 text-xs">{anomalyEvidenceText(item)}</p></article>) : <><p className="mt-2 text-sm text-ink-500">本次报告未返回异常候选。</p><p className="mt-1 text-xs text-ink-500">未返回候选不代表全部交易安全。</p></>}</section><section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">周期性支出</h2>{sections.recurring === 'unavailable' ? <p className="mt-2 text-sm text-amber-700">周期支出识别暂不可用。</p> : array(payload.recurring).length ? array(payload.recurring).map((item, i) => <article key={`${text(item.merchant)}-${i}`} className="mt-2 rounded bg-slate-50 p-3 text-sm"><p>{text(item.merchant)} · {item.cadence === 'YEARLY' ? '年度' : '月度'} · {recurringStatusLabel(item)}</p><p className="mt-1">本期 {array(item.occurrences).length} 笔 · 平均 {amount(item.average_amount)}</p>{item.status === 'VERIFIED' && <p className="mt-1 text-xs text-ink-500">当前核实时间 {text(item.verified_at)}；此状态来自当前记录，不代表报告截止日当时已核实。</p>}</article>) : <p className="mt-2 text-sm text-ink-500">未观察到满足三次稳定扣费门槛的周期支出。</p>}{sections.recurring === 'insufficient_history' && <p className="mt-2 text-xs text-amber-800">当前可用历史跨度约 {text(payload.recurring_coverage_days, '0')} 天；月度候选可按已有证据展示，但历史不足以判断年度周期支出。</p>}</section></section>
          <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-semibold">交易明细</h2><p className="text-xs text-ink-500">快照共 {tx.data?.total ?? text(summary.transaction_count, '0')} 笔，包含供追查的冲正流水。</p></div><div className="flex gap-2"><Button variant="outline" disabled={transactionPage <= 1} onClick={() => changeTransactionPage(p => p - 1)}>上一页</Button><Button variant="outline" disabled={!tx.data || transactionPage * tx.data.page_size >= tx.data.total} onClick={() => changeTransactionPage(p => p + 1)}>下一页</Button></div></div><div className="mt-3 flex flex-wrap gap-2"><label className="grid gap-1 text-xs text-ink-500">方向<select className="input" value={transactionDirection} onChange={event => { resetTransactionPage(); setTransactionDirection(event.target.value) }}><option value="">全部方向</option><option value="debit">支出</option><option value="credit">收入</option><option value="unknown">未知</option></select></label><label className="grid gap-1 text-xs text-ink-500">分类<select className="input" value={transactionCategory} onChange={event => { resetTransactionPage(); setTransactionCategory(event.target.value) }}><option value="">全部分类</option>{categoryOptions.map(category => <option key={category} value={category}>{category}</option>)}</select></label><label className="grid gap-1 text-xs text-ink-500">起始日期<input className="input" type="date" value={transactionFrom} onChange={event => { resetTransactionPage(); setTransactionFrom(event.target.value) }} /></label><label className="grid gap-1 text-xs text-ink-500">结束日期<input className="input" type="date" value={transactionTo} onChange={event => { resetTransactionPage(); setTransactionTo(event.target.value) }} /></label></div>{tx.isPending ? <LoadingState label="正在读取交易快照…" /> : tx.error ? <ErrorState error={tx.error} onRetry={() => void tx.refetch()} /> : <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead><tr className="border-b text-xs text-ink-500"><th className="p-2">日期</th><th className="p-2">账户</th><th className="p-2">方向／类型</th><th className="p-2">商户／分类</th><th className="p-2">核心流水</th><th className="p-2 text-right">金额</th></tr></thead><tbody>{rows.map(row => <tr key={`${text(row.account_id)}-${text(row.transaction_id)}`} className="border-b"><td className="p-2">{text(row.date)}</td><td className="p-2">尾号 {formatAccountNo(text(accountNumbers.get(Number(row.account_id)), ''))}</td><td className="p-2">{text(row.direction)} · {text(row.kind)}{row.reversed === true ? ' · 冲正（不计入统计）' : ''}</td><td className="p-2">{text(row.merchant, '—')} · {text(row.category)}</td><td className="p-2"><Link className="text-brand-700 underline" to={`/accounts/${text(row.account_id)}?transaction=${text(row.transaction_id)}`}>查看 #{text(row.transaction_id)}</Link></td><td className="p-2 text-right">{amount(row.amount)}</td></tr>)}</tbody></table>{rows.length === 0 && <p className="p-3 text-sm text-ink-500">没有符合筛选条件的快照流水。</p>}</div>}</section>
        </>}
      </>}
    </section>}
    <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
      <h2 className="font-semibold">历史报告版本</h2>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-xs text-ink-500">开始期间<input className="input w-36" value={historyFrom} onChange={event => { setSummaryPage(1); setHistoryFrom(event.target.value) }} placeholder="YYYY 或 YYYY-MM" /></label>
        <label className="grid gap-1 text-xs text-ink-500">结束期间<input className="input w-36" value={historyTo} onChange={event => { setSummaryPage(1); setHistoryTo(event.target.value) }} placeholder="YYYY 或 YYYY-MM" /></label>
        <label className="grid gap-1 text-xs text-ink-500">账户<select className="input min-w-40" value={historyAccountId} onChange={event => { setSummaryPage(1); setHistoryAccountId(event.target.value) }}><option value="">全部范围</option>{accounts.data.map(a => <option key={a.id} value={a.id}>{a.product_name} · 尾号 {formatAccountNo(a.account_no)}</option>)}</select></label>
        <label className="grid gap-1 text-xs text-ink-500">状态<select className="input" value={historyStatus} onChange={event => { setSummaryPage(1); setHistoryStatus(event.target.value) }}><option value="">全部状态</option><option value="queued">排队中</option><option value="running">生成中</option><option value="complete">完整</option><option value="partial">部分可用</option><option value="failed">失败</option></select></label>
      </div>
      {regenerate.error && <p role="alert" className="mt-2 text-sm text-red-700">重新生成失败：{regenerate.error.message}</p>}
    {summaries.isPending ? <LoadingState label="正在读取历史报告…" /> : summaries.error ? <ErrorState error={summaries.error} onRetry={() => void summaries.refetch()} /> : summaries.data?.items.length ? <>
      <div className="mt-3 divide-y">{summaries.data.items.map(item => {
        const ids = Array.isArray(item.account_ids) ? item.account_ids.map(Number) : []
        const scope = text(item.account_scope, '')
        const accountId = scope === 'all_accounts' ? null : scope === 'single_account' ? Number(item.scope_account_id) : ids.length === 1 ? ids[0] : null
        const canRegenerate = scope === 'all_accounts' || (scope === 'single_account' && Number.isInteger(accountId)) || (!scope && ids.length > 0)
        return <div key={text(item.id)} className="flex flex-wrap items-center justify-between gap-2 py-3">
          <Link to={`/insights/reports/${text(item.id)}`} className="flex min-w-0 flex-1 flex-wrap justify-between gap-2 text-sm hover:text-brand-700"><span>{text(item.period)} · {text(item.status)} · {text(item.transaction_count, '—')} 笔</span><span className="text-xs text-ink-500">截止 {text(item.cutoff_date)} · {text(item.created_at)}</span></Link>
          <Button variant="outline" onClick={() => regenerate.mutate({ period: text(item.period, ''), accountId })} disabled={regenerate.isPending || !item.period || !canRegenerate}>重新生成</Button>
          <Button variant="outline" onClick={() => remove.mutate(text(item.id))} disabled={remove.isPending}>删除</Button>
        </div>
      })}</div>
      <div className="mt-2 flex items-center justify-between text-xs text-ink-500"><span>共 {summaries.data.total} 个版本 · 第 {summaryPage} 页</span><div className="flex gap-2"><Button variant="outline" disabled={summaryPage <= 1} onClick={() => setSummaryPage(page => page - 1)}>上一页</Button><Button variant="outline" disabled={summaryPage * summaries.data.page_size >= summaries.data.total} onClick={() => setSummaryPage(page => page + 1)}>下一页</Button></div></div>
    </> : <p className="mt-2 text-sm text-ink-500">当前筛选下没有保存的账单报告。</p>}
    </section>
  </main>
}

function metricName(key: string) { return ({ income: '收入', expense: '消费', fees: '费用', external_transfer: '对外转账', net_cash_flow: '净现金流' } as Record<string, string>)[key] ?? key }
function comparisonReason(value: unknown) {
  return ({ baseline_zero: '可比期间该项为零，不计算增长率', no_comparable_transactions: '缺少可比期间流水', no_current_transactions: '本期无有效流水，无法比较' } as Record<string, string>)[String(value)] ?? '缺少可靠可比数据'
}
function recurringStatusLabel(item: JsonObject) {
  if (item.status === 'VERIFIED') return '已核实'
  if (item.status === 'IGNORED') return '已忽略'
  if (item.status === 'CANCELLED') return '已取消'
  return '待核实候选'
}

function Chart({ title, values }: { title: string; values: [string, unknown][] }) {
  const points = values.map(([label, raw], index) => ({ label, income: Number(object(raw).income ?? 0), expense: Number(object(raw).expense ?? 0), index }))
  const max = Math.max(1, ...points.flatMap(row => [row.income, row.expense]))
  const y = (value: number) => 108 - value / max * 90
  const poly = (key: 'income' | 'expense') => points.map(row => `${12 + row.index * (276 / Math.max(1, points.length - 1))},${y(row[key])}`).join(' ')
  return <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">{title}</h2>{points.length ? <><svg role="img" aria-label={title} viewBox="0 0 300 130" className="mt-2 h-40 w-full"><line x1="10" x2="290" y1="110" y2="110" stroke="#cbd5e1" /><polyline fill="none" stroke="#0f766e" strokeWidth="3" points={poly('income')} /><polyline fill="none" stroke="#dc2626" strokeWidth="3" points={poly('expense')} />{points.map((point, index) => <text key={point.label} x={12 + index * (276 / Math.max(1, points.length - 1))} y="126" textAnchor="middle" fontSize="7">{point.label.slice(-5)}</text>)}</svg><p className="text-xs text-ink-500">收入（青绿） · 消费（红色）</p><div className="mt-2 max-h-32 overflow-auto text-xs">{points.map(row => <p key={row.label}>{row.label} · 收入 {amount(row.income)} · 消费 {amount(row.expense)}</p>)}</div></> : <p className="mt-3 text-sm text-ink-500">没有实际流水可绘制趋势。</p>}</section>
}
