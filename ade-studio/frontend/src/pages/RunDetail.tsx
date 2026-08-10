import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  DomainBadge,
  Empty,
  ErrorNote,
  InfoNote,
  Section,
  Spinner,
  StatusBadge,
} from '../components/ui'
import type { RunArtifact, RunDetail } from '../lib/api'
import { api } from '../lib/api'
import { formatBytes, formatCost, formatDateTime, formatDuration, percent } from '../lib/format'
import { useMutation, useQuery } from '../lib/hooks'
import { getOperator } from '../lib/operator'

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const { data: run, loading, error, reload } = useQuery<RunDetail>(
    runId ? `/api/runs/${runId}` : null,
  )
  const [viewing, setViewing] = useState<RunArtifact | null>(null)
  const [content, setContent] = useState<string>('')

  const decide = useMutation(async (approve: boolean) =>
    api.post<RunDetail>(`/api/runs/${runId}/decision`, { approve, actor: getOperator() }),
  )

  if (loading) return <Spinner label="Loading run" />
  if (error || !run) return <Empty title="Run not found" hint={error ?? undefined} />

  const openArtifact = async (artifact: RunArtifact) => {
    setViewing(artifact)
    setContent('')
    try {
      const payload = await api.get<{ content: string }>(artifact.view_url)
      setContent(payload.content)
    } catch (err) {
      setContent(String(err))
    }
  }

  return (
    <div className="space-y-6">
      <header className="card card-pad">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-slate-500">{run.agent_id}</span>
              <DomainBadge domain={run.agent_domain} />
              <StatusBadge status={run.status} />
              {run.provider === 'simulation' ? (
                <span className="chip border-amber-500/40 bg-amber-500/10 text-amber-300">
                  offline simulation
                </span>
              ) : null}
            </div>
            <h1 className="mt-2 text-2xl font-semibold text-white">{run.agent_name}</h1>
            <p className="mt-1 font-mono text-xs text-slate-500">{run.id}</p>
          </div>

          <div className="flex shrink-0 flex-wrap gap-2">
            <Link to={`/agents/${run.agent_id}`} className="btn-ghost">
              Run again
            </Link>
            {run.artifacts.length > 0 ? (
              <a className="btn-primary" href={run.bundle_url} download>
                ↓ Download all ({run.artifacts.length})
              </a>
            ) : null}
          </div>
        </div>

        <dl className="mt-5 grid gap-4 border-t border-ink-800 pt-4 text-sm sm:grid-cols-3 lg:grid-cols-6">
          <Meta label="Model" value={run.model_id} mono />
          <Meta label="Effort" value={run.effort} />
          <Meta label="Cost" value={formatCost(run.usage.cost_usd)} />
          <Meta label="Tokens" value={`${run.usage.input_tokens} in / ${run.usage.output_tokens} out`} />
          <Meta label="Duration" value={formatDuration(run.duration_ms)} />
          <Meta label="Started" value={formatDateTime(run.created_at)} />
        </dl>
      </header>

      {run.status === 'awaiting_approval' ? (
        <div className="card card-pad border-amber-500/40 bg-amber-500/5">
          <h2 className="text-sm font-semibold text-amber-200">Awaiting human acceptance</h2>
          <p className="mt-1 text-sm text-slate-300">
            This agent operates at an advisory tier, so its artifacts are proposals. Accepting
            promotes them to records; rejecting leaves them for the audit trail without adopting
            them.
          </p>
          {decide.error ? (
            <div className="mt-3">
              <ErrorNote message={decide.error} />
            </div>
          ) : null}
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              className="btn-primary"
              disabled={decide.pending}
              onClick={async () => {
                await decide.run(true)
                reload()
              }}
            >
              Accept proposal
            </button>
            <button
              type="button"
              className="btn-danger"
              disabled={decide.pending}
              onClick={async () => {
                await decide.run(false)
                reload()
              }}
            >
              Reject
            </button>
          </div>
        </div>
      ) : null}

      {run.error ? <ErrorNote message={run.error} /> : null}

      {run.summary ? (
        <Section title="Summary">
          <p className="text-sm leading-relaxed text-slate-300">{run.summary}</p>
        </Section>
      ) : null}

      {run.artifacts.length > 0 ? (
        <Section
          title="Artifacts"
          description="Every file this run produced, with its hash and provenance."
        >
          <div className="grid gap-3 md:grid-cols-2">
            {run.artifacts.map((artifact) => (
              <div key={artifact.id} className="rounded-lg border border-ink-700 bg-ink-850/40 p-4">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-mono text-xs text-accent">{artifact.filename}</span>
                  <span
                    className={`chip ${
                      artifact.kind === 'proposal'
                        ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
                        : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                    }`}
                  >
                    {artifact.kind}
                  </span>
                </div>
                <p className="mt-1.5 text-sm font-medium text-slate-200">{artifact.title}</p>
                <p className="mt-1 text-xs leading-relaxed text-slate-500">{artifact.description}</p>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span>{formatBytes(artifact.size_bytes)}</span>
                  <span>·</span>
                  <span className="font-mono">{artifact.sha256.slice(0, 12)}</span>
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    className="btn-ghost px-3 py-1.5 text-xs"
                    onClick={() => openArtifact(artifact)}
                  >
                    View
                  </button>
                  <a className="btn-ghost px-3 py-1.5 text-xs" href={artifact.download_url} download>
                    ↓ Download
                  </a>
                </div>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      {viewing ? (
        <Section
          title={viewing.filename}
          description={viewing.title}
          actions={
            <button type="button" className="btn-ghost" onClick={() => setViewing(null)}>
              Close
            </button>
          }
        >
          <pre className="scroll-thin max-h-[28rem] overflow-auto rounded-lg border border-ink-700 bg-ink-950 p-4 text-xs leading-relaxed text-slate-300">
            {content || 'Loading…'}
          </pre>
        </Section>
      ) : null}

      {run.findings.length > 0 ? (
        <Section title="Findings">
          <ul className="space-y-2">
            {run.findings.map((finding, index) => (
              <li key={index} className="flex gap-3 text-sm text-slate-300">
                <span className="mt-0.5 font-mono text-xs text-slate-600">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span className="leading-relaxed">{finding}</span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {run.handoffs.length > 0 ? (
        <Section
          title="Handoffs"
          description="Work this agent deliberately did not do, because another agent owns it."
        >
          <ul className="space-y-2">
            {run.handoffs.map((handoff, index) => (
              <li key={index} className="rounded-lg border border-ink-700 bg-ink-850/40 px-4 py-3">
                <Link
                  to={`/agents/${handoff.to_agent_id}`}
                  className="text-sm font-medium text-accent hover:underline"
                >
                  {handoff.to_agent_id} · {handoff.to_agent_name}
                </Link>
                <p className="mt-1 text-sm text-slate-400">{handoff.reason}</p>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {run.open_questions.length > 0 ? (
        <Section title="Open questions for a human">
          <ul className="space-y-2">
            {run.open_questions.map((question, index) => (
              <li key={index} className="text-sm text-slate-300">
                · {question}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {run.profiles.length > 0 ? (
        <Section
          title="Deterministic profile"
          description="Computed by the profiler, not by the model. These are the numbers the agent reasoned over."
        >
          <div className="space-y-6">
            {run.profiles.map((profile) => (
              <div key={profile.table}>
                <div className="mb-2 flex flex-wrap items-center gap-3">
                  <span className="font-mono text-sm text-slate-200">{profile.table}</span>
                  <span className="text-xs text-slate-500">
                    {profile.row_count.toLocaleString()} rows · sampled {profile.sampled_rows} (
                    {profile.sample_strategy})
                  </span>
                </div>
                <div className="overflow-x-auto rounded-lg border border-ink-700">
                  <table className="w-full min-w-[720px] text-xs">
                    <thead className="bg-ink-850 text-left uppercase tracking-wider text-slate-500">
                      <tr>
                        <th className="px-3 py-2">Column</th>
                        <th className="px-3 py-2">Type</th>
                        <th className="px-3 py-2 text-right">Null %</th>
                        <th className="px-3 py-2 text-right">Distinct</th>
                        <th className="px-3 py-2">Patterns</th>
                        <th className="px-3 py-2">Key</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-800">
                      {profile.columns.map((column) => (
                        <tr key={column.column}>
                          <td className="px-3 py-1.5 font-mono text-slate-300">{column.column}</td>
                          <td className="px-3 py-1.5 text-slate-500">{column.data_type}</td>
                          <td
                            className={`px-3 py-1.5 text-right tabular-nums ${
                              column.null_ratio > 0.02 ? 'text-amber-300' : 'text-slate-400'
                            }`}
                          >
                            {percent(column.null_ratio)}
                          </td>
                          <td className="px-3 py-1.5 text-right tabular-nums text-slate-400">
                            {column.distinct_count}
                          </td>
                          <td className="px-3 py-1.5 text-slate-500">
                            {column.sample_patterns.join(', ') || '—'}
                          </td>
                          <td className="px-3 py-1.5">
                            {column.is_candidate_key ? (
                              <span className="chip border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
                                candidate
                              </span>
                            ) : (
                              <span className="text-slate-600">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      <Section title="Guardrails" description="Evaluated before execution and recorded here.">
        <div className="space-y-2">
          {run.gates.map((gate) => (
            <div
              key={gate.name}
              className="flex items-start gap-3 rounded-lg border border-ink-700 bg-ink-850/40 px-4 py-2.5 text-sm"
            >
              <span className={gate.passed ? 'text-emerald-400' : 'text-rose-400'}>
                {gate.passed ? '✓' : '✕'}
              </span>
              <div>
                <span className="font-mono text-xs uppercase tracking-wider text-slate-500">
                  {gate.name.replace(/_/g, ' ')}
                </span>
                <p className="mt-0.5 text-slate-300">{gate.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Event log">
        <ol className="space-y-1.5">
          {run.events.map((event, index) => (
            <li key={index} className="flex gap-3 text-xs">
              <span className="w-32 shrink-0 font-mono text-slate-600">
                {formatDateTime(event.at)}
              </span>
              <span
                className={
                  event.level === 'error'
                    ? 'text-rose-300'
                    : event.level === 'warning'
                      ? 'text-amber-300'
                      : 'text-slate-400'
                }
              >
                {event.message}
                {Object.keys(event.data).length > 0 ? (
                  <span className="ml-2 text-slate-600">{JSON.stringify(event.data)}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ol>
      </Section>

      {run.approved_by ? (
        <InfoNote>
          Decision recorded by <strong>{run.approved_by}</strong> at{' '}
          {formatDateTime(run.approved_at ?? '')}.
        </InfoNote>
      ) : null}
    </div>
  )
}

function Meta({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className={`mt-1 text-slate-200 ${mono ? 'font-mono text-xs' : 'text-sm'}`}>{value}</dd>
    </div>
  )
}
