import { useState } from 'react'
import { Link } from 'react-router-dom'
import { DomainBadge, Empty, Section, Spinner, TierBadge } from '../components/ui'
import { useQuery } from '../lib/hooks'

interface AcademyOverview {
  agent_count: number
  domains: {
    domain: string
    blurb: string
    agents: { id: string; name: string; tier: string; purpose: string; core: string }[]
  }[]
  tiers: { tier: string; name: string; meaning: string; in_the_product: string }[]
  design_rules: { rule: string; detail: string; enforced_by: string }[]
  learning_paths: {
    id: string
    title: string
    why: string
    steps: { id: string; name: string; tier: string; domain: string; one_liner: string }[]
  }[]
}

type Tab = 'start' | 'paths' | 'catalog' | 'tiers' | 'rules'

const TABS: { id: Tab; label: string }[] = [
  { id: 'start', label: 'Start here' },
  { id: 'paths', label: 'Learning paths' },
  { id: 'catalog', label: 'All 35 agents' },
  { id: 'tiers', label: 'Autonomy tiers' },
  { id: 'rules', label: 'Design rules' },
]

export default function Academy() {
  const { data, loading, error } = useQuery<AcademyOverview>('/api/academy')
  const [tab, setTab] = useState<Tab>('start')

  if (loading) return <Spinner label="Loading the academy" />
  if (error || !data) return <Empty title="Could not load the academy" hint={error ?? undefined} />

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white">Academy</h1>
        <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-400">
          What each of the {data.agent_count} agents is for, where its boundaries are, and how the
          fleet fits together. Every lesson is generated from the agent's own specification, so the
          training material cannot drift from the contract the runtime enforces.
        </p>
      </header>

      <div className="flex flex-wrap gap-2 border-b border-ink-800 pb-3">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`rounded-lg px-3 py-1.5 text-sm transition ${
              tab === item.id
                ? 'bg-accent/10 font-medium text-accent'
                : 'text-slate-400 hover:bg-ink-850 hover:text-slate-200'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'start' ? <StartHere data={data} /> : null}
      {tab === 'paths' ? <Paths data={data} /> : null}
      {tab === 'catalog' ? <Catalog data={data} /> : null}
      {tab === 'tiers' ? <Tiers data={data} /> : null}
      {tab === 'rules' ? <Rules data={data} /> : null}
    </div>
  )
}

function StartHere({ data }: { data: AcademyOverview }) {
  return (
    <div className="space-y-6">
      <Section title="The idea in one page">
        <div className="space-y-4 text-sm leading-relaxed text-slate-300">
          <p>
            Data engineering is not one job. Profiling a table, deciding what a column means,
            choosing a grain, writing the pipeline, setting a quality threshold and deciding who may
            see the result are different kinds of work, with different evidence and different ways
            of being wrong.
          </p>
          <p>
            The fleet splits that work into {data.agent_count} agents whose scopes do not overlap.
            Each agent's specification names the agent that owns every neighbouring piece of work,
            and those boundaries are reciprocal — if agent 01 says classification belongs to agent
            02, agent 02's spec says it receives that from 01.
          </p>
          <p>
            Three consequences follow, and they are what the product enforces. An agent that cannot
            get its required inputs is <strong className="text-white">blocked</strong> rather than
            guessing. An agent whose tier is advisory produces a{' '}
            <strong className="text-white">proposal</strong> a human accepts. And every number an
            agent reports about data is{' '}
            <strong className="text-white">computed, not generated</strong> — the model interprets
            statistics, it never invents them.
          </p>
        </div>
      </Section>

      <div className="grid gap-4 md:grid-cols-3">
        {data.domains.slice(0, 6).map((domain) => (
          <div key={domain.domain} className="card card-pad">
            <DomainBadge domain={domain.domain} />
            <p className="mt-3 text-sm leading-relaxed text-slate-400">{domain.blurb}</p>
            <p className="mt-3 text-xs text-slate-500">{domain.agents.length} agents</p>
          </div>
        ))}
      </div>

      <Section
        title="Where to go next"
        description="Follow a path, or open any agent's lesson directly."
      >
        <div className="grid gap-3 md:grid-cols-2">
          {data.learning_paths.slice(0, 4).map((path) => (
            <div key={path.id} className="rounded-lg border border-ink-700 bg-ink-850/40 p-4">
              <p className="text-sm font-semibold text-white">{path.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-slate-400">{path.why}</p>
              <div className="mt-3 flex flex-wrap gap-1">
                {path.steps.map((step) => (
                  <Link
                    key={step.id}
                    to={`/academy/${step.id}`}
                    className="chip border-ink-600 bg-ink-800 font-mono text-slate-400 hover:border-accent/40 hover:text-accent"
                  >
                    {step.id}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}

function Paths({ data }: { data: AcademyOverview }) {
  return (
    <div className="space-y-6">
      {data.learning_paths.map((path) => (
        <Section key={path.id} title={path.title} description={path.why}>
          <ol className="space-y-2">
            {path.steps.map((step, index) => (
              <li key={step.id} className="flex items-start gap-3">
                <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-ink-600 bg-ink-850 text-[11px] text-slate-400">
                  {index + 1}
                </span>
                <Link
                  to={`/academy/${step.id}`}
                  className="min-w-0 flex-1 rounded-lg border border-ink-700 bg-ink-850/40 px-4 py-2.5 transition hover:border-accent/40"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-slate-500">{step.id}</span>
                    <span className="text-sm font-medium text-slate-200">{step.name}</span>
                    <TierBadge tier={step.tier} />
                    <DomainBadge domain={step.domain} />
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{step.one_liner}</p>
                </Link>
              </li>
            ))}
          </ol>
        </Section>
      ))}
    </div>
  )
}

function Catalog({ data }: { data: AcademyOverview }) {
  return (
    <div className="space-y-6">
      {data.domains.map((domain) => (
        <Section
          key={domain.domain}
          title={domain.domain}
          description={domain.blurb}
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {domain.agents.map((agent) => (
              <Link
                key={agent.id}
                to={`/academy/${agent.id}`}
                className="rounded-lg border border-ink-700 bg-ink-850/40 p-4 transition hover:border-accent/40"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-slate-500">{agent.id}</span>
                  <TierBadge tier={agent.tier} />
                </div>
                <p className="mt-1.5 text-sm font-semibold text-slate-100">{agent.name}</p>
                <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-slate-400">
                  {agent.purpose}
                </p>
              </Link>
            ))}
          </div>
        </Section>
      ))}
    </div>
  )
}

function Tiers({ data }: { data: AcademyOverview }) {
  return (
    <Section
      title="Autonomy tiers"
      description="Tier is structural — a property of the agent's job, not of how well it happens to be performing."
    >
      <div className="space-y-3">
        {data.tiers.map((tier) => (
          <div key={tier.tier} className="rounded-lg border border-ink-700 bg-ink-850/40 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <TierBadge tier={tier.tier} name={tier.name} />
            </div>
            <p className="mt-2 text-sm leading-relaxed text-slate-300">{tier.meaning}</p>
            <p className="mt-2 border-t border-ink-800 pt-2 text-xs text-slate-500">
              <span className="text-slate-400">In ADE Studio: </span>
              {tier.in_the_product}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs leading-relaxed text-slate-500">
        Agents 02, 26 and 27 are capped at L1 in regulated environments regardless of measured
        accuracy. Mark a source as regulated when you register it and the cap applies automatically.
      </p>
    </Section>
  )
}

function Rules({ data }: { data: AcademyOverview }) {
  return (
    <Section
      title="Design rules"
      description="The five rules the catalog is built on, and where each one is enforced in this product."
    >
      <ol className="space-y-3">
        {data.design_rules.map((rule, index) => (
          <li key={rule.rule} className="rounded-lg border border-ink-700 bg-ink-850/40 p-4">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-ink-600 text-[11px] text-slate-400">
                {index + 1}
              </span>
              <div>
                <p className="text-sm font-semibold text-white">{rule.rule}</p>
                <p className="mt-1 text-sm leading-relaxed text-slate-400">{rule.detail}</p>
                <p className="mt-2 text-xs text-accent">Enforced by: {rule.enforced_by}</p>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </Section>
  )
}
