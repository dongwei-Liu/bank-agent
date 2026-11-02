import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import { api, type BankingAction } from '@/lib/api'
import { formatMoney } from '@/lib/format'

const FINAL = ['SUCCEEDED', 'FAILED', 'CANCELLED']
const title: Record<string, string> = {
  transfer: '确认转账',
  internal_transfer: '确认本人互转',
  subscription: '确认定存申购',
  subscription_cancel: '确认取消 Demo 订阅',
  card_application: '确认申请借记卡',
  card_activate: '安全激活借记卡',
  card_reveal: '安全查看 Demo 卡号',
  card_controls: '确认卡片设置',
  card_lock: '确认锁定卡片',
  card_unlock: '安全解锁卡片',
  card_report_lost: '确认挂失卡片',
  card_replace: '确认补发卡片',
  card_transaction: '确认 Demo 商户消费',
  redemption: '确认定存赎回',
  schedule_authorization: '确认定时转账',
  orchestration_authorization: '授权生日鲜花与蛋糕计划',
}

const statusLabels: Record<string, string> = {
  WAITING_CONFIRMATION: '等待你确认参数',
  WAITING_VERIFICATION: '需要安全验证码',
  AUTHORIZED: '已授权，等待处理',
  EXECUTING: '正在处理',
  RECONCILING: '正在核对处理结果',
  SUCCEEDED: '操作成功',
  FAILED: '操作失败',
  CANCELLED: '已取消',
}

const statusBadgeLabels: Record<string, string> = {
  WAITING_CONFIRMATION: '待确认',
  WAITING_VERIFICATION: '待验证',
  AUTHORIZED: '已授权',
  EXECUTING: '处理中',
  RECONCILING: '核对中',
  SUCCEEDED: '成功',
  FAILED: '失败',
  CANCELLED: '已取消',
}

export function ActionPage() {
  const { actionId = '' } = useParams()
  const client = useQueryClient()
  const [otp, setOtp] = useState('')
  const [pollTimedOutFor, setPollTimedOutFor] = useState<string | null>(null)
  const pollTimedOut = pollTimedOutFor === actionId
  const action = useQuery({
    queryKey: ['action', actionId],
    queryFn: () => api.action(actionId),
    refetchInterval: (query) =>
      !pollTimedOut && query.state.data && !FINAL.includes(query.state.data.status)
        ? 2000
        : false,
  })
  const stillProcessing = Boolean(
    action.data && !FINAL.includes(action.data.status),
  )

  useEffect(() => {
    if (!stillProcessing) return
    const timeout = window.setTimeout(() => setPollTimedOutFor(actionId), 60_000)
    return () => window.clearTimeout(timeout)
  }, [actionId, stillProcessing])

  const run = useMutation({
    mutationFn: async (command: string) => {
      const current = action.data!
      if (command === 'confirm') return api.confirmAction(current.id, current.request_hash)
      if (command === 'otp') {
        await api.sendOtp(current.id)
        return api.action(current.id)
      }
      if (command === 'verify') return api.verifyAction(current.id, otp)
      if (command === 'cancel') return api.cancelAction(current.id)
      if (command === 'resume') return api.resumeAction(current.id)
      return api.reconcileAction(current.id)
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['action', actionId] })
      void client.invalidateQueries({ queryKey: ['accounts'] })
      void client.invalidateQueries({ queryKey: ['cards'] })
      void client.invalidateQueries({ queryKey: ['card-transactions'] })
      if (action.data?.kind === 'subscription_cancel') {
        void client.invalidateQueries({ queryKey: ['subscriptions'] })
        void client.invalidateQueries({ queryKey: ['subscription'] })
        void client.invalidateQueries({ queryKey: ['subscription-renewals'] })
      }
      if (action.data?.kind === 'orchestration_authorization') {
        const taskId = String(action.data.payload.task_id ?? '')
        if (taskId) void client.invalidateQueries({ queryKey: ['task', taskId] })
        void client.invalidateQueries({ queryKey: ['tasks'] })
      }
    },
  })
  const audit = useQuery({
    queryKey: ['action-audit', actionId],
    queryFn: () => api.actionAudit(actionId),
    enabled: action.data?.status != null,
  })
  const getDevOtp = useMutation({
    mutationFn: () => api.devOtp(actionId),
    onSuccess: (data) => setOtp(data.code),
  })

  if (action.isPending) return <LoadingState label="正在读取操作状态…" />
  if (action.error) return <ErrorState error={action.error} onRetry={() => void action.refetch()} />

  const data = action.data!
  const confirmationExpired = ['WAITING_CONFIRMATION', 'WAITING_VERIFICATION'].includes(data.status)
    && Boolean(data.expires_at && Date.parse(data.expires_at) <= action.dataUpdatedAt)
  const cardId = String(data.payload.card_id ?? '')
  const snapshot = data.payload.subscription_snapshot && typeof data.payload.subscription_snapshot === 'object'
    ? data.payload.subscription_snapshot as Record<string, unknown>
    : data.payload
  const subscriptionCadence = String(snapshot.cadence ?? '')
  const taskId = String(data.payload.task_id ?? '')
  const returnTo = data.kind === 'orchestration_authorization' && taskId
    ? `/tasks/${encodeURIComponent(taskId)}`
    : data.kind === 'subscription_cancel'
    ? '/subscriptions'
    : data.kind === 'card_transaction'
      ? '/demo/merchant'
      : data.kind === 'card_reveal'
        ? `/cards/${cardId}`
        : data.kind.startsWith('card_')
          ? '/cards'
          : ['subscription', 'redemption'].includes(data.kind)
            ? '/wealth'
          : '/payments'

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">{title[data.kind] ?? '操作处理'}</h1>
        <p className="mt-1 text-sm text-ink-500">追踪号 {data.id}</p>
      </div>
      <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
        <Status action={data} />
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div><dt className="text-ink-500">金额</dt><dd className="font-semibold">¥{data.amount}</dd></div>
          <div><dt className="text-ink-500">创建时间</dt><dd>{new Date(data.created_at).toLocaleString()}</dd></div>
        </dl>
        {data.kind === 'subscription_cancel' && (
          <section aria-label="取消确认内容" className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
            <h2 className="font-medium">请核对要取消的 Demo 订阅</h2>
            <dl className="mt-2 grid grid-cols-2 gap-2">
              <div><dt className="text-amber-800">商户</dt><dd>{String(snapshot.merchant ?? '—')}</dd></div>
              <div><dt className="text-amber-800">预计金额</dt><dd>{formatMoney(String(snapshot.expected_amount ?? '0'), 'CNY')}</dd></div>
              <div><dt className="text-amber-800">周期</dt><dd>{subscriptionCadence === 'MONTHLY' ? '每月' : subscriptionCadence === 'YEARLY' ? '每年' : '—'}</dd></div>
              <div><dt className="text-amber-800">预计扣费日</dt><dd>{String(snapshot.next_charge_at ?? '未设置')}</dd></div>
            </dl>
          </section>
        )}
        {data.error_code && (
          <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            处理未完成（{data.error_code}）。如需协助，请提供上方追踪号。
          </p>
        )}
        {confirmationExpired && (
          <div role="alert" className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
            <p>此确认请求已过期，不能继续执行。返回订阅管理后可以重新查看信息并发起新的取消请求。</p>
            {data.kind === 'subscription_cancel' && <Link className="mt-2 inline-block font-medium underline" to="/subscriptions">返回订阅管理并重新申请</Link>}
          </div>
        )}
        {data.kind === 'subscription_cancel' && data.status === 'FAILED' && (
          <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            取消请求已明确失败，订阅未被标记为已取消。返回订阅管理后可重新核对信息并申请；系统不会自动重发。
          </p>
        )}
        {pollTimedOut && stillProcessing && (
          <div className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
            <p>仍在处理中。系统已停止自动刷新，不会重新创建请求。</p>
            <div className="mt-3 flex gap-2">
              <Button variant="outline" onClick={() => void action.refetch()}>手动刷新</Button>
              {data.status === 'RECONCILING' && (
                <Button onClick={() => run.mutate('reconcile')} disabled={run.isPending}>核对处理结果</Button>
              )}
            </div>
          </div>
        )}
        <div className="mt-5 space-y-3">
          {data.status === 'WAITING_CONFIRMATION' && !confirmationExpired && (
            <div className="flex gap-2">
              <Button onClick={() => run.mutate('confirm')} disabled={run.isPending} className="bg-brand-600">确认并继续</Button>
              <Button onClick={() => run.mutate('cancel')} variant="outline">取消操作</Button>
            </div>
          )}
          {data.status === 'WAITING_VERIFICATION' && !confirmationExpired && (
            <>
              <div className="flex gap-2">
                <Button onClick={() => run.mutate('otp')} variant="outline">发送验证码</Button>
                <Button onClick={() => getDevOtp.mutate()} variant="outline">读取开发验证码</Button>
              </div>
              <div className="flex gap-2">
                <input className="input" maxLength={6} inputMode="numeric" placeholder="6 位验证码" value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))} />
                <Button onClick={() => run.mutate('verify')} disabled={otp.length !== 6 || run.isPending} className="bg-brand-600">验证并执行</Button>
              </div>
            </>
          )}
          {['AUTHORIZED', 'EXECUTING'].includes(data.status) && (
            <Button onClick={() => run.mutate('resume')} disabled={run.isPending}>继续处理</Button>
          )}
          {data.status === 'RECONCILING' && !pollTimedOut && (
            <Button onClick={() => run.mutate('reconcile')} disabled={run.isPending}>核对处理结果</Button>
          )}
          {FINAL.includes(data.status) && (
            <Link
              to={returnTo}
              state={data.kind === 'card_reveal' && data.status === 'SUCCEEDED' ? { revealActionId: data.id } : undefined}
              className="inline-flex rounded-lg bg-brand-600 px-4 py-2 text-sm text-white"
            >
              {data.kind === 'card_reveal' && data.status === 'SUCCEEDED'
                ? '查看完整 Demo 卡号'
                : data.kind === 'subscription_cancel' && data.status !== 'SUCCEEDED'
                  ? '重新查看订阅并申请'
                  : data.kind === 'orchestration_authorization'
                    ? '返回生日任务'
                    : '返回业务页面'}
            </Link>
          )}
          {run.error && <p role="alert" className="text-sm text-red-600">{run.error.message}</p>}
        </div>
      </section>
      <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
        <h2 className="font-semibold">操作记录</h2>
        <div className="mt-3 space-y-2">
          {audit.data?.map((row) => (
            <p key={row.id} className="rounded-lg bg-slate-50 p-2 text-xs text-ink-500">
              {row.summary} · {new Date(row.created_at).toLocaleString()}
            </p>
          ))}
          {audit.data?.length === 0 && <p className="text-sm text-ink-500">暂无操作记录</p>}
        </div>
      </section>
    </div>
  )
}

function Status({ action }: { action: BankingAction }) {
  const label = statusLabels[action.status] ?? '状态更新中'
  const badgeLabel = statusBadgeLabels[action.status] ?? '处理中'
  return (
    <div className="flex items-center justify-between">
      <div><p className="text-xs text-ink-500">当前状态</p><p className="mt-1 text-lg font-semibold">{label}</p></div>
      <span className={`rounded-full px-3 py-1 text-xs ${action.status === 'SUCCEEDED' ? 'bg-emerald-50 text-emerald-700' : action.status === 'FAILED' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'}`}>{badgeLabel}</span>
    </div>
  )
}
