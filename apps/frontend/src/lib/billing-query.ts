import type { QueryClient } from '@tanstack/react-query'

/** Refresh every live view whose classification may have changed. */
export function invalidateBillingQueries(client: QueryClient) {
  for (const queryKey of [
    ['categories'],
    ['classification-rules'],
    ['transaction-annotations'],
    ['transactions'],
    ['transaction'],
    ['billing-statistics'],
    ['billing-anomalies'],
  ]) {
    void client.invalidateQueries({ queryKey })
  }
}
