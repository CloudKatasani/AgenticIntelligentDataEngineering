import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarSeries,
  DomainBadge,
  Empty,
  ErrorNote,
  InfoNote,
  Meter,
  Section,
  Spinner,
  Stat,
  TierBadge,
} from '../components/ui'
import { useQuery } from '../lib/hooks'
import {
  domainStyle,
  formatAge,
  formatCost,
  formatDateTime,
  formatDuration,
  formatNumber,
  formatTokens,
  pct,
} from '../lib/format'

interface Bucket {
  runs: number
  succeeded: number
  awaiting_approval: number
  blocked: number
  failed: number
  partial: number
  rejected: number
  completion_rate: number
  block_rate: number
  artifacts: number
  objects: number
  cost_usd: number
  modelled_cost_usd: number
  cost_per_run_usd: number
  cost_per_artifact_usd: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  p50_duration_ms: number | null
  p95_duration_ms: number | null
  distinct_users: number
  distinct_models: number
  simulated_runs: number
  live_runs: number
  first_run_at: string
  last_run_at: string
}

interface AgentRow extends Bucket {
  agent_id: string
  agent_name: string
  domain: string
  tier: string
  core: boolean
  requires_approval: boolean
  overrides: number
  blocked_by_gate: Record<string, number>
}

interface Snapshot {
  window_days: number
  generated_at: string
  identity_basis: string
  totals: {
    runs: number
    runs_in_window: number
    artifacts: number
    objects_processed: number
    spend_usd: number
    spend_in_window_usd: number
    modelled_spend_usd: number
    total_tokens: number
    fleet_size: number
    agents_exercised: number
    fleet_coverage: number
    distinct_users: number
    awaiting_approval: number
    live_runs: number
    simulated_runs: number
    never_executed_runs: number
    simulated_share: number
  }
  portfolio: {
    fleet_size: number
    exercised: number
    coverage: number
    core_agents: number
    core_exercised: number
    core_coverage: number
    top_agent_id: string
    top_agent_share: number
    never_run: { id: string; name: string; domain: string; tier: string; core: boolean }[]
    by_domain: { key: string; agents: number; exercised: number; runs: number; cost_usd: number; coverage: number }[]
    by_tier: { key: string; agents: number; exercised: number; runs: number; cost_usd: number; coverage: number }[]
  }
  agents: AgentRow[]
  usage: {
    status_mix: Record<string, number>
    p50_duration_ms: number | null
    p95_duration_ms: number | null
    max_duration_ms: number | null
    gates: { name: string; evaluated: number; blocked: number; block_rate: number }[]
    overrides: { run_id: string; agent_id: string; agent_name: string; actor: string; reason: string; at: string }[]
    override_count: number
    handoffs_recorded: number
    pending_approvals: {
      run_id: string
      agent_id: string
      agent_name: string
      actor: string
      created_at: string
      age_hours: number | null
      artifacts: number
    }[]
    pending_count: number
    approvals_granted: number
    median_approval_lag_hours: number | null
    daily: { date: string; value: number; runs: number }[]
  }
  finops: {
    spend_usd: number
    spend_in_window_usd: number
    modelled_spend_usd: number
    wasted_usd: number
    wasted_share: number
    by_model: (Bucket & {
      model_id: string
      display_name: string
      model_tier: string
      input_usd_per_mtok: number | null
      output_usd_per_mtok: number | null
    })[]
    by_domain: (Bucket & { key: string })[]
    top_agents: (Bucket & { agent_id: string; agent_name: string; domain: string })[]
    capped_runs: number
    near_cap: { run_id: string; agent_id: string; agent_name: string; cost_usd: number; cap_usd: number; utilisation: number }[]
    daily: { date: string; value: number; runs: number }[]
    daily_modelled: { date: string; value: number; runs: number }[]
    projection: { daily_usd: number; monthly_usd: number; basis: string }
  }
  adoption: {
    total_users: number
    active_in_window: number
    new_in_window: number
    returning_users: number
    returning_rate: number
    median_fleet_breadth: number
    users: (Bucket & {
      actor: string
      agents_used: number
      fleet_breadth: number
      approvals_given: number
      active_in_window: boolean
      new_in_window: boolean
    })[]
    daily_active: { date: string; value: number; runs: number }[]
  }
}

const WINDOWS = [7, 30, 90]

const GATE_LABELS: Record<string, string> = {
  object_selection: 'Object selection',
  object_budget: 'Object budget',
  required_parameters: 'Required parameters',
  hard_dependencies: 'Hard dependencies',
  autonomy_tier: 'Autonomy tier',
  production_actions: 'Production actions',
  cost_cap: 'Cost cap',
}

type SortKey = 'runs' | 'cost_usd' | 'artifacts' | 'distinct_users' | 'block_rate'

export default function Observability() {
  const [days, setDays] = useState(30)
  const [sort, setSort] = useState<SortKey>('runs')
  const [onlyUsed, setOnlyUsed] = useState(true)
  const { data, loading, error } = useQuery<Snapshot>(`/api/observability?window_days=${days}`, [days])

  if (loading) return <Spinner label="Computing fleet metrics" />
  if (error) return <ErrorNote message={error} />
  if (!data) return <Empty title="No metrics available" />

  const { totals, portfolio, usage, finops, adoption } = data
  // Nothing has been billed until a model is connected; until then every
  // money figure switches to the modelled list price and says so.
  const billed = totals.spend_usd > 0
  const rows = data.agents
    .filter((row) => (onlyUsed ? row.runs > 0 : true))
    .slice()
    .sort((a, b) => (b[sort] as number) - (a[sort] as number))

  if (totals.runs === 0) {
    return (
      <div className="space-y-6">
        <Header days={days} setDays={setDays} generated={data.generated_at} />
        <Empty
          title="No runs yet, so there is nothing to measure"
          hint="Every figure on this tab is counted from runs that actually happened. Run an agent from the fleet and this fills in."
        />
        <InfoNote>
          Start with{' '}
          <Link to="/agents/01" className="underline">
            01 Source Profiling Agent
          </Link>
          , which has no hard dependencies and runs from a clean install.
        </InfoNote>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Header days={days} setDays={setDays} generated={data.generated_at} />

      {/* ---------------------------------------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Fleet coverage"
          value={`${portfolio.exercised}/${portfolio.fleet_size}`}
          hint={`${pct(portfolio.coverage)} of agents used · ${portfolio.core_exercised}/${portfolio.core_agents} core`}
        />
        <Stat
          label="Runs"
          value={formatNumber(totals.runs)}
          hint={`${formatNumber(totals.runs_in_window)} in the last ${days} days`}
        />
        <Stat
          label={totals.spend_usd > 0 ? 'Model spend' : 'Modelled cost'}
          value={formatCost(totals.spend_usd > 0 ? totals.spend_usd : finops.modelled_spend_usd)}
          hint={
            totals.spend_usd > 0
              ? `${formatCost(finops.projection.monthly_usd)}/month at the current rate`
              : 'Nothing billed — list price for this activity'
          }
        />
        <Stat
          label="Operators"
          value={adoption.total_users}
          hint={`${adoption.active_in_window} active in window · ${adoption.returning_users} returning`}
        />
      </div>

      {totals.simulated_runs > 0 ? (
        <InfoNote tone="warn">
          <strong>
            {totals.simulated_runs} of {totals.simulated_runs + totals.live_runs} executed runs ran
            offline
          </strong>{' '}
          ({pct(totals.simulated_share)}). Simulation runs consume no tokens and cost nothing, so
          spend figures below reflect live runs only. Configure a model to make FinOps meaningful.
          {totals.never_executed_runs > 0 ? (
            <>
              {' '}
              A further {totals.never_executed_runs} run
              {totals.never_executed_runs === 1 ? ' was' : 's were'} blocked by a guardrail before
              reaching a model at all.
            </>
          ) : null}
        </InfoNote>
      ) : null}

      {/* ---------------------------------------------------------------- */}
      <Section
        title="Agent portfolio"
        description="Coverage, not volume. An estate running one agent hundreds of times has a portfolio problem that a run count hides."
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <div className="label mb-3">Coverage by domain</div>
            <div className="space-y-2.5">
              {portfolio.by_domain.map((entry) => (
                <div key={entry.key}>
                  <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                    <span className="flex items-center gap-2">
                      <span className={`h-1.5 w-1.5 rounded-full ${domainStyle(entry.key).dot}`} />
                      <span className="text-slate-300">{domainStyle(entry.key).label}</span>
                    </span>
                    <span className="tabular-nums text-slate-400">
                      {entry.exercised}/{entry.agents} agents
                      <span className="ml-2 text-slate-500">{entry.runs} runs</span>
                    </span>
                  </div>
                  <Meter
                    ratio={entry.coverage}
                    tone={entry.coverage === 0 ? 'bad' : entry.coverage < 0.5 ? 'warn' : 'good'}
                  />
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="label mb-3">Coverage by autonomy tier</div>
            <div className="space-y-2.5">
              {portfolio.by_tier.map((entry) => (
                <div key={entry.key}>
                  <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                    <TierBadge tier={entry.key} />
                    <span className="tabular-nums text-slate-400">
                      {entry.exercised}/{entry.agents} agents
                      <span className="ml-2 text-slate-500">{entry.runs} runs</span>
                    </span>
                  </div>
                  <Meter
                    ratio={entry.coverage}
                    tone={entry.coverage === 0 ? 'bad' : entry.coverage < 0.5 ? 'warn' : 'good'}
                  />
                </div>
              ))}
            </div>

            <div className="mt-5 rounded-lg border border-ink-800 bg-ink-900/40 px-4 py-3 text-sm">
              <div className="flex items-baseline justify-between">
                <span className="text-slate-400">Concentration</span>
                <span className="tabular-nums font-medium text-white">
                  {pct(portfolio.top_agent_share)}
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">
                Share of all runs on the single busiest agent
                {portfolio.top_agent_id ? ` (${portfolio.top_agent_id})` : ''}. High concentration
                with broad coverage is a fleet with a workhorse; high concentration with narrow
                coverage is a pilot that never widened.
              </p>
            </div>
          </div>
        </div>

        {portfolio.never_run.length > 0 ? (
          <div className="mt-6 border-t border-ink-800 pt-5">
            <div className="label mb-2">
              Never run — {portfolio.never_run.length} agent
              {portfolio.never_run.length === 1 ? '' : 's'}
            </div>
            <p className="mb-3 text-sm text-slate-400">
              Capability the estate owns and has not touched. This is the portfolio gap worth
              reviewing before buying anything new.
            </p>
            <div className="flex flex-wrap gap-1.5">
              {portfolio.never_run.map((agent) => (
                <Link
                  key={agent.id}
                  to={`/agents/${agent.id}`}
                  className="chip border-ink-700 bg-ink-850 text-slate-400 transition hover:border-accent/40 hover:text-accent"
                  title={`${agent.name} · ${agent.domain} · ${agent.tier}`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${domainStyle(agent.domain).dot}`} />
                  {agent.id}
                  {agent.core ? <span className="text-amber-400">★</span> : null}
                </Link>
              ))}
            </div>
          </div>
        ) : null}
      </Section>

      {/* ---------------------------------------------------------------- */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Section title="Run volume" description={`Daily, last ${days} days`}>
          <BarSeries points={usage.daily} format={(v) => `${v} runs`} />
          <div className="mt-3 flex justify-between text-xs text-slate-500">
            <span>{usage.daily[0]?.date}</span>
            <span>{usage.daily[usage.daily.length - 1]?.date}</span>
          </div>
        </Section>

        <Section
          title={billed ? 'Spend' : 'Modelled cost'}
          description={`Daily, last ${days} days${billed ? '' : ' — list price, not billed'}`}
        >
          <BarSeries
            points={billed ? finops.daily : finops.daily_modelled}
            format={formatCost}
            tone="bg-emerald-400"
          />
          <div className="mt-3 flex justify-between text-xs text-slate-500">
            <span>
              {formatCost(billed ? finops.spend_in_window_usd : finops.modelled_spend_usd)} in window
            </span>
            <span>
              {billed && finops.projection.monthly_usd > 0
                ? `≈${formatCost(finops.projection.monthly_usd)}/mo`
                : '—'}
            </span>
          </div>
        </Section>

        <Section title="Active operators" description={`Distinct per day, last ${days} days`}>
          <BarSeries points={adoption.daily_active} format={(v) => `${v} operators`} tone="bg-sky-400" />
          <div className="mt-3 flex justify-between text-xs text-slate-500">
            <span>{adoption.total_users} total</span>
            <span>{adoption.new_in_window} new in window</span>
          </div>
        </Section>
      </div>

      {/* ---------------------------------------------------------------- */}
      <Section
        title="Per-agent usage"
        description="Every agent in the fleet, with what it has cost and what it has produced."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setOnlyUsed(!onlyUsed)}
              className="chip border-ink-700 bg-ink-850 text-slate-400 hover:text-slate-200"
            >
              {onlyUsed ? 'Showing used only' : 'Showing all 35'}
            </button>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortKey)}
              className="input h-8 w-auto py-0 text-xs"
            >
              <option value="runs">Sort: runs</option>
              <option value="cost_usd">Sort: spend</option>
              <option value="artifacts">Sort: artifacts</option>
              <option value="distinct_users">Sort: operators</option>
              <option value="block_rate">Sort: block rate</option>
            </select>
          </div>
        }
      >
        <div className="-mx-1 overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b border-ink-800 text-left text-xs uppercase tracking-wider text-slate-500">
                <th className="px-2 py-2 font-medium">Agent</th>
                <th className="px-2 py-2 text-right font-medium">Runs</th>
                <th className="px-2 py-2 font-medium">Outcome mix</th>
                <th className="px-2 py-2 text-right font-medium">Artifacts</th>
                <th className="px-2 py-2 text-right font-medium">Spend</th>
                <th className="px-2 py-2 text-right font-medium">p50 / p95</th>
                <th className="px-2 py-2 text-right font-medium">Operators</th>
                <th className="px-2 py-2 text-right font-medium">Last run</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.agent_id} className="border-b border-ink-850 last:border-0">
                  <td className="px-2 py-2.5">
                    <Link
                      to={`/agents/${row.agent_id}`}
                      className="flex items-center gap-2 text-slate-200 hover:text-accent"
                    >
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${domainStyle(row.domain).dot}`}
                      />
                      <span className="tabular-nums text-slate-500">{row.agent_id}</span>
                      <span className="truncate">{row.agent_name}</span>
                      {row.core ? <span className="text-xs text-amber-400">★</span> : null}
                    </Link>
                    {row.overrides > 0 ? (
                      <span className="mt-1 inline-block text-[11px] text-amber-400">
                        {row.overrides} dependency override{row.overrides === 1 ? '' : 's'}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-slate-200">{row.runs}</td>
                  <td className="px-2 py-2.5">
                    {row.runs > 0 ? (
                      <div className="flex items-center gap-2">
                        <div className="flex h-1.5 w-24 overflow-hidden rounded-full bg-ink-800">
                          <Segment count={row.succeeded} total={row.runs} className="bg-emerald-400" />
                          <Segment count={row.awaiting_approval} total={row.runs} className="bg-amber-400" />
                          <Segment count={row.partial} total={row.runs} className="bg-amber-500" />
                          <Segment count={row.blocked} total={row.runs} className="bg-rose-400" />
                          <Segment count={row.failed} total={row.runs} className="bg-rose-500" />
                        </div>
                        <span className="text-xs text-slate-500">
                          {row.blocked > 0 ? `${row.blocked} blocked` : `${pct(row.completion_rate)} complete`}
                        </span>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-600">never run</span>
                    )}
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">
                    {row.artifacts || '—'}
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">
                    {row.cost_usd > 0 ? formatCost(row.cost_usd) : '—'}
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-xs text-slate-400">
                    {row.p50_duration_ms == null
                      ? '—'
                      : `${formatDuration(row.p50_duration_ms)} / ${formatDuration(row.p95_duration_ms)}`}
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">
                    {row.distinct_users || '—'}
                  </td>
                  <td className="px-2 py-2.5 text-right text-xs text-slate-400">
                    {row.last_run_at ? formatDateTime(row.last_run_at) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length === 0 ? <Empty title="No agents match this filter" /> : null}
      </Section>

      {/* ---------------------------------------------------------------- */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Section
          title="Guardrail outcomes"
          description="Which gate stops work, and how often. A high block rate on hard dependencies means the fleet is being driven out of order."
        >
          <div className="space-y-3">
            {usage.gates.map((gate) => (
              <div key={gate.name}>
                <div className="mb-1 flex items-baseline justify-between text-sm">
                  <span className="text-slate-300">{GATE_LABELS[gate.name] ?? gate.name}</span>
                  <span className="tabular-nums text-slate-400">
                    {gate.blocked} blocked
                    <span className="ml-2 text-slate-500">of {gate.evaluated} evaluated</span>
                  </span>
                </div>
                <Meter
                  ratio={gate.block_rate}
                  tone={gate.block_rate === 0 ? 'good' : gate.block_rate > 0.3 ? 'bad' : 'warn'}
                />
              </div>
            ))}
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-ink-800 pt-4 text-sm">
            <div>
              <dt className="label">Dependency overrides</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-white">
                {usage.override_count}
              </dd>
              <p className="text-xs text-slate-500">Each carries a written reason in provenance</p>
            </div>
            <div>
              <dt className="label">Scope handoffs</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-white">
                {usage.handoffs_recorded}
              </dd>
              <p className="text-xs text-slate-500">Work refused because another agent owns it</p>
            </div>
          </dl>

          {usage.overrides.length > 0 ? (
            <div className="mt-4 space-y-2 border-t border-ink-800 pt-4">
              <div className="label">Recent overrides</div>
              {usage.overrides.slice(0, 4).map((item) => (
                <Link
                  key={item.run_id}
                  to={`/runs/${item.run_id}`}
                  className="block rounded-lg border border-amber-500/25 bg-amber-500/5 px-3 py-2 text-xs hover:border-amber-500/50"
                >
                  <span className="text-amber-300">
                    {item.agent_id} {item.agent_name}
                  </span>
                  <span className="ml-2 text-slate-500">{item.actor}</span>
                  <p className="mt-0.5 text-slate-400">{item.reason}</p>
                </Link>
              ))}
            </div>
          ) : null}
        </Section>

        <Section
          title="Approval queue"
          description="L0 and L1 agents produce proposals. Until a human accepts one, it does not satisfy a downstream dependency — so this queue is a throughput constraint, not an inbox."
        >
          <div className="grid grid-cols-3 gap-4 border-b border-ink-800 pb-4">
            <div>
              <div className="label">Pending</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-white">
                {usage.pending_count}
              </div>
            </div>
            <div>
              <div className="label">Granted</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-white">
                {usage.approvals_granted}
              </div>
            </div>
            <div>
              <div className="label">Median wait</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-white">
                {formatAge(usage.median_approval_lag_hours)}
              </div>
            </div>
          </div>

          {usage.pending_approvals.length > 0 ? (
            <ul className="mt-4 space-y-2">
              {usage.pending_approvals.slice(0, 6).map((item) => (
                <li key={item.run_id}>
                  <Link
                    to={`/runs/${item.run_id}`}
                    className="flex items-center justify-between gap-3 rounded-lg border border-ink-800 px-3 py-2 text-sm transition hover:border-accent/40"
                  >
                    <span className="min-w-0 truncate">
                      <span className="tabular-nums text-slate-500">{item.agent_id}</span>{' '}
                      <span className="text-slate-200">{item.agent_name}</span>
                      <span className="ml-2 text-xs text-slate-500">{item.actor}</span>
                    </span>
                    <span className="shrink-0 text-xs tabular-nums text-amber-300">
                      waiting {formatAge(item.age_hours)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-slate-500">Nothing is waiting on a human.</p>
          )}
        </Section>
      </div>

      {/* ---------------------------------------------------------------- */}
      <Section
        title="FinOps"
        description="Where the money went, and what it bought."
        actions={
          finops.spend_usd === 0 ? (
            <span className="chip border-ink-700 bg-ink-850 text-slate-400">
              No billable spend yet
            </span>
          ) : undefined
        }
      >
        {finops.spend_usd === 0 ? (
          <div className="space-y-4">
            <InfoNote>
              Nothing has been billed: every run so far executed offline, which consumes no tokens.
              Rather than show zeros, the figure below is what this same activity{' '}
              <strong>would have cost</strong> at list price on the models each run selected.
            </InfoNote>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Stat
                label="Modelled cost"
                value={formatCost(finops.modelled_spend_usd)}
                hint={`${totals.runs} runs at list price — modelled, not billed`}
              />
              <Stat
                label="Per run"
                value={formatCost(totals.runs ? finops.modelled_spend_usd / totals.runs : 0)}
                hint="Average across every run in the journal"
              />
              <Stat
                label="Per artifact"
                value={formatCost(totals.artifacts ? finops.modelled_spend_usd / totals.artifacts : 0)}
                hint={`${totals.artifacts} artifacts produced`}
              />
              <Stat
                label="Modelled monthly"
                value={formatCost((finops.modelled_spend_usd / Math.max(1, days)) * 30)}
                hint="At this activity level, on these models"
              />
            </div>

            <div>
              <div className="label mb-3">Modelled cost by model</div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-ink-800 text-left text-xs uppercase tracking-wider text-slate-500">
                    <th className="py-2 font-medium">Model</th>
                    <th className="py-2 text-right font-medium">Runs</th>
                    <th className="py-2 text-right font-medium">$/Mtok in</th>
                    <th className="py-2 text-right font-medium">$/Mtok out</th>
                    <th className="py-2 text-right font-medium">Modelled</th>
                  </tr>
                </thead>
                <tbody>
                  {finops.by_model.map((model) => (
                    <tr key={model.model_id} className="border-b border-ink-850 last:border-0">
                      <td className="py-2 text-slate-200">
                        {model.display_name}
                        <span className="ml-2 text-xs text-slate-500">{model.model_tier}</span>
                      </td>
                      <td className="py-2 text-right tabular-nums text-slate-300">{model.runs}</td>
                      <td className="py-2 text-right tabular-nums text-slate-400">
                        {model.input_usd_per_mtok == null ? '—' : `$${model.input_usd_per_mtok}`}
                      </td>
                      <td className="py-2 text-right tabular-nums text-slate-400">
                        {model.output_usd_per_mtok == null ? '—' : `$${model.output_usd_per_mtok}`}
                      </td>
                      <td className="py-2 text-right tabular-nums text-slate-200">
                        {formatCost(model.modelled_cost_usd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-xs leading-relaxed text-slate-500">
                Model choice is per task, so this table is also the lever: agent 01's numbers are
                computed deterministically rather than generated, which is why it defaults to a fast
                model. Moving open-ended work to a frontier model and mechanical work to a fast one
                is where the spend difference lives.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Stat label="Total spend" value={formatCost(finops.spend_usd)} />
              <Stat
                label={`Last ${days} days`}
                value={formatCost(finops.spend_in_window_usd)}
                hint={finops.projection.basis}
              />
              <Stat
                label="Spend on failed runs"
                value={formatCost(finops.wasted_usd)}
                hint={`${pct(finops.wasted_share)} of total — blocked runs cost nothing and are excluded`}
              />
              <Stat
                label="Runs that hit the cap"
                value={finops.capped_runs}
                hint={`${finops.near_cap.length} more within 80% of theirs`}
              />
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <div>
                <div className="label mb-3">By model</div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-ink-800 text-left text-xs uppercase tracking-wider text-slate-500">
                      <th className="py-2 font-medium">Model</th>
                      <th className="py-2 text-right font-medium">Runs</th>
                      <th className="py-2 text-right font-medium">Tokens</th>
                      <th className="py-2 text-right font-medium">Spend</th>
                      <th className="py-2 text-right font-medium">$/artifact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {finops.by_model.map((model) => (
                      <tr key={model.model_id} className="border-b border-ink-850 last:border-0">
                        <td className="py-2 text-slate-200">
                          {model.display_name}
                          <span className="ml-2 text-xs text-slate-500">{model.model_tier}</span>
                        </td>
                        <td className="py-2 text-right tabular-nums text-slate-300">{model.runs}</td>
                        <td className="py-2 text-right tabular-nums text-slate-400">
                          {formatTokens(model.total_tokens)}
                        </td>
                        <td className="py-2 text-right tabular-nums text-slate-200">
                          {formatCost(model.cost_usd)}
                        </td>
                        <td className="py-2 text-right tabular-nums text-slate-400">
                          {model.artifacts ? formatCost(model.cost_per_artifact_usd) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div>
                <div className="label mb-3">By domain</div>
                <div className="space-y-2.5">
                  {finops.by_domain.map((entry) => (
                    <div key={entry.key}>
                      <div className="mb-1 flex items-baseline justify-between text-sm">
                        <span className="flex items-center gap-2">
                          <span className={`h-1.5 w-1.5 rounded-full ${domainStyle(entry.key).dot}`} />
                          <span className="text-slate-300">{domainStyle(entry.key).label}</span>
                        </span>
                        <span className="tabular-nums text-slate-300">
                          {formatCost(entry.cost_usd)}
                          <span className="ml-2 text-xs text-slate-500">{entry.runs} runs</span>
                        </span>
                      </div>
                      <Meter
                        ratio={finops.spend_usd ? entry.cost_usd / finops.spend_usd : 0}
                        tone="good"
                      />
                    </div>
                  ))}
                </div>

                {finops.near_cap.length > 0 ? (
                  <div className="mt-5 border-t border-ink-800 pt-4">
                    <div className="label mb-2">Approaching their cost cap</div>
                    <ul className="space-y-1.5">
                      {finops.near_cap.slice(0, 5).map((item) => (
                        <li key={item.run_id} className="flex justify-between text-xs">
                          <Link to={`/runs/${item.run_id}`} className="text-slate-300 hover:text-accent">
                            {item.agent_id} {item.agent_name}
                          </Link>
                          <span className="tabular-nums text-amber-300">
                            {pct(item.utilisation)} of {formatCost(item.cap_usd)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </div>

            <div className="mt-6 border-t border-ink-800 pt-5">
              <div className="label mb-3">Costliest agents</div>
              <div className="grid gap-2 sm:grid-cols-2">
                {finops.top_agents.map((agent) => (
                  <Link
                    key={agent.agent_id}
                    to={`/agents/${agent.agent_id}`}
                    className="flex items-center justify-between gap-3 rounded-lg border border-ink-800 px-3 py-2 text-sm transition hover:border-accent/40"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <DomainBadge domain={agent.domain} />
                      <span className="truncate text-slate-200">{agent.agent_name}</span>
                    </span>
                    <span className="shrink-0 tabular-nums text-slate-300">
                      {formatCost(agent.cost_usd)}
                      <span className="ml-2 text-xs text-slate-500">
                        {formatCost(agent.cost_per_run_usd)}/run
                      </span>
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          </>
        )}
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        title="Adoption"
        description="Who uses the fleet, how much of it they reach, and whether they came back."
      >
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat label="Operators" value={adoption.total_users} hint={`${adoption.active_in_window} active in window`} />
          <Stat
            label="Returning"
            value={pct(adoption.returning_rate)}
            hint={`${adoption.returning_users} ran more than once`}
          />
          <Stat label="New in window" value={adoption.new_in_window} hint={`First run in the last ${days} days`} />
          <Stat
            label="Median fleet breadth"
            value={pct(adoption.median_fleet_breadth)}
            hint="Share of the 35 agents a typical operator has used"
          />
        </div>

        <div className="mt-6 -mx-1 overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-ink-800 text-left text-xs uppercase tracking-wider text-slate-500">
                <th className="px-2 py-2 font-medium">Operator</th>
                <th className="px-2 py-2 text-right font-medium">Runs</th>
                <th className="px-2 py-2 font-medium">Fleet breadth</th>
                <th className="px-2 py-2 text-right font-medium">Artifacts</th>
                <th className="px-2 py-2 text-right font-medium">Spend</th>
                <th className="px-2 py-2 text-right font-medium">Approvals</th>
                <th className="px-2 py-2 text-right font-medium">First seen</th>
                <th className="px-2 py-2 text-right font-medium">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {adoption.users.map((user) => (
                <tr key={user.actor} className="border-b border-ink-850 last:border-0">
                  <td className="px-2 py-2.5">
                    <span className="text-slate-200">{user.actor}</span>
                    {user.new_in_window ? (
                      <span className="ml-2 chip border-sky-500/30 bg-sky-500/10 text-[10px] text-sky-300">
                        new
                      </span>
                    ) : null}
                    {!user.active_in_window ? (
                      <span className="ml-2 text-[11px] text-slate-600">inactive</span>
                    ) : null}
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-slate-200">{user.runs}</td>
                  <td className="px-2 py-2.5">
                    <div className="flex items-center gap-2">
                      <Meter ratio={user.fleet_breadth} className="w-20" />
                      <span className="text-xs tabular-nums text-slate-400">
                        {user.agents_used}/{totals.fleet_size}
                      </span>
                    </div>
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">
                    {user.artifacts || '—'}
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">
                    {user.cost_usd > 0 ? formatCost(user.cost_usd) : '—'}
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">
                    {user.approvals_given || '—'}
                  </td>
                  <td className="px-2 py-2.5 text-right text-xs text-slate-400">
                    {formatDateTime(user.first_run_at)}
                  </td>
                  <td className="px-2 py-2.5 text-right text-xs text-slate-400">
                    {formatDateTime(user.last_run_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-4 border-t border-ink-800 pt-4 text-xs leading-relaxed text-slate-500">
          {data.identity_basis}
        </p>
      </Section>
    </div>
  )
}

function Header({
  days,
  setDays,
  generated,
}: {
  days: number
  setDays: (value: number) => void
  generated: string
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-white">Observability &amp; FinOps</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-400">
          Portfolio coverage, per-agent usage, model spend and operator adoption — all computed from
          the run journal. Everything is counted rather than inferred, except the two figures
          labelled as modelled or projected.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex rounded-lg border border-ink-700 p-0.5">
          {WINDOWS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setDays(option)}
              className={`rounded-md px-2.5 py-1 text-xs transition ${
                days === option ? 'bg-accent/15 font-medium text-accent' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {option}d
            </button>
          ))}
        </div>
        <span className="hidden text-xs text-slate-600 sm:inline">
          as of {formatDateTime(generated)}
        </span>
      </div>
    </header>
  )
}

function Segment({ count, total, className }: { count: number; total: number; className: string }) {
  if (count === 0) return null
  return <div className={className} style={{ width: `${(count / total) * 100}%` }} />
}
