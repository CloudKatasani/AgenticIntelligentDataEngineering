"""Chapter 7 — Cross-cutting. Route, measure, and critique the fleet (33–35)."""

from __future__ import annotations

from app.domain.canvas import Exhibit, ExampleArtifact, WorkedExample

CHAPTER = "7 · Cross-cutting — route, measure, critique"

EXAMPLES: list[WorkedExample] = [
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="33",
        chapter=CHAPTER,
        scenario=(
            "Meridian's head of data engineering states an objective in one sentence. The "
            "supervisor plans a route through the dependency graph and stops at the first "
            "decision only a human can make."
        ),
        inputs=[
            Exhibit(
                label="Fleet goal and scope",
                kind="structured_request",
                origin="Typed into the workbench by the head of data engineering",
                format="text",
                stat="the only input · no data objects at all",
                note="An estate-scoped agent. It selects no tables and reads no files.",
                body="""Onboard the FINANCE schema end to end and get it certified for self-serve
analytics, the same way we did RETAIL. Target: before the next quarterly
business review, six weeks out.""",
            ),
        ],
        upstream=["Agent registry (capabilities, tiers, input contracts)", "Dependency graph", "Run ledger"],
        outputs=[
            ExampleArtifact(
                filename="orchestration-plan.yaml",
                title="Orchestration plan",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: FleetPlan
metadata:
  goal: "Onboard FINANCE end to end and certify for self-serve"
  scope: ADE_DEMO.FINANCE (ACCOUNTS, EXCHANGE_RATES, GL_TRANSACTIONS)
  deadline: "6 weeks"
  planned_from: dependency graph + agent input contracts

waves:
  - wave: 1
    parallel: true
    agents:
      - { id: "01", task: "Profile all 3 FINANCE objects", blocked_by: [] }
      - { id: "04", task: "Reconstruct lineage from the FINANCE load code", blocked_by: [],
          note: "Independent of 01 — reads code, not rows. Runs in parallel." }
      - { id: "06", task: "Interrogate the legacy GL extract", blocked_by: [] }

  - wave: 2
    agents:
      - { id: "02", task: "Classify FINANCE columns", blocked_by: ["01"] }
      - { id: "05", task: "Bind governed terms", blocked_by: ["01"] }
      - { id: "03", task: "Document the objects", blocked_by: ["01", "04"] }

  - wave: 3
    agents:
      - { id: "08", task: "Model the finance product", blocked_by: ["01", "05"],
          human_input_required: "Workload intent — what the product must answer" }

  - wave: 4
    agents:
      - { id: "07", task: "Physical DDL", blocked_by: ["08", "02"] }
      - { id: "09", task: "Source-to-target mapping", blocked_by: ["08", "01"] }

  - wave: 5
    agents:
      - { id: "16", task: "Quality rules", blocked_by: ["01", "02"] }
      - { id: "13", task: "Data contract", blocked_by: ["07", "16"] }
      - { id: "26", task: "Access model", blocked_by: ["02"] }

  - wave: 6
    agents:
      - { id: "29", task: "Certify for self-serve", blocked_by: ["13", "03", "16", "12"] }

stop_conditions:
  - at: wave 3
    reason: >-
      Agent 08 requires a stated workload intent and will not proceed without
      one. This is not a scheduling gap — modelling without a stated workload is
      guesswork, and the agent's input contract enforces it.
    needs: "A sentence from finance describing what the product must answer."
    owner: "head of data engineering / finance"

  - at: wave 2, agent 02
    reason: >-
      FINANCE is likely to be marked regulated. If so, agent 02 is capped at L1
      and its output is a proposal requiring named acceptance. Approval capacity
      is on the critical path, not just compute.
    needs: "A named data-protection approver with time reserved."

critical_path:
  sequence: ["01", "05", "08", "09", "07", "13", "29"]
  note: >-
    Seven sequential agents, each gated on human approval where the tier is
    advisory. The binding constraint on the six-week deadline is approval
    latency, not agent runtime.

not_planned:
  - agent: "20"
    reason: "Remediation is incident-driven. Scheduling it in an onboarding plan would be nonsense."
  - agent: "18"
    reason: >-
      Parity compares two estates. FINANCE is being onboarded, not migrated —
      there is no second estate to compare against. Included only if a legacy
      finance system is in scope, which the goal does not say.""",
            ),
            ExampleArtifact(
                filename="routing-decision.md",
                title="Routing decision",
                format="markdown",
                source="reasoned",
                body="""# Fleet plan — onboard FINANCE, certify for self-serve

**14 agent runs across 6 waves.** Every dependency comes from the graph, not
from an opinion about ordering.

## The plan stops at wave 3, deliberately

Waves 1 and 2 can start today. Wave 3 cannot, because **agent 08 requires a
stated workload intent** and will not proceed without one.

That is not a gap in this plan. Modelling without knowing what the model is for
is guesswork, and agent 08's input contract enforces it. The supervisor's job
here is to surface that requirement in week one rather than in week four when
someone notices the model design is stalled.

**What is needed:** a sentence from finance describing what the product must
answer. It took the retail onboarding about twenty minutes to write.

## The constraint that will decide the six weeks

The critical path is `01 → 05 → 08 → 09 → 07 → 13 → 29` — seven sequential
agents. Four of them are advisory tier, meaning their output is a proposal
until a named human accepts it.

**The binding constraint is approval latency, not agent runtime.** The agents
will finish their work in hours. If each approval takes a week, the path is
seven weeks and the deadline is missed on process, not capability.

Recommendation: name the approvers now and reserve their time. That is the
single highest-leverage thing to do this week.

## What runs in parallel that people expect to be sequential

Agent 04 (lineage) does **not** depend on agent 01 (profiling). It reads code,
not rows. Teams habitually run profiling first and wait; there is no need. Same
for agent 06 on the legacy extract.

Three agents start on day one.

## Two agents deliberately not scheduled

**Agent 20** is incident-driven. Scheduling remediation into an onboarding plan
would be meaningless.

**Agent 18** compares two estates. FINANCE is being onboarded, not migrated. If
there is a legacy finance system in scope, say so and this plan changes — the
goal as stated does not mention one.

## What this agent did not do

It did not dispatch anything. This is a plan for a human to approve and run.
""",
            ),
        ],
        highlights=[
            "Estate-scoped: it selects no tables and reads no files — one sentence in, a fleet plan out.",
            "It identifies that the six-week deadline will be decided by approval latency, not agent runtime.",
            "It corrects a common sequencing assumption: lineage does not wait for profiling.",
            "It refuses to schedule two agents and explains why each is wrong for this goal.",
        ],
        handoffs=[
            "Executing each wave → the individual agents, on human approval",
            "Measuring whether the fleet performed → 34 Evaluator Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="34",
        chapter=CHAPTER,
        scenario=(
            "Someone proposes promoting agent 02 from advisory to supervised so classification "
            "stops needing sign-off. The evaluator measures it against a golden set and "
            "recommends against."
        ),
        inputs=[
            Exhibit(
                label="What to evaluate",
                kind="structured_request",
                origin="Typed into the workbench by the platform lead",
                format="text",
                stat="a promotion request",
                body="""Assess agent 02 (Data Classification) for promotion from L1 to L2 on
non-regulated sources. Rationale: classification review is a bottleneck — every
run waits on a governance approver and we have 340 objects to onboard.""",
            ),
            Exhibit(
                label="telemetry/golden_set_02.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="12 labelled columns · expert-assigned",
                note="Without a golden set the evaluation is qualitative, and the agent says so.",
                body="""column,expert_label,agent_label,agreed
RETAIL.CUSTOMERS.national_id,RESTRICTED,RESTRICTED,yes
RETAIL.CUSTOMERS.email,RESTRICTED,RESTRICTED,yes
RETAIL.CUSTOMERS.date_of_birth,RESTRICTED,RESTRICTED,yes
RETAIL.CUSTOMERS.marketing_opt_in,RESTRICTED,RESTRICTED,yes
RETAIL.CUSTOMERS.lifetime_value,CONFIDENTIAL,CONFIDENTIAL,yes
RETAIL.CUSTOMERS.customer_id,INTERNAL,INTERNAL,yes
RETAIL.CUSTOMERS.country_code,INTERNAL,INTERNAL,yes
RETAIL.CUSTOMERS.city,RESTRICTED,INTERNAL,no
FINANCE.ACCOUNTS.account_holder,RESTRICTED,RESTRICTED,yes
FINANCE.ACCOUNTS.balance,CONFIDENTIAL,CONFIDENTIAL,yes
FINANCE.GL_TRANSACTIONS.memo,RESTRICTED,INTERNAL,no
FINANCE.GL_TRANSACTIONS.amount,CONFIDENTIAL,CONFIDENTIAL,yes""",
            ),
        ],
        outputs=[
            ExampleArtifact(
                filename="evaluation-scorecard.json",
                title="Evaluation scorecard",
                format="json",
                source="reasoned",
                body="""{
  "agent": "02 Data Classification Agent",
  "request": "Promote L1 -> L2 on non-regulated sources",
  "golden_set": { "size": 12, "labelled_by": "Meridian Data Governance" },

  "metrics": {
    "overall_agreement": 0.833,
    "by_label": {
      "RESTRICTED": { "recall": 0.667, "precision": 1.000, "n": 6,
                      "note": "Missed 2 of 6. Never over-labelled." },
      "CONFIDENTIAL": { "recall": 1.000, "precision": 1.000, "n": 3 },
      "INTERNAL": { "recall": 1.000, "precision": 0.600, "n": 3,
                    "note": "Precision is low because the 2 missed RESTRICTED columns landed here." }
    }
  },

  "error_analysis": [
    {
      "column": "RETAIL.CUSTOMERS.city",
      "expert": "RESTRICTED", "agent": "INTERNAL",
      "class": "combination risk",
      "detail": "City alone is not identifying. Combined with date_of_birth and country_code it re-identifies individuals in small populations. The agent flagged this exact question as unresolved in its own output rather than getting it silently wrong.",
      "mitigating": true
    },
    {
      "column": "FINANCE.GL_TRANSACTIONS.memo",
      "expert": "RESTRICTED", "agent": "INTERNAL",
      "class": "free-text leakage",
      "detail": "A free-text memo field can contain anything, including personal data pasted by a human. The agent classified on the column's declared purpose rather than its possible contents. It did NOT flag this one.",
      "mitigating": false
    }
  ],

  "promotion_recommendation": {
    "verdict": "DO NOT PROMOTE",
    "threshold_required": "RESTRICTED recall >= 0.95 for autonomous operation",
    "measured": 0.667,
    "reasoning": "The failure mode is under-labelling personal data. At L2 the agent applies labels without review, so each miss becomes an unreviewed exposure. Errors here are asymmetric: over-labelling costs friction, under-labelling costs a breach.",
    "sample_size_caveat": "12 columns is far too small to certify an autonomy change. A 95% recall claim needs a golden set in the hundreds. This evaluation can justify a NO; it could not have justified a YES."
  },

  "alternative": {
    "proposal": "Selective L2 on CONFIDENTIAL and INTERNAL only; RESTRICTED stays L1.",
    "measured_basis": "Both non-RESTRICTED labels scored 1.0 recall and 1.0 precision on this set.",
    "effect": "Removes review from roughly 60% of columns while keeping a human on every personal-data decision.",
    "still_requires": "A larger golden set before adoption."
  }
}""",
            ),
            ExampleArtifact(
                filename="evaluation-report.md",
                title="Evaluation report",
                format="markdown",
                source="reasoned",
                body="""# Evaluation — agent 02, promotion L1 → L2

## Recommendation: do not promote

83.3% overall agreement. That number is not the reason.

**RESTRICTED recall is 0.667.** The agent missed two of six personal-data
columns. At L1 that costs a reviewer thirty seconds. At L2 there is no reviewer,
and each miss is an unlabelled personal-data column sitting in the estate.

## The errors are asymmetric, and that decides it

The agent never over-labelled — precision on RESTRICTED is 1.000. Its failure
mode is exclusively *under*-labelling.

- Over-labelling costs friction: someone requests access and is refused.
- Under-labelling costs a breach: nobody requests access because nothing says
  the data is sensitive.

An 83% agreement rate is a good score for a classifier and an unacceptable one
for an autonomous privacy control.

## One miss is mitigated, one is not

**`city`** — the agent classified INTERNAL where the expert said RESTRICTED,
because in combination with date of birth and country it re-identifies people.
**The agent raised this exact question as unresolved in its own output.** It did
not get it wrong silently; it escalated it. That is the behaviour you want, and
it is why L1 works.

**`GL_TRANSACTIONS.memo`** — a free-text field. The agent classified on the
column's declared purpose rather than what a human might paste into it. It did
not flag this one, and free-text leakage is a known, common exposure. This is a
genuine capability gap.

## What this evaluation cannot tell you

**Twelve columns is far too small to certify an autonomy change.** A 95% recall
claim needs a golden set in the hundreds.

This asymmetry is worth stating plainly: a small golden set can justify a NO —
one clear failure mode is enough — but it can never justify a YES. If Meridian
wants this promotion, the first step is a larger labelled set, not a rerun.

## A narrower change that the evidence does support

CONFIDENTIAL and INTERNAL both scored 1.0 recall and 1.0 precision. **Promote
those two labels to L2 and keep RESTRICTED at L1.**

That removes review from roughly 60% of columns — most of the stated bottleneck
— while keeping a human on every personal-data decision. It still needs a
larger golden set before adoption, but it is the shape of change this evidence
can support.
""",
            ),
        ],
        highlights=[
            "It recommends against a promotion the platform lead wanted, on measured evidence.",
            "The asymmetry argument is the core: over-labelling costs friction, under-labelling costs a breach.",
            "It distinguishes a miss the agent escalated from one it got silently wrong.",
            "It states that a small golden set can justify a NO but never a YES.",
            "It proposes a narrower change the evidence actually supports.",
        ],
        handoffs=[
            "Closing the free-text capability gap → the agent 02 owner",
            "Tier caps on regulated sources → enforced structurally, not by evaluation",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="35",
        chapter=CHAPTER,
        scenario=(
            "A pull request implements the customer dimension. The reviewer checks the code "
            "against the artifacts it claims to implement — and finds a contradiction between "
            "the PR and the approved mapping."
        ),
        inputs=[
            Exhibit(
                label="PR #412 — dim_customer.sql",
                kind="code_artifacts",
                origin="Sample artifacts / warehouse-code",
                format="sql",
                stat="changed file under review",
                body="""{{ config(materialized='incremental', unique_key='customer_id') }}

with source_customers as (
    select
        customer_id,
        lower(trim(email))                    as email,
        national_id,                          -- <-- raw value
        year(date_of_birth)                   as birth_year,
        case when country_code in ('FR','DE','ES','IT','NL','SE','PL')
             then 'EMEA'
             when country_code in ('US','CA','MX')
             then 'AMER'
             else 'APAC' end                  as region_code,
        segment
    from {{ source('retail', 'customers') }}
)

select *, current_timestamp() as dw_loaded_at
from source_customers""",
            ),
            Exhibit(
                label="policies/review-standards.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="what a review is against",
                body="""# Review standards
- Code must implement the approved mapping spec, or declare the deviation.
- RESTRICTED columns per the classification must never land raw.
- No invented business logic — groupings and rules come from a governed source.
- Incremental models must be idempotent.""",
            ),
        ],
        upstream=[
            "mapping-spec.yaml — agent 09",
            "classification.json — agent 02",
            "entity-model.yaml — agent 08",
        ],
        outputs=[
            ExampleArtifact(
                filename="review-verdict.json",
                title="Review verdict",
                format="json",
                source="reasoned",
                body="""{
  "pull_request": "#412 dim_customer.sql",
  "verdict": "REQUEST_CHANGES",
  "blocking_findings": 2,
  "non_blocking_findings": 2,

  "findings": [
    {
      "id": "REV-001",
      "severity": "blocking",
      "class": "privacy",
      "line": 6,
      "finding": "`national_id` is selected raw.",
      "contradicts": "classification.json (agent 02): national_id is RESTRICTED, masking required. mapping-spec.yaml (agent 09): target column is national_id_token via SHA2.",
      "impact": "A raw national identifier lands in the analytics estate. The approved design specifically avoided this by never landing the value at all.",
      "required": "Apply the SHA2 tokenization from the approved mapping."
    },
    {
      "id": "REV-002",
      "severity": "blocking",
      "class": "invented business logic",
      "line": "8-13",
      "finding": "A hardcoded CASE assigns countries to regions.",
      "contradicts": "mapping-spec.yaml (agent 09) marks region_code as status: GAP — 'no region dimension exists; a lookup table must be supplied'.",
      "impact": "This grouping is the author's invention. It compiles, runs, and produces plausible regional revenue numbers that do not match Meridian's actual region definitions. Wrong in the way nobody notices for a quarter.",
      "required": "Remove. Supply the region lookup, or leave the column unpopulated as the mapping specifies."
    },
    {
      "id": "REV-003",
      "severity": "non-blocking",
      "class": "model conformance",
      "finding": "No SCD2 columns — valid_from, valid_to, is_current are absent.",
      "contradicts": "entity-model.yaml (agent 08): DIM_CUSTOMER is type SCD2.",
      "note": "Materialized incremental on customer_id, which is type-1 overwrite behaviour. A customer changing region loses their history, which is the exact failure the SCD2 decision was made to prevent."
    },
    {
      "id": "REV-004",
      "severity": "non-blocking",
      "class": "house style",
      "finding": "`select *` in a committed model.",
      "contradicts": "Meridian dbt conventions: no SELECT * in committed models."
    }
  ],

  "cross_artifact_consistency": {
    "checked": ["mapping-spec.yaml", "classification.json", "entity-model.yaml", "review-standards.md"],
    "note": "Both blocking findings are contradictions between the code and an artifact it claims to implement. Neither is visible by reading the SQL alone."
  }
}""",
            ),
            ExampleArtifact(
                filename="review-findings.md",
                title="Review findings",
                format="markdown",
                source="reasoned",
                body="""# Review — PR #412, `dim_customer.sql`

**Verdict: REQUEST CHANGES.** Two blocking findings. Both are contradictions
between this code and an artifact it claims to implement — neither is visible
by reading the SQL on its own.

## REV-002 — the invented region grouping

```sql
case when country_code in ('FR','DE','ES','IT','NL','SE','PL') then 'EMEA'
```

The approved mapping marks `region_code` as **GAP**: *"no region dimension
exists; a lookup table must be supplied."*

This CASE is the author's guess at Meridian's regions. It compiles, it runs,
and it produces regional revenue numbers that look completely normal.

Nothing fails. A commercial director builds a quarterly narrative on EMEA
performance, and the grouping is not the one Meridian actually uses. It is
discovered when someone compares against a finance report six weeks later.

**This is the finding that justifies cross-artifact review.** A human reviewer
reading only this diff sees reasonable-looking SQL. The problem is only visible
against the mapping spec.

## REV-001 — the raw identifier

`national_id` is selected raw. Agent 02 classified it RESTRICTED with masking
required, and agent 09's mapping tokenizes it with SHA2 precisely so the raw
value never lands.

This PR undoes a privacy control by writing one fewer function call.

## REV-003 — the SCD2 that is not

The approved model says `DIM_CUSTOMER` is SCD2, with a written rationale: a
customer who changes region must not retrospectively move their whole history.

This PR is a type-1 overwrite. It reintroduces exactly the failure the design
decision was made to prevent. Non-blocking only because it is a visible,
structural gap rather than a silent one — but it must be resolved before merge.

## What this reviewer is not

It is not a linter. REV-004 (`select *`) is the only style finding and it is
last, because it is the least important thing on this page. The value here is
checking code against the artifacts it claims to implement.
""",
            ),
        ],
        highlights=[
            "Both blocking findings are invisible in the diff alone — they are contradictions with the approved artifacts.",
            "The invented region grouping compiles, runs, and produces plausible wrong numbers for a quarter.",
            "It ranks a privacy regression and a design contradiction above style, and says so.",
        ],
        handoffs=[
            "Fixing the implementation → 10 Coding Agent",
            "Supplying the region lookup → 09 Data Mapping Agent",
        ],
    ),
]
