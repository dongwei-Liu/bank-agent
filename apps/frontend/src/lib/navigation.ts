import {
  ArrowLeftRight,
  Home,
  ChartNoAxesCombined,
  ReceiptText,
  User,
  Wallet,
  Zap,
  type LucideIcon,
} from 'lucide-react'

/**
 * 前端导航与快捷入口配置（单一事实来源）。
 *
 * 底部 Tab 和功能入口的单一导航事实来源。
 *
 * `status`：
 * - ready   ：页面已可用、数据来自真实接口
 * - partial ：页面已可用，但依赖的后端接口尚未接入（例如转账提交）
 * - pending ：仅有占位页，功能未实现
 */

export type PageStatus = 'ready' | 'partial' | 'pending'

export type NavItem = {
  to: string
  label: string
  icon: LucideIcon
  status: PageStatus
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: '首页', icon: Home, status: 'ready' },
  { to: '/accounts', label: '账户', icon: Wallet, status: 'ready' },
  { to: '/payments', label: '支付', icon: ArrowLeftRight, status: 'ready' },
  { to: '/insights', label: '洞察', icon: ChartNoAxesCombined, status: 'ready' },
  { to: '/me', label: '我的', icon: User, status: 'ready' },
]

export type QuickAction = {
  id: string
  label: string
  icon: LucideIcon
  status: PageStatus
  to?: string
}

export const QUICK_ACTIONS: QuickAction[] = [
  { id: 'transfer', label: '转账汇款', icon: ArrowLeftRight, status: 'ready', to: '/payments/new' },
  { id: 'balance', label: '余额查询', icon: Wallet, status: 'ready', to: '/accounts' },
  { id: 'statement', label: '账户明细', icon: ReceiptText, status: 'ready', to: '/accounts' },
  { id: 'bills', label: '账单分析', icon: Zap, status: 'ready', to: '/insights' },
]

export function findNavItem(pathname: string): NavItem | undefined {
  if (pathname === '/') {
    return NAV_ITEMS[0]
  }

  return NAV_ITEMS.find((item) => item.to !== '/' && pathname.startsWith(item.to))
}
