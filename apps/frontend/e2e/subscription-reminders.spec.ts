import { expect, test } from '@playwright/test'
import { installDurableAgentBridge } from './support/durable-agent'

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`subscription query, reminder setup, inbox, budget and confirmed Demo action at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.addInitScript(() => {
      sessionStorage.setItem('bank-agent.access-token', 'access')
      sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long')
    })
    let agentCalls = 0
    let ruleStatus = 'ACTIVE'
    let notificationRead = false
    let budgetSaved = false
    let actionConfirmed = false
    let queryConfirmed = false
    let directForecastReads = 0
    let privateQueryReads = 0
    const rule = { id: 'rule-1', scope: 'AMOUNT_GT', subscription_id: null, amount_gt: '50.00', month: '2026-11', lead_days: [3], status: ruleStatus, created_at: '2026-10-27T00:00:00Z', updated_at: '2026-10-27T00:00:00Z' }
    const subscription = { id: 'sub-1', merchant: 'Stream Box', merchant_category: '订阅', demo_adapter: true, status: 'VERIFIED', cadence: 'MONTHLY', expected_amount: '68.00', amount_tolerance: '0.10', next_charge_at: '2026-11-15', occurrence_count: 3, evidence: {}, action_id: null }
    const action = () => ({ id: 'action-1', kind: 'subscription_cancel', request_hash: 'request-hash', status: actionConfirmed ? 'SUCCEEDED' : 'WAITING_CONFIRMATION', amount: '68.00', payload: { subscription_id: 'sub-1', subscription_snapshot: { merchant: 'Stream Box', expected_amount: '68.00', cadence: 'MONTHLY', next_charge_at: '2026-11-15' } }, result: {}, steps: {}, error_code: null, created_at: '2026-10-27T00:00:00Z', confirmed_at: null, executed_at: null, expires_at: '2099-01-01T00:00:00Z' })
    const queryAction = () => ({ id: 'query-action-1', kind: 'subscription_query', request_hash: 'query-hash', status: queryConfirmed ? 'SUCCEEDED' : 'WAITING_CONFIRMATION', amount: '0', payload: {}, result: queryConfirmed ? { result_id: 'forecast-1', result_kind: 'forecast' } : {}, steps: {}, error_code: null, created_at: '2026-10-27T00:00:00Z', confirmed_at: null, executed_at: null, risk_level: 'YELLOW', source: 'AGENT', expires_at: '2099-01-01T00:00:00Z' })

    await page.route('**/api/**', async (route) => {
      const request = route.request()
      const path = new URL(request.url()).pathname
      const method = request.method()
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 1, is_admin: false } })
      if (path === '/api/accounts') return route.fulfill({ json: [] })
      if (path === '/api/accounts/summary') return route.fulfill({ json: { currency: 'CNY', total: '0', account_count: 0, complete: true } })
      if (path === '/api/actions') return route.fulfill({ json: [] })
      if (path === '/api/health') return route.fulfill({ json: { status: 'UP' } })
      if (path === '/api/subscriptions' && method === 'GET') return route.fulfill({ json: [subscription] })
      if (path === '/api/subscriptions/renewals') return route.fulfill({ json: { as_of: '2026-10-27', timezone: 'Asia/Shanghai', days: 3, from_date: '2026-10-27', to_date: '2026-10-30', last_scan_at: '2026-10-27T09:00:00+08:00', upcoming: [], needs_review: [] } })
      if (path === '/api/subscriptions/forecast') { directForecastReads += 1; return route.fulfill({ json: { as_of: '2026-10-27', timezone: 'Asia/Shanghai', from_date: '2026-10-01', to_date: '2026-10-31', last_scan_at: null, items: [], projected_total: '0.00', needs_review: [], complete: true, status: 'complete' } }) }
      if (path === '/api/subscriptions/reminder-rules' && method === 'GET') return route.fulfill({ json: ruleStatus === 'DELETED' ? [] : [{ ...rule, status: ruleStatus }] })
      if (path === '/api/subscriptions/budget-rules' && method === 'GET') return route.fulfill({ json: budgetSaved ? [{ id: 'budget-1', month: '2026-11', amount: '50.00', status: 'ACTIVE', last_evaluated_on: '2026-10-27' }] : [] })
      if (path === '/api/notifications/unread-count') return route.fulfill({ json: { count: notificationRead ? 0 : 1 } })
      if (path === '/api/notifications') return route.fulfill({ json: [{ id: 'notice-1', kind: 'REMINDER', status: 'ACTIVE', payload: { title: 'Stream Box预计续费提醒', message: '预计于2026-11-15扣费，金额68.00元。' }, read_at: notificationRead ? '2026-10-27T09:00:00+08:00' : null, created_at: '2026-10-27T09:00:00+08:00', invalidated_at: null }] })
      if (path === '/api/notifications/notice-1/read' && method === 'POST') { notificationRead = true; return route.fulfill({ json: { id: 'notice-1', read: true } }) }
      if (path === '/api/actions/query-action-1') return route.fulfill({ json: queryAction() })
      if (path === '/api/actions/query-action-1/confirm' && method === 'POST') { queryConfirmed = true; return route.fulfill({ json: queryAction() }) }
      if (path === '/api/agent/subscription-results/forecast-1') { privateQueryReads += 1; return route.fulfill({ json: { id: 'forecast-1', kind: 'forecast', created_at: '2026-10-27T00:00:00Z', expires_at: '2026-10-27T00:30:00Z', data: { from_date: '2026-11-01', to_date: '2026-11-30', projected_total: '68.00', complete: true, needs_review: [], items: [{ subscription_id: 'sub-1', merchant: 'Stream Box', amount: '68.00', charge_date: '2026-11-15' }] } } }) }
      if (path === '/api/subscriptions/reminder-rules/rule-1/pause' && method === 'POST') { ruleStatus = 'PAUSED'; return route.fulfill({ json: { ...rule, status: ruleStatus } }) }
      if (path === '/api/subscriptions/reminder-rules/rule-1' && method === 'PUT') { ruleStatus = 'ACTIVE'; return route.fulfill({ json: { ...rule, status: ruleStatus, replayed: false } }) }
      if (path === '/api/subscriptions/budget-rules' && method === 'POST') { budgetSaved = true; return route.fulfill({ json: { rule: { id: 'budget-1', month: '2026-11', amount: '50.00', status: 'ACTIVE' }, reused: false, evaluation: { month: '2026-11', budget: '50.00', actual_total: '0.00', projected_remaining: '68.00', known_total: '68.00', over_budget: true, complete: true, suggestions: [{ subscription_id: 'sub-1', merchant: 'Stream Box', amount: '68.00', demo_cancellable: true }] } }, status: 201 }) }
      if (path === '/api/subscriptions/sub-1/cancel' && method === 'POST') return route.fulfill({ json: action(), status: 201 })
      if (path === '/api/actions/action-1') return route.fulfill({ json: action() })
      if (path === '/api/actions/action-1/audit') return route.fulfill({ json: [] })
      if (path === '/api/actions/action-1/confirm' && method === 'POST') { actionConfirmed = true; return route.fulfill({ json: action() }) }
      return route.fulfill({ status: 404, json: { error: { message: `unhandled ${method} ${path}` } } })
    })

    await installDurableAgentBridge(page, (body, headers) => {
      expect(headers.authorization).toBe('Bearer access')
      agentCalls += 1
      if (agentCalls === 1) return { trace_id: 'query-1', message: '请核对查询条件。', events: [
        { type: 'SUBSCRIPTION_QUERY_REQUESTED', data: { action_id: 'query-action-1', query_type: 'FORECAST', summary: '续费预测', conditions: ['期间：2026-11-01 至 2026-11-30（上海时间）', '金额严格大于 50 元'], risk_level: 'YELLOW', status: 'WAITING_CONFIRMATION', expires_at: '2099-01-01T00:00:00Z' } },
      ] }
      if (agentCalls === 2) return { trace_id: 'reminder-1', message: '请补充提醒提前量。', events: [
        { type: 'SUBSCRIPTION_FORECAST_READY', data: { result_id: 'forecast-1', from_date: '2026-11-01', to_date: '2026-11-30', complete: true, item_count: 1 } },
        { type: 'SUBSCRIPTION_CLARIFICATION_REQUIRED', data: { clarification_id: 'clarification-1', question: '你希望在预计扣费前几天提醒？', options: [1, 3, 7] } },
      ] }
      expect(body).toMatchObject({ message: '提前3天', continuation_ref: 'clarification-1' })
      return { trace_id: 'saved-1', message: '提醒规则已保存。', events: [{ type: 'SUBSCRIPTION_REMINDER_RULE_SAVED', data: { rule_id: 'rule-1', scope: 'AMOUNT_GT', month: '2026-11', lead_days: [3], amount_gt: '50.00', reused: false } }] }
    })
    await page.goto('/subscriptions')
    await expect.poll(() => directForecastReads).toBeGreaterThan(0)
    await page.getByRole('link', { name: /站内提醒/ }).click()
    await expect(page.getByRole('region', { name: '站内提醒' })).toBeVisible()
    await page.getByRole('button', { name: '标为已读' }).click()
    await expect(page.getByRole('button', { name: '标为已读' })).toHaveCount(0)

    await page.getByRole('button', { name: '打开智能助理' }).click()
    await page.getByLabel('给智能银行助理发送消息').fill('帮我看看下个月有哪些自动扣费，超过50元都告诉我')
    await page.getByRole('button', { name: '发送消息' }).click()
    const queryCard = page.getByLabel('订阅查询确认')
    await expect(queryCard).toContainText('黄色权限')
    await expect(queryCard).toContainText('金额严格大于 50 元')
    expect(privateQueryReads).toBe(0)
    await queryCard.getByRole('button', { name: '确认查询' }).click()
    await expect(page.getByLabel('预计续费查询结果')).toContainText('Stream Box')

    await page.getByLabel('给智能银行助理发送消息').fill('帮我看看下个月有哪些自动扣费，超过50元的都提醒我')
    await page.getByRole('button', { name: '发送消息' }).click()
    await expect(page.getByLabel('预计续费查询结果')).toContainText('Stream Box')
    await page.getByRole('button', { name: '提前3天' }).click()
    await expect(page.getByLabel('提醒规则已保存')).toBeVisible()
    await page.getByRole('link', { name: '管理提醒规则' }).click()
    await expect(page).toHaveURL(/\/subscriptions/)
    await expect(page.getByText('提前 3 天 · 2026-11')).toBeVisible()
    await page.getByRole('button', { name: '暂停' }).click()
    await expect(page.getByText('PAUSED')).toBeVisible()
    await page.getByRole('button', { name: '编辑' }).click()
    await page.getByRole('button', { name: '保存规则修改' }).click()
    await expect(page.getByText('ACTIVE')).toBeVisible()

    await page.getByLabel('预算金额').fill('50')
    await page.getByRole('button', { name: '保存并立即评估' }).click()
    await expect(page.getByLabel('订阅预算评估')).toContainText('已知金额已超过预算')
    await page.getByRole('button', { name: '申请取消并确认' }).click()
    await expect(page.getByLabel('取消确认内容')).toContainText('Stream Box')
    await expect(page.getByRole('button', { name: '确认并继续' })).toBeVisible()
    await page.getByRole('button', { name: '确认并继续' }).click()
    await expect(page.getByText('操作成功')).toBeVisible()
    expect(agentCalls).toBe(3)
    expect(queryConfirmed).toBe(true)
    expect(privateQueryReads).toBeGreaterThan(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
