import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import { formatBytes, formatDateTime } from '../lib/format'
import { Empty, ErrorNote, Spinner } from './ui'

export interface DocumentSpace {
  id: string
  name: string
  kind: string
  owner: string
  regulated: boolean
  root_path: string | null
  site_url: string | null
  channel_name: string | null
  bucket: string | null
}

export interface DocumentRef {
  id: string
  space_id: string
  name: string
  path: string
  size_bytes: number
  modified_at: string
  is_folder: boolean
  content_type: string
}

const SPACE_ICONS: Record<string, string> = {
  upload: '⇧',
  sharepoint: '◧',
  teams: '◍',
  shared_drive: '▤',
  object_store: '⬢',
}

const SPACE_LABELS: Record<string, string> = {
  upload: 'Upload',
  sharepoint: 'SharePoint',
  teams: 'Teams',
  shared_drive: 'Shared drive',
  object_store: 'Object storage',
}

/**
 * Choose files for one input slot, from wherever they live.
 *
 * The space kinds sit side by side rather than behind a mode switch: in a real
 * estate the copybooks are on a share, the metering export is in a Teams
 * channel, and the thing someone just received by email is on their laptop.
 * Which one an agent gets should not change how it is chosen.
 */
export default function FilePicker({
  spaces,
  selected,
  onChange,
  accepts,
  maxFiles,
}: {
  spaces: DocumentSpace[]
  selected: DocumentRef[]
  onChange: (files: DocumentRef[]) => void
  accepts: string[]
  maxFiles: number
}) {
  const [spaceId, setSpaceId] = useState(spaces[0]?.id ?? '')
  const [path, setPath] = useState('')
  const [entries, setEntries] = useState<DocumentRef[]>([])
  const [parent, setParent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const space = useMemo(() => spaces.find((s) => s.id === spaceId), [spaces, spaceId])
  const chosen = useMemo(() => new Set(selected.map((f) => f.id)), [selected])

  useEffect(() => {
    if (!spaces.length) return
    if (!spaces.some((s) => s.id === spaceId)) setSpaceId(spaces[0].id)
  }, [spaces, spaceId])

  const browse = useCallback(
    async (target: string) => {
      if (!spaceId) return
      setLoading(true)
      setError(null)
      try {
        const result = await api.get<{ entries: DocumentRef[]; parent: string | null }>(
          `/api/inputs/spaces/${spaceId}/browse?path=${encodeURIComponent(target)}`,
        )
        setEntries(result.entries)
        setParent(result.parent)
        setPath(target)
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
        setEntries([])
      } finally {
        setLoading(false)
      }
    },
    [spaceId],
  )

  useEffect(() => {
    setQuery('')
    void browse('')
  }, [browse])

  const search = useCallback(async () => {
    if (!query.trim()) return void browse(path)
    setLoading(true)
    try {
      const result = await api.get<{ entries: DocumentRef[] }>(
        `/api/inputs/spaces/${spaceId}/search?q=${encodeURIComponent(query)}`,
      )
      setEntries(result.entries)
      setParent(path)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [query, spaceId, path, browse])

  function toggle(entry: DocumentRef) {
    if (chosen.has(entry.id)) {
      onChange(selected.filter((f) => f.id !== entry.id))
    } else if (selected.length < maxFiles) {
      onChange([...selected, entry])
    }
  }

  async function upload(files: FileList | null) {
    if (!files?.length || !space) return
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      for (const file of Array.from(files)) form.append('files', file)
      const result = await api.postForm<{ uploaded: DocumentRef[] }>(
        `/api/inputs/spaces/${space.id}/upload`,
        form,
      )
      onChange([...selected, ...result.uploaded].slice(0, maxFiles))
      await browse(path)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  // Extension filtering is a hint, not a rule: a client's metering export is a
  // CSV until the day it is a JSON, and refusing it would be an obstacle
  // rather than a guardrail. Non-matching files are shown, just dimmed.
  const matches = (entry: DocumentRef) =>
    !accepts.length ||
    entry.is_folder ||
    accepts.some((extension) => entry.name.toLowerCase().endsWith(extension))

  if (!spaces.length) {
    return (
      <Empty
        title="No file sources registered"
        hint="Add a SharePoint library, Teams channel, shared drive or upload area under Sources."
      />
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {spaces.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setSpaceId(option.id)}
            className={`chip transition ${
              option.id === spaceId
                ? 'border-accent/50 bg-accent/10 text-accent'
                : 'border-ink-700 bg-ink-850 text-slate-400 hover:text-slate-200'
            }`}
            title={SPACE_LABELS[option.kind] ?? option.kind}
          >
            <span className="opacity-70">{SPACE_ICONS[option.kind] ?? '▤'}</span>
            {option.name}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void search()}
          placeholder="Search this source…"
          className="input h-8 flex-1 py-0 text-xs"
        />
        {space?.kind === 'upload' ? (
          <>
            <input
              ref={fileInput}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => void upload(e.target.files)}
            />
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              disabled={uploading}
              className="btn-secondary h-8 px-3 text-xs"
            >
              {uploading ? 'Uploading…' : 'Upload files'}
            </button>
          </>
        ) : null}
      </div>

      {path || parent !== null ? (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <button
            type="button"
            onClick={() => void browse('')}
            className="hover:text-accent"
            disabled={!path}
          >
            {space?.name ?? 'root'}
          </button>
          {path ? <span>/ {path}</span> : null}
          {parent !== null && path ? (
            <button
              type="button"
              onClick={() => void browse(parent)}
              className="ml-auto hover:text-accent"
            >
              ↑ up
            </button>
          ) : null}
        </div>
      ) : null}

      {error ? <ErrorNote message={error} /> : null}
      {loading ? <Spinner label="Loading" /> : null}

      {!loading && !error ? (
        <div className="max-h-72 overflow-y-auto rounded-lg border border-ink-800">
          {entries.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-slate-500">
              Nothing here.
              {space?.kind === 'upload' ? ' Upload a file to get started.' : ''}
            </div>
          ) : (
            <ul className="divide-y divide-ink-850">
              {entries.map((entry) => (
                <li key={entry.id}>
                  {entry.is_folder ? (
                    <button
                      type="button"
                      onClick={() => void browse(entry.path)}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-300 hover:bg-ink-850"
                    >
                      <span className="text-slate-500">▸</span>
                      {entry.name}
                    </button>
                  ) : (
                    <label
                      className={`flex cursor-pointer items-center gap-2.5 px-3 py-2 text-sm hover:bg-ink-850 ${
                        matches(entry) ? 'text-slate-300' : 'text-slate-600'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={chosen.has(entry.id)}
                        onChange={() => toggle(entry)}
                        disabled={!chosen.has(entry.id) && selected.length >= maxFiles}
                      />
                      <span className="min-w-0 flex-1 truncate">{entry.name}</span>
                      <span className="shrink-0 text-xs tabular-nums text-slate-500">
                        {formatBytes(entry.size_bytes)}
                      </span>
                      <span className="hidden shrink-0 text-xs text-slate-600 sm:inline">
                        {formatDateTime(entry.modified_at)}
                      </span>
                    </label>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      {selected.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-slate-500">
            {selected.length} of {maxFiles} selected:
          </span>
          {selected.map((file) => (
            <button
              key={file.id}
              type="button"
              onClick={() => onChange(selected.filter((f) => f.id !== file.id))}
              className="chip border-accent/40 bg-accent/10 text-accent"
              title={`${file.path} — click to remove`}
            >
              {file.name} ✕
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
