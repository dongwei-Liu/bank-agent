import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import {
  api,
  type OrchestrationNode,
  type OrchestrationTaskStatus,
} from '@/lib/api'
import { formatAccountNo, formatMoney } from '@/lib/format'

const taskStatusLabels: Record<OrchestrationTaskStatus, string> = {
  WAITING_AUTHORIZATION: '等待完整计划授权',
  ACTIVE: '计划已启用',
  PAUSED: '已暂停，已建立的资金预留会保留',
  CANCELLING: '正在释放未使用的资金预留',
  WAITING_USER: '等待人工处理',
  PARTIAL: '部分完成，需要决定剩余步骤',
  SUCCEEDED: '全部完成',
  FAILED: '执行失败',
  CANCELLED: '已取消',
}

const nodeStatusLabels: Record<OrchestrationNode['status'], string> = {
  PENDING: '等待执行',
  WAITING_AUTHORIZATION: '等待授权',
  RUNNING: '处理中',
  RECONCILING: '正在核对结果',
  WAITING_USER: '等待人工处理',
  SUCCEEDED: '已完成',
  FAILED: '明确失败',
  CANCELLED: '已取消',
  SKIPPED: '已跳过',
}

const commandLabels = {
  pause: '暂停计划',
  resume: '恢复计划',
  takeover: '转为人工处理',
  cancel: '取消剩余任务',
} as const

const taskEventLabels: Record<string, string> = {
  TASK_CREATED: '固定生日计划已创建',
  TASK_AUTHORIZED: '完整计划已授权',
  TASK_PAUSED: '计划已暂停',
  TASK_RESUMED: '计划已恢复',
  TASK_TAKEN_OVER: '已转为人工处理',
  TASK_CANCEL_REQUESTED: '已申请安全取消',
  TASK_CANCELLED: '未完成部分已取消',
  TASK_SUCCEEDED: '鲜花和蛋糕任务全部完成',
  NODE_STARTED: '步骤开始处理',
  NODE_SUCCEEDED: '步骤处理完成',
  NODE_FAILED: '步骤明确失败',
  NODE_RECONCILING: '步骤结果需要核对',
  NODE_RETRIED: '失败步骤已申请重试',
  NODE_RECONCILED: '步骤核对完成',
  RESERVATION_HELD: '资金已预留',
  RESERVATION_RELEASED: '未使用的预留资金已释放',
  ORDER_SUCCEEDED: 'Demo 商户订单已完成',
}

function dateTime(value: string | null) {
  if (!value) return '尚未安排'
  return new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
}

function purposeLabel(value: string) {
  return value === 'FLOWER' ? '鲜花' : value === 'CAKE' ? '蛋糕' : '礼物'
}

function statusTone(status: string) {
  if (status === 'SUCCEEDED' || status === 'CONSUMED' || status === 'RELEASED') return 'bg-emerald-50 text-emerald-800'
  if (status === 'FAILED' || status === 'RECONCILING' || status === 'PARTIAL') return 'bg-red-50 text-red-700'
  if (status === 'CANCELLED' || status === 'SKIPPED') return 'bg-slate-100 text-slate-600'
  return 'bg-amber-50 text-amber-800'
}

type TaskMutation =
  | { kind: 'command'; command: 'pause' | 'resume' | 'cancel' | 'takeover'; key: string }
  | { kind: 'retry'; nodeId: string; key: string }
  | { kind: 'reconcile'; nodeId: string; key: string }

export function TaskPage() {
  const { taskId = '' } = useParams()
  const client = useQueryClient()
  const query = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.task(taskId),
    retry: false,
  })
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts, retry: false })
  const mutate = useMutation({
    mutationFn: (operation: TaskMutation) => {
      if (operation.kind === 'command') {
        return api.taskCommand(taskId, operation.command, operation.key)
      }
      if (operation.kind === 'retry') {
        return api.retryTaskNode(taskId, operation.nodeId, operation.key)
      }
      return api.reconcileTaskNode(taskId, operation.nodeId, operation.key)
    },
    onSuccess: (task) => {
      client.setQueryData(['task', taskId], task)
      void client.invalidateQueries({ queryKey: ['tasks'] })
      void client.invalidateQueries({ queryKey: ['accounts'] })
      if (task.authorization?.action_id) {
        void client.invalidateQueries({ queryKey: ['action', task.authorization.action_id] })
      }
    },
  })

  if (query.isPending) return <LoadingState label="正在读取生日任务…" />
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} unavailableWhenMissing />

  const task = query.data
  const account = accounts.data?.find((item) => item.id === task.from_account_id)
  const runCommand = (command: 'pause' | 'resume' | 'cancel' | 'takeover') => {
    mutate.mutate({ kind: 'command', command, key: crypto.randomUUID() })
  }
  const runNode = (kind: 'retry' | 'reconcile', nodeId: string) => {
    mutate.mutate({ kind, nodeId, key: crypto.randomUUID() })
  }

  return <div className="mx-auto max-w-4xl space-y-4">
    <header className="space-y-1">
      <p className="text-sm text-brand-700">固定生日礼物任务</p>
      <h1 className="text-2xl font-semibold">{task.event.label}</h1>
      <p className="text-sm text-ink-500">事件日期 {task.event.event_date} · 任务编号 {task.id}</p>
    </header>

    <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
      <p className="font-semibold">演示边界</p>
      <p className="mt-1">该任务只会按固定白名单流程向 Fineract 演示花店和蛋糕店付款。它不会访问真实外部商户，也不能由模型添加任意步骤。</p>
    </section>

    <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-ink-500">当前状态</p>
          <p className="mt-1 text-lg font-semibold">{taskStatusLabels[task.status]}</p>
          <p className="mt-1 text-sm text-ink-500">下次计划处理：{dateTime(task.next_run_at)}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusTone(task.status)}`}>{task.status}</span>
      </div>
      <dl className="mt-4 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-3">
        <div><dt className="text-xs text-ink-500">完整计划金额</dt><dd className="mt-1 font-semibold">{formatMoney(task.total_amount, task.currency)}</dd></div>
        <div><dt className="text-xs text-ink-500">付款账户</dt><dd className="mt-1 font-semibold">{account ? `${account.product_name} · ${formatAccountNo(account.account_no)}` : accounts.isError ? '账户信息暂不可用' : '正在读取账户…'}</dd></div>
        <div><dt className="text-xs text-ink-500">授权风险级别</dt><dd className="mt-1 font-semibold">RED · 必须确认并完成 OTP</dd></div>
      </dl>

      {task.authorization && <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm">
        <p className="font-medium">完整计划授权：{task.authorization.status}</p>
        <p className="mt-1 text-xs text-slate-600">授权完成前不会建立资金 Hold，也不会向 Demo 商户付款。</p>
        <Link className="mt-2 inline-block text-brand-700 underline" to={`/actions/${encodeURIComponent(task.authorization.action_id)}`}>核对并完成确认 / OTP</Link>
      </div>}

      {task.error_code && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">任务未能继续自动处理。请查看下方失败或核对中的步骤，并选择服务端允许的恢复方式。</p>}
      {mutate.error && <ErrorState error={mutate.error} />}
      {task.allowed_commands.length > 0 && <div className="mt-4 flex flex-wrap gap-2">
        {task.allowed_commands.map((command) => <Button
          key={command}
          size="sm"
          variant={command === 'cancel' ? 'destructive' : command === 'takeover' ? 'outline' : 'default'}
          disabled={mutate.isPending}
          onClick={() => runCommand(command)}
        >{commandLabels[command]}</Button>)}
      </div>}
    </section>

    <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
      <h2 className="font-semibold">执行步骤</h2>
      <p className="mt-1 text-sm text-ink-500">顺序固定为计划核对、完整授权、两项资金预留、提前两天购买、完成通知。</p>
      <ol className="mt-4 space-y-3">
        {task.nodes.map((node, index) => <li key={node.id} className="rounded-xl border border-slate-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3"><span className="grid size-7 place-items-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">{index + 1}</span><p className="font-medium">{node.label}</p></div>
            <span className={`rounded-full px-2.5 py-1 text-xs ${statusTone(node.status)}`}>{nodeStatusLabels[node.status]}</span>
          </div>
          <div className="mt-2 grid gap-1 pl-10 text-xs text-slate-500 sm:grid-cols-3">
            <span>计划时间：{dateTime(node.scheduled_at)}</span>
            {Number(node.amount) > 0 && <span>金额：{formatMoney(node.amount, task.currency)}</span>}
            <span>已尝试：{node.attempts} 次</span>
          </div>
          {node.status === 'FAILED' && <Button className="ml-10 mt-3" size="sm" variant="outline" disabled={mutate.isPending} onClick={() => runNode('retry', node.id)}>重试此步骤</Button>}
          {node.status === 'RECONCILING' && <Button className="ml-10 mt-3" size="sm" disabled={mutate.isPending} onClick={() => runNode('reconcile', node.id)}>只读核对结果</Button>}
        </li>)}
      </ol>
    </section>

    <div className="grid gap-4 md:grid-cols-2">
      <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
        <h2 className="font-semibold">资金预留</h2>
        <p className="mt-1 text-xs text-slate-500">Hold 不会改变账面余额，但会减少可用余额；取消时只释放尚未消费的部分。</p>
        <div className="mt-3 space-y-2">{task.reservations.map((item) => <div key={item.id} className="flex items-center justify-between rounded-lg bg-slate-50 p-3 text-sm">
          <div><p className="font-medium">{purposeLabel(item.purpose)}</p><p className="text-xs text-slate-500">{formatMoney(item.amount, item.currency)}</p></div>
          <span className={`rounded-full px-2 py-1 text-xs ${statusTone(item.status)}`}>{item.status}</span>
        </div>)}</div>
      </section>
      <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
        <h2 className="font-semibold">Demo 商户订单</h2>
        <p className="mt-1 text-xs text-slate-500">仅在购买节点到期且资金释放成功后，才会向对应 Fineract Demo 商户账户转账。</p>
        <div className="mt-3 space-y-2">{task.orders.map((item) => {
          const node = task.nodes.find((candidate) => candidate.id === item.node_id)
          return <div key={item.id} className="flex items-center justify-between rounded-lg bg-slate-50 p-3 text-sm">
            <div><p className="font-medium">{node?.label ?? '礼物订单'}</p><p className="text-xs text-slate-500">{formatMoney(item.amount, item.currency)}</p></div>
            <span className={`rounded-full px-2 py-1 text-xs ${statusTone(item.status)}`}>{item.status}</span>
          </div>
        })}</div>
      </section>
    </div>

    <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
      <h2 className="font-semibold">任务记录</h2>
      <ol className="mt-3 space-y-2">{task.events.map((event) => <li key={event.id} className="flex items-start justify-between gap-3 border-b border-slate-100 py-2 text-sm last:border-0">
        <span>{taskEventLabels[event.type] ?? '任务状态已更新'}</span><time className="shrink-0 text-xs text-slate-500">{dateTime(event.created_at)}</time>
      </li>)}</ol>
      {!task.events.length && <p className="mt-3 text-sm text-slate-500">尚无任务记录。</p>}
    </section>
  </div>
}
