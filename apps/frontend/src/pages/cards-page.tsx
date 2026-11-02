import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CreditCard, LockKeyhole, Plus, ShieldAlert, ShoppingBag, UnlockKeyhole } from 'lucide-react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import { EmptyState, ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import { api, type Card } from '@/lib/api'
import { formatMoney } from '@/lib/format'

export function CardsPage() {
  const navigate = useNavigate()
  const [alias, setAlias] = useState('')
  const applyKey = useRef(crypto.randomUUID())
  const cards = useQuery({ queryKey: ['cards'], queryFn: api.cards, retry: false })
  const apply = useMutation({
    mutationFn: () => api.createCard({ product_name: '智汇借记卡', alias }, applyKey.current),
    onSuccess: (action) => navigate(`/actions/${action.id}`),
  })
  if (cards.isPending) return <LoadingState label="正在读取本人银行卡…" />
  if (cards.error) return <ErrorState error={cards.error} onRetry={() => void cards.refetch()} />
  return <div className="space-y-4">
    <header><h1 className="text-xl font-semibold">我的银行卡</h1><p className="mt-1 text-sm text-ink-500">普通 Demo 借记卡；每张卡绑定一个真实 Fineract CNY 储蓄账户。</p></header>
    <section className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <h2 className="font-semibold">申请普通借记卡</h2>
      <p className="mt-1 text-xs text-ink-500">确认后自动创建零余额账户并生成待激活卡。申请不会扣款，激活必须使用验证码。</p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row"><input className="input flex-1" maxLength={100} placeholder="卡片别名（可选，例如：日常消费）" value={alias} onChange={(event) => setAlias(event.target.value)} /><Button className="bg-brand-600" disabled={apply.isPending} onClick={() => apply.mutate()}><Plus className="mr-1 size-4" />{apply.isPending ? '正在创建申请…' : '申请新卡'}</Button></div>
      {apply.error && <p role="alert" className="mt-2 text-sm text-red-600">{apply.error.message}</p>}
    </section>
    {cards.data?.length === 0 ? <EmptyState title="暂无银行卡" description="提交申请并确认后，待激活卡会显示在这里。" /> : <div className="grid gap-4 sm:grid-cols-2">{cards.data?.map((card) => <CardTile key={card.id} card={card} onOpen={() => navigate(`/cards/${card.id}`)} />)}</div>}
  </div>
}

function CardTile({ card, onOpen }: { card: Card; onOpen: () => void }) {
  return <button onClick={onOpen} className="rounded-2xl bg-gradient-to-br from-navy-800 to-brand-700 p-5 text-left text-white shadow-sm">
    <div className="flex items-start justify-between"><div><p className="font-semibold">{card.alias || card.product_name}</p><p className="mt-1 text-xs text-white/70">{card.product_name}</p></div><CreditCard className="size-6 text-white/70" /></div>
    <p className="mt-7 font-mono text-base tracking-wider">{card.masked_number}</p>
    <div className="mt-4 flex items-end justify-between"><div><p className="text-[10px] text-white/60">关联账户余额</p><p className="font-semibold">{formatMoney(card.available_balance, card.currency)}</p></div><span className="rounded-full bg-white/15 px-2 py-1 text-[10px]">{statusLabel(card.status)}</span></div>
  </button>
}

export function CardDetailPage() {
  const { cardId = '' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const client = useQueryClient()
  const keys = useRef({
    activate: crypto.randomUUID(), reveal: crypto.randomUUID(), limits: crypto.randomUUID(), lock: crypto.randomUUID(),
    unlock: crypto.randomUUID(), 'report-lost': crypto.randomUUID(), replace: crypto.randomUUID(),
  })
  const [revealActionId] = useState(() => String((location.state as { revealActionId?: string } | null)?.revealActionId ?? ''))
  const [revealHidden, setRevealHidden] = useState(false)
  const card = useQuery({ queryKey: ['card', cardId], queryFn: () => api.card(cardId), retry: false })
  const transactions = useQuery({ queryKey: ['card-transactions', cardId], queryFn: () => api.cardTransactions(cardId), retry: false })
  const revealed = useQuery({ queryKey: ['card-reveal', cardId, revealActionId], queryFn: () => api.revealCardNumber(cardId, revealActionId), enabled: Boolean(revealActionId), retry: false })
  type Command = keyof typeof keys.current
  const command = useMutation({
    mutationFn: ({ name, body = {} }: { name: Command; body?: Record<string, unknown> }) => api.cardCommand(cardId, name, body, keys.current[name]),
    onSuccess: (action) => navigate(`/actions/${action.id}`),
  })
  const rename = useMutation({
    mutationFn: (alias: string) => api.renameCard(cardId, alias),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['card', cardId] }); void client.invalidateQueries({ queryKey: ['cards'] }) },
  })
  useEffect(() => {
    if (revealActionId) navigate(location.pathname, { replace: true, state: null })
  }, [location.pathname, navigate, revealActionId])
  useEffect(() => {
    if (!revealed.data) return
    const timeout = window.setTimeout(() => setRevealHidden(true), Math.max(0, Date.parse(revealed.data.expires_at) - Date.now()))
    return () => window.clearTimeout(timeout)
  }, [revealed.data])
  if (card.isPending) return <LoadingState label="正在读取卡片状态…" />
  if (card.error) return <ErrorState error={card.error} onRetry={() => void card.refetch()} />
  const data = card.data!
  return <div className="mx-auto max-w-2xl space-y-4">
    <header><h1 className="text-xl font-semibold">{data.alias || data.product_name}</h1><p className="mt-1 text-sm text-ink-500">{data.masked_number} · 关联账户 #{data.account_id}</p></header>
    <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs text-ink-500">当前状态</p><p className="mt-1 text-lg font-semibold">{statusLabel(data.status)}</p></div><CardStateActions card={data} pending={command.isPending} run={(name) => command.mutate({ name })} /></div>
      {command.error && <p role="alert" className="mt-3 text-sm text-red-600">{command.error.message}</p>}
      <dl className="mt-5 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-ink-500">账户余额</dt><dd className="font-semibold">{formatMoney(data.available_balance, data.currency)}</dd></div><div><dt className="text-ink-500">单笔限额</dt><dd>{formatMoney(data.single_limit, data.currency)}</dd></div><div><dt className="text-ink-500">日累计限额</dt><dd>{formatMoney(data.daily_limit, data.currency)}</dd></div><div><dt className="text-ink-500">境外交易</dt><dd>{data.international_enabled ? '已开启' : '已关闭'}</dd></div></dl>
    </section>
    {revealActionId && <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5"><h2 className="font-semibold text-amber-950">完整 Demo 卡号</h2>{revealed.isPending ? <p className="mt-2 text-sm text-amber-800">正在读取一次性授权结果…</p> : revealed.error ? <p role="alert" className="mt-2 text-sm text-red-700">{revealed.error.message}</p> : revealHidden ? <p className="mt-2 text-sm text-amber-800">已超过 60 秒，卡号已从页面清除。</p> : <><p className="mt-3 font-mono text-lg tracking-wider text-amber-950">{revealed.data?.number.replace(/(.{4})/g, '$1 ').trim()}</p><p className="mt-2 text-xs text-amber-800">最多显示 60 秒；刷新、离开页面或到期后需重新 OTP 验证。</p></>}</section>}
    {!['LOST', 'REPLACED'].includes(data.status) && <CardControls card={data} pending={command.isPending} onSubmit={(body) => command.mutate({ name: 'limits', body })} />}
    <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200"><div className="flex items-center justify-between gap-3"><div><h2 className="font-semibold">Demo 消费记录</h2><p className="mt-1 text-xs text-ink-500">成功消费对应 Fineract 双边转账；拒绝记录不会扣款。</p></div><Button variant="outline" onClick={() => navigate('/demo/merchant')}><ShoppingBag className="mr-1 size-4" />前往 Demo 商城</Button></div>{transactions.isPending ? <p className="mt-3 text-sm text-ink-500">正在读取…</p> : transactions.error ? <p className="mt-3 text-sm text-ink-500">Demo 交易服务仅在开发/演示环境开放。</p> : transactions.data?.length === 0 ? <p className="mt-3 text-sm text-ink-500">暂无消费记录。</p> : <div className="mt-3 space-y-2">{transactions.data?.map((row) => <div key={row.id} className="flex items-center justify-between rounded-xl bg-slate-50 p-3 text-sm"><div><p className="font-medium">{row.merchant_name}</p><p className="text-xs text-ink-500">{row.channel} · {new Date(row.created_at).toLocaleString()}</p>{row.decline_code && <p className="text-xs text-red-600">{row.decline_code}</p>}</div><div className="text-right"><p className="font-semibold">{formatMoney(row.amount, row.currency)}</p><p className={row.status === 'APPROVED' ? 'text-xs text-emerald-700' : row.status === 'DECLINED' ? 'text-xs text-red-600' : 'text-xs text-amber-700'}>{row.status}</p></div></div>)}</div>}</section>
    <AliasEditor card={data} pending={rename.isPending} onSave={(value) => rename.mutate(value)} error={rename.error?.message} />
    <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">卡号仅为比赛 Demo 标识，不是真实支付凭据。完整号码必须通过 OTP 临时查看，不提供 CVV；Demo 商城仅模拟受控商户网络，成功资金事实仍由 Fineract 记录。</p>
  </div>
}

function CardStateActions({ card, pending, run }: { card: Card; pending: boolean; run: (name: 'activate' | 'reveal' | 'lock' | 'unlock' | 'report-lost' | 'replace') => void }) {
  if (card.status === 'PENDING_ACTIVATION') return <Button className="bg-brand-600" disabled={pending} onClick={() => run('activate')}>使用 OTP 激活</Button>
  if (card.status === 'ACTIVE') return <div className="flex flex-wrap gap-2"><Button className="bg-brand-600" disabled={pending} onClick={() => run('reveal')}>安全查看卡号</Button><Button variant="outline" disabled={pending} onClick={() => run('lock')}><LockKeyhole />锁卡</Button><Button variant="destructive" disabled={pending} onClick={() => run('report-lost')}><ShieldAlert />挂失</Button></div>
  if (card.status === 'LOCKED') return <div className="flex gap-2"><Button className="bg-brand-600" disabled={pending} onClick={() => run('unlock')}><UnlockKeyhole />OTP 解锁</Button><Button variant="destructive" disabled={pending} onClick={() => run('report-lost')}><ShieldAlert />挂失</Button></div>
  if (card.status === 'LOST') return <Button className="bg-brand-600" disabled={pending} onClick={() => run('replace')}>OTP 补卡</Button>
  return null
}

function CardControls({ card, pending, onSubmit }: { card: Card; pending: boolean; onSubmit: (body: Record<string, unknown>) => void }) {
  const [singleLimit, setSingleLimit] = useState(card.single_limit)
  const [dailyLimit, setDailyLimit] = useState(card.daily_limit)
  const [channels, setChannels] = useState({ online_enabled: card.online_enabled, pos_enabled: card.pos_enabled, atm_enabled: card.atm_enabled, international_enabled: card.international_enabled })
  return <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200"><h2 className="font-semibold">限额与交易渠道</h2><p className="mt-1 text-xs text-ink-500">降额或关闭渠道只需确认；提额或开启任何渠道必须 OTP。</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-sm">单笔限额<input className="input mt-1 w-full" inputMode="decimal" value={singleLimit} onChange={(event) => setSingleLimit(event.target.value)} /></label><label className="text-sm">日累计限额<input className="input mt-1 w-full" inputMode="decimal" value={dailyLimit} onChange={(event) => setDailyLimit(event.target.value)} /></label></div><div className="mt-4 grid grid-cols-2 gap-2 text-sm">{([['online_enabled', '线上交易'], ['pos_enabled', 'POS 交易'], ['atm_enabled', 'ATM 交易'], ['international_enabled', '境外交易']] as const).map(([key, label]) => <label key={key} className="flex items-center gap-2 rounded-lg bg-slate-50 p-3"><input type="checkbox" checked={channels[key]} onChange={(event) => setChannels({ ...channels, [key]: event.target.checked })} />{label}</label>)}</div><Button className="mt-4 bg-brand-600" disabled={pending} onClick={() => onSubmit({ single_limit: singleLimit, daily_limit: dailyLimit, ...channels })}>提交设置变更</Button></section>
}

function AliasEditor({ card, pending, onSave, error }: { card: Card; pending: boolean; onSave: (alias: string) => void; error?: string }) {
  const [value, setValue] = useState(card.alias)
  return <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200"><h2 className="font-semibold">卡片别名</h2><div className="mt-3 flex gap-2"><input className="input flex-1" maxLength={100} value={value} placeholder="例如：日常消费" onChange={(event) => setValue(event.target.value)} /><Button variant="outline" disabled={pending || value === card.alias} onClick={() => onSave(value)}>保存别名</Button></div>{error && <p role="alert" className="mt-2 text-sm text-red-600">{error}</p>}</section>
}

function statusLabel(status: Card['status']) {
  return { PENDING_ACTIVATION: '待激活', ACTIVE: '正常', LOCKED: '已锁定', LOST: '已挂失', REPLACED: '已补换' }[status]
}
