import { useState } from 'react'
import { Link } from 'react-router-dom'
import { DomainBadge, Empty, Spinner, StatusBadge } from '../components/ui'
import type { RunSummary } from '../lib/api'
import { formatCost, formatDateTime, formatDuration } from '../lib/format'
import { useQuery } from '../lib/hooks'

export default function Runs() {
  const [status, setStatus] = useState('all')
  const { data, loading, error } = useQuery<{ count: number; runs: RunSummary[] }>(
    '/api/runs?limit=200',
  )

  if (loading) return <Spinner label="Loading runs" />
  if (error || !data) return <Empty title="Could not load runs" hint={error ?? undefined} />

  const runs = status === 'all' ? data.runs : data.runs.filter((r) => r.status === status)

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">Runs &amp; artifacts</h1>
          <p className="mt-1 text-sm text-slate-400">
            {data.count} runs. Every run keeps its guardrail verdicts, provenance and downloadable
            output.
          </p>
        </div>
        <select
          className="input w-56"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="succeeded">Succeeded</option>
          <option value="awaiting_approval">Awaiting acceptance</option>
          <option value="blocked">Blocked</option>
          <option value="failed">Failed</option>
          <option value="rejected">Rejected</option>
        </select>
      </header>

      {runs.length === 0 ? (
        <Empty
          title="No runs to show"
          hint="Pick an agent from the fleet and run it against the demo warehouse."
        />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[880px] text-sm">
            <thead className="border-b border-ink-800 text-left text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-5 py-3">Agent</th>
                <th className="px-3 py-3">Objects</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Model</th>
                <th className="px-3 py-3 text-right">Artifacts</th>
                <th className="px-3 py-3 text-right">Cost</th>
                <th className="px-3 py-3 text-right">Duration</th>
                <th className="px-5 py-3 text-right">When</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-800">
              {runs.map((run) => (
                <tr key={run.id} className="transition hover:bg-ink-850/50">
                  <td className="px-5 py-3">
                    <Link to={`/runs/${run.id}`} className="block">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-slate-500">{run.agent_id}</span>
                        <span className="font-medium text-slate-200">{run.agent_name}</span>
                      </div>
                      <div className="mt-1">
                        <DomainBadge domain={run.agent_domain} />
                      </div>
                    </Link>
                  </td>
                  <td className="max-w-[220px] px-3 py-3">
                    <span className="block truncate font-mono text-xs text-slate-500">
                      {run.objects.join(', ') || '—'}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-3 py-3">
                    <span className="font-mono text-xs text-slate-400">{run.model_id}</span>
                    <span className="ml-1 text-[11px] text-slate-600">{run.effort}</span>
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums text-slate-400">
                    {run.artifact_count}
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums text-slate-400">
                    {formatCost(run.cost_usd)}
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums text-slate-400">
                    {formatDuration(run.duration_ms)}
                  </td>
                  <td className="px-5 py-3 text-right text-xs text-slate-500">
                    {formatDateTime(run.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
