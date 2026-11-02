import { useMemo, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { AgentContext } from './agent-context'

export function AgentProvider({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [open, setOpen] = useState(() => location.pathname === '/agent')
  const value = useMemo(() => ({ open, openPanel: () => setOpen(true), closePanel: () => setOpen(false), togglePanel: () => setOpen((v) => !v) }), [open])
  return <AgentContext.Provider value={value}>{children}</AgentContext.Provider>
}
