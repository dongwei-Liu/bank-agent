import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'

import { ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import { api, ApiError } from '@/lib/api'
import { formatAccountNo, formatMoney } from '@/lib/format'

export function TransferPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const internal = location.pathname === '/payments/internal'
  const suggested = Number((location.state as { fromAccountId?: number } | null)?.fromAccountId)
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts })
  const recipients = useQuery({ queryKey: ['recipients'], queryFn: () => api.recipients(), enabled: !internal })
  const [fromAccountId, setFromAccountId] = useState(Number.isInteger(suggested) ? String(suggested) : '')
  const [recipientId, setRecipientId] = useState('')
  const [toAccountId, setToAccountId] = useState('')
  const [amount, setAmount] = useState('')
  const [remark, setRemark] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const key = useRef(crypto.randomUUID())

  if (accounts.isPending || (!internal && recipients.isPending)) return <LoadingState label="正在准备转账…" />
  if (accounts.error || (!internal && recipients.error)) return <ErrorState error={accounts.error ?? recipients.error} onRetry={() => { void accounts.refetch(); if (!internal) void recipients.refetch() }} />

  const selected = accounts.data?.find((item) => item.id === Number(fromAccountId))
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    const numericAmount = Number(amount)
    if (!fromAccountId || (!internal && !recipientId) || (internal && !toAccountId) || !Number.isFinite(numericAmount) || numericAmount <= 0) return setError(`请选择付款账户、${internal ? '转入账户' : '收款人'}并填写有效金额`)
    if (internal && fromAccountId === toAccountId) return setError('付款账户和转入账户不能相同')
    if (selected && numericAmount > Number(selected.available_balance)) return setError('转账金额不能超过可用余额')
    setSubmitting(true)
    try {
      const action = internal
        ? await api.createInternalTransfer({ from_account_id: Number(fromAccountId), to_account_id: Number(toAccountId), amount, currency: 'CNY', remark }, key.current)
        : await api.createTransfer({ from_account_id: Number(fromAccountId), recipient_id: recipientId, amount, currency: 'CNY', remark }, key.current)
      navigate(`/actions/${action.id}`)
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : '提交失败，请稍后重试')
    } finally { setSubmitting(false) }
  }

  return <div className="mx-auto max-w-2xl space-y-4">
    <div><h1 className="text-xl font-semibold">{internal ? '本人账户互转' : '普通转账'}</h1><p className="mt-1 text-sm text-ink-500">提交后进入安全确认流程，不会在本页直接扣款。</p></div>
    <div className="flex gap-1 rounded-xl bg-white p-1 ring-1 ring-slate-200"><button type="button" onClick={() => navigate('/payments/new')} className={`flex-1 rounded-lg px-3 py-2 text-sm ${!internal ? 'bg-brand-600 text-white' : 'text-ink-500'}`}>转给他人</button><button type="button" onClick={() => navigate('/payments/internal')} className={`flex-1 rounded-lg px-3 py-2 text-sm ${internal ? 'bg-brand-600 text-white' : 'text-ink-500'}`}>本人互转</button></div>
    <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-5 ring-1 ring-slate-200">
      <label className="block text-sm font-medium">付款账户<select className="input mt-1" value={fromAccountId} onChange={(e) => setFromAccountId(e.target.value)}><option value="">请选择</option>{accounts.data?.map((account) => <option key={account.id} value={account.id}>{account.product_name} · {formatAccountNo(account.account_no)} · {formatMoney(account.available_balance, account.currency)}</option>)}</select></label>
      {internal ? <label className="block text-sm font-medium">转入账户<select className="input mt-1" value={toAccountId} onChange={(e) => setToAccountId(e.target.value)}><option value="">请选择</option>{accounts.data?.filter((account) => account.id !== Number(fromAccountId)).map((account) => <option key={account.id} value={account.id}>{account.product_name} · {formatAccountNo(account.account_no)} · {formatMoney(account.available_balance, account.currency)}</option>)}</select></label> : <label className="block text-sm font-medium">收款人<select className="input mt-1" value={recipientId} onChange={(e) => setRecipientId(e.target.value)}><option value="">请选择</option>{recipients.data?.map((recipient) => <option key={recipient.id} value={recipient.id}>{recipient.name}{recipient.alias ? `（${recipient.alias}）` : ''}</option>)}</select></label>}
      <label className="block text-sm font-medium">金额（元）<input className="input mt-1" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" /></label>
      <label className="block text-sm font-medium">备注<input className="input mt-1" value={remark} maxLength={500} onChange={(e) => setRemark(e.target.value)} placeholder="选填" /></label>
      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      <div className="flex gap-2"><Button type="submit" disabled={submitting} className="bg-brand-600 hover:bg-brand-700">{submitting ? '正在创建安全操作…' : '下一步：确认转账'}</Button><Button type="button" variant="outline" onClick={() => navigate('/payments')}>取消</Button></div>
    </form>
  </div>
}
