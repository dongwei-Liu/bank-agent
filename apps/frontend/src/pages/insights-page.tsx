import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import { ApiError, api, type ClassificationRule, type JsonObject } from '@/lib/api'
import { invalidateBillingQueries } from '@/lib/billing-query'
import { anomalyEvidenceText, anomalyStatusLabel, anomalyTitle, EMPTY_ANOMALIES_TEXT } from '@/lib/evidence'
import { formatAccountNo, formatMoney, shanghaiDateKey } from '@/lib/format'
import { AnomalyReviewControls } from '@/components/anomaly-review-controls'

type RuleDraft = Omit<ClassificationRule, 'id' | 'user_id'> & { id?: string }
const value = (object: JsonObject | undefined, key: string) => String(object?.[key] ?? '0')
const currentMonth = () => shanghaiDateKey().slice(0, 7)
const firstDay = () => `${currentMonth()}-01`
const today = () => shanghaiDateKey()
const displayError = (error: unknown) => {
  if (error instanceof ApiError && ['WRITE_RESULT_UNKNOWN', 'NETWORK_ERROR'].includes(error.code)) {
    return `${error.message} 操作结果尚未确认，请刷新页面核对后再操作；不要重复提交。`
  }
  return error instanceof Error ? error.message : '操作失败，请刷新后核对。'
}

export function InsightsPage() {
  const client = useQueryClient()
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts })
  const [accountId, setAccountId] = useState('')
  const [fromDate, setFromDate] = useState(firstDay())
  const [toDate, setToDate] = useState(today())
  const selected = accountId ? Number(accountId) : undefined
  const enabled = Boolean(accounts.data?.length)
  const stats = useQuery({ queryKey: ['billing-statistics', selected, fromDate, toDate], queryFn: () => api.billingStatistics(selected, fromDate, toDate), enabled })
  const anomalies = useQuery({ queryKey: ['billing-anomalies', selected, fromDate, toDate], queryFn: () => api.billingAnomalies(selected, fromDate, toDate), enabled })
  const renewals = useQuery({ queryKey: ['subscription-renewals', 3], queryFn: () => api.subscriptionRenewals(3) })
  const categories = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const rules = useQuery({ queryKey: ['classification-rules'], queryFn: api.classificationRules })
  const [categoryName, setCategoryName] = useState('')
  const [editingCategory, setEditingCategory] = useState<{ id: string; name: string } | null>(null)
  const [ruleDraft, setRuleDraft] = useState<RuleDraft>({ category_id: '', field: 'merchant', contains: '', priority: 100 })
  const [notice, setNotice] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  const changed = () => invalidateBillingQueries(client)
  const saveCategory = useMutation({
    mutationFn: () => editingCategory
      ? api.updateCategory(editingCategory.id, editingCategory.name)
      : api.createCategory(categoryName),
    onSuccess: () => {
      setCategoryName('')
      setEditingCategory(null)
      setNotice('分类已保存；实时统计已刷新，历史报告仍保留生成时快照。')
      setErrorMessage('')
      changed()
    },
    onError: (error) => setErrorMessage(displayError(error)),
  })
  const removeCategory = useMutation({
    mutationFn: api.deleteCategory,
    onSuccess: () => { setNotice('分类已删除。'); setErrorMessage(''); changed() },
    onError: (error) => setErrorMessage(displayError(error)),
  })
  const saveRule = useMutation({
    mutationFn: () => {
      const { id, ...body } = ruleDraft
      return id ? api.updateClassificationRule(id, body) : api.createClassificationRule(body)
    },
    onSuccess: () => {
      setRuleDraft({ category_id: '', field: 'merchant', contains: '', priority: 100 })
      setNotice('分类规则已保存；实时统计已刷新，历史报告仍保留生成时快照。')
      setErrorMessage('')
      changed()
    },
    onError: (error) => setErrorMessage(displayError(error)),
  })
  const removeRule = useMutation({
    mutationFn: api.deleteClassificationRule,
    onSuccess: () => { setNotice('分类规则已删除，实时统计已刷新。'); setErrorMessage(''); changed() },
    onError: (error) => setErrorMessage(displayError(error)),
  })
  const categoryRows = useMemo(() => Object.entries((stats.data?.categories as Record<string, unknown> | undefined) ?? {}), [stats.data])
  const anomalyRows = Array.isArray(anomalies.data) ? anomalies.data : anomalies.data?.items ?? []
  const saving = saveCategory.isPending || saveRule.isPending
  if (accounts.isPending) return <LoadingState label="正在读取账户…" />
  if (accounts.error) return <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
  if (!accounts.data?.length) return <EmptyState title="暂无账户" description="有账户后才能生成账单洞察。" />

  return <div className="space-y-4">
    <div><h1 className="text-xl font-semibold">财务洞察</h1><p className="mt-1 text-sm text-ink-500">统计与异常证据均来自真实账户流水。</p></div>
    {notice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
    {errorMessage && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{errorMessage}</p>}
    <section className="space-y-3 rounded-xl bg-teal-50 p-4 text-sm text-teal-900 ring-1 ring-teal-100">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-semibold">订阅续费提醒</h2><p className="mt-1 text-xs text-teal-800">仅显示已核实订阅的预计日期，不代表已发生扣费。</p></div><Link to="/subscriptions" className="font-medium text-teal-800 hover:underline">订阅管理 →</Link></div>
      {renewals.isPending && <LoadingState label="正在读取续费安排…" />}
      {renewals.error && <ErrorState error={renewals.error} onRetry={() => void renewals.refetch()} />}
      {renewals.data && <p className="text-xs text-teal-800">预计范围：{renewals.data.from_date} 至 {renewals.data.to_date}（{renewals.data.timezone}）· 最近扫描：{renewals.data.last_scan_at ? new Date(renewals.data.last_scan_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '尚未扫描'}</p>}
      {renewals.data?.upcoming.map((row) => <Link key={row.id} to={`/subscriptions/${row.id}`} className="flex flex-wrap justify-between gap-1 rounded-lg bg-white/70 px-3 py-2 hover:bg-white"><span>{row.merchant} · 预计 {formatMoney(row.expected_amount, 'CNY')}</span><span>{row.next_charge_at} · {row.cadence === 'MONTHLY' ? '每月' : '每年'}</span></Link>)}
      {renewals.data && renewals.data.upcoming.length === 0 && <p className="text-teal-800">未来三天没有已核实订阅预计续费。</p>}
      {renewals.data?.needs_review.map((row) => <p key={row.id} className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">{row.merchant} 的预计日期 {row.next_charge_at} 已过，建议重新扫描核对；这不表示实际漏扣。</p>)}
    </section>
    <section className="grid gap-3 sm:grid-cols-3"><Link to={`/insights/bills/${currentMonth()}`} className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><p className="font-medium">本月消费统计</p><p className="mt-1 text-sm text-ink-500">查看本月收支、分类和异常证据 →</p></Link><Link to={`/insights/bills/${today().slice(0, 4)}`} className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><p className="font-medium">本年消费统计</p><p className="mt-1 text-sm text-ink-500">按月查看全年统计 →</p></Link><Link to="/insights/reports" className="rounded-xl bg-teal-50 p-4 ring-1 ring-teal-100"><p className="font-medium">月度／年度账单报告</p><p className="mt-1 text-sm text-ink-500">生成并保存完整报告，查看趋势、对比和明细 →</p></Link></section>
    <section className="flex flex-wrap gap-2 rounded-xl bg-white p-4 ring-1 ring-slate-200"><select aria-label="统计账户" className="input max-w-xs" value={accountId} onChange={(e) => setAccountId(e.target.value)}><option value="">全部账户</option>{accounts.data.map((a) => <option key={a.id} value={a.id}>{a.product_name} · {formatAccountNo(a.account_no)}</option>)}</select><input aria-label="统计开始日期" className="input max-w-44" type="date" max={today()} value={fromDate} onChange={(e) => setFromDate(e.target.value)} /><input aria-label="统计结束日期" className="input max-w-44" type="date" max={today()} value={toDate} onChange={(e) => setToDate(e.target.value)} /><Link to="/insights/reports" className="rounded-lg px-3 py-2 text-sm text-brand-700 underline">生成完整报告</Link></section>
    {stats.isPending ? <LoadingState label="正在计算账单…" /> : stats.error ? <ErrorState error={stats.error} onRetry={() => void stats.refetch()} /> : <><p className="text-xs text-ink-500">统计范围：{selected === undefined ? `全部 ${String((stats.data?.account_ids as unknown[])?.length ?? 0)} 个账户` : '当前账户'} · 数据截止 {stats.data?.data_cutoff ? new Date(stats.data.data_cutoff).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '—'}（上海时间）</p><section className="grid gap-3 sm:grid-cols-3"><Metric label="收入" amount={value(stats.data?.totals as JsonObject, 'income')} /><Metric label="支出" amount={value(stats.data?.totals as JsonObject, 'expense')} /><Metric label="对外转账" amount={value(stats.data?.totals as JsonObject, 'transfer')} /></section><section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">支出分类</h2><div className="mt-3 space-y-3">{categoryRows.map(([name, amount]) => <div key={name}><div className="flex justify-between text-sm"><span>{name}</span><span>{formatMoney(String(amount), 'CNY')}</span></div><div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, Math.max(4, Number(amount) / Math.max(...categoryRows.map(([, n]) => Number(n)), 1) * 100))}%` }} /></div></div>)}{!categoryRows.length && <p className="text-sm text-ink-500">本区间暂无支出</p>}</div></section></>}
    <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">异常交易候选</h2><p className="mt-1 text-xs text-ink-500">这是检测证据，不代表已确认欺诈。</p><div className="mt-3 space-y-2">{anomalies.isPending && <LoadingState label="正在检测异常消费…" />}{anomalies.error && <ErrorState error={anomalies.error} onRetry={() => void anomalies.refetch()} />}{!anomalies.isPending && !anomalies.error && anomalyRows.map((row) => <article key={String(row.anomaly_key)} className="rounded-lg bg-amber-50 p-3"><p className="text-sm font-medium">{anomalyTitle(row)} · {anomalyStatusLabel(row.current_review_status ?? row.status)}</p><p className="mt-1 text-xs text-ink-500">{anomalyEvidenceText(row)}{row.observation_kind ? '' : ` · 涉及 ${(row.transaction_ids as unknown[])?.length ?? 0} 笔流水`}</p><AnomalyReviewControls row={row} /></article>)}{!anomalies.isPending && !anomalies.error && anomalyRows.length === 0 && <p className="text-sm text-ink-500">{EMPTY_ANOMALIES_TEXT}</p>}</div></section>
    <section className="grid gap-4 md:grid-cols-2">
      <div className="space-y-3 rounded-xl bg-white p-4 ring-1 ring-slate-200">
        <div><h2 className="font-semibold">个人分类</h2><p className="text-xs text-ink-500">修改后立即影响实时统计与之后生成的报告，历史报告保留原快照。</p></div>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); saveCategory.mutate() }}><input aria-label="新分类名称" className="input min-w-0 flex-1" value={categoryName} onChange={(e) => setCategoryName(e.target.value)} placeholder="新分类名称" /><Button type="submit" disabled={!categoryName.trim() || saving}>添加</Button></form>
        {editingCategory && <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); saveCategory.mutate() }}><input aria-label="编辑分类名称" className="input min-w-0 flex-1" value={editingCategory.name} onChange={(e) => setEditingCategory({ ...editingCategory, name: e.target.value })} /><Button type="submit" disabled={!editingCategory.name.trim() || saving}>保存</Button><Button type="button" variant="outline" onClick={() => setEditingCategory(null)}>取消</Button></form>}
        {categories.isPending ? <LoadingState /> : categories.error ? <ErrorState error={categories.error} onRetry={() => void categories.refetch()} /> : categories.data?.length ? categories.data.map((category) => <div key={category.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 p-2 text-sm"><span>{category.name}</span><div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setEditingCategory({ id: category.id, name: category.name })}>编辑分类</Button><Button size="sm" variant="destructive" disabled={removeCategory.isPending} onClick={() => removeCategory.mutate(category.id)}>删除分类</Button></div></div>) : <p className="text-sm text-ink-500">暂无个人分类</p>}
      </div>
      <div className="space-y-3 rounded-xl bg-white p-4 ring-1 ring-slate-200">
        <div><h2 className="font-semibold">个人分类规则</h2><p className="text-xs text-ink-500">优先级 0–1000，数值越大越先匹配；同优先级按稳定顺序匹配。</p></div>
        <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); saveRule.mutate() }}>
          <select aria-label="规则目标分类" className="input" required value={ruleDraft.category_id} onChange={(e) => setRuleDraft({ ...ruleDraft, category_id: e.target.value })}><option value="">规则目标分类</option>{categories.data?.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select>
          <select aria-label="规则匹配字段" className="input" value={ruleDraft.field} onChange={(e) => setRuleDraft({ ...ruleDraft, field: e.target.value as RuleDraft['field'] })}><option value="merchant">商户</option><option value="note">备注</option><option value="type">交易类型</option></select>
          <input aria-label="规则匹配文字" className="input" value={ruleDraft.contains} onChange={(e) => setRuleDraft({ ...ruleDraft, contains: e.target.value })} placeholder="字段包含文字" required />
          <label className="block text-sm">优先级（0–1000）<input aria-label="规则优先级" className="input mt-1" type="number" min={0} max={1000} value={ruleDraft.priority} onChange={(e) => setRuleDraft({ ...ruleDraft, priority: Number(e.target.value) })} /></label>
          <div className="flex gap-2"><Button type="submit" disabled={!ruleDraft.category_id || !ruleDraft.contains.trim() || saving}>{ruleDraft.id ? '保存规则' : '添加分类规则'}</Button>{ruleDraft.id && <Button type="button" variant="outline" onClick={() => setRuleDraft({ category_id: '', field: 'merchant', contains: '', priority: 100 })}>取消编辑</Button>}</div>
        </form>
        {rules.isPending ? <LoadingState /> : rules.error ? <ErrorState error={rules.error} onRetry={() => void rules.refetch()} /> : rules.data?.length ? rules.data.map((rule) => <article key={rule.id} className="space-y-2 rounded-lg bg-slate-50 p-3 text-sm"><p>{categories.data?.find((category) => category.id === rule.category_id)?.name ?? '未知分类'} · {rule.field === 'merchant' ? '商户' : rule.field === 'note' ? '备注' : '交易类型'}包含“{rule.contains}” · 优先级 {rule.priority}</p><div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setRuleDraft({ id: rule.id, category_id: rule.category_id, field: rule.field, contains: rule.contains, priority: rule.priority })}>编辑规则</Button><Button size="sm" variant="destructive" disabled={removeRule.isPending} onClick={() => removeRule.mutate(rule.id)}>删除规则</Button></div></article>) : <p className="text-sm text-ink-500">暂无分类规则</p>}
      </div>
    </section>
    <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">已生成报告</h2><p className="mt-2 text-sm text-ink-500">报告生成、历史版本和筛选明细集中在报告页。</p><Link to="/insights/reports" className="mt-2 inline-block text-sm text-brand-700 underline">打开月度／年度报告 →</Link></section>
  </div>
}

function Metric({ label, amount }: { label: string; amount: string }) { return <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><p className="text-xs text-ink-500">{label}</p><p className="mt-2 text-xl font-semibold">{formatMoney(amount, 'CNY')}</p></div> }
