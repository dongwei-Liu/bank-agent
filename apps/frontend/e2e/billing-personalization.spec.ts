import { expect, test } from '@playwright/test'

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`personal billing corrections and rule management at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.addInitScript(() => {
      sessionStorage.setItem('bank-agent.access-token', 'access')
      sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long')
    })

    let annotation: Record<string, unknown> | null = null
    let categories = [{ id: 'food', name: '餐饮' }]
    let rules: Array<Record<string, unknown>> = []
    let anomalyStatus = 'unreviewed'
    let failReview = true
    const writes: string[] = []

    await page.route('**/api/**', async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      const path = url.pathname
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 1, is_admin: false } })
      if (path === '/api/health') return route.fulfill({ json: { status: 'UP', service: 'bank-agent-backend', message: 'ok' } })
      if (path === '/api/accounts') return route.fulfill({ json: [{ id: 1, account_no: '000000001', client_id: 1, client_name: 'Alice', product_id: 1, product_name: '日常账户', deposit_type: 'Savings', currency: 'CNY', status: 'ACTIVE', available_balance: '100.00' }] })
      if (path === '/api/accounts/1') return route.fulfill({ json: { id: 1, account_no: '000000001', client_id: 1, client_name: 'Alice', product_id: 1, product_name: '日常账户', deposit_type: 'Savings', currency: 'CNY', status: 'ACTIVE', available_balance: '100.00', external_id: null, submitted_on: null, approved_on: null, activated_on: null, nominal_annual_interest_rate: '0', allow_overdraft: false } })
      if (path === '/api/accounts/1/transactions') return route.fulfill({ json: { items: [], total: 0, page: 0, page_size: 20 } })
      if (path === '/api/accounts/1/transactions/18') return route.fulfill({ json: { transaction_id: 18, account_id: 1, date: '2026-10-03', amount: '12.50', currency: 'CNY', direction: 'debit', kind: 'expense', type: 'withdrawal', reversed: false, transfer_reference: null, category_id: annotation?.category_id ?? null, category: annotation ? '餐饮' : '未分类', merchant: annotation?.merchant ?? 'Cafe', note: annotation?.note ?? 'bank note' } })
      if (path === '/api/transaction-annotations' && request.method() === 'GET') return route.fulfill({ json: annotation ? [annotation] : [] })
      if (path === '/api/transaction-annotations' && request.method() === 'POST') {
        writes.push('annotation:create')
        annotation = { id: 'annotation-1', ...(request.postDataJSON() as Record<string, unknown>) }
        return route.fulfill({ status: 201, json: annotation })
      }
      if (path === '/api/transaction-annotations/annotation-1' && request.method() === 'DELETE') {
        writes.push('annotation:delete')
        annotation = null
        return route.fulfill({ json: { deleted: true } })
      }
      if (path === '/api/categories' && request.method() === 'GET') return route.fulfill({ json: categories })
      if (path === '/api/categories/food' && request.method() === 'PUT') {
        writes.push('category:update')
        categories = [{ id: 'food', name: String((request.postDataJSON() as { name: string }).name) }]
        return route.fulfill({ json: categories[0] })
      }
      if (path === '/api/categories/food' && request.method() === 'DELETE') return route.fulfill({ status: 409, json: { error: { code: 'CATEGORY_IN_USE', message: '类别仍被规则或标注引用' } } })
      if (path === '/api/classification-rules' && request.method() === 'GET') return route.fulfill({ json: rules })
      if (path === '/api/classification-rules' && request.method() === 'POST') {
        writes.push('rule:create')
        const body = request.postDataJSON() as Record<string, unknown>
        rules = [{ id: 'rule-1', ...body }]
        return route.fulfill({ status: 201, json: rules[0] })
      }
      if (path === '/api/classification-rules/rule-1' && request.method() === 'PUT') {
        writes.push('rule:update')
        rules = [{ id: 'rule-1', ...(request.postDataJSON() as Record<string, unknown>) }]
        return route.fulfill({ json: rules[0] })
      }
      if (path === '/api/classification-rules/rule-1' && request.method() === 'DELETE') {
        writes.push('rule:delete')
        rules = []
        return route.fulfill({ json: { deleted: true } })
      }
      if (path === '/api/billing/statistics') return route.fulfill({ json: { account_id: null, account_ids: [1], complete: true, from_date: '2026-10-01', to_date: '2026-10-28', currency: 'CNY', totals: { income: '0', expense: '12.50', transfer: '0' }, direction_totals: {}, categories: { '餐饮': '12.50' }, monthly: {}, transaction_count: 1, data_cutoff: '2026-10-28T00:00:00+08:00', rule_version: 'billing-v1', configuration_hash: 'test', snapshot_atomic: false } })
      if (path === '/api/billing/anomalies') return route.fulfill({ json: { items: [{ anomaly_key: 'anomaly-1', rule: 'DUPLICATE_V1', status: anomalyStatus, evidence: { merchant: 'Cafe', amount: '12.50', date: '2026-10-03' }, transaction_ids: [18] }] } })
      if (path === '/api/billing/anomaly-reviews' && request.method() === 'POST') {
        writes.push('anomaly:review')
        if (failReview) return route.fulfill({ status: 503, json: { error: { code: 'UPSTREAM_ERROR', message: '核实暂不可用' } } })
        anomalyStatus = String((request.postDataJSON() as { status: string }).status)
        return route.fulfill({ json: { anomaly_key: 'anomaly-1', status: anomalyStatus } })
      }
      if (path === '/api/subscriptions/renewals') return route.fulfill({ json: { as_of: '2026-10-28', timezone: 'Asia/Shanghai', days: 3, from_date: '2026-10-28', to_date: '2026-10-31', last_scan_at: null, upcoming: [], needs_review: [] } })
      if (path === '/api/actions') return route.fulfill({ json: [] })
      return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: '未配置的受控测试接口' } } })
    })

    await page.goto('/accounts/1?transaction=18')
    await expect(page.getByText('单笔流水详情')).toBeVisible()
    await page.getByRole('button', { name: '修正分类与备注' }).click()
    await page.getByLabel('个人分类').selectOption('food')
    await page.getByRole('button', { name: '保存标注' }).click()
    await expect(page.getByRole('status')).toContainText('个人标注已保存')
    expect(annotation).toMatchObject({ account_id: 1, transaction_id: 18, category_id: 'food', merchant: 'Cafe', note: 'bank note' })
    await page.getByRole('button', { name: '清除全部个人标注' }).click()
    await expect(page.getByRole('status')).toContainText('已恢复自动分类')
    expect(annotation).toBeNull()

    await page.goto('/insights')
    await expect(page.getByRole('heading', { name: '财务洞察' })).toBeVisible()
    const categoriesSection = page.getByRole('heading', { name: '个人分类' }).locator('xpath=ancestor::section[1]')
    await categoriesSection.getByRole('button', { name: '编辑分类' }).click()
    await page.getByLabel('编辑分类名称').fill('餐饮新版')
    await categoriesSection.getByRole('button', { name: '保存' }).click()
    await expect(page.getByRole('status')).toContainText('分类已保存')
    await categoriesSection.getByRole('button', { name: '删除分类' }).click()
    await expect(page.getByRole('alert')).toContainText('类别仍被规则或标注引用')

    const rulesSection = page.getByRole('heading', { name: '个人分类规则' }).locator('xpath=ancestor::section[1]')
    await page.getByLabel('规则目标分类').selectOption('food')
    await page.getByLabel('规则匹配字段').selectOption('merchant')
    await page.getByLabel('规则匹配文字').fill('Cafe')
    await page.getByLabel('规则优先级').fill('100')
    await rulesSection.getByRole('button', { name: '添加分类规则' }).click()
    await expect(rulesSection.getByText(/商户包含“Cafe” · 优先级 100/)).toBeVisible()
    await rulesSection.getByRole('button', { name: '编辑规则' }).click()
    await page.getByLabel('规则匹配字段').selectOption('note')
    await page.getByLabel('规则匹配文字').fill('午餐')
    await page.getByLabel('规则优先级').fill('250')
    await rulesSection.getByRole('button', { name: '保存规则' }).click()
    await expect(rulesSection.getByText(/备注包含“午餐” · 优先级 250/)).toBeVisible()
    await rulesSection.getByRole('button', { name: '删除规则' }).click()
    await expect(rulesSection.getByText('暂无分类规则')).toBeVisible()

    const anomaly = page.locator('article').filter({ hasText: '重复扣款候选' })
    await anomaly.getByRole('button', { name: '确认异常' }).click()
    await expect(page.getByRole('alert')).toContainText('核实暂不可用')
    failReview = false
    await anomaly.getByRole('button', { name: '确认异常' }).click()
    await expect(page.getByText('异常候选已确认。', { exact: true })).toBeVisible()

    expect(writes).toEqual(['annotation:create', 'annotation:delete', 'category:update', 'rule:create', 'rule:update', 'rule:delete', 'anomaly:review', 'anomaly:review'])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
