"""Chapter 1 — Discovery. Find out what is actually there (agents 01–06)."""

from __future__ import annotations

from app.domain.canvas import Exhibit, ExampleArtifact, WorkedExample

CHAPTER = "1 · Discovery — find out what is actually there"

EXAMPLES: list[WorkedExample] = [
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="01",
        chapter=CHAPTER,
        scenario=(
            "Meridian has registered its retail source. Nobody can say which columns are "
            "trustworthy, whether customer_id is really unique, or how bad the email data is. "
            "Profiling is the first move because every other agent reasons over its output."
        ),
        inputs=[
            Exhibit(
                label="ADE_DEMO.RETAIL.CUSTOMERS",
                kind="database_objects",
                origin="ADE Demo Warehouse (read-only service account)",
                format="table",
                stat="2,000 rows · 12 columns · sampled 200",
                note="Read-only. The connector rejects any statement that could mutate a source.",
                body="""customer_id | first_name | last_name | email                        | phone            | national_id | country_code
------------+------------+-----------+------------------------------+------------------+-------------+-------------
       1001 | Amara      | Osei      | amara.osei1001@example.com   | +1-415-555-0142  | 412-88-3391 | US
       1002 | Tomas      | Novak     | tomas.novak1002@example.com  | (415) 555-0177   | 233-41-9902 | CZ
       1003 | Priya      | Raman     | (null)                       | 4155550118       | 601-22-7745 | IN
       1004 | Lars       | Andersen  | lars.andersen@@invalid       | +1-628-555-0193  | 388-90-1123 | DK
       1005 | Wei        | Chen      | wei.chen1005@example.com     | (628) 555-0164   | 505-63-8810 | SG""",
            ),
        ],
        outputs=[
            ExampleArtifact(
                filename="profile.json",
                title="Statistical profile",
                format="json",
                source="deterministic",
                note="Every number here was counted by the profiler. No model touched it.",
                body="""{
  "table": "ADE_DEMO.RETAIL.CUSTOMERS",
  "row_count": 2000,
  "sampled_rows": 200,
  "sample_strategy": "first 200 rows of 2000",
  "candidate_primary_keys": [
    { "column": "customer_id", "confidence": 1.0, "evidence": "unique and non-null across 200 sampled rows" }
  ],
  "columns": [
    {
      "column": "customer_id", "data_type": "BIGINT",
      "null_count": 0, "null_ratio": 0.0,
      "distinct_count": 200, "distinct_ratio": 1.0,
      "min_value": "1", "max_value": "200", "is_candidate_key": true
    },
    {
      "column": "email", "data_type": "VARCHAR",
      "null_count": 8, "null_ratio": 0.04,
      "distinct_count": 192, "distinct_ratio": 0.96,
      "sample_patterns": ["email (186/192 matched)"],
      "is_candidate_key": false
    },
    {
      "column": "phone", "data_type": "VARCHAR",
      "null_count": 0, "null_ratio": 0.0,
      "distinct_count": 200, "distinct_ratio": 1.0,
      "sample_patterns": ["us_phone (67/200 matched)", "digits_only (66/200 matched)"],
      "is_candidate_key": true
    },
    {
      "column": "national_id", "data_type": "VARCHAR",
      "null_count": 0, "null_ratio": 0.0,
      "distinct_count": 200, "distinct_ratio": 1.0,
      "sample_patterns": ["ssn_like (200/200 matched)"],
      "is_candidate_key": true
    }
  ]
}""",
            ),
            ExampleArtifact(
                filename="inferred-constraints.yaml",
                title="Inferred constraint set",
                format="yaml",
                source="reasoned",
                note="Confidence and evidence on every candidate — a reviewer can audit the call.",
                body="""apiVersion: ade/v1
kind: InferredConstraints
metadata:
  object: ADE_DEMO.RETAIL.CUSTOMERS
  basis: 200 sampled rows of 2,000

primary_key_candidates:
  - column: customer_id
    confidence: 0.98
    evidence: "distinct_ratio=1.0, null_ratio=0.0 across the sample"
    recommendation: promote to PRIMARY KEY

  - column: national_id
    confidence: 0.30
    evidence: "unique in sample, but semantically a person identifier"
    recommendation: >-
      Do NOT promote. Uniqueness here is a property of the sample, not a
      business rule — two records for the same person would collide. Agent 02
      is expected to classify this column as RESTRICTED.

not_null_candidates:
  - { column: customer_id, confidence: 0.98 }
  - { column: country_code, confidence: 0.95 }

rejected:
  - column: email
    reason: "4% null in sample; cannot be NOT NULL without a data fix first"
""",
            ),
            ExampleArtifact(
                filename="profiling-run-report.md",
                title="Profiling run report",
                format="markdown",
                source="reasoned",
                note="Interpretation of the numbers — and an explicit statement of what it did not do.",
                body="""# Profiling run report — ADE_DEMO.RETAIL.CUSTOMERS

**Coverage:** 1 of 1 requested object profiled. No objects skipped.
**Sample:** first 200 rows of 2,000 (10%). Volumetrics below are sample-scaled
and marked where that matters.

## What the numbers say

**`customer_id` is your key.** Unique and non-null across every sampled row.
Nothing else in this table qualifies on evidence rather than coincidence.

**`email` is 4% missing and 3% malformed.** Eight sampled rows are null; six
more match the shape `name@@domain` — a doubled `@`, which is a data-entry
defect rather than a formatting variant. At table scale that is roughly 80
missing and 60 malformed addresses.

**`phone` has three competing formats.** `+1-415-555-0142`, `(415) 555-0177`
and `4155550118` all appear. No single parse will work; standardisation is
needed before this column can be matched or dialled.

**`national_id` is US SSN-shaped in 100% of sampled rows.** This is a
classification concern, not a profiling one — flagged here and handed off.

## Sampling caveat

The first-200-rows strategy is cheap and was sufficient to establish key
candidates. It is **not** safe for distribution claims: if the table is loaded
in insertion order, the sample is the oldest customers. Re-profile with a
random sample before using these distributions to set quality thresholds.
""",
            ),
        ],
        highlights=[
            "Every number in profile.json was counted, not generated — the artifact records `source: deterministic`.",
            "The agent refuses to promote national_id to a key despite it being unique in the sample, and says why.",
            "It states its own sampling limitation rather than letting the reader over-trust the distributions.",
        ],
        handoffs=[
            "Sensitivity labels on national_id → 02 Data Classification Agent",
            "Business descriptions for these columns → 03 Catalog & Documentation Agent",
            "Quality thresholds derived from these distributions → 16 Data Quality Rules Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="02",
        chapter=CHAPTER,
        scenario=(
            "The profile shows an SSN-shaped column sitting in the analytics estate. Before "
            "anyone builds on it, Meridian needs every column labelled against their own "
            "taxonomy — not a generic one — with the regulation that drives each label."
        ),
        inputs=[
            Exhibit(
                label="ADE_DEMO.RETAIL.CUSTOMERS",
                kind="database_objects",
                origin="ADE Demo Warehouse",
                format="table",
                stat="12 columns in scope",
                note="Scope only. The statistics arrive from agent 01 through the context layer.",
                body="""customer_id, first_name, last_name, email, phone, national_id,
date_of_birth, city, country_code, marketing_opt_in, signup_date, lifetime_value""",
            ),
            Exhibit(
                label="policies/sensitivity-taxonomy.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="4 labels · 3 regulations · 3 standing rules",
                note="Meridian's own taxonomy. Without it the agent falls back to a generic model and says so.",
                body="""# Sensitivity taxonomy — Meridian Data Governance

| Label | Definition | Handling |
|---|---|---|
| PUBLIC | Publishable without restriction. | No control. |
| INTERNAL | Default for business data. | Authenticated access only. |
| CONFIDENTIAL | Commercially sensitive. | Named roles; reviewed quarterly. |
| RESTRICTED | Personal or regulated data. | Masking required; reviewed monthly. |

## Rules
1. A column containing a national identifier is RESTRICTED without exception.
2. A customer email address is RESTRICTED; an internal distribution list is INTERNAL.
3. A derived column inherits the highest sensitivity of its inputs.""",
            ),
        ],
        upstream=["profile.json — agent 01 (statistics and detected patterns)"],
        outputs=[
            ExampleArtifact(
                filename="classification.json",
                title="Column classification",
                format="json",
                source="reasoned",
                note="Every label cites the taxonomy rule and the profiled evidence behind it.",
                body="""{
  "object": "ADE_DEMO.RETAIL.CUSTOMERS",
  "taxonomy": "Meridian Data Governance v4",
  "columns": [
    {
      "column": "national_id",
      "label": "RESTRICTED",
      "regulations": ["GDPR Art.4(1)", "CCPA §1798.140(o)"],
      "confidence": 0.97,
      "evidence": "profile: ssn_like pattern matched 200/200 sampled values",
      "rule_applied": "Rule 1 — a national identifier is RESTRICTED without exception",
      "masking": "required — tokenize or drop before any analytics consumer"
    },
    {
      "column": "email",
      "label": "RESTRICTED",
      "regulations": ["GDPR Art.4(1)"],
      "confidence": 0.94,
      "evidence": "profile: email pattern matched 186/192 non-null values; customer-facing table",
      "rule_applied": "Rule 2 — a customer email address is RESTRICTED",
      "masking": "required for non-privileged roles"
    },
    {
      "column": "date_of_birth",
      "label": "RESTRICTED",
      "regulations": ["GDPR Art.4(1)"],
      "confidence": 0.91,
      "evidence": "DATE column named date_of_birth on a customer entity",
      "rule_applied": "Rule 1 by analogy — combined with name and city this is directly identifying",
      "masking": "generalize to birth year for analytics use"
    },
    {
      "column": "lifetime_value",
      "label": "CONFIDENTIAL",
      "regulations": [],
      "confidence": 0.88,
      "evidence": "derived commercial measure; not personally identifying on its own",
      "rule_applied": "Taxonomy default for commercially sensitive measures"
    },
    {
      "column": "marketing_opt_in",
      "label": "RESTRICTED",
      "regulations": ["GDPR Art.7", "ePrivacy"],
      "confidence": 0.86,
      "evidence": "consent flag — its value is the legal basis for processing",
      "rule_applied": "Rule 1 by analogy",
      "note": "Consent state is itself regulated; it must not be defaulted or backfilled."
    },
    { "column": "customer_id", "label": "INTERNAL", "confidence": 0.95,
      "evidence": "surrogate key, no external meaning", "regulations": [] },
    { "column": "country_code", "label": "INTERNAL", "confidence": 0.93,
      "evidence": "ISO country code, low cardinality", "regulations": [] }
  ],
  "unresolved": [
    {
      "column": "city",
      "question": "INTERNAL alone, or RESTRICTED in combination with date_of_birth and country_code?",
      "reason": "Quasi-identifier. The taxonomy does not cover combination risk; a human must decide.",
      "owner": "Meridian Data Governance"
    }
  ]
}""",
            ),
            ExampleArtifact(
                filename="sensitive-data-register.md",
                title="Sensitive data register",
                format="markdown",
                source="reasoned",
                note="The version a DPO reads. Same content, no JSON.",
                body="""# Sensitive data register — RETAIL.CUSTOMERS

**Status: PROPOSAL.** Agent 02 operates at tier L1. These labels take effect
only when a named human accepts them.

## Regulated columns

| Column | Label | Basis | Required handling |
|---|---|---|---|
| `national_id` | RESTRICTED | GDPR Art.4(1), CCPA | Tokenize or drop before analytics |
| `email` | RESTRICTED | GDPR Art.4(1) | Mask for non-privileged roles |
| `date_of_birth` | RESTRICTED | GDPR Art.4(1) | Generalize to birth year |
| `marketing_opt_in` | RESTRICTED | GDPR Art.7, ePrivacy | Never default or backfill |
| `lifetime_value` | CONFIDENTIAL | Commercial | Named roles only |

## The finding that needs attention

`national_id` is a US-format identifier sitting **unmasked in a table that
feeds the analytics estate**. Agent 04's lineage shows `RETAIL.CUSTOMERS`
flowing into `ANALYTICS.CUSTOMER_360`, which agent 26 shows is granted to
`PUBLIC`. That chain is the actual exposure; each link on its own looks
harmless.

## One question for a human

`city` is INTERNAL on its own. Combined with `date_of_birth` and
`country_code` it is a quasi-identifier that can re-identify individuals in a
small population. The taxonomy does not address combination risk. **Meridian
Data Governance must decide** — this agent will not decide it by default.
""",
            ),
        ],
        highlights=[
            "Runs at tier L1, so the output is a proposal in `awaiting_approval` — labels are not applied until a human accepts.",
            "Every label cites the taxonomy rule and the profiled evidence, so a DPO can audit each one.",
            "It escalates the quasi-identifier question rather than guessing, and names the owner.",
            "On a source marked regulated, this agent is capped at L1 regardless of measured accuracy.",
        ],
        handoffs=[
            "Grants that expose these columns → 26 Access & Entitlement Agent",
            "Retention periods for personal data → 27 Privacy & Retention Agent",
            "How these columns propagate downstream → 04 Lineage Reconstruction Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="03",
        chapter=CHAPTER,
        scenario=(
            "Meridian's catalog has 40% column coverage and most descriptions read 'customer "
            "id'. The agent writes descriptions grounded in how the columns are actually "
            "queried, and reconciles against the existing docs instead of trusting them."
        ),
        inputs=[
            Exhibit(
                label="ADE_DEMO.RETAIL.CUSTOMERS",
                kind="database_objects",
                origin="ADE Demo Warehouse",
                format="table",
                stat="12 columns to describe",
                body="customer_id, email, phone, national_id, lifetime_value, signup_date, marketing_opt_in, …",
            ),
            Exhibit(
                label="telemetry/query_history.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="6 queries · 2 distinct consumers",
                note="Turns 'what a column is' into 'what it is used for'.",
                body="""query_id,user,warehouse,elapsed_ms,statement
q_1002,analyst_a,WH_BI,38200,SELECT * FROM ANALYTICS.CUSTOMER_360 WHERE lifetime_value > 1000
q_1003,analyst_b,WH_BI,41100,SELECT * FROM ANALYTICS.CUSTOMER_360 WHERE last_order_ts > CURRENT_DATE - 30
q_1004,svc_bi,WH_BI,712000,SELECT category, SUM(amount_usd) FROM ANALYTICS.FCT_ORDERS GROUP BY 1""",
            ),
            Exhibit(
                label="Existing column comments",
                kind="policy_document",
                origin="Catalog export",
                format="text",
                stat="3 of 12 columns documented",
                note="Framed to the model as untrusted data, never as instructions.",
                body="""customer_id     -- "customer id"
lifetime_value  -- "LTV. Updated nightly by the CRM sync."
marketing_opt_in -- "opt in flag (legacy: 1=yes 0=no, now boolean)\"""",
            ),
        ],
        upstream=["profile.json — agent 01", "lineage-graph.json — agent 04 (when available)"],
        outputs=[
            ExampleArtifact(
                filename="catalog-entries.json",
                title="Catalog entries",
                format="json",
                source="reasoned",
                note="Loadable straight into the catalog; each entry carries its evidence.",
                body="""{
  "object": "ADE_DEMO.RETAIL.CUSTOMERS",
  "description": "One row per registered retail customer. Populated by the CRM sync and, for pre-2019 customers, by the mainframe CUST_MAST extract. Not restricted to customers who have ordered — see the governed definition of Customer, which is narrower.",
  "columns": [
    {
      "column": "customer_id",
      "description": "Surrogate key assigned by the CRM at registration. Stable for the life of the customer. Not the mainframe CUST_NO — see lineage for the join.",
      "evidence": "profile: unique, non-null; lineage: joined to LEGACY.CUST_MAST.CUST_NO in load_fct_orders.sql",
      "confidence": 0.94
    },
    {
      "column": "lifetime_value",
      "description": "Cumulative net order value in USD, excluding tax, refunds and cancelled orders. Refreshed nightly by the CRM sync — it is not computed from ANALYTICS.FCT_ORDERS and will disagree with it.",
      "evidence": "existing comment (unverified) + query history: filtered by 2 of 3 BI consumers",
      "confidence": 0.71,
      "flag": "DISAGREEMENT — see data-dictionary.md"
    },
    {
      "column": "marketing_opt_in",
      "description": "Consent to marketing contact. Boolean today; rows loaded before the 2023 CRM migration carried 1/0 integers and were cast on load.",
      "evidence": "existing comment (unverified); profile: BOOLEAN, no nulls",
      "confidence": 0.83
    },
    {
      "column": "phone",
      "description": "Primary contact number. Stored as entered, in three competing formats — not normalised. Any matching or dialling use needs standardisation first.",
      "evidence": "profile: us_phone matched 67/200, digits_only 66/200",
      "confidence": 0.92
    }
  ]
}""",
            ),
            ExampleArtifact(
                filename="data-dictionary.md",
                title="Data dictionary",
                format="markdown",
                source="reasoned",
                note="The disagreement section is the point — existing docs were reconciled, not trusted.",
                body="""# Data dictionary — RETAIL.CUSTOMERS

One row per registered retail customer.

| Column | Business meaning | Confidence |
|---|---|---|
| `customer_id` | CRM surrogate key, stable for life | 0.94 |
| `email` | Primary contact address. 4% missing, 3% malformed | 0.96 |
| `phone` | Contact number, three formats, not normalised | 0.92 |
| `lifetime_value` | Cumulative net order value, USD, CRM-sourced | 0.71 ⚠ |
| `marketing_opt_in` | Marketing consent. Pre-2023 rows cast from 1/0 | 0.83 |

## Where the existing documentation disagrees with the data

The catalog comment on `lifetime_value` says "Updated nightly by the CRM sync".
Query history shows two BI consumers filtering on it as though it were the
authoritative revenue measure, while `ANALYTICS.FCT_ORDERS` computes revenue
independently from order lines.

**These two numbers will not match**, and nothing currently says so. The
existing comment is not wrong — it is incomplete in the way that causes an
argument in a steering meeting.

Recorded as an open question rather than resolved here: which is authoritative
is a business decision, and agent 05 owns the governed definition.

## What this dictionary deliberately does not do

It does not assign sensitivity labels — those are agent 02's, and they exist
for these columns already. It does not define *Customer* as a business term;
that is the governed glossary, owned by agent 05.
""",
            ),
        ],
        highlights=[
            "Existing documentation is treated as untrusted input — reconciled against the data, not repeated.",
            "It surfaces a live disagreement (two competing revenue numbers) that nobody had written down.",
            "Query history turns descriptions from 'what the column is' into 'what it is used for'.",
        ],
        handoffs=[
            "The governed definition of Customer → 05 Glossary & Semantic Alignment Agent",
            "Sensitivity labels → 02 Data Classification Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="04",
        chapter=CHAPTER,
        scenario=(
            "Nobody at Meridian can answer 'if I change RAW.ORDERS, what breaks?'. There is no "
            "lineage tool. The agent reconstructs it by parsing the warehouse code — it reads "
            "code, not rows."
        ),
        inputs=[
            Exhibit(
                label="warehouse-code/load_fct_orders.sql",
                kind="code_artifacts",
                origin="Sample artifacts / warehouse-code (shared drive)",
                format="sql",
                stat="26 lines · 3 statements · 7 objects referenced",
                note="Comments are stripped before parsing, so prose cannot become a false edge.",
                body="""-- Nightly load: RAW -> ANALYTICS
CREATE OR REPLACE TABLE ANALYTICS.FCT_ORDERS AS
SELECT
    o.order_id, o.customer_id, o.order_ts,
    o.amount * COALESCE(r.rate, 1.0) AS amount_usd,
    p.category
FROM RAW.ORDERS o
JOIN RAW.ORDER_ITEMS i  ON i.order_id = o.order_id
JOIN RAW.PRODUCTS p     ON p.product_id = i.product_id
LEFT JOIN REF.EXCHANGE_RATES r
       ON r.currency = o.currency
      AND r.rate_date = CAST(o.order_ts AS DATE);

-- Legacy customers are appended from the mainframe extract.
INSERT INTO ANALYTICS.DIM_CUSTOMER
SELECT CUST_NO, CUST_NM, ST_CD, CRT_DT FROM LEGACY.CUST_MAST;

INSERT INTO AUDIT.LOAD_LOG
SELECT 'FCT_ORDERS', CURRENT_TIMESTAMP(), COUNT(*) FROM ANALYTICS.FCT_ORDERS;""",
            ),
            Exhibit(
                label="warehouse-code/customer_360.sql",
                kind="code_artifacts",
                origin="Sample artifacts / warehouse-code",
                format="sql",
                stat="12 lines · 1 view · 2 objects read",
                body="""CREATE OR REPLACE VIEW ANALYTICS.CUSTOMER_360 AS
SELECT
    c.customer_id, c.email,
    c.national_id,          -- flagged as PII by agent 02
    SUM(f.amount_usd) AS lifetime_value,
    MAX(f.order_ts)    AS last_order_ts
FROM ANALYTICS.DIM_CUSTOMER c
LEFT JOIN ANALYTICS.FCT_ORDERS f ON f.customer_id = c.customer_id
GROUP BY 1, 2, 3;""",
            ),
        ],
        outputs=[
            ExampleArtifact(
                filename="lineage-graph.json",
                title="Lineage graph",
                format="json",
                source="reasoned",
                note="Edges parsed from an AST, each with the file and confidence behind it.",
                body="""{
  "nodes": [
    { "id": "RAW.ORDERS", "type": "table", "layer": "raw" },
    { "id": "RAW.ORDER_ITEMS", "type": "table", "layer": "raw" },
    { "id": "RAW.PRODUCTS", "type": "table", "layer": "raw" },
    { "id": "REF.EXCHANGE_RATES", "type": "table", "layer": "reference" },
    { "id": "LEGACY.CUST_MAST", "type": "table", "layer": "legacy" },
    { "id": "ANALYTICS.FCT_ORDERS", "type": "table", "layer": "analytics" },
    { "id": "ANALYTICS.DIM_CUSTOMER", "type": "table", "layer": "analytics" },
    { "id": "ANALYTICS.CUSTOMER_360", "type": "view", "layer": "consumption" },
    { "id": "AUDIT.LOAD_LOG", "type": "table", "layer": "audit" }
  ],
  "edges": [
    { "from": "RAW.ORDERS", "to": "ANALYTICS.FCT_ORDERS", "type": "derives",
      "confidence": 1.0, "evidence": "load_fct_orders.sql:6 FROM clause (parsed)" },
    { "from": "RAW.ORDER_ITEMS", "to": "ANALYTICS.FCT_ORDERS", "type": "derives",
      "confidence": 1.0, "evidence": "load_fct_orders.sql:7 JOIN (parsed)" },
    { "from": "RAW.PRODUCTS", "to": "ANALYTICS.FCT_ORDERS", "type": "derives",
      "confidence": 1.0, "evidence": "load_fct_orders.sql:8 JOIN (parsed)" },
    { "from": "REF.EXCHANGE_RATES", "to": "ANALYTICS.FCT_ORDERS", "type": "enriches",
      "confidence": 1.0, "evidence": "load_fct_orders.sql:9 LEFT JOIN (parsed)",
      "column_level": "amount_usd = amount * COALESCE(rate, 1.0)" },
    { "from": "LEGACY.CUST_MAST", "to": "ANALYTICS.DIM_CUSTOMER", "type": "appends",
      "confidence": 1.0, "evidence": "load_fct_orders.sql:15 INSERT INTO (parsed)" },
    { "from": "ANALYTICS.DIM_CUSTOMER", "to": "ANALYTICS.CUSTOMER_360", "type": "derives",
      "confidence": 1.0, "evidence": "customer_360.sql:6 FROM (parsed)" },
    { "from": "ANALYTICS.FCT_ORDERS", "to": "ANALYTICS.CUSTOMER_360", "type": "derives",
      "confidence": 1.0, "evidence": "customer_360.sql:7 LEFT JOIN (parsed)" }
  ],
  "unresolved": [
    { "object": "ANALYTICS.DIM_CUSTOMER",
      "issue": "Written by an INSERT with no matching CREATE in the supplied artifacts",
      "impact": "Its full upstream set is unknown; another job may also write it" }
  ]
}""",
            ),
            ExampleArtifact(
                filename="lineage-report.md",
                title="Lineage reconstruction report",
                format="markdown",
                source="reasoned",
                note="States its coverage limit plainly — 2 files parsed, not the whole estate.",
                body="""# Lineage reconstruction — Meridian warehouse

**Parsed:** 2 SQL files, 3 statements, 9 objects, 7 edges. All edges are
AST-derived; none are inferred from naming.

## The chain that matters

```
RAW.ORDERS ─┐
RAW.ORDER_ITEMS ─┼─▶ ANALYTICS.FCT_ORDERS ─┐
RAW.PRODUCTS ─┘                            ├─▶ ANALYTICS.CUSTOMER_360
REF.EXCHANGE_RATES ─(enriches)─┘           │
LEGACY.CUST_MAST ──▶ ANALYTICS.DIM_CUSTOMER┘
```

**`LEGACY.CUST_MAST` reaches `CUSTOMER_360` in two hops.** The mainframe
extract everyone assumes is decommissioned is two joins away from the
customer-facing view. That is the single most useful fact on this page.

## Column-level finding

`amount_usd` is `amount * COALESCE(rate, 1.0)`. When the exchange-rate lookup
misses, **the rate silently becomes 1.0** and a EUR order is counted as though
it were dollars. There is no error and no null — the number is simply wrong.
The incident log for 2026-07-07 shows `REF.EXCHANGE_RATES` returning zero rows
for the prior day, which is exactly this condition.

## Coverage limit

Two files were supplied. This is the lineage of *those files*, not of the
estate. `ANALYTICS.DIM_CUSTOMER` is written by an INSERT with no CREATE in
scope, so something outside the supplied set also writes it. Do not read the
absence of an edge as the absence of a dependency.
""",
            ),
        ],
        highlights=[
            "Reads code, not rows — no database object is selected anywhere in this run.",
            "The COALESCE finding is a silent-correctness bug found by reading one expression.",
            "It states its coverage limit: absence of an edge is not absence of a dependency.",
            "Comment stripping is why `-- appended from the mainframe` did not become a table called `the`.",
        ],
        handoffs=[
            "Business rules embedded in the legacy artifacts → 06 Source System Interrogation Agent",
            "Impact of a schema change on these paths → 21 Schema Drift & Impact Agent",
            "The 2026-07-07 incident this explains → 19 Root Cause Analysis Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="05",
        chapter=CHAPTER,
        scenario=(
            "Marketing and finance both report 'active customers' and get different numbers. "
            "The governed glossary says 12 months; marketing has been using 24. The agent binds "
            "governed terms to physical columns and reports where the estate disagrees."
        ),
        inputs=[
            Exhibit(
                label="policies/business-glossary.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="5 governed terms · 2 stewards",
                note="The authority. The agent binds to it; it does not invent terms.",
                body="""# Governed business glossary — extract

## Customer
A party that has placed at least one completed order. Steward: commercial-ops.
Excludes prospects and closed accounts. Version 4.2, approved 2026-02-10.

## Active customer
A Customer with a completed order in the trailing 12 months. Steward:
commercial-ops. Note: the marketing team uses a 24-month definition in their
own reporting; the governed definition is 12 months.

## Lifetime value
Sum of net order value in USD across the whole relationship, excluding tax,
refunds and cancelled orders. Steward: finance. Version 2.0.""",
            ),
            Exhibit(
                label="ADE_DEMO.RETAIL.CUSTOMERS",
                kind="database_objects",
                origin="ADE Demo Warehouse",
                format="table",
                stat="optional scope narrowing",
                body="customer_id, lifetime_value, signup_date, marketing_opt_in, …",
            ),
        ],
        upstream=["profile.json — agent 01", "catalog-entries.json — agent 03"],
        outputs=[
            ExampleArtifact(
                filename="glossary-terms.yaml",
                title="Glossary terms",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: GlossaryTerms
metadata:
  source: Meridian governed glossary v4.2
  note: >-
    Terms are transcribed from the governed glossary, not authored here. Where
    this agent proposes a change it is marked `proposed` and left unapplied.

terms:
  - term: Customer
    definition: A party that has placed at least one completed order.
    steward: commercial-ops
    version: "4.2"
    excludes: [prospects, closed accounts]

  - term: Active customer
    definition: A Customer with a completed order in the trailing 12 months.
    steward: commercial-ops
    version: "4.2"
    conflict:
      observed: "Marketing reporting uses a trailing 24-month window."
      governed: "12 months."
      impact: "Marketing's active count is ~1.9x the governed figure."
      resolution: human — commercial-ops owns this term

  - term: Lifetime value
    definition: >-
      Sum of net order value in USD across the whole relationship, excluding
      tax, refunds and cancelled orders.
    steward: finance
    version: "2.0"

proposed:
  - term: Registered customer
    rationale: >-
      RETAIL.CUSTOMERS holds 2,000 rows, but the governed Customer definition
      requires a completed order. The physical table is a superset with no
      governed name, which is why two teams can both be "right" about a count.
    status: proposed — requires commercial-ops approval""",
            ),
            ExampleArtifact(
                filename="term-bindings.json",
                title="Term-to-column bindings",
                format="json",
                source="reasoned",
                body="""{
  "bindings": [
    {
      "term": "Lifetime value",
      "binds_to": "ANALYTICS.CUSTOMER_360.lifetime_value",
      "confidence": 0.62,
      "status": "CONTESTED",
      "evidence": "Name matches exactly, but two physical columns claim this term.",
      "detail": "RETAIL.CUSTOMERS.lifetime_value is CRM-maintained; ANALYTICS.CUSTOMER_360.lifetime_value is SUM(FCT_ORDERS.amount_usd). The governed definition excludes refunds; neither implementation demonstrably does.",
      "action": "finance to designate the authoritative column before this term is certified"
    },
    {
      "term": "Customer",
      "binds_to": "ANALYTICS.DIM_CUSTOMER",
      "confidence": 0.55,
      "status": "MISMATCH",
      "evidence": "DIM_CUSTOMER includes rows appended from LEGACY.CUST_MAST regardless of order history.",
      "detail": "The governed definition requires a completed order. This table does not filter on that, so it implements 'Registered customer', not 'Customer'.",
      "action": "either rename the physical object or approve the proposed term"
    },
    {
      "term": "Active customer",
      "binds_to": null,
      "confidence": 0.0,
      "status": "UNBOUND",
      "evidence": "No physical column or view implements a trailing-window flag.",
      "detail": "Every consumer computes it inline, which is how the 12/24-month divergence went unnoticed for so long.",
      "action": "candidate for a semantic-layer metric — handed to agent 12"
    }
  ],
  "summary": { "bound": 0, "contested": 1, "mismatched": 1, "unbound": 1 }
}""",
            ),
        ],
        highlights=[
            "Zero clean bindings out of three — and that is the valuable result, not a failure.",
            "It explains *why* two teams both believe they are right about the active-customer count.",
            "It proposes a new term rather than silently redefining a governed one, and marks it unapplied.",
        ],
        handoffs=[
            "Turning 'Active customer' into a computed metric → 12 Semantic Layer Agent",
            "Column descriptions → 03 Catalog & Documentation Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="06",
        chapter=CHAPTER,
        scenario=(
            "The mainframe team retired in 2019 and took the knowledge with them. Meridian has "
            "the copybooks and the COBOL, and needs the business rules out of them before "
            "anyone can migrate. Every claim must cite a file and line."
        ),
        inputs=[
            Exhibit(
                label="legacy/CUSTMAST.cpy",
                kind="code_artifacts",
                origin="Sample artifacts / legacy (shared drive)",
                format="cobol",
                stat="14 fields · packed decimal · undocumented status codes",
                note="Field layout and PIC clauses are extracted deterministically.",
                body="""      * CUSTOMER MASTER RECORD - MAINFRAME EXTRACT
      * LAST CHANGED 1998-11-02 BY BATCH TEAM
       01  CUST-MASTER-REC.
           05  CUST-NO             PIC 9(08).
           05  CUST-NAME.
               10  CUST-LAST       PIC X(20).
               10  CUST-FIRST      PIC X(15).
           05  ST-CD               PIC X(02).
           05  STAT-CD             PIC X(01).
      *        A = ACTIVE, C = CLOSED, S = SUSPENDED, D = DECEASED
           05  CRT-DT              PIC 9(08).
      *        YYYYMMDD, 00000000 WHEN UNKNOWN
           05  BAL-AMT             PIC S9(9)V99 COMP-3.
           05  CR-LIMIT            PIC S9(7)V99 COMP-3.
           05  RISK-IND            PIC X(01).
      *        COMPUTED NIGHTLY BY RSKCALC, SEE RSKCALC.CBL""",
            ),
            Exhibit(
                label="legacy/RSKCALC.cbl",
                kind="code_artifacts",
                origin="Sample artifacts / legacy",
                format="cobol",
                stat="20 lines · 2 business rules · 1 undocumented override",
                body="""       PROGRAM-ID. RSKCALC.
       PROCEDURE DIVISION.
       0100-MAIN.
           IF BAL-AMT > CR-LIMIT
               MOVE 'H' TO RISK-IND
           ELSE
               IF BAL-AMT > (CR-LIMIT * 0.80)
                   MOVE 'M' TO RISK-IND
               ELSE
                   MOVE 'L' TO RISK-IND
               END-IF
           END-IF.
      *    ACCOUNTS DORMANT OVER 400 DAYS ARE FORCED TO 'L'
      *    REGARDLESS OF BALANCE - AGREED WITH CREDIT 1997
           IF DAYS-SINCE-ACTIVITY > 400
               MOVE 'L' TO RISK-IND
           END-IF.
           GOBACK.""",
            ),
        ],
        outputs=[
            ExampleArtifact(
                filename="extracted-rules.json",
                title="Extracted business rules",
                format="json",
                source="reasoned",
                note="Each rule is tagged PARSED (read from code) or INFERRED (read from a comment).",
                body="""{
  "source_system": "Mainframe customer master (CUST_MAST)",
  "rules": [
    {
      "id": "R-001",
      "name": "Risk indicator banding",
      "statement": "RISK_IND = 'H' when BAL_AMT > CR_LIMIT; 'M' when BAL_AMT > 0.80 * CR_LIMIT; otherwise 'L'.",
      "provenance": "RSKCALC.cbl:4-12",
      "tag": "PARSED",
      "confidence": 1.0,
      "migration_relevance": "high — this rule has no equivalent in the target model"
    },
    {
      "id": "R-002",
      "name": "Dormancy override",
      "statement": "An account with no activity for more than 400 days is forced to RISK_IND = 'L' regardless of balance.",
      "provenance": "RSKCALC.cbl:14-17",
      "tag": "PARSED",
      "confidence": 1.0,
      "migration_relevance": "critical",
      "note": "Applied AFTER the banding rule, so it overrides 'H'. A dormant account 40% over its limit reads as low risk. The comment attributes this to a 1997 agreement with Credit. Whether that agreement still stands is a question for a human — it is 29 years old."
    },
    {
      "id": "R-003",
      "name": "Status code domain",
      "statement": "STAT_CD ∈ {A: active, C: closed, S: suspended, D: deceased}.",
      "provenance": "CUSTMAST.cpy:11 (comment)",
      "tag": "INFERRED",
      "confidence": 0.80,
      "note": "Read from a comment, not from enforcing code. No validation exists in the supplied artifacts; the actual data may contain values outside this set."
    },
    {
      "id": "R-004",
      "name": "Unknown creation date sentinel",
      "statement": "CRT_DT = 00000000 means the creation date is unknown, not 0000-01-01.",
      "provenance": "CUSTMAST.cpy:13 (comment)",
      "tag": "INFERRED",
      "confidence": 0.85,
      "migration_relevance": "critical",
      "note": "A naive DATE cast turns this into a date 2,000 years in the past and every downstream age calculation becomes nonsense."
    },
    {
      "id": "R-005",
      "name": "Packed decimal balance",
      "statement": "BAL_AMT is PIC S9(9)V99 COMP-3 — signed packed decimal, 2 implied decimals.",
      "provenance": "CUSTMAST.cpy:14",
      "tag": "PARSED",
      "confidence": 1.0,
      "migration_relevance": "critical",
      "note": "Reading these bytes as characters produces silent garbage rather than an error."
    }
  ],
  "summary": { "parsed": 3, "inferred": 2, "critical_for_migration": 3 }
}""",
            ),
            ExampleArtifact(
                filename="source-system-dossier.md",
                title="Source system dossier",
                format="markdown",
                source="reasoned",
                body="""# Source system dossier — mainframe CUST_MAST

**Status: PROPOSAL** (tier L1). Nothing here is authoritative until a human
with mainframe knowledge confirms it — and the point of this document is that
such a person may no longer exist at Meridian.

## What this system actually does

A customer master with 14 fields, last structurally changed in 1998. It carries
a nightly-computed credit risk indicator whose logic lives in a separate
program, and two sentinel conventions that are documented only in comments.

## The three findings that will break a naive migration

**1. The dormancy override inverts risk.** `RSKCALC` bands risk on balance
versus credit limit, then unconditionally overrides to 'L' for accounts dormant
over 400 days. A dormant account 40% over its limit reports as *low* risk. This
is intentional — a 1997 agreement with Credit — but a translator that reads
only the banding rule will produce a different answer for those accounts.

**2. `CRT_DT = 00000000` means unknown.** Cast naively it becomes a date in
year 0. Every tenure and age calculation downstream is then wrong, silently.

**3. `BAL-AMT` is packed decimal.** `PIC S9(9)V99 COMP-3` is not text. Read as
characters it produces plausible-looking garbage rather than an error.

## What could not be determined

- Whether `STAT_CD` is enforced anywhere. The domain is a comment, not a check
  constraint, so live data may contain values outside `{A, C, S, D}`.
- Whether the 1997 dormancy agreement is still policy.
- What populates `DAYS-SINCE-ACTIVITY`. It is referenced by `RSKCALC` but
  defined in neither supplied artifact.

## What this agent did not do

It did not translate anything. Rules are stated in plain language with a file
and line; turning them into runnable Snowflake SQL is agent 14's job, and the
separation exists so the rule inventory can be reviewed by a business person
who does not read SQL.
""",
            ),
        ],
        highlights=[
            "Every rule cites a file and line, and is tagged PARSED or INFERRED — read from code, or read from a comment.",
            "The dormancy override is the kind of finding that costs a migration six months when it is missed.",
            "It lists what it could not determine, including a 29-year-old policy question for a human.",
            "It refuses to translate: rules first, in language a business reviewer can check.",
        ],
        handoffs=[
            "Translating these rules into Snowflake SQL → 14 Legacy Modernization Agent",
            "Lineage edges from the same artifacts → 04 Lineage Reconstruction Agent",
            "The S2T mapping that consumes these rules → 09 Data Mapping Agent",
        ],
    ),
]
