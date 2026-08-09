import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Empty, InfoNote, Section, Spinner } from '../components/ui'
import { domainHex, domainStyle } from '../lib/format'
import { useQuery } from '../lib/hooks'

interface GraphData {
  nodes: { id: string; name: string; domain: string; tier: string; core: boolean }[]
  edges: { from: string; to: string; kind: 'hard' | 'soft' }[]
  topological_order: string[]
  cycles: string[][]
  acyclic: boolean
}

const NODE_W = 150
const NODE_H = 34
const COL_GAP = 90
const ROW_GAP = 14

/**
 * Layered dependency graph, drawn as SVG.
 *
 * Depth comes from the hard-dependency chain, so the horizontal axis is
 * genuinely "what must run before what" rather than an arbitrary layout.
 */
export default function Graph() {
  const { data, loading, error } = useQuery<GraphData>('/api/graph')
  const [showSoft, setShowSoft] = useState(true)
  const [focus, setFocus] = useState<string | null>(null)

  const layout = useMemo(() => {
    if (!data) return null

    const hardParents = new Map<string, string[]>()
    for (const node of data.nodes) hardParents.set(node.id, [])
    for (const edge of data.edges) {
      if (edge.kind === 'hard') hardParents.get(edge.to)?.push(edge.from)
    }

    // Longest-path depth over hard edges.
    const depth = new Map<string, number>()
    const resolve = (id: string, seen: Set<string>): number => {
      if (depth.has(id)) return depth.get(id)!
      if (seen.has(id)) return 0
      seen.add(id)
      const parents = hardParents.get(id) ?? []
      const value = parents.length === 0 ? 0 : Math.max(...parents.map((p) => resolve(p, seen))) + 1
      depth.set(id, value)
      return value
    }
    for (const node of data.nodes) resolve(node.id, new Set())

    const columns = new Map<number, typeof data.nodes>()
    for (const node of data.nodes) {
      const level = depth.get(node.id) ?? 0
      if (!columns.has(level)) columns.set(level, [])
      columns.get(level)!.push(node)
    }
    for (const [, group] of columns) {
      group.sort((a, b) => a.domain.localeCompare(b.domain) || a.id.localeCompare(b.id))
    }

    const positions = new Map<string, { x: number; y: number }>()
    let maxRows = 0
    for (const [level, group] of [...columns.entries()].sort((a, b) => a[0] - b[0])) {
      maxRows = Math.max(maxRows, group.length)
      group.forEach((node, row) => {
        positions.set(node.id, {
          x: level * (NODE_W + COL_GAP) + 20,
          y: row * (NODE_H + ROW_GAP) + 20,
        })
      })
    }

    return {
      positions,
      width: (columns.size - 1) * (NODE_W + COL_GAP) + NODE_W + 40,
      height: maxRows * (NODE_H + ROW_GAP) + 40,
      levels: columns.size,
    }
  }, [data])

  if (loading) return <Spinner label="Loading the dependency graph" />
  if (error || !data || !layout) return <Empty title="Could not load the graph" hint={error ?? undefined} />

  const visibleEdges = data.edges.filter((edge) => showSoft || edge.kind === 'hard')
  const connected = new Set<string>()
  if (focus) {
    connected.add(focus)
    for (const edge of data.edges) {
      if (edge.from === focus) connected.add(edge.to)
      if (edge.to === focus) connected.add(edge.from)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">Dependency graph</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">
            Solid edges are hard dependencies that block execution; dotted edges are soft
            dependencies that only improve quality. Columns are execution depth: everything in a
            column can run once the previous columns have.
          </p>
        </div>
        <button
          type="button"
          className={showSoft ? 'btn-primary' : 'btn-ghost'}
          onClick={() => setShowSoft((v) => !v)}
        >
          Soft edges {showSoft ? 'on' : 'off'}
        </button>
      </header>

      {data.acyclic ? (
        <InfoNote>
          The hard-dependency graph is acyclic across all {data.nodes.length} agents — validated at
          load time, so a hand-edited spec cannot silently introduce a cycle.
        </InfoNote>
      ) : (
        <InfoNote tone="warn">
          Cycles detected: {data.cycles.map((c) => c.join(' → ')).join(' | ')}
        </InfoNote>
      )}

      <Section
        title="Fleet graph"
        description={
          focus
            ? `Highlighting agent ${focus} and its immediate neighbours. Click it again to clear.`
            : 'Click a node to highlight its neighbours; click its id to open the agent.'
        }
      >
        <div className="scroll-thin overflow-x-auto">
          <svg
            width={layout.width}
            height={layout.height}
            viewBox={`0 0 ${layout.width} ${layout.height}`}
            className="min-w-full"
            role="img"
            aria-label="Agent dependency graph"
          >
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#33405a" />
              </marker>
            </defs>

            {visibleEdges.map((edge, index) => {
              const from = layout.positions.get(edge.from)
              const to = layout.positions.get(edge.to)
              if (!from || !to) return null
              const x1 = from.x + NODE_W
              const y1 = from.y + NODE_H / 2
              const x2 = to.x
              const y2 = to.y + NODE_H / 2
              const mid = (x1 + x2) / 2
              const dim = focus && !(connected.has(edge.from) && connected.has(edge.to))
              return (
                <path
                  key={index}
                  d={`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`}
                  fill="none"
                  stroke={edge.kind === 'hard' ? '#3f5170' : '#2a3448'}
                  strokeWidth={edge.kind === 'hard' ? 1.4 : 1}
                  strokeDasharray={edge.kind === 'soft' ? '4 4' : undefined}
                  markerEnd="url(#arrow)"
                  opacity={dim ? 0.12 : 0.85}
                />
              )
            })}

            {data.nodes.map((node) => {
              const position = layout.positions.get(node.id)!
              const dim = focus ? !connected.has(node.id) : false
              return (
                <g
                  key={node.id}
                  transform={`translate(${position.x}, ${position.y})`}
                  opacity={dim ? 0.25 : 1}
                  className="cursor-pointer"
                  onClick={() => setFocus((current) => (current === node.id ? null : node.id))}
                >
                  <rect
                    width={NODE_W}
                    height={NODE_H}
                    rx={7}
                    fill={focus === node.id ? '#0f766e' : '#182031'}
                    stroke={focus === node.id ? '#5eead4' : '#232d42'}
                  />
                  <circle cx={12} cy={NODE_H / 2} r={3.5} fill={domainHex(node.domain)} />
                  <text x={24} y={NODE_H / 2 + 4} fontSize="11" fill="#e2e8f0" fontFamily="ui-monospace">
                    {node.id}
                  </text>
                  <text x={44} y={NODE_H / 2 + 4} fontSize="10.5" fill="#94a3b8">
                    {node.name.length > 22 ? `${node.name.slice(0, 21)}…` : node.name}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        <div className="mt-4 flex flex-wrap gap-3 border-t border-ink-800 pt-4">
          {['discovery', 'build', 'quality', 'operations', 'governance', 'consumption', 'cross-cutting'].map(
            (domain) => {
              const style = domainStyle(domain)
              return (
                <span key={domain} className="flex items-center gap-1.5 text-xs text-slate-400">
                  <span className={`h-2 w-2 rounded-full ${style.dot}`} />
                  {style.label}
                </span>
              )
            },
          )}
        </div>
      </Section>

      {focus ? (
        <Section title={`Agent ${focus}`}>
          <div className="flex flex-wrap gap-2">
            <Link to={`/agents/${focus}`} className="btn-primary">
              Run agent {focus}
            </Link>
            <Link to={`/academy/${focus}`} className="btn-ghost">
              Learn agent {focus}
            </Link>
          </div>
        </Section>
      ) : null}

      <Section
        title="Execution order"
        description="A topological ordering of the fleet honouring every hard dependency."
      >
        <div className="flex flex-wrap gap-1.5">
          {data.topological_order.map((id, index) => (
            <Link
              key={id}
              to={`/academy/${id}`}
              className="chip border-ink-600 bg-ink-800 font-mono text-slate-400 hover:border-accent/40 hover:text-accent"
              title={`Position ${index + 1}`}
            >
              {id}
            </Link>
          ))}
        </div>
      </Section>
    </div>
  )
}
