import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Empty, ErrorNote, InfoNote, Section, Spinner, TierBadge } from '../components/ui'
import { KindBadge } from '../components/InputSlots'
import { useQuery } from '../lib/hooks'
import { domainStyle } from '../lib/format'

interface Exhibit {
  label: string
  kind: string
  origin: string
  format: string
  body: string
  stat: string
  note: string
}

interface ExampleArtifact {
  filename: string
  title: string
  format: string
  source: string
  body: string
  note: string
}

interface AgentCanvas {
  agent_id: string
  scenario: string
  chapter: string
  inputs: Exhibit[]
  upstream: string[]
  outputs: ExampleArtifact[]
  highlights: string[]
  handoffs: string[]
  illustration_note: string
  agent: {
    id: string
    name: string
    domain: string
    tier: string
    tier_name: string
    purpose: string
    requires_approval: boolean
    core: boolean
  }
}

interface FleetEntry {
  agent_id: string
  agent_name: string
  domain: string
  tier: string
  scenario: string
  input_kinds: string[]
  input_labels: string[]
  output_files: string[]
  upstream_count: number
  highlight: string
}

interface FleetCanvas {
  story: { title: string; premise: string; estate: string }
  chapters: { title: string; agents: FleetEntry[] }[]
  total: number
}

const KIND_LABELS: Record<string, string> = {
  database_objects: 'Database objects',
  code_artifacts: 'Code & ETL',
  telemetry_export: 'Telemetry',
  policy_document: 'Policy document',
  structured_request: 'Written request',
  upstream_artifacts: 'Upstream only',
}

/** Monospace body with a subtle language tag. Deliberately not a full
 *  syntax highlighter — a demo screen wants the shape of the file legible,
 *  and a highlighter that mis-colours a dialect is worse than none. */
function Body({ body, format }: { body: string; format: string }) {
  return (
    <div className="relative">
      <span className="absolute right-2 top-2 rounded bg-ink-900/80 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-slate-500">
        {format}
      </span>
      <pre className="max-h-[28rem] overflow-auto rounded-lg border border-ink-800 bg-ink-950 p-4 text-[12.5px] leading-relaxed text-slate-300">
        <code>{body}</code>
      </pre>
    </div>
  )
}

function Collapsible({
  title,
  subtitle,
  badge,
  defaultOpen = false,
  children,
}: {
  title: string
  subtitle?: string
  badge?: React.ReactNode
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-lg border border-ink-800">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-ink-850"
      >
        <span className="mt-0.5 w-3 shrink-0 text-xs text-slate-500">{open ? '▾' : '▸'}</span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm text-slate-200">{title}</span>
            {badge}
          </span>
          {subtitle ? <span className="mt-0.5 block text-xs text-slate-500">{subtitle}</span> : null}
        </span>
      </button>
      {open ? <div className="border-t border-ink-800 p-4">{children}</div> : null}
    </div>
  )
}

/**
 * One agent's worked example: exhibits in, agent in the middle, artifacts out.
 *
 * Built for a demo where the audience is a head of data engineering rather
 * than a buyer of slideware — which is why every artifact body is the real
 * shape of the file, and why the page says plainly that it is an illustration
 * with a live run one click away.
 */
export default function Canvas() {
  const { agentId } = useParams<{ agentId: string }>()
  return agentId ? <AgentView agentId={agentId} /> : <FleetView />
}

function FleetView() {
  const { data, loading, error } = useQuery<FleetCanvas>('/api/canvas')

  if (loading) return <Spinner label="Loading the fleet canvas" />
  if (error) return <ErrorNote message={error} />
  if (!data) return <Empty title="No canvas available" />

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white">Canvas</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-400">
          A worked example for every agent — what goes in, what comes out. All 35 are set in one
          estate, so read end to end they are a single migration.
        </p>
      </header>

      <Section title={data.story.title} description={data.story.premise}>
        <p className="text-sm text-slate-400">{data.story.estate}</p>
      </Section>

      {data.chapters.map((chapter) => (
        <Section key={chapter.title} title={chapter.title}>
          <div className="grid gap-3 lg:grid-cols-2">
            {chapter.agents.map((entry) => (
              <Link
                key={entry.agent_id}
                to={`/canvas/${entry.agent_id}`}
                className="group rounded-lg border border-ink-800 p-4 transition hover:border-accent/40"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${domainStyle(entry.domain).dot}`}
                  />
                  <span className="tabular-nums text-xs text-slate-500">{entry.agent_id}</span>
                  <span className="font-medium text-slate-200 group-hover:text-accent">
                    {entry.agent_name}
                  </span>
                  <TierBadge tier={entry.tier} />
                </div>

                <p className="mt-2 text-sm leading-relaxed text-slate-400">{entry.scenario}</p>

                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-slate-500">in</span>
                  {entry.input_kinds.map((kind) => (
                    <KindBadge key={kind} kind={kind} label={KIND_LABELS[kind] ?? kind} />
                  ))}
                  <span className="text-slate-600">→</span>
                  <span className="text-slate-500">out</span>
                  {entry.output_files.map((file) => (
                    <span key={file} className="font-mono text-[11px] text-emerald-300">
                      {file}
                    </span>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </Section>
      ))}
    </div>
  )
}

function AgentView({ agentId }: { agentId: string }) {
  const { data, loading, error } = useQuery<AgentCanvas>(`/api/canvas/${agentId}`, [agentId])

  if (loading) return <Spinner label="Loading the worked example" />
  if (error) return <ErrorNote message={error} />
  if (!data) return <Empty title="No worked example for this agent" />

  const { agent } = data

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Link to="/canvas" className="text-slate-500 hover:text-accent">
              Canvas
            </Link>
            <span className="text-slate-700">/</span>
            <span className="text-slate-500">{data.chapter}</span>
          </div>
          <h1 className="mt-1 text-2xl font-semibold text-white">
            <span className="tabular-nums text-slate-500">{agent.id}</span> {agent.name}
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">{data.scenario}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Link to={`/academy/${agent.id}`} className="btn-ghost">
            Learn this agent
          </Link>
          <Link to={`/agents/${agent.id}`} className="btn-primary">
            Run it for real →
          </Link>
        </div>
      </header>

      <InfoNote>{data.illustration_note}</InfoNote>

      {/* ------------------------------------------------------------ */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] lg:items-start">
        {/* INPUT */}
        <div className="min-w-0 space-y-3">
          <div className="label">Input — what this agent is given</div>

          {data.inputs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-ink-700 px-4 py-6 text-center">
              <p className="text-sm text-slate-300">Nothing from the operator</p>
              <p className="mt-1 text-xs text-slate-500">
                Everything this agent needs arrives from upstream runs.
              </p>
            </div>
          ) : (
            data.inputs.map((exhibit) => (
              <Collapsible
                key={exhibit.label}
                title={exhibit.label}
                subtitle={`${exhibit.origin}${exhibit.stat ? ` · ${exhibit.stat}` : ''}`}
                badge={<KindBadge kind={exhibit.kind} label={KIND_LABELS[exhibit.kind] ?? exhibit.kind} />}
                defaultOpen
              >
                {exhibit.note ? (
                  <p className="mb-3 text-xs leading-relaxed text-slate-400">{exhibit.note}</p>
                ) : null}
                <Body body={exhibit.body} format={exhibit.format} />
              </Collapsible>
            ))
          )}

          {data.upstream.length > 0 ? (
            <div className="rounded-lg border border-ink-800 bg-ink-900/40 p-4">
              <div className="label mb-2">From upstream agents</div>
              <ul className="space-y-1 text-xs text-slate-400">
                {data.upstream.map((item) => (
                  <li key={item}>· {item}</li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] leading-relaxed text-slate-600">
                Guaranteed by the dependency gate. The operator is never asked for these.
              </p>
            </div>
          ) : null}
        </div>

        {/* AGENT */}
        <div className="lg:sticky lg:top-6 lg:w-52">
          <div className="rounded-lg border border-accent/30 bg-accent/5 p-4 text-center">
            <div className="text-[11px] uppercase tracking-wider text-accent/70">Agent</div>
            <div className="mt-1 text-sm font-medium text-white">{agent.name}</div>
            <div className="mt-2 flex justify-center">
              <TierBadge tier={agent.tier} name={agent.tier_name} />
            </div>
            {agent.requires_approval ? (
              <p className="mt-3 text-[11px] leading-relaxed text-amber-300">
                Advisory tier — output is a proposal until a human accepts it.
              </p>
            ) : null}
          </div>
          <div className="mt-2 hidden text-center text-2xl text-ink-700 lg:block">→</div>
        </div>

        {/* OUTPUT */}
        <div className="min-w-0 space-y-3">
          <div className="label">Output — what this agent generates</div>
          {data.outputs.map((artifact) => (
            <Collapsible
              key={artifact.filename}
              title={artifact.filename}
              subtitle={artifact.title}
              badge={
                <span
                  className={`chip ${
                    artifact.source === 'deterministic'
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                      : 'border-violet-500/30 bg-violet-500/10 text-violet-300'
                  }`}
                >
                  {artifact.source}
                </span>
              }
              defaultOpen
            >
              {artifact.note ? (
                <p className="mb-3 text-xs leading-relaxed text-slate-400">{artifact.note}</p>
              ) : null}
              <Body body={artifact.body} format={artifact.format} />
            </Collapsible>
          ))}
        </div>
      </div>

      {/* ------------------------------------------------------------ */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Section
          title="What to point at"
          description="The moments in this output that answer a data leader's real question."
        >
          <ul className="space-y-2.5">
            {data.highlights.map((item) => (
              <li key={item} className="flex gap-2.5 text-sm leading-relaxed text-slate-300">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                {item}
              </li>
            ))}
          </ul>
        </Section>

        <Section
          title="What it refused to do"
          description="Work this agent deliberately did not take on, because another agent owns it."
        >
          {data.handoffs.length === 0 ? (
            <p className="text-sm text-slate-500">No handoffs recorded for this example.</p>
          ) : (
            <ul className="space-y-2">
              {data.handoffs.map((item) => (
                <li
                  key={item}
                  className="rounded-lg border border-ink-800 px-3 py-2 text-sm text-slate-400"
                >
                  {item}
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </div>
  )
}
