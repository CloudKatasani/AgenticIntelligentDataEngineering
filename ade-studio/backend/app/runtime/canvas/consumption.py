"""Chapter 6 — Consumption. Make it usable (agents 30–32)."""

from __future__ import annotations

from app.domain.canvas import Exhibit, ExampleArtifact, WorkedExample

CHAPTER = "6 · Consumption — make it usable"

EXAMPLES: list[WorkedExample] = [
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="30",
        chapter=CHAPTER,
        scenario=(
            "Meridian's BI estate has three reports called some variation of 'Revenue by "
            "Category'. Nobody knows which is authoritative. The agent clusters them on "
            "structure and usage, and refuses to retire anything on similarity alone."
        ),
        inputs=[
            Exhibit(
                label="telemetry/bi_inventory.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="6 reports · 3 near-duplicates · 1 orphan",
                body="""report_id,name,workspace,owner,last_opened,views_30d,source_objects
rpt_001,Revenue by Category,Commercial,priya@meridian.example,2026-07-09,412,ANALYTICS.FCT_ORDERS
rpt_002,Revenue by Category (copy),Commercial,raj@meridian.example,2026-03-02,3,ANALYTICS.FCT_ORDERS
rpt_003,Revenue by Category FINAL v2,Commercial,raj@meridian.example,2026-07-08,388,ANALYTICS.FCT_ORDERS
rpt_004,Customer LTV,Marketing,dana@meridian.example,2026-07-10,204,ANALYTICS.CUSTOMER_360
rpt_005,Customer LTV OLD,Marketing,,2025-11-14,0,ANALYTICS.CUSTOMER_360
rpt_006,Ops Freshness Monitor,Data Platform,dana@meridian.example,2026-07-10,96,AUDIT.LOAD_LOG""",
            ),
        ],
        upstream=["lineage-graph.json — agent 04", "semantic-model.yaml — agent 12"],
        outputs=[
            ExampleArtifact(
                filename="dashboard-inventory.csv",
                title="Dashboard inventory",
                format="csv",
                source="reasoned",
                body="""report_id,name,owner,views_30d,cluster,recommendation,confidence,blocker
rpt_001,Revenue by Category,priya@meridian.example,412,revenue-by-category,KEEP — primary,0.91,
rpt_003,Revenue by Category FINAL v2,raj@meridian.example,388,revenue-by-category,INVESTIGATE — actively used duplicate,0.55,two live reports both in use
rpt_002,Revenue by Category (copy),raj@meridian.example,3,revenue-by-category,RETIRE — 3 views in 30d,0.86,
rpt_004,Customer LTV,dana@meridian.example,204,customer-ltv,KEEP,0.93,
rpt_005,Customer LTV OLD,,0,customer-ltv,RETIRE — unowned and unopened since 2025-11,0.94,no owner to confirm with
rpt_006,Ops Freshness Monitor,dana@meridian.example,96,operations,KEEP — no duplicates,0.95,""",
            ),
            ExampleArtifact(
                filename="rationalization-report.md",
                title="Rationalization report",
                format="markdown",
                source="reasoned",
                body="""# BI rationalization — Meridian

**6 reports, 2 duplicate clusters, 2 clear retirement candidates.**

## The cluster worth talking about

Three reports share the name "Revenue by Category" and the same source object.
Usage separates them cleanly:

| Report | Owner | Views (30d) | Verdict |
|---|---|---|---|
| `rpt_001` Revenue by Category | priya | 412 | Keep |
| `rpt_003` …FINAL v2 | raj | 388 | **Investigate** |
| `rpt_002` …(copy) | raj | 3 | Retire |

`rpt_002` is a copy nobody opens. Straightforward.

**`rpt_001` and `rpt_003` are the interesting case.** Both are actively used —
412 and 388 views — by different owners, over the same source. That is not
clutter, it is two teams who each believe they have the authoritative revenue
report, and they may well produce different numbers.

Agent 12 found the same split at the metric layer: `Revenue`, `Revenue (net)`
and `Total Revenue` were three definitions of one thing. These two dashboards
are almost certainly that disagreement rendered as pixels.

**Recommendation: do not retire either.** Reconcile the definitions first
(agent 12 has done that), then retire whichever no longer matches the governed
metric. Retiring an actively used report to tidy an inventory is how a BI
rationalization programme loses its mandate in week two.

## The easy one

`rpt_005 Customer LTV OLD` — **no owner**, not opened since November 2025, zero
views in 30 days. Retire.

The lack of an owner is itself the finding: there is nobody to confirm with,
and an unowned dashboard on `CUSTOMER_360` is an unowned exposure of RESTRICTED
columns.

## What I did not do

I did not cluster on name similarity alone. `rpt_006 Ops Freshness Monitor`
reads `AUDIT.LOAD_LOG` and has no structural sibling, so it is untouched
despite being small and low-traffic. Low usage is not duplication.
""",
            ),
        ],
        highlights=[
            "It refuses to retire two actively-used reports, and explains that they are a metric disagreement rather than clutter.",
            "The unowned dashboard is flagged as an ownership finding, not just a cleanup item.",
            "Low usage is explicitly not treated as duplication.",
        ],
        handoffs=[
            "Reconciling the competing revenue definitions → 12 Semantic Layer Agent",
            "Who can read the unowned dashboard's source → 26 Access & Entitlement Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="31",
        chapter=CHAPTER,
        scenario=(
            "A commercial analyst asks a question in plain language. The agent answers from "
            "certified assets only, cites what it used, and runs as the asking user's role — "
            "not as a service account."
        ),
        inputs=[
            Exhibit(
                label="Analyst question",
                kind="structured_request",
                origin="Typed into the workbench by priya@meridian.example (role: FINANCE_ANALYST)",
                format="text",
                stat="natural language",
                body="Which product categories grew fastest in EMEA last quarter?",
            ),
            Exhibit(
                label="ANALYTICS scope",
                kind="database_objects",
                origin="ADE Demo Warehouse",
                format="table",
                stat="optional narrowing",
                body="ANALYTICS.FCT_ORDERS · ANALYTICS.DIM_CUSTOMER · ANALYTICS.DIM_PRODUCT",
            ),
        ],
        upstream=["semantic-model.yaml — agent 12", "data-product-manifest.yaml — agent 29"],
        outputs=[
            ExampleArtifact(
                filename="generated-query.sql",
                title="Generated query",
                format="sql",
                source="reasoned",
                body="""-- Question: which product categories grew fastest in EMEA last quarter?
-- Metrics: net_revenue (governed, agent 12)
-- Executed as: FINANCE_ANALYST. Row access and masking policies apply.
--
-- ⚠ THIS QUERY CANNOT BE RUN AS WRITTEN. See query-explanation.md.
--    DIM_CUSTOMER.region_code is an unmapped gap (agent 09), so "EMEA"
--    has no column to filter on.

WITH quarterly AS (
    SELECT
        p.category,
        DATE_TRUNC('quarter', d.date_actual)                 AS quarter,
        SUM(f.net_amount_usd - f.discount_amount_usd)        AS net_revenue
    FROM ANALYTICS.FCT_ORDER_LINE f
    JOIN ANALYTICS.DIM_PRODUCT  p ON p.product_key  = f.product_key
    JOIN ANALYTICS.DIM_CUSTOMER c ON c.customer_key = f.customer_key
    JOIN ANALYTICS.DIM_DATE     d ON d.date_key     = f.date_key
    WHERE c.region_code = 'EMEA'          -- ⚠ column is not populated
      AND c.is_current                     -- SCD2: current version only
      AND d.date_actual >= DATEADD(quarter, -2, DATE_TRUNC('quarter', CURRENT_DATE))
    GROUP BY 1, 2
)

SELECT
    category,
    net_revenue                                              AS current_quarter,
    LAG(net_revenue) OVER (PARTITION BY category ORDER BY quarter) AS prior_quarter,
    ROUND(
        (net_revenue - LAG(net_revenue) OVER (PARTITION BY category ORDER BY quarter))
        / NULLIF(LAG(net_revenue) OVER (PARTITION BY category ORDER BY quarter), 0) * 100,
    1)                                                       AS growth_pct
FROM quarterly
QUALIFY quarter = DATE_TRUNC('quarter', DATEADD(quarter, -1, CURRENT_DATE))
ORDER BY growth_pct DESC;""",
            ),
            ExampleArtifact(
                filename="query-explanation.md",
                title="Query explanation",
                format="markdown",
                source="reasoned",
                body="""# "Which product categories grew fastest in EMEA last quarter?"

## I cannot answer this yet, and here is precisely why

The query is written and correct. It cannot run, because **`region_code` is not
populated** — agent 09 declared it an unmapped GAP and agent 12 marked the
`sales_region` dimension BLOCKED for the same reason.

There is no column in the certified estate that means EMEA.

## What I refused to do

I could have written `WHERE c.country_code IN ('FR','DE','ES','IT','NL', ...)`.
It would have run, returned numbers, and looked like an answer.

It would also have been **my guess at Meridian's region definition**, and
Meridian's actual EMEA grouping lives in a spreadsheet this agent has never
seen. The analyst would have quoted the number in a QBR.

A wrong answer that looks right is worse than a refusal.

## What I did use

- **`net_revenue`** — the governed metric from agent 12, which is
  `SUM(net_amount_usd - discount_amount_usd)`. Not `Revenue` or `Total Revenue`
  from the old BI estate; those had different definitions.
- **`is_current`** on the SCD2 dimension, so a customer who changed region does
  not drag their history with them.
- **Certified assets only.** `RETAIL.CUSTOMERS` also has a `country_code` and
  is not certified, so it was not considered.

## Access

The query runs as `FINANCE_ANALYST`, the asking user's effective role — not as
a service account. Masking policies apply: if this analyst is not entitled to
see an email address, they will not see one, and the agent does not need to
know that in advance.

## To make this answerable

Supply the region lookup. Agent 09's mapping names it as the blocker, and one
table closes it.
""",
            ),
        ],
        highlights=[
            "It refuses to invent a region grouping, and explains that a plausible answer would have been quoted in a QBR.",
            "It uses the governed metric rather than any of the three legacy BI definitions.",
            "It runs as the asking user's role, so entitlements apply without the agent knowing them.",
            "The blocker is named precisely: one lookup table makes the question answerable.",
        ],
        handoffs=[
            "Supplying the region lookup → 09 Data Mapping Agent",
            "Certifying the assets it may use → 29 Data Product Publishing Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="32",
        chapter=CHAPTER,
        scenario=(
            "Two requests land in the data team's queue. The agent triages them into scoped "
            "stories — and finds that one is already answered by an asset that exists."
        ),
        inputs=[
            Exhibit(
                label="Inbound requests",
                kind="structured_request",
                origin="Pasted into the workbench from the ticket queue",
                format="text",
                stat="2 tickets",
                body="""DATA-1182 (Sales): We need a churn dashboard by customer segment. Ideally
weekly. We keep asking for this and it never gets prioritised.

DATA-1187 (Finance): Daily margin by SKU, self-serve. We currently export
CSVs from three places and reconcile them in a spreadsheet every morning.""",
            ),
        ],
        upstream=[
            "data-product-manifest.yaml — agent 29",
            "semantic-model.yaml — agent 12",
            "data-dictionary.md — agent 03",
        ],
        outputs=[
            ExampleArtifact(
                filename="intake-ticket.yaml",
                title="Intake tickets",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: IntakeTickets

tickets:
  - id: DATA-1182
    title: Churn dashboard by customer segment
    requester: Sales
    verdict: NEEDS_DEFINITION
    blocking_question:
      question: "What is churn at Meridian?"
      detail: >-
        No governed term for churn exists (agent 05's glossary has Customer and
        Active customer, not churn). Without a definition this could mean no
        order in 90 days, an explicit cancellation, or a subscription lapse.
        Each implies different data and a different answer.
      owner: commercial-ops
    also_blocked_by:
      - "DIM_CUSTOMER.segment is UNMAPPED (agent 09) — there is no segment column to group by."
    estimated_after_unblocking: "M — one fact extension plus a dashboard"
    note: >-
      The requester says this 'never gets prioritised'. The likelier reading is
      that it has been picked up several times and stalled on the same two
      questions. Stating them explicitly is more useful than another estimate.

  - id: DATA-1187
    title: Daily margin by SKU, self-serve
    requester: Finance
    verdict: PARTIALLY_ANSWERED_BY_EXISTING_ASSET
    existing:
      asset: ANALYTICS.FCT_ORDER_LINE
      why: >-
        Order-line grain with product_key already supports revenue by SKU per
        day. The governed metric net_revenue (agent 12) covers the revenue half.
      gap: "Cost of goods is not in the model, so margin cannot be computed."
    estimated: "S — add a cost measure, then it is a semantic-layer definition"
    recommendation: >-
      Do not build a new pipeline. Extend the existing fact with unit cost and
      define margin as a governed metric. The three CSV exports Finance is
      reconciling are a symptom of the missing metric, not of missing data.""",
            ),
            ExampleArtifact(
                filename="triage-note.md",
                title="Triage note",
                format="markdown",
                source="reasoned",
                body="""# Triage — DATA-1182, DATA-1187

## DATA-1187 is nearly free

Finance want daily margin by SKU and are reconciling three CSV exports by hand
every morning.

**Most of that already exists.** `ANALYTICS.FCT_ORDER_LINE` is at order-line
grain with a product key, and `net_revenue` is already a governed metric. The
only missing piece is cost of goods.

Add a cost measure, define `margin` in the semantic layer, and the manual
reconciliation stops. That is a small change, not a project — and it retires a
daily manual process, which makes it the highest-value item in the queue.

The three CSV exports are the tell: when people export and reconcile by hand,
the usual cause is a missing *definition*, not missing data.

## DATA-1182 is not a prioritisation problem

Sales say the churn dashboard "never gets prioritised". More likely it has been
picked up repeatedly and stalled on the same two questions:

1. **What is churn?** There is no governed definition. No order in 90 days, an
   explicit cancellation, and a subscription lapse are three different
   questions with three different answers.
2. **`DIM_CUSTOMER.segment` has no source.** Agent 09 declared it UNMAPPED, so
   there is nothing to group by.

Neither is an engineering constraint. Both need a commercial-ops decision, and
until they are made, any estimate is fiction.

## What this triage deliberately does not do

It does not estimate DATA-1182. An estimate on an undefined requirement is a
number that will be quoted back later, and the honest answer is "we can size
this the day churn has a definition".
""",
            ),
        ],
        highlights=[
            "One request is largely answered by an asset that already exists — the manual CSV reconciliation is a missing metric, not missing data.",
            "The other is reframed: it is not a prioritisation problem, it is two unanswered business questions.",
            "It refuses to estimate an undefined requirement rather than producing a number that gets quoted back.",
        ],
        handoffs=[
            "Defining churn as a governed term → 05 Glossary & Semantic Alignment Agent",
            "Adding the margin metric → 12 Semantic Layer Agent",
        ],
    ),
]
