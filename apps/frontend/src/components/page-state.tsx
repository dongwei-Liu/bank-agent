import { AlertTriangle, LoaderCircle, ServerOff } from 'lucide-react'
import { ApiError } from '@/lib/api'

export function LoadingState({ label = '正在加载…' }: { label?: string }) {
  return <div className="flex items-center justify-center gap-2 rounded-2xl bg-white p-8 text-sm text-ink-500 ring-1 ring-slate-200"><LoaderCircle className="size-4 animate-spin" />{label}</div>
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="rounded-2xl bg-white p-8 text-center ring-1 ring-slate-200"><p className="font-medium text-ink-900">{title}</p><p className="mt-1 text-sm text-ink-500">{description}</p></div>
}

type ErrorStateProps = { error: unknown; onRetry?: () => void; unavailableWhenMissing?: boolean }

export function ErrorState({ error, onRetry, unavailableWhenMissing = false }: ErrorStateProps) {
  const apiError = error instanceof ApiError ? error : null
  const unavailable = apiError?.status === 501 || (unavailableWhenMissing && apiError?.status === 404)
  const title = unavailable
    ? '服务尚未接入'
    : apiError?.code === 'REQUEST_TIMEOUT'
      ? '请求超时'
      : apiError?.code === 'WRITE_RESULT_UNKNOWN'
        ? '操作结果尚未确定'
        : apiError?.status === 403
          ? '没有操作权限'
          : apiError?.status === 404
            ? '没有找到相关内容'
            : apiError?.status === 409
              ? '当前状态已经变化'
              : apiError?.status === 422
                ? '提交内容有误'
                : apiError?.status === 503
                  ? '服务暂时不可用'
                  : '暂时无法完成请求'
  const canRetry = Boolean(onRetry && (!apiError || apiError.retryable))
  return <div className="rounded-2xl border border-red-100 bg-red-50 p-5 text-red-800">
    <div className="flex items-start gap-3">{unavailable ? <ServerOff className="mt-0.5 size-5" /> : <AlertTriangle className="mt-0.5 size-5" />}<div className="flex-1"><p className="font-medium">{title}</p><p className="mt-1 text-sm text-red-700">{apiError?.message || (error instanceof Error ? error.message : '未知错误')}</p>{apiError?.code && <p className="mt-1 text-xs text-red-500">错误码：{apiError.code}</p>}</div></div>
    {canRetry && <button type="button" onClick={onRetry} className="mt-3 rounded-lg bg-white px-3 py-1.5 text-xs font-medium ring-1 ring-red-200">重试</button>}
  </div>
}
