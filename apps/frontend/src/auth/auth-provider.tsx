import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, clearTokens, hasStoredSession, storeTokens, type CurrentUser } from '@/lib/api'
import { AuthContext } from './auth-context'


export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [ready, setReady] = useState(false)
  const queryClient = useQueryClient()
  const clearSession = useCallback(() => { clearTokens(); setUser(null); queryClient.clear() }, [queryClient])

  useEffect(() => {
    let active = true
    const restore = async () => {
      if (!hasStoredSession()) { if (active) setReady(true); return }
      try { const current = await api.me(); if (active) setUser(current) }
      catch { if (active) clearSession() }
      finally { if (active) setReady(true) }
    }
    const lost = () => clearSession()
    window.addEventListener('bank-agent-auth-lost', lost)
    void restore()
    return () => { active = false; window.removeEventListener('bank-agent-auth-lost', lost) }
  }, [clearSession])

  const login = useCallback(async (username: string, password: string) => {
    const tokens = await api.login(username, password)
    storeTokens(tokens)
    try { setUser(await api.me()) } catch (error) { clearSession(); throw error }
  }, [clearSession])
  const logout = useCallback(async () => { try { await api.logout() } finally { clearSession() } }, [clearSession])
  const value = useMemo(() => ({ user, ready, login, logout }), [user, ready, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
