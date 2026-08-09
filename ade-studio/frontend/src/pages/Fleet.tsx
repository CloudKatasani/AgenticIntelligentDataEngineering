import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { DomainBadge, Empty, Spinner, TierBadge } from '../components/ui'
import type { AgentSummary } from '../lib/api'
import { useQuery } from '../lib/hooks'

interface FleetResponse {
  count: number
  domains: string[]
  agents: AgentSummary[]
}

export default function Fleet() {
  const { data, loading, error } = useQuery<FleetResponse>('/api/agents')
  const [search, setSearch] = useState('')
  const [domain, setDomain] = useState<string>('all')
  const [tier, setTier] = useState<string>('all')
  const [coreOnly, setCoreOnly] = useState(false)

  const filtered = useMemo(() => {
    if (!data) return []
    const needle = search.trim().toLowerCase()
    return data.agents.filter((agent) => {
      if (domain !== 'all' && agent.domain !== domain) return false
      if (tier !== 'all' && agent.tier !== tier) return false
      if (coreOnly && !agent.core_original_scope) return false
      if (!needle) return true
      return (
        agent.name.toLowerCase().includes(needle) ||
        agent.purpose.toLowerCase().includes(needle) ||
        agent.id.includes(needle) ||
        agent.slug.includes(needle)
      )
    })
  }, [data, search, domain, tier, coreOnly])

  if (loading) return <Spinner label="Loading the agent catalog" />
  if (error || !data) return <Empty title="Could not load the fleet" hint={error ?? undefined} />

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">Agent fleet</h1>
          <p className="mt-1 text-sm text-slate-400">
            {data.count} agents. Select one to configure and run it.
          </p>
        </div>
      </header>

      <div className="card card-pad">
        <div className="grid gap-3 md:grid-cols-[1fr_auto_auto_auto]">
          <input
            className="input"
            placeholder="Search by name, purpose or id…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <select className="input md:w-44" value={domain} onChange={(e) => setDomain(e.target.value)}>
            <option value="all">All domains</option>
            {data.domains.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <select className="input md:w-36" value={tier} onChange={(e) => setTier(e.target.value)}>
            <option value="all">All tiers</option>
            {['L0', 'L1', 'L2', 'L3', 'L4'].map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setCoreOnly((value) => !value)}
            className={coreOnly ? 'btn-primary' : 'btn-ghost'}
          >
            ★ Core six
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <Empty title="No agents match those filters" hint="Try clearing the search or filters." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((agent) => (
            <Link
              key={agent.id}
              to={`/agents/${agent.id}`}
              className="card group flex flex-col p-5 transition hover:border-accent/40 hover:bg-ink-850"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-mono text-xs text-slate-500">{agent.id}</span>
                <div className="flex flex-wrap justify-end gap-1.5">
                  {agent.core_original_scope ? (
                    <span className="chip border-accent/40 bg-accent/10 text-accent">★ core</span>
                  ) : null}
                  <TierBadge tier={agent.tier} />
                </div>
              </div>

              <h3 className="mt-2 text-base font-semibold text-white group-hover:text-accent">
                {agent.name}
              </h3>
              <p className="mt-2 line-clamp-3 flex-1 text-sm leading-relaxed text-slate-400">
                {agent.purpose}
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <DomainBadge domain={agent.domain} />
                {agent.hard_dependencies.length > 0 ? (
                  <span className="chip border-ink-600 bg-ink-800 text-slate-400">
                    needs {agent.hard_dependencies.map((d) => d.agent_id).join(', ')}
                  </span>
                ) : (
                  <span className="chip border-ink-600 bg-ink-800 text-slate-500">no hard deps</span>
                )}
                <span className="chip border-ink-600 bg-ink-800 text-slate-400">
                  {agent.artifact_count} artifacts
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
