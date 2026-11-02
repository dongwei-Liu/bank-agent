import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { EmptyState, ErrorState, LoadingState } from '@/components/page-state'
import { api, ApiError, type JsonObject } from '@/lib/api'
import { anomalyEvidenceText, anomalyStatusLabel, anomalyTitle, EMPTY_ANOMALIES_TEXT } from '@/lib/evidence'
import { formatAccountNo, formatMoney } from '@/lib/format'
import { resolveBillPeriod } from '@/lib/bill-period'
import { AnomalyReviewControls } from '@/components/anomaly-review-controls'

export function BillPage() {
  const { period = '' } = useParams()
  const navigate = useNavigate()
  const range = resolveBillPeriod(period)
  const [accountId, setAccountId] = useState('')
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts })
  const selected = accountId ? Number(accountId) : undefined
  const enabled = Boolean(range && accounts.data?.length)
  const stats = useQuery({
    queryKey: ['billing-statistics', selected, range?.fromDate, range?.toDate],
    queryFn: () => api.billingStatistics(selected, range!.fromDate, range!.toDate),
    enabled,
  })
  const anomalies = useQuery({
    queryKey: ['billing-anomalies', selected, range?.fromDate, range?.toDate],
    queryFn: () => api.billingAnomalies(selected, range!.fromDate, range!.toDate),
    enabled,
  })
  const categoryRows = useMemo(
    () => Object.entries(stats.data?.categories ?? {}).sort((a, b) => Number(b[1]) - Number(a[1])),
    [stats.data],
  )
  const monthlyRows = useMemo(
    () => Object.entries(stats.data?.monthly ?? {}).sort(([a], [b]) => a.localeCompare(b)),
    [stats.data],
  )
  const anomalyRows = Array.isArray(anomalies.data) ? anomalies.data : anomalies.data?.items ?? []
  const report = useMutation({ mutationFn: () => api.generateBillReport(selected ?? null, period, crypto.randomUUID()),
    onSuccess: (result) => navigate(`/insights/reports/${result.report_id}`) })

  if (!range) {
    return <EmptyState title="账单期间无效" description="请选择当前或过去的月份、年份，不能查看未来账单。" />
  }
  if (accounts.isPending) return <LoadingState label="正在读取账户…" />
  if (accounts.error) return <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
  if (!accounts.data?.length) return <EmptyState title="暂无账户" description="有账户后才能查看实时账单。" />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-xl font-semibold">{range.label}</h1><p className="mt-1 text-sm text-ink-500">实时读取 Fineract 流水，不使用旧报告快照。</p></div>
        <Link to="/insights" className="text-sm text-brand-700">返回财务洞察</Link>
        <button className="rounded-lg bg-brand-700 px-3 py-2 text-sm text-white disabled:opacity-50" disabled={report.isPending}
          onClick={() => report.mutate()}>{report.isPending ? '正在提交报告…' : '生成完整报告'}</button>
      </div>
      <section className="flex flex-wrap items-center gap-2 rounded-xl bg-white p-4 ring-1 ring-slate-200">
        <Link className="rounded-lg border px-3 py-2 text-sm" to={`/insights/bills/${range.previous}`}>← 上一{range.kind === 'month' ? '月' : '年'}</Link>
        {range.next && <Link className="rounded-lg border px-3 py-2 text-sm" to={`/insights/bills/${range.next}`}>下一{range.kind === 'month' ? '月' : '年'} →</Link>}
        <Link className="rounded-lg border px-3 py-2 text-sm" to={`/insights/bills/${range.kind === 'month' ? range.year : range.month}`}>{range.kind === 'month' ? '查看全年' : '查看当月'}</Link>
        <select className="input ml-auto max-w-xs" value={accountId} onChange={(event) => setAccountId(event.target.value)}>
          <option value="">全部账户</option>
          {accounts.data.map((account) => <option key={account.id} value={account.id}>{account.product_name} · {formatAccountNo(account.account_no)}</option>)}
        </select>
      </section>
      {stats.isPending ? <LoadingState label="正在实时计算账单…" /> : stats.error ? <ErrorState error={stats.error} onRetry={() => void stats.refetch()} /> : stats.data && (
        <>
          <section className="rounded-xl bg-slate-50 p-4 text-xs text-ink-500 ring-1 ring-slate-200">
            <p>查询期间：{range.fromDate} 至 {range.toDate}</p>
            <p>统计范围：{selected === undefined ? `全部 ${stats.data.account_ids.length} 个账户` : '当前账户'} · 共 {stats.data.transaction_count} 笔流水</p>
            <p className="mt-1">数据截止：{new Date(stats.data.data_cutoff).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}（上海时间）· 分类规则：{stats.data.rule_version}</p>
            {!stats.data.snapshot_atomic && <p className="mt-1">提示：核心银行不提供跨页原子快照；查询期间若流水变化，中端会拒绝不完整结果，不会静默漏算。</p>}
          </section>
          <section className="grid gap-3 sm:grid-cols-3">
            <Metric label="收入" amount={stats.data.totals.income ?? '0'} />
            <Metric label="支出" amount={stats.data.totals.expense ?? '0'} />
            <Metric label="对外转账" amount={stats.data.totals.transfer ?? '0'} />
          </section>
          {range.kind === 'year' && (
            <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
              <h2 className="font-semibold">逐月收支明细</h2>
              <div className="mt-3 space-y-2">{monthlyRows.map(([month, totals]) => <div key={month} className="grid grid-cols-1 gap-2 rounded-lg bg-slate-50 p-3 text-sm sm:grid-cols-4"><span>{month}</span><span className="text-emerald-700">收入 {formatMoney(totals.income ?? '0', 'CNY')}</span><span className="text-red-700">消费 {formatMoney(totals.expense ?? '0', 'CNY')}</span><span>对外转账 {formatMoney(totals.transfer ?? '0', 'CNY')}</span></div>)}{monthlyRows.length === 0 && <p className="text-sm text-ink-500">本年度暂无可统计流水</p>}</div>
            </section>
          )}
          <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
            <h2 className="font-semibold">支出分类</h2>
            <div className="mt-3 space-y-3">{categoryRows.map(([name, amount]) => <CategoryBar key={name} name={name} amount={amount} max={Number(categoryRows[0]?.[1] ?? 1)} />)}{categoryRows.length === 0 && <p className="text-sm text-ink-500">本期间暂无支出</p>}</div>
          </section>
        </>
      )}
      {anomalies.isPending ? <LoadingState label="正在核对异常证据…" /> : anomalies.error ? <ErrorState error={anomalies.error} onRetry={() => void anomalies.refetch()} /> : (
        <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
          <h2 className="font-semibold">异常交易候选</h2>
          <p className="mt-1 text-xs text-ink-500">候选只用于提醒，不会自动冻结账户或撤销交易。</p>
          <div className="mt-3 space-y-2">{anomalyRows.map((row) => <AnomalyEvidence key={String(row.anomaly_key)} row={row} />)}{anomalyRows.length === 0 && <p className="text-sm text-ink-500">{EMPTY_ANOMALIES_TEXT}</p>}</div>
        </section>
      )}
      {report.error && <div className="space-y-2"><ErrorState error={report.error} /><Link className="inline-block text-sm text-brand-700 underline" to="/insights/reports">查看报告列表核对处理结果 →</Link>{report.error instanceof ApiError && ['WRITE_RESULT_UNKNOWN', 'NETWORK_ERROR'].includes(report.error.code) && <p className="text-xs text-amber-800">报告生成请求结果尚未确认，请先核对报告列表，再决定是否重新提交。</p>}</div>}
    </div>
  )
}

function Metric({ label, amount }: { label: string; amount: string }) {
  return <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><p className="text-xs text-ink-500">{label}</p><p className="mt-2 text-xl font-semibold">{formatMoney(amount, 'CNY')}</p></div>
}

function CategoryBar({ name, amount, max }: { name: string; amount: string; max: number }) {
  const width = Math.min(100, Math.max(4, Number(amount) / Math.max(max, 1) * 100))
  return <div><div className="flex justify-between text-sm"><span>{name}</span><span>{formatMoney(amount, 'CNY')}</span></div><div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-500" style={{ width: `${width}%` }} /></div></div>
}

function AnomalyEvidence({ row }: { row: JsonObject }) {
  return <article className="rounded-lg bg-amber-50 p-3"><p className="text-sm font-medium">{anomalyTitle(row)} · {anomalyStatusLabel(row.current_review_status ?? row.status)}</p><p className="mt-1 text-xs text-ink-500">{anomalyEvidenceText(row)}</p><AnomalyReviewControls row={row} /></article>
}
