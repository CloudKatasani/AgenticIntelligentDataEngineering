import { useEffect, useMemo, useState } from 'react'
import type { ColumnMeta, ConnectionSummary, TableMeta } from '../lib/api'
import { api } from '../lib/api'
import { useQuery } from '../lib/hooks'
import { formatNumber } from '../lib/format'
import { Empty, Field, Spinner } from './ui'

export interface SelectedObject {
  database: string | null
  schema_name: string | null
  table: string
  columns: string[]
}

export function objectKey(object: SelectedObject): string {
  return [object.database, object.schema_name, object.table].filter(Boolean).join('.')
}

/**
 * Browse a source's catalog and pick the objects an agent will run against.
 *
 * The same component serves every source kind, because the backend exposes one
 * metadata shape for all of them.
 */
export default function ObjectPicker({
  connections,
  connectionId,
  onConnectionChange,
  selected,
  onChange,
}: {
  connections: ConnectionSummary[]
  connectionId: string | null
  onConnectionChange: (id: string) => void
  selected: SelectedObject[]
  onChange: (objects: SelectedObject[]) => void
}) {
  const [database, setDatabase] = useState<string | null>(null)
  const [schema, setSchema] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const { data: databases } = useQuery<{ databases: string[] }>(
    connectionId ? `/api/connections/${connectionId}/databases` : null,
  )
  const { data: schemas } = useQuery<{ schemas: string[] }>(
    connectionId
      ? `/api/connections/${connectionId}/schemas${database ? `?database=${encodeURIComponent(database)}` : ''}`
      : null,
  )
  const tablesPath = useMemo(() => {
    if (!connectionId || !schema) return null
    const params = new URLSearchParams()
    if (database) params.set('database', database)
    params.set('schema', schema)
    return `/api/connections/${connectionId}/tables?${params.toString()}`
  }, [connectionId, database, schema])
  const { data: tables, loading: tablesLoading, error: tablesError } = useQuery<{ tables: TableMeta[] }>(tablesPath)

  // Reset the drill-down whenever the source changes.
  useEffect(() => {
    setDatabase(null)
    setSchema(null)
  }, [connectionId])

  useEffect(() => {
    if (!database && databases?.databases.length) setDatabase(databases.databases[0])
  }, [databases, database])

  useEffect(() => {
    if (!schema && schemas?.schemas.length) setSchema(schemas.schemas[0])
  }, [schemas, schema])

  const isSelected = (table: TableMeta) =>
    selected.some(
      (o) => o.table === table.name && o.schema_name === (table.schema_name ?? schema),
    )

  const toggle = (table: TableMeta) => {
    const entry: SelectedObject = {
      database: database ?? null,
      schema_name: table.schema_name ?? schema ?? null,
      table: table.name,
      columns: [],
    }
    if (isSelected(table)) {
      onChange(selected.filter((o) => objectKey(o) !== objectKey(entry)))
    } else {
      onChange([...selected, entry])
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Source">
          <select
            className="input"
            value={connectionId ?? ''}
            onChange={(event) => onConnectionChange(event.target.value)}
          >
            <option value="" disabled>
              Select a source…
            </option>
            {connections.map((connection) => (
              <option key={connection.id} value={connection.id}>
                {connection.name} ({connection.kind})
                {connection.regulated ? ' · regulated' : ''}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Database / catalog">
          <select
            className="input"
            value={database ?? ''}
            onChange={(event) => {
              setDatabase(event.target.value || null)
              setSchema(null)
            }}
            disabled={!databases?.databases.length}
          >
            {(databases?.databases ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
            {!databases?.databases.length ? <option value="">—</option> : null}
          </select>
        </Field>

        <Field label="Schema">
          <select
            className="input"
            value={schema ?? ''}
            onChange={(event) => setSchema(event.target.value || null)}
            disabled={!schemas?.schemas.length}
          >
            {(schemas?.schemas ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
            {!schemas?.schemas.length ? <option value="">—</option> : null}
          </select>
        </Field>
      </div>

      {tablesError ? (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {tablesError}
        </div>
      ) : null}

      {tablesLoading ? <Spinner label="Reading catalog" /> : null}

      {tables && tables.tables.length === 0 ? (
        <Empty title="No objects in this schema" />
      ) : null}

      {tables && tables.tables.length > 0 ? (
        <div className="max-h-80 overflow-y-auto rounded-lg border border-ink-700 scroll-thin">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-ink-850 text-left text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="w-10 px-3 py-2" />
                <th className="px-3 py-2">Object</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2 text-right">Rows</th>
                <th className="w-20 px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-800">
              {tables.tables.map((table) => (
                <TableRow
                  key={table.name}
                  table={table}
                  connectionId={connectionId!}
                  database={database}
                  schema={schema}
                  selected={isSelected(table)}
                  expanded={expanded === table.name}
                  onToggleSelect={() => toggle(table)}
                  onToggleExpand={() =>
                    setExpanded((current) => (current === table.name ? null : table.name))
                  }
                  selectedColumns={
                    selected.find((o) => o.table === table.name)?.columns ?? []
                  }
                  onColumnsChange={(columns) =>
                    onChange(
                      selected.map((o) =>
                        o.table === table.name ? { ...o, columns } : o,
                      ),
                    )
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {selected.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-wider text-slate-500">In scope</span>
          {selected.map((object) => (
            <span
              key={objectKey(object)}
              className="chip border-accent/30 bg-accent/10 font-mono text-accent"
            >
              {objectKey(object)}
              {object.columns.length ? ` · ${object.columns.length} cols` : ''}
              <button
                type="button"
                className="ml-1 text-accent/70 hover:text-white"
                onClick={() => onChange(selected.filter((o) => objectKey(o) !== objectKey(object)))}
                aria-label={`Remove ${objectKey(object)}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function TableRow({
  table,
  connectionId,
  database,
  schema,
  selected,
  expanded,
  onToggleSelect,
  onToggleExpand,
  selectedColumns,
  onColumnsChange,
}: {
  table: TableMeta
  connectionId: string
  database: string | null
  schema: string | null
  selected: boolean
  expanded: boolean
  onToggleSelect: () => void
  onToggleExpand: () => void
  selectedColumns: string[]
  onColumnsChange: (columns: string[]) => void
}) {
  const [columns, setColumns] = useState<ColumnMeta[] | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!expanded || columns) return
    setLoading(true)
    const params = new URLSearchParams({ table: table.name })
    if (database) params.set('database', database)
    if (schema) params.set('schema', schema)
    api
      .get<TableMeta>(`/api/connections/${connectionId}/columns?${params.toString()}`)
      .then((meta) => setColumns(meta.columns))
      .catch(() => setColumns([]))
      .finally(() => setLoading(false))
  }, [expanded, columns, connectionId, database, schema, table.name])

  return (
    <>
      <tr className={selected ? 'bg-accent/5' : ''}>
        <td className="px-3 py-2">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="h-4 w-4 rounded border-ink-600 bg-ink-850 accent-teal-400"
            aria-label={`Select ${table.name}`}
          />
        </td>
        <td className="px-3 py-2 font-mono text-xs text-slate-200">{table.name}</td>
        <td className="px-3 py-2 text-xs text-slate-500">{table.kind}</td>
        <td className="px-3 py-2 text-right text-xs tabular-nums text-slate-400">
          {table.row_count == null ? '—' : formatNumber(table.row_count)}
        </td>
        <td className="px-3 py-2 text-right">
          <button
            type="button"
            onClick={onToggleExpand}
            className="text-xs text-slate-500 hover:text-accent"
          >
            {expanded ? 'hide' : 'columns'}
          </button>
        </td>
      </tr>
      {expanded ? (
        <tr>
          <td colSpan={5} className="bg-ink-950/60 px-3 py-3">
            {loading ? (
              <span className="text-xs text-slate-500">Reading columns…</span>
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-slate-500">
                  Leave all unchecked to profile every column.
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {(columns ?? []).map((column) => {
                    const active = selectedColumns.includes(column.name)
                    return (
                      <button
                        key={column.name}
                        type="button"
                        onClick={() =>
                          onColumnsChange(
                            active
                              ? selectedColumns.filter((c) => c !== column.name)
                              : [...selectedColumns, column.name],
                          )
                        }
                        className={`chip font-mono ${
                          active
                            ? 'border-accent/40 bg-accent/10 text-accent'
                            : 'border-ink-700 bg-ink-850 text-slate-400 hover:border-ink-600'
                        }`}
                        title={column.data_type}
                      >
                        {column.name}
                        <span className="opacity-50">{column.data_type}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </td>
        </tr>
      ) : null}
    </>
  )
}
