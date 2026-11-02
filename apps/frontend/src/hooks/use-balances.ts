import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useBalances() {
  const queryClient = useQueryClient()
  const accountsQuery = useQuery({ queryKey: ['accounts'], queryFn: api.accounts, staleTime: 30_000 })
  const summaryQuery = useQuery({ queryKey: ['accounts', 'summary'], queryFn: api.accountSummary, staleTime: 30_000 })
  return {
    accounts: accountsQuery.data ?? [],
    balances: accountsQuery.data ?? [],
    summary: summaryQuery.data,
    total: summaryQuery.data?.total ?? '0',
    isPending: accountsQuery.isPending || summaryQuery.isPending,
    error: accountsQuery.error ?? summaryQuery.error,
    refetch: () => Promise.all([accountsQuery.refetch(), summaryQuery.refetch()]),
    refresh: () => void queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  }
}
