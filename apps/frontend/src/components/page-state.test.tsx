import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/api'
import { ErrorState } from './page-state'

describe('ErrorState', () => {
  it('allows a retry for recoverable query failures', () => {
    const retry = vi.fn()
    render(<ErrorState error={new ApiError(0, { code: 'REQUEST_TIMEOUT', message: '请求超时', retryable: true })} onRetry={retry} />)
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(screen.getAllByText('请求超时')).toHaveLength(2)
    expect(retry).toHaveBeenCalledOnce()
  })

  it('does not offer a retry when a write result is unknown', () => {
    render(<ErrorState error={new ApiError(0, { code: 'WRITE_RESULT_UNKNOWN', message: '请核对结果', retryable: false })} onRetry={vi.fn()} />)
    expect(screen.getByText('操作结果尚未确定')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重试' })).not.toBeInTheDocument()
  })

  it('distinguishes a missing resource from an unavailable future service', () => {
    const error = new ApiError(404, { code: 'NOT_FOUND', message: '资源不存在' })
    const { rerender } = render(<ErrorState error={error} />)
    expect(screen.getByText('没有找到相关内容')).toBeInTheDocument()
    rerender(<ErrorState error={error} unavailableWhenMissing />)
    expect(screen.getByText('服务尚未接入')).toBeInTheDocument()
  })
})
