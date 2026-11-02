import { createContext, useContext } from 'react'

export type AgentApi = {
  open: boolean
  openPanel: () => void
  closePanel: () => void
  togglePanel: () => void
}

export const AgentContext = createContext<AgentApi | null>(null)

export function useAgent() {
  const value = useContext(AgentContext)
  if (!value) throw new Error('useAgent 必须在 <AgentProvider> 内部使用')
  return value
}
