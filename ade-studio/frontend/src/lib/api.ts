/**
 * Typed client for the ADE Studio API.
 *
 * One place that knows about transport, so components deal in domain objects.
 */

export class ApiError extends Error {
  code: string
  details: unknown
  status: number

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    let code = 'http_error'
    let message = `${response.status} ${response.statusText}`
    let details: unknown
    try {
      const body = await response.json()
      if (body?.error) {
        code = body.error.code ?? code
        message = body.error.message ?? message
        details = body.error.details
      } else if (body?.detail) {
        message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      /* non-JSON error body — keep the status line */
    }
    throw new ApiError(response.status, code, message, details)
  }
  return (await response.json()) as T
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T,>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  del: <T,>(path: string) => request<T>(path, { method: 'DELETE' }),
}

/* ----------------------------------------------------------------------- */
/* Domain types (mirroring the backend's response shapes)                   */
/* ----------------------------------------------------------------------- */

export type Tier = 'L0' | 'L1' | 'L2' | 'L3' | 'L4'

export interface Dependency {
  agent_id: string
  agent_name: string
  kind: 'hard' | 'soft'
}

export interface Recommendation {
  model_id: string
  effort: string
  reason: string
  max_output_tokens: number
}

export interface AgentSummary {
  id: string
  slug: string
  name: string
  domain: string
  tier: Tier
  tier_name: string
  core_original_scope: boolean
  purpose: string
  requires_dataset: boolean
  requires_approval: boolean
  hard_dependencies: Dependency[]
  soft_dependencies: Dependency[]
  artifact_count: number
  recommended_model: Recommendation
}

export interface ArtifactSpec {
  key: string
  filename: string
  title: string
  description: string
  format: string
  source: string
}

export interface AgentParameter {
  key: string
  label: string
  type: 'string' | 'text' | 'integer' | 'number' | 'boolean' | 'enum'
  description: string
  default: unknown
  options: string[]
  required: boolean
}

export interface NonGoal {
  exclusion: string
  owned_by: string
  owner_name: string
}

export interface AgentDetail extends Omit<AgentSummary, 'artifact_count' | 'recommended_model'> {
  tier_definition: string
  scope: string[]
  non_goals: NonGoal[]
  inputs: string[]
  outputs: string[]
  tools: string[]
  context_layer_requirements: string[]
  triggers: string[]
  acceptance_criteria: string[]
  evaluation: string[]
  kpis: string[]
  escalation: string
  skill_markdown: string
  artifacts: ArtifactSpec[]
  parameters: AgentParameter[]
  recommended_model: Recommendation
  dependents: { id: string; name: string; domain: string }[]
  seams: { direction: string; counterpart_id: string; counterpart_name: string; detail: string }[]
  execution_plan: { id: string; name: string; tier: Tier }[]
}

export interface ModelDescriptor {
  id: string
  display_name: string
  tier: 'frontier' | 'balanced' | 'fast'
  context_window: number
  max_output_tokens: number
  input_usd_per_mtok: number
  output_usd_per_mtok: number
  strengths: string[]
  best_for_domains: string[]
  notes: string
}

export interface ProviderStatus {
  provider: string
  live: boolean
  detail: string
}

export interface ConnectionSummary {
  id: string
  name: string
  kind: string
  environment: string
  owner: string
  regulated: boolean
  database?: string | null
  schema_name?: string | null
  host?: string | null
  has_password: boolean
  has_access_token: boolean
}

export interface SourceCapability {
  kind: string
  label: string
  driver_installed: boolean
  install_hint: string
  fields: string[]
}

export interface TableMeta {
  database?: string | null
  schema_name?: string | null
  name: string
  kind: string
  row_count?: number | null
  comment?: string | null
  columns: ColumnMeta[]
}

export interface ColumnMeta {
  name: string
  data_type: string
  nullable: boolean
  comment?: string | null
  ordinal: number
}

export interface GateResult {
  name: string
  passed: boolean
  detail: string
  blocking: boolean
}

export interface RunArtifact extends ArtifactSpec {
  id: string
  run_id: string
  agent_id: string
  kind: 'proposal' | 'record'
  size_bytes: number
  sha256: string
  created_at: string
  download_url: string
  view_url: string
}

export type RunStatus =
  | 'queued'
  | 'running'
  | 'awaiting_approval'
  | 'succeeded'
  | 'failed'
  | 'blocked'
  | 'rejected'
  | 'partial'

export interface RunSummary {
  id: string
  agent_id: string
  agent_name: string
  agent_domain: string
  status: RunStatus
  model_id: string
  effort: string
  provider: string
  created_at: string
  duration_ms: number | null
  artifact_count: number
  cost_usd: number
  objects: string[]
  summary: string
  error: string | null
}

export interface RunDetail extends RunSummary {
  gates: GateResult[]
  artifacts: RunArtifact[]
  findings: string[]
  open_questions: string[]
  handoffs: { to_agent_id: string; to_agent_name: string; reason: string }[]
  events: { at: string; level: string; message: string; data: Record<string, unknown> }[]
  profiles: TableProfile[]
  usage: {
    input_tokens: number
    output_tokens: number
    cost_usd: number
  }
  bundle_url: string
  approved_by: string | null
  approved_at: string | null
}

export interface ColumnProfile {
  column: string
  data_type: string
  null_count: number
  null_ratio: number
  distinct_count: number
  distinct_ratio: number
  min_value: string | null
  max_value: string | null
  sample_patterns: string[]
  is_candidate_key: boolean
}

export interface TableProfile {
  table: string
  row_count: number
  sampled_rows: number
  sample_strategy: string
  columns: ColumnProfile[]
  candidate_primary_keys: { column: string; confidence: number; evidence: string }[]
}

export interface RunPreview {
  gates: GateResult[]
  blocked: boolean
  requires_approval: boolean
  effective_tier: Tier
  artifacts: ArtifactSpec[]
  estimate: {
    input_tokens: number
    output_tokens: number
    cost_usd: number
    model: string
    note: string
  }
}
