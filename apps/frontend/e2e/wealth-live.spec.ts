import { expect, test } from '@playwright/test'


test.skip(process.env.BANK_AGENT_LIVE_E2E !== '1', '仅在显式启用本机真实栈验收时运行')

test('真实前端完成定存目录、比较、推荐、测评和待确认申购', async ({ page }) => {
  const password = process.env.BANK_AGENT_DEMO_PASSWORD
  if (!password) throw new Error('BANK_AGENT_DEMO_PASSWORD is required')

  await page.goto('/login')
  await page.getByLabel('用户名').fill('alice')
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '安全登录' }).click()
  await expect(page).toHaveURL(/\/$/)

  await page.goto('/wealth')
  await expect(page.getByRole('heading', { name: '定存与财富' })).toBeVisible()
  const threeMonth = page.locator('article').filter({ hasText: 'BANK_AGENT_DEMO_FIXED_3M' })
  const sixMonth = page.locator('article').filter({ hasText: 'BANK_AGENT_DEMO_FIXED_6M' })
  await expect(threeMonth).toBeVisible()
  await expect(sixMonth).toBeVisible()

  await page.getByRole('checkbox', { name: 'BANK_AGENT_DEMO_FIXED_3M 加入比较' }).check()
  await page.getByRole('checkbox', { name: 'BANK_AGENT_DEMO_FIXED_6M 加入比较' }).check()
  await page.getByRole('button', { name: /比较已选 2 项/ }).click()
  const comparison = page.getByLabel('产品比较结果')
  await expect(comparison.getByText(/金额：¥100(?:\.0+)?–¥100000(?:\.0+)?/)).toHaveCount(2)

  await page.getByRole('button', { name: '本次申购测评' }).click()
  await expect(page.getByRole('heading', { name: '本次申购风险测评' })).toBeVisible()
  for (const fieldset of await page.locator('fieldset').all()) {
    await fieldset.locator('input[type="radio"]').first().check()
  }
  await page.getByRole('button', { name: '提交本次测评' }).click()
  await expect(page).toHaveURL(/\/wealth$/)
  await expect(page.getByText(/已有未使用的 15 分钟测评，风险等级 1/)).toBeVisible()

  await page.getByPlaceholder('金额').fill('1000')
  await page.getByLabel('期限（月）').fill('3')
  await page.getByRole('button', { name: '获取推荐' }).click()
  await expect(page.getByText('匹配产品：BANK_AGENT_DEMO_FIXED_3M')).toBeVisible()
  await expect(page.getByText(/Demo 年利率 1(?:\.0+)?% · 预估利息 ¥2\.50/)).toBeVisible()

  const refreshedThreeMonth = page.locator('article').filter({ hasText: 'BANK_AGENT_DEMO_FIXED_3M' })
  await refreshedThreeMonth.getByRole('button', { name: '申购' }).click()
  await refreshedThreeMonth.getByLabel('付款账户').selectOption({ index: 1 })
  await refreshedThreeMonth.getByPlaceholder('申购金额').fill('1000')
  await refreshedThreeMonth.getByLabel('申购期限（月）').fill('3')
  await refreshedThreeMonth.getByRole('button', { name: '进入安全确认' }).click()

  await expect(page).toHaveURL(/\/actions\//)
  await expect(page.getByRole('heading', { name: '确认定存申购' })).toBeVisible()
  await expect(page.getByText('等待你确认参数')).toBeVisible()
})

test('真实 React 智能助手返回定存产品与适配推荐卡', async ({ page }) => {
  test.setTimeout(360_000)
  const password = process.env.BANK_AGENT_DEMO_PASSWORD
  if (!password) throw new Error('BANK_AGENT_DEMO_PASSWORD is required')

  await page.goto('/login')
  await page.getByLabel('用户名').fill('alice')
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '安全登录' }).click()
  await expect(page).toHaveURL(/\/$/)

  await page.goto('/wealth/risk-assessment')
  await expect(page.getByRole('heading', { name: '本次申购风险测评' })).toBeVisible()
  await expect(page.locator('fieldset')).toHaveCount(5)
  for (const fieldset of await page.locator('fieldset').all()) {
    await fieldset.locator('input[type="radio"]').first().check()
  }
  await page.getByRole('button', { name: '提交本次测评' }).click()
  await expect(page).toHaveURL(/\/wealth$/)

  await page.getByRole('button', { name: '打开智能助理' }).click()
  const dialog = page.getByRole('dialog', { name: '智能银行助理' })
  const createdConversation = page.waitForResponse((response) =>
    response.request().method() === 'POST'
    && response.url().endsWith('/api/agent/conversations')
    && response.ok(),
  )
  const loadedConversation = page.waitForResponse((response) =>
    response.request().method() === 'GET'
    && /\/api\/agent\/conversations\/[^/]+$/.test(new URL(response.url()).pathname)
    && response.ok(),
  )
  await dialog.getByRole('button', { name: '新建对话' }).click()
  await createdConversation
  await loadedConversation
  const input = dialog.getByLabel('给智能银行助理发送消息')

  const catalogPrompt = '查询目前可用的人民币定存产品。'
  await input.fill(catalogPrompt)
  const send = dialog.getByRole('button', { name: '发送消息' })
  await expect(send).toBeEnabled()
  await send.click()
  await expect(dialog.getByText('定存产品目录')).toBeVisible({ timeout: 180_000 })
  await expect(dialog.getByText('BANK_AGENT_DEMO_FIXED_3M')).toBeVisible()
  await expect(dialog.getByText('BANK_AGENT_DEMO_FIXED_6M')).toBeVisible()

  const recommendationPrompt = '我想存1000元，期限3个月，需要流动性，请推荐适合我的定存产品。'
  await input.fill(recommendationPrompt)
  await expect(send).toBeEnabled()
  await send.click()
  await expect(dialog.getByText('定存适配推荐')).toBeVisible({ timeout: 180_000 })
  await expect(dialog.getByText('BANK_AGENT_DEMO_FIXED_3M').last()).toBeVisible()
  await expect(dialog.getByText(/按 ¥1,000\.00、3 个月、需要流动性筛选/)).toBeVisible()
  await expect(dialog.getByRole('alert')).toHaveCount(0)
})
