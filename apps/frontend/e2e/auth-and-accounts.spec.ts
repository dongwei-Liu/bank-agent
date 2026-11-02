import { expect, test } from '@playwright/test'

test('login, restore and current-user accounts', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/auth/login') return route.fulfill({ json: { access_token: 'access', refresh_token: 'refresh-token-value-long', token_type: 'bearer', expires_in: 900 } })
    if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
    if (path === '/api/accounts') return route.fulfill({ json: [{ id: 2, account_no: '000000002', client_id: 2, client_name: 'Alice Chen', product_id: 2, product_name: 'BANK_AGENT_SAVINGS', deposit_type: 'Savings', currency: 'CNY', status: 'ACTIVE', available_balance: '19264.64' }] })
    if (path === '/api/accounts/summary') return route.fulfill({ json: { currency: 'CNY', total: '19264.64', account_count: 1, complete: true } })
    if (path === '/api/actions') return route.fulfill({ json: [] })
    if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
  })
  await page.goto('/login'); await page.getByLabel('用户名').fill('alice'); await page.getByLabel('密码').fill('demo-password'); await page.getByRole('button', { name: '安全登录' }).click()
  await expect(page.getByText('你好，alice')).toBeVisible(); await page.reload(); await expect(page.getByText('BANK_AGENT_SAVINGS')).toBeVisible()
})

test('390px mobile layout keeps five primary navigation items usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => { sessionStorage.setItem('bank-agent.access-token', 'access'); sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long') })
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
    if (path === '/api/accounts/summary') return route.fulfill({ json: { currency: 'CNY', total: '0', account_count: 0, complete: true } })
    if (path === '/api/accounts' || path === '/api/actions') return route.fulfill({ json: [] })
    if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
  })
  await page.goto('/')
  for (const label of ['首页', '账户', '支付', '洞察', '我的']) await expect(page.getByRole('link', { name: label })).toBeVisible()
})

test('internal transfer submits two owned accounts through an Action', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('bank-agent.access-token', 'access'); sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long') })
  let submitted: Record<string, unknown> | undefined
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
    if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
    if (path === '/api/accounts') return route.fulfill({ json: [
      { id: 2, account_no: '000000002', client_id: 2, client_name: 'Alice Chen', product_id: 2, product_name: '日常账户', deposit_type: 'Savings', currency: 'CNY', status: 'ACTIVE', available_balance: '1000.00' },
      { id: 4, account_no: '000000004', client_id: 2, client_name: 'Alice Chen', product_id: 2, product_name: '备用账户', deposit_type: 'Savings', currency: 'CNY', status: 'ACTIVE', available_balance: '500.00' },
    ] })
    if (path === '/api/internal-transfers' && route.request().method() === 'POST') {
      submitted = route.request().postDataJSON() as Record<string, unknown>
      expect(route.request().headers()['idempotency-key']).toBeTruthy()
      return route.fulfill({ status: 201, json: { id: 'a1', kind: 'internal_transfer', request_hash: 'hash', status: 'WAITING_CONFIRMATION', amount: '25.50', payload: {}, result: {}, steps: {}, error_code: null, created_at: new Date().toISOString(), confirmed_at: null, executed_at: null } })
    }
    if (path === '/api/actions/a1') return route.fulfill({ json: { id: 'a1', kind: 'internal_transfer', request_hash: 'hash', status: 'WAITING_CONFIRMATION', amount: '25.50', payload: {}, result: {}, steps: {}, error_code: null, created_at: new Date().toISOString(), confirmed_at: null, executed_at: null } })
    if (path === '/api/actions/a1/audit') return route.fulfill({ json: [] })
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
  })
  await page.goto('/payments/internal')
  await page.getByLabel('付款账户').selectOption('2')
  await page.getByLabel('转入账户').selectOption('4')
  await page.getByLabel('金额（元）').fill('25.50')
  await page.getByRole('button', { name: '下一步：确认转账' }).click()
  await expect(page).toHaveURL(/\/actions\/a1$/)
  expect(submitted).toMatchObject({ from_account_id: 2, to_account_id: 4, amount: '25.50' })
})

test('insights defaults to all-account billing without an account filter', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('bank-agent.access-token', 'access'); sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long') })
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
    if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
    if (path === '/api/accounts') return route.fulfill({ json: [
      { id: 2, account_no: '000000002', client_id: 2, client_name: 'Alice Chen', product_id: 2, product_name: '日常账户', deposit_type: 'Savings', currency: 'CNY', status: 'ACTIVE', available_balance: '1000.00' },
      { id: 4, account_no: '000000004', client_id: 2, client_name: 'Alice Chen', product_id: 2, product_name: '备用账户', deposit_type: 'Savings', currency: 'CNY', status: 'ACTIVE', available_balance: '500.00' },
    ] })
    if (path === '/api/billing/statistics') {
      expect(url.searchParams.has('account_id')).toBe(false)
      return route.fulfill({ json: { account_id: null, account_ids: [2, 4], complete: true, currency: 'CNY', totals: { income: '100', expense: '20' }, categories: { 餐饮: '20' }, data_cutoff: '2026-10-14T12:00:00+08:00' } })
    }
    if (path === '/api/billing/anomalies') {
      expect(url.searchParams.has('account_id')).toBe(false)
      return route.fulfill({ json: { account_id: null, account_ids: [2, 4], complete: true, from_date: '2026-10-01', to_date: '2026-10-14', data_cutoff: '2026-10-14T12:00:00+08:00', items: [] } })
    }
    if (path === '/api/subscriptions/renewals') return route.fulfill({ json: { as_of: '2026-10-26', timezone: 'Asia/Shanghai', days: 3, from_date: '2026-10-26', to_date: '2026-10-29', last_scan_at: null, upcoming: [], needs_review: [] } })
    if (['/api/categories', '/api/classification-rules', '/api/bill-reports'].includes(path)) return route.fulfill({ json: [] })
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
  })
  await page.goto('/insights')
  await expect(page.getByRole('combobox').first()).toHaveValue('')
  await expect(page.getByText(/统计范围：全部 2 个账户/)).toBeVisible()
  await expect(page.getByText('¥20.00')).toHaveCount(2)
})

test('subscription candidate can be verified from deterministic evidence', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('bank-agent.access-token', 'access'); sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long') })
  let verified = false
  let renewalReads = 0
  const subscription = (status: 'CANDIDATE' | 'VERIFIED') => ({ id: 's1', merchant: 'Demo Video', merchant_category: '娱乐', demo_adapter: true, status, cadence: 'MONTHLY', expected_amount: '100.00', amount_tolerance: '0.1000', next_charge_at: '2026-10-15', occurrence_count: 3, evidence: { observed_gaps_days: [30, 30] }, action_id: null })
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
    if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
    if (path === '/api/subscriptions' && route.request().method() === 'GET') return route.fulfill({ json: [subscription(verified ? 'VERIFIED' : 'CANDIDATE')] })
    if (path === '/api/subscriptions/renewals') { renewalReads += 1; return route.fulfill({ json: { as_of: '2026-10-26', timezone: 'Asia/Shanghai', days: 3, from_date: '2026-10-26', to_date: '2026-10-29', last_scan_at: null, upcoming: [], needs_review: [] } }) }
    if (path === '/api/subscriptions/s1/verify') {
      expect(route.request().headers()['idempotency-key']).toBeTruthy()
      verified = true
      return route.fulfill({ json: subscription('VERIFIED') })
    }
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
  })
  await page.goto('/subscriptions')
  await expect(page.getByText('Demo Video')).toBeVisible()
  await page.getByRole('button', { name: '确认是订阅' }).click()
  await expect(page.getByText('已核实', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '取消 Demo 订阅' })).toBeVisible()
  await expect.poll(() => renewalReads).toBeGreaterThan(1)
})

test('Demo subscription cancellation confirms the displayed snapshot through an Action', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('bank-agent.access-token', 'access'); sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long') })
  let status = 'WAITING_CONFIRMATION'
  const subscription = { id: 's1', merchant: 'Demo Video', merchant_category: '娱乐', demo_adapter: true, status: 'VERIFIED', cadence: 'MONTHLY', expected_amount: '100.00', amount_tolerance: '0.1000', next_charge_at: '2026-11-01', occurrence_count: 3, evidence: {}, action_id: null }
  const action = () => ({
    id: 'cancel-action-1', kind: 'subscription_cancel', request_hash: 'h'.repeat(64), status, amount: '0.00',
    payload: { subscription_id: 's1', merchant: 'Demo Video', expected_amount: '100.00', cadence: 'MONTHLY', next_charge_at: '2026-11-01', subscription_snapshot: { merchant_id: 'm1', merchant: 'Demo Video', expected_amount: '100.00', cadence: 'MONTHLY', next_charge_at: '2026-11-01' } },
    result: {}, steps: {}, error_code: null, created_at: new Date().toISOString(), expires_at: new Date(Date.now() + 600_000).toISOString(), confirmed_at: null, executed_at: null,
  })
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
    if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
    if (path === '/api/subscriptions' && route.request().method() === 'GET') return route.fulfill({ json: [subscription] })
    if (path === '/api/subscriptions/renewals') return route.fulfill({ json: { as_of: '2026-10-26', timezone: 'Asia/Shanghai', days: 3, from_date: '2026-10-26', to_date: '2026-10-29', last_scan_at: null, upcoming: [], needs_review: [] } })
    if (path === '/api/subscriptions/s1/cancel') {
      expect(route.request().headers()['idempotency-key']).toBeTruthy()
      return route.fulfill({ status: 201, json: action() })
    }
    if (path === '/api/actions/cancel-action-1' && route.request().method() === 'GET') return route.fulfill({ json: action() })
    if (path === '/api/actions/cancel-action-1/audit') return route.fulfill({ json: [] })
    if (path === '/api/actions/cancel-action-1/confirm') { status = 'SUCCEEDED'; return route.fulfill({ json: action() }) }
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
  })
  await page.goto('/subscriptions')
  await page.getByRole('button', { name: '取消 Demo 订阅' }).click()
  await expect(page).toHaveURL(/\/actions\/cancel-action-1$/)
  await expect(page.getByRole('region', { name: '取消确认内容' })).toContainText('Demo Video')
  await expect(page.getByRole('region', { name: '取消确认内容' })).toContainText('100.00')
  await expect(page.getByRole('region', { name: '取消确认内容' })).toContainText('每月')
  await expect(page.getByRole('region', { name: '取消确认内容' })).toContainText('2026-11-01')
  await page.getByRole('button', { name: '确认并继续' }).click()
  await expect(page.getByText('操作成功')).toBeVisible()
})

test('debit card application uses an idempotent Action instead of fake card data', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('bank-agent.access-token', 'access'); sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long') })
  let submitted: Record<string, unknown> | undefined
  const action = { id: 'card-action-1', kind: 'card_application', request_hash: 'h'.repeat(64), status: 'WAITING_CONFIRMATION', amount: '0', payload: { product_name: '智汇借记卡', alias: '日常消费' }, result: {}, steps: {}, error_code: null, created_at: new Date().toISOString(), confirmed_at: null, executed_at: null }
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
    if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
    if (path === '/api/cards' && route.request().method() === 'GET') return route.fulfill({ json: [] })
    if (path === '/api/cards' && route.request().method() === 'POST') {
      submitted = route.request().postDataJSON() as Record<string, unknown>
      expect(route.request().headers()['idempotency-key']).toBeTruthy()
      return route.fulfill({ status: 201, json: action })
    }
    if (path === '/api/actions/card-action-1') return route.fulfill({ json: action })
    if (path === '/api/actions/card-action-1/audit') return route.fulfill({ json: [] })
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
  })
  await page.goto('/cards')
  await page.getByPlaceholder('卡片别名（可选，例如：日常消费）').fill('日常消费')
  await page.getByRole('button', { name: '申请新卡' }).click()
  await expect(page).toHaveURL(/\/actions\/card-action-1$/)
  await expect(page.getByRole('heading', { name: '确认申请借记卡' })).toBeVisible()
  expect(submitted).toEqual({ product_name: '智汇借记卡', alias: '日常消费' })
})

test('active debit card lock enters the shared confirmation flow', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('bank-agent.access-token', 'access'); sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long') })
  const card = { id: 'c1', account_id: 8, product_name: '智汇借记卡', alias: '日常消费', masked_number: '•••• •••• •••• 1234', last4: '1234', status: 'ACTIVE', currency: 'CNY', available_balance: '500.00', single_limit: '5000.00', daily_limit: '20000.00', online_enabled: true, pos_enabled: true, atm_enabled: true, international_enabled: false, replaces_card_id: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }
  const action = { id: 'card-lock-1', kind: 'card_lock', request_hash: 'h'.repeat(64), status: 'WAITING_CONFIRMATION', amount: '0', payload: { card_id: 'c1' }, result: {}, steps: {}, error_code: null, created_at: new Date().toISOString(), confirmed_at: null, executed_at: null }
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
    if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
    if (path === '/api/cards/c1' && route.request().method() === 'GET') return route.fulfill({ json: card })
    if (path === '/api/cards/c1/lock' && route.request().method() === 'POST') {
      expect(route.request().headers()['idempotency-key']).toBeTruthy()
      return route.fulfill({ status: 201, json: action })
    }
    if (path === '/api/actions/card-lock-1') return route.fulfill({ json: action })
    if (path === '/api/actions/card-lock-1/audit') return route.fulfill({ json: [] })
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
  })
  await page.goto('/cards/c1')
  await page.getByRole('button', { name: '锁卡' }).click()
  await expect(page).toHaveURL(/\/actions\/card-lock-1$/)
  await expect(page.getByRole('heading', { name: '确认锁定卡片' })).toBeVisible()
})

test('OTP card-number reveal is temporary and never comes from card detail data', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('bank-agent.access-token', 'access'); sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long') })
  const card = { id: 'c1', account_id: 8, product_name: '智汇借记卡', alias: '日常消费', masked_number: '•••• •••• •••• 1234', last4: '1234', status: 'ACTIVE', currency: 'CNY', available_balance: '500.00', single_limit: '5000.00', daily_limit: '20000.00', online_enabled: true, pos_enabled: true, atm_enabled: true, international_enabled: false, replaces_card_id: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }
  let status = 'WAITING_CONFIRMATION'
  const action = () => ({ id: 'reveal-1', kind: 'card_reveal', request_hash: 'h'.repeat(64), status, amount: '0', payload: { card_id: 'c1' }, result: status === 'SUCCEEDED' ? { card_id: 'c1', expires_at: new Date(Date.now() + 60_000).toISOString() } : {}, steps: {}, error_code: null, created_at: new Date().toISOString(), confirmed_at: null, executed_at: null })
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
    if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
    if (path === '/api/cards/c1' && route.request().method() === 'GET') return route.fulfill({ json: card })
    if (path === '/api/cards/c1/reveal' && route.request().method() === 'POST') return route.fulfill({ status: 201, json: action() })
    if (path === '/api/cards/c1/reveal' && route.request().method() === 'GET') {
      expect(url.searchParams.get('action_id')).toBe('reveal-1')
      return route.fulfill({ headers: { 'Cache-Control': 'no-store, max-age=0' }, json: { number: '6222020000001234', expires_at: new Date(Date.now() + 60_000).toISOString() } })
    }
    if (path === '/api/actions/reveal-1' && route.request().method() === 'GET') return route.fulfill({ json: action() })
    if (path === '/api/actions/reveal-1/confirm') { status = 'WAITING_VERIFICATION'; return route.fulfill({ json: action() }) }
    if (path === '/api/dev/otp-inbox/reveal-1') return route.fulfill({ json: { code: '123456' } })
    if (path === '/api/actions/reveal-1/verify') { status = 'SUCCEEDED'; return route.fulfill({ json: action() }) }
    if (path === '/api/actions/reveal-1/audit') return route.fulfill({ json: [] })
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
  })
  await page.goto('/cards/c1')
  await expect(page.getByText('6222020000001234')).toHaveCount(0)
  await page.getByRole('button', { name: '安全查看卡号' }).click()
  await page.getByRole('button', { name: '确认并继续' }).click()
  await page.getByRole('button', { name: '读取开发验证码' }).click()
  await page.getByRole('button', { name: '验证并执行' }).click()
  await page.getByRole('link', { name: '查看完整 Demo 卡号' }).click()
  await expect(page.getByText('6222 0200 0000 1234')).toBeVisible()
  await page.reload()
  await expect(page.getByText('6222 0200 0000 1234')).toHaveCount(0)
})

test('Demo merchant card purchase enters confirmation before core settlement', async ({ page }) => {
  await page.addInitScript(() => { sessionStorage.setItem('bank-agent.access-token', 'access'); sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long') })
  const card = { id: 'c1', account_id: 8, product_name: '智汇借记卡', alias: '日常消费', masked_number: '•••• •••• •••• 1234', last4: '1234', status: 'ACTIVE', currency: 'CNY', available_balance: '500.00', single_limit: '5000.00', daily_limit: '20000.00', online_enabled: true, pos_enabled: true, atm_enabled: true, international_enabled: false, replaces_card_id: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }
  let status = 'WAITING_CONFIRMATION'
  let submitted: Record<string, unknown> | undefined
  const action = () => ({ id: 'purchase-1', kind: 'card_transaction', request_hash: 'h'.repeat(64), status, amount: '25.80', payload: { card_id: 'c1', merchant_id: 'm1', amount: '25.80', channel: 'ONLINE', country_code: 'CN' }, result: status === 'SUCCEEDED' ? { status: 'APPROVED', merchant_name: '智汇 Demo 商城', fineract_transfer_id: 9 } : {}, steps: {}, error_code: null, created_at: new Date().toISOString(), confirmed_at: null, executed_at: null })
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 2, is_admin: false } })
    if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
    if (path === '/api/cards') return route.fulfill({ json: [card] })
    if (path === '/api/demo/merchants') return route.fulfill({ json: [{ id: 'm1', name: '智汇 Demo 商城', category: '购物' }] })
    if (path === '/api/demo/card-transactions' && route.request().method() === 'POST') {
      submitted = route.request().postDataJSON() as Record<string, unknown>
      expect(route.request().headers()['idempotency-key']).toBeTruthy()
      return route.fulfill({ status: 201, json: action() })
    }
    if (path === '/api/actions/purchase-1' && route.request().method() === 'GET') return route.fulfill({ json: action() })
    if (path === '/api/actions/purchase-1/confirm') { status = 'SUCCEEDED'; return route.fulfill({ json: action() }) }
    if (path === '/api/actions/purchase-1/audit') return route.fulfill({ json: [] })
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'not found' } } })
  })
  await page.goto('/demo/merchant')
  await expect(page.getByRole('heading', { name: 'Demo 商城' })).toBeVisible()
  await page.getByLabel('消费金额（元）').fill('25.80')
  await page.getByRole('button', { name: '下一步：确认消费' }).click()
  await expect(page).toHaveURL(/\/actions\/purchase-1$/)
  await expect(page.getByRole('heading', { name: '确认 Demo 商户消费' })).toBeVisible()
  expect(submitted).toEqual({ card_id: 'c1', merchant_id: 'm1', amount: '25.80', channel: 'ONLINE', country_code: 'CN' })
  await page.getByRole('button', { name: '确认并继续' }).click()
  await expect(page.getByText('操作成功')).toBeVisible()
  await expect(page.getByRole('link', { name: '返回业务页面' })).toHaveAttribute('href', '/demo/merchant')
})
