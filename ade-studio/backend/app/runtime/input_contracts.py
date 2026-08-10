"""What each of the 35 agents asks the operator for.

Every slot below traces to a line in that agent's own ``spec.yaml`` under
``inputs``, quoted in ``spec_reference``. The specs already say what each agent
consumes; this table is the reading of them, not an invention on top.

The distinction that shapes the table: a spec's ``inputs`` list mixes two very
different things.

*Upstream artifacts* — "profile.json (01)", "Approved model spec (08)" — come
from the context layer, produced by a previous run. The operator never supplies
those; the hard-dependency gate already guarantees them, and asking for them
again would be asking a human to fetch something the system already holds.

*Primary inputs* — "Legacy artifact repository (copybooks, ETL XML)",
"Platform usage/metering views", "Goal statement + scope from a human owner" —
come from outside the fleet. Those are the slots.

An agent whose spec lists only upstream artifacts gets no slots at all, and the
workbench says so rather than presenting an empty table picker: agent 09 needs
the approved model spec and the profile, both of which arrive through the
dependency gate. Agent 11 is the same. That is not a gap in the UI — it is the
correct answer to "what do you need from me".
"""

from __future__ import annotations

from app.domain.input_contract import InputKind, InputOrigin, InputSlot

# Extensions offered per kind. Indicative rather than enforced — a client's
# metering export is a CSV until the day it is a JSON, and refusing it on the
# extension would be an obstacle rather than a guardrail.
CODE_EXTENSIONS = [
    ".sql", ".ddl", ".hql", ".py", ".scala", ".java", ".cbl", ".cob", ".cpy",
    ".xml", ".json", ".yaml", ".yml", ".dtsx", ".ktr", ".kjb", ".sas", ".prc",
    ".jcl", ".txt", ".md",
]
TELEMETRY_EXTENSIONS = [".csv", ".tsv", ".json", ".jsonl", ".parquet", ".log", ".txt", ".xlsx"]
DOCUMENT_EXTENSIONS = [".pdf", ".docx", ".md", ".txt", ".csv", ".xlsx", ".json", ".yaml", ".yml"]


def _objects(
    *,
    key: str = "objects",
    label: str = "Database objects",
    required: bool = True,
    help: str,
    spec_reference: str,
) -> InputSlot:
    return InputSlot(
        key=key,
        label=label,
        kind=InputKind.DATABASE_OBJECTS,
        required=required,
        help=help,
        spec_reference=spec_reference,
    )


def _code(
    *, key: str, label: str, help: str, spec_reference: str, required: bool = True, max_files: int = 25
) -> InputSlot:
    return InputSlot(
        key=key,
        label=label,
        kind=InputKind.CODE_ARTIFACTS,
        required=required,
        help=help,
        spec_reference=spec_reference,
        accepts=CODE_EXTENSIONS,
        max_files=max_files,
    )


def _telemetry(
    *, key: str, label: str, help: str, spec_reference: str, required: bool = True
) -> InputSlot:
    return InputSlot(
        key=key,
        label=label,
        kind=InputKind.TELEMETRY_EXPORT,
        required=required,
        help=help,
        spec_reference=spec_reference,
        accepts=TELEMETRY_EXTENSIONS,
        max_files=10,
    )


def _document(
    *, key: str, label: str, help: str, spec_reference: str, required: bool = True
) -> InputSlot:
    return InputSlot(
        key=key,
        label=label,
        kind=InputKind.POLICY_DOCUMENT,
        required=required,
        help=help,
        spec_reference=spec_reference,
        accepts=DOCUMENT_EXTENSIONS,
        max_files=10,
    )


def _request(
    *, key: str, label: str, help: str, spec_reference: str, placeholder: str, required: bool = True
) -> InputSlot:
    return InputSlot(
        key=key,
        label=label,
        kind=InputKind.STRUCTURED_REQUEST,
        required=required,
        help=help,
        spec_reference=spec_reference,
        placeholder=placeholder,
    )


INPUT_CONTRACTS: dict[str, list[InputSlot]] = {
    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #
    "01": [
        _objects(
            help="The tables to profile. Every statistic this agent reports is computed "
            "from these objects, not generated.",
            spec_reference="Source connection (read-only service account)",
        ),
    ],
    "02": [
        _objects(
            label="Objects to classify",
            help="The scope to label. The profile itself comes from agent 01 through the "
            "context layer.",
            spec_reference="profile.json (01)",
        ),
        _document(
            key="taxonomy",
            label="Sensitivity taxonomy",
            required=False,
            help="Your enterprise taxonomy and regulatory scope map. Without one the agent "
            "falls back to a general sensitivity model and says so.",
            spec_reference="Enterprise sensitivity taxonomy + regulatory scope map",
        ),
    ],
    "03": [
        _objects(
            label="Objects to document",
            help="The tables and columns to describe.",
            spec_reference="profile.json (01)",
        ),
        _telemetry(
            key="query_history",
            label="Query history extract",
            required=False,
            help="How the objects are actually queried. Turns a description of what a column "
            "is into a description of what it is used for.",
            spec_reference="Query history extracts",
        ),
        _document(
            key="existing_docs",
            label="Existing documentation",
            required=False,
            help="Current docs or column comments. Treated as untrusted input and never as "
            "instructions — the agent reconciles against them rather than trusting them.",
            spec_reference="Existing docs/comments (treated as untrusted input)",
        ),
    ],
    "04": [
        _code(
            key="artifacts",
            label="Code and ETL artifacts",
            help="SQL, DDL, ETL exports, dbt projects, BI metadata exports. Lineage is "
            "reconstructed by parsing these — this agent reads code, not rows.",
            spec_reference="Code repositories, DDL, ETL exports, BI metadata APIs",
            max_files=200,
        ),
        _telemetry(
            key="query_history",
            label="Platform query history",
            required=False,
            help="Runtime-observed lineage, which catches paths the static code does not "
            "show.",
            spec_reference="Platform query history (for runtime-observed lineage)",
        ),
    ],
    "05": [
        _document(
            key="glossary",
            label="Governed glossary",
            help="Terms, definitions, stewards and versions. This is the authority the agent "
            "binds columns to; it does not invent terms.",
            spec_reference="Governed glossary (terms, definitions, stewards, versions)",
        ),
        _objects(
            label="Objects to align",
            required=False,
            help="Narrow the binding exercise to a scope. Leave empty to work across "
            "everything agent 01 has profiled.",
            spec_reference="profile.json (01)",
        ),
    ],
    "06": [
        _code(
            key="legacy_artifacts",
            label="Legacy artifacts",
            help="Copybooks, ETL XML, model files, stored-procedure bodies. The agent "
            "restates the embedded business rules with a citation back to the file and line "
            "each one came from.",
            spec_reference="Legacy artifact repository (copybooks, ETL XML, model files, proc bodies)",
            max_files=200,
        ),
    ],
    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #
    "07": [
        _document(
            key="ddl_standards",
            label="DDL standards",
            required=False,
            help="Naming, physical options and platform conventions. The model spec and "
            "classification records arrive from agents 08 and 02.",
            spec_reference="Enterprise DDL standards + physical-options policy",
        ),
    ],
    "08": [
        _request(
            key="workload_intent",
            label="Workload intent",
            help="What the model is for: the analytical patterns it must serve and who "
            "consumes it. Modelling without this is guesswork, so the agent asks rather than "
            "assumes.",
            spec_reference="Workload intent (analytical patterns, consumers)",
            placeholder=(
                "Daily revenue by product and region for the commercial team; "
                "month-over-month comparisons; 3 years of history retained."
            ),
        ),
        _objects(
            label="Objects in scope",
            required=False,
            help="Narrow the model to a subset. The profile itself comes from agent 01.",
            spec_reference="profile.json (01)",
        ),
    ],
    "09": [],  # Model spec (08), profile (01), rule inventory (06), lineage (04)
    "10": [
        _document(
            key="style_guide",
            label="House style guide",
            required=False,
            help="Repo conventions the generated code must follow.",
            spec_reference="House style guide + repo conventions",
        ),
        _code(
            key="repo_context",
            label="Existing repository code",
            required=False,
            help="Representative files from the target repo, so the output matches what is "
            "already there rather than a generic house style.",
            spec_reference="House style guide + repo conventions",
        ),
    ],
    "11": [],  # S2T spec (09), model spec (08), profile (01)
    "12": [
        _telemetry(
            key="measure_inventory",
            label="Existing BI measure inventory",
            required=False,
            help="Current measures and their definitions, so the semantic layer reconciles "
            "with what analysts already use instead of competing with it.",
            spec_reference="Existing BI measure inventory",
        ),
    ],
    "13": [
        _document(
            key="sla_statements",
            label="Owner SLAs and consumer registrations",
            help="What the producing team commits to and who depends on it. A contract "
            "without a stated commitment is documentation, not a contract.",
            spec_reference="Owner SLA statements / Consumer registrations",
        ),
    ],
    "14": [
        _code(
            key="legacy_artifacts",
            label="Legacy code to migrate",
            help="The source artifacts being modernised — COBOL, SAS, Informatica, SSIS, "
            "stored procedures. Anything that cannot be translated faithfully is recorded in "
            "a declared-delta register rather than silently changed.",
            spec_reference="Legacy artifacts + rule inventory slice (06)",
            max_files=200,
        ),
        _document(
            key="target_conventions",
            label="Target platform conventions",
            required=False,
            help="House style for the platform being migrated to.",
            spec_reference="Target platform conventions + house style",
        ),
    ],
    "15": [
        _objects(
            label="Objects to ingest",
            help="The source tables an ingestion pattern is being chosen for.",
            spec_reference="profile.json (01)",
        ),
        _document(
            key="interface_docs",
            label="Source interface documentation",
            required=False,
            help="How the source exposes data — APIs, extract schedules, CDC availability. "
            "Decides whether an incremental pattern is even possible.",
            spec_reference="Source interface documentation",
        ),
    ],
    # ------------------------------------------------------------------ #
    # Quality
    # ------------------------------------------------------------------ #
    "16": [
        _objects(
            label="Objects to write rules for",
            help="Thresholds are derived from the profiled distributions of these objects, "
            "not from generic defaults.",
            spec_reference="profile.json (01)",
        ),
    ],
    "17": [
        _telemetry(
            key="telemetry",
            label="Pipeline run telemetry",
            help="Row counts, arrival times and run outcomes over a history long enough to "
            "establish a baseline. Freshness cannot be judged from a snapshot.",
            spec_reference="Pipeline run telemetry, row counts, arrival times",
        ),
        _document(
            key="event_calendar",
            label="Event calendar",
            required=False,
            help="Maintenance windows and known bulk loads, so expected spikes are not "
            "reported as anomalies.",
            spec_reference="Event calendar (maintenance windows, known bulk loads)",
        ),
    ],
    "18": [
        _objects(
            key="source_objects",
            label="Source estate objects",
            help="The originating side of the comparison.",
            spec_reference="Read access to both estates",
        ),
        _objects(
            key="target_objects",
            label="Target estate objects",
            help="The migrated side. This agent is the only one that reads two estates at "
            "once — pick the same logical tables on each.",
            spec_reference="Read access to both estates",
        ),
        _document(
            key="tolerance_policy",
            label="Tolerance policy",
            required=False,
            help="What counts as an acceptable difference. Without it the agent reports "
            "exact-match parity only.",
            spec_reference="Tolerance policy",
        ),
    ],
    "19": [
        _request(
            key="incident",
            label="Incident summary",
            help="What broke, when it was noticed, and the blast radius as currently "
            "understood.",
            spec_reference="Incident with evidence bundle (17/21/16-fires/orchestrator failures)",
            placeholder=(
                "Nightly revenue load finished with 0 rows at 03:12 UTC. "
                "Finance dashboard is stale. Started after last night's release."
            ),
        ),
        _telemetry(
            key="evidence",
            label="Evidence bundle",
            help="Run logs, alert payloads, platform event feeds. The agent reasons over "
            "evidence and cites it; it does not speculate from the summary alone.",
            spec_reference="Git history, run logs, platform event feeds",
        ),
    ],
    "20": [
        _document(
            key="action_catalog",
            label="Approved action catalog",
            help="The versioned, human-approved set of actions this agent may propose. It "
            "will not invent an action outside the catalog, and it never executes against "
            "production regardless.",
            spec_reference="Action catalog (versioned, human-approved)",
        ),
    ],
    "21": [
        _telemetry(
            key="snapshots",
            label="Schema snapshots or change events",
            help="At least two points in time. Drift is a difference, so a single snapshot "
            "cannot show one.",
            spec_reference="Scheduled schema snapshots + platform change events",
        ),
    ],
    # ------------------------------------------------------------------ #
    # Operations
    # ------------------------------------------------------------------ #
    "22": [
        _telemetry(
            key="metering",
            label="Usage and metering export",
            help="Warehouse metering, credit consumption or billing export. Every figure "
            "this agent reports is computed from this file.",
            spec_reference="Platform usage/metering views",
        ),
        _document(
            key="tags_and_budgets",
            label="Tag taxonomy and budget targets",
            required=False,
            help="Ownership tags and finance-owned budgets, so spend is attributed to teams "
            "rather than to warehouses.",
            spec_reference="Tag taxonomy + ownership registry / Budget targets from finance owners",
        ),
    ],
    "23": [
        _telemetry(
            key="query_history",
            label="Query history and profiles",
            help="Execution history with timings. Tuning without measurements is guessing.",
            spec_reference="Query history + profiles",
        ),
        _code(
            key="dbt_artifacts",
            label="dbt run artifacts",
            required=False,
            help="manifest.json and run_results.json, which tie slow queries back to the "
            "models that issued them.",
            spec_reference="dbt run artifacts",
        ),
    ],
    "24": [
        _request(
            key="backfill_request",
            label="Backfill request",
            help="Scope, reason and requester. The plan is built around a stated intent and "
            "the agent will not infer one.",
            spec_reference="Backfill request (scope, reason, requester)",
            placeholder=(
                "Rebuild fct_orders for 2026-01-01 to 2026-03-31. "
                "Currency conversion was wrong before the 04-02 fix. Requested by finance-ops."
            ),
        ),
        _telemetry(
            key="orchestrator_state",
            label="Orchestrator state and calendar",
            required=False,
            help="Current DAG state, freezes and maintenance windows, so the plan schedules "
            "around them.",
            spec_reference="Orchestrator state + calendar (freezes, maintenance)",
        ),
    ],
    "25": [
        _telemetry(
            key="storage_metering",
            label="Storage metering and access history",
            help="Size over time and when each asset was last read. Archive candidates are "
            "identified from access, not from age alone.",
            spec_reference="Storage metering + access history",
        ),
        _document(
            key="retention_policy",
            label="Retention policy matrix",
            required=False,
            help="How long each data class must be kept. Regulatory retention comes from "
            "agent 27 when it has run.",
            spec_reference="Retention policy matrix",
        ),
    ],
    # ------------------------------------------------------------------ #
    # Governance
    # ------------------------------------------------------------------ #
    "26": [
        _document(
            key="entitlement_matrix",
            label="Role-entitlement matrix",
            help="Human-owned: which roles are entitled to what. The agent proposes grants "
            "against this matrix and never authors the matrix itself.",
            spec_reference="Role-entitlement matrix (human-owned)",
        ),
        _telemetry(
            key="current_grants",
            label="Current grants inventory",
            required=False,
            help="What is granted today, so the output is a diff rather than a fresh set.",
            spec_reference="Current grants inventory",
        ),
    ],
    "27": [
        _document(
            key="regulation_library",
            label="Regulatory requirement library",
            help="Counsel-owned requirements. The agent applies them; it does not interpret "
            "regulation on its own authority.",
            spec_reference="Regulatory requirement library (counsel-owned)",
        ),
        _document(
            key="legal_hold",
            label="Legal-hold register",
            required=False,
            help="Assets under hold, which override every retention recommendation.",
            spec_reference="Legal-hold register",
        ),
    ],
    "28": [
        _document(
            key="control_catalog",
            label="Control catalog and evidence templates",
            help="Compliance-owned framework controls and the shape each piece of evidence "
            "must take. The agent assembles the binder; the artifacts come from the context "
            "layer.",
            spec_reference="Framework control catalogs + evidence templates (compliance-owned)",
        ),
    ],
    "29": [
        _request(
            key="publication_request",
            label="Publication request",
            help="The asset being published and its accountable owner. Gate evidence is "
            "pulled from agents 13, 03, 16 and 12 rather than asked for here.",
            spec_reference="Publication request (asset, owner)",
            placeholder="Publish ANALYTICS.FCT_ORDERS as a certified data product. Owner: revenue-data-team.",
        ),
        _document(
            key="standards_checklist",
            label="Standards checklist",
            required=False,
            help="The versioned publication checklist to evaluate against.",
            spec_reference="Standards checklist (versioned)",
        ),
    ],
    # ------------------------------------------------------------------ #
    # Consumption
    # ------------------------------------------------------------------ #
    "30": [
        _telemetry(
            key="bi_inventory",
            label="BI estate inventory",
            help="Reports, dashboards and their metadata, exported from the BI platform. "
            "Duplicate-detection works over this inventory.",
            spec_reference="BI estate inventory + metadata",
        ),
        _telemetry(
            key="usage_telemetry",
            label="Usage telemetry",
            required=False,
            help="View counts and last-opened dates. Separates the unused from the merely "
            "similar.",
            spec_reference="Usage telemetry",
        ),
    ],
    "31": [
        _request(
            key="question",
            label="Analyst question",
            help="The business question in plain language. The agent answers only from "
            "certified assets and cites what it used.",
            spec_reference="User question + role context",
            placeholder="Which product categories grew fastest in EMEA last quarter?",
        ),
        _objects(
            label="Objects the analyst may use",
            required=False,
            help="Constrain the answer to a scope. Left empty, the agent works from the "
            "certified-asset registry.",
            spec_reference="Certified-asset registry (29)",
        ),
    ],
    "32": [
        _request(
            key="requests",
            label="Inbound requests",
            help="Tickets or chat threads to triage. The agent turns them into scoped "
            "stories and points at existing assets that already answer them.",
            spec_reference="Inbound requests (tickets, chat, 31 demand signals)",
            placeholder=(
                "DATA-1182: Sales want a churn dashboard by segment.\n"
                "DATA-1187: Finance need daily margin by SKU, ideally self-serve."
            ),
        ),
        _telemetry(
            key="ticket_export",
            label="Ticket export",
            required=False,
            help="A batch export instead of pasting them in.",
            spec_reference="Inbound requests (tickets, chat, 31 demand signals)",
        ),
    ],
    # ------------------------------------------------------------------ #
    # Cross-cutting — estate-scoped, no data objects
    # ------------------------------------------------------------------ #
    "33": [
        _request(
            key="goal",
            label="Fleet goal and scope",
            help="What the fleet should achieve, stated by a human owner. The supervisor "
            "plans a route through the dependency graph to reach it.",
            spec_reference="Goal statement + scope from a human owner",
            placeholder="Onboard the FINANCE schema end to end and get it certified for self-serve.",
        ),
    ],
    "34": [
        _request(
            key="evaluation_target",
            label="What to evaluate",
            help="The agent, version or promotion request under assessment.",
            spec_reference="Promotion requests (agent versions, tier changes)",
            placeholder="Assess agent 02 for promotion from L1 to L2 on non-regulated sources.",
        ),
        _telemetry(
            key="golden_sets",
            label="Golden datasets",
            required=False,
            help="Labelled examples with known answers. Without them the evaluation is "
            "qualitative and the agent says so.",
            spec_reference="Agent output samples + golden datasets per agent",
        ),
    ],
    "35": [
        _code(
            key="changed_artifacts",
            label="Artifacts under review",
            help="The changed files and the artifacts they touch — spec, model, contract, "
            "manifest. The reviewer checks them against each other, not just individually.",
            spec_reference="Flagged PR + linked artifacts (spec, model, contract, manifest)",
            max_files=100,
        ),
        _document(
            key="standards",
            label="Standards and policy documents",
            required=False,
            help="What the review is against. Without it the reviewer applies the fleet's "
            "own contracts only.",
            spec_reference="Standards and policy documents",
        ),
    ],
}


SUPERSEDED_PARAMETERS: dict[str, set[str]] = {
    "32": {"request_text"},
    "34": {"target_agent_id"},
    "35": {"artifact_under_review"},
}
"""Run parameters that an input slot now covers.

These agents once asked for their primary input as a free-text parameter,
because there was nowhere else to put it. The slot is the better home — agent
35 now receives the actual changed files rather than a sentence describing
them — so the parameter is retired rather than asked twice. Listed explicitly
because the keys do not match, and a silent overlap would show the operator two
boxes for one answer and then block on the empty one.
"""


def slots_for(agent_id: str) -> list[InputSlot]:
    """The input contract for one agent.

    An unknown agent — a spec added after this table was written — gets a
    permissive default rather than nothing, so a new agent folder is runnable
    the moment it is dropped in. It is deliberately loose: guessing a strict
    contract would block a working agent, while guessing a loose one only
    fails to guide.
    """
    if agent_id in INPUT_CONTRACTS:
        return list(INPUT_CONTRACTS[agent_id])
    return [
        _objects(
            required=False,
            help="This agent has no curated input contract yet, so the general object "
            "picker is offered.",
            spec_reference="derived default",
        ),
        _request(
            key="brief",
            label="Brief",
            required=False,
            help="Anything else this agent needs, in prose.",
            spec_reference="derived default",
            placeholder="",
        ),
    ]


def primary_kind(agent_id: str) -> str:
    """The headline input kind, for badges and filtering.

    An agent with no slots is upstream-fed: everything it needs arrives through
    the dependency gate.
    """
    slots = slots_for(agent_id)
    required = [s for s in slots if s.required]
    if not slots:
        return "upstream_artifacts"
    return (required or slots)[0].kind.value
