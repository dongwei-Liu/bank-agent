import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftRight, ChevronRight, CreditCard, Eye, EyeOff, ReceiptText, ShoppingBag, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/auth-context'
import { ErrorState, LoadingState } from '@/components/page-state'
import { useBalances } from '@/hooks/use-balances'
import { api } from '@/lib/api'
import { formatAccountNo, formatMoney } from '@/lib/format'

export function HomePage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { accounts, summary, total, isPending, error, refetch } = useBalances()
  const actions = useQuery({ queryKey: ['actions'], queryFn: api.actions, staleTime: 15_000 })
  const [hidden, setHidden] = useState(false)
  const pendingActions = (actions.data ?? []).filter((item) => !['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(item.status)).slice(0, 3)
  if (isPending) return <LoadingState label="正在读取本人账户…" />
  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />

  const shortcuts = [
    { label: '转账汇款', icon: ArrowLeftRight, to: '/payments/new' },
    { label: '账户明细', icon: ReceiptText, to: '/accounts' },
    { label: '账单分析', icon: Sparkles, to: '/insights' },
    { label: '定存财富', icon: ChevronRight, to: '/wealth' },
    { label: '银行卡', icon: CreditCard, to: '/cards' },
    { label: 'Demo 商城', icon: ShoppingBag, to: '/demo/merchant' },
  ]
  return <div className="space-y-4">
    <section className="rounded-2xl bg-gradient-to-br from-brand-700 via-brand-600 to-brand-500 p-5 text-white shadow-lg shadow-brand-600/20">
      <div className="flex items-center justify-between"><p className="text-xs text-white/80">你好，{user?.username}</p><button onClick={() => setHidden((v) => !v)} className="flex items-center gap-1 text-xs">{hidden ? <EyeOff className="size-4" /> : <Eye className="size-4" />}{hidden ? '显示' : '隐藏'}</button></div>
      <p className="mt-2 text-3xl font-semibold tabular-nums">{hidden ? '****' : formatMoney(total, summary?.currency ?? 'CNY')}</p>
      <p className="mt-1 text-xs text-white/70">名下账户合计 · {summary?.account_count ?? accounts.length} 个账户</p>
      <div className="mt-4 flex gap-2 border-t border-white/20 pt-3"><button onClick={() => navigate('/payments/new')} className="rounded-full bg-white px-4 py-2 text-xs font-medium text-brand-700">转账</button><button onClick={() => navigate('/accounts')} className="rounded-full border border-white/40 px-4 py-2 text-xs">查看账户</button></div>
    </section>

    <section className="rounded-2xl bg-white p-4 ring-1 ring-slate-200"><h2 className="text-sm font-semibold">快捷办理</h2><div className="mt-3 grid grid-cols-3 gap-3 sm:grid-cols-6">{shortcuts.map(({ label, icon: Icon, to }) => <button key={label} onClick={() => navigate(to)} className="flex flex-col items-center gap-2 text-xs text-ink-700"><span className="flex size-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><Icon className="size-5" /></span>{label}</button>)}</div></section>

    {pendingActions.length > 0 && <section className="rounded-2xl bg-white p-4 ring-1 ring-slate-200"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold">待处理操作</h2><button onClick={() => navigate('/me')} className="text-xs text-brand-600">全部</button></div><div className="mt-3 space-y-2">{pendingActions.map((action) => <button key={action.id} onClick={() => navigate(`/actions/${action.id}`)} className="flex w-full items-center justify-between rounded-xl bg-amber-50 px-3 py-2 text-left text-sm"><span>{action.kind} · ¥{action.amount}</span><span className="text-xs text-amber-700">{action.status}</span></button>)}</div></section>}

    <section className="overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200"><div className="flex items-center justify-between border-b border-slate-100 px-4 py-3"><h2 className="text-sm font-semibold">我的账户</h2><button onClick={() => navigate('/accounts')} className="flex items-center text-xs text-ink-500">全部<ChevronRight className="size-4" /></button></div>{accounts.map((account) => <button key={account.id} onClick={() => navigate(`/accounts/${account.id}`)} className="flex w-full items-center justify-between border-b border-slate-100 px-4 py-3 text-left last:border-0"><div><p className="text-sm font-medium">{account.product_name}</p><p className="text-xs text-ink-500">{formatAccountNo(account.account_no)} · {account.status}</p></div><p className="text-sm font-semibold">{hidden ? '****' : formatMoney(account.available_balance, account.currency)}</p></button>)}</section>
  </div>
}
