import { LoaderCircle } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/auth/auth-context'

export function ProtectedRoute() {
  const { user, ready } = useAuth()
  const location = useLocation()
  if (!ready) return <div className="flex min-h-svh items-center justify-center gap-2 text-sm text-ink-500"><LoaderCircle className="size-4 animate-spin" />正在恢复安全会话…</div>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}
