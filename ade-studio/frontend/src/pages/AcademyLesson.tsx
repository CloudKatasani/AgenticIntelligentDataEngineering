import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { DomainBadge, Empty, Section, Spinner, TierBadge } from '../components/ui'
import { useQuery } from '../lib/hooks'

interface Lesson {
  agent: {
    id: string
    name: string
    domain: string
    tier: string
    tier_name: string
    tier_definition: string
    core_original_scope: boolean
    purpose: string
  }
  in_one_sentence: string
  why_it_exists: string
  owns: string[]
  does_not_own: { exclusion: string; owner_id: string; owner_name: string }[]
  seams: { direction: string; counterpart_id: string; counterpart_name: string; detail: string }[]
  reads: string[]
  produces: string[]
  artifacts: { key: string; filename: string; title: string; description: string; format: string }[]
  tools: string[]
  depends_on: {
    hard: { agent_id: string; agent_name: string }[]
    soft: { agent_id: string; agent_name: string }[]
    context_layer: string[]
  }
  feeds: { id: string; name: string; domain: string }[]
  triggers: string[]
  workflow: string[]
  acceptance_criteria: string[]
  evaluation: string[]
  kpis: string[]
  escalation: string
  guardrails: string[]
  checkpoint: { question: string; options: string[]; answer: string; explanation: string }[]
  skill_markdown: string
}

export default function AcademyLesson() {
  const { agentId } = useParams<{ agentId: string }>()
  const { data, loading, error } = useQuery<Lesson>(
    agentId ? `/api/academy/agents/${agentId}` : null,
  )
  const [showSkill, setShowSkill] = useState(false)

  if (loading) return <Spinner label="Loading lesson" />
  if (error || !data) return <Empty title="Lesson not found" hint={error ?? undefined} />

  const { agent } = data

  return (
    <div className="space-y-6">
      <nav className="text-xs text-slate-500">
        <Link to="/academy" className="hover:text-accent">
          Academy
        </Link>
        <span className="mx-2">/</span>
        <span className="text-slate-400">
          {agent.id} · {agent.name}
        </span>
      </nav>

      <header className="card card-pad">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-slate-500">Agent {agent.id}</span>
              <DomainBadge domain={agent.domain} />
              <TierBadge tier={agent.tier} name={agent.tier_name} />
              {agent.core_original_scope ? (
                <span className="chip border-accent/40 bg-accent/10 text-accent">★ core</span>
              ) : null}
            </div>
            <h1 className="mt-2 text-2xl font-semibold text-white">{agent.name}</h1>
            <p className="mt-2 max-w-3xl text-base leading-relaxed text-slate-300">
              {data.in_one_sentence}
            </p>
          </div>
          <Link to={`/agents/${agent.id}`} className="btn-primary shrink-0">
            Run this agent →
          </Link>
        </div>
      </header>

      <Section title="Why this agent exists">
        <p className="text-sm leading-relaxed text-slate-300">{data.why_it_exists}</p>
        <p className="mt-3 text-sm leading-relaxed text-slate-400">{agent.purpose}</p>
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="What it owns">
          <ul className="space-y-2">
            {data.owns.map((item) => (
              <li key={item} className="flex gap-2 text-sm leading-relaxed text-slate-300">
                <span className="mt-1 text-emerald-400">✓</span>
                {item}
              </li>
            ))}
          </ul>
        </Section>

        <Section
          title="What it must never do"
          description="Each exclusion names the agent that owns it. Doing an adjacent agent's job is a scope violation even when the output is correct."
        >
          <ul className="space-y-2">
            {data.does_not_own.map((item) => (
              <li key={item.exclusion} className="text-sm leading-relaxed text-slate-300">
                <span className="mr-2 text-rose-400">✕</span>
                {item.exclusion}
                {item.owner_id ? (
                  <Link
                    to={`/academy/${item.owner_id}`}
                    className="ml-1 whitespace-nowrap text-accent hover:underline"
                  >
                    → {item.owner_name}
                  </Link>
                ) : (
                  <span className="ml-1 text-slate-500">→ {item.owner_name}</span>
                )}
              </li>
            ))}
          </ul>
        </Section>
      </div>

      <Section
        title="Autonomy"
        description="What this agent is permitted to do without a human in the loop."
      >
        <div className="rounded-lg border border-ink-700 bg-ink-850/40 p-4">
          <TierBadge tier={agent.tier} name={agent.tier_name} />
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{agent.tier_definition}</p>
        </div>
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Depends on">
          {data.depends_on.hard.length === 0 && data.depends_on.soft.length === 0 ? (
            <p className="text-sm text-slate-400">
              No agent dependencies — it can start from platform and context-layer inputs alone.
            </p>
          ) : (
            <div className="space-y-4">
              {data.depends_on.hard.length > 0 ? (
                <div>
                  <p className="label">Hard — blocks execution</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {data.depends_on.hard.map((dep) => (
                      <Link
                        key={dep.agent_id}
                        to={`/academy/${dep.agent_id}`}
                        className="chip border-rose-500/30 bg-rose-500/10 text-rose-300 hover:border-rose-500/60"
                      >
                        {dep.agent_id} {dep.agent_name}
                      </Link>
                    ))}
                  </div>
                </div>
              ) : null}
              {data.depends_on.soft.length > 0 ? (
                <div>
                  <p className="label">Soft — improves quality</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {data.depends_on.soft.map((dep) => (
                      <Link
                        key={dep.agent_id}
                        to={`/academy/${dep.agent_id}`}
                        className="chip border-ink-600 bg-ink-800 text-slate-400 hover:border-accent/40"
                      >
                        {dep.agent_id} {dep.agent_name}
                      </Link>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          )}
          {data.depends_on.context_layer.length > 0 ? (
            <div className="mt-4 border-t border-ink-800 pt-3">
              <p className="label">Context-layer prerequisites</p>
              <ul className="mt-2 space-y-1">
                {data.depends_on.context_layer.map((item) => (
                  <li key={item} className="text-xs text-slate-400">
                    · {item}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </Section>

        <Section title="Feeds">
          {data.feeds.length === 0 ? (
            <p className="text-sm text-slate-400">No agent consumes this agent's output directly.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {data.feeds.map((dep) => (
                <Link
                  key={dep.id}
                  to={`/academy/${dep.id}`}
                  className="chip border-ink-600 bg-ink-800 text-slate-400 hover:border-accent/40"
                >
                  {dep.id} {dep.name}
                </Link>
              ))}
            </div>
          )}
        </Section>
      </div>

      {data.workflow.length > 0 ? (
        <Section title="How it works" description="The workflow declared in this agent's skill.">
          <ol className="space-y-2">
            {data.workflow.map((step, index) => (
              <li key={index} className="flex gap-3 text-sm leading-relaxed text-slate-300">
                <span className="mt-0.5 font-mono text-xs text-slate-600">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span>{step.replace(/^\d+\.\s*/, '')}</span>
              </li>
            ))}
          </ol>
        </Section>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Reads">
          <ul className="space-y-1.5">
            {data.reads.map((item) => (
              <li key={item} className="text-sm text-slate-300">
                · {item}
              </li>
            ))}
          </ul>
        </Section>
        <Section title="Produces">
          <ul className="space-y-1.5">
            {data.produces.map((item) => (
              <li key={item} className="text-sm text-slate-300">
                · {item}
              </li>
            ))}
          </ul>
          <div className="mt-4 border-t border-ink-800 pt-3">
            <p className="label">Files a run downloads</p>
            <ul className="mt-2 space-y-1">
              {data.artifacts.map((artifact) => (
                <li key={artifact.key} className="text-xs text-slate-400">
                  <span className="font-mono text-accent">{artifact.filename}</span> — {artifact.title}
                </li>
              ))}
            </ul>
          </div>
        </Section>
      </div>

      {data.seams.length > 0 ? (
        <Section
          title="Seams with neighbouring agents"
          description="Boundaries are reciprocal: both sides of every seam name the other."
        >
          <div className="grid gap-2 md:grid-cols-2">
            {data.seams.map((seam, index) => (
              <div
                key={index}
                className="rounded-lg border border-ink-700 bg-ink-850/40 px-4 py-3 text-sm"
              >
                <span
                  className={`chip ${
                    seam.direction === 'hands_off'
                      ? 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                      : seam.direction === 'human_owned'
                        ? 'border-slate-500/30 bg-slate-500/10 text-slate-300'
                        : 'border-sky-500/30 bg-sky-500/10 text-sky-300'
                  }`}
                >
                  {seam.direction === 'hands_off'
                    ? 'hands off to'
                    : seam.direction === 'human_owned'
                      ? 'stays with a human'
                      : 'receives from'}
                </span>
                {seam.counterpart_id ? (
                  <Link
                    to={`/academy/${seam.counterpart_id}`}
                    className="ml-2 font-medium text-slate-200 hover:text-accent"
                  >
                    {seam.counterpart_id} {seam.counterpart_name}
                  </Link>
                ) : (
                  <span className="ml-2 font-medium text-slate-400">{seam.counterpart_name}</span>
                )}
                <p className="mt-1.5 text-xs leading-relaxed text-slate-400">{seam.detail}</p>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="How it is measured" description="Evaluation is owned by agent 34.">
          <ul className="space-y-2">
            {data.evaluation.map((item) => (
              <li key={item} className="text-sm leading-relaxed text-slate-300">
                · {item}
              </li>
            ))}
          </ul>
          {data.kpis.length > 0 ? (
            <div className="mt-4 border-t border-ink-800 pt-3">
              <p className="label">Operational KPIs</p>
              <ul className="mt-2 space-y-1">
                {data.kpis.map((kpi) => (
                  <li key={kpi} className="text-xs text-slate-400">
                    · {kpi}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </Section>

        <Section title="Before it answers" description="Self-checks the agent must pass.">
          <ul className="space-y-2">
            {data.acceptance_criteria.map((item) => (
              <li key={item} className="flex gap-2 text-sm leading-relaxed text-slate-300">
                <span className="mt-0.5 text-emerald-400">✓</span>
                {item}
              </li>
            ))}
          </ul>
          {data.escalation ? (
            <div className="mt-4 border-t border-ink-800 pt-3">
              <p className="label">When it stops and escalates</p>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-400">{data.escalation}</p>
            </div>
          ) : null}
        </Section>
      </div>

      {data.guardrails.length > 0 ? (
        <Section
          title="Universal guardrails"
          description="Applied to every agent in the fleet, this one included."
        >
          <ul className="space-y-2">
            {data.guardrails.map((rule) => (
              <li key={rule} className="flex gap-2 text-sm leading-relaxed text-slate-300">
                <span className="mt-0.5 text-accent">§</span>
                {rule}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <Checkpoint questions={data.checkpoint} />

      <Section
        title="Full skill definition"
        description="The exact text loaded into this agent's context at runtime."
        actions={
          <button type="button" className="btn-ghost" onClick={() => setShowSkill((v) => !v)}>
            {showSkill ? 'Hide' : 'Show'}
          </button>
        }
      >
        {showSkill ? (
          <pre className="scroll-thin max-h-[32rem] overflow-auto rounded-lg border border-ink-700 bg-ink-950 p-4 text-xs leading-relaxed text-slate-300">
            {data.skill_markdown}
          </pre>
        ) : (
          <p className="text-sm text-slate-500">
            The runtime loads this agent's SKILL.md verbatim — the boundaries and guardrail sections
            are never summarised or compressed.
          </p>
        )}
      </Section>
    </div>
  )
}

function Checkpoint({
  questions,
}: {
  questions: { question: string; options: string[]; answer: string; explanation: string }[]
}) {
  const [answers, setAnswers] = useState<Record<number, string>>({})

  if (questions.length === 0) return null

  return (
    <Section
      title="Checkpoint"
      description="Three questions on the boundary. Answers come from the agent's own spec."
    >
      <div className="space-y-5">
        {questions.map((question, index) => {
          const chosen = answers[index]
          return (
            <div key={index}>
              <p className="text-sm font-medium text-slate-200">
                {index + 1}. {question.question}
              </p>
              <div className="mt-2 space-y-1.5">
                {question.options.map((option) => {
                  const isChosen = chosen === option
                  const isCorrect = option === question.answer
                  const style = !chosen
                    ? 'border-ink-700 bg-ink-850/40 hover:border-ink-600'
                    : isCorrect
                      ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-200'
                      : isChosen
                        ? 'border-rose-500/50 bg-rose-500/10 text-rose-200'
                        : 'border-ink-800 bg-ink-850/20 text-slate-500'
                  return (
                    <button
                      key={option}
                      type="button"
                      disabled={Boolean(chosen)}
                      onClick={() => setAnswers((a) => ({ ...a, [index]: option }))}
                      className={`block w-full rounded-lg border px-4 py-2 text-left text-sm transition ${style}`}
                    >
                      {option}
                    </button>
                  )
                })}
              </div>
              {chosen ? (
                <p className="mt-2 rounded-lg border border-ink-700 bg-ink-850/60 px-4 py-2 text-xs leading-relaxed text-slate-400">
                  {question.explanation}
                </p>
              ) : null}
            </div>
          )
        })}
      </div>
    </Section>
  )
}
