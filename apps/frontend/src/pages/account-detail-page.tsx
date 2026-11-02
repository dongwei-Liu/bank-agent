import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import { ApiError, api, type Transaction } from '@/lib/api'
import { invalidateBillingQueries } from '@/lib/billing-query'
import { formatAccountNo, formatMoney } from '@/lib/format'

const messageOf = (error: unknown) => error instanceof Error ? error.message : '操作失败，请刷新后核对。'

export function AccountDetailPage() {
  const id = Number(useParams().accountId)
  const navigate = useNavigate()
  const client = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [page, setPage] = useState(0)
  const [direction, setDirection] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const value = Number(searchParams.get('transaction'))
    return Number.isSafeInteger(value) && value > 0 ? value : null
  })
  const [editing, setEditing] = useState(false)
  const [categoryId, setCategoryId] = useState('')
  const [merchant, setMerchant] = useState('')
  const [note, setNote] = useState('')
  const [notice, setNotice] = useState('')
  const [writeError, setWriteError] = useState('')
  const selectTransaction = (transactionId: number) => {
    setSelectedId(transactionId)
    setEditing(false)
    setNotice('')
    setWriteError('')
    setSearchParams({ transaction: String(transactionId) })
  }
  const closeTransaction = () => {
    setSelectedId(null)
    setEditing(false)
    setSearchParams(params => { params.delete('transaction'); return params })
  }
  const account = useQuery({ queryKey: ['account', id], queryFn: () => api.account(id), enabled: Number.isInteger(id) })
  const transactions = useQuery({ queryKey: ['transactions', id, page, direction, fromDate, toDate], queryFn: () => api.transactions(id, { page, page_size: 20, direction: direction || undefined, from_date: fromDate || undefined, to_date: toDate || undefined }), enabled: Number.isInteger(id) })
  const selected = useQuery({ queryKey: ['transaction', id, selectedId], queryFn: () => api.transaction(id, selectedId!), enabled: selectedId != null })
  const annotations = useQuery({
    queryKey: ['transaction-annotations', id, selectedId],
    queryFn: () => api.transactionAnnotations(id, selectedId!),
    enabled: selectedId != null,
  })
  const categories = useQuery({ queryKey: ['categories'], queryFn: api.categories, enabled: selectedId != null })
  const annotation = annotations.data?.[0]
  const bodyFor = () => ({ account_id: id, transaction_id: selectedId!, category_id: categoryId || null, merchant: merchant.trim() || null, note })
  const save = useMutation({
    mutationFn: () => annotation
      ? api.updateTransactionAnnotation(annotation.id, bodyFor())
      : api.saveTransactionAnnotation(bodyFor()),
    onSuccess: () => {
      setEditing(false)
      setNotice('个人标注已保存，流水、账单统计和异常查询已刷新。')
      setWriteError('')
      invalidateBillingQueries(client)
    },
    onError: (error) => setWriteError(messageOf(error)),
  })
  const clear = useMutation({
    mutationFn: () => api.deleteTransactionAnnotation(annotation!.id),
    onSuccess: () => {
      setEditing(false)
      setNotice('个人标注已清除，已恢复自动分类。')
      setWriteError('')
      invalidateBillingQueries(client)
    },
    onError: (error) => setWriteError(messageOf(error)),
  })
  const writeResultUnknown = [save.error, clear.error].some(error =>
    error instanceof ApiError && ['WRITE_RESULT_UNKNOWN', 'NETWORK_ERROR'].includes(error.code),
  )
  const beginEdit = (transaction: Transaction) => {
    setCategoryId(annotation?.category_id ?? '')
    setMerchant(annotation?.merchant ?? transaction.merchant ?? '')
    setNote(annotation?.note ?? transaction.note ?? '')
    setEditing(true)
    setNotice('')
    setWriteError('')
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate()
  }
  if (account.isPending) return <LoadingState label="正在读取账户详情…" />
  if (account.error) return <ErrorState error={account.error} onRetry={() => void account.refetch()} />
  const data = account.data!
  return <div className="space-y-4">
    <button type="button" onClick={() => navigate('/accounts')} className="flex items-center gap-1 text-sm text-ink-500"><ArrowLeft className="size-4" />返回账户</button>
    <section className="rounded-2xl bg-gradient-to-br from-brand-700 to-brand-500 p-5 text-white"><p className="text-xs text-white/70">{data.product_name} · {data.status}</p><p className="mt-2 text-3xl font-semibold">{formatMoney(data.available_balance, data.currency)}</p><p className="mt-1 text-xs text-white/70">{formatAccountNo(data.account_no)} · 激活于 {data.activated_on ?? '—'}</p></section>
    <section className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <div className="flex flex-wrap gap-2"><select aria-label="流水方向" value={direction} onChange={(e) => { setDirection(e.target.value); setPage(0) }} className="rounded-lg border border-slate-300 px-3 py-2 text-xs"><option value="">全部方向</option><option value="credit">收入</option><option value="debit">支出</option></select><input aria-label="流水开始日期" type="date" value={fromDate} onChange={(e) => { setFromDate(e.target.value); setPage(0) }} className="rounded-lg border border-slate-300 px-3 py-2 text-xs" /><input aria-label="流水结束日期" type="date" value={toDate} onChange={(e) => { setToDate(e.target.value); setPage(0) }} className="rounded-lg border border-slate-300 px-3 py-2 text-xs" /></div>
      <div className="mt-4 divide-y divide-slate-100">{transactions.isPending && <p className="py-6 text-center text-sm text-ink-500">正在读取流水…</p>}{transactions.error && <ErrorState error={transactions.error} onRetry={() => void transactions.refetch()} />}{transactions.data?.items.length === 0 && <EmptyState title="没有符合条件的流水" description="可以调整方向或日期范围后重新查询。" />}{transactions.data?.items.map((item) => <button type="button" onClick={() => selectTransaction(item.transaction_id)} key={item.transaction_id} className="flex w-full items-center justify-between py-3 text-left"><div><p className="text-sm font-medium">{item.merchant || item.category || item.kind}</p><p className="text-xs text-ink-500">{item.date} · {item.note || item.type}</p></div><p className={`font-semibold ${item.direction === 'credit' ? 'text-brand-600' : 'text-ink-900'}`}>{item.direction === 'credit' ? '+' : '-'}{formatMoney(item.amount, item.currency)}</p></button>)}</div>
      {transactions.data && <div className="mt-3 flex items-center justify-between text-xs text-ink-500"><span>共 {transactions.data.total} 笔</span><div className="flex gap-2"><button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="rounded-lg border p-2 disabled:opacity-30"><ChevronLeft className="size-4" /></button><button disabled={(page + 1) * 20 >= transactions.data.total} onClick={() => setPage((p) => p + 1)} className="rounded-lg border p-2 disabled:opacity-30"><ChevronRight className="size-4" /></button></div></div>}
    </section>
    {selectedId != null && <section className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <div className="flex justify-between"><h2 className="font-semibold">单笔流水详情</h2><button type="button" onClick={closeTransaction} className="text-sm text-brand-600">关闭</button></div>
      {selected.isPending ? <p className="text-sm text-ink-500">读取中…</p> : selected.error ? <ErrorState error={selected.error} onRetry={() => void selected.refetch()} /> : selected.data && <>
        <dl className="grid grid-cols-2 gap-3 text-sm"><div><dt className="text-ink-500">流水号</dt><dd>{selected.data.transaction_id}</dd></div><div><dt className="text-ink-500">类型</dt><dd>{selected.data.type}</dd></div><div><dt className="text-ink-500">分类</dt><dd>{selected.data.category}</dd></div><div><dt className="text-ink-500">商户</dt><dd>{selected.data.merchant || '—'}</dd></div><div className="col-span-2"><dt className="text-ink-500">备注</dt><dd>{selected.data.note || '—'}</dd></div></dl>
        {annotations.isPending || categories.isPending ? <LoadingState label="正在读取个人标注…" /> : annotations.error ? <ErrorState error={annotations.error} onRetry={() => void annotations.refetch()} /> : categories.error ? <ErrorState error={categories.error} onRetry={() => void categories.refetch()} /> : <>
          {notice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
          {writeError && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{writeError}{writeResultUnknown ? '结果尚未确认，请刷新此流水核对标注后再操作；不要重复提交。' : ''}</p>}
          {editing ? <form className="space-y-3 rounded-lg bg-slate-50 p-3" onSubmit={submit}>
            <p className="text-sm font-medium">编辑个人标注</p>
            <label className="block text-sm">分类<select aria-label="个人分类" className="input mt-1" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}><option value="">按规则自动分类</option>{categories.data?.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
            <label className="block text-sm">商户<input aria-label="个人商户" className="input mt-1" maxLength={100} value={merchant} onChange={(e) => setMerchant(e.target.value)} /></label>
            <label className="block text-sm">备注<textarea aria-label="个人备注" className="input mt-1 min-h-20" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} /></label>
            <p className="text-xs text-ink-500">仅保存个人分类与备注，不会修改银行原始流水。清除标注可恢复自动规则。</p>
            <div className="flex flex-wrap gap-2"><Button type="submit" disabled={save.isPending}>{save.isPending ? '正在保存…' : '保存标注'}</Button><Button type="button" variant="outline" disabled={save.isPending} onClick={() => setEditing(false)}>取消</Button></div>
          </form> : <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" disabled={annotations.isPending} onClick={() => beginEdit(selected.data!)}>{annotation ? '编辑个人标注' : '修正分类与备注'}</Button>{annotation && <Button type="button" variant="destructive" disabled={clear.isPending} onClick={() => clear.mutate()}>{clear.isPending ? '正在清除…' : '清除全部个人标注'}</Button>}</div>}
        </>}
      </>}
    </section>}
  </div>
}
