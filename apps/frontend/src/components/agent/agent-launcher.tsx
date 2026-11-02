import { Bot, MessageCircle, X } from 'lucide-react'

import { useAgent } from '@/agent/agent-context'
import { AgentPanel } from '@/components/agent/agent-panel'

/**
 * AI 助手入口：右下角悬浮球 + 展开后的对话面板。
 *
 * 它是全局常驻的——不占用导航位，也不要求用户先进入某个页面，
 * 符合银行 App「悬浮客服」的习惯，同时把「对话式办理」做成第一入口。
 */
export function AgentLauncher() {
  const { open, togglePanel } = useAgent()

  return (
    <>
      {open && <AgentPanel onClose={togglePanel} />}

      <button
        type="button"
        onClick={togglePanel}
        aria-label={open ? '收起智能助理' : '打开智能助理'}
        className="group fixed right-5 bottom-24 z-40 flex size-14 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg shadow-brand-600/30 transition-all hover:bg-brand-700 active:scale-95 sm:right-6"
      >
        <span className="absolute inset-0 animate-pulse rounded-full bg-brand-400 opacity-50 group-hover:opacity-0" />
        {open ? (
          <X className="relative size-6" />
        ) : (
          <>
            <Bot className="relative size-6" />
          </>
        )}
      </button>

      {/* 桌面端悬浮球旁的引导气泡，仅首次展示 */}
      {!open && (
        <div className="fixed right-24 bottom-28 z-40 hidden items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-md sm:flex">
          <MessageCircle className="size-4 text-brand-600" />
          查询余额与账单
        </div>
      )}
    </>
  )
}
