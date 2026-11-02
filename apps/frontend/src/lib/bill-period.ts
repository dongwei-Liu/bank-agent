import { shanghaiDateKey } from './format'

export type PeriodRange = {
  kind: 'month' | 'year'
  label: string
  fromDate: string
  toDate: string
  previous: string
  next: string | null
  year: string
  month: string
}

export function resolveBillPeriod(period: string, currentDate = new Date()): PeriodRange | null {
  const today = shanghaiDateKey(currentDate)
  const currentMonth = today.slice(0, 7)
  const currentYear = today.slice(0, 4)
  if (/^\d{4}-\d{2}$/.test(period)) {
    const [year, month] = period.split('-').map(Number)
    if (month < 1 || month > 12 || period > currentMonth) return null
    const end = `${period}-${String(new Date(year, month, 0).getDate()).padStart(2, '0')}`
    const previousDate = new Date(year, month - 2, 1)
    const nextDate = new Date(year, month, 1)
    const next = `${nextDate.getFullYear()}-${String(nextDate.getMonth() + 1).padStart(2, '0')}`
    return {
      kind: 'month', label: `${year} 年 ${month} 月 · 月度账单`,
      fromDate: `${period}-01`, toDate: period === currentMonth ? today : end,
      previous: `${previousDate.getFullYear()}-${String(previousDate.getMonth() + 1).padStart(2, '0')}`,
      next: next > currentMonth ? null : next, year: String(year), month: period,
    }
  }
  if (/^\d{4}$/.test(period) && period <= currentYear) {
    const year = Number(period)
    return {
      kind: 'year', label: `${year} 年 · 年度账单`,
      fromDate: `${period}-01-01`, toDate: period === currentYear ? today : `${period}-12-31`,
      previous: String(year - 1), next: String(year + 1) > currentYear ? null : String(year + 1),
      year: period, month: period === currentYear ? currentMonth : `${period}-12`,
    }
  }
  return null
}
