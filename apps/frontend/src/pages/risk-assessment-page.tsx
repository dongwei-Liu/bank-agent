import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import { api, type JsonObject } from '@/lib/api'

export function RiskAssessmentPage() {
  const navigate = useNavigate(); const client = useQueryClient(); const query = useQuery({ queryKey: ['questionnaire'], queryFn: api.questionnaire }); const [answers, setAnswers] = useState<number[]>([])
  const submit = useMutation({ mutationFn: () => api.assess(answers), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['risk-assessments'] }); navigate('/wealth') } })
  if (query.isPending) return <LoadingState label="正在读取风险问卷…" />
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const questions = (query.data?.questions as JsonObject[]) ?? []
  return <div className="mx-auto max-w-2xl space-y-4"><div><h1 className="text-xl font-semibold">本次申购风险测评</h1><p className="mt-1 text-sm text-ink-500">结果在 15 分钟内仅可用于一笔定存申购，不构成投资建议。</p></div><form onSubmit={(e) => { e.preventDefault(); submit.mutate() }} className="space-y-4">{questions.map((question, index) => <fieldset key={String(question.id)} className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><legend className="font-medium">{index + 1}. {String(question.text)}</legend><div className="mt-3 space-y-2">{(question.choices as string[]).map((choice, choiceIndex) => <label key={choice} className="flex items-center gap-2 text-sm"><input type="radio" name={`q${index}`} checked={answers[index] === choiceIndex + 1} onChange={() => setAnswers((old) => { const next = [...old]; next[index] = choiceIndex + 1; return next })} />{choice}</label>)}</div></fieldset>)}<Button type="submit" disabled={answers.filter(Boolean).length !== questions.length || submit.isPending} className="bg-brand-600">提交本次测评</Button>{submit.error && <p className="text-sm text-red-600">{submit.error.message}</p>}</form></div>
}
