import { useQuery } from '@tanstack/react-query'
import { Bell, Bot, CircleCheck, CircleX, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAgent } from '@/agent/agent-context'
import { api, fetchHealth } from '@/lib/api'

/**
 * 顶部品牌栏：仿银行 App 的红色渐变顶栏。
 *
 * 页面跳转全部交给底部导航（`bottom-tab-bar`），顶栏只承担
 * 品牌展示、后端连接状态和 AI 助手搜索框入口。
 */
export function BankHeader() {
  const { openPanel } = useAgent()

  return (
    <header className="sticky top-0 z-30">
      <div className="bg-gradient-to-r from-brand-800 via-brand-600 to-brand-500 px-4 pt-3 pb-4 sm:px-6">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-lg bg-white/15 text-sm font-semibold text-white ring-1 ring-white/30">
              银
            </span>
            <div className="leading-tight">
              <p className="text-base font-semibold tracking-tight text-white">智汇银行</p>
              <p className="text-[11px] text-white/75">AI 智能助理版 · Bank Agent</p>
            </div>
          </div>
          <div className="flex items-center gap-2"><NotificationEntry /><ConnectionBadge /></div>
        </div>

        <button
          type="button"
          onClick={openPanel}
          className="mx-auto mt-3 flex h-10 w-full max-w-6xl items-center gap-2 rounded-full bg-white px-4 text-left text-sm text-ink-500 shadow-sm transition-shadow hover:shadow-md"
        >
          <Bot className="size-4 shrink-0 text-brand-600" />
          <span className="min-w-0 flex-1 truncate">
            向智能助理提问
          </span>
          <span className="shrink-0 rounded-full bg-brand-600 px-2.5 py-1 text-xs text-white">
            打开
          </span>
        </button>
      </div>
    </header>
  )
}

function NotificationEntry() {
  const { data } = useQuery({
    queryKey: ['notification-unread-count'],
    queryFn: api.unreadNotificationCount,
    staleTime: 15_000,
    refetchInterval: 30_000,
    retry: false,
  })
  return <Link to="/subscriptions#notifications" aria-label={`站内提醒，${data?.count ?? 0}条未读`} className="relative flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-xs text-white ring-1 ring-white/25 hover:bg-white/25">
    <Bell className="size-3.5" />提醒
    {Boolean(data?.count) && <span className="rounded-full bg-white px-1.5 py-0.5 text-[10px] font-semibold text-brand-700">{data!.count}</span>}
  </Link>
}

function ConnectionBadge() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    staleTime: 30_000,
    retry: 1,
  })

  if (isPending) {
    return (
      <span className="flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-xs text-white/90 ring-1 ring-white/25">
        <LoaderCircle className="size-3.5 animate-spin" />
        连接中
      </span>
    )
  }

  if (isError || !data) {
    return (
      <span className="flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-xs text-white/90 ring-1 ring-white/25">
        <CircleX className="size-3.5" />
        后端未连接
      </span>
    )
  }

  return (
    <span className="flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-xs text-white/90 ring-1 ring-white/25">
      <CircleCheck className="size-3.5" />
      {data.service} 在线
    </span>
  )
}
