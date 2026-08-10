"""Chapter 4 — Operations. Run it economically (agents 22–25)."""

from __future__ import annotations

from app.domain.canvas import Exhibit, ExampleArtifact, WorkedExample

CHAPTER = "4 · Operations — run it economically"

_METERING = """date,warehouse,credits,cost_usd,queries,owner_tag
2026-07-01,WH_ETL,412.5,825.00,1840,data-platform
2026-07-01,WH_BI,118.0,236.00,9210,analytics
2026-07-01,WH_ADHOC,96.5,193.00,412,
2026-07-02,WH_ETL,438.0,876.00,1902,data-platform
2026-07-02,WH_BI,121.5,243.00,9455,analytics
2026-07-02,WH_ADHOC,142.0,284.00,388,
2026-07-03,WH_ETL,905.0,1810.00,1877,data-platform
2026-07-03,WH_BI,119.0,238.00,9301,analytics
2026-07-03,WH_ADHOC,88.5,177.00,401,
2026-07-04,WH_ETL,441.0,882.00,1863,data-platform
2026-07-04,WH_BI,120.0,240.00,9388,analytics
2026-07-04,WH_ADHOC,101.0,202.00,377,"""

EXAMPLES: list[WorkedExample] = [
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="22",
        chapter=CHAPTER,
        scenario=(
            "Meridian's platform bill grew 40% in a quarter and finance wants it attributed to "
            "teams. The agent computes every figure from the metering export — and finds a "
            "one-day spike nobody had noticed."
        ),
        inputs=[
            Exhibit(
                label="telemetry/warehouse_metering.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="12 rows · 4 days · 3 warehouses · $6,206.00 total",
                note="Every number the agent reports is counted from this file, not estimated.",
                body=_METERING,
            ),
            Exhibit(
                label="policies/tag-taxonomy.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="ownership tags + budgets",
                body="""# Cost ownership
- Every warehouse carries an `owner_tag` matching a team in the ownership registry.
- Untagged spend is charged to the platform budget by default.
- FY26 targets: data-platform $28,000/mo · analytics $8,000/mo · unallocated < 5%.""",
            ),
        ],
        outputs=[
            ExampleArtifact(
                filename="savings-opportunities.json",
                title="Savings opportunities",
                format="json",
                source="reasoned",
                body="""{
  "period": "2026-07-01 to 2026-07-04",
  "measured": {
    "total_cost_usd": 6206.00,
    "total_credits": 3103.0,
    "by_warehouse": [
      { "warehouse": "WH_ETL",   "cost_usd": 4393.00, "share": 0.708, "queries": 7482 },
      { "warehouse": "WH_BI",    "cost_usd": 957.00,  "share": 0.154, "queries": 37354 },
      { "warehouse": "WH_ADHOC", "cost_usd": 856.00,  "share": 0.138, "queries": 1578 }
    ],
    "note": "Counted from warehouse_metering.csv. No estimation."
  },

  "opportunities": [
    {
      "id": "FIN-001",
      "title": "WH_ETL spike on 2026-07-03",
      "observed": "905.0 credits versus a 4-day median of 438.0 — 2.07x, on 1,877 queries versus a 1,875 median.",
      "inference": "Cost doubled while query count did not move. That is a per-query cost change, not more work — consistent with a warehouse resize or a query plan regression.",
      "estimated_recoverable_usd_per_month": 4110.00,
      "confidence": 0.72,
      "next_step": "Handed to agent 23. Identifying which query regressed is model-level tuning, not cost attribution."
    },
    {
      "id": "FIN-002",
      "title": "WH_ADHOC is untagged",
      "observed": "$856.00 over 4 days, owner_tag empty on every row.",
      "inference": "13.8% of spend is unattributable. The policy target is under 5%.",
      "estimated_recoverable_usd_per_month": 0.00,
      "note": "This recovers no money. It makes the money visible, which is what enables the conversation about whether 1,578 ad-hoc queries are worth $6,400/month.",
      "confidence": 0.99
    },
    {
      "id": "FIN-003",
      "title": "WH_BI cost per query is 43x better than WH_ADHOC",
      "observed": "WH_BI $0.026/query over 37,354 queries. WH_ADHOC $0.542/query over 1,578.",
      "inference": "Ad-hoc queries are long-running and un-cached. Not necessarily waste — exploration is legitimate — but the ratio is worth a conversation.",
      "confidence": 0.85
    }
  ],

  "not_claimed": [
    "No projection beyond the 4 measured days. A 4-day window cannot establish a monthly run rate; the monthly figures above are 4-day observations scaled, and are labelled as such wherever they appear."
  ]
}""",
            ),
            ExampleArtifact(
                filename="cost-analysis.md",
                title="Cost analysis",
                format="markdown",
                source="reasoned",
                body="""# Platform cost analysis — 1–4 July 2026

**$6,206.00 over four days.** Every figure here is counted from the metering
export. Where something is scaled or inferred, it says so.

## Where it goes

| Warehouse | Cost | Share | Queries | $/query |
|---|---|---|---|---|
| `WH_ETL` | $4,393.00 | 70.8% | 7,482 | $0.587 |
| `WH_BI` | $957.00 | 15.4% | 37,354 | $0.026 |
| `WH_ADHOC` | $856.00 | 13.8% | 1,578 | $0.542 |

## The finding

**`WH_ETL` cost doubled on 3 July and nothing else moved.** 905 credits against
a 438 median — 2.07× — on 1,877 queries against a 1,875 median.

Same work, twice the money. That is a per-query cost change, which means either
the warehouse was resized or a query plan regressed. Extrapolated over a month
it is roughly **$4,110** of recoverable spend, and nobody noticed because the
bill is reviewed monthly and one day inside a month does not stand out.

Identifying *which* query is agent 23's job. This agent owns attribution, not
model-level tuning, and the handoff is deliberate.

## The 13.8% nobody owns

`WH_ADHOC` has no `owner_tag` on any row — $856 over four days against a policy
target of under 5% unallocated.

Tagging it recovers no money. It makes the money visible, which is what turns
"the platform bill is up" into "ad-hoc exploration costs us $6,400 a month, is
that what we want". That is the conversation worth having.

## What is not claimed

Four days is not a run rate. The monthly figures above are four-day
observations scaled by 7.5 and are labelled as extrapolations everywhere they
appear. Give this agent a full billing period and it will stop extrapolating.
""",
            ),
        ],
        highlights=[
            "The spike is found by comparing cost against query volume — the same work at twice the price.",
            "It hands query-level tuning to agent 23 rather than straying outside cost attribution.",
            "One opportunity recovers no money and is included anyway, because visibility is the point.",
            "It refuses to present a 4-day window as a monthly run rate.",
        ],
        handoffs=[
            "Which query regressed → 23 Performance Tuning Agent",
            "Storage tiering and retention economics → 25 Capacity & Retention Agent",
            "Enforcing a budget freeze → a human owner; no agent takes this on",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="23",
        chapter=CHAPTER,
        scenario=(
            "Agent 22 found the cost. Now find the query. The agent reads execution history and "
            "proposes changes it can benchmark, refusing the ones it cannot."
        ),
        inputs=[
            Exhibit(
                label="telemetry/query_history.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="6 queries · 1 accidental cross join",
                note="Tuning without measurements is guessing.",
                body="""query_id,user,warehouse,elapsed_ms,bytes_scanned,rows,statement
q_1001,svc_etl,WH_ETL,412000,88123456789,182450,INSERT INTO ANALYTICS.FCT_ORDERS SELECT ...
q_1002,analyst_a,WH_BI,38200,2312456789,1204,SELECT * FROM ANALYTICS.CUSTOMER_360 WHERE lifetime_value > 1000
q_1003,analyst_b,WH_BI,41100,2298113456,1188,SELECT * FROM ANALYTICS.CUSTOMER_360 WHERE last_order_ts > CURRENT_DATE - 30
q_1004,svc_bi,WH_BI,712000,44123456789,88213,SELECT category SUM(amount_usd) FROM ANALYTICS.FCT_ORDERS GROUP BY 1
q_1005,analyst_a,WH_ADHOC,1841000,192334455667,4,SELECT COUNT(*) FROM RAW.ORDERS o JOIN RAW.ORDER_ITEMS i ON 1=1
q_1006,svc_etl,WH_ETL,412000,87991234567,180551,INSERT INTO ANALYTICS.FCT_ORDERS SELECT ...""",
            ),
        ],
        upstream=["savings-opportunities.json — agent 22", "lineage-graph.json — agent 04"],
        outputs=[
            ExampleArtifact(
                filename="recommended-changes.sql",
                title="Recommended changes",
                format="sql",
                source="reasoned",
                body="""-- Tuning recommendations · derived from query_history.csv
-- Every change below is benchmarkable. Nothing is applied.

-- ─────────────────────────────────────────────────────────────────────
-- 1. q_1005 — accidental cross join. 192 GB scanned to return 4 rows.
-- ─────────────────────────────────────────────────────────────────────
-- Current (ON 1=1 is a cross join, almost certainly unintended):
--   SELECT COUNT(*) FROM RAW.ORDERS o JOIN RAW.ORDER_ITEMS i ON 1=1;
--
-- Intended, on the evidence of every other join in the estate:
    SELECT COUNT(*)
    FROM RAW.ORDERS o
    JOIN RAW.ORDER_ITEMS i ON i.order_id = o.order_id;
-- Expected: 192 GB -> ~0.4 GB scanned, 1,841s -> ~3s.
-- NOTE: this changes the ANSWER, not just the plan. 4 rows was the count of a
-- cartesian product. The author must confirm the intent before this is applied.

-- ─────────────────────────────────────────────────────────────────────
-- 2. q_1004 — full scan for a category aggregate run every hour.
-- ─────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS ANALYTICS.MV_REVENUE_BY_CATEGORY AS
SELECT category, DATE_TRUNC('day', order_ts) AS order_date,
       SUM(amount_usd) AS amount_usd, COUNT(*) AS order_lines
FROM ANALYTICS.FCT_ORDERS
GROUP BY 1, 2;
-- Expected: 44 GB -> ~0.1 GB per execution, 712s -> ~2s.
-- Cost: MV maintenance on every FCT_ORDERS load. Break-even at ~6 executions
-- per day; observed frequency is hourly, so this pays for itself.

-- ─────────────────────────────────────────────────────────────────────
-- 3. q_1002 / q_1003 — SELECT * on a wide view.
-- ─────────────────────────────────────────────────────────────────────
-- Both scan ~2.3 GB to return ~1,200 rows. Projecting only the used columns
-- would cut this, but the used columns are not knowable from the history —
-- the statements are literally SELECT *. Recommendation is to the authors,
-- not a rewrite this agent can benchmark.

-- ─────────────────────────────────────────────────────────────────────
-- NOT RECOMMENDED
-- ─────────────────────────────────────────────────────────────────────
-- Resizing WH_ETL. Agent 22 observed the 2026-07-03 cost doubling, but
-- q_1001 and q_1006 both ran 412,000 ms with near-identical bytes scanned on
-- either side of the spike. The ETL queries did not regress. Whatever changed
-- on 07-03 is not visible in this history, and recommending a resize on this
-- evidence would be guessing.""",
            ),
            ExampleArtifact(
                filename="tuning-plan.md",
                title="Tuning plan",
                format="markdown",
                source="reasoned",
                body="""# Tuning plan — Meridian warehouse

## Ranked by measured waste

| # | Query | Scanned | Elapsed | Returned | Finding |
|---|---|---|---|---|---|
| 1 | `q_1005` | 192 GB | 1,841 s | 4 rows | Cross join (`ON 1=1`) |
| 2 | `q_1004` | 44 GB | 712 s | 88,213 rows | Hourly full scan |
| 3 | `q_1002/3` | 2.3 GB | ~40 s | ~1,200 rows | `SELECT *` on a wide view |

## The one that matters

`q_1005` scanned **192 GB to return four rows**. The join condition is `ON 1=1`
— a cartesian product between two tables, almost certainly a typo for
`ON i.order_id = o.order_id`.

The fix is one line. The caveat is important: **it changes the answer.** Four
rows was the count of a cross product; the corrected query returns something
else entirely. The author must confirm intent — this agent will not silently
change a number someone may have reported.

## What I did not find

Agent 22 handed over the 2026-07-03 `WH_ETL` cost doubling. **The ETL queries
did not regress.** `q_1001` and `q_1006` bracket the spike at 412,000 ms with
near-identical bytes scanned.

Whatever changed on 3 July is not in this query history — a warehouse resize, a
concurrency change, or something outside the captured window. Recommending a
resize on this evidence would be guessing, and a confident wrong recommendation
is worse than an honest gap.

**Requested:** warehouse configuration history for 2–4 July.

## Cost of the recommendations

The materialized view is not free. It is maintained on every `FCT_ORDERS` load
and break-even is roughly six executions per day. Observed frequency is hourly,
so it pays for itself — but that break-even is stated so the trade-off is
visible rather than assumed.
""",
            ),
        ],
        highlights=[
            "The cross join returns four rows from 192 GB — and the fix changes the answer, which is called out rather than glossed.",
            "It reports what it could NOT find and requests the specific data that would close the gap.",
            "The materialized view's maintenance cost and break-even point are both stated.",
        ],
        handoffs=[
            "Cost attribution and budgets → 22 FinOps Agent",
            "Impact of the materialization change → 04 Lineage Reconstruction Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="24",
        chapter=CHAPTER,
        scenario=(
            "The FX bug means Q1 revenue was converted at the wrong rate. Finance wants it "
            "rebuilt. The agent plans the backfill around the dependency graph and the freeze "
            "calendar — and asks for the reason, not just the range."
        ),
        inputs=[
            Exhibit(
                label="Backfill request",
                kind="structured_request",
                origin="Typed into the workbench by finance-ops",
                format="text",
                stat="scope · reason · requester",
                note="The agent will not infer an intent. Scope without a reason is refused.",
                body="""Rebuild fct_orders for 2026-01-01 to 2026-03-31.
Currency conversion was wrong before the 04-02 fix — EUR and GBP orders were
booked at rate 1.0 whenever the rate lookup missed.
Requested by finance-ops for the Q1 restatement. Needed before the 15th.""",
            ),
            Exhibit(
                label="telemetry/orchestrator_state.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="freeze windows and current DAG state",
                body="""window_start,window_end,type,detail
2026-07-11T00:00Z,2026-07-13T23:59Z,FREEZE,Quarter-end close — no production changes
2026-07-14T01:00Z,2026-07-14T03:00Z,MAINTENANCE,Platform upgrade
current_dag,,RUNNING,load_fct_orders scheduled daily 02:00Z""",
            ),
        ],
        upstream=["lineage-graph.json — agent 04", "ingestion-design.yaml — agent 15"],
        outputs=[
            ExampleArtifact(
                filename="orchestration-plan.yaml",
                title="Orchestration plan",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: BackfillPlan
metadata:
  requester: finance-ops
  reason: "Q1 restatement — FX conversion defect before the 2026-04-02 fix"
  scope: "ANALYTICS.FCT_ORDERS, 2026-01-01 to 2026-03-31 (90 days)"
  deadline: 2026-07-15

window:
  earliest_start: 2026-07-14T03:00Z
  reason: >-
    2026-07-11 to 07-13 is a quarter-end freeze and 07-14 01:00-03:00 is
    platform maintenance. The first clear slot is 07-14 03:00Z, which leaves
    roughly 45 hours before the deadline.

batching:
  strategy: monthly
  batches: [2026-01, 2026-02, 2026-03]
  reason: >-
    A single 90-day batch is ~16.2M rows and would hold WH_ETL for an estimated
    6-7 hours, colliding with the 02:00 nightly load. Monthly batches run in
    ~2 hours each and can be paused between.
  parallelism: 1
  parallelism_reason: "Sequential. The three batches write the same table and the same partitions."

downstream:
  action: pause_then_refresh
  paused_during_backfill:
    - refresh_customer_360
    - export_marketing_cdp
  reason: >-
    Both read FCT_ORDERS. Leaving them running would export partially-restated
    Q1 data to the marketing CDP, where it cannot be recalled.
  refresh_after: [refresh_customer_360, export_marketing_cdp]

verification:
  - "Row count per month within agent 17's daily band, summed."
  - "SUM(amount_usd) for Q1 differs from the pre-backfill value — if it does NOT, the FX fix did not take effect and the backfill achieved nothing."
  - "No order rows with currency <> 'USD' and rate = 1.0."

rollback:
  method: "Restore from Time Travel to the pre-backfill timestamp."
  retention_required_hours: 72
  note: "Snowflake Time Travel default is 24h. Extend to 72h BEFORE starting, or there is no rollback."

blocking_question:
  question: "Does the Q1 restatement need the original values preserved for audit?"
  why: "An in-place backfill overwrites them. If audit needs both, this becomes a versioned load, which is a different plan."
  owner: finance
  status: unanswered""",
            ),
            ExampleArtifact(
                filename="backfill-runbook.md",
                title="Backfill runbook",
                format="markdown",
                source="reasoned",
                body="""# Backfill runbook — Q1 FX restatement

**Do not start until the blocking question below is answered.**

## Before you begin

1. **Extend Time Travel on `ANALYTICS.FCT_ORDERS` to 72 hours.** The default is
   24. Three sequential monthly batches plus verification exceeds 24 hours, so
   with the default there is no rollback for January by the time March runs.
2. Confirm the FX fix is deployed. Backfilling with the defect still present
   rewrites the same wrong numbers and consumes the window.
3. Pause `refresh_customer_360` and `export_marketing_cdp`.

## Execution — 2026-07-14 from 03:00Z

| Batch | Range | Est. rows | Est. duration | Verify before continuing |
|---|---|---|---|---|
| 1 | 2026-01 | ~5.4M | ~2h | Row count, FX check |
| 2 | 2026-02 | ~5.0M | ~2h | Row count, FX check |
| 3 | 2026-03 | ~5.8M | ~2h | Row count, FX check |

Sequential, not parallel — all three write the same table. Verify after each;
do not chain them unattended.

## The verification that actually matters

`SUM(amount_usd)` for Q1 **must differ** from its pre-backfill value. If it
comes back identical, the FX fix did not take effect and the backfill has spent
six hours rewriting the same wrong numbers. Capture the before-value first.

## Why downstream is paused

`export_marketing_cdp` pushes to an external system. A partially-restated Q1
export cannot be recalled once it has left. Pausing costs one day of freshness;
not pausing costs a data-correction exercise in someone else's platform.

## The question that blocks this

**Does the restatement need the original values kept for audit?** An in-place
backfill overwrites them. If audit needs both, this is a versioned load and the
plan is different. Finance owns the answer. This agent will not assume it.
""",
            ),
        ],
        highlights=[
            "It plans around the freeze calendar rather than the requested date, and says which windows it avoided.",
            "The Time Travel extension is a precondition — without it, January has no rollback by the time March runs.",
            "The key verification is that the number *changed*: an identical sum means the backfill achieved nothing.",
            "It blocks on an audit question rather than assuming an in-place overwrite is acceptable.",
        ],
        handoffs=[
            "Executing this plan → a human, via the orchestrator",
            "Actions available during an incident → 20 Remediation / Self-Healing Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="25",
        chapter=CHAPTER,
        scenario=(
            "Storage has grown 3x in a year. The agent identifies archive candidates from access "
            "history rather than age — and refuses to touch anything under legal hold."
        ),
        inputs=[
            Exhibit(
                label="telemetry/storage_metering.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="6 objects · size and last-read",
                note="Archive candidates come from access, not from age alone.",
                body="""object,size_gb,rows,last_read,reads_90d,monthly_cost_usd
ANALYTICS.FCT_ORDERS,842.0,197000000,2026-07-10,18420,1936.60
ANALYTICS.CUSTOMER_360,12.4,2000,2026-07-10,9204,28.52
LEGACY.CUST_MAST,3.1,2100,2026-02-14,2,7.13
AUDIT.LOAD_LOG,410.0,880000000,2026-01-08,0,943.00
RAW.ORDERS_ARCHIVE_2019,1204.0,290000000,2024-11-02,0,2769.20
STAGE.TMP_CUSTOMER_MERGE,88.0,4100000,2026-03-19,0,202.40""",
            ),
            Exhibit(
                label="policies/retention-and-legal-hold.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="4 data classes · 1 active hold",
                body="""# Retention and legal-hold policy

| Data class | Minimum | Maximum | Basis |
|---|---|---|---|
| Financial transactions | 7 years | 10 years | SOX |
| Customer personal data | Relationship | +2 years | GDPR minimisation |
| Pipeline logs | 90 days | 1 year | Operational |

## Legal holds in force
- `LEGACY.CUST_MAST` — hold LH-2026-004, opened 2026-03-11. No deletion or
  archival permitted while open.""",
            ),
        ],
        upstream=["data-contract.yaml — agent 13", "retention-policy.yaml — agent 27"],
        outputs=[
            ExampleArtifact(
                filename="capacity-forecast.json",
                title="Capacity forecast",
                format="json",
                source="reasoned",
                body="""{
  "measured": {
    "total_gb": 2559.5,
    "total_monthly_cost_usd": 5886.85,
    "note": "Counted from storage_metering.csv."
  },

  "candidates": [
    {
      "object": "RAW.ORDERS_ARCHIVE_2019",
      "size_gb": 1204.0,
      "monthly_cost_usd": 2769.20,
      "last_read": "2024-11-02",
      "reads_90d": 0,
      "recommendation": "Move to external stage / cold storage",
      "estimated_saving_usd_per_month": 2492.28,
      "confidence": 0.88,
      "retention_check": "2019 financial transactions — 7-year minimum expires 2026-12-31. Archive, do NOT delete.",
      "blocking": false
    },
    {
      "object": "AUDIT.LOAD_LOG",
      "size_gb": 410.0,
      "monthly_cost_usd": 943.00,
      "reads_90d": 0,
      "recommendation": "Apply the 1-year retention maximum the policy already sets",
      "estimated_saving_usd_per_month": 786.00,
      "confidence": 0.91,
      "retention_check": "Pipeline logs: 90-day minimum, 1-year maximum. 880M rows implies retention well beyond the maximum — the policy exists and is not enforced.",
      "blocking": false
    },
    {
      "object": "STAGE.TMP_CUSTOMER_MERGE",
      "size_gb": 88.0,
      "monthly_cost_usd": 202.40,
      "last_read": "2026-03-19",
      "recommendation": "Drop — staging remnant, unread for 4 months",
      "estimated_saving_usd_per_month": 202.40,
      "confidence": 0.75,
      "caveat": "Named like a one-off migration table. Confirm with the revenue-data-team that the merge it staged is complete."
    }
  ],

  "refused": [
    {
      "object": "LEGACY.CUST_MAST",
      "size_gb": 3.1,
      "reads_90d": 2,
      "why_it_looks_like_a_candidate": "Last read 2026-02-14, effectively unused, small.",
      "refusal": "LEGAL HOLD LH-2026-004, opened 2026-03-11. No archival or deletion permitted while the hold is open. Not proposed at any size or cost.",
      "escalation": "Legal owns the hold. This agent does not evaluate whether it should still be open."
    }
  ],

  "total_recoverable_usd_per_month": 3480.68,
  "share_of_storage_spend": 0.591
}""",
            ),
            ExampleArtifact(
                filename="retention-plan.md",
                title="Retention plan",
                format="markdown",
                source="reasoned",
                body="""# Retention plan — Meridian storage

**$5,886.85/month across 2,559 GB. $3,480.68/month is recoverable — 59% of
storage spend.**

## What to act on

| Object | Action | Saving/mo | Confidence |
|---|---|---|---|
| `RAW.ORDERS_ARCHIVE_2019` | Move to cold storage | $2,492.28 | 0.88 |
| `AUDIT.LOAD_LOG` | Enforce the existing 1-year maximum | $786.00 | 0.91 |
| `STAGE.TMP_CUSTOMER_MERGE` | Drop after confirmation | $202.40 | 0.75 |

`AUDIT.LOAD_LOG` is worth a sentence: **the policy already caps pipeline logs
at one year.** 880 million rows says it has never been enforced. This is not a
new policy proposal, it is applying one Meridian already wrote.

## What I will not touch

`LEGACY.CUST_MAST` is under **legal hold LH-2026-004**, opened 11 March 2026.

On every signal this agent uses it looks like a candidate — last read in
February, two reads in ninety days, tiny. It is not proposed, at any size, at
any cost. A legal hold is not a factor to weigh against savings; it is a stop.

Whether the hold should still be open is a question for legal. This agent does
not have an opinion on it.

## Archive, never delete

`RAW.ORDERS_ARCHIVE_2019` holds 2019 financial transactions. SOX sets a
seven-year minimum, which does not expire until 31 December 2026. The
recommendation is explicitly **archive to cold storage**, not delete — the
saving comes from the storage tier, not from destroying records.
""",
            ),
        ],
        highlights=[
            "The legal hold is a stop, not a factor to weigh — the object is refused at any size or cost.",
            "The largest log saving comes from enforcing a policy Meridian already wrote and never applied.",
            "Archive versus delete is kept distinct: the SOX minimum has not expired.",
        ],
        handoffs=[
            "Whether the legal hold should remain open → legal; no agent takes this on",
            "Regulatory retention requirements → 27 Privacy & Retention Agent",
        ],
    ),
]
