import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { storeTokens } from '@/lib/api'
import { server } from '@/test/server'
import { useAuth } from './auth-context'
import { AuthProvider } from './auth-provider'

function Probe() { const { ready, user } = useAuth(); return <span>{ready ? user?.username ?? 'anonymous' : 'restoring'}</span> }
describe('AuthProvider', () => {
  it('restores a stored session through /me', async () => {
    storeTokens({ access_token: 'access', refresh_token: 'refresh-token-value-long', token_type: 'bearer', expires_in: 60 })
    server.use(http.get('/api/me', () => HttpResponse.json({ id: 'u1', username: 'alice', client_id: 2, is_admin: false })))
    render(<QueryClientProvider client={new QueryClient()}><AuthProvider><Probe /></AuthProvider></QueryClientProvider>)
    expect(await screen.findByText('alice')).toBeInTheDocument()
  })
})
