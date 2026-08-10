"""Chapter 5 — Governance. Prove it is controlled (agents 26–29)."""

from __future__ import annotations

from app.domain.canvas import Exhibit, ExampleArtifact, WorkedExample

CHAPTER = "5 · Governance — prove it is controlled"

_GRANTS = """grantee,grantee_type,privilege,object,object_type,granted_by,granted_at
FINANCE_ANALYST,ROLE,SELECT,ANALYTICS.FCT_ORDERS,TABLE,SECURITYADMIN,2025-02-11
FINANCE_ANALYST,ROLE,SELECT,ANALYTICS.CUSTOMER_360,VIEW,SECURITYADMIN,2025-02-11
MARKETING,ROLE,SELECT,ANALYTICS.CUSTOMER_360,VIEW,SECURITYADMIN,2025-06-03
CONTRACTOR_TEMP,ROLE,SELECT,ANALYTICS.CUSTOMER_360,VIEW,SECURITYADMIN,2024-08-19
CONTRACTOR_TEMP,ROLE,SELECT,LEGACY.CUST_MAST,TABLE,SECURITYADMIN,2024-08-19
DATA_PLATFORM,ROLE,OWNERSHIP,ANALYTICS,SCHEMA,ACCOUNTADMIN,2024-01-05
PUBLIC,ROLE,SELECT,ANALYTICS.CUSTOMER_360,VIEW,SECURITYADMIN,2026-01-22"""

EXAMPLES: list[WorkedExample] = [
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="26",
        chapter=CHAPTER,
        scenario=(
            "CUSTOMER_360 exposes an SSN-shaped column, and nobody has reviewed who can read "
            "it. The agent compares the live grants against Meridian's own entitlement matrix "
            "and finds a grant to PUBLIC."
        ),
        inputs=[
            Exhibit(
                label="policies/role-entitlement-matrix.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="5 roles · 3 standing rules",
                note="Human-owned. The agent proposes against this matrix; it never authors it.",
                body="""# Role-entitlement matrix (human-owned)

| Role | Permitted sensitivity | Notes |
|---|---|---|
| FINANCE_ANALYST | Up to CONFIDENTIAL | No RESTRICTED columns. |
| MARKETING | Up to INTERNAL | Aggregates only over customer data. |
| DATA_PLATFORM | All | Break-glass; every use logged and reviewed. |
| CONTRACTOR_TEMP | Up to INTERNAL | Time-boxed; must expire within 90 days. |
| PUBLIC | None | No grants to PUBLIC in any environment. |

## Standing rules
1. No role receives RESTRICTED access without a named data-protection approval.
2. Contractor roles are reviewed every 30 days and revoked on contract end.
3. Grants to PUBLIC are prohibited.""",
            ),
            Exhibit(
                label="telemetry/grants_inventory.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="7 grants · 5 roles",
                note="So the output is a diff against reality, not a fresh grant set.",
                body=_GRANTS,
            ),
        ],
        upstream=["classification.json — agent 02 (RESTRICTED columns)"],
        outputs=[
            ExampleArtifact(
                filename="access-model.yaml",
                title="Access model",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: AccessModel
metadata:
  scope: ANALYTICS
  matrix: Meridian role-entitlement matrix (human-owned)
  basis: grants_inventory.csv + classification.json (agent 02)

violations:
  - id: ACC-001
    severity: critical
    grant: "PUBLIC → SELECT on ANALYTICS.CUSTOMER_360"
    granted_at: 2026-01-22
    rule_broken: "Standing rule 3 — grants to PUBLIC are prohibited"
    exposure: >-
      CUSTOMER_360 projects national_id and email, both classified RESTRICTED
      by agent 02. PUBLIC means every role in the account, including future
      ones nobody has created yet.
    remediation: "REVOKE SELECT ON ANALYTICS.CUSTOMER_360 FROM ROLE PUBLIC;"
    proposed_not_executed: true

  - id: ACC-002
    severity: high
    grant: "CONTRACTOR_TEMP → SELECT on ANALYTICS.CUSTOMER_360 and LEGACY.CUST_MAST"
    granted_at: 2024-08-19
    rule_broken: "Standing rule 2 — contractor roles time-boxed to 90 days"
    detail: "Granted 692 days ago. The matrix permits INTERNAL only; both objects carry RESTRICTED columns."
    remediation: "REVOKE both grants. If access is still needed, re-grant with an expiry."
    proposed_not_executed: true

  - id: ACC-003
    severity: high
    grant: "MARKETING → SELECT on ANALYTICS.CUSTOMER_360"
    granted_at: 2025-06-03
    rule_broken: "Matrix — MARKETING is permitted aggregates only over customer data"
    detail: "The grant is row-level SELECT on a view exposing email and national_id."
    remediation: >-
      Replace with a grant on an aggregate view, or attach a masking policy so
      MARKETING sees masked values. Both options given; choosing is a human call.
    proposed_not_executed: true

compliant:
  - grant: "FINANCE_ANALYST → SELECT on ANALYTICS.FCT_ORDERS"
    note: "No RESTRICTED columns on that object. Within the matrix."
  - grant: "DATA_PLATFORM → OWNERSHIP on ANALYTICS"
    note: "Break-glass role, permitted all sensitivities. Use is logged and reviewed."

not_proposed:
  - description: "Revoking FINANCE_ANALYST's access to CUSTOMER_360."
    reason: >-
      The matrix permits up to CONFIDENTIAL, and CUSTOMER_360 carries RESTRICTED
      columns — so this looks like a violation. It is not resolvable from the
      matrix alone: standing rule 1 allows RESTRICTED access with a named
      data-protection approval, and whether one exists is not in the supplied
      inventory. Escalated rather than guessed.""",
            ),
            ExampleArtifact(
                filename="entitlement-review.md",
                title="Entitlement review",
                format="markdown",
                source="reasoned",
                body="""# Entitlement review — ANALYTICS

**Status: PROPOSAL.** Tier L1, and the source is marked regulated, so this
agent is capped at advisory regardless of measured accuracy. No grant has been
changed. Every statement below is a `REVOKE` someone else runs.

## The finding

**`PUBLIC` has SELECT on `ANALYTICS.CUSTOMER_360`, granted 22 January 2026.**

`CUSTOMER_360` projects `national_id` and `email` — both classified RESTRICTED
by agent 02. `PUBLIC` in Snowflake means every role in the account, including
roles that do not exist yet. Meridian's own matrix prohibits grants to `PUBLIC`
in any environment.

This has been live for roughly six months.

```sql
REVOKE SELECT ON ANALYTICS.CUSTOMER_360 FROM ROLE PUBLIC;
```

## The one that has been open for 692 days

`CONTRACTOR_TEMP` holds SELECT on `CUSTOMER_360` and `LEGACY.CUST_MAST`,
granted 19 August 2024. The matrix time-boxes contractor roles to 90 days and
requires revocation at contract end. Nobody revoked it.

## The one that is arguable

`MARKETING` has row-level SELECT on `CUSTOMER_360` where the matrix permits
aggregates only. Two remediations are offered — an aggregate view, or a masking
policy — because they have different operating costs and choosing between them
is a Meridian decision, not this agent's.

## What I escalated instead of deciding

`FINANCE_ANALYST` also reads `CUSTOMER_360`, which carries RESTRICTED columns,
while the matrix permits up to CONFIDENTIAL. That reads as a violation — **but
standing rule 1 permits RESTRICTED access with a named data-protection
approval**, and the supplied inventory does not say whether one exists.

Reporting it as a violation would be wrong if an approval exists. Ignoring it
would be wrong if one does not. It is escalated to Meridian Data Governance
with exactly that question.
""",
            ),
        ],
        highlights=[
            "The grant to PUBLIC has been live six months and is a two-line finding once the inventory meets the matrix.",
            "It offers two remediations for the arguable case rather than picking one on the client's behalf.",
            "It escalates the case it genuinely cannot resolve, stating precisely what evidence would settle it.",
            "Capped at L1 on a regulated source — proposals only, no matter how confident.",
        ],
        handoffs=[
            "The classification these labels come from → 02 Data Classification Agent",
            "Evidence for the access control in the audit binder → 28 Regulatory Evidence Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="27",
        chapter=CHAPTER,
        scenario=(
            "A GDPR erasure request arrives. Meridian cannot answer where that person's data "
            "lives. The agent traces personal data through lineage and produces a retention "
            "policy that respects the legal hold."
        ),
        inputs=[
            Exhibit(
                label="policies/regulatory-requirements.md",
                kind="policy_document",
                origin="Sample artifacts / policies (counsel-owned)",
                format="markdown",
                stat="counsel-owned requirements",
                note="The agent applies these; it does not interpret regulation on its own authority.",
                body="""# Regulatory requirement library (counsel-owned)

## GDPR
- Art.17 erasure: fulfil within 30 days of a verified request.
- Art.5(1)(e) storage limitation: personal data kept no longer than necessary.
- Derived and aggregated data containing personal data is in scope.

## SOX
- Financial transaction records: 7-year minimum retention.

## Conflict rule
Where a retention obligation conflicts with an erasure request, the retention
obligation prevails and the erasure is recorded as partially fulfilled with a
stated legal basis.""",
            ),
            Exhibit(
                label="policies/retention-and-legal-hold.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="1 active hold",
                body="""## Legal holds in force
- `LEGACY.CUST_MAST` — hold LH-2026-004, opened 2026-03-11, no deletion or
  archival permitted while open.""",
            ),
        ],
        upstream=["classification.json — agent 02", "lineage-graph.json — agent 04"],
        outputs=[
            ExampleArtifact(
                filename="privacy-assessment.md",
                title="Privacy assessment",
                format="markdown",
                source="reasoned",
                body="""# Privacy assessment — customer personal data

## Where personal data actually lives

Agent 02 classified four columns RESTRICTED in `RETAIL.CUSTOMERS`. Agent 04's
lineage shows where they propagate:

```
RETAIL.CUSTOMERS ──▶ ANALYTICS.DIM_CUSTOMER ──▶ ANALYTICS.CUSTOMER_360
       │                      ▲                          │
       │             LEGACY.CUST_MAST                    └──▶ Marketing CDP (external)
       └──────────────────────────────────────────────▶ (national_id, email, dob)
```

**Five locations, one of them outside Meridian.** The nightly CDP export leaves
the estate entirely, which is the part most erasure processes forget.

## An erasure request cannot currently be fulfilled

To honour Art.17 for one customer, Meridian must reach:

1. `RETAIL.CUSTOMERS` — source, deletable.
2. `ANALYTICS.DIM_CUSTOMER` — SCD2, so **every historical version** of that
   customer, not just the current row.
3. `ANALYTICS.CUSTOMER_360` — a view, resolves automatically.
4. `LEGACY.CUST_MAST` — **blocked by legal hold LH-2026-004.**
5. Marketing CDP — external system, outside this platform's control, requiring
   a separate process that does not currently exist.

Items 4 and 5 mean an erasure request today is **partially fulfillable at
best**, and the requester would have to be told so.

## The conflict, and how the policy resolves it

`LEGACY.CUST_MAST` is under legal hold. Counsel's own conflict rule states that
a retention obligation prevails and the erasure is recorded as partially
fulfilled with a stated legal basis.

That is the answer, and it comes from Meridian's requirement library rather
than from this agent's judgement. **This agent does not interpret GDPR** — it
applies the library counsel wrote and points out where the library is silent.

## Where the library is silent

Nothing addresses **personal data already exported to an external processor**.
The CDP export runs nightly and carries `email`. There is no documented recall
process. Counsel needs to extend the library; this is not something a data
platform can decide.
""",
            ),
            ExampleArtifact(
                filename="retention-policy.yaml",
                title="Retention policy",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: RetentionPolicy
metadata:
  scope: customer personal data
  basis: counsel-owned requirement library
  status: PROPOSAL — tier L1, regulated scope

objects:
  - object: RETAIL.CUSTOMERS
    classification: RESTRICTED
    retention: "duration of relationship + 2 years"
    basis: "GDPR Art.5(1)(e) via Meridian library"
    erasure: supported
    method: "hard delete of the customer row"

  - object: ANALYTICS.DIM_CUSTOMER
    classification: RESTRICTED
    retention: "follows RETAIL.CUSTOMERS"
    erasure: supported_with_caveat
    caveat: >-
      SCD2. Erasure must remove every version row for the customer, not the
      current one. A naive DELETE ... WHERE is_current leaves the history and
      the request is silently unfulfilled.

  - object: ANALYTICS.CUSTOMER_360
    classification: RESTRICTED (inherited)
    retention: derived
    erasure: automatic
    note: "A view. Resolves when its bases are erased."

  - object: LEGACY.CUST_MAST
    classification: RESTRICTED
    retention: "held indefinitely"
    erasure: BLOCKED
    blocking_basis: "Legal hold LH-2026-004, opened 2026-03-11"
    note: >-
      Under the library's conflict rule, the retention obligation prevails.
      Erasure is recorded as partially fulfilled with this legal basis stated
      to the requester. This agent will not propose deletion here.

  - object: "Marketing CDP export (external)"
    classification: RESTRICTED
    retention: unknown
    erasure: NO_PROCESS
    note: >-
      Personal data leaves the estate nightly. No documented recall process
      exists and the requirement library does not address external processors.
      Escalated to counsel — outside what a data platform can resolve.

gaps_for_counsel:
  - "No recall process for personal data already exported to the marketing CDP."
  - "The library does not state whether SCD2 history counts as separate records for erasure."
""",
            ),
        ],
        highlights=[
            "It answers 'can we actually fulfil an erasure request' with 'partially, and here is exactly why not'.",
            "The SCD2 caveat is the kind of detail that makes an erasure silently incomplete.",
            "It applies counsel's conflict rule rather than interpreting GDPR itself, and names where the library is silent.",
            "Data that has already left the estate is the gap most processes forget.",
        ],
        handoffs=[
            "Storage tiering economics → 25 Capacity & Retention Agent",
            "Who can read these columns → 26 Access & Entitlement Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="28",
        chapter=CHAPTER,
        scenario=(
            "The SOC 2 audit is in six weeks and evidence collection has historically taken "
            "three people a month. The agent assembles the binder from artifacts the fleet has "
            "already produced — and flags the controls it cannot evidence."
        ),
        inputs=[
            Exhibit(
                label="policies/control-catalog.md",
                kind="policy_document",
                origin="Sample artifacts / policies (compliance-owned)",
                format="markdown",
                stat="4 controls · evidence template",
                body="""# Control catalog extract — SOC 2 / internal

| Control | Requirement | Evidence expected |
|---|---|---|
| CC6.1 | Logical access is restricted to authorised users. | Grants inventory + entitlement matrix + review record |
| CC7.2 | Anomalies are detected and acted upon. | Monitoring config + incident records |
| CC8.1 | Changes are authorised, tested and approved. | Change tickets + PR approvals |
| PI1.4 | Data is complete and accurate. | Reconciliation results + DQ scorecards |

## Evidence template
Every item requires: control ID, asset, evidence artifact, date produced,
producer, and the approval record that accepted it.""",
            ),
        ],
        upstream=[
            "entitlement-review.md — agent 26",
            "monitor-config.yaml — agent 17",
            "root-cause-analysis.md — agent 19",
            "parity-report.md — agent 18",
            "quality-rules.yaml — agent 16",
        ],
        outputs=[
            ExampleArtifact(
                filename="control-mapping.json",
                title="Control mapping",
                format="json",
                source="reasoned",
                body="""{
  "framework": "SOC 2 (Meridian control catalog extract)",
  "assembled_from": "context-layer artifacts produced by the fleet",
  "controls": [
    {
      "control": "CC6.1",
      "requirement": "Logical access is restricted to authorised users.",
      "status": "EVIDENCED_WITH_EXCEPTIONS",
      "evidence": [
        { "artifact": "grants_inventory.csv", "produced": "2026-07-10", "producer": "platform export" },
        { "artifact": "role-entitlement-matrix.md", "produced": "2026-05-02", "producer": "Meridian Data Governance" },
        { "artifact": "entitlement-review.md", "produced": "2026-07-10", "producer": "agent 26 run r_88512", "approval": "PENDING" }
      ],
      "exceptions": [
        "PUBLIC holds SELECT on a view exposing RESTRICTED columns (ACC-001), open since 2026-01-22.",
        "A contractor role has held access for 692 days against a 90-day limit (ACC-002)."
      ],
      "auditor_note": "The review exists and identifies the exceptions. The exceptions are not yet remediated. Presenting this as EVIDENCED would be a misrepresentation."
    },
    {
      "control": "CC7.2",
      "requirement": "Anomalies are detected and acted upon.",
      "status": "EVIDENCED",
      "evidence": [
        { "artifact": "monitor-config.yaml", "produced": "2026-07-10", "producer": "agent 17 run r_88498" },
        { "artifact": "baselines.json", "produced": "2026-07-10", "producer": "agent 17 (deterministic)" },
        { "artifact": "root-cause-analysis.md", "produced": "2026-07-07", "producer": "agent 19 run r_88431" },
        { "artifact": "remediation-record.md", "produced": "2026-07-07", "producer": "agent 20 run r_88433", "approval": "change board 2026-07-07" }
      ],
      "auditor_note": "A detected anomaly, a documented root cause and an approved remediation, all within 24 hours. This is the strongest control in the pack."
    },
    {
      "control": "CC8.1",
      "requirement": "Changes are authorised, tested and approved.",
      "status": "NOT_EVIDENCED",
      "evidence": [],
      "gap": "No change tickets or PR approval records are present in the context layer.",
      "why": "ADE Studio does not read Meridian's change management system. This evidence exists; it is simply not in scope for the fleet to collect.",
      "action": "Compliance must attach change records manually. This agent will not fabricate a control it cannot evidence."
    },
    {
      "control": "PI1.4",
      "requirement": "Data is complete and accurate.",
      "status": "EVIDENCED_WITH_EXCEPTIONS",
      "evidence": [
        { "artifact": "parity-report.md", "produced": "2026-07-09", "producer": "agent 18 run r_88470" },
        { "artifact": "quality-rules.yaml", "produced": "2026-07-08", "producer": "agent 16 run r_88455" }
      ],
      "exceptions": [
        "Parity verdict is NOT READY FOR CUTOVER — two columns unmapped.",
        "FCT_ORDERS contract records accuracy as AT_RISK due to the FX defect."
      ]
    }
  ],
  "summary": { "evidenced": 1, "evidenced_with_exceptions": 2, "not_evidenced": 1 }
}""",
            ),
            ExampleArtifact(
                filename="evidence-pack.md",
                title="Evidence pack",
                format="markdown",
                source="reasoned",
                body="""# SOC 2 evidence pack — Meridian data platform

**Assembled 2026-07-10 from artifacts the fleet had already produced.** Nothing
here was created for the audit; every item is a run output with a producer, a
date and a provenance hash.

## Summary

| Control | Status | Evidence items |
|---|---|---|
| CC6.1 Logical access | ⚠ Evidenced with exceptions | 3 |
| CC7.2 Anomaly detection | ✅ Evidenced | 4 |
| CC8.1 Change management | ⛔ Not evidenced | 0 |
| PI1.4 Completeness & accuracy | ⚠ Evidenced with exceptions | 2 |

## The strongest control

**CC7.2.** On 7 July a monitor fired, agent 19 produced a root cause within
hours, and agent 20 produced an approved remediation the same day. Detection,
diagnosis and response, all with timestamps and named approvers.

That chain is the argument for this platform, and it exists as a by-product of
operating rather than as an audit exercise.

## The control I cannot evidence

**CC8.1 requires change tickets and PR approvals.** ADE Studio does not read
Meridian's change management system, so there is nothing in the context layer.

The evidence exists. It is not in scope for this fleet to collect. Compliance
attaches it manually.

Stated as **NOT_EVIDENCED** rather than quietly omitted, because a binder that
silently skips a control is worse than one with an honest gap — an auditor who
finds the gap themselves discounts everything else in the pack.

## Exceptions an auditor will ask about

1. **`PUBLIC` can read RESTRICTED columns**, open since January. Agent 26
   identified it; remediation is pending approval.
2. **A contractor role has held access for 692 days** against a 90-day limit.
3. **Migration parity is NOT READY** — two columns unmapped.
4. **`FCT_ORDERS` accuracy is contractually AT_RISK** because of the FX defect.

All four are already documented by the agents that found them. Presenting
CC6.1 as fully evidenced while items 1 and 2 are open would be a
misrepresentation, so it is not presented that way.
""",
            ),
        ],
        highlights=[
            "The binder is assembled from artifacts already produced — audit evidence as a by-product of operating.",
            "One control is marked NOT_EVIDENCED rather than quietly omitted; a gap an auditor finds themselves discounts the whole pack.",
            "Exceptions are surfaced rather than buried, each traced to the agent that found it.",
        ],
        handoffs=[
            "Remediating the access exceptions → 26 Access & Entitlement Agent",
            "Change management evidence → compliance; outside the fleet's scope",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="29",
        chapter=CHAPTER,
        scenario=(
            "The team wants customer-360 certified for self-serve. The agent evaluates it "
            "against the publication checklist and refuses — with a list short enough to act on."
        ),
        inputs=[
            Exhibit(
                label="Publication request",
                kind="structured_request",
                origin="Typed into the workbench by the revenue-data-team",
                format="text",
                stat="asset · owner",
                body="""Publish ANALYTICS.CUSTOMER_360 as a certified data product for self-serve
analytics. Owner: revenue-data-team. Intended audience: Commercial BI, Finance,
Marketing. We would like it certified before the quarterly business review.""",
            ),
            Exhibit(
                label="policies/publication-checklist.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="6 gates",
                body="""# Data product publication checklist v2
1. A published data contract with named consumers.
2. Catalog documentation with >= 90% column coverage.
3. A quality scorecard with no open error-severity rules.
4. Semantic layer definitions for every published metric.
5. An access model reviewed within the last 90 days, no open critical findings.
6. A named accountable owner who is not the publishing team.""",
            ),
        ],
        upstream=[
            "data-contract.yaml — agent 13",
            "data-dictionary.md — agent 03",
            "quality-rules.yaml — agent 16",
            "semantic-model.yaml — agent 12",
            "entitlement-review.md — agent 26",
        ],
        outputs=[
            ExampleArtifact(
                filename="publication-readiness.md",
                title="Publication readiness",
                format="markdown",
                source="reasoned",
                body="""# Publication readiness — ANALYTICS.CUSTOMER_360

## Verdict: NOT READY. Two gates fail.

| # | Gate | Status | Evidence |
|---|---|---|---|
| 1 | Published data contract | ✅ PASS | `data-contract.yaml` v1.0.0, 3 named consumers (agent 13) |
| 2 | Docs ≥ 90% column coverage | ✅ PASS | 12 of 12 columns described (agent 03) |
| 3 | No open error-severity DQ rules | ✅ PASS | 5 rules, 0 firing (agent 16) |
| 4 | Semantic definitions for every metric | ⚠ PARTIAL | `sales_region` is BLOCKED (agent 12) |
| 5 | Access reviewed, no critical findings | ⛔ FAIL | ACC-001 open since 2026-01-22 (agent 26) |
| 6 | Accountable owner outside the publishing team | ⛔ FAIL | Owner given as revenue-data-team, who are publishing |

## Gate 5 — the one that should stop the conversation

`PUBLIC` has SELECT on this exact view, and this view projects `national_id`
and `email`, both classified RESTRICTED.

**Certifying it for self-serve would advertise it to the whole organisation
while every role in the account can already read the personal data in it.**
Certification would make the exposure worse, not better.

One statement fixes it:

```sql
REVOKE SELECT ON ANALYTICS.CUSTOMER_360 FROM ROLE PUBLIC;
```

## Gate 6 — a governance gap, not a paperwork gap

The checklist requires an accountable owner who is **not** the publishing team,
so that certification is a review rather than a self-declaration. The request
names `revenue-data-team` as both. A different named owner is needed — this is
not a formality the agent can wave through.

## Gate 4 — partial, and survivable

`sales_region` is defined in the semantic layer and marked BLOCKED because
`DIM_CUSTOMER.region_code` is an unmapped gap. Publishing without it is
acceptable **if** the metric is withheld rather than published as an empty
dimension. Recorded as partial rather than failed.

## What to do

Two actions clear this: revoke the PUBLIC grant, and name an accountable owner
outside the publishing team. Both are hours of work, not weeks. Re-run this
agent afterwards.
""",
            ),
            ExampleArtifact(
                filename="data-product-manifest.yaml",
                title="Data product manifest",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: DataProductManifest
metadata:
  product: customer-360
  asset: ANALYTICS.CUSTOMER_360
  version: "0.9.0-rc"
  status: NOT_CERTIFIED

# Deliberately versioned 0.9.0-rc, not 1.0.0. The manifest is written so the
# work is not wasted, and it will not certify itself.

certification:
  status: BLOCKED
  blocking_gates: [5, 6]
  blocking_summary:
    - "Gate 5: PUBLIC holds SELECT on this view, which exposes RESTRICTED columns."
    - "Gate 6: no accountable owner outside the publishing team."

product:
  description: >-
    One row per customer with lifetime value and last order date, joining the
    conformed customer dimension to the order fact.
  owner: revenue-data-team
  accountable_owner: null   # required by gate 6
  audience: [Commercial BI, Finance close, Marketing CDP]

interfaces:
  contract: ANALYTICS.FCT_ORDERS v1.0.0 (agent 13)
  semantic_metrics: [net_revenue, completed_net_revenue, active_customers, average_order_value]
  withheld_metrics:
    - metric: sales_region
      reason: "Depends on DIM_CUSTOMER.region_code, an unmapped gap. Withheld rather than published empty."

quality:
  rules: 5
  open_error_severity: 0
  scorecard: quality-rules.yaml (agent 16)

known_limitations:
  - "amount_usd accuracy is contractually AT_RISK pending the FX fix."
  - "sales_region is not available."
""",
            ),
        ],
        highlights=[
            "It refuses certification, and the reason is that certifying would make an existing exposure worse.",
            "The manifest is written anyway, versioned 0.9.0-rc, so the work is not wasted — but it will not certify itself.",
            "Gate 6 is treated as a governance requirement, not paperwork: certification must be a review, not a self-declaration.",
            "The two blocking actions are hours of work, and it says so.",
        ],
        handoffs=[
            "Revoking the PUBLIC grant → 26 Access & Entitlement Agent",
            "Publishing metrics over the certified product → 12 Semantic Layer Agent",
        ],
    ),
]
