import { expect, test } from '@playwright/test'

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`saved annual report can be regenerated with its original account scope at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.addInitScript(() => {
      sessionStorage.setItem('bank-agent.access-token', 'access')
      sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long')
    })
    let generationBody: Record<string, unknown> | undefined
    await page.route('**/api/**', async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      const path = url.pathname
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
      if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
      if (path === '/api/accounts') return route.fulfill({ json: [
        { id: 2, account_no: '000000002', client_id: 2, client_name: 'Alice Chen', product_id: 2, product_name: '日常账户', deposit_type: 'Savings', currency: 'CNY', status: 'ACTIVE', available_balance: '1000.00' },
      ] })
      if (path === '/api/bill-report-summaries') return route.fulfill({ json: { items: [
        { id: 'saved-report', period: '2025', status: 'partial', cutoff_date: '2025-12-31', created_at: '2026-01-01T00:00:00Z', account_ids: [2], account_scope: 'all_accounts', scope_account_id: null, transaction_count: 12 },
      ], total: 1, page: 1, page_size: 20 } })
      if (path === '/api/bill-report-generations' && request.method() === 'POST') {
        generationBody = request.postDataJSON() as Record<string, unknown>
        expect(request.headers()['idempotency-key']).toBeTruthy()
        return route.fulfill({ status: 202, json: { report_id: 'new-report', status: 'queued', period: '2025' } })
      }
      if (path === '/api/bill-report-generations/new-report/status') return route.fulfill({ json: { report_id: 'new-report', status: 'complete', progress: 100, period: '2025' } })
      if (path === '/api/bill-reports/new-report') return route.fulfill({ json: {
        id: 'new-report', schema_version: 1, status: 'complete', period: '2025', from_date: '2025-01-01', to_date: '2025-12-31', cutoff_date: '2025-12-31', partial_period: false,
        account_ids: [2], account_scope: 'all_accounts', scope_account_id: null, snapshot_atomic: false,
        historical_coverage: { status: 'observed', observed_days: 365, read_complete: true }, recurring_coverage_days: 365,
        sections: { summary: 'complete', trends: 'complete', transactions: 'complete', comparison: 'complete', anomalies: 'complete', recurring: 'complete', narrative: 'complete' },
        summary: { transaction_count: 12, expense_count: 12, average_expense: '20.00', totals: { income: '1000.00', expense: '240.00', fees: '0.00', external_transfer: '0.00', principal_flow: '0.00', net_cash_flow: '760.00' }, categories: [], daily: {}, monthly: { '2025-01': { income: '1000.00', expense: '240.00' } }, habits: { weekday_weekend_expense_count: { weekday: 8, weekend: 4 } } },
        comparison: {}, anomalies: [], recurring: [], narrative: { items: [], source: 'complete' },
      } })
      if (path === '/api/bill-reports/new-report/transactions') return route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 50 } })
      return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
    })

    await page.goto('/insights/reports')
    await expect(page.getByRole('link', { name: /2025 · partial · 12 笔/ })).toBeVisible()
    await page.getByRole('button', { name: '重新生成' }).click()
    await expect(page).toHaveURL(/\/insights\/reports\/new-report$/)
    await expect(page.getByRole('heading', { name: '2025 年度报告' })).toBeVisible()
    await expect(page.getByRole('img', { name: '逐月收支趋势' })).toBeVisible()
    expect(generationBody).toEqual({ account_id: null, period: '2025' })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
