# ADE Studio

A control plane for the [Agentic Data Engineering agent fleet](../ade-agent-specs/README.md).

Pick one of the 35 agents, point it at a database object, choose the model for that
task, run it, and download what it produces. The guardrails the catalog specifies —
non-overlapping scope, typed dependencies, structural autonomy tiers, deterministic
statistics — are enforced in code, not requested in prose.

```
┌──────────────┐        ┌──────────────────┐        ┌────────────────────┐
│  Agent fleet │        │   Run engine     │        │   Source systems   │
│  (35 specs)  │───────▶│  gates → profile │───────▶│ Snowflake, Oracle, │
│  loaded from │        │  → reason → sign │        │ BigQuery, Postgres │
│  the catalog │        └────────┬─────────┘        │ Databricks, files… │
└──────────────┘                 │                  └────────────────────┘
                                 ▼
                    artifacts + provenance manifest
                    (download individually or as a zip)
```

## Quickstart

Nothing is required beyond Python 3.11 and Node 20. The app ships a seeded demo
warehouse and an offline execution mode, so a fresh clone runs an agent immediately —
no database and no API key.

```bash
cd ade-studio

# Backend
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[dev]"

# Frontend (built once; the backend then serves it)
npm --prefix frontend install
npm --prefix frontend run build

# Run
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
```

Open <http://127.0.0.1:8000>. Go to **Agent fleet → 01 Source Profiling Agent**, pick
`ADE_DEMO.RETAIL.CUSTOMERS`, and run it.

For frontend development with hot reload, run `npm --prefix frontend run dev` and use
port 5173; it proxies `/api` to the backend.

### Connecting real models

```bash
export ADE_ANTHROPIC_API_KEY=sk-ant-...
```

Without a key the app runs in **offline simulation mode**: the profiler still computes
real statistics from your real data, and the narrative around them is templated. Every
artifact and every run produced this way is labelled `simulation`, so it can never be
mistaken for model output.

### Connecting real sources

Database drivers are optional extras — the app runs with none installed and reports each
source's driver status honestly instead of failing at run time.

```bash
backend/.venv/bin/pip install -e "backend[snowflake,oracle,postgres]"
```

Supported: Snowflake, Oracle, PostgreSQL, Redshift, MySQL, SQL Server, Databricks SQL,
BigQuery, flat files (CSV/Parquet/JSON), and the bundled demo warehouse. Add one under
**Sources**; the object picker, profiler and run engine work identically across all of them.

## What the product does

### Run any agent against any object

The workbench is the same four steps for all 35 agents, because the differences live in
the specs rather than in bespoke screens:

1. **Source and objects** — browse catalog → schema → table, and optionally narrow to
   specific columns.
2. **Model for this task** — every model in the current lineup with its pricing and
   context window, plus a recommendation for *this* agent and the reason behind it. Agent
   08 (open-ended modelling) defaults to a frontier model; agent 01 (whose numbers are
   computed, not generated) defaults to a fast one. You override per run.
3. **Parameters** — the knobs that agent's spec declares (target dialect, modelling style,
   regulations in scope, severity floor…), plus a free-text objective.
4. **Guardrails and run** — every gate is evaluated and shown *before* anything executes,
   with a cost estimate.

### Artifacts you can actually use

Each agent has a file contract: agent 07 emits `schema.sql`, `schema-contract.yaml` and
`migration-notes.md`; agent 16 emits `quality-rules.yaml`, `thresholds.json` and
`rule-rationale.md`. Every artifact is hashed, viewable inline and downloadable
individually or as a zip containing a `MANIFEST.json` with full provenance — model,
effort, gates, objects, token usage and approval record.

### Academy

A tab that teaches the fleet: why each agent exists, what it owns, what it must never do
and who owns that instead, its dependencies and dependents, its workflow, how it is
measured, and a checkpoint quiz. Six guided learning paths run through the graph
("Onboard a new source, end to end", "Make a dataset trustworthy", "Modernize a legacy
system"…).

Every lesson is generated from the agent's own `spec.yaml` and `SKILL.md`. Nothing is
hand-written per agent, so the training material cannot drift from the contract the
runtime enforces — the usual failure mode of an internal wiki.

## How the design rules are enforced

The catalog states five design rules. Each maps to a specific mechanism:

| Catalog rule | Enforced by |
|---|---|
| Non-overlapping scope by construction | `handoffs` is a required field of every run's output contract; the run records work the agent refused because another agent owns it |
| Dependencies are typed; hard deps block | The `hard_dependencies` gate refuses to run an agent until its upstream agents have completed for that scope. Overridable only with a reason written into the provenance |
| Autonomy tiers are structural | L0/L1 runs finish in `awaiting_approval` and their artifacts are `proposal`s until a human accepts. Agents 02, 26 and 27 are capped at L1 whenever the source is marked regulated. Agent 20 never executes against production |
| Determinism where possible | `runtime/deterministic/profiler.py` computes every statistic; the model receives them as facts and is instructed never to recompute a number |
| Cross-cutting agents have no domain scope | Agents 33–35 are estate-scoped and require no object selection |

Two further guardrails come from the universal-guardrails section of every SKILL.md:

- **Read-only by construction.** `assert_read_only()` runs over every statement the
  connectors issue and rejects anything that could mutate a source.
- **Harvested metadata is untrusted.** Table names, column comments and sampled values are
  framed to the model as untrusted input, never as instructions.

## Architecture

Ports and adapters, so the run engine never learns what it is talking to.

```
backend/app/
├── domain/        Pure models — agents, connections, models, runs. No I/O.
├── ports/         Interfaces: SourceConnector, LLMProvider, repositories.
├── adapters/
│   ├── connectors/  One class per dialect + the seeded demo warehouse
│   ├── llm/         Anthropic provider + offline simulation provider
│   └── storage/     Filesystem artifacts, JSON repositories
├── runtime/
│   ├── deterministic/profiler.py   Every number an agent reports
│   ├── prompt.py                   SKILL.md verbatim + task brief + output schema
│   └── artifact_plans.py           Per-agent file contracts and parameters
├── services/      Catalog, graph, models, runs, academy
└── api/           FastAPI routers; deps.py is the composition root
```

**The fleet is not hardcoded.** `CatalogService` reads `ade-agent-specs/registry.yaml`
and each agent's `spec.yaml` and `SKILL.md` at load time. Adding an agent means adding a
spec folder — the workbench, graph, academy and run engine pick it up with no code
change. An agent with no curated artifact plan falls back to one derived from its declared
outputs, so a new spec is runnable immediately.

## Tests

```bash
backend/.venv/bin/python -m pytest backend
node frontend/scripts/e2e-smoke.mjs      # drives a real run through the UI
```

The suite asserts the invariants the product rests on: all 35 agents load, every
dependency and non-goal resolves to a real agent, the hard-dependency graph is acyclic,
seams are reciprocal, the profiler's numbers match what lands in the artifacts, hard
dependencies block, advisory tiers produce proposals, regulated sources cap the tier, and
agent 20 refuses production.

## Configuration

All settings are environment variables prefixed `ADE_`.

| Variable | Default | Purpose |
|---|---|---|
| `ADE_ANTHROPIC_API_KEY` | unset | Enables live model runs |
| `ADE_DEFAULT_MODEL_ID` | `claude-opus-5` | Fallback model |
| `ADE_SPECS_ROOT` | auto-discovered | Path to `ade-agent-specs` |
| `ADE_DATA_ROOT` | `backend/.ade-studio-data` | Artifacts, runs, connections, demo warehouse |
| `ADE_DEFAULT_COST_CAP_USD` | `5.0` | Per-run spend cap |
| `ADE_MAX_OBJECTS_PER_RUN` | `25` | Objects per run |
| `ADE_MAX_SAMPLE_ROWS` | `500` | Upper bound on profiling sample size |

## Known limits

Worth stating plainly for a client conversation:

- **Runs are synchronous.** A run holds its HTTP request. That is fine for the object
  counts the gate allows; a production deployment would move execution to a queue.
- **Persistence is JSON files.** Single-process by design. The repository ports exist so
  moving to Postgres touches no service code.
- **No authentication.** There is no user model, so approvals record an actor string
  rather than an authenticated identity. Put this behind your own auth before exposing it.
- **Agent 20 plans but never executes.** Remediation output is always a reviewable plan;
  ADE Studio has no write path to any source.
