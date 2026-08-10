import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ModelPicker from '../components/ModelPicker'
import type { DocumentSpace } from '../components/FilePicker'
import InputSlots, {
  KindBadge,
  slotFilled,
  type InputContract,
  type SlotValue,
} from '../components/InputSlots'
import {
  DomainBadge,
  Empty,
  ErrorNote,
  Field,
  InfoNote,
  Section,
  Spinner,
  TierBadge,
  Toggle,
} from '../components/ui'
import type {
  AgentDetail,
  ConnectionSummary,
  ModelDescriptor,
  ProviderStatus,
  RunDetail,
  RunPreview,
} from '../lib/api'
import { api } from '../lib/api'
import { formatCost } from '../lib/format'
import { useMutation, useQuery } from '../lib/hooks'
import { getOperator } from '../lib/operator'

interface ModelsResponse {
  models: ModelDescriptor[]
  effort_levels: { value: string; label: string; note: string }[]
  provider: ProviderStatus
}

export default function Workbench() {
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()

  const { data: agent, loading, error } = useQuery<AgentDetail>(
    agentId ? `/api/agents/${agentId}` : null,
  )
  const { data: models } = useQuery<ModelsResponse>('/api/models')
  const { data: connectionsData } = useQuery<{ connections: ConnectionSummary[] }>(
    '/api/connections',
  )
  const { data: contract } = useQuery<InputContract>(
    agentId ? `/api/inputs/contract/${agentId}` : null,
    [agentId],
  )
  const { data: spacesData } = useQuery<{ spaces: DocumentSpace[] }>('/api/inputs/spaces')

  const [connectionId, setConnectionId] = useState<string | null>(null)
  const [slotValues, setSlotValues] = useState<Record<string, SlotValue>>({})
  const [modelId, setModelId] = useState('')
  const [effort, setEffort] = useState('high')
  const [parameters, setParameters] = useState<Record<string, unknown>>({})
  const [objective, setObjective] = useState('')
  const [costCap, setCostCap] = useState('5')
  const [override, setOverride] = useState(false)
  const [overrideReason, setOverrideReason] = useState('')
  const [preview, setPreview] = useState<RunPreview | null>(null)

  // Seed the form from the agent's own defaults as soon as it loads.
  useEffect(() => {
    if (!agent) return
    setModelId(agent.recommended_model.model_id)
    setEffort(agent.recommended_model.effort)
    const defaults: Record<string, unknown> = {}
    for (const parameter of agent.parameters) {
      if (parameter.default !== null && parameter.default !== undefined) {
        defaults[parameter.key] = parameter.default
      }
    }
    setParameters(defaults)
    setSlotValues({})
    setPreview(null)
  }, [agent])

  useEffect(() => {
    const list = connectionsData?.connections ?? []
    if (!connectionId && list.length) setConnectionId(list[0].id)
  }, [connectionsData, connectionId])

  // One binding per slot the agent declared, in the shape the API expects.
  // Empty slots are dropped rather than sent as blanks, so the gate reports
  // "needs a metering export" instead of "received an empty metering export".
  const inputs = useMemo(() => {
    const payload: Record<string, unknown> = {}
    for (const slot of contract?.slots ?? []) {
      const value = slotValues[slot.key]
      if (!slotFilled(slot, value)) continue
      if (slot.kind === 'database_objects') {
        payload[slot.key] = {
          origin: 'connection',
          connection_id: connectionId,
          datasets: value.objects.map((object) => ({
            database: object.database,
            schema_name: object.schema_name,
            table: object.table,
            columns: object.columns,
          })),
        }
      } else if (slot.kind === 'structured_request') {
        payload[slot.key] = { origin: 'inline', text: value.text }
      } else {
        // Files from several spaces can fill one slot; the origin recorded is
        // the space the first file came from, and each id carries its own.
        const spaceId = value.files[0]?.space_id ?? ''
        const kind = (spacesData?.spaces ?? []).find((s) => s.id === spaceId)?.kind ?? 'upload'
        payload[slot.key] = { origin: kind, file_ids: value.files.map((f) => f.id) }
      }
    }
    return payload
  }, [contract, slotValues, connectionId, spacesData])

  const body = useMemo(
    () => ({
      agent_id: agentId ?? '',
      connection_id: connectionId,
      inputs,
      model_id: modelId,
      effort,
      max_output_tokens: agent?.recommended_model.max_output_tokens ?? 16000,
      parameters,
      objective,
      cost_cap_usd: Number(costCap) || undefined,
      override_dependency_gate: override,
      override_reason: overrideReason,
    }),
    [agentId, connectionId, inputs, modelId, effort, agent, parameters, objective, costCap, override, overrideReason],
  )

  // The operator is read at call time rather than memoised into `body`: a
  // memo would freeze whoever was signed in when the page mounted.
  const previewMutation = useMutation(async () =>
    api.post<RunPreview>('/api/runs/preview', { ...body, actor: getOperator() }),
  )
  const runMutation = useMutation(async () =>
    api.post<RunDetail>('/api/runs', { ...body, actor: getOperator() }),
  )

  // Re-check the guardrails whenever the configuration changes.
  const refreshPreview = useCallback(async () => {
    if (!agentId || !modelId) return
    const result = await previewMutation.run(undefined as never)
    if (result) setPreview(result)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentId, modelId, body])

  useEffect(() => {
    const timer = setTimeout(refreshPreview, 250)
    return () => clearTimeout(timer)
  }, [refreshPreview])

  if (loading) return <Spinner label="Loading agent" />
  if (error || !agent) return <Empty title="Agent not found" hint={error ?? undefined} />

  const connections = connectionsData?.connections ?? []
  const blockingGates = (preview?.gates ?? []).filter((g) => g.blocking && !g.passed)
  const canRun = Boolean(modelId) && !previewMutation.pending && blockingGates.length === 0

  return (
    <div className="space-y-6">
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
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">{agent.purpose}</p>
          </div>
          <div className="flex shrink-0 gap-2">
            <Link to={`/canvas/${agent.id}`} className="btn-ghost">
              ▧ Worked example
            </Link>
            <Link to={`/academy/${agent.id}`} className="btn-ghost">
              ✦ Learn this agent
            </Link>
          </div>
        </div>

        <div className="mt-4 grid gap-3 border-t border-ink-800 pt-4 sm:grid-cols-3">
          <Boundary title="Owns" items={agent.scope.slice(0, 3)} />
          <Boundary
            title="Hands off"
            items={agent.non_goals.slice(0, 3).map((g) => `${g.exclusion} → ${g.owner_name}`)}
          />
          <Boundary
            title="Depends on"
            items={
              agent.hard_dependencies.length
                ? agent.hard_dependencies.map((d) => `${d.agent_id} ${d.agent_name} (hard)`)
                : ['No hard dependencies']
            }
          />
        </div>
      </header>

      {models && !models.provider.live ? (
        <InfoNote tone="warn">{models.provider.detail}</InfoNote>
      ) : null}

      <Section
        title="1 · Inputs"
        description={
          contract
            ? contract.upstream_only
              ? 'Everything this agent needs comes from upstream agents.'
              : `What ${contract.agent_name} needs, taken from its own spec.`
            : 'Loading this agent\u2019s input contract\u2026'
        }
        actions={
          contract && !contract.upstream_only ? (
            <KindBadge kind={contract.primary_kind} label={contract.primary_kind_label} />
          ) : undefined
        }
      >
        {!contract ? (
          <Spinner label="Loading input contract" />
        ) : (
          <InputSlots
            contract={contract}
            values={slotValues}
            onChange={(key, value) => setSlotValues((current) => ({ ...current, [key]: value }))}
            connections={connections}
            connectionId={connectionId}
            onConnectionChange={(id) => {
              setConnectionId(id)
              // Object selections belong to the source they were made against.
              setSlotValues((current) => {
                const next: Record<string, SlotValue> = {}
                for (const [key, value] of Object.entries(current)) {
                  next[key] = { ...value, objects: [] }
                }
                return next
              })
            }}
            spaces={spacesData?.spaces ?? []}
          />
        )}
      </Section>

      <Section
        title="2 · Model for this task"
        description="Each run records the model and effort it used, so results stay reproducible."
      >
        {models ? (
          <ModelPicker
            models={models.models}
            effortLevels={models.effort_levels}
            modelId={modelId}
            effort={effort}
            recommendation={agent.recommended_model}
            onModelChange={setModelId}
            onEffortChange={setEffort}
          />
        ) : (
          <Spinner label="Loading models" />
        )}
      </Section>

      <Section title="3 · Parameters" description="Run-time knobs declared by this agent's spec.">
        <div className="grid gap-4 md:grid-cols-2">
          {agent.parameters.map((parameter) => (
            <Field
              key={parameter.key}
              label={`${parameter.label}${parameter.required ? ' *' : ''}`}
              hint={parameter.description}
            >
              {parameter.type === 'enum' ? (
                <select
                  className="input"
                  value={String(parameters[parameter.key] ?? '')}
                  onChange={(e) =>
                    setParameters((p) => ({ ...p, [parameter.key]: e.target.value }))
                  }
                >
                  {parameter.options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              ) : parameter.type === 'boolean' ? (
                <Toggle
                  checked={Boolean(parameters[parameter.key])}
                  onChange={(value) => setParameters((p) => ({ ...p, [parameter.key]: value }))}
                  label={parameter.label}
                />
              ) : parameter.type === 'text' ? (
                <textarea
                  className="input min-h-[92px]"
                  value={String(parameters[parameter.key] ?? '')}
                  onChange={(e) =>
                    setParameters((p) => ({ ...p, [parameter.key]: e.target.value }))
                  }
                />
              ) : (
                <input
                  className="input"
                  type={parameter.type === 'integer' || parameter.type === 'number' ? 'number' : 'text'}
                  value={String(parameters[parameter.key] ?? '')}
                  onChange={(e) =>
                    setParameters((p) => ({
                      ...p,
                      [parameter.key]:
                        parameter.type === 'integer'
                          ? Number(e.target.value)
                          : e.target.value,
                    }))
                  }
                />
              )}
            </Field>
          ))}

          <Field
            label="Objective (optional)"
            hint="Business context for this run. Appended to the task brief."
          >
            <textarea
              className="input min-h-[92px]"
              placeholder="e.g. Onboarding the retail source for the customer-360 data product."
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
            />
          </Field>

          <Field label="Cost cap (USD)" hint="Work stops and partial results persist if reached.">
            <input
              className="input"
              type="number"
              step="0.5"
              min="0.5"
              value={costCap}
              onChange={(event) => setCostCap(event.target.value)}
            />
          </Field>
        </div>
      </Section>

      <Section
        title="4 · Guardrails and run"
        description="Every gate is evaluated before anything executes, and recorded on the run."
      >
        {previewMutation.error ? <ErrorNote message={previewMutation.error} /> : null}

        <div className="space-y-2">
          {(preview?.gates ?? []).map((gate) => (
            <div
              key={gate.name}
              className={`flex items-start gap-3 rounded-lg border px-4 py-2.5 text-sm ${
                gate.passed
                  ? 'border-ink-700 bg-ink-850/50 text-slate-300'
                  : gate.blocking
                    ? 'border-rose-500/40 bg-rose-500/10 text-rose-200'
                    : 'border-amber-500/40 bg-amber-500/10 text-amber-200'
              }`}
            >
              <span className="mt-0.5">{gate.passed ? '✓' : gate.blocking ? '✕' : '!'}</span>
              <div className="min-w-0">
                <span className="font-mono text-xs uppercase tracking-wider opacity-70">
                  {gate.name.replace(/_/g, ' ')}
                </span>
                <p className="mt-0.5">{gate.detail}</p>
              </div>
            </div>
          ))}
        </div>

        {blockingGates.some((g) => g.name === 'hard_dependencies') ? (
          <div className="mt-4 space-y-3 rounded-lg border border-ink-700 bg-ink-850/50 p-4">
            <Toggle
              checked={override}
              onChange={setOverride}
              label="Override the dependency gate for this run"
            />
            {override ? (
              <input
                className="input"
                placeholder="Reason for the override — recorded on the run"
                value={overrideReason}
                onChange={(event) => setOverrideReason(event.target.value)}
              />
            ) : null}
            <p className="text-xs text-slate-500">
              Running an agent without its hard dependencies means it reasons without inputs it was
              designed to consume. The reason is written into the run's provenance.
            </p>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap items-center justify-between gap-4 border-t border-ink-800 pt-5">
          <div className="text-sm text-slate-400">
            {preview ? (
              <>
                <span className="text-slate-300">
                  {preview.artifacts.length} artifacts · est. {formatCost(preview.estimate.cost_usd)}
                </span>
                <span className="ml-2 text-xs text-slate-500">{preview.estimate.note}</span>
                {preview.requires_approval ? (
                  <p className="mt-1 text-xs text-amber-300">
                    Tier {preview.effective_tier}: output will be a proposal requiring acceptance.
                  </p>
                ) : null}
              </>
            ) : (
              'Checking guardrails…'
            )}
          </div>

          <button
            type="button"
            className="btn-primary"
            disabled={!canRun || runMutation.pending}
            onClick={async () => {
              const run = await runMutation.run(undefined as never)
              if (run) navigate(`/runs/${run.id}`)
            }}
          >
            {runMutation.pending ? 'Running…' : `Run agent ${agent.id}`}
          </button>
        </div>

        {runMutation.error ? (
          <div className="mt-3">
            <ErrorNote message={runMutation.error} />
          </div>
        ) : null}
      </Section>

      <Section
        title="Artifacts this agent produces"
        description="The file contract for every run of this agent."
      >
        <ul className="grid gap-3 md:grid-cols-2">
          {agent.artifacts.map((artifact) => (
            <li key={artifact.key} className="rounded-lg border border-ink-700 bg-ink-850/40 p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-accent">{artifact.filename}</span>
                <span className="chip border-ink-600 bg-ink-800 text-slate-400">
                  {artifact.format}
                </span>
              </div>
              <p className="mt-1.5 text-sm font-medium text-slate-200">{artifact.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">{artifact.description}</p>
              {artifact.source === 'deterministic' ? (
                <p className="mt-2 text-[11px] text-emerald-400">
                  Computed deterministically — not model-generated.
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  )
}

function Boundary({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="label">{title}</p>
      <ul className="mt-2 space-y-1">
        {items.map((item) => (
          <li key={item} className="text-xs leading-relaxed text-slate-400">
            · {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
