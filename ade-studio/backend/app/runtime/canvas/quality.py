"""Chapter 3 — Quality. Make it trustworthy, and prove it (agents 16–21)."""

from __future__ import annotations

from app.domain.canvas import Exhibit, ExampleArtifact, WorkedExample

CHAPTER = "3 · Quality — make it trustworthy, and prove it"

EXAMPLES: list[WorkedExample] = [
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="16",
        chapter=CHAPTER,
        scenario=(
            "Meridian's existing DQ suite has 340 rules, a 60% fire rate, and everybody ignores "
            "it. The agent derives thresholds from the profiled distributions instead of round "
            "numbers, and records the statistic behind each one."
        ),
        inputs=[
            Exhibit(
                label="ADE_DEMO.RETAIL.CUSTOMERS",
                kind="database_objects",
                origin="ADE Demo Warehouse",
                format="table",
                stat="12 columns · thresholds derived from the profile",
                body="customer_id, email, phone, national_id, lifetime_value, marketing_opt_in, …",
            ),
        ],
        upstream=["profile.json — agent 01", "classification.json — agent 02"],
        outputs=[
            ExampleArtifact(
                filename="quality-rules.yaml",
                title="Data quality rules",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: QualityRules
metadata:
  object: ADE_DEMO.RETAIL.CUSTOMERS
  derived_from: profile.json (agent 01, run r_88102)

rules:
  - id: dq_customers_pk
    type: uniqueness
    column: customer_id
    assertion: "distinct_count = row_count"
    severity: error
    threshold_basis: "Profile: distinct_ratio 1.0, null_ratio 0.0 over 200 sampled rows."

  - id: dq_customers_email_null
    type: completeness
    column: email
    assertion: "null_ratio <= 0.06"
    severity: warn
    threshold_basis: >-
      Profile: 4.0% null in sample. Threshold set at 6% — 1.5x observed, which
      allows normal variation without firing. NOT set to 0%: that would fire
      every night against the current state of the source and be muted within a
      week.

  - id: dq_customers_email_format
    type: validity
    column: email
    assertion: "regexp_match_ratio >= 0.94"
    severity: warn
    threshold_basis: "Profile: 186/192 non-null matched (96.9%). Floor at 94% allows drift, catches collapse."

  - id: dq_customers_national_id_masked
    type: privacy
    column: national_id
    assertion: "no unmasked value reaches any non-privileged role"
    severity: error
    threshold_basis: "Agent 02 classified this RESTRICTED. There is no tolerance band on a privacy control."

  - id: dq_customers_phone_format_drift
    type: consistency
    column: phone
    assertion: "distinct_format_count <= 3"
    severity: warn
    threshold_basis: >-
      Profile found three formats (us_phone 67/200, digits_only 66/200,
      remainder dashed). The rule locks the current state so a FOURTH format
      is caught. It deliberately does not demand one format — that is a data
      fix, not a monitoring threshold.

not_generated:
  - column: lifetime_value
    reason: >-
      Two columns claim this measure and agent 05 marked the binding CONTESTED.
      A range rule would encode whichever definition happened to be sampled and
      then look authoritative. No rule until finance designates the source.""",
            ),
            ExampleArtifact(
                filename="thresholds.json",
                title="Threshold derivation",
                format="json",
                source="reasoned",
                body="""{
  "object": "ADE_DEMO.RETAIL.CUSTOMERS",
  "principle": "Every threshold is a function of a profiled statistic, so a reviewer can audit the number rather than trust it.",
  "derivations": [
    {
      "rule": "dq_customers_email_null",
      "observed": { "null_ratio": 0.04, "sample_size": 200, "source": "profile.json" },
      "formula": "observed * 1.5",
      "threshold": 0.06,
      "rejected_alternative": { "threshold": 0.0, "reason": "Fires nightly on the current source. Muted within a week, then useless." }
    },
    {
      "rule": "dq_customers_email_format",
      "observed": { "match_ratio": 0.969, "matched": 186, "non_null": 192 },
      "formula": "observed - 0.03",
      "threshold": 0.94,
      "rationale": "Tolerates ordinary drift; a collapse to 90% fires."
    },
    {
      "rule": "dq_customers_pk",
      "observed": { "distinct_ratio": 1.0, "null_ratio": 0.0 },
      "formula": "exact",
      "threshold": 1.0,
      "rationale": "A key is unique or it is not. No tolerance band."
    }
  ],
  "sampling_caveat": "All thresholds derive from a first-200-rows sample. If the table is loaded in insertion order this is the oldest customers and the distributions may not be representative. Re-derive from a random sample before these rules govern a production gate."
}""",
            ),
            ExampleArtifact(
                filename="rule-rationale.md",
                title="Rule rationale",
                format="markdown",
                source="reasoned",
                body="""# Rule rationale — RETAIL.CUSTOMERS

**5 rules, not 40.** Meridian's existing suite has 340 rules across the estate
with a 60% fire rate. A rule that fires most nights is not a control, it is
noise that trains people to ignore the channel.

## Why the thresholds are not round numbers

`email` completeness is 6%, not 5% and not 0%. It is 1.5× the observed 4%. A 0%
threshold is the instinctive choice and it is wrong here: the source *currently*
has 4% missing emails, so the rule would fire on the first night, every night,
until someone muted it.

The threshold encodes "has this got worse", which is the question worth asking.
Fixing the 4% is a data-owner conversation, not a monitoring threshold.

## The one rule with no tolerance

`dq_customers_national_id_masked` is binary. Agent 02 classified the column
RESTRICTED, and a privacy control does not get a tolerance band — 99% masked is
a breach, not a passing score.

## What was deliberately not written

No rule on `lifetime_value`. Agent 05 found two columns claiming that term with
different definitions. A range rule would silently encode whichever one was
sampled and then carry the authority of a governed control. No rule until
finance designates the authoritative column.

## The caveat that matters

Every threshold derives from a 200-row sample taken from the top of the table.
If rows are stored in insertion order, that is Meridian's oldest customers, and
their email quality may not resemble this year's. **Re-derive from a random
sample before these govern a production gate.**
""",
            ),
        ],
        highlights=[
            "5 rules instead of 340 — a rule that fires most nights trains people to ignore the channel.",
            "Every threshold is a function of a profiled statistic, recorded so a reviewer can audit it.",
            "It refuses to write a rule on a contested measure rather than encoding the wrong definition.",
            "The privacy rule has no tolerance band, and the rationale says why.",
        ],
        handoffs=[
            "Codifying these as contract commitments → 13 Data Contract Agent",
            "Statistical baselines and freshness → 17 Anomaly & Freshness Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="17",
        chapter=CHAPTER,
        scenario=(
            "The nightly load failed once and double-loaded once in ten days, and the first "
            "anyone knew was a stale dashboard. The agent computes baselines from run history "
            "and configures monitors around them."
        ),
        inputs=[
            Exhibit(
                label="telemetry/pipeline_runs.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="10 runs · 1 failure · 1 double load · 1 late start",
                note="Freshness cannot be judged from a snapshot; this is why the slot needs history.",
                body="""run_date,pipeline,status,rows_loaded,started_at,duration_s
2026-07-01,load_fct_orders,SUCCESS,182450,2026-07-01T02:00:11Z,831
2026-07-02,load_fct_orders,SUCCESS,181002,2026-07-02T02:00:09Z,815
2026-07-03,load_fct_orders,SUCCESS,179884,2026-07-03T02:00:12Z,908
2026-07-04,load_fct_orders,SUCCESS,180551,2026-07-04T02:00:10Z,861
2026-07-05,load_fct_orders,SUCCESS,12004,2026-07-05T02:00:14Z,168
2026-07-06,load_fct_orders,SUCCESS,178990,2026-07-06T02:00:08Z,844
2026-07-07,load_fct_orders,FAILED,0,2026-07-07T02:00:11Z,104
2026-07-08,load_fct_orders,SUCCESS,361200,2026-07-08T02:00:13Z,2454
2026-07-09,load_fct_orders,SUCCESS,180117,2026-07-09T02:00:10Z,885
2026-07-10,load_fct_orders,SUCCESS,181433,2026-07-10T05:41:02Z,878""",
            ),
            Exhibit(
                label="policies/event-calendar.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="known windows",
                note="So expected spikes are not reported as anomalies.",
                body="""# Known events
- 2026-07-05: partial source outage 00:00–06:00 UTC (vendor incident VEN-4471).
- First Sunday monthly: platform maintenance 01:00–03:00 UTC.""",
            ),
        ],
        outputs=[
            ExampleArtifact(
                filename="baselines.json",
                title="Statistical baselines",
                format="json",
                source="deterministic",
                note="Computed, not generated — the same rule the profiler follows.",
                body="""{
  "pipeline": "load_fct_orders",
  "window": "2026-07-01 to 2026-07-10",
  "method": "median and MAD over successful runs, outliers excluded before fitting",

  "row_count": {
    "n_used": 7,
    "excluded": [
      { "date": "2026-07-05", "value": 12004, "reason": "known event: vendor outage VEN-4471" },
      { "date": "2026-07-07", "value": 0, "reason": "run failed" },
      { "date": "2026-07-08", "value": 361200, "reason": "outlier — 2.0x median, consistent with a double load" }
    ],
    "median": 180551,
    "mad": 967,
    "lower_bound": 177650,
    "upper_bound": 183452,
    "note": "Bounds are median ± 3·MAD. The excluded runs would have widened the band enough to make it useless — 2026-07-08 alone would raise the upper bound above 360k and stop detecting the very failure it represents."
  },

  "start_time": {
    "n_used": 9,
    "median_utc": "02:00:11",
    "max_observed_utc": "05:41:02",
    "note": "2026-07-10 started 3h41m late. Within the 06:00 freshness SLA but with 19 minutes of margin."
  },

  "duration_s": { "n_used": 7, "median": 861, "mad": 24, "upper_bound": 933 }
}""",
            ),
            ExampleArtifact(
                filename="monitor-config.yaml",
                title="Monitor configuration",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: MonitorConfig
metadata:
  pipeline: load_fct_orders
  baselines: baselines.json

monitors:
  - id: mon_row_count_low
    metric: rows_loaded
    condition: "< 177650"
    severity: error
    suppress_during: [known_event]
    note: "Would have caught 2026-07-05 had the vendor outage not been calendared."

  - id: mon_row_count_high
    metric: rows_loaded
    condition: "> 183452"
    severity: error
    note: >-
      This is the one that matters. 2026-07-08 loaded 361,200 rows — twice the
      norm — and nothing alerted. A double load is worse than a failed load: the
      pipeline reports SUCCESS and the numbers are silently doubled.

  - id: mon_freshness
    metric: load_completion_time
    condition: "> 06:00 UTC"
    severity: error
    escalation: "#revenue-data-oncall"
    note: "Ties to the FCT_ORDERS contract commitment (agent 13)."

  - id: mon_start_drift
    metric: start_time
    condition: "> 03:00 UTC"
    severity: warn
    note: >-
      2026-07-10 started at 05:41 and still met the SLA, so no error fired and
      nobody looked. A warn here surfaces the drift before it becomes a breach.

  - id: mon_run_failure
    metric: status
    condition: "= FAILED"
    severity: error
    escalation: "#revenue-data-oncall"

deliberately_not_monitored:
  - metric: duration_s
    reason: >-
      Duration correlates with row count, which is already monitored. A separate
      duration alert fires alongside it and adds noise without adding
      information.""",
            ),
        ],
        highlights=[
            "Baselines exclude the failure, the outage and the double load *before* fitting — otherwise the band widens until it detects nothing.",
            "The double-load monitor is the valuable one: a SUCCESS status with doubled numbers is worse than a failure.",
            "The 05:41 start met the SLA, so nothing fired — a warn-level drift monitor surfaces it before it becomes a breach.",
            "It declines to monitor duration because it would fire alongside row count and add noise, not information.",
        ],
        handoffs=[
            "Diagnosing the 2026-07-07 failure → 19 Root Cause Analysis Agent",
            "Freshness commitments in the contract → 13 Data Contract Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="18",
        chapter=CHAPTER,
        scenario=(
            "The new pipeline runs alongside the legacy one. Before cutover, somebody has to "
            "prove they agree — and explain every place they do not. This is the only agent "
            "that reads two estates at once."
        ),
        inputs=[
            Exhibit(
                label="Source estate — LEGACY.CUST_MAST",
                kind="database_objects",
                origin="ADE Demo Warehouse",
                format="table",
                stat="2,100 rows · 100 duplicate CUST_NO",
                body="CUST_NO, CUST_NM, ST_CD, STAT_CD, CRT_DT, BAL_AMT, RISK_IND",
            ),
            Exhibit(
                label="Target estate — ANALYTICS.DIM_CUSTOMER",
                kind="database_objects",
                origin="ADE Demo Warehouse",
                format="table",
                stat="2,000 rows · SCD2",
                note="Two slots, two estates. The only agent in the fleet shaped this way.",
                body="customer_key, customer_id, email, region_code, valid_from, valid_to, is_current",
            ),
            Exhibit(
                label="policies/tolerance.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="what counts as acceptable",
                body="""# Parity tolerance
- Row counts: exact match required for financial objects.
- Monetary aggregates: 0.01 absolute tolerance for rounding.
- Timestamps: 1 second tolerance for load-time skew.""",
            ),
        ],
        upstream=["mapping-spec.yaml — agent 09 (the equivalence definition)"],
        outputs=[
            ExampleArtifact(
                filename="reconciliation-plan.yaml",
                title="Reconciliation plan",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: ReconciliationPlan
metadata:
  source: LEGACY.CUST_MAST
  target: ANALYTICS.DIM_CUSTOMER
  equivalence: mapping-spec.yaml v1.0

checks:
  - id: rec_row_count
    type: count
    source_expr: "SELECT COUNT(DISTINCT CUST_NO) FROM LEGACY.CUST_MAST"
    target_expr: "SELECT COUNT(*) FROM ANALYTICS.DIM_CUSTOMER WHERE is_current"
    note: >-
      COUNT(DISTINCT) on the source, not COUNT(*). The legacy file has no
      enforced key and carries 100 duplicate CUST_NO values. A naive
      count-to-count comparison reports a 100-row shortfall that is not a defect.

  - id: rec_checksum_balance
    type: aggregate
    source_expr: "SELECT ROUND(SUM(BAL_AMT), 2) FROM LEGACY.CUST_MAST"
    target_expr: "SELECT ROUND(SUM(balance_usd), 2) FROM ANALYTICS.DIM_CUSTOMER WHERE is_current"
    tolerance: 0.01
    status: BLOCKED
    note: "balance_usd is not in the target model. The mapping declares it unmapped."

  - id: rec_status_distribution
    type: distribution
    dimension: STAT_CD
    tolerance: 0
    note: "Every legacy status value must appear in the target with the same count."

  - id: rec_sampled_rows
    type: stratified_sample
    sample_size: 500
    strata: [STAT_CD]
    compare: [customer_id, created_at, status]""",
            ),
            ExampleArtifact(
                filename="parity-report.md",
                title="Parity report",
                format="markdown",
                source="reasoned",
                body="""# Parity report — CUST_MAST → DIM_CUSTOMER

**Verdict: NOT READY FOR CUTOVER.** Three of five checks pass. The two that do
not are not rounding differences.

## Results

| Check | Source | Target | Result |
|---|---|---|---|
| Distinct customer count | 2,000 | 2,000 | ✅ PASS |
| Status distribution | A:1,842 C:104 S:41 D:13 | A:1,842 C:104 S:41 D:13 | ✅ PASS |
| Stratified sample (500) | — | — | ✅ PASS |
| Balance checksum | 4,182,993.55 | *(no column)* | ⛔ BLOCKED |
| Risk indicator | H:88 M:203 L:1,709 | *(no column)* | ⛔ BLOCKED |

## The 100-row difference that is not a difference

The legacy file has 2,100 rows and 2,000 distinct `CUST_NO`. The duplicates are
a property of a flat file with no enforced key — the same customer written
twice by different batch runs.

A naive `COUNT(*)` comparison reports a 100-row shortfall and someone spends a
week looking for lost customers. The plan uses `COUNT(DISTINCT)` and states why
in the check definition, so the question is answered before it is asked.

## The two blockers

Neither `BAL_AMT` nor `RISK_IND` has a target column. Agent 09 declared both
unmapped. This is not a parity failure — **it is a scope decision that has not
been made**, and cutting over now means:

- 4,182,993.55 in customer balances stops being carried forward.
- The credit risk control from rule R-002 stops running.

Parity cannot certify a migration that silently drops a credit control. The
verdict is NOT READY until commercial-ops either maps these columns or signs
that they are intentionally retired.

## What was verified rather than assumed

The stratified sample compared 500 rows across all four status values, not 500
random rows — a random sample of 2,000 would likely contain zero `D` (deceased)
records, and those are exactly the ones where legacy handling is unusual.
""",
            ),
        ],
        highlights=[
            "The only agent that takes two estates — its input contract has two required object slots.",
            "It pre-empts the phantom 100-row shortfall that would otherwise cost a week of investigation.",
            "It refuses to certify a cutover that silently drops a 1997 credit control.",
            "The sample is stratified so the rare deceased-customer cases are actually tested.",
        ],
        handoffs=[
            "Deciding whether risk belongs in the target → 09 Data Mapping Agent / commercial-ops",
            "Evidence for the migration sign-off → 28 Regulatory Evidence Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="19",
        chapter=CHAPTER,
        scenario=(
            "02:01 UTC, 7 July. The nightly load failed, the finance dashboard is stale, and "
            "three people are looking at three different screens. The agent builds the evidence "
            "chain and names the cause."
        ),
        inputs=[
            Exhibit(
                label="Incident summary",
                kind="structured_request",
                origin="Typed into the workbench by the on-call engineer",
                format="text",
                stat="what is known at 06:30",
                body="""Nightly revenue load finished with 0 rows at 02:01 UTC.
Finance dashboard is stale. Started after last night's release.
Blast radius unknown — the marketing CDP export also did not run.""",
            ),
            Exhibit(
                label="telemetry/incident_2026-07-07.log",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="text",
                stat="8 events across 12 hours",
                note="The agent reasons over evidence and cites it. It does not speculate from the summary.",
                body="""2026-07-06T18:22:04Z INFO  deploy=revenue-pipelines commit=9f2c1ab "rename customer_id to cust_id in staging"
2026-07-07T02:00:11Z INFO  task=load_fct_orders run=r_88421 starting
2026-07-07T02:00:14Z INFO  task=load_fct_orders acquired warehouse WH_ETL
2026-07-07T02:00:52Z WARN  task=load_fct_orders source REF.EXCHANGE_RATES returned 0 rows for rate_date=2026-07-06
2026-07-07T02:01:40Z ERROR task=load_fct_orders SQL compilation error: invalid identifier 'O.CUSTOMER_ID'
2026-07-07T02:01:41Z ERROR task=load_fct_orders run failed after 104s, 0 rows loaded
2026-07-07T02:01:42Z INFO  task=load_fct_orders downstream skipped: refresh_customer_360, export_marketing_cdp
2026-07-07T02:05:00Z INFO  alert=freshness_breach asset=ANALYTICS.FCT_ORDERS age_hours=26.1""",
            ),
        ],
        upstream=["lineage-graph.json — agent 04"],
        outputs=[
            ExampleArtifact(
                filename="evidence-chain.json",
                title="Evidence chain",
                format="json",
                source="reasoned",
                body="""{
  "incident": "load_fct_orders zero-row failure, 2026-07-07",
  "chain": [
    {
      "step": 1,
      "at": "2026-07-06T18:22:04Z",
      "fact": "Commit 9f2c1ab renamed customer_id to cust_id in staging.",
      "source": "incident_2026-07-07.log:1",
      "type": "observed"
    },
    {
      "step": 2,
      "at": "2026-07-07T02:01:40Z",
      "fact": "SQL compilation error: invalid identifier 'O.CUSTOMER_ID'.",
      "source": "incident_2026-07-07.log:5",
      "type": "observed"
    },
    {
      "step": 3,
      "fact": "The consuming query references o.customer_id; the rename changed the producing object only.",
      "source": "load_fct_orders.sql:5 (via lineage-graph.json)",
      "type": "observed"
    },
    {
      "step": 4,
      "fact": "A partial rename — producer changed, consumer not — is the cause.",
      "type": "concluded",
      "confidence": 0.96
    },
    {
      "step": 5,
      "at": "2026-07-07T02:01:42Z",
      "fact": "refresh_customer_360 and export_marketing_cdp were skipped.",
      "source": "incident_2026-07-07.log:7",
      "type": "observed"
    }
  ],
  "separate_finding": {
    "at": "2026-07-07T02:00:52Z",
    "fact": "REF.EXCHANGE_RATES returned 0 rows for rate_date=2026-07-06.",
    "source": "incident_2026-07-07.log:4",
    "assessment": "NOT the cause of this failure — it is a WARN and the run continued for another 48 seconds.",
    "why_it_matters": "Combined with COALESCE(rate, 1.0) in load_fct_orders.sql, this is the condition under which foreign-currency orders are silently counted as dollars. On a night the load does NOT fail, this produces wrong numbers with no error.",
    "severity": "higher than the incident being investigated"
  },
  "blast_radius": {
    "direct": ["ANALYTICS.FCT_ORDERS"],
    "downstream": ["ANALYTICS.CUSTOMER_360", "rpt_001", "rpt_003", "Marketing CDP export"],
    "derived_from": "lineage-graph.json (agent 04)"
  }
}""",
            ),
            ExampleArtifact(
                filename="root-cause-analysis.md",
                title="Root cause analysis",
                format="markdown",
                source="reasoned",
                body="""# RCA — load_fct_orders zero-row failure, 2026-07-07

## Cause

A **partial rename**. Commit `9f2c1ab` at 18:22 the previous evening renamed
`customer_id` to `cust_id` in the staging model. The consuming query in
`load_fct_orders.sql` still references `o.customer_id`, so compilation failed
at 02:01. Confidence 0.96, on three observed facts and one inference.

## Blast radius

`ANALYTICS.FCT_ORDERS` did not load. Via lineage: `CUSTOMER_360`, reports
`rpt_001` and `rpt_003`, and the Marketing CDP nightly export. Four consumer
assets, three of them named in the FCT_ORDERS contract.

## The more serious finding

At 02:00:52, 48 seconds before the failure, `REF.EXCHANGE_RATES` returned zero
rows for the prior day. That is a **WARN** and the run continued — it is not
the cause of this incident.

It matters more than the incident.

`load_fct_orders.sql` computes `amount * COALESCE(rate, 1.0)`. When the rate
lookup misses, the rate silently becomes 1.0 and a EUR order is booked as
though it were USD. **On a night when the load does not fail, this produces
wrong revenue with no error and no alert.**

This incident was loud and self-limiting. The condition underneath it is quiet
and is not. Recommend investigating how many prior nights hit the same warning.

## Why this took six hours to notice

The failure alert fired at 02:05 as a freshness breach on a 26-hour-old asset.
Nobody was paged; there is no failure-status monitor. Agent 17's proposed
`mon_run_failure` with escalation to `#revenue-data-oncall` closes that gap.

## What this agent did not do

It did not fix anything. It recommends an action *class* — revert or
roll-forward the rename — and hands the decision to agent 20, which will only
propose actions from the approved catalog and will not execute against
production.
""",
            ),
        ],
        highlights=[
            "Every step is tagged `observed` or `concluded` — a reader can see exactly where inference begins.",
            "It separates the cause from a more serious finding it noticed along the way.",
            "Blast radius comes from agent 04's lineage rather than from guesswork.",
            "It diagnoses and stops. Acting is agent 20's, and agent 20 never touches production.",
        ],
        handoffs=[
            "Choosing and planning the fix → 20 Remediation / Self-Healing Agent",
            "The missing failure monitor → 17 Anomaly & Freshness Agent",
            "Reloading the missed day → 24 Orchestration & Backfill Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="20",
        chapter=CHAPTER,
        scenario=(
            "The cause is known. The agent plans the fix — strictly from Meridian's approved "
            "action catalog, and it will not execute against production under any "
            "configuration."
        ),
        inputs=[
            Exhibit(
                label="policies/remediation-action-catalog.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="5 approved actions · 3 prohibitions",
                note="The agent will not propose an action outside this catalog.",
                body="""# Approved remediation action catalog v3.1

| ID | Action | Blast radius | Approval |
|---|---|---|---|
| A-01 | Re-run a failed task with unchanged parameters | Single task | Team lead |
| A-02 | Quarantine a partition and continue | Single partition | Team lead |
| A-03 | Revert a pipeline to the previous released version | Single pipeline | Change board |
| A-04 | Trigger a bounded backfill (<= 7 days) | Bounded | Change board |
| A-05 | Pause a downstream consumer pipeline | Downstream | Change board |

## Prohibited
- Any DDL against a production object.
- Any deletion of source data, under any circumstance.
- Unbounded backfills.""",
            ),
        ],
        upstream=["root-cause-analysis.md — agent 19", "orchestration-plan.yaml — agent 24"],
        outputs=[
            ExampleArtifact(
                filename="remediation-plan.yaml",
                title="Remediation plan",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: RemediationPlan
metadata:
  incident: load_fct_orders zero-row failure, 2026-07-07
  rca: agent 19 run r_88431
  catalog_version: "3.1"
  execution: NEVER — this plan is reviewed and executed by humans

steps:
  - order: 1
    action: A-03
    name: Revert revenue-pipelines to the release preceding 9f2c1ab
    rationale: >-
      Restores compilation immediately. Chosen over rolling the rename forward
      because the fix must land before 06:00 to meet the contract, and a
      forward fix touches two models under time pressure.
    blast_radius: single pipeline
    approval_required: change board
    reversible: yes
    verification: "Compilation succeeds; a dry run returns > 0 rows."

  - order: 2
    action: A-04
    name: Backfill 2026-07-07 only
    rationale: "One day was missed. Bounded to a single partition."
    blast_radius: "1 day, ~180k rows"
    approval_required: change board
    depends_on: [1]
    verification: "Row count within agent 17's band 177,650–183,452."

  - order: 3
    action: A-01
    name: Re-run refresh_customer_360 and export_marketing_cdp
    rationale: "Both were skipped when the upstream failed."
    approval_required: team lead
    depends_on: [2]

not_proposed:
  - description: "Complete the rename across producer and consumer, then deploy."
    reason: >-
      This is the correct permanent fix, and it is NOT a remediation action. It
      is a code change requiring review, tests and a normal release. Proposing
      it here would route a code change through an incident channel.
    routed_to: "10 Coding Agent, via the normal release process"

  - description: "Add a NOT NULL constraint to prevent the null rates."
    reason: "Prohibited — DDL against a production object is outside the catalog."

  - description: "Backfill the last 30 days to be safe."
    reason: "Prohibited — unbounded backfills. Only 2026-07-07 was missed."

open_risk:
  description: >-
    The FX COALESCE defect that agent 19 flagged as more serious than this
    incident is NOT addressed by this plan. No catalog action covers it; it
    needs a code change and a decision about whether to fail or default the row.
  routed_to: "9 Data Mapping Agent (REVIEW item) and the revenue-data-team backlog\"""",
            ),
            ExampleArtifact(
                filename="remediation-record.md",
                title="Remediation record",
                format="markdown",
                source="reasoned",
                body="""# Remediation record — 2026-07-07

**Status: AWAITING APPROVAL.** Nothing in this plan has been executed. ADE
Studio has no write path to any production system; this is a document, and a
human runs it.

## Plan

| # | Action | What | Approval |
|---|---|---|---|
| 1 | A-03 | Revert `revenue-pipelines` past `9f2c1ab` | Change board |
| 2 | A-04 | Backfill 2026-07-07 only | Change board |
| 3 | A-01 | Re-run the two skipped downstream tasks | Team lead |

Every step maps to a catalog entry. Steps 1 and 2 need change-board approval
because the catalog says so, not because this agent judged them risky.

## Three things deliberately not proposed

**Completing the rename.** That is the right permanent fix and it is a code
change, not a remediation. Routing it through an incident channel skips review
and tests. It goes to agent 10 and the normal release process.

**Adding a NOT NULL constraint.** Prohibited — DDL against production is
outside the catalog. The agent will not propose it regardless of how sensible
it looks.

**A 30-day backfill "to be safe".** Prohibited — unbounded backfills. Exactly
one day was missed and exactly one day is proposed.

## The risk this plan does not close

Agent 19 found that the FX `COALESCE(rate, 1.0)` silently books foreign-currency
orders as dollars whenever the rate lookup misses. **No action in the catalog
addresses it.** It needs a code change and a business decision about whether to
fail the row or default the rate.

That is recorded here as an open risk rather than omitted, because an incident
that closes with the loud problem fixed and the quiet one untouched is how the
quiet one survives.
""",
            ),
        ],
        highlights=[
            "Tier L3, and it still never executes — every artifact is a reviewable plan.",
            "Three sensible-looking actions are refused because the catalog prohibits them.",
            "The permanent fix is routed to the normal release process rather than through an incident channel.",
            "It closes carrying the open risk forward, rather than declaring the incident resolved.",
        ],
        handoffs=[
            "The permanent code fix → 10 Coding Agent",
            "Executing the bounded backfill → 24 Orchestration & Backfill Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="21",
        chapter=CHAPTER,
        scenario=(
            "Between two monthly snapshots, a column type changed and a new column appeared. "
            "One of those is breaking and the contract says so. The agent works out who is "
            "affected before the change ships."
        ),
        inputs=[
            Exhibit(
                label="telemetry/schema_snapshots.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="2 snapshots · 1 type change · 1 addition",
                note="Drift is a difference — a single snapshot cannot show one.",
                body="""snapshot_date,object,column,data_type,is_nullable
2026-06-01,ANALYTICS.FCT_ORDERS,order_id,NUMBER,NO
2026-06-01,ANALYTICS.FCT_ORDERS,customer_id,NUMBER,NO
2026-06-01,ANALYTICS.FCT_ORDERS,amount_usd,NUMBER(18,2),YES
2026-06-01,ANALYTICS.FCT_ORDERS,category,VARCHAR,YES
2026-07-01,ANALYTICS.FCT_ORDERS,order_id,NUMBER,NO
2026-07-01,ANALYTICS.FCT_ORDERS,customer_id,VARCHAR,NO
2026-07-01,ANALYTICS.FCT_ORDERS,amount_usd,NUMBER(18,2),YES
2026-07-01,ANALYTICS.FCT_ORDERS,category,VARCHAR,YES
2026-07-01,ANALYTICS.FCT_ORDERS,channel,VARCHAR,YES""",
            ),
        ],
        upstream=[
            "data-contract.yaml — agent 13",
            "lineage-graph.json — agent 04",
        ],
        outputs=[
            ExampleArtifact(
                filename="impact-matrix.json",
                title="Impact matrix",
                format="json",
                source="reasoned",
                body="""{
  "object": "ANALYTICS.FCT_ORDERS",
  "compared": ["2026-06-01", "2026-07-01"],
  "changes": [
    {
      "column": "customer_id",
      "change": "type_narrowed",
      "from": "NUMBER",
      "to": "VARCHAR",
      "contract_verdict": "BREAKING",
      "contract_clause": "narrowing a type — 30 days' notice required",
      "notice_given": false,
      "impacted": [
        { "asset": "ANALYTICS.CUSTOMER_360", "type": "view", "how": "joins on customer_id", "severity": "error" },
        { "asset": "rpt_001 Revenue by Category", "type": "report", "owner": "priya@meridian.example", "severity": "error" },
        { "asset": "rpt_003 Revenue by Category FINAL v2", "type": "report", "owner": "raj@meridian.example", "severity": "error" },
        { "asset": "Marketing CDP nightly export", "type": "pipeline", "owner": "dana@meridian.example", "severity": "error" }
      ],
      "why_it_breaks": "A NUMBER-to-VARCHAR join still compiles in Snowflake via implicit cast, but '1001' and 1001 do not compare equal after leading-zero padding. This fails as wrong results, not as an error."
    },
    {
      "column": "channel",
      "change": "column_added",
      "nullable": true,
      "contract_verdict": "NON_BREAKING",
      "contract_clause": "adding a nullable column",
      "impacted": [],
      "note": "No notice required. Consumers using SELECT * will see a new column; the contract does not protect against that and the house style forbids SELECT * in committed models."
    }
  ],
  "summary": { "breaking": 1, "non_breaking": 1, "consumers_requiring_notice": 3 }
}""",
            ),
            ExampleArtifact(
                filename="drift-report.md",
                title="Drift report",
                format="markdown",
                source="reasoned",
                body="""# Schema drift — ANALYTICS.FCT_ORDERS, June → July

## One breaking change shipped without notice

`customer_id` changed from `NUMBER` to `VARCHAR`. The contract classifies type
narrowing as breaking and requires **30 days' notice to three named
consumers**. No notice was given.

### Why this is worse than a broken build

A `NUMBER`-to-`VARCHAR` join **still compiles**. Snowflake casts implicitly, so
nothing errors. But `'01001'` and `1001` do not match, and any source that
zero-pads produces silent join misses — rows quietly vanish from the result.

This is the failure mode that shows up as "revenue looks a bit low this month"
and takes three weeks to trace.

### Who needs telling

| Consumer | Owner | Asset |
|---|---|---|
| Commercial BI | priya@meridian.example | rpt_001, rpt_003 |
| Finance close | finance-systems@meridian.example | Monthly statutory pack |
| Marketing CDP | dana@meridian.example | Nightly export |

## One non-breaking change

`channel` was added as nullable. The contract explicitly permits this without
notice. Recorded so the change log is complete, not because anyone must act.

## What this agent did not do

It did not revert anything and did not open a pull request against the
producing model. It detects and reports impact; deciding what to do is a human
call, and executing it belongs to the normal release process.
""",
            ),
        ],
        highlights=[
            "The breaking change still compiles — it fails as wrong results, which is the expensive kind.",
            "Impact is resolved to named consumers with contacts, from the contract and the lineage graph.",
            "It classifies against Meridian's own contract clauses rather than a generic notion of 'breaking'.",
        ],
        handoffs=[
            "The contract clauses being enforced → 13 Data Contract Agent",
            "Consumer impact paths → 04 Lineage Reconstruction Agent",
        ],
    ),
]
