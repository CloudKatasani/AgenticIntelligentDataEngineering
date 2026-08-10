"""Per-agent artifact contracts and run parameters.

Each agent's ``outputs`` in spec.yaml describes *what* it produces in prose.
This module turns that prose into a concrete file contract — a filename, a
format, and whether the content is computed or reasoned — so every run yields
downloadable deliverables instead of a wall of chat text.

Agents not listed here fall back to :func:`derive_plan`, which builds a plan
from the spec's ``outputs``. That keeps the catalog authoritative: a new agent
folder works without touching this file.
"""

from __future__ import annotations

import re

from app.domain.agent import (
    AgentParameter,
    ArtifactFormat,
    ArtifactSource,
    ArtifactSpec,
    ParameterType,
)

F = ArtifactFormat
S = ArtifactSource


def _a(
    key: str,
    filename: str,
    title: str,
    description: str,
    fmt: ArtifactFormat,
    source: ArtifactSource = S.REASONED,
) -> ArtifactSpec:
    return ArtifactSpec(
        key=key, filename=filename, title=title, description=description, format=fmt, source=source
    )


ARTIFACT_PLANS: dict[str, list[ArtifactSpec]] = {
    "01": [
        _a("profile", "profile.json", "Statistical profile",
           "Per-column statistics computed deterministically from the sampled rows.",
           F.JSON, S.DETERMINISTIC),
        _a("constraints", "inferred-constraints.yaml", "Inferred constraint set",
           "Candidate primary keys, foreign keys and not-null candidates, each with a confidence score and its evidence.",
           F.YAML),
        _a("report", "profiling-run-report.md", "Profiling run report",
           "Coverage, skipped objects with reasons, and interpretation of anomalous distributions.",
           F.MARKDOWN),
    ],
    "02": [
        _a("classification", "classification.json", "Column classification",
           "Sensitivity and compliance labels per column with confidence and the evidence behind each label.",
           F.JSON),
        _a("register", "sensitive-data-register.md", "Sensitive data register",
           "Operator-readable register of every column carrying a regulated classification.",
           F.MARKDOWN),
    ],
    "03": [
        _a("catalog", "catalog-entries.json", "Catalog entries",
           "Structured table and column descriptions ready to load into the catalog.",
           F.JSON),
        _a("documentation", "data-dictionary.md", "Data dictionary",
           "Human-readable dictionary with business descriptions and usage notes.",
           F.MARKDOWN),
    ],
    "04": [
        _a("lineage", "lineage-graph.json", "Lineage graph",
           "Node and edge list of reconstructed lineage with a confidence per edge.",
           F.JSON),
        _a("report", "lineage-report.md", "Lineage reconstruction report",
           "How lineage was derived, what remains unresolved, and where evidence is weak.",
           F.MARKDOWN),
    ],
    "05": [
        _a("glossary", "glossary-terms.yaml", "Glossary terms",
           "Business terms with definitions, owners and synonyms.", F.YAML),
        _a("bindings", "term-bindings.json", "Term-to-column bindings",
           "Which physical columns each business term binds to, with confidence.", F.JSON),
    ],
    "06": [
        _a("dossier", "source-system-dossier.md", "Source system dossier",
           "Extracted operational behaviour, edge cases and undocumented rules of the source system.",
           F.MARKDOWN),
        _a("rules", "extracted-rules.json", "Extracted business rules",
           "Structured rules recovered from the source, each tagged PARSED or INFERRED.", F.JSON),
    ],
    "07": [
        _a("ddl", "schema.sql", "Physical schema DDL",
           "Target DDL with types, keys, constraints and comments.", F.SQL),
        _a("contract", "schema-contract.yaml", "Schema contract",
           "Machine-readable description of the schema for downstream contract checks.", F.YAML),
        _a("notes", "migration-notes.md", "Migration notes",
           "Type decisions, nullability calls and anything requiring review before deployment.",
           F.MARKDOWN),
    ],
    "08": [
        _a("design", "model-design.md", "Model design",
           "Proposed entities, grain, relationships and the reasoning behind each modelling decision.",
           F.MARKDOWN),
        _a("entities", "entity-model.yaml", "Entity model",
           "Machine-readable entity, attribute and relationship definitions.", F.YAML),
    ],
    "09": [
        _a("mapping", "mapping-spec.yaml", "Source-to-target mapping",
           "Column-level mapping with transformation expressions and a confidence per mapping.",
           F.YAML),
        _a("matrix", "mapping-coverage.csv", "Mapping coverage matrix",
           "Every target column with its source, transformation and coverage status.", F.CSV),
        _a("notes", "mapping-notes.md", "Mapping notes",
           "Ambiguous mappings, assumptions taken, and the open questions a human must close.",
           F.MARKDOWN),
    ],
    "10": [
        _a("pipeline", "pipeline.sql", "Pipeline code",
           "Executable transformation implementing the approved mapping.", F.SQL),
        _a("notes", "implementation-notes.md", "Implementation notes",
           "Design choices, idempotency strategy and operational caveats.", F.MARKDOWN),
    ],
    "11": [
        _a("tests", "tests.yaml", "Generated test suite",
           "CI assertions derived from the mapping and profile, each tied to what it protects.",
           F.YAML),
        _a("plan", "test-plan.md", "Test plan",
           "What is covered, what is deliberately not covered, and why.", F.MARKDOWN),
    ],
    "12": [
        _a("semantic", "semantic-model.yaml", "Semantic model",
           "Metrics, dimensions and joins defined over the physical model.", F.YAML),
        _a("metrics", "metric-definitions.md", "Metric definitions",
           "Each metric in business language with its exact calculation and grain.", F.MARKDOWN),
    ],
    "13": [
        _a("contract", "data-contract.yaml", "Data contract",
           "Schema, quality commitments, freshness SLOs and breaking-change policy.", F.YAML),
        _a("changelog", "contract-changelog.md", "Contract changelog",
           "What this version commits to and how it differs from the prior version.", F.MARKDOWN),
    ],
    "14": [
        _a("translated", "translated-logic.sql", "Translated logic",
           "Legacy logic expressed in the target platform's dialect.", F.SQL),
        _a("report", "modernization-report.md", "Modernization report",
           "Behavioural equivalences, deliberate deviations, and logic that could not be translated.",
           F.MARKDOWN),
    ],
    "15": [
        _a("design", "ingestion-design.yaml", "Ingestion design",
           "Load pattern, cadence, watermarking and change-detection strategy per object.", F.YAML),
        _a("rationale", "pattern-rationale.md", "Pattern rationale",
           "Why this pattern fits the source's volumetrics and change characteristics.", F.MARKDOWN),
    ],
    "16": [
        _a("rules", "quality-rules.yaml", "Data quality rules",
           "Production rules with thresholds and severities, each justified by a profiled statistic.",
           F.YAML),
        _a("thresholds", "thresholds.json", "Threshold derivation",
           "The statistic behind every threshold, so a reviewer can audit the number.", F.JSON),
        _a("rationale", "rule-rationale.md", "Rule rationale",
           "Why each rule exists and what failure it is designed to catch.", F.MARKDOWN),
    ],
    "17": [
        _a("baselines", "baselines.json", "Freshness and volume baselines",
           "Learned baselines per object, computed from observed history.", F.JSON, S.DETERMINISTIC),
        _a("monitors", "monitor-config.yaml", "Monitor configuration",
           "Anomaly and freshness monitors with sensitivity settings.", F.YAML),
    ],
    "18": [
        _a("plan", "reconciliation-plan.yaml", "Reconciliation plan",
           "Which measures are compared between systems, at what grain and tolerance.", F.YAML),
        _a("report", "parity-report.md", "Parity report",
           "Where the two systems agree, where they diverge, and the size of each break.",
           F.MARKDOWN),
    ],
    "19": [
        _a("rca", "root-cause-analysis.md", "Root cause analysis",
           "Chain of evidence from symptom to cause, with confidence and what was ruled out.",
           F.MARKDOWN),
        _a("evidence", "evidence-chain.json", "Evidence chain",
           "Structured evidence supporting the diagnosis, for the remediation agent to consume.",
           F.JSON),
    ],
    "20": [
        _a("actions", "remediation-plan.yaml", "Remediation plan",
           "Proposed actions drawn strictly from the versioned action catalog, with rollback for each.",
           F.YAML),
        _a("record", "remediation-record.md", "Remediation record",
           "What would change, its blast radius, and the approval this plan requires.", F.MARKDOWN),
    ],
    "21": [
        _a("drift", "drift-report.md", "Schema drift report",
           "Detected drift against the contracted schema and its downstream impact.", F.MARKDOWN),
        _a("impact", "impact-matrix.json", "Impact matrix",
           "Every downstream consumer affected by each drift event.", F.JSON),
    ],
    "22": [
        _a("analysis", "cost-analysis.md", "Cost analysis",
           "Where spend concentrates and what is driving it.", F.MARKDOWN),
        _a("opportunities", "savings-opportunities.json", "Savings opportunities",
           "Ranked opportunities with estimated saving and implementation risk.", F.JSON),
    ],
    "23": [
        _a("plan", "tuning-plan.md", "Performance tuning plan",
           "Prioritised latency interventions with expected effect and measurement method.",
           F.MARKDOWN),
        _a("changes", "recommended-changes.sql", "Recommended changes",
           "Clustering, partitioning and query rewrites, ready for review.", F.SQL),
    ],
    "24": [
        _a("plan", "orchestration-plan.yaml", "Orchestration plan",
           "Task graph, dependencies, schedules and backfill windows.", F.YAML),
        _a("runbook", "backfill-runbook.md", "Backfill runbook",
           "Ordered steps, checkpoints and abort criteria for the backfill.", F.MARKDOWN),
    ],
    "25": [
        _a("forecast", "capacity-forecast.json", "Capacity forecast",
           "Projected storage and compute growth per object.", F.JSON),
        _a("plan", "retention-plan.md", "Retention plan",
           "Proposed tiering and retention, cross-checked against privacy requirements.", F.MARKDOWN),
    ],
    "26": [
        _a("model", "access-model.yaml", "Access model",
           "Roles, grants and masking policies derived from the classification.", F.YAML),
        _a("review", "entitlement-review.md", "Entitlement review",
           "Who can see what today, what should change, and the risk of each gap.", F.MARKDOWN),
    ],
    "27": [
        _a("assessment", "privacy-assessment.md", "Privacy assessment",
           "Processing purposes, lawful basis and subject-rights exposure per classified column.",
           F.MARKDOWN),
        _a("policy", "retention-policy.yaml", "Retention and erasure policy",
           "Retention periods and erasure procedures per data category.", F.YAML),
    ],
    "28": [
        _a("pack", "evidence-pack.md", "Regulatory evidence pack",
           "Narrative evidence assembled from upstream agent records, with citations to each source artifact.",
           F.MARKDOWN),
        _a("controls", "control-mapping.json", "Control mapping",
           "Each control mapped to the evidence that satisfies it.", F.JSON),
    ],
    "29": [
        _a("manifest", "data-product-manifest.yaml", "Data product manifest",
           "Product definition, owner, contract reference, SLOs and consumer-facing description.",
           F.YAML),
        _a("readiness", "publication-readiness.md", "Publication readiness",
           "Which publication gates pass, which fail, and what must close before release.",
           F.MARKDOWN),
    ],
    "30": [
        _a("report", "rationalization-report.md", "BI rationalization report",
           "Duplicate, unused and conflicting reports, with a consolidation recommendation.",
           F.MARKDOWN),
        _a("inventory", "dashboard-inventory.csv", "Dashboard inventory",
           "Every asset with usage, owner, and its rationalization disposition.", F.CSV),
    ],
    "31": [
        _a("query", "generated-query.sql", "Generated query",
           "SQL answering the natural-language question, written against the semantic layer.", F.SQL),
        _a("explanation", "query-explanation.md", "Query explanation",
           "What the query does in business language, its assumptions, and its limits.", F.MARKDOWN),
    ],
    "32": [
        _a("ticket", "intake-ticket.yaml", "Structured intake ticket",
           "The request captured as a structured, routable ticket.", F.YAML),
        _a("triage", "triage-note.md", "Triage note",
           "Whether this is already served by an existing product, and where it should route.",
           F.MARKDOWN),
    ],
    "33": [
        _a("plan", "orchestration-plan.yaml", "Fleet orchestration plan",
           "Which agents run, in what order, with the handoff contract between each.", F.YAML),
        _a("routing", "routing-decision.md", "Routing decision",
           "Why this decomposition, and which agents were deliberately not invoked.", F.MARKDOWN),
    ],
    "34": [
        _a("scorecard", "evaluation-scorecard.json", "Evaluation scorecard",
           "Measured scores against the target agent's declared evaluation thresholds.", F.JSON),
        _a("report", "evaluation-report.md", "Evaluation report",
           "What was measured, against which golden set, and whether the tier is justified.",
           F.MARKDOWN),
    ],
    "35": [
        _a("findings", "review-findings.md", "Review findings",
           "Critique of the artifact under review, ordered by severity.", F.MARKDOWN),
        _a("verdict", "review-verdict.json", "Review verdict",
           "Structured accept / revise / reject verdict with per-criterion reasoning.", F.JSON),
    ],
}


# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #

_BASE_PARAMETERS: list[AgentParameter] = [
    AgentParameter(
        key="sample_rows",
        label="Sample rows per object",
        type=ParameterType.INTEGER,
        description="How many rows to sample when computing deterministic statistics.",
        default=200,
    ),
    AgentParameter(
        key="depth",
        label="Analysis depth",
        type=ParameterType.ENUM,
        description="Trades thoroughness against cost and latency.",
        default="standard",
        options=["quick", "standard", "exhaustive"],
    ),
]

_AGENT_PARAMETERS: dict[str, list[AgentParameter]] = {
    "02": [
        AgentParameter(
            key="regulations",
            label="Regulations in scope",
            type=ParameterType.STRING,
            description="Comma-separated frameworks to classify against, e.g. GDPR, HIPAA, PCI-DSS.",
            default="GDPR, PCI-DSS",
        )
    ],
    "07": [
        AgentParameter(
            key="target_platform",
            label="Target platform",
            type=ParameterType.ENUM,
            default="snowflake",
            options=["snowflake", "databricks", "bigquery", "postgres", "oracle", "redshift"],
            description="Dialect the emitted DDL targets.",
        )
    ],
    "08": [
        AgentParameter(
            key="modeling_style",
            label="Modeling style",
            type=ParameterType.ENUM,
            default="dimensional",
            options=["dimensional", "data_vault", "third_normal_form", "one_big_table"],
            description="Modelling paradigm for the proposed design.",
        )
    ],
    "10": [
        AgentParameter(
            key="language",
            label="Implementation language",
            type=ParameterType.ENUM,
            default="sql",
            options=["sql", "dbt", "pyspark", "python"],
            description="What the coding agent emits.",
        ),
        AgentParameter(
            key="load_strategy",
            label="Load strategy",
            type=ParameterType.ENUM,
            default="incremental",
            options=["full_refresh", "incremental", "scd_type_2"],
            description="How the pipeline writes to the target.",
        ),
    ],
    "11": [
        AgentParameter(
            key="test_framework",
            label="Test framework",
            type=ParameterType.ENUM,
            default="dbt",
            options=["dbt", "great_expectations", "soda", "pytest"],
            description="Framework the generated assertions target.",
        )
    ],
    "14": [
        AgentParameter(
            key="source_dialect",
            label="Legacy dialect",
            type=ParameterType.ENUM,
            default="informatica",
            options=["informatica", "datastage", "ssis", "cobol", "teradata_bteq", "oracle_plsql"],
            description="Legacy technology being modernized.",
        )
    ],
    "16": [
        AgentParameter(
            key="severity_floor",
            label="Minimum severity to emit",
            type=ParameterType.ENUM,
            default="warn",
            options=["info", "warn", "error"],
            description="Rules below this severity are omitted from the ruleset.",
        )
    ],
    "20": [
        AgentParameter(
            key="allow_production_actions",
            label="Allow production actions",
            type=ParameterType.BOOLEAN,
            default=False,
            description="Agent 20 is the only agent permitted to mutate production data, and only from the versioned action catalog. Off by default.",
        )
    ],
    "27": [
        AgentParameter(
            key="jurisdictions",
            label="Jurisdictions",
            type=ParameterType.STRING,
            default="EU, US-CA",
            description="Comma-separated jurisdictions whose privacy regimes apply.",
        )
    ],
    "31": [
        AgentParameter(
            key="question",
            label="Business question",
            type=ParameterType.TEXT,
            description="The natural-language question to translate into SQL.",
            required=True,
        )
    ],
    "32": [
        AgentParameter(
            key="request_text",
            label="Incoming request",
            type=ParameterType.TEXT,
            description="The raw request to structure and triage.",
            required=True,
        )
    ],
    "33": [
        AgentParameter(
            key="goal",
            label="Fleet goal",
            type=ParameterType.TEXT,
            description="The outcome to decompose across the fleet.",
            required=True,
        )
    ],
    "34": [
        AgentParameter(
            key="target_agent_id",
            label="Agent under evaluation",
            type=ParameterType.STRING,
            description="Two-digit id of the agent being measured, e.g. 16.",
            required=True,
        )
    ],
    "35": [
        AgentParameter(
            key="artifact_under_review",
            label="Artifact under review",
            type=ParameterType.TEXT,
            description="Paste the artifact content, or reference a prior run id.",
            required=True,
        )
    ],
}

# Agents that reason over the estate, telemetry or another agent's output rather
# than over a table selection. The workbench does not force object selection for
# these, though a dataset may still be supplied for context.
_ESTATE_SCOPED = {"22", "24", "25", "28", "30", "32", "33", "34", "35"}

# Design rule 3: capped at L1 in regulated environments regardless of measured
# accuracy.
REGULATED_TIER_CAP = {"02", "26", "27"}


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48] or "output"


def derive_plan(agent_id: str, outputs: list[str]) -> list[ArtifactSpec]:
    """Fallback contract for an agent with no curated plan.

    Builds one artifact per declared output so a newly added spec folder is
    immediately runnable.
    """
    plan: list[ArtifactSpec] = []
    for index, output in enumerate(outputs[:4], start=1):
        slug = _slugify(output.split("(")[0])
        fmt = F.JSON if slug.endswith("json") else F.MARKDOWN
        plan.append(
            _a(
                key=f"output_{index}",
                filename=f"{slug}.{'json' if fmt is F.JSON else 'md'}",
                title=output[:80],
                description=output,
                fmt=fmt,
            )
        )
    if not plan:
        plan.append(
            _a("report", "agent-report.md", "Agent report",
               "Findings and recommendations from this run.", F.MARKDOWN)
        )
    return plan


def plan_for(agent_id: str, outputs: list[str]) -> list[ArtifactSpec]:
    return ARTIFACT_PLANS.get(agent_id) or derive_plan(agent_id, outputs)


def parameters_for(agent_id: str) -> list[AgentParameter]:
    """Run knobs, minus anything the agent's input contract already asks for.

    Some agents declared a parameter for the same thing their input slot now
    covers — agent 33's fleet goal, agent 24's backfill request. Leaving both in
    place would show the operator two boxes for one answer and then block the
    run on the one they did not fill in.
    """
    from app.runtime.input_contracts import SUPERSEDED_PARAMETERS, slots_for

    owned = {slot.key for slot in slots_for(agent_id)} | SUPERSEDED_PARAMETERS.get(agent_id, set())
    return [
        parameter
        for parameter in _BASE_PARAMETERS + _AGENT_PARAMETERS.get(agent_id, [])
        if parameter.key not in owned
    ]


def requires_dataset(agent_id: str) -> bool:
    return agent_id not in _ESTATE_SCOPED
