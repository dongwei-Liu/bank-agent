import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { EmptyState, ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import { api, type JsonObject } from '@/lib/api'

const read = (row: JsonObject, ...keys: string[]) => {
  for (const key of keys) if (row[key] != null) return String(row[key])
  return '—'
}

function productFromRecommendation(row: JsonObject) {
  return row.product && typeof row.product === 'object'
    ? row.product as JsonObject
    : row
}

function termUnit(product: JsonObject) {
  const value = product.minDepositTermType
  const id = value && typeof value === 'object'
    ? Number((value as JsonObject).id)
    : Number(product.minDepositTermTypeId)
  return id === 0 ? '天' : id === 1 ? '周' : id === 3 ? '年' : '个月'
}

function demoAnnualRate(product: JsonObject) {
  const active = product.activeChart
  const charts = active && typeof active === 'object'
    ? [active as JsonObject]
    : Array.isArray(product.interestRateCharts)
      ? product.interestRateCharts as JsonObject[]
      : []
  const slabs = charts.flatMap((chart) => Array.isArray(chart.chartSlabs)
    ? chart.chartSlabs as JsonObject[]
    : [])
  const rates = [...new Set(slabs.map((slab) => read(slab, 'annualInterestRate')).filter((rate) => rate !== '—'))]
  return rates.length === 1 ? `${rates[0]}%` : rates.length ? `${rates.join('–')}%` : '以核心银行计算为准'
}

export function WealthPage() {
  const navigate = useNavigate()
  const products = useQuery({ queryKey: ['investment-products'], queryFn: api.products })
  const holdings = useQuery({ queryKey: ['holdings'], queryFn: api.holdings })
  const assessments = useQuery({ queryKey: ['risk-assessments'], queryFn: api.assessments, refetchInterval: 30_000 })
  const [amount, setAmount] = useState('1000')
  const [months, setMonths] = useState('3')
  const [liquidity, setLiquidity] = useState(false)
  const [selected, setSelected] = useState<number[]>([])
  const recommendations = useMutation({ mutationFn: () => api.recommendations(amount, Number(months), liquidity) })
  const comparison = useMutation({ mutationFn: () => api.compareProducts(selected) })

  if (products.isPending || holdings.isPending) return <LoadingState label="正在读取定存与持有…" />
  if (products.error || holdings.error) {
    return <ErrorState error={products.error ?? holdings.error} onRetry={() => { void products.refetch(); void holdings.refetch() }} />
  }

  const freshAssessment = assessments.data?.find((row) =>
    row.purpose === 'subscription'
    && !row.used_at
    && !row.action_id
    && new Date(String(row.expires_at)).getTime() > assessments.dataUpdatedAt,
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">定存与财富</h1>
          <p className="mt-1 text-sm text-ink-500">产品和持有状态来自 Fineract。当前利率为比赛 Demo 配置，推荐不构成投资建议。</p>
        </div>
        <Button variant="outline" onClick={() => navigate('/wealth/risk-assessment')}>本次申购测评</Button>
      </div>

      <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
        <h2 className="font-semibold">本次申购测评</h2>
        <p className="mt-2 text-sm text-ink-500">
          {freshAssessment
            ? `已有未使用的 15 分钟测评，风险等级 ${read(freshAssessment, 'level')}；申购一次后即失效。`
            : '当前没有可用于申购的测评；每笔申购前都需要重新完成。'}
        </p>
      </section>

      <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
        <h2 className="font-semibold">适配推荐</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <input className="input max-w-40" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="金额" />
          <input aria-label="期限（月）" className="input max-w-32" type="number" min="1" max="120" value={months} onChange={(event) => setMonths(event.target.value)} />
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={liquidity} onChange={(event) => setLiquidity(event.target.checked)} />需要流动性</label>
          <Button onClick={() => recommendations.mutate()} disabled={!freshAssessment || recommendations.isPending}>获取推荐</Button>
        </div>
        {!freshAssessment && <p className="mt-2 text-sm text-amber-700">先完成本次风险测评，系统才能做适当性匹配。</p>}
        {recommendations.data && (
          <div className="mt-3 space-y-2">
            {recommendations.data.length ? recommendations.data.map((row) => {
              const product = productFromRecommendation(row)
              return (
                <div key={read(product, 'id', 'name')} className="rounded-lg bg-brand-50 p-3 text-sm">
                  <p className="font-medium">匹配产品：{read(product, 'name', 'id')}</p>
                  <p className="mt-1 text-ink-500">Demo 年利率 {read(row, 'annual_interest_rate')}% · 预估利息 ¥{read(row, 'estimated_interest')} · {read(row, 'reason')}</p>
                </div>
              )
            }) : <p className="text-sm text-ink-500">当前条件下没有匹配产品。</p>}
          </div>
        )}
        {recommendations.error && <p className="mt-2 text-sm text-red-600">{recommendations.error.message}</p>}
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">定存产品</h2>
          <Button size="sm" variant="outline" disabled={selected.length < 2 || comparison.isPending} onClick={() => comparison.mutate()}>比较已选 {selected.length} 项</Button>
        </div>
        {comparison.data && (
          <div aria-label="产品比较结果" className="mb-3 grid gap-2 md:grid-cols-2">
            {comparison.data.map((product) => <ProductFacts key={read(product, 'id')} product={product} compact />)}
          </div>
        )}
        {products.data?.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {products.data.map((product) => (
              <div key={read(product, 'id')}>
                <label className="mb-1 flex items-center gap-2 text-xs text-ink-500">
                  <input type="checkbox" aria-label={`${read(product, 'name')} 加入比较`} checked={selected.includes(Number(product.id))} onChange={(event) => setSelected((old) => event.target.checked ? [...old, Number(product.id)] : old.filter((id) => id !== Number(product.id)))} />
                  加入比较
                </label>
                <ProductCard product={product} assessmentId={freshAssessment ? String(freshAssessment.id) : undefined} />
              </div>
            ))}
          </div>
        ) : <EmptyState title="暂无可用产品" description="核心银行当前未返回定存产品。" />}
      </section>

      <section>
        <h2 className="mb-3 font-semibold">我的持有</h2>
        {holdings.data?.length
          ? <div className="grid gap-3 md:grid-cols-2">{holdings.data.map((holding) => <HoldingCard key={read(holding, 'id')} holding={holding} />)}</div>
          : <EmptyState title="暂无定存持有" description="申购成功后将在这里显示真实持有账户。" />}
      </section>
    </div>
  )
}

function ProductFacts({ product, compact = false }: { product: JsonObject; compact?: boolean }) {
  const suitability = product.suitability && typeof product.suitability === 'object'
    ? product.suitability as JsonObject
    : null
  const term = read(product, 'minDepositTerm')
  const maxTerm = read(product, 'maxDepositTerm')
  const termText = term === maxTerm ? `${term} ${termUnit(product)}` : `${term}–${maxTerm} ${termUnit(product)}`
  return (
    <div className={compact ? 'rounded-lg bg-brand-50 p-3 text-sm' : 'mt-3 grid grid-cols-2 gap-2 text-sm text-ink-600'}>
      {compact && <p className="font-medium text-ink-900">{read(product, 'name')}</p>}
      <p>Demo 年利率：{demoAnnualRate(product)}</p>
      <p>期限：{termText}</p>
      <p>金额：¥{read(product, 'minDepositAmount')}–¥{read(product, 'maxDepositAmount')}</p>
      <p>提前支取：{suitability?.allows_premature ? '支持整笔申请' : '不支持'}</p>
    </div>
  )
}

function ProductCard({ product, assessmentId }: { product: JsonObject; assessmentId?: string }) {
  const navigate = useNavigate()
  const client = useQueryClient()
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts })
  const [open, setOpen] = useState(false)
  const [accountId, setAccountId] = useState('')
  const [amount, setAmount] = useState('')
  const [months, setMonths] = useState(read(product, 'minDepositTerm'))
  const key = useRef(crypto.randomUUID())
  const subscribe = useMutation({
    mutationFn: () => api.subscribe({ product_id: Number(product.id), from_account_id: Number(accountId), amount, term_months: Number(months), assessment_id: assessmentId }, key.current),
    onSuccess: async (action) => {
      await client.invalidateQueries({ queryKey: ['risk-assessments'] })
      navigate(`/actions/${action.id}`)
    },
  })

  return (
    <article className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
      <p className="font-medium">{read(product, 'name', 'shortName')}</p>
      <p className="mt-1 text-xs text-ink-500">产品 #{read(product, 'id')} · 低风险 Demo 定存 · 数据来自 Fineract</p>
      <ProductFacts product={product} />
      <Button onClick={() => assessmentId ? setOpen((value) => !value) : navigate('/wealth/risk-assessment')} className="mt-3 bg-brand-600">{assessmentId ? '申购' : '先完成本次测评'}</Button>
      {open && (
        <form onSubmit={(event) => { event.preventDefault(); subscribe.mutate() }} className="mt-4 space-y-2 border-t pt-4">
          <select aria-label="付款账户" className="input" value={accountId} onChange={(event) => setAccountId(event.target.value)} required>
            <option value="">付款账户</option>
            {accounts.data?.map((account) => <option value={account.id} key={account.id}>{account.product_name} · ¥{account.available_balance}</option>)}
          </select>
          <input className="input" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="申购金额" inputMode="decimal" required />
          <input aria-label="申购期限（月）" className="input" value={months} onChange={(event) => setMonths(event.target.value)} type="number" min="1" max="120" placeholder="期限（月）" required />
          <Button type="submit" disabled={subscribe.isPending}>进入安全确认</Button>
          {subscribe.error && <p className="text-sm text-red-600">{subscribe.error.message}</p>}
        </form>
      )}
    </article>
  )
}

function HoldingCard({ holding }: { holding: JsonObject }) {
  const navigate = useNavigate()
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts })
  const [accountId, setAccountId] = useState('')
  const [quote, setQuote] = useState<JsonObject | null>(null)
  const key = useRef(crypto.randomUUID())
  const quoteRequest = useMutation({ mutationFn: () => api.redemptionQuote(Number(holding.id), Number(accountId)), onSuccess: setQuote })
  const redeem = useMutation({ mutationFn: () => api.redeem({ holding_id: Number(holding.id), to_account_id: Number(accountId), quote_hash: String(quote?.quote_hash) }, key.current), onSuccess: (action) => navigate(`/actions/${action.id}`) })
  return (
    <article className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
      <p className="font-medium">{read(holding, 'depositProductName', 'productName')}</p>
      <p className="mt-2 text-xl font-semibold">¥{read(holding, 'depositAmount')}</p>
      <p className="mt-1 text-xs text-ink-500">状态：{read((holding.status as JsonObject) ?? {}, 'value')} · 到期：{read(holding, 'maturityDate')}</p>
      <div className="mt-3 flex gap-2">
        <select className="input" value={accountId} onChange={(event) => { setAccountId(event.target.value); setQuote(null) }}>
          <option value="">选择赎回入账账户</option>
          {accounts.data?.map((account) => <option key={account.id} value={account.id}>{account.product_name}</option>)}
        </select>
        <Button variant="outline" disabled={!accountId || quoteRequest.isPending} onClick={() => quoteRequest.mutate()}>获取报价</Button>
      </div>
      {quote && (
        <div className="mt-3 rounded-lg bg-brand-50 p-3 text-sm">
          <p>预计到账 ¥{read(quote, 'estimated_amount')}</p>
          <p className="text-xs text-ink-500">报价日期 {read(quote, 'date')}，提交前会再次核对。</p>
          <Button className="mt-2 bg-brand-600" disabled={redeem.isPending} onClick={() => redeem.mutate()}>进入赎回确认</Button>
        </div>
      )}
      {(quoteRequest.error || redeem.error) && <p className="mt-2 text-sm text-red-600">{(quoteRequest.error ?? redeem.error)?.message}</p>}
    </article>
  )
}
