import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useQuery } from '../lib/hooks'

interface Health {
  agents_loaded: number
  graph_acyclic: boolean
  provider: { provider: string; live: boolean; detail: string }
}

const NAV = [
  { to: '/', label: 'Overview', end: true, icon: '◈' },
  { to: '/fleet', label: 'Agent fleet', icon: '⬡' },
  { to: '/runs', label: 'Runs & artifacts', icon: '▤' },
  { to: '/academy', label: 'Academy', icon: '✦' },
  { to: '/graph', label: 'Dependency graph', icon: '⇄' },
  { to: '/connections', label: 'Sources', icon: '⛁' },
]

export default function Layout({ children }: { children: ReactNode }) {
  const { data: health } = useQuery<Health>('/api/health')

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-ink-800 bg-ink-900/50 lg:flex">
        <div className="border-b border-ink-800 px-5 py-5">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-ink-950">
              A
            </span>
            <div>
              <div className="text-sm font-semibold text-white">ADE Studio</div>
              <div className="text-[11px] text-slate-500">Agentic Data Engineering</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  isActive
                    ? 'bg-accent/10 font-medium text-accent'
                    : 'text-slate-400 hover:bg-ink-850 hover:text-slate-200'
                }`
              }
            >
              <span className="w-4 text-center text-xs opacity-70">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-ink-800 p-4 text-[11px] leading-relaxed text-slate-500">
          <div className="flex items-center gap-2">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                health?.provider.live ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
            <span className="font-medium text-slate-400">
              {health?.provider.live ? 'Claude models connected' : 'Offline simulation mode'}
            </span>
          </div>
          <p className="mt-1.5">{health?.provider.detail}</p>
          <p className="mt-3 border-t border-ink-800 pt-3">
            {health?.agents_loaded ?? '—'} agents loaded ·{' '}
            {health?.graph_acyclic ? 'graph acyclic' : 'graph has cycles'}
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-ink-800 bg-ink-900/50 px-4 py-3 lg:hidden">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-xs font-bold text-ink-950">
            A
          </span>
          <span className="text-sm font-semibold text-white">ADE Studio</span>
          <nav className="ml-auto flex gap-1 overflow-x-auto">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-md px-2 py-1 text-xs ${
                    isActive ? 'bg-accent/10 text-accent' : 'text-slate-400'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  )
}
