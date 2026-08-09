import type { ReactNode } from 'react'
import { STATUS_LABELS, STATUS_STYLES, TIER_STYLES, domainStyle } from '../lib/format'

export function Badge({ className = '', children }: { className?: string; children: ReactNode }) {
  return <span className={`chip ${className}`}>{children}</span>
}

export function TierBadge({ tier, name }: { tier: string; name?: string }) {
  return (
    <Badge className={TIER_STYLES[tier] ?? TIER_STYLES.L1}>
      {tier}
      {name ? <span className="font-normal opacity-80">· {name}</span> : null}
    </Badge>
  )
}

export function DomainBadge({ domain }: { domain: string }) {
  const style = domainStyle(domain)
  return (
    <Badge className={style.chip}>
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </Badge>
  )
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge className={STATUS_STYLES[status] ?? STATUS_STYLES.queued}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  )
}

export function Section({
  title,
  description,
  actions,
  children,
}: {
  title: string
  description?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="card card-pad">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">{title}</h2>
          {description ? <p className="mt-1 text-sm text-slate-400">{description}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  )
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string
  value: ReactNode
  hint?: string
}) {
  return (
    <div className="card card-pad">
      <div className="label">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
      {hint ? <div className="mt-1 text-xs text-slate-400">{hint}</div> : null}
    </div>
  )
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-ink-700 px-6 py-10 text-center">
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {hint ? <p className="mt-1 text-sm text-slate-500">{hint}</p> : null}
    </div>
  )
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 px-2 py-6 text-sm text-slate-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-600 border-t-accent" />
      {label}…
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
      {message}
    </div>
  )
}

export function InfoNote({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' }) {
  const styles =
    tone === 'warn'
      ? 'border-amber-500/40 bg-amber-500/10 text-amber-200'
      : 'border-sky-500/30 bg-sky-500/10 text-sky-200'
  return <div className={`rounded-lg border px-4 py-3 text-sm ${styles}`}>{children}</div>
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {hint ? <span className="mt-0.5 block text-xs text-slate-500">{hint}</span> : null}
      <div className="mt-1.5">{children}</div>
    </label>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex items-center gap-3 text-left"
      aria-pressed={checked}
    >
      <span
        className={`relative h-5 w-9 shrink-0 rounded-full transition ${
          checked ? 'bg-accent' : 'bg-ink-700'
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
            checked ? 'left-[18px]' : 'left-0.5'
          }`}
        />
      </span>
      <span className="text-sm text-slate-300">{label}</span>
    </button>
  )
}
