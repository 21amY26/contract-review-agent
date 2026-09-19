import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { FileText, LayoutDashboard, Layers, Settings as SettingsIcon } from 'lucide-react'

const navItems = [
  { to: '/', label: 'Home', icon: LayoutDashboard },
  { to: '/analysis', label: 'Analysis', icon: FileText },
  { to: '/reports', label: 'Reports', icon: Layers },
  { to: '/history', label: 'History', icon: FileText },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

export default function AppShell() {
  const navigate = useNavigate()
  const rawUser = localStorage.getItem('currentUser')
  const user = rawUser ? JSON.parse(rawUser) : null
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.16),_transparent_38%),_#020617] text-slate-50">
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-cyan-400">
              Contract Review AI
            </p>
            <p className="text-sm text-slate-400">Agentic contract review and compliance risk management</p>
          </div>
          <nav className="flex items-center gap-2">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
                    isActive
                      ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-950/30'
                      : 'text-slate-200 hover:bg-slate-800'
                  }`
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            {user ? (
              <>
                <div className="text-sm text-slate-200">{user.name ?? user.email}</div>
                <button
                  type="button"
                  onClick={() => {
                    localStorage.removeItem('currentUser')
                    localStorage.removeItem('token')
                    navigate('/login')
                  }}
                  className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-200"
                >
                  Sign out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login" className="text-sm text-slate-200 hover:text-white">Sign in</NavLink>
                <NavLink to="/signup" className="text-sm text-slate-200 hover:text-white">Create account</NavLink>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8 sm:py-10">
        <Outlet />
      </main>
    </div>
  )
}
