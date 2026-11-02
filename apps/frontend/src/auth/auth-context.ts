import { createContext, useContext } from 'react'

import type { CurrentUser } from '@/lib/api'

export type AuthContextValue = {
  user: CurrentUser | null
  ready: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return value
}
