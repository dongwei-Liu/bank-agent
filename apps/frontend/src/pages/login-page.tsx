import { useEffect, useState } from 'react'
import { Landmark, LoaderCircle, LockKeyhole } from 'lucide-react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/auth-context'

export function LoginPage() {
  const { user, ready, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('alice')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { document.title = '登录 · 智汇银行' }, [])

  if (ready && user) return <Navigate to="/" replace />
  return <main className="flex min-h-svh items-center justify-center bg-gradient-to-br from-brand-900 via-brand-700 to-brand-500 p-4">
    <section className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl shadow-black/20">
      <div className="flex items-center gap-3"><span className="flex size-12 items-center justify-center rounded-2xl bg-brand-600 text-white"><Landmark className="size-6" /></span><div><h1 className="text-xl font-semibold text-ink-900">智汇银行</h1><p className="text-xs text-ink-500">Bank Agent 安全登录</p></div></div>
      <form className="mt-7 space-y-4" onSubmit={async (event) => { event.preventDefault(); setPending(true); setError(''); try { await login(username, password); const from = (location.state as { from?: string } | null)?.from; navigate(from && from !== '/login' ? from : '/', { replace: true }) } catch (reason) { setError(reason instanceof Error ? reason.message : '登录失败') } finally { setPending(false) } }}>
        <label className="block"><span className="mb-1.5 block text-xs font-medium text-ink-700">用户名</span><input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} className="h-11 w-full rounded-xl border border-slate-300 px-3 text-sm outline-none focus:border-brand-500" /></label>
        <label className="block"><span className="mb-1.5 block text-xs font-medium text-ink-700">密码</span><input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 w-full rounded-xl border border-slate-300 px-3 text-sm outline-none focus:border-brand-500" placeholder="填写 .env 中的 DEMO_PASSWORD" /></label>
        {error && <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button disabled={pending || !username || !password} className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-brand-600 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">{pending ? <LoaderCircle className="size-4 animate-spin" /> : <LockKeyhole className="size-4" />}安全登录</button>
      </form>
      <p className="mt-5 text-center text-xs leading-relaxed text-ink-500">演示环境账号：alice / bob / charlie / mom<br />密码不会写入前端代码或浏览器永久存储。</p>
    </section>
  </main>
}
