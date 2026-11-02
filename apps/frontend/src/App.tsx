import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AgentProvider } from '@/agent/agent-provider'
import { ProtectedRoute } from '@/auth/protected-route'
import { AppShell } from '@/components/app-shell'
import { HomePage } from '@/pages/home-page'
import { LoginPage } from '@/pages/login-page'

const AccountDetailPage = lazy(() => import('@/pages/account-detail-page').then(module => ({ default: module.AccountDetailPage })))
const AccountsPage = lazy(() => import('@/pages/accounts-page').then(module => ({ default: module.AccountsPage })))
const ActionPage = lazy(() => import('@/pages/action-page').then(module => ({ default: module.ActionPage })))
const BillPage = lazy(() => import('@/pages/bill-page').then(module => ({ default: module.BillPage })))
const BillReportsPage = lazy(() => import('@/pages/bill-reports-page').then(module => ({ default: module.BillReportsPage })))
const TaskPage = lazy(() => import('@/pages/future-service-page').then(module => ({ default: module.TaskPage })))
const CardsPage = lazy(() => import('@/pages/cards-page').then(module => ({ default: module.CardsPage })))
const CardDetailPage = lazy(() => import('@/pages/cards-page').then(module => ({ default: module.CardDetailPage })))
const DemoMerchantPage = lazy(() => import('@/pages/demo-merchant-page').then(module => ({ default: module.DemoMerchantPage })))
const InsightsPage = lazy(() => import('@/pages/insights-page').then(module => ({ default: module.InsightsPage })))
const PaymentsPage = lazy(() => import('@/pages/payments-page').then(module => ({ default: module.PaymentsPage })))
const ProfilePage = lazy(() => import('@/pages/profile-page').then(module => ({ default: module.ProfilePage })))
const RiskAssessmentPage = lazy(() => import('@/pages/risk-assessment-page').then(module => ({ default: module.RiskAssessmentPage })))
const TransferPage = lazy(() => import('@/pages/transfer-page').then(module => ({ default: module.TransferPage })))
const SubscriptionsPage = lazy(() => import('@/pages/subscriptions-page').then(module => ({ default: module.SubscriptionsPage })))
const SubscriptionDetailPage = lazy(() => import('@/pages/subscriptions-page').then(module => ({ default: module.SubscriptionDetailPage })))
const WealthPage = lazy(() => import('@/pages/wealth-page').then(module => ({ default: module.WealthPage })))

/**
 * 应用路由。
 *
 * AI 助手不再是一个独立页面，而是全局悬浮窗（见 AgentLauncher）；
 * `/agent` 保留为深链：进入后自动唤起悬浮面板。
 *
 * 未接入的场景（账单、卡片、理财详情）完成纵向切片后再各自追加路由。
 */
export default function App() {
  return (
    <AgentProvider>
      <Suspense fallback={<div className="p-6 text-sm text-ink-500">正在加载页面…</div>}>
        <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<HomePage />} />
            <Route path="accounts" element={<AccountsPage />} />
            <Route path="accounts/:accountId" element={<AccountDetailPage />} />
            <Route path="payments" element={<PaymentsPage />} />
            <Route path="payments/new" element={<TransferPage />} />
            <Route path="payments/internal" element={<TransferPage />} />
            <Route path="actions/:actionId" element={<ActionPage />} />
            <Route path="insights" element={<InsightsPage />} />
            <Route path="insights/bills/:period" element={<BillPage />} />
            <Route path="insights/reports" element={<BillReportsPage />} />
            <Route path="insights/reports/:reportId" element={<BillReportsPage />} />
            <Route path="wealth" element={<WealthPage />} />
            <Route path="wealth/risk-assessment" element={<RiskAssessmentPage />} />
            <Route path="me" element={<ProfilePage />} />
            <Route path="cards" element={<CardsPage />} />
            <Route path="cards/:cardId" element={<CardDetailPage />} />
            <Route path="demo/merchant" element={<DemoMerchantPage />} />
            <Route path="subscriptions" element={<SubscriptionsPage />} />
            <Route path="subscriptions/:subscriptionId" element={<SubscriptionDetailPage />} />
            <Route path="tasks/:taskId" element={<TaskPage />} />
            <Route path="transfer" element={<Navigate to="/payments/new" replace />} />
            <Route path="profile" element={<Navigate to="/me" replace />} />
            <Route path="agent" element={<Navigate to="/" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
        </Routes>
      </Suspense>
    </AgentProvider>
  )
}
