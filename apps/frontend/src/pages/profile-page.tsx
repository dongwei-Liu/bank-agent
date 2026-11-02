import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/auth-context'
import { ErrorState, LoadingState } from '@/components/page-state'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'

export function ProfilePage() {
  const { user, logout } = useAuth(); const navigate = useNavigate(); const actions = useQuery({ queryKey: ['actions'], queryFn: api.actions })
  return <div className="space-y-4"><div><h1 className="text-xl font-semibold">我的</h1><p className="mt-1 text-sm text-ink-500">当前身份与本人操作记录</p></div><section className="rounded-xl bg-white p-5 ring-1 ring-slate-200"><p className="font-semibold">{user?.username}</p><p className="mt-1 text-sm text-ink-500">客户 ID {user?.client_id} · {user?.is_admin ? '管理员' : '普通用户'} · 开发环境</p><Button className="mt-4" variant="outline" onClick={async () => { await logout(); navigate('/login') }}>退出登录</Button></section><section className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><h2 className="font-semibold">本人操作记录</h2>{actions.isPending ? <LoadingState label="加载中…" /> : actions.error ? <ErrorState error={actions.error} onRetry={() => void actions.refetch()} /> : <div className="mt-3 divide-y">{actions.data?.map((a) => <Link key={a.id} to={`/actions/${a.id}`} className="flex justify-between py-3 text-sm"><span>{a.kind} · ¥{a.amount}</span><span className="text-ink-500">{a.status}</span></Link>)}{!actions.data?.length && <p className="py-4 text-sm text-ink-500">暂无操作记录</p>}</div>}</section></div>
}
