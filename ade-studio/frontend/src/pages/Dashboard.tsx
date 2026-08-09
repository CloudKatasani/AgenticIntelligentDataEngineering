import { Link } from 'react-router-dom'
import { DomainBadge, Empty, Section, Spinner, Stat, StatusBadge } from '../components/ui'
import { useQuery } from '../lib/hooks'
import { formatCost, formatDateTime } from '../lib/format'

interface DashboardData {
  fleet: {
    agents: number
    core_agents: number
    by_domain: Record<string, number>
    by_tier: Record<string, number>
    requiring_approval: number
  }
  activity: {
    total_runs: number
    by_status: Record<string, number>
    total_cost_usd: number
    total_artifacts: number
    awaiting_approval: number
    agents_exercised: number
    recent: {
      id: string
      agent_id: string
      agent_name: string
      status: string
      created_at: string
      artifact_count: number
    }[]
  }
  connections: number
}

export default function Dashboard() {
  const { data, loading, error } = useQuery<DashboardData>('/api/dashboard')

  if (loading) return <Spinner label="Loading fleet status" />
  if (error || !data) return <Empty title="Could not load the dashboard" hint={error ?? undefined} />

  const domainMax = Math.max(...Object.values(data.fleet.by_domain), 1)

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white">Fleet overview</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-400">
          Thirty-five specialised agents with non-overlapping scope, typed dependencies and
          structural autonomy tiers. Pick an agent, point it at a database object, choose the model
          for that task, and download what it produces.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Agents in fleet"
          value={data.fleet.agents}
          hint={`${data.fleet.core_agents} from the original core scope`}
        />
        <Stat
          label="Runs executed"
          value={data.activity.total_runs}
          hint={`${data.activity.agents_exercised} distinct agents exercised`}
        />
        <Stat
          label="Artifacts produced"
          value={data.activity.total_artifacts}
          hint={`${formatCost(data.activity.total_cost_usd)} total model spend`}
        />
        <Stat
          label="Awaiting acceptance"
          value={data.activity.awaiting_approval}
          hint={`${data.fleet.requiring_approval} agents are advisory by tier`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section
          title="Fleet by domain"
          description="Scope is partitioned so no two agents own the same ground."
        >
          <ul className="space-y-3">
            {Object.entries(data.fleet.by_domain).map(([domain, count]) => (
              <li key={domain} className="flex items-center gap-3">
                <div className="w-32 shrink-0">
                  <DomainBadge domain={domain} />
                </div>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink-800">
                  <div
                    className="h-full rounded-full bg-accent/70"
                    style={{ width: `${(count / domainMax) * 100}%` }}
                  />
                </div>
                <span className="w-6 text-right text-sm tabular-nums text-slate-400">{count}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section
          title="Autonomy tiers"
          description="Tier is a structural property of the agent, not a measure of its confidence."
        >
          <ul className="space-y-3">
            {['L0', 'L1', 'L2', 'L3', 'L4'].map((tier) => {
              const count = data.fleet.by_tier[tier] ?? 0
              return (
                <li key={tier} className="flex items-center gap-3">
                  <span className="w-8 font-mono text-sm text-slate-400">{tier}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink-800">
                    <div
                      className="h-full rounded-full bg-sky-400/60"
                      style={{ width: `${(count / data.fleet.agents) * 100}%` }}
                    />
                  </div>
                  <span className="w-6 text-right text-sm tabular-nums text-slate-400">{count}</span>
                </li>
              )
            })}
          </ul>
          <p className="mt-4 text-xs text-slate-500">
            L0 and L1 agents produce proposals that a human must accept. Only agent 20 may act on
            production data, and only from a versioned action catalog.
          </p>
        </Section>
      </div>

      <Section
        title="Recent runs"
        description="Every run keeps its gates, provenance and artifacts."
        actions={
          <Link to="/runs" className="btn-ghost">
            All runs
          </Link>
        }
      >
        {data.activity.recent.length === 0 ? (
          <Empty
            title="No runs yet"
            hint="Open the agent fleet, pick an agent and run it against the demo warehouse."
          />
        ) : (
          <ul className="divide-y divide-ink-800">
            {data.activity.recent.map((run) => (
              <li key={run.id}>
                <Link
                  to={`/runs/${run.id}`}
                  className="flex flex-wrap items-center gap-3 py-3 transition hover:opacity-80"
                >
                  <span className="font-mono text-xs text-slate-500">{run.agent_id}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-slate-200">
                    {run.agent_name}
                  </span>
                  <StatusBadge status={run.status} />
                  <span className="text-xs text-slate-500">{run.artifact_count} artifacts</span>
                  <span className="w-28 text-right text-xs text-slate-500">
                    {formatDateTime(run.created_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}
