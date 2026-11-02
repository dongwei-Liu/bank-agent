import { RefreshCw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/page-state'
import { useBalances } from '@/hooks/use-balances'
import { formatAccountNo, formatMoney } from '@/lib/format'

export function AccountsPage() {
  const navigate = useNavigate()
  const { accounts, isPending, error, refetch, refresh } = useBalances()
  if (isPending) return <LoadingState label="正在查询本人账户…" />
  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
  return <div className="space-y-4"><header className="flex items-center justify-between"><div><h1 className="text-lg font-semibold">我的账户</h1><p className="text-xs text-ink-500">仅显示当前登录人的真实账户</p></div><button onClick={refresh} className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs"><RefreshCw className="size-4" />刷新</button></header><nav className="flex gap-2"><button className="rounded-full bg-brand-600 px-4 py-2 text-xs text-white">账户</button><button onClick={() => navigate('/cards')} className="rounded-full bg-white px-4 py-2 text-xs text-ink-600 ring-1 ring-slate-200">银行卡</button></nav>
    {accounts.length === 0 ? <EmptyState title="暂无账户" description="当前用户没有可用的 CNY 储蓄账户。" /> : <div className="grid gap-4 sm:grid-cols-2">{accounts.map((account, index) => <article key={account.id} className={`rounded-2xl p-5 text-white shadow-sm ${index === 0 ? 'bg-gradient-to-br from-brand-700 to-brand-500' : 'bg-gradient-to-br from-navy-800 to-navy-900'}`}><div className="flex items-start justify-between"><div><p className="font-medium">{account.product_name}</p><p className="text-xs text-white/70">{account.client_name} · {account.deposit_type}</p></div><span className="rounded-full bg-white/15 px-2 py-1 text-[10px]">{account.status}</span></div><p className="mt-5 text-2xl font-semibold">{formatMoney(account.available_balance, account.currency)}</p><p className="mt-1 text-xs text-white/70">账号 {formatAccountNo(account.account_no)}</p><div className="mt-5 flex gap-2"><button onClick={() => navigate('/payments/new', { state: { fromAccountId: account.id } })} className="flex-1 rounded-lg bg-white py-2 text-xs font-medium text-brand-700">转账</button><button onClick={() => navigate(`/accounts/${account.id}`)} className="flex-1 rounded-lg border border-white/40 py-2 text-xs">明细</button></div></article>)}</div>}
  </div>
}
