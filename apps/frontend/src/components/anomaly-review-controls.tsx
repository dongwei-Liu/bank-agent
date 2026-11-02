import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type AgentAnalysis, type AnomalyReviewStatus } from '@/lib/api'
import { invalidateBillingQueries } from '@/lib/billing-query'

type ReviewableRow = Record<string, unknown> & { anomaly_key?: string; status?: string; current_review_status?: string }

function updateRows(rows: unknown[], anomalyKey: string, status: AnomalyReviewStatus, privateSnapshot: boolean) {
  return rows.map((value) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return value
    const row = value as ReviewableRow
    if (row.anomaly_key !== anomalyKey) return value
    return privateSnapshot
      ? { ...row, current_review_status: status }
      : { ...row, status }
  })
}

function applyReview(value: unknown, anomalyKey: string, status: AnomalyReviewStatus, privateSnapshot: boolean) {
  if (!value || typeof value !== 'object') return value
  if (privateSnapshot) {
    const analysis = value as AgentAnalysis
    if (analysis.kind !== 'anomalies') return value
    return { ...analysis, data: { ...analysis.data, items: updateRows(analysis.data.items, anomalyKey, status, true) } }
  }
  if (Array.isArray(value)) return updateRows(value, anomalyKey, status, false)
  const result = value as Record<string, unknown>
  return Array.isArray(result.items)
    ? { ...result, items: updateRows(result.items, anomalyKey, status, false) }
    : value
}

export function AnomalyReviewControls({ row }: { row: ReviewableRow }) {
  const client = useQueryClient()
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const anomalyKey = row.anomaly_key
  const status = row.current_review_status ?? row.status ?? 'unreviewed'
  const review = useMutation({
    mutationFn: (next: AnomalyReviewStatus) => api.reviewAnomaly(anomalyKey!, next),
    onSuccess: (response, requested) => {
      const saved = response.status ?? requested
      client.setQueriesData<AgentAnalysis>({ queryKey: ['private-analysis'] }, (current) =>
        applyReview(current, anomalyKey!, saved, true) as AgentAnalysis,
      )
      client.setQueriesData({ queryKey: ['billing-anomalies'] }, (current) =>
        applyReview(current, anomalyKey!, saved, false),
      )
      invalidateBillingQueries(client)
      void client.invalidateQueries({ queryKey: ['private-analysis'] })
      setMessage(saved === 'verified' ? '异常候选已确认。' : '异常候选已忽略。')
      setError('')
    },
    onError: (reason) => {
      setError(reason instanceof Error ? reason.message : '提交失败，请刷新后重试。')
      setMessage('')
    },
  })

  if (!anomalyKey) return null
  const pendingStatus = review.isPending ? review.variables : undefined
  const verified = status === 'verified'
  const ignored = status === 'ignored'
  const base = 'rounded-md px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-60'
  return <div className="mt-2 space-y-1">
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        aria-pressed={verified}
        disabled={review.isPending || verified}
        onClick={() => review.mutate('verified')}
        className={`${base} ${verified ? 'bg-emerald-700 text-white' : 'bg-slate-900 text-white'}`}
      >{pendingStatus === 'verified' ? '确认中…' : verified ? '已确认' : '确认异常'}</button>
      <button
        type="button"
        aria-pressed={ignored}
        disabled={review.isPending || ignored}
        onClick={() => review.mutate('ignored')}
        className={`${base} ${ignored ? 'border border-slate-400 bg-slate-200 text-slate-800' : 'border border-slate-300 bg-white text-slate-800'}`}
      >{pendingStatus === 'ignored' ? '忽略中…' : ignored ? '已忽略' : '忽略'}</button>
    </div>
    {message && <p role="status" className="text-xs text-emerald-800">{message}</p>}
    {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
  </div>
}
