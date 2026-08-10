import ObjectPicker, { type SelectedObject } from './ObjectPicker'
import FilePicker, { type DocumentRef, type DocumentSpace } from './FilePicker'
import { InfoNote } from './ui'
import type { ConnectionSummary } from '../lib/api'

export interface InputSlot {
  key: string
  label: string
  kind: string
  kind_label: string
  required: boolean
  help: string
  spec_reference: string
  origins: string[]
  accepts: string[]
  placeholder: string
  max_files: number
  accepts_files: boolean
}

export interface InputContract {
  agent_id: string
  agent_name: string
  primary_kind: string
  primary_kind_label: string
  upstream_only: boolean
  upstream_note: string
  slots: InputSlot[]
}

export interface SlotValue {
  objects: SelectedObject[]
  files: DocumentRef[]
  text: string
}

export const emptySlot = (): SlotValue => ({ objects: [], files: [], text: '' })

export function slotFilled(slot: InputSlot, value: SlotValue | undefined): boolean {
  if (!value) return false
  if (slot.kind === 'database_objects') return value.objects.length > 0
  if (slot.kind === 'structured_request') return value.text.trim().length > 0
  return value.files.length > 0
}

const KIND_BADGES: Record<string, string> = {
  database_objects: 'border-sky-500/30 bg-sky-500/10 text-sky-300',
  code_artifacts: 'border-violet-500/30 bg-violet-500/10 text-violet-300',
  telemetry_export: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  policy_document: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  structured_request: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300',
  upstream_artifacts: 'border-slate-500/30 bg-slate-500/10 text-slate-300',
}

export function KindBadge({ kind, label }: { kind: string; label: string }) {
  return <span className={`chip ${KIND_BADGES[kind] ?? KIND_BADGES.upstream_artifacts}`}>{label}</span>
}

/**
 * Render the inputs one agent asks for.
 *
 * Every agent used to get the same table picker, which was wrong for
 * twenty-nine of the thirty-five: a lineage agent needs SQL and ETL exports, a
 * FinOps agent needs a metering export, a supervisor needs a sentence. The
 * slots come from the agent's own spec, so this component has no per-agent
 * knowledge in it.
 */
export default function InputSlots({
  contract,
  values,
  onChange,
  connections,
  connectionId,
  onConnectionChange,
  spaces,
}: {
  contract: InputContract
  values: Record<string, SlotValue>
  onChange: (key: string, value: SlotValue) => void
  connections: ConnectionSummary[]
  connectionId: string | null
  onConnectionChange: (id: string) => void
  spaces: DocumentSpace[]
}) {
  if (contract.upstream_only) {
    return (
      <InfoNote>
        <strong>This agent asks you for nothing.</strong> {contract.upstream_note} Satisfy its
        dependencies by running the upstream agents, and it has everything it needs.
      </InfoNote>
    )
  }

  return (
    <div className="space-y-6">
      {contract.slots.map((slot) => {
        const value = values[slot.key] ?? emptySlot()
        const filled = slotFilled(slot, value)

        return (
          <div key={slot.key} className="rounded-lg border border-ink-800 p-4">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-slate-200">{slot.label}</span>
              <KindBadge kind={slot.kind} label={slot.kind_label} />
              {slot.required ? (
                <span className="text-[11px] uppercase tracking-wider text-rose-400">required</span>
              ) : (
                <span className="text-[11px] uppercase tracking-wider text-slate-600">optional</span>
              )}
              {filled ? <span className="ml-auto text-xs text-emerald-400">✓ supplied</span> : null}
            </div>

            <p className="mb-3 text-sm leading-relaxed text-slate-400">{slot.help}</p>

            {slot.kind === 'database_objects' ? (
              <ObjectPicker
                connections={connections}
                connectionId={connectionId}
                onConnectionChange={onConnectionChange}
                selected={value.objects}
                onChange={(objects) => onChange(slot.key, { ...value, objects })}
              />
            ) : slot.kind === 'structured_request' ? (
              <textarea
                value={value.text}
                onChange={(e) => onChange(slot.key, { ...value, text: e.target.value })}
                placeholder={slot.placeholder}
                rows={4}
                className="input font-normal"
              />
            ) : (
              <FilePicker
                spaces={spaces}
                selected={value.files}
                onChange={(files) => onChange(slot.key, { ...value, files })}
                accepts={slot.accepts}
                maxFiles={slot.max_files}
              />
            )}

            {slot.spec_reference ? (
              <p className="mt-3 border-t border-ink-850 pt-2 text-[11px] text-slate-600">
                From this agent's spec: <span className="text-slate-500">{slot.spec_reference}</span>
              </p>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
