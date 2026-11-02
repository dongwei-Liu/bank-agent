import { describe, expect, it } from 'vitest'
import { billPresentation, formatAccountNo, shanghaiDateKey } from './format'

describe('formatAccountNo', () => {
  it('只显示普通账户号的最后四位', () => {
    expect(formatAccountNo('000000002')).toBe('**** 0002')
  })

  it('短账号和空值也不会原样展示', () => {
    expect(formatAccountNo('123')).toBe('**** 123')
    expect(formatAccountNo('')).toBe('****')
  })

  it('展示前移除账号中的空白字符', () => {
    expect(formatAccountNo('0000 0000 1234')).toBe('**** 1234')
  })
})

it('uses Shanghai calendar days instead of the browser timezone', () => {
  expect(shanghaiDateKey(new Date('2026-10-31T16:30:00.000Z'))).toBe('2026-11-01')
})

it.each([
  ['2026-09-01', '2026-09-30', 'month', '2026 年 9 月 · 消费分类统计'],
  ['2024-02-01', '2024-02-29', 'month', '2024 年 2 月 · 消费分类统计'],
  ['2026-01-01', '2026-12-31', 'year', '2026 年 · 年度消费分类统计'],
  ['2026-01-01', '2026-09-30', 'range', '区间消费统计'],
  ['2026-09-02', '2026-09-30', 'range', '区间消费统计'],
  ['2026-13-01', '2026-13-31', 'range', '区间消费统计'],
])('classifies %s through %s', (from, to, kind, title) => {
  expect(billPresentation(from, to)).toEqual({ kind, title })
})
