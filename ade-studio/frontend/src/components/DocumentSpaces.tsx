import { useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useMutation, useQuery } from '../lib/hooks'
import type { DocumentSpace } from './FilePicker'
import { Empty, ErrorNote, Field, InfoNote, Section, Spinner } from './ui'

interface SpaceCapability {
  kind: string
  label: string
  note: string
  fields: string[]
  dependency_available: boolean
  dependency_detail: string
}

interface Reachability {
  reachable: boolean
  detail: string
}

const FIELD_LABELS: Record<string, string> = {
  site_url: 'Site URL',
  tenant_id: 'Directory (tenant) ID',
  client_id: 'Application (client) ID',
  client_secret: 'Client secret',
  team_id: 'Team ID',
  channel_name: 'Channel name',
  root_path: 'Path on the server',
  bucket: 'Bucket',
  prefix: 'Key prefix',
  region: 'Region',
}

const FIELD_HINTS: Record<string, string> = {
  site_url: 'https://contoso.sharepoint.com/sites/DataPlatform',
  root_path: '/mnt/shared/data-platform',
  channel_name: 'The channel name exactly as it appears in Teams',
  prefix: 'Optional. Restricts the space to one prefix in the bucket.',
}

/**
 * The file half of Sources.
 *
 * Most of the fleet reads files rather than tables, and in a real estate those
 * files are in SharePoint, a Teams channel or on a share — not on the
 * operator's laptop. Registering the location once means an agent run can
 * point at it instead of someone downloading and re-uploading.
 */
export default function DocumentSpaces() {
  const { data: caps } = useQuery<{ kinds: SpaceCapability[] }>('/api/inputs/capabilities')
  const { data, loading, error, reload } = useQuery<{ spaces: DocumentSpace[] }>(
    '/api/inputs/spaces',
  )
  const [adding, setAdding] = useState(false)
  const [checks, setChecks] = useState<Record<string, Reachability>>({})

  const test = useMutation(async (id: string) => {
    const result = await api.get<Reachability>(`/api/inputs/spaces/${id}/test`)
    setChecks((current) => ({ ...current, [id]: result }))
    return result
  })
  const remove = useMutation(async (id: string) => api.del(`/api/inputs/spaces/${id}`))

  if (loading) return <Spinner label="Loading file sources" />
  if (error || !data) return <Empty title="Could not load file sources" hint={error ?? undefined} />

  const labelFor = (kind: string) => caps?.kinds.find((k) => k.kind === kind)?.label ?? kind

  return (
    <Section
      title="File sources"
      description="Where agents read documents, code and exports from. Read-only in every case except uploads."
      actions={
        <button type="button" className="btn-secondary" onClick={() => setAdding((v) => !v)}>
          {adding ? 'Cancel' : '+ Add file source'}
        </button>
      }
    >
      {data.spaces.length === 0 ? (
        <Empty
          title="No file sources yet"
          hint="Add one to give file-driven agents something to read."
        />
      ) : (
        <div className="space-y-3">
          {data.spaces.map((space) => {
            const check = checks[space.id]
            return (
              <div
                key={space.id}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-ink-800 px-4 py-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-200">{space.name}</span>
                    <span className="chip border-ink-700 bg-ink-850 text-slate-400">
                      {labelFor(space.kind)}
                    </span>
                    {space.regulated ? (
                      <span className="chip border-rose-500/30 bg-rose-500/10 text-rose-300">
                        regulated
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-0.5 truncate text-xs text-slate-500">
                    {space.site_url ||
                      space.root_path ||
                      space.bucket ||
                      'Uploaded from the workbench'}
                    {space.channel_name ? ` · #${space.channel_name}` : ''}
                  </p>
                  {check ? (
                    <p
                      className={`mt-1 text-xs ${
                        check.reachable ? 'text-emerald-400' : 'text-rose-300'
                      }`}
                    >
                      {check.detail}
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="btn-secondary h-8 px-3 text-xs"
                  onClick={() => void test.run(space.id)}
                  disabled={test.pending}
                >
                  Test
                </button>
                <button
                  type="button"
                  className="h-8 px-2 text-xs text-slate-500 hover:text-rose-300"
                  onClick={async () => {
                    await remove.run(space.id)
                    reload()
                  }}
                >
                  Remove
                </button>
              </div>
            )
          })}
        </div>
      )}

      {adding && caps ? (
        <div className="mt-4 border-t border-ink-800 pt-4">
          <AddSpace
            capabilities={caps.kinds}
            onDone={() => {
              setAdding(false)
              reload()
            }}
          />
        </div>
      ) : null}
    </Section>
  )
}

function AddSpace({
  capabilities,
  onDone,
}: {
  capabilities: SpaceCapability[]
  onDone: () => void
}) {
  const [kind, setKind] = useState(
    capabilities.find((c) => c.kind === 'sharepoint')?.kind ?? 'upload',
  )
  const [name, setName] = useState('')
  const [regulated, setRegulated] = useState(false)
  const [values, setValues] = useState<Record<string, string>>({})

  const selected = useMemo(() => capabilities.find((c) => c.kind === kind), [capabilities, kind])
  const create = useMutation(async (payload: Record<string, unknown>) =>
    api.post('/api/inputs/spaces', payload),
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">
        {capabilities.map((option) => (
          <button
            key={option.kind}
            type="button"
            onClick={() => {
              setKind(option.kind)
              setValues({})
            }}
            className={`chip transition ${
              option.kind === kind
                ? 'border-accent/50 bg-accent/10 text-accent'
                : 'border-ink-700 bg-ink-850 text-slate-400 hover:text-slate-200'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {selected ? <p className="text-sm text-slate-400">{selected.note}</p> : null}

      {selected && !selected.dependency_available ? (
        <InfoNote tone="warn">
          This source type needs a package that is not installed: {selected.dependency_detail}. You
          can still register it; it will report itself unreachable until the package is present.
        </InfoNote>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Name">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Data platform SharePoint"
            className="input"
          />
        </Field>
        {(selected?.fields ?? []).map((field) => (
          <Field key={field} label={FIELD_LABELS[field] ?? field} hint={FIELD_HINTS[field]}>
            <input
              type={field === 'client_secret' ? 'password' : 'text'}
              value={values[field] ?? ''}
              onChange={(e) => setValues((c) => ({ ...c, [field]: e.target.value }))}
              className="input"
            />
          </Field>
        ))}
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={regulated}
          onChange={(e) => setRegulated(e.target.checked)}
        />
        Regulated — caps agents 02, 26 and 27 at advisory tier for anything read from here
      </label>

      {create.error ? <ErrorNote message={create.error} /> : null}

      <button
        type="button"
        className="btn-primary"
        disabled={!name.trim() || create.pending}
        onClick={async () => {
          const result = await create.run({ name, kind, regulated, ...values })
          if (result) onDone()
        }}
      >
        {create.pending ? 'Adding…' : 'Add file source'}
      </button>
    </div>
  )
}
