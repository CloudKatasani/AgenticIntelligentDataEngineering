export const DOMAIN_STYLES: Record<string, { chip: string; dot: string; label: string }> = {
  discovery: { chip: 'border-sky-500/30 bg-sky-500/10 text-sky-300', dot: 'bg-sky-400', label: 'Discovery' },
  build: { chip: 'border-violet-500/30 bg-violet-500/10 text-violet-300', dot: 'bg-violet-400', label: 'Build' },
  quality: { chip: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300', dot: 'bg-emerald-400', label: 'Quality' },
  operations: { chip: 'border-amber-500/30 bg-amber-500/10 text-amber-300', dot: 'bg-amber-400', label: 'Operations' },
  governance: { chip: 'border-rose-500/30 bg-rose-500/10 text-rose-300', dot: 'bg-rose-400', label: 'Governance' },
  consumption: { chip: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300', dot: 'bg-cyan-400', label: 'Consumption' },
  'cross-cutting': { chip: 'border-slate-500/30 bg-slate-500/10 text-slate-300', dot: 'bg-slate-400', label: 'Cross-cutting' },
}

/** Literal colours for SVG, where Tailwind's `bg-*` utilities do not apply. */
export const DOMAIN_HEX: Record<string, string> = {
  discovery: '#38bdf8',
  build: '#a78bfa',
  quality: '#34d399',
  operations: '#fbbf24',
  governance: '#fb7185',
  consumption: '#22d3ee',
  'cross-cutting': '#94a3b8',
}

export function domainHex(domain: string): string {
  return DOMAIN_HEX[domain] ?? '#94a3b8'
}

export function domainStyle(domain: string) {
  return (
    DOMAIN_STYLES[domain] ?? {
      chip: 'border-slate-500/30 bg-slate-500/10 text-slate-300',
      dot: 'bg-slate-400',
      label: domain,
    }
  )
}

export const TIER_STYLES: Record<string, string> = {
  L0: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
  L1: 'border-sky-500/40 bg-sky-500/10 text-sky-300',
  L2: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  L3: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  L4: 'border-violet-500/40 bg-violet-500/10 text-violet-300',
}

export const STATUS_STYLES: Record<string, string> = {
  succeeded: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  awaiting_approval: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  blocked: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
  failed: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
  rejected: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
  partial: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  running: 'border-sky-500/40 bg-sky-500/10 text-sky-300',
  queued: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
}

export const STATUS_LABELS: Record<string, string> = {
  succeeded: 'Succeeded',
  awaiting_approval: 'Awaiting acceptance',
  blocked: 'Blocked',
  failed: 'Failed',
  rejected: 'Rejected',
  partial: 'Partial (cost cap)',
  running: 'Running',
  queued: 'Queued',
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function formatNumber(value: number): string {
  return value.toLocaleString('en-US')
}

export function formatCost(usd: number): string {
  if (usd === 0) return '$0.00'
  if (usd < 0.01) return `$${usd.toFixed(4)}`
  return `$${usd.toFixed(2)}`
}

export function formatDuration(ms: number | null): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

export function formatDateTime(iso: string): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function percent(ratio: number): string {
  return `${(ratio * 100).toFixed(ratio > 0 && ratio < 0.001 ? 4 : 2)}%`
}

/** Percentage rounded to whole points, for dashboard figures where decimals are noise. */
export function pct(ratio: number): string {
  return `${Math.round(ratio * 100)}%`
}

export function formatTokens(value: number): string {
  if (value < 1000) return String(value)
  if (value < 1_000_000) return `${(value / 1000).toFixed(1)}K`
  return `${(value / 1_000_000).toFixed(2)}M`
}

/** Relative age, for queue items where "9h ago" reads better than a timestamp. */
export function formatAge(hours: number | null): string {
  if (hours == null) return '—'
  if (hours < 1) return `${Math.round(hours * 60)}m`
  if (hours < 48) return `${Math.round(hours)}h`
  return `${Math.round(hours / 24)}d`
}
