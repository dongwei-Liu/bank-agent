import { NavLink, useLocation } from 'react-router-dom'

import { NAV_ITEMS } from '@/lib/navigation'
import { cn } from '@/lib/utils'

/**
 * 底部导航栏：仿银行 App 的五大 tab（首页 / 账户 / 转账 / 理财 / 我的）。
 *
 * 全端全宽贴底，内容与顶栏同宽（max-w-6xl + 同款左右内边距），
 * 视觉上和顶部品牌栏等宽对齐。与顶栏、快捷宫格共用 `NAV_ITEMS` 配置。
 */
export function BottomTabBar() {
  const location = useLocation()

  return (
    <nav className="fixed bottom-0 z-30 w-full border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] shadow-[0_-1px_4px_rgba(0,0,0,0.03)]">
      <div className="mx-auto flex max-w-6xl px-4 sm:px-6">
        {NAV_ITEMS.map((item) => {
          const active =
            item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to)

          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={cn(
                'flex flex-1 flex-col items-center gap-1 py-2 text-[11px] transition-colors sm:px-6 sm:py-2.5 sm:text-xs',
                active ? 'text-brand-600' : 'text-ink-500 hover:text-brand-600',
              )}
            >
              <item.icon className={cn('size-5 sm:size-[18px]', active && 'stroke-[2.25]')} />
              {item.label}
              <span
                className={cn(
                  'h-0.5 w-6 rounded-full transition-colors',
                  active ? 'bg-brand-600' : 'bg-transparent',
                )}
              />
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
