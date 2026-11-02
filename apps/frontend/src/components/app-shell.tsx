import { Outlet } from 'react-router-dom'

import { AgentLauncher } from '@/components/agent/agent-launcher'
import { BankHeader } from '@/components/bank-header'
import { BottomTabBar } from '@/components/bottom-tab-bar'

/**
 * 应用外壳：品牌顶栏（品牌区 + 连接状态 + AI 助手入口）+ 内容区 + 全端底部 Tab 导航，
 * 以及全局常驻的 AI 助手悬浮球。页面跳转导航全部在底部（`bottom-tab-bar`）。
 */
export function AppShell() {
  return (
    <div className="min-h-svh bg-page-50 text-ink-900">
      <BankHeader />

      <main className="mx-auto max-w-6xl px-4 pt-4 pb-28 sm:px-6 sm:pb-16">
        <Outlet />
      </main>

      <BottomTabBar />
      <AgentLauncher />
    </div>
  )
}
