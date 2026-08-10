/**
 * Who is driving the studio.
 *
 * The product has no authentication, so this is a declared label rather than a
 * verified identity — and the observability tab says so wherever it counts
 * operators. It is recorded anyway: adoption cannot be measured without knowing
 * who ran what, and an honest approximation beats a missing dimension.
 */

const KEY = 'ade.operator'
const DEFAULT = 'operator'

export function getOperator(): string {
  try {
    return localStorage.getItem(KEY)?.trim() || DEFAULT
  } catch {
    // Private browsing or a blocked store: fall back rather than break the run.
    return DEFAULT
  }
}

export function setOperator(value: string): void {
  try {
    const trimmed = value.trim()
    if (trimmed) localStorage.setItem(KEY, trimmed)
    else localStorage.removeItem(KEY)
  } catch {
    /* nothing to do — the run still carries the default */
  }
}
