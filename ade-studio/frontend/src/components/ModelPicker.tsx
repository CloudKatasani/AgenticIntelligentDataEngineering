import type { ModelDescriptor, Recommendation } from '../lib/api'
import { Field } from './ui'

const TIER_LABEL: Record<string, string> = {
  frontier: 'Frontier',
  balanced: 'Balanced',
  fast: 'Fast',
}

const TIER_CHIP: Record<string, string> = {
  frontier: 'border-violet-500/40 bg-violet-500/10 text-violet-300',
  balanced: 'border-sky-500/40 bg-sky-500/10 text-sky-300',
  fast: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
}

/**
 * Per-task model selection.
 *
 * The recommendation is shown with its reason so the choice is informed rather
 * than inherited — a different agent in the same session can use a different
 * model.
 */
export default function ModelPicker({
  models,
  effortLevels,
  modelId,
  effort,
  recommendation,
  onModelChange,
  onEffortChange,
}: {
  models: ModelDescriptor[]
  effortLevels: { value: string; label: string; note: string }[]
  modelId: string
  effort: string
  recommendation?: Recommendation
  onModelChange: (id: string) => void
  onEffortChange: (effort: string) => void
}) {
  const selected = models.find((m) => m.id === modelId)

  return (
    <div className="space-y-4">
      {recommendation ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-ink-700 bg-ink-850/60 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs uppercase tracking-wider text-slate-500">
              Recommended for this agent
            </p>
            <p className="mt-0.5 text-sm text-slate-300">{recommendation.reason}</p>
          </div>
          <button
            type="button"
            className="btn-ghost shrink-0"
            onClick={() => {
              onModelChange(recommendation.model_id)
              onEffortChange(recommendation.effort)
            }}
          >
            Use {models.find((m) => m.id === recommendation.model_id)?.display_name ?? recommendation.model_id}
          </button>
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {models.map((model) => {
          const active = model.id === modelId
          const recommended = recommendation?.model_id === model.id
          return (
            <button
              key={model.id}
              type="button"
              onClick={() => onModelChange(model.id)}
              className={`rounded-lg border p-4 text-left transition ${
                active
                  ? 'border-accent/60 bg-accent/5 ring-1 ring-accent/30'
                  : 'border-ink-700 bg-ink-850/50 hover:border-ink-600'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-sm font-semibold text-white">{model.display_name}</span>
                <span className={`chip ${TIER_CHIP[model.tier]}`}>{TIER_LABEL[model.tier]}</span>
              </div>
              <p className="mt-1 font-mono text-[11px] text-slate-500">{model.id}</p>
              <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-slate-400">
                <dt>Input</dt>
                <dd className="text-right tabular-nums">${model.input_usd_per_mtok}/Mtok</dd>
                <dt>Output</dt>
                <dd className="text-right tabular-nums">${model.output_usd_per_mtok}/Mtok</dd>
                <dt>Context</dt>
                <dd className="text-right tabular-nums">
                  {(model.context_window / 1000).toLocaleString()}K
                </dd>
              </dl>
              {recommended ? (
                <p className="mt-2 text-[11px] font-medium text-accent">★ Recommended here</p>
              ) : null}
            </button>
          )
        })}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Effort"
          hint="Controls how deeply the model reasons, trading cost and latency against thoroughness."
        >
          <select
            className="input"
            value={effort}
            onChange={(event) => onEffortChange(event.target.value)}
          >
            {effortLevels.map((level) => (
              <option key={level.value} value={level.value}>
                {level.label} — {level.note}
              </option>
            ))}
          </select>
        </Field>

        {selected ? (
          <div className="rounded-lg border border-ink-700 bg-ink-850/50 p-4">
            <p className="text-xs uppercase tracking-wider text-slate-500">Why this model</p>
            <ul className="mt-2 space-y-1 text-xs text-slate-400">
              {selected.strengths.map((strength) => (
                <li key={strength} className="flex gap-2">
                  <span className="text-accent">·</span>
                  {strength}
                </li>
              ))}
            </ul>
            {selected.notes ? (
              <p className="mt-2 border-t border-ink-800 pt-2 text-xs text-slate-500">
                {selected.notes}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}
