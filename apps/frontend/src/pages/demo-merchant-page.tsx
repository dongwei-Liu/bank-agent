import { useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { CreditCard, ShoppingBag } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { EmptyState, ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { formatMoney } from '@/lib/format'

export function DemoMerchantPage() {
  const navigate = useNavigate()
  const cards = useQuery({ queryKey: ['cards'], queryFn: api.cards, retry: false })
  const merchants = useQuery({ queryKey: ['demo-merchants'], queryFn: api.demoMerchants, retry: false })
  const [cardId, setCardId] = useState('')
  const [merchantId, setMerchantId] = useState('')
  const [amount, setAmount] = useState('')
  const [channel, setChannel] = useState<'ONLINE' | 'POS' | 'ATM'>('ONLINE')
  const [countryCode, setCountryCode] = useState('CN')
  const key = useRef(crypto.randomUUID())
  const activeCards = (cards.data ?? []).filter((card) => card.status === 'ACTIVE')
  const effectiveCardId = cardId || activeCards[0]?.id || ''
  const effectiveMerchantId = merchantId || merchants.data?.[0]?.id || ''

  const purchase = useMutation({
    mutationFn: () => api.createDemoCardTransaction({ card_id: effectiveCardId, merchant_id: effectiveMerchantId, amount, channel, country_code: countryCode }, key.current),
    onSuccess: (action) => navigate(`/actions/${action.id}`),
  })
  if (cards.isPending || merchants.isPending) return <LoadingState label="正在打开 Demo 商城…" />
  if (cards.error) return <ErrorState error={cards.error} onRetry={() => void cards.refetch()} />
  if (merchants.error) return <ErrorState error={merchants.error} onRetry={() => void merchants.refetch()} />
  if (merchants.data?.length === 0) return <EmptyState title="Demo 商户尚未初始化" description="先运行 Fineract Seed 和中端初始化脚本。" />

  const selectedCard = activeCards.find((card) => card.id === effectiveCardId)
  return <div className="mx-auto max-w-2xl space-y-4">
    <header><h1 className="flex items-center gap-2 text-xl font-semibold"><ShoppingBag className="size-5 text-brand-600" />Demo 商城</h1><p className="mt-1 text-sm text-ink-500">用于验证卡片规则和 Fineract 真实双边入账，不连接真实银行卡组织或外部商户。</p></header>
    <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
      <h2 className="font-semibold">发起一笔演示消费</h2>
      {activeCards.length === 0 ? <EmptyState title="没有可交易的卡片" description="请先申请、确认并使用 OTP 激活一张借记卡。" /> : <div className="mt-4 space-y-4">
        <label className="block text-sm">付款卡片<select aria-label="付款卡片" className="input mt-1 w-full" value={effectiveCardId} onChange={(event) => setCardId(event.target.value)}>{activeCards.map((card) => <option key={card.id} value={card.id}>{card.alias || card.product_name} · {card.masked_number} · {formatMoney(card.available_balance, card.currency)}</option>)}</select></label>
        <label className="block text-sm">Demo 商户<select aria-label="Demo 商户" className="input mt-1 w-full" value={effectiveMerchantId} onChange={(event) => setMerchantId(event.target.value)}>{merchants.data?.map((merchant) => <option key={merchant.id} value={merchant.id}>{merchant.name} · {merchant.category}</option>)}</select></label>
        <div className="grid gap-3 sm:grid-cols-3"><label className="text-sm">金额（元）<input aria-label="消费金额（元）" className="input mt-1 w-full" inputMode="decimal" placeholder="例如 25.80" value={amount} onChange={(event) => setAmount(event.target.value)} /></label><label className="text-sm">渠道<select aria-label="交易渠道" className="input mt-1 w-full" value={channel} onChange={(event) => setChannel(event.target.value as typeof channel)}><option value="ONLINE">线上</option><option value="POS">POS</option><option value="ATM">ATM</option></select></label><label className="text-sm">国家/地区代码<input aria-label="国家地区代码" className="input mt-1 w-full uppercase" maxLength={2} value={countryCode} onChange={(event) => setCountryCode(event.target.value.toUpperCase().replace(/[^A-Z]/g, ''))} /></label></div>
        {selectedCard && <p className="rounded-xl bg-slate-50 p-3 text-xs text-ink-500"><CreditCard className="mr-1 inline size-4" />单笔限额 {formatMoney(selectedCard.single_limit, 'CNY')}，日累计限额 {formatMoney(selectedCard.daily_limit, 'CNY')}。中端会在确认时重新校验状态、渠道、限额和余额。</p>}
        <Button className="bg-brand-600" disabled={purchase.isPending || !amount || countryCode.length !== 2} onClick={() => purchase.mutate()}>{purchase.isPending ? '正在创建授权…' : '下一步：确认消费'}</Button>
        {purchase.error && <p role="alert" className="text-sm text-red-600">{purchase.error.message}</p>}
      </div>}
    </section>
    <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">这是醒目标注的比赛 Demo：卡号和商户网络均为模拟；放行后的资金转账、余额和双方流水来自 Apache Fineract。</p>
  </div>
}
