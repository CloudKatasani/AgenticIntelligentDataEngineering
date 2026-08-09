import { useMemo, useState } from 'react'
import { Empty, ErrorNote, Field, InfoNote, Section, Spinner, Toggle } from '../components/ui'
import type { ConnectionSummary, SourceCapability } from '../lib/api'
import { api } from '../lib/api'
import { useMutation, useQuery } from '../lib/hooks'

const FIELD_LABELS: Record<string, string> = {
  account: 'Account identifier',
  username: 'Username',
  password: 'Password',
  warehouse: 'Warehouse',
  database: 'Database / catalog',
  schema_name: 'Default schema',
  role: 'Role',
  host: 'Host',
  port: 'Port',
  service_name: 'Service name',
  project_id: 'GCP project id',
  http_path: 'HTTP path',
  access_token: 'Access token',
  file_path: 'Directory path',
}

interface HealthResult {
  ok: boolean
  detail: string
  latency_ms: number | null
  driver_installed: boolean
  server_version: string | null
}

export default function Connections() {
  const { data: caps } = useQuery<{ sources: SourceCapability[] }>('/api/connections/capabilities')
  const { data, loading, error, reload } = useQuery<{ connections: ConnectionSummary[] }>(
    '/api/connections',
  )
  const [adding, setAdding] = useState(false)
  const [results, setResults] = useState<Record<string, HealthResult>>({})

  const test = useMutation(async (id: string) => {
    const result = await api.post<HealthResult>(`/api/connections/${id}/test`, {})
    setResults((current) => ({ ...current, [id]: result }))
    return result
  })

  const remove = useMutation(async (id: string) => api.del(`/api/connections/${id}`))

  if (loading) return <Spinner label="Loading sources" />
  if (error || !data) return <Empty title="Could not load sources" hint={error ?? undefined} />

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">Sources</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">
            Register the systems agents read from. Every connection is used read-only: the
            connectors refuse any statement that could mutate a source.
          </p>
        </div>
        <button type="button" className="btn-primary" onClick={() => setAdding((v) => !v)}>
          {adding ? 'Cancel' : '+ Add source'}
        </button>
      </header>

      {adding && caps ? (
        <AddConnection
          capabilities={caps.sources}
          onDone={() => {
            setAdding(false)
            reload()
          }}
        />
      ) : null}

      <Section title="Registered sources">
        {data.connections.length === 0 ? (
          <Empty title="No sources yet" hint="Add one above to get started." />
        ) : (
          <div className="space-y-3">
            {data.connections.map((connection) => {
              const result = results[connection.id]
              return (
                <div
                  key={connection.id}
                  className="rounded-lg border border-ink-700 bg-ink-850/40 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-white">{connection.name}</span>
                        <span className="chip border-ink-600 bg-ink-800 text-slate-400">
                          {connection.kind}
                        </span>
                        <span className="chip border-ink-600 bg-ink-800 text-slate-400">
                          {connection.environment}
                        </span>
                        {connection.regulated ? (
                          <span className="chip border-rose-500/40 bg-rose-500/10 text-rose-300">
                            regulated
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1 font-mono text-xs text-slate-500">
                        {[connection.host, connection.database, connection.schema_name]
                          .filter(Boolean)
                          .join(' · ') || connection.id}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <button
                        type="button"
                        className="btn-ghost px-3 py-1.5 text-xs"
                        disabled={test.pending}
                        onClick={() => test.run(connection.id)}
                      >
                        Test
                      </button>
                      {connection.id !== 'conn_demo' ? (
                        <button
                          type="button"
                          className="btn-danger px-3 py-1.5 text-xs"
                          onClick={async () => {
                            await remove.run(connection.id)
                            reload()
                          }}
                        >
                          Remove
                        </button>
                      ) : null}
                    </div>
                  </div>

                  {result ? (
                    <p
                      className={`mt-3 rounded-md border px-3 py-2 text-xs ${
                        result.ok
                          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                          : 'border-rose-500/30 bg-rose-500/10 text-rose-200'
                      }`}
                    >
                      {result.detail}
                      {result.server_version ? ` · ${result.server_version}` : ''}
                      {result.latency_ms != null ? ` · ${result.latency_ms} ms` : ''}
                    </p>
                  ) : null}

                  {connection.regulated ? (
                    <p className="mt-2 text-xs text-slate-500">
                      Agents 02, 26 and 27 are capped at tier L1 against this source.
                    </p>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </Section>

      {caps ? (
        <Section
          title="Supported source systems"
          description="Drivers are optional. A source whose driver is not installed is reported honestly rather than failing at run time."
        >
          <div className="grid gap-2 md:grid-cols-2">
            {caps.sources.map((source) => (
              <div
                key={source.kind}
                className="flex items-center justify-between gap-3 rounded-lg border border-ink-700 bg-ink-850/40 px-4 py-2.5"
              >
                <div className="min-w-0">
                  <p className="text-sm text-slate-200">{source.label}</p>
                  {!source.driver_installed ? (
                    <p className="mt-0.5 font-mono text-[11px] text-slate-500">
                      {source.install_hint}
                    </p>
                  ) : null}
                </div>
                <span
                  className={`chip shrink-0 ${
                    source.driver_installed
                      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                      : 'border-ink-600 bg-ink-800 text-slate-500'
                  }`}
                >
                  {source.driver_installed ? 'ready' : 'driver needed'}
                </span>
              </div>
            ))}
          </div>
        </Section>
      ) : null}
    </div>
  )
}

function AddConnection({
  capabilities,
  onDone,
}: {
  capabilities: SourceCapability[]
  onDone: () => void
}) {
  const [kind, setKind] = useState(capabilities[1]?.kind ?? 'snowflake')
  const [name, setName] = useState('')
  const [environment, setEnvironment] = useState('dev')
  const [regulated, setRegulated] = useState(false)
  const [values, setValues] = useState<Record<string, string>>({})

  const capability = useMemo(
    () => capabilities.find((c) => c.kind === kind),
    [capabilities, kind],
  )

  const create = useMutation(async () =>
    api.post('/api/connections', {
      name: name || `${kind} source`,
      kind,
      environment,
      regulated,
      ...Object.fromEntries(
        Object.entries(values).map(([key, value]) => [
          key,
          key === 'port' ? Number(value) || null : value,
        ]),
      ),
    }),
  )

  return (
    <Section title="Add a source">
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Source system">
          <select
            className="input"
            value={kind}
            onChange={(event) => {
              setKind(event.target.value)
              setValues({})
            }}
          >
            {capabilities.map((source) => (
              <option key={source.kind} value={source.kind}>
                {source.label}
                {source.driver_installed ? '' : ' — driver not installed'}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Display name">
          <input
            className="input"
            value={name}
            placeholder="e.g. Snowflake — Analytics PROD"
            onChange={(event) => setName(event.target.value)}
          />
        </Field>

        <Field label="Environment" hint="Production sources gate what agents may act on.">
          <select
            className="input"
            value={environment}
            onChange={(event) => setEnvironment(event.target.value)}
          >
            <option value="dev">dev</option>
            <option value="test">test</option>
            <option value="prod">prod</option>
          </select>
        </Field>

        <div className="flex items-end pb-2">
          <Toggle
            checked={regulated}
            onChange={setRegulated}
            label="Regulated — caps agents 02, 26 and 27 at tier L1"
          />
        </div>

        {(capability?.fields ?? []).map((field) => (
          <Field key={field} label={FIELD_LABELS[field] ?? field}>
            <input
              className="input"
              type={field === 'password' || field === 'access_token' ? 'password' : 'text'}
              value={values[field] ?? ''}
              onChange={(event) =>
                setValues((current) => ({ ...current, [field]: event.target.value }))
              }
            />
          </Field>
        ))}
      </div>

      {capability && !capability.driver_installed ? (
        <div className="mt-4">
          <InfoNote tone="warn">
            The driver for {capability.label} is not installed in this environment. You can still
            save the connection; browsing and running against it needs{' '}
            <code className="font-mono">{capability.install_hint}</code>.
          </InfoNote>
        </div>
      ) : null}

      {create.error ? (
        <div className="mt-4">
          <ErrorNote message={create.error} />
        </div>
      ) : null}

      <div className="mt-5 flex gap-2 border-t border-ink-800 pt-4">
        <button
          type="button"
          className="btn-primary"
          disabled={create.pending}
          onClick={async () => {
            const result = await create.run(undefined as never)
            if (result) onDone()
          }}
        >
          Save source
        </button>
        <button type="button" className="btn-ghost" onClick={onDone}>
          Cancel
        </button>
      </div>
    </Section>
  )
}
