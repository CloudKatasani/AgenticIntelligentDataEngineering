# Running ADE Studio locally

Everything below was run from a clean clone on the way to writing it. Timings
are what it actually took; nothing here is aspirational.

You need **Python 3.11+** and **Node 20+**. You do not need a database, an API
key, or an AWS account — the app ships a seeded demo warehouse and an offline
execution mode, so a fresh clone runs an agent immediately.

## Install and run

```bash
git clone https://github.com/CloudKatasani/AgenticIntelligentDataEngineering
cd AgenticIntelligentDataEngineering/ade-studio

# Backend — about 25 seconds
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[dev]"

# Frontend — about 15 seconds. Built once; the backend then serves it.
npm --prefix frontend install
npm --prefix frontend run build

# Run
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
```

Open **<http://127.0.0.1:8000>**.

First boot seeds a ~30k-row DuckDB warehouse into
`backend/.ade-studio-data/`, which takes about a second and a half. It happens
at startup rather than on first request, so the first page load isn't the one
that pays for it.

Confirm it came up healthy:

```bash
curl -s http://127.0.0.1:8000/api/health
```

```json
{
  "status": "ok",
  "agents_loaded": 35,
  "graph_acyclic": true,
  "provider": { "provider": "simulation", "live": false }
}
```

`agents_loaded: 35` means the catalog under `ade-agent-specs/` parsed. If that
number is wrong, the specs are the thing to look at, not the app.

`provider: simulation` is expected with no API key — see
[Connecting a real model](#connecting-a-real-model).

## Your first run

**Agent fleet → 01 Source Profiling Agent.** Agent 01 has no hard
dependencies, so it is the one that runs from a clean install.

1. Source `ADE Demo Warehouse` → database `ADE_DEMO` → schema `RETAIL` → check
   `CUSTOMERS`.
2. Leave the model on its recommendation. Agent 01's numbers are computed
   rather than generated, so it recommends a fast model and tells you why.
3. Run.

You get three artifacts — `profile.json`, `inferred-constraints.yaml`,
`profiling-run-report.md` — each viewable inline, downloadable on its own, or
as a zip with a `MANIFEST.json` carrying full provenance.

The demo data has real defects in it, so the profile has real findings. On
`RETAIL.CUSTOMERS` you should see `email` at a 4% null ratio flagged for
completeness, a second finding on malformed addresses, `phone` split across
three formatting conventions, and `national_id` flagged as PII-shaped.

## A ten-minute demo

This is the sequence worth walking a client through, because each step shows a
guardrail rather than just another output. It is a verified path — the gate
messages quoted below are what the app actually says.

**1. Run agent 01 on `RETAIL.CUSTOMERS`.** Artifacts, downloads, real numbers.

**2. Try agent 07 (SchemaBuilder) next, and watch it refuse.**

> No completed run found for required upstream agent(s): 08 Data Modeling
> Agent; 02 Data Classification Agent. Run them first, or override with a
> recorded reason.

The gates are evaluated and shown *before* anything executes, alongside a cost
estimate. Nothing has been spent at this point.

**3. Run agent 02 (Data Classification).** It succeeds — and lands in
`awaiting_approval`, not `succeeded`. Agent 02 is autonomy tier L1, so its
output is a *proposal* until a human accepts it. Same for agent 05.

**4. Approve both from the run page.** The approval is recorded with an actor
and a note, and it goes into the artifact manifest.

**5. Go back to agent 08.** Its dependency gate is now green.

The point to make out loud: an unapproved upstream run does **not** satisfy a
downstream dependency. Approving 05 is what unblocks 08. That is the autonomy
tier and the dependency graph enforcing each other, and it is structural — no
prompt asks the model to behave this way.

**6. Open the Academy tab.** Every lesson is generated from that agent's own
`spec.yaml` and `SKILL.md`, so the training material cannot drift from the
contract the runtime enforces.

Two more moments if you have time: **agent 33** blocks on a missing required
parameter (`Fleet goal`) rather than guessing one, and **agent 20** refuses to
execute against production at all — its remediation output is always a
reviewable plan.

## What's in the demo warehouse

`ADE_DEMO`, three schemas, deliberately imperfect:

| Schema | Tables |
|---|---|
| `RETAIL` | `CUSTOMERS` (2,000), `ORDERS` (8,000), `ORDER_ITEMS` (19,963), `PAYMENTS` (7,800), `PRODUCTS` (300) |
| `FINANCE` | `GL_TRANSACTIONS` (5,000), `EXCHANGE_RATES` (400), `ACCOUNTS` (120) |
| `LEGACY` | `CUST_MAST` (2,100) |

`RETAIL.CUSTOMERS` carries missing and malformed emails, phone-format drift,
and PII-shaped columns. `LEGACY.CUST_MAST` is a mainframe-style extract —
cryptic column names, packed fields, and 100 duplicated customer numbers in
2,100 rows, because the legacy file has no enforced key. That is the table to
use when demonstrating the modernization and glossary agents.

## Connecting a real model

```bash
export ADE_ANTHROPIC_API_KEY=sk-ant-...
# restart the server
```

`/api/health` will then report `"live": true`.

Without a key the app runs in **offline simulation mode**. This is worth being
precise about, because it is the difference between a demo that is honest and
one that isn't: the profiler still computes every statistic from your real
data, and only the narrative around those numbers is templated. Every run and
every artifact produced this way is labelled `simulation`, so it cannot be
mistaken for model output.

## Connecting a real database

Drivers are optional extras. The app runs with none installed and reports each
source's driver status rather than failing at run time.

```bash
backend/.venv/bin/pip install -e "backend[snowflake,oracle,postgres]"
```

Available extras: `snowflake`, `oracle`, `postgres`, `mysql`, `mssql`,
`bigquery`, `databricks`.

Add the source under **Sources**, hit **Test**, and it appears in the object
picker. The picker, profiler and run engine work identically across every
dialect, including flat files (CSV/Parquet/JSON).

Use a **read-only database user**. The app enforces this itself —
`assert_read_only()` inspects every statement the connectors issue and rejects
anything that could mutate a source — but the grant should agree with the
guarantee.

## Frontend development

For hot reload, run the backend and the Vite dev server side by side:

```bash
# Terminal 1 — backend on 8000
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000 --reload

# Terminal 2 — Vite on 5173, proxying /api to 8000
npm --prefix frontend run dev
```

Use <http://127.0.0.1:5173>. The proxy target is hardcoded to port 8000 in
`frontend/vite.config.ts`, so if you moved the backend, move it there too.

You do not need `npm run build` while developing — that step exists so the
backend can serve the built bundle from one process in a demo.

## Tests

```bash
cd ade-studio
backend/.venv/bin/python -m pytest backend        # 70 tests, ~12s
```

The suite asserts the invariants the product rests on rather than the shape of
its code: all 35 agents load, every dependency and non-goal resolves to a real
agent, the hard-dependency graph is acyclic, seams are reciprocal, the
profiler's numbers match what lands in the artifacts, hard dependencies block,
advisory tiers produce proposals, regulated sources cap the tier, and agent 20
refuses production.

There is also a browser end-to-end check that drives a real run through the UI
and confirms the artifacts download. It needs a Chromium binary:

```bash
npx --prefix frontend playwright install chromium
node frontend/scripts/e2e-smoke.mjs
```

It targets `http://127.0.0.1:8000` by default; set `ADE_BASE_URL` to point it
elsewhere, and `PLAYWRIGHT_CHROMIUM_PATH` if you already have a browser you'd
rather it used.

## Where state lives, and how to reset it

Everything the app writes goes to one directory:

```
ade-studio/backend/.ade-studio-data/
├── artifacts/              every run's output files
├── connections.json        saved sources (secrets masked on read)
├── runs.json               the run journal
└── demo_warehouse.duckdb   the seeded demo data
```

To start completely fresh — new run history, new demo data:

```bash
rm -rf ade-studio/backend/.ade-studio-data
```

The next start re-seeds it. Nothing outside that directory is touched, and the
directory is git-ignored.

## Configuration

All settings are environment variables prefixed `ADE_`.

| Variable | Default | Purpose |
|---|---|---|
| `ADE_ANTHROPIC_API_KEY` | unset | Enables live model runs |
| `ADE_DEFAULT_MODEL_ID` | `claude-opus-5` | Fallback model |
| `ADE_SPECS_ROOT` | auto-discovered | Path to `ade-agent-specs` |
| `ADE_DATA_ROOT` | `backend/.ade-studio-data` | Where the state above lives |
| `ADE_DEFAULT_COST_CAP_USD` | `5.0` | Per-run spend cap |
| `ADE_MAX_OBJECTS_PER_RUN` | `25` | Objects per run |
| `ADE_MAX_SAMPLE_ROWS` | `500` | Upper bound on profiling sample size |

They can also go in a `.env` file next to where you start the server.

## Troubleshooting

**The UI is blank, or every route 404s.** The built frontend isn't there. Run
`npm --prefix frontend run build` — the backend serves `frontend/dist/` and
silently skips mounting it when the directory is missing, so the API keeps
working while the UI doesn't.

**`agents_loaded` is 0, or the app won't start.** It couldn't find
`ade-agent-specs/`. The app locates it by walking up from its own file, so this
means the directory was moved or the clone is partial. Set `ADE_SPECS_ROOT` to
an absolute path.

**Port 8000 is taken.** Pass `--port 8010`. If you're also using the Vite dev
server, update the proxy target in `frontend/vite.config.ts` to match.

**Every agent I try says it's blocked.** Working as intended — most agents
have hard dependencies. Start with **01**, which has none, and follow the
chain the run page names. Agents 33–35 are estate-scoped and need no object
selection at all, but do need their parameters.

**A run finished as `awaiting_approval` and I expected `succeeded`.** Also
working as intended: L0 and L1 agents produce proposals until a human accepts
them. Approve it on the run page.

**Runs feel slow.** They're synchronous — a run holds its HTTP request. That's
fine for the object counts the gates allow. A production deployment would move
execution onto a queue; the ports are in place for it, so that change touches
no service code.

## Running it on AWS

This document covers local only. For a deployable AWS stack — ECS Fargate
behind an ALB, S3 for artifacts, DynamoDB for state, Secrets Manager for
credentials, and Claude through Amazon Bedrock — see the AWS build:
**<https://github.com/CloudKatasani/AgenticIntelligentDataEngineering-AWS>**.
