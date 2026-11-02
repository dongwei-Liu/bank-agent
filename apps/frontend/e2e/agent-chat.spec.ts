import { expect, test } from '@playwright/test'
import { installDurableAgentBridge } from './support/durable-agent'

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`keeps each result card with its own reply across replay, refresh, and another question at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    let turn = 0
    const totals: Record<string, string> = { 'result-1': '11.00', 'result-2': '22.00', 'result-3': '33.00' }
    await page.addInitScript(() => {
      sessionStorage.setItem('bank-agent.access-token', 'access')
      sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long')
    })
    await page.route('**/api/**', async (route) => {
      const path = new URL(route.request().url()).pathname
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 7 } })
      if (path === '/api/accounts') return route.fulfill({ json: [{ id: 7, account_no: '000000007', currency: 'CNY', product_name: '储蓄', available_balance: '1000', status: 'ACTIVE' }] })
      if (path === '/api/accounts/summary') return route.fulfill({ json: { currency: 'CNY', total: '1000', account_count: 1, complete: true } })
      if (path === '/api/actions') return route.fulfill({ json: [] })
      if (path === '/api/health') return route.fulfill({ json: { status: 'UP' } })
      if (path.startsWith('/api/agent/analyses/')) {
        const analysisId = path.split('/').at(-1) ?? ''
        return route.fulfill({ json: {
          analysis_id: analysisId, kind: 'balance', expires_at: '2030-01-01T00:00:00Z',
          data: { account_ids: [7], currency: 'CNY', total: totals[analysisId], account_count: 1, complete: true },
        } })
      }
      return route.fulfill({ status: 404, json: { error: { message: 'not found' } } })
    })
    await installDurableAgentBridge(page, (body) => {
      if (body.message === '谢谢') return { trace_id: 'text-only', message: '收到。', events: [] }
      turn += 1
      return {
        trace_id: `multi-${turn}`,
        message: `第 ${turn} 轮查询完成。`,
        events: [{ type: 'ANALYSIS_READY', data: { analysis_id: `result-${turn}`, kind: 'balance' } }],
      }
    })

    await page.goto('/')
    await page.getByRole('button', { name: '打开智能助理' }).click()
    const dialog = page.getByRole('dialog', { name: '智能银行助理' })
    const input = dialog.getByLabel('给智能银行助理发送消息')
    for (const [index, question] of ['查第一笔结果', '查第二笔结果', '查第三笔结果'].entries()) {
      await input.fill(question)
      await dialog.getByRole('button', { name: '发送消息' }).click()
      await expect(dialog.getByText(`第 ${index + 1} 轮查询完成。`)).toBeVisible()
      await expect(dialog.getByLabel('授权分析结果')).toHaveCount(index + 1)
    }
    for (const amount of Object.values(totals)) {
      await expect(dialog.getByLabel('授权分析结果').filter({ hasText: amount })).toHaveCount(1)
    }

    await page.reload()
    await page.getByRole('button', { name: '打开智能助理' }).click()
    const restoredDialog = page.getByRole('dialog', { name: '智能银行助理' })
    await expect(restoredDialog.getByLabel('授权分析结果')).toHaveCount(3)
    await restoredDialog.getByLabel('给智能银行助理发送消息').fill('谢谢')
    await restoredDialog.getByRole('button', { name: '发送消息' }).click()
    await expect(restoredDialog.getByText('收到。')).toBeVisible()
    await expect(restoredDialog.getByLabel('授权分析结果')).toHaveCount(3)
    for (const amount of Object.values(totals)) {
      await expect(restoredDialog.getByLabel('授权分析结果').filter({ hasText: amount })).toHaveCount(1)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`unified chat shows balance and billing results at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    const messages: string[] = []
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.addInitScript(() => {
      sessionStorage.setItem('bank-agent.access-token', 'access')
      sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long')
    })
    await page.route('**/api/**', async (route) => {
      const request = route.request()
      const path = new URL(request.url()).pathname
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 7, is_admin: false } })
      if (path === '/api/accounts') return route.fulfill({ json: [{ id: 7, account_no: '000000007', currency: 'CNY', product_name: '储蓄账户', available_balance: '1000', status: 'ACTIVE' }] })
      if (path === '/api/accounts/summary') return route.fulfill({ json: { currency: 'CNY', total: '1000', account_count: 1, complete: true } })
      if (path === '/api/actions') return route.fulfill({ json: [] })
      if (path === '/api/health') return route.fulfill({ json: { status: 'UP' } })
      if (path === '/api/agent/messages') {
        expect(request.headers().authorization).toBe('Bearer access')
        const body = request.postDataJSON()
        expect(Object.keys(body)).toEqual(['message', 'query_context'])
        const allAccounts = body.message.includes('所有账户')
        expect(body.query_context).toEqual(allAccounts ? (body.message.includes('在 2026-09') ? { period: '2026-09' } : {}) : { account_id: 7, period: '2026-09' })
        messages.push(body.message)
        const answer = body.message.startsWith('查询我所有账户') ? (body.message.includes('异常') ? '全部账户发现 1 个异常候选，请核实。' : '全部账户消费统计：100 CNY。') : body.message.includes('异常') ? '发现 1 个疑似重复消费候选，请核实。' : body.message.includes('统计我所有账户') ? '本月全部账户消费统计：100 CNY。' : body.message.includes('统计') ? '2026 年 9 月消费统计：100 CNY，其中未分类 100 CNY。' : body.message.includes('消费情况') ? '九月份的消费已按所选年份查询。' : '本人储蓄可用余额为 1000 CNY。'
        return route.fulfill({ json: { trace_id: `chat-${messages.length}`, message: answer, events: [] } })
      }
      return route.fulfill({ status: 404, json: { error: { message: 'not found' } } })
    })
    await installDurableAgentBridge(page, (raw, headers) => {
      expect(headers.authorization).toBe('Bearer access')
      const body = raw as { message: string; query_context: Record<string, unknown> }
      expect(Object.keys(body)).toEqual(['message', 'query_context'])
      const allAccounts = body.message.includes('所有账户')
      expect(body.query_context).toEqual(allAccounts ? (body.message.includes('在 2026-09') ? { period: '2026-09' } : {}) : { account_id: 7, period: '2026-09' })
      messages.push(body.message)
      const answer = body.message.startsWith('查询我所有账户') ? (body.message.includes('异常') ? '全部账户发现 1 个异常候选，请核实。' : '全部账户消费统计：100 CNY。') : body.message.includes('异常') ? '发现 1 个疑似重复消费候选，请核实。' : body.message.includes('统计我所有账户') ? '本月全部账户消费统计：100 CNY。' : body.message.includes('统计') ? '2026 年 9 月消费统计：100 CNY，其中未分类 100 CNY。' : body.message.includes('消费情况') ? '九月份的消费已按所选年份查询。' : '本人储蓄可用余额为 1000 CNY。'
      return { trace_id: `chat-${messages.length}`, message: answer, events: [] }
    })
    await page.goto('/')
    await page.getByRole('button', { name: '打开智能助理' }).click()
    const dialog = page.getByRole('dialog', { name: '智能银行助理' })
    await expect(dialog).toBeVisible()
    await expect(page.getByLabel('账单账户')).toHaveValue('7')
    await page.getByLabel('账单月份').fill('2026-09')
    await page.getByRole('button', { name: '查余额', exact: true }).click()
    await expect(page.getByText('本人储蓄可用余额为 1000 CNY。')).toBeVisible()
    await page.getByRole('button', { name: '消费统计', exact: true }).click()
    await expect(page.getByText('2026 年 9 月消费统计：100 CNY，其中未分类 100 CNY。')).toBeVisible()
    await page.getByRole('button', { name: '异常候选', exact: true }).click()
    await expect(page.getByText('发现 1 个疑似重复消费候选，请核实。')).toBeVisible()
    await page.getByLabel('给智能银行助理发送消息').fill('账户id7在9月份的消费情况')
    await page.getByRole('button', { name: '发送消息', exact: true }).click()
    await expect(page.getByText('九月份的消费已按所选年份查询。')).toBeVisible()
    await page.getByRole('button', { name: '全部账户统计', exact: true }).click()
    await expect(page.getByText('全部账户消费统计：100 CNY。')).toBeVisible()
    await page.getByRole('button', { name: '全部账户异常', exact: true }).click()
    await expect(page.getByText('全部账户发现 1 个异常候选，请核实。')).toBeVisible()
    await page.getByLabel('给智能银行助理发送消息').fill('统计我所有账户的消费分类，按金额从高到低列出。')
    await page.getByRole('button', { name: '发送消息', exact: true }).click()
    await expect(page.getByText('本月全部账户消费统计：100 CNY。')).toBeVisible()
    expect(messages).toEqual(['我还有多少钱？', '查询账户 7 在 2026-09 的消费分类统计', '查询账户 7 在 2026-09 的异常消费候选', '账户id7在9月份的消费情况', '查询我所有账户在 2026-09 的消费分类统计', '查询我所有账户在 2026-09 的异常消费候选', '统计我所有账户的消费分类，按金额从高到低列出。'])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(errors).toEqual([])
    await page.screenshot({ path: `../../.runtime/unified-agent-ui-${viewport.width}.png`, fullPage: true })
  })
}

for (const width of [1440, 390]) {
  test(`private analysis cards fetch exact data separately at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const privateReads: string[] = []
    let reviewPayload: unknown
    await page.addInitScript(() => {
      sessionStorage.setItem('bank-agent.access-token', 'access')
      sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long')
    })
    await page.route('**/api/**', async (route) => {
      const path = new URL(route.request().url()).pathname
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 7 } })
      if (path === '/api/accounts') return route.fulfill({ json: [{ id: 7, account_no: '000000007', currency: 'CNY', product_name: '储蓄', available_balance: '777.33' }] })
      if (path === '/api/accounts/summary') return route.fulfill({ json: { currency: 'CNY', total: '777.33', account_count: 1, complete: true } })
      if (path === '/api/actions') return route.fulfill({ json: [] })
      if (path === '/api/health') return route.fulfill({ json: { status: 'UP' } })
      if (path === '/api/agent/messages') return route.fulfill({ json: { trace_id: 'private', message: '查询已完成，精确结果请查看结果卡。', events: ['balance', 'statistics', 'anomalies'].map(kind => ({ type: 'ANALYSIS_READY', data: { analysis_id: kind, kind } })) } })
      if (path.startsWith('/api/agent/analyses/')) {
        expect(route.request().headers().authorization).toBe('Bearer access')
        const kind = path.split('/').pop()!
        privateReads.push(kind)
        const data = kind === 'balance' ? { currency: 'CNY', total: '777.33', account_count: 1, complete: true } : kind === 'statistics' ? { account_ids: [7], currency: 'CNY', from_date: '2026-09-01', to_date: '2026-09-30', transaction_count: 6, totals: { expense: '123.45' }, categories: { 餐飲: '123.45' }, monthly: {}, snapshot_atomic: false, data_cutoff: '2026-10-22T00:00:00Z' } : { account_ids: [7], from_date: '2026-09-01', to_date: '2026-09-30', items: [{ anomaly_key: 'a1', rule: 'DUPLICATE_V1', status: 'unreviewed', evidence: { merchant: 'Private Cafe', amount: '88.50', date: '2026-09-10' } }], detection: { status: 'no_model' } }
        return route.fulfill({ json: { analysis_id: kind, kind, expires_at: '2030-01-01T00:00:00Z', data } })
      }
      if (path === '/api/billing/anomaly-reviews') {
        reviewPayload = route.request().postDataJSON()
        return route.fulfill({ json: { status: 'verified' } })
      }
      return route.fulfill({ status: 404, json: {} })
    })
    await installDurableAgentBridge(page, () => ({ trace_id: 'private', message: '查询已完成，精确结果请查看结果卡。', events: ['balance', 'statistics', 'anomalies'].map(kind => ({ type: 'ANALYSIS_READY', data: { analysis_id: kind, kind } })) }))
    await page.goto('/')
    await page.getByRole('button', { name: '打开智能助理' }).click()
    await page.getByRole('button', { name: '查余额', exact: true }).click()
    await expect(page.getByLabel('授权分析结果')).toHaveCount(3)
    const cards = page.getByLabel('授权分析结果')
    await expect(cards.nth(0)).toContainText('777.33')
    await expect(cards.nth(1)).toContainText('123.45')
    await expect(cards.nth(2)).toContainText('Private Cafe')
    await expect(cards.nth(2)).not.toContainText('本次仅规则检测')
    await cards.nth(2).getByRole('button', { name: '确认异常' }).click()
    await expect(cards.nth(2)).toContainText('已确认')
    await expect(page.getByRole('status')).toContainText('异常候选已确认')
    expect(reviewPayload).toEqual({ anomaly_key: 'a1', status: 'verified' })
    expect([...new Set(privateReads)].sort()).toEqual(['anomalies', 'balance', 'statistics'])
    expect(privateReads.filter((kind) => kind === 'anomalies')).toHaveLength(2)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

for (const width of [1440, 390]) {
  test(`six detection capabilities and provisional observation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.addInitScript(() => sessionStorage.setItem('bank-agent.access-token', 'access'))
    const types = ['SPENDING_SURGE_V1', 'DAILY_CONCENTRATION_V1', 'MERCHANT_DEVIATION_V1', 'CATEGORY_MIX_SHIFT_V1', 'SUBSCRIPTION_DEVIATION_V1', 'ACCOUNT_HABIT_SHIFT_V1']
    await page.route('**/api/**', async (route) => {
      const path = new URL(route.request().url()).pathname
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 7 } })
      if (path === '/api/accounts') return route.fulfill({ json: [{ id: 7, account_no: '000000007', currency: 'CNY', product_name: '储蓄', available_balance: '100' }] })
      if (path === '/api/accounts/summary') return route.fulfill({ json: { currency: 'CNY', total: '100', account_count: 1, complete: true } })
      if (path === '/api/actions') return route.fulfill({ json: [] })
      if (path === '/api/health') return route.fulfill({ json: { status: 'UP' } })
      if (path === '/api/agent/messages') return route.fulfill({ json: { trace_id: 'six', message: '检测结果已生成，请查看结果卡。', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'six', kind: 'anomalies' } }] } })
      if (path === '/api/agent/analyses/six') return route.fulfill({ json: {
        analysis_id: 'six', kind: 'anomalies', expires_at: '2030-01-01T00:00:00Z', data: {
          account_ids: [7], from_date: '2026-09-01', to_date: '2026-09-30',
          detection: { status: 'no_model', capabilities: Object.fromEntries(types.map(type => [type, { status: 'partial', sources: ['rule'], skip_reasons: ['insufficient_history'] }])) },
          items: types.map(type => ({ anomaly_key: type, rule: type, transaction_ids: type === 'SUBSCRIPTION_DEVIATION_V1' ? [] : [1], observation_kind: type === 'SUBSCRIPTION_DEVIATION_V1' ? 'expected_charge_not_observed' : undefined,
            findings: [{ type, sources: ['rule'], provisional: true, window: { from_date: '2026-09-24', to_date: '2026-09-30' }, evidence: type === 'SUBSCRIPTION_DEVIATION_V1' ? { reason_codes: ['EXPECTED_CHARGE_NOT_OBSERVED'], expected_date: '2026-09-25', cutoff_date: '2026-09-30' } : { amount: '654.32', count: 6 } }] })),
        },
      } })
      return route.fulfill({ status: 404, json: {} })
    })
    await installDurableAgentBridge(page, () => ({ trace_id: 'six', message: '检测结果已生成，请查看结果卡。', events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'six', kind: 'anomalies' } }] }))
    await page.goto('/')
    await page.getByRole('button', { name: '打开智能助理' }).click()
    await page.getByRole('button', { name: '全部账户异常', exact: true }).click()
    const card = page.getByLabel('授权分析结果')
    for (const title of ['累计消费突增', '日级集中消费', '商户维度异常', '消费类别结构突变', '订阅涨价或周期异常', '账户使用习惯异常']) await expect(card).toContainText(title)
    await expect(card).toContainText('654.32')
    await expect(card).toContainText('当日临时提示')
    await expect(card).not.toContainText('部分执行')
    await expect(card).toContainText('截至查询截止未匹配到预期扣费')
    await expect(card).not.toContainText('涉及0笔')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

for (const width of [1440, 390]) {
  test(`monthly annual and anomaly presentation across surfaces at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.addInitScript(() => sessionStorage.setItem('bank-agent.access-token', 'access'))
    const stats = { account_ids: [7], currency: 'CNY', from_date: '2025-01-01', to_date: '2025-12-31', transaction_count: 9,
      totals: { income: '900', expense: '300', transfer: '77' }, categories: { 餐饮: '300' },
      monthly: { '2025-09': { income: '600', expense: '200', transfer: '55' }, '2025-01': { income: '300', expense: '100', transfer: '22' } },
      data_cutoff: '2025-12-31T23:59:00+08:00', snapshot_atomic: true }
    const anomalies = { account_ids: [7], items: [{ anomaly_key: 'model', rule: 'IFOREST_V1', status: 'verified', evidence: { amount: '321.12', score: 0.9876, threshold: 0.7654 } }],
      detection: { status: 'no_model', capabilities: { SPENDING_SURGE_V1: { status: 'skipped', sources: ['rule'], skip_reasons: ['insufficient_history'] } } } }
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 7 } })
      if (path === '/api/accounts') return route.fulfill({ json: [{ id: 7, account_no: '000000007', currency: 'CNY', product_name: '储蓄', available_balance: '100' }] })
      if (path === '/api/billing/statistics') return route.fulfill({ json: stats })
      if (path === '/api/billing/anomalies') return route.fulfill({ json: anomalies })
      if (path === '/api/subscriptions/renewals') return route.fulfill({ json: { as_of: '2026-10-26', timezone: 'Asia/Shanghai', days: 3, from_date: '2026-10-26', to_date: '2026-10-29', last_scan_at: null, upcoming: [], needs_review: [] } })
      if (path === '/api/agent/messages') return route.fulfill({ json: { trace_id: 'period-result', message: '结果已生成', events: ['year', 'month'].map(id => ({ type: 'ANALYSIS_READY', data: { analysis_id: id, kind: 'statistics' } })) } })
      if (path.startsWith('/api/agent/analyses/')) return route.fulfill({ json: { kind: 'statistics', expires_at: '2030-01-01T00:00:00Z', data: path.endsWith('/year') ? stats : { ...stats, from_date: '2025-09-01', to_date: '2025-09-30' } } })
      return route.fulfill({ json: [] })
    })
    await installDurableAgentBridge(page, () => ({ trace_id: 'period-result', message: '结果已生成', events: ['year', 'month'].map(id => ({ type: 'ANALYSIS_READY', data: { analysis_id: id, kind: 'statistics' } })) }))
    for (const path of ['/insights/bills/2025', '/insights']) {
      await page.goto(path)
      await expect(page.getByText(/消费模式偏离个人历史/)).toBeVisible()
      await expect(page.getByText(/个人消费行为偏离候选 · 已确认/)).toBeVisible()
      await expect(page.locator('main')).not.toContainText(/0.9876|0.7654|本次仅规则检测|执行覆盖|模型评分|insufficient_history/)
      if (path.endsWith('2025')) {
        const rows = page.getByRole('heading', { name: '逐月收支明细' }).locator('..')
        await expect(rows).toContainText('55.00')
        expect((await rows.innerText()).indexOf('2025-01')).toBeLessThan((await rows.innerText()).indexOf('2025-09'))
        await expect(rows).not.toContainText('2025-12')
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    }
    await page.getByRole('button', { name: '打开智能助理' }).click()
    await page.getByRole('button', { name: '消费统计', exact: true }).click()
    const cards = page.getByLabel('授权分析结果')
    await expect(cards.nth(0)).toContainText('2025 年 · 年度消费分类统计')
    await expect(cards.nth(0)).toContainText('逐月收支明细')
    await expect(cards.nth(1)).toContainText('2025 年 9 月 · 消费分类统计')
    await expect(cards.nth(1)).not.toContainText('逐月收支明细')
    await page.screenshot({ path: `../../.runtime/bill-presentation-${width}.png`, fullPage: true })
  })
}

for (const width of [1440, 390]) {
  test(`subscription scan summary and navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    let agentRequests = 0
    await page.addInitScript(() => {
      sessionStorage.setItem('bank-agent.access-token', 'access')
      sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long')
    })
    await page.route('**/api/**', async (route) => {
      const request = route.request()
      const path = new URL(request.url()).pathname
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 1, is_admin: false } })
      if (path === '/api/accounts') return route.fulfill({ json: [] })
      if (path === '/api/accounts/summary') return route.fulfill({ json: { currency: 'CNY', total: '0', account_count: 0, complete: true } })
      if (path === '/api/actions') return route.fulfill({ json: [] })
      if (path === '/api/health') return route.fulfill({ json: { status: 'UP' } })
      if (path === '/api/agent/messages') {
        agentRequests += 1
        expect(request.method()).toBe('POST')
        expect(request.headers().authorization).toBe('Bearer access')
        return route.fulfill({ json: {
          trace_id: 'scan-ui', message: '订阅扣费识别已完成。',
          events: [{ type: 'SUBSCRIPTION_SCAN_COMPLETED', data: {
            created: 0, updated: 0, found: 0, matched_candidates: 0,
            from_date: '2024-08-17', to_date: '2026-10-26',
            scanned_at: '2026-10-26T08:00:00+00:00', timezone: 'Asia/Shanghai',
          } }],
        } })
      }
      if (path === '/api/subscriptions') return route.fulfill({ json: [] })
      if (path === '/api/subscriptions/renewals') return route.fulfill({ json: {
        as_of: '2026-10-26', timezone: 'Asia/Shanghai', days: 3,
        from_date: '2026-10-26', to_date: '2026-10-29',
        last_scan_at: '2026-10-26T08:00:00+00:00', upcoming: [], needs_review: [],
      } })
      return route.fulfill({ status: 404, json: { error: { message: '未配置的受控测试接口' } } })
    })
    await installDurableAgentBridge(page, (_body, headers) => {
      agentRequests += 1
      expect(headers.authorization).toBe('Bearer access')
      return {
        trace_id: 'scan-ui', message: '订阅扣费识别已完成。',
        events: [{ type: 'SUBSCRIPTION_SCAN_COMPLETED', data: {
          created: 0, updated: 0, found: 0, matched_candidates: 0,
          from_date: '2024-08-17', to_date: '2026-10-26',
          scanned_at: '2026-10-26T08:00:00+00:00', timezone: 'Asia/Shanghai',
        } }],
      }
    })
    await page.goto('/')
    await page.getByRole('button', { name: '打开智能助理' }).click()
    await page.getByRole('button', { name: '识别订阅扣费', exact: true }).click()
    await expect(page.getByLabel('订阅识别结果')).toContainText('不代表没有订阅')
    expect(agentRequests).toBe(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByRole('link', { name: '查看订阅候选与扣费证据' }).click()
    await expect(page).toHaveURL(/\/subscriptions$/)
    await expect(page.getByRole('dialog', { name: '智能银行助理' })).toHaveCount(0)
  })
}

for (const width of [1440, 390]) {
  test(`subscription cancellation confirmation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => {
      sessionStorage.setItem('bank-agent.access-token', 'access')
      sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long')
    })
    let confirmed = false
    let confirms = 0
    const action = () => ({
      id: 'action-1', kind: 'subscription_cancel', request_hash: 'hash-1',
      status: confirmed ? 'SUCCEEDED' : 'WAITING_CONFIRMATION', amount: '100',
      payload: { subscription_id: 'sub-1', subscription_snapshot: {
        merchant: 'Demo Video', expected_amount: '100', cadence: 'MONTHLY', next_charge_at: '2026-11-01',
      } },
      result: {}, steps: {}, error_code: null, created_at: '2026-10-27T00:00:00Z',
      confirmed_at: null, executed_at: null, expires_at: '2099-01-01T00:00:00Z',
    })
    await page.route('**/api/**', async (route) => {
      const request = route.request()
      const path = new URL(request.url()).pathname
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 1, is_admin: false } })
      if (path === '/api/accounts') return route.fulfill({ json: [] })
      if (path === '/api/accounts/summary') return route.fulfill({ json: { currency: 'CNY', total: '0', account_count: 0, complete: true } })
      if (path === '/api/actions') return route.fulfill({ json: [] })
      if (path === '/api/health') return route.fulfill({ json: { status: 'UP' } })
      if (path === '/api/agent/messages') return route.fulfill({ json: {
        trace_id: 'cancel-ui', message: '请核对并确认。',
        events: [{ type: 'SUBSCRIPTION_CANCEL_REQUESTED', data: { action_id: 'action-1', status: 'WAITING_CONFIRMATION' } }],
      } })
      if (path === '/api/actions/action-1/audit') return route.fulfill({ json: [] })
      if (path === '/api/actions/action-1/confirm') {
        expect(request.method()).toBe('POST')
        expect(request.postDataJSON()).toEqual({ request_hash: 'hash-1' })
        confirms += 1
        confirmed = true
        return route.fulfill({ json: action() })
      }
      if (path === '/api/actions/action-1') return route.fulfill({ json: action() })
      return route.fulfill({ status: 404, json: {} })
    })
    await installDurableAgentBridge(page, () => ({
      trace_id: 'cancel-ui', message: '请核对并确认。',
      events: [{ type: 'SUBSCRIPTION_CANCEL_REQUESTED', data: { action_id: 'action-1', status: 'WAITING_CONFIRMATION' } }],
    }))
    await page.goto('/')
    await page.getByRole('button', { name: '打开智能助理' }).click()
    await page.getByLabel('给智能银行助理发送消息').fill('取消 Demo Video 订阅')
    await page.getByRole('button', { name: '发送消息' }).click()
    await expect(page.getByLabel('订阅取消请求')).toContainText('请求尚未执行')
    expect(confirms).toBe(0)
    await page.getByRole('link', { name: '核对并确认取消' }).click()
    await expect(page).toHaveURL(/\/actions\/action-1$/)
    await expect(page.getByLabel('取消确认内容')).toContainText('Demo Video')
    await page.getByRole('button', { name: '确认并继续' }).click()
    await expect(page.getByText('操作成功', { exact: true })).toBeVisible()
    expect(confirms).toBe(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

for (const width of [1440, 390]) {
  test(`natural-language bill report opens and anomaly review state updates at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => {
      sessionStorage.setItem('bank-agent.access-token', 'access')
      sessionStorage.setItem('bank-agent.refresh-token', 'refresh-token-value-long')
    })
    let agentRequests = 0
    let reviewStatus: 'unreviewed' | 'verified' | 'ignored' = 'unreviewed'
    await page.route('**/api/**', async (route) => {
      const request = route.request()
      const path = new URL(request.url()).pathname
      if (path === '/api/me') return route.fulfill({ json: { id: 'u1', username: 'alice', client_id: 1, is_admin: false } })
      if (path === '/api/accounts') return route.fulfill({ json: [{ id: 7, account_no: '000000007', currency: 'CNY', product_name: '储蓄' }] })
      if (path === '/api/accounts/summary') return route.fulfill({ json: { currency: 'CNY', total: '0', account_count: 1, complete: true } })
      if (path === '/api/actions') return route.fulfill({ json: [] })
      if (path === '/api/health') return route.fulfill({ json: { status: 'UP' } })
      if (path === '/api/agent/messages') {
        agentRequests += 1
        const body = request.postDataJSON() as { message: string }
        if (body.message.includes('报告')) {
          return route.fulfill({ json: {
            trace_id: 'report-opened-ui',
            message: '已找到对应报告任务，正在生成；结果卡会显示进度。',
            events: [{ type: 'BILL_REPORT_OPENED', data: {
              report_id: 'natural-language-report', period: '2026', status: 'queued', generated: false,
            } }],
          } })
        }
        return route.fulfill({ json: {
          trace_id: 'anomaly-review-ui', message: '发现待核实候选。',
          events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'anomaly-review-ui', kind: 'anomalies' } }],
        } })
      }
      if (path === '/api/agent/analyses/anomaly-review-ui') {
        return route.fulfill({ json: {
          analysis_id: 'anomaly-review-ui', kind: 'anomalies', expires_at: '2099-01-01T00:00:00Z',
          data: { account_ids: [7], from_date: '2026-10-01', to_date: '2026-10-31', items: [{
            anomaly_key: 'ui-review-key', rule: 'DUPLICATE_V1', status: 'unreviewed',
            current_review_status: reviewStatus,
            evidence: { merchant: 'Demo Shop', amount: '80.00', date: '2026-10-12', samples: 2 },
          }] },
        } })
      }
      if (path === '/api/billing/anomaly-reviews') {
        expect(request.method()).toBe('POST')
        const body = request.postDataJSON() as { anomaly_key: string; status: 'verified' | 'ignored' }
        expect(body.anomaly_key).toBe('ui-review-key')
        reviewStatus = body.status
        return route.fulfill({ json: { id: 'review-1', anomaly_key: body.anomaly_key, status: reviewStatus } })
      }
      if (path === '/api/bill-report-generations/natural-language-report/status') {
        return route.fulfill({ json: { report_id: 'natural-language-report', status: 'queued', progress: 15, period: '2026' } })
      }
      if (path === '/api/bill-reports/natural-language-report') return route.fulfill({ json: { id: 'natural-language-report', status: 'queued' } })
      return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: '未配置的受控测试接口' } } })
    })

    await installDurableAgentBridge(page, (body) => {
      agentRequests += 1
      if (String(body.message).includes('报告')) {
        return {
          trace_id: 'report-opened-ui',
          message: '已找到对应报告任务，正在生成；结果卡会显示进度。',
          events: [{ type: 'BILL_REPORT_OPENED', data: {
            report_id: 'natural-language-report', period: '2026', status: 'queued', generated: false,
          } }],
        }
      }
      return {
        trace_id: 'anomaly-review-ui', message: '发现待核实候选。',
        events: [{ type: 'ANALYSIS_READY', data: { analysis_id: 'anomaly-review-ui', kind: 'anomalies' } }],
      }
    })
    await page.goto('/')
    await page.getByRole('button', { name: '打开智能助理' }).click()
    await page.getByLabel('给智能银行助理发送消息').fill('查看我的年度账单报告')
    await page.getByRole('button', { name: '发送消息' }).click()
    await expect(page.getByText('已找到对应报告任务，正在生成；结果卡会显示进度。')).toBeVisible()
    await expect(page.getByLabel('账单报告结果')).toContainText('等待生成')
    expect(agentRequests).toBe(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByRole('link', { name: '查看报告进度' }).click()
    await expect(page).toHaveURL(/\/insights\/reports\/natural-language-report$/)

    await page.goto('/')
    await page.getByRole('button', { name: '打开智能助理' }).click()
    await page.getByLabel('给智能银行助理发送消息').fill('查询异常候选')
    await page.getByRole('button', { name: '发送消息' }).click()
    const result = page.getByLabel('授权分析结果')
    await expect(result.getByRole('button', { name: '确认异常' })).toBeVisible()
    await result.getByRole('button', { name: '确认异常' }).click()
    await expect(result.getByRole('button', { name: '已确认' })).toBeDisabled()
    await expect(result.getByRole('button', { name: '忽略' })).toBeEnabled()
    await result.getByRole('button', { name: '忽略' }).click()
    await expect(result.getByRole('button', { name: '已忽略' })).toBeDisabled()
    await expect(result.getByRole('button', { name: '确认异常' })).toBeEnabled()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
