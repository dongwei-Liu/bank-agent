/**
 * 金额展示格式化。
 *
 * 后端返回的金额是字符串（Decimal），这里只在**展示**时转成数字。
 * 业务计算一律在后端完成——前端不做任何金额运算，避免精度问题和造假嫌疑。
 */

export function formatMoney(amount: string, currency = 'CNY'): string {
  const value = Number(amount)

  if (Number.isNaN(value)) {
    return amount
  }

  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

export function formatAccountNo(accountNo: string): string {
  const compact = accountNo.replace(/\s/g, '')

  if (!compact) {
    return '****'
  }

  return `**** ${compact.slice(-4)}`
}

export function shanghaiDateKey(date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date)
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

/** Only complete calendar periods receive a monthly/yearly statistics title. */
export function billPresentation(fromDate: string, toDate: string): { kind: 'month' | 'year' | 'range'; title: string } {
  const fallback = { kind: 'range' as const, title: '区间消费统计' }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(fromDate) || !/^\d{4}-\d{2}-\d{2}$/.test(toDate)) return fallback
  const [year, month, day] = fromDate.split('-').map(Number)
  if (month < 1 || month > 12 || day !== 1) return fallback
  if (fromDate === `${year}-01-01` && toDate === `${year}-12-31`) return { kind: 'year', title: `${year} 年 · 年度消费分类统计` }
  const end = new Date(`${fromDate}T00:00:00Z`)
  end.setUTCMonth(end.getUTCMonth() + 1, 0)
  if (toDate === end.toISOString().slice(0, 10)) return { kind: 'month', title: `${year} 年 ${month} 月 · 消费分类统计` }
  return fallback
}
