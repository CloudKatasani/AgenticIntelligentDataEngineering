# ADE Studio

A control plane for the [Agentic Data Engineering agent fleet](../ade-agent-specs/README.md).

Pick one of the 35 agents, give it what it actually needs — a table, a folder of COBOL
copybooks, a metering export, a sentence — choose the model for that task, run it, and
download what it produces. The guardrails the catalog specifies —
non-overlapping scope, typed dependencies, structural autonomy tiers, deterministic
statistics — are enforced in code, not requested in prose.

```
┌──────────────┐        ┌──────────────────┐        ┌────────────────────┐
│  Agent fleet │        │   Run engine     │        │  Databases         │
│  (35 specs)  │───────▶│  gates → read    │───────▶│  Snowflake, Oracle…│
│  loaded from │        │  → reason → sign │        ├────────────────────┤
│  the catalog │        └────────┬─────────┘        │  Files             │
└──────────────┘                 │                  │  SharePoint, Teams,│
                                 │                  │  shares, S3, upload│
                                 │                  └────────────────────┘
                                 ▼
                    artifacts + provenance manifest
                    (download individually or as a zip)
```

## Quickstart

Nothing is required beyond Python 3.11 and Node 20. The app ships a seeded demo
warehouse and an offline execution mode, so a fresh clone runs an agent immediately —
no database and no API key.

For the longer version — a demo script, troubleshooting, and how to reset state —
see [RUNNING.md](../RUNNING.md).

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
`ADE_DEMO.RETAIL.CUSTOMERS`, and run it. Then try **06 Source System Interrogation**,
which asks for COBOL copybooks instead — a sample set is seeded alongside the demo
warehouse, so both work on a fresh clone.

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

### Connecting file sources

SharePoint and Teams need one extra package; object storage needs boto3. Both report
themselves unreachable with the install hint rather than failing at run time.

```bash
backend/.venv/bin/pip install -e "backend[sharepoint]"   # SharePoint + Teams
backend/.venv/bin/pip install -e "backend[aws]"          # S3
```

Uploads and shared drives need nothing. Register any of them under **Sources → File
sources**; ADE Studio authenticates to SharePoint and Teams with read-only application
credentials.

### Connecting real databases

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

1. **Inputs** — whatever *that* agent needs. Not the same for any two of them; see below.
2. **Model for this task** — every model in the current lineup with its pricing and
   context window, plus a recommendation for *this* agent and the reason behind it. Agent
   08 (open-ended modelling) defaults to a frontier model; agent 01 (whose numbers are
   computed, not generated) defaults to a fast one. You override per run.
3. **Parameters** — the knobs that agent's spec declares (target dialect, modelling style,
   regulations in scope, severity floor…), plus a free-text objective.
4. **Guardrails and run** — every gate is evaluated and shown *before* anything executes,
   with a cost estimate.

### Every agent asks for what it actually consumes

Only **6 of the 35** agents read database tables. A lineage agent reads SQL and ETL
exports; a legacy-interrogation agent reads COBOL copybooks and Informatica XML; a FinOps
agent reads a metering export; a supervisor reads a sentence. Two agents ask for nothing
at all, because everything they need arrives from upstream runs.

So each agent declares **input slots**, and every slot traces back to a line in that
agent's own `spec.yaml`, quoted underneath it in the UI:

| Primary input | Agents | Example |
|---|---|---|
| Database objects | 6 | 01 profiles the tables you select |
| Code and ETL artifacts | 4 | 06 reads copybooks and proc bodies |
| Telemetry export | 7 | 22 reads a warehouse metering export |
| Policy document | 8 | 26 reads your role-entitlement matrix |
| Written request | 8 | 24 needs a backfill scope and reason |
| Upstream artifacts only | 2 | 09 and 11 ask you for nothing |

Files can come from a **SharePoint library, a Teams channel, a mounted shared drive, an S3
bucket, or a direct upload** — registered once under Sources, then picked per run. Where a
file lives is not the agent's business: a copybook is a copybook whether it arrived from
SharePoint or a laptop, and the prompt cannot tell the difference.

Everything ADE Studio reads is read-only. Uploads are the one place it writes, and the API
refuses an upload aimed at any other kind of space — it will never write to a customer's
SharePoint library or bucket.

The gate matches. Agent 22 is blocked for a missing metering export, not for an unselected
table; agent 09 is never asked for anything at all.

### Artifacts you can actually use

Each agent has a file contract: agent 07 emits `schema.sql`, `schema-contract.yaml` and
`migration-notes.md`; agent 16 emits `quality-rules.yaml`, `thresholds.json` and
`rule-rationale.md`. Every artifact is hashed, viewable inline and downloadable
individually or as a zip containing a `MANIFEST.json` with full provenance — model,
effort, gates, objects, token usage and approval record.

### Canvas — a worked example for every agent

The tab built for the demo. For each of the 35 agents: the exact input it is
given on the left, the agent in the middle, and the artifacts it generates on
the right — full file bodies, not summaries. A COBOL copybook in, a rule
inventory with file-and-line citations out.

All 35 are set in **one estate telling one story**: a mainframe customer master
and a legacy warehouse becoming a certified customer-360 product. Read end to
end they are a single migration; read one at a time, each is a demo of one
agent. The objects are the ones in the seeded demo warehouse and sample file
workspace, so "can I see that for real?" runs the same configuration rather
than a different one.

Each example also carries **what to point at** — the moments that answer a data
leader's actual question — and **what it refused to do**, with the agent that
owns that work instead.

Two things keep it honest. Every example is labelled an illustration rather
than a run record, with a live run one click away. And the artifact filenames,
their deterministic-versus-reasoned labels, and the input kinds are all
validated against the live catalog in CI — so an example cannot drift into
showing something the product no longer does. That check caught a real drift
the first time it ran.

### Observability and FinOps

A tab that answers the four questions a client asks after the pilot: which of the 35
agents do we actually use, what is the fleet doing and where does it stop, where does
the money go, and who is using this.

Portfolio is measured as **coverage, not volume** — an estate running one agent four
hundred times has a problem that a run count hides, so the tab reports agents exercised
per domain and per tier, names every agent never run, and shows what share of activity
sits on the single busiest one. Per-agent usage gives runs, outcome mix, artifacts,
spend, p50/p95 duration and distinct operators for all 35. Guardrail outcomes show
which gate refuses work most often — a high hard-dependency block rate means the fleet
is being driven out of order. Adoption reports operator breadth across the fleet and
whether people came back after their first run.

Everything is counted from the run journal. Two figures are not measurements — the
30-day projection and the modelled list-price cost — and both say so wherever they
appear. The modelled figure exists because an offline run bills nothing, and "what
would this activity have cost" is exactly the question at that point.

Operator identity is self-declared: there is no authentication, and the tab states that
where it counts people rather than implying a verified identity.

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
| Determinism where possible | `runtime/deterministic/profiler.py` computes every statistic from tables, and `runtime/deterministic/artifacts.py` does the same for files — SQL object references, copybook field layouts, CSV column totals. The model receives them as facts and is instructed never to recompute a number |
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
│   ├── documents/   SharePoint, Teams, shared drives, S3, uploads
│   ├── llm/         Anthropic provider + offline simulation provider
│   └── storage/     Filesystem artifacts, JSON repositories
├── runtime/
│   ├── deterministic/profiler.py   Every number an agent reports about a table
│   ├── deterministic/artifacts.py  Every number it reports about a file
│   ├── input_contracts.py          What each of the 35 agents asks you for
│   ├── canvas/                     A worked example per agent, one story
│   ├── prompt.py                   SKILL.md verbatim + task brief + output schema
│   └── artifact_plans.py           Per-agent file contracts and parameters
├── services/      Catalog, graph, models, runs, academy, observability, canvas
└── api/           FastAPI routers; deps.py is the composition root
```

**The fleet is not hardcoded.** `CatalogService` reads `ade-agent-specs/registry.yaml`
and each agent's `spec.yaml` and `SKILL.md` at load time. Adding an agent means adding a
spec folder — the workbench, graph, academy and run engine pick it up with no code
change. An agent with no curated artifact plan falls back to one derived from its declared
outputs, so a new spec is runnable immediately.

## Tests

```bash
backend/.venv/bin/python -m pytest backend        # 444 tests
node frontend/scripts/e2e-smoke.mjs               # drives a real run through the UI
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
