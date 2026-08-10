"""Chapter 2 — Build. Design it, then implement it (agents 07–15)."""

from __future__ import annotations

from app.domain.canvas import Exhibit, ExampleArtifact, WorkedExample

CHAPTER = "2 · Build — design it, then implement it"

EXAMPLES: list[WorkedExample] = [
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="08",
        chapter=CHAPTER,
        scenario=(
            "Meridian wants a customer-360 product serving daily revenue by product and region, "
            "with month-over-month comparison and three years of history. The agent proposes the "
            "model — and this is the one agent that will not start without a stated workload."
        ),
        inputs=[
            Exhibit(
                label="Workload intent",
                kind="structured_request",
                origin="Typed into the workbench by the data architect",
                format="text",
                stat="the only required input",
                note="Modelling without a stated workload is guesswork. The agent asks rather than assumes.",
                body="""Daily revenue by product category and sales region for the commercial team.
Month-over-month and year-over-year comparisons. Three years of history retained.
Consumers: Commercial BI (Power BI), the finance monthly close, and the
marketing CDP nightly export. Expected volume ~180k orders/day. Analysts must
be able to answer "which categories grew fastest in EMEA last quarter" without
writing a join.""",
            ),
            Exhibit(
                label="ADE_DEMO.RETAIL (scope)",
                kind="database_objects",
                origin="ADE Demo Warehouse",
                format="table",
                stat="5 tables · 30,063 rows",
                body="CUSTOMERS (2,000) · ORDERS (8,000) · ORDER_ITEMS (19,963) · PAYMENTS (7,800) · PRODUCTS (300)",
            ),
        ],
        upstream=["profile.json — agent 01", "term-bindings.json — agent 05"],
        outputs=[
            ExampleArtifact(
                filename="entity-model.yaml",
                title="Entity model",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: EntityModel
metadata:
  product: customer-360
  style: dimensional (Kimball)
  grain_statement: "One row per order line, per day, per product."

facts:
  - name: FCT_ORDER_LINE
    grain: order_line_id
    reason: >-
      The stated workload needs revenue by product category. Product only
      exists at line level, so an order-grain fact cannot answer the question
      without a second table. Line grain is the lowest grain any stated
      consumer requires.
    measures:
      - { name: net_amount_usd, type: NUMBER(18,2), additive: true }
      - { name: quantity, type: NUMBER(10,0), additive: true }
      - { name: discount_amount_usd, type: NUMBER(18,2), additive: true }
    degenerate_dimensions: [order_id]
    foreign_keys: [customer_key, product_key, date_key, region_key]

dimensions:
  - name: DIM_CUSTOMER
    type: SCD2
    reason: >-
      Sales region is an attribute of the customer and it changes. The stated
      workload compares periods, so a customer who moved region mid-year must
      not retrospectively move their whole history.
    natural_key: customer_id
    tracked_attributes: [region_code, segment]
    static_attributes: [customer_id, signup_date]

  - name: DIM_PRODUCT
    type: SCD2
    natural_key: product_id
    tracked_attributes: [category, list_price]

  - name: DIM_DATE
    type: static
    grain: day
    span: "2023-01-01 to 2029-12-31"

open_questions:
  - question: "Is revenue recognised at order date or ship date?"
    why: "The monthly close and the BI dashboard will disagree at every month boundary."
    owner: finance
    blocking: true

  - question: "Does 'net' exclude refunds processed in a later period?"
    why: "Determines whether FCT_ORDER_LINE needs a reversal row or a restatement."
    owner: finance
    blocking: true""",
            ),
            ExampleArtifact(
                filename="model-design.md",
                title="Model design",
                format="markdown",
                source="reasoned",
                body="""# Customer-360 model design

**Status: PROPOSAL.** Agent 08 is tier L0 — advisory. This design binds
downstream work, so nothing built on it is valid until a human accepts it.

## Grain

**One row per order line per day.** Chosen because the stated workload asks for
revenue by product category, and product only exists at line level. An
order-grain fact would force every category question through a second join,
which is exactly what "answer it without writing a join" rules out.

## Why SCD2 on customer

Sales region is a customer attribute and it changes. The workload compares
periods. If region were a type-1 overwrite, a customer moving from EMEA to
AMER would silently move their entire order history with them, and last year's
EMEA number would change every time someone relocated. That is the failure mode
that makes finance stop trusting a warehouse.

The cost is real: SCD2 means surrogate keys, effective dating, and a fact that
joins on the key rather than the natural id. Stated so the trade-off is a
decision rather than a surprise.

## Two questions that block implementation

1. **Order date or ship date for revenue recognition?** The monthly close and
   the daily dashboard will disagree at every month boundary if this is left
   unstated. Finance owns it.
2. **Do refunds restate the original period or post to the current one?**
   Determines whether the fact needs reversal rows.

Both are marked `blocking: true`. Agent 09 cannot produce a defensible mapping
without them, and the model deliberately does not guess.

## What this design does not include

No physical DDL — no data types beyond logical, no clustering, no partitioning.
Those are agent 07's, and separating them keeps this document reviewable by a
business stakeholder who does not read DDL.
""",
            ),
        ],
        highlights=[
            "Tier L0 — the most consequential agent in the fleet is also the least autonomous.",
            "The grain decision is justified against the stated workload, not asserted.",
            "Two blocking questions are raised rather than guessed, and each names its owner.",
            "The SCD2 trade-off is stated as a cost, so it is a decision rather than a surprise.",
        ],
        handoffs=[
            "Physical DDL and platform options → 07 SchemaBuilder Agent",
            "Column-level source-to-target mapping → 09 Data Mapping Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="07",
        chapter=CHAPTER,
        scenario=(
            "The model is approved. Now it needs to be real Snowflake DDL that follows "
            "Meridian's standards and respects the classification labels — a RESTRICTED column "
            "cannot be deployed without a masking policy."
        ),
        inputs=[
            Exhibit(
                label="policies/ddl-standards.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="naming, types, physical options",
                body="""# Meridian DDL standards
- Tables: `DIM_` / `FCT_` prefix. Columns snake_case.
- Surrogate keys: NUMBER(38,0) IDENTITY, named `<entity>_key`.
- Money: NUMBER(18,2). Never FLOAT.
- Every table carries `dw_loaded_at TIMESTAMP_NTZ` and `dw_batch_id VARCHAR(64)`.
- Facts over 100M rows are clustered on the date key.
- RESTRICTED columns require an attached masking policy at deploy time.""",
            ),
        ],
        upstream=[
            "entity-model.yaml — agent 08 (approved)",
            "classification.json — agent 02 (RESTRICTED columns)",
        ],
        outputs=[
            ExampleArtifact(
                filename="schema.sql",
                title="Physical schema DDL",
                format="sql",
                source="reasoned",
                body="""-- Meridian customer-360 · generated from approved model v1.0
-- Standards: Meridian DDL standards v3. Classification: agent 02 run r_88104.

CREATE OR REPLACE TABLE ANALYTICS.DIM_CUSTOMER (
    customer_key        NUMBER(38,0) IDENTITY  NOT NULL,
    customer_id         NUMBER(38,0)           NOT NULL COMMENT 'CRM surrogate key. Stable for life.',
    email               VARCHAR(320)                    COMMENT 'RESTRICTED — GDPR Art.4(1). Masking policy attached.',
    national_id_token   VARCHAR(64)                     COMMENT 'RESTRICTED — tokenized. Raw value never lands here.',
    birth_year          NUMBER(4,0)                     COMMENT 'RESTRICTED, generalized from date_of_birth per agent 02.',
    region_code         VARCHAR(8)             NOT NULL,
    segment             VARCHAR(32),
    valid_from          TIMESTAMP_NTZ          NOT NULL,
    valid_to            TIMESTAMP_NTZ          NOT NULL DEFAULT '9999-12-31'::TIMESTAMP_NTZ,
    is_current          BOOLEAN                NOT NULL DEFAULT TRUE,
    dw_loaded_at        TIMESTAMP_NTZ          NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    dw_batch_id         VARCHAR(64)            NOT NULL,
    CONSTRAINT pk_dim_customer PRIMARY KEY (customer_key)
)
COMMENT = 'SCD2 customer dimension. Grain: one row per customer per attribute version.';

CREATE OR REPLACE TABLE ANALYTICS.FCT_ORDER_LINE (
    order_line_key      NUMBER(38,0) IDENTITY  NOT NULL,
    order_id            NUMBER(38,0)           NOT NULL COMMENT 'Degenerate dimension.',
    customer_key        NUMBER(38,0)           NOT NULL,
    product_key         NUMBER(38,0)           NOT NULL,
    date_key            NUMBER(8,0)            NOT NULL,
    quantity            NUMBER(10,0)           NOT NULL,
    net_amount_usd      NUMBER(18,2)           NOT NULL COMMENT 'NUMBER not FLOAT — money never rounds.',
    discount_amount_usd NUMBER(18,2)           NOT NULL DEFAULT 0,
    dw_loaded_at        TIMESTAMP_NTZ          NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    dw_batch_id         VARCHAR(64)            NOT NULL,
    CONSTRAINT pk_fct_order_line PRIMARY KEY (order_line_key),
    CONSTRAINT fk_fol_customer FOREIGN KEY (customer_key) REFERENCES ANALYTICS.DIM_CUSTOMER(customer_key),
    CONSTRAINT fk_fol_product  FOREIGN KEY (product_key)  REFERENCES ANALYTICS.DIM_PRODUCT(product_key)
)
CLUSTER BY (date_key)
COMMENT = 'Grain: one row per order line. ~180k rows/day, ~197M over 3 years.';

-- RESTRICTED columns are not deployable without these.
CREATE MASKING POLICY IF NOT EXISTS ANALYTICS.mask_email AS (val VARCHAR) RETURNS VARCHAR ->
    CASE WHEN CURRENT_ROLE() IN ('DATA_PLATFORM','FINANCE_ANALYST') THEN val
         ELSE REGEXP_REPLACE(val, '^[^@]+', '****') END;

ALTER TABLE ANALYTICS.DIM_CUSTOMER MODIFY COLUMN email SET MASKING POLICY ANALYTICS.mask_email;""",
            ),
            ExampleArtifact(
                filename="schema-contract.yaml",
                title="Schema contract",
                format="yaml",
                source="reasoned",
                note="The machine-readable form the CI schema-diff engine checks against.",
                body="""apiVersion: ade/v1
kind: SchemaContract
metadata:
  object: ANALYTICS.DIM_CUSTOMER
  model_version: "1.0"
  generated_from: entity-model.yaml (agent 08, approved)

columns:
  - { name: customer_key,      type: NUMBER(38,0),  nullable: false, role: surrogate_key }
  - { name: customer_id,       type: NUMBER(38,0),  nullable: false, role: natural_key }
  - { name: email,             type: VARCHAR(320),  nullable: true,  classification: RESTRICTED,
      masking_policy: ANALYTICS.mask_email }
  - { name: national_id_token, type: VARCHAR(64),   nullable: true,  classification: RESTRICTED,
      note: "Tokenized. The raw value is never written to this column." }
  - { name: birth_year,        type: NUMBER(4,0),   nullable: true,  classification: RESTRICTED }
  - { name: region_code,       type: VARCHAR(8),    nullable: false, status: UNPOPULATED,
      note: "Declared a GAP in the mapping. The column exists; nothing writes it yet." }
  - { name: valid_from,        type: TIMESTAMP_NTZ, nullable: false, role: scd2 }
  - { name: valid_to,          type: TIMESTAMP_NTZ, nullable: false, role: scd2 }
  - { name: is_current,        type: BOOLEAN,       nullable: false, role: scd2 }

grain: "One row per customer per attribute version."

invariants:
  - "Exactly one row per customer_id has is_current = true."
  - "valid_to > valid_from for every row."
  - "No unmasked RESTRICTED value is readable by a role outside the entitlement matrix."

checked_by:
  - "CI schema-diff on every pull request (agent 13 contract)."
  - "Generated tests (agent 11)."
""",
            ),
            ExampleArtifact(
                filename="migration-notes.md",
                title="Migration notes",
                format="markdown",
                source="reasoned",
                body="""# Migration notes — customer-360 physical schema

## Type decisions

**Money is `NUMBER(18,2)`, never `FLOAT`.** Standards require it and the reason
is arithmetic: floating point cannot represent 0.10 exactly, so a sum over 197M
rows drifts. At Meridian's volume that drift is visible in the monthly close.

**`national_id` becomes `national_id_token VARCHAR(64)`.** Agent 02 classified
the source column RESTRICTED with masking required. Rather than land the raw
value and mask it, the physical model never receives it. A masking policy can
be removed by anyone with the right role; a column that was never populated
cannot be un-redacted.

**`date_of_birth` becomes `birth_year NUMBER(4,0)`**, per the generalization
agent 02 specified.

## Nullability

`email` is nullable, against instinct. The profile shows 4% null in the source.
A NOT NULL constraint here would reject 4% of Meridian's customers at load
time — the constraint would be correct and the pipeline would be broken. Fix
the data first, then tighten.

## Clustering

`FCT_ORDER_LINE` is clustered on `date_key`. At ~180k rows/day the table
crosses 100M rows in about 18 months, and every stated query filters on a date
range. Below that size clustering costs more in maintenance than it returns —
the standard's 100M threshold is doing real work here.

## Requires review before deploy

The two blocking questions from agent 08 — revenue recognition date and refund
treatment — are still open. This DDL assumes **order date** and **reversal
rows**. If finance decides otherwise, `FCT_ORDER_LINE` needs a
`transaction_type` column and this DDL changes.
""",
            ),
        ],
        highlights=[
            "The RESTRICTED classification from agent 02 changes the physical design: the raw identifier never lands at all.",
            "`email` stays nullable and the notes explain why a 'correct' NOT NULL would break the load.",
            "It carries agent 08's unresolved questions forward rather than quietly assuming them away.",
        ],
        handoffs=[
            "Column-level mapping into these tables → 09 Data Mapping Agent",
            "Contract and SLA on the deployed objects → 13 Data Contract Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="09",
        chapter=CHAPTER,
        scenario=(
            "The schema is deployed and empty. Somebody has to say exactly which source column "
            "becomes which target column, with the transformation written down. This is the "
            "contract between design and code — and it asks the operator for nothing."
        ),
        inputs=[],
        upstream=[
            "entity-model.yaml — agent 08 (approved model)",
            "profile.json — agent 01 (source statistics)",
            "extracted-rules.json — agent 06 (legacy rule inventory)",
            "lineage-graph.json — agent 04 (for derived sources)",
        ],
        outputs=[
            ExampleArtifact(
                filename="mapping-spec.yaml",
                title="Source-to-target mapping",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: MappingSpec
metadata:
  target: ANALYTICS.DIM_CUSTOMER
  model_version: "1.0"

mappings:
  - target: customer_id
    source: RETAIL.CUSTOMERS.customer_id
    transform: direct
    confidence: 0.99

  - target: email
    source: RETAIL.CUSTOMERS.email
    transform: "LOWER(TRIM(email))"
    confidence: 0.95
    note: >-
      Profile shows 4% null and 3% matching `name@@domain`. This mapping does
      NOT repair malformed values — it normalises case and whitespace only.
      Repair is a data-owner decision, not a silent transformation.

  - target: national_id_token
    source: RETAIL.CUSTOMERS.national_id
    transform: "SHA2(CONCAT(national_id, $SALT), 256)"
    confidence: 0.90
    note: "Raw value never lands. Required by agent 02's RESTRICTED classification."

  - target: birth_year
    source: RETAIL.CUSTOMERS.date_of_birth
    transform: "YEAR(date_of_birth)"
    confidence: 0.93

  - target: region_code
    source: RETAIL.CUSTOMERS.country_code
    transform: "region_lookup(country_code)"
    confidence: 0.55
    status: GAP
    note: >-
      No region dimension exists. `country_code` is not `region_code` — EMEA
      spans 40+ countries. A lookup table must be supplied before this mapping
      can be implemented.

  - target: valid_from
    source: null
    transform: "batch effective timestamp"
    confidence: 0.99
    note: "SCD2 mechanics, not source-derived."

legacy_reconciliation:
  - target: DIM_CUSTOMER (legacy-origin rows)
    source: LEGACY.CUST_MAST
    rules_applied: [R-004, R-005]
    note: >-
      R-004: CRT_DT = 00000000 maps to NULL, not to a date. R-005: BAL_AMT is
      packed decimal and must be unpacked, not cast. Both from agent 06.
    unmapped:
      - field: RISK_IND
        reason: >-
          The target model has no risk concept. Rules R-001 and R-002 govern it
          and would be lost. Declared rather than dropped — commercial-ops must
          decide whether risk belongs in customer-360 at all.""",
            ),
            ExampleArtifact(
                filename="mapping-coverage.csv",
                title="Mapping coverage matrix",
                format="csv",
                source="reasoned",
                body="""target_table,target_column,source,transform,confidence,status
ANALYTICS.DIM_CUSTOMER,customer_key,,IDENTITY,1.00,MECHANICAL
ANALYTICS.DIM_CUSTOMER,customer_id,RETAIL.CUSTOMERS.customer_id,direct,0.99,MAPPED
ANALYTICS.DIM_CUSTOMER,email,RETAIL.CUSTOMERS.email,LOWER(TRIM(email)),0.95,MAPPED
ANALYTICS.DIM_CUSTOMER,national_id_token,RETAIL.CUSTOMERS.national_id,SHA2 tokenize,0.90,MAPPED
ANALYTICS.DIM_CUSTOMER,birth_year,RETAIL.CUSTOMERS.date_of_birth,YEAR(),0.93,MAPPED
ANALYTICS.DIM_CUSTOMER,region_code,RETAIL.CUSTOMERS.country_code,region_lookup(),0.55,GAP
ANALYTICS.DIM_CUSTOMER,segment,,,0.00,UNMAPPED
ANALYTICS.DIM_CUSTOMER,valid_from,,batch timestamp,0.99,MECHANICAL
ANALYTICS.DIM_CUSTOMER,valid_to,,'9999-12-31',0.99,MECHANICAL
ANALYTICS.DIM_CUSTOMER,is_current,,derived,0.99,MECHANICAL
ANALYTICS.FCT_ORDER_LINE,net_amount_usd,RAW.ORDER_ITEMS.amount * rate,FX conversion,0.72,REVIEW
ANALYTICS.FCT_ORDER_LINE,quantity,RAW.ORDER_ITEMS.quantity,direct,0.99,MAPPED""",
            ),
            ExampleArtifact(
                filename="mapping-notes.md",
                title="Mapping notes",
                format="markdown",
                source="reasoned",
                body="""# Mapping notes — customer-360

**Coverage: 8 of 12 columns mapped. 1 gap, 1 unmapped, 2 needing review.**
Stated up front because a coverage number is the first thing that gets
misreported as "done".

## The gap: region

`region_code` has no source. `country_code` is not a region — EMEA spans 40+
countries and Meridian's own reporting groups them in a way that exists in a
spreadsheet somewhere, not in the warehouse. **A lookup table must be supplied.**

This is declared as a GAP rather than papered over with
`CASE WHEN country_code IN (...)`. An invented grouping would be wrong in a way
that produces plausible numbers, which is worse than a missing column.

## The unmapped column: segment

`DIM_CUSTOMER.segment` exists in the approved model and has no source anywhere
in the profiled estate. Either the model anticipated data that does not exist
yet, or the source was missed. Flagged for the architect.

## The FX review item

`net_amount_usd` derives from `amount * COALESCE(rate, 1.0)` in the existing
load. Agent 04 flagged that COALESCE: on a rate-lookup miss a EUR order is
counted as dollars. This mapping **inherits that defect** if implemented as-is.
Recommendation: fail the row rather than default the rate. Marked REVIEW rather
than fixed unilaterally, because failing rows changes load behaviour and that
is an operational decision.

## What is deliberately lost

`LEGACY.CUST_MAST.RISK_IND` has no target. Rules R-001 and R-002 from agent 06
govern it — including the dormancy override that inverts risk for dormant
accounts. Migrating without it silently drops a credit control that has been
running since 1997. Declared in the mapping so the decision is explicit.
""",
            ),
        ],
        highlights=[
            "This agent asks the operator for nothing — every input arrives through the dependency gate.",
            "Gaps are declared rather than papered over: an invented region grouping would produce plausible wrong numbers.",
            "It inherits and flags agent 04's FX defect rather than silently reproducing it.",
            "A 29-year-old credit control being dropped is stated as a decision, not lost in a migration.",
        ],
        handoffs=[
            "Turning this into runnable code → 10 Coding Agent",
            "Verifying parity after implementation → 18 Reconciliation & Parity Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="10",
        chapter=CHAPTER,
        scenario=(
            "The mapping is approved. The agent writes the pipeline in Meridian's house style — "
            "idempotent, restartable, and matching the conventions of the repo it will live in."
        ),
        inputs=[
            Exhibit(
                label="policies/house-style.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="repo conventions",
                body="""# Meridian dbt conventions
- Incremental models use `merge` with an explicit unique_key.
- Every model is idempotent: a re-run for the same batch produces the same rows.
- No `SELECT *` in committed models.
- Batch id threaded through as `{{ var('batch_id') }}`.
- CTEs named for what they contain, not `a`, `b`, `c`.""",
            ),
        ],
        upstream=["mapping-spec.yaml — agent 09", "schema.sql manifest — agent 07"],
        outputs=[
            ExampleArtifact(
                filename="pipeline.sql",
                title="Pipeline code",
                format="sql",
                source="reasoned",
                body="""{{ config(
    materialized='incremental',
    unique_key='customer_id',
    incremental_strategy='merge'
) }}

-- DIM_CUSTOMER (SCD2) · implements mapping-spec.yaml v1.0
-- Idempotent: re-running batch {{ var('batch_id') }} produces identical rows.

with source_customers as (

    select
        customer_id,
        lower(trim(email))                              as email,
        sha2(concat(national_id, '{{ var("pii_salt") }}'), 256) as national_id_token,
        year(date_of_birth)                             as birth_year,
        country_code,
        segment,
        _loaded_at
    from {{ source('retail', 'customers') }}
    {% if is_incremental() %}
      where _loaded_at > (select coalesce(max(dw_loaded_at), '1900-01-01') from {{ this }})
    {% endif %}

),

legacy_customers as (

    -- R-004 (agent 06): 00000000 means unknown, not year zero.
    -- R-005 (agent 06): BAL_AMT is packed decimal; unpacked upstream in the extract.
    select
        cust_no                                          as customer_id,
        null                                             as email,
        null                                             as national_id_token,
        null                                             as birth_year,
        st_cd                                            as country_code,
        null                                             as segment,
        case when crt_dt = '00000000' then null
             else to_date(crt_dt, 'YYYYMMDD') end        as legacy_created_at
    from {{ source('legacy', 'cust_mast') }}

),

unioned as (
    select customer_id, email, national_id_token, birth_year, country_code, segment
    from source_customers
    union all
    select customer_id, email, national_id_token, birth_year, country_code, segment
    from legacy_customers
),

versioned as (

    select
        *,
        -- region_code is deliberately absent: mapping-spec marks it GAP.
        current_timestamp()                              as valid_from,
        '9999-12-31'::timestamp_ntz                      as valid_to,
        true                                             as is_current,
        current_timestamp()                              as dw_loaded_at,
        '{{ var("batch_id") }}'                          as dw_batch_id
    from unioned

)

select * from versioned""",
            ),
            ExampleArtifact(
                filename="implementation-notes.md",
                title="Implementation notes",
                format="markdown",
                source="reasoned",
                body="""# Implementation notes — DIM_CUSTOMER

## Idempotency

`merge` on `customer_id` with a high-watermark filter on `_loaded_at`. Re-running
batch `{{ var('batch_id') }}` produces identical rows — no duplicates, no
double-counting. The pipeline-run history shows 2026-07-08 loaded 361,200 rows
against a 180k daily norm, which is exactly what a non-idempotent re-run looks
like. This design makes that specific failure impossible.

## What is deliberately not implemented

**`region_code` is absent from the output.** The mapping marks it a GAP. Writing
`CASE WHEN country_code IN ('FR','DE','ES') THEN 'EMEA'` would compile, run, and
be wrong in a way nobody notices for a quarter. The column is left out so the
model fails loudly at contract validation rather than quietly at reporting time.

**The FX COALESCE is not reproduced.** The mapping flagged it REVIEW. This code
does not touch `net_amount_usd` at all pending that decision.

## Caveats for review

The SCD2 implementation here **inserts new versions but does not close old
ones** — `valid_to` is always the sentinel and `is_current` is always true. That
is a deliberate first cut: closing prior versions needs the effective-dating
rule that agent 08 left open. As written this produces duplicate current rows
for any changed customer, which the generated tests will catch.

Stated rather than hidden. A pipeline that looks complete and is not is worse
than one that is obviously partial.
""",
            ),
        ],
        highlights=[
            "The code refuses to implement the region gap — a plausible-looking CASE would be wrong for a quarter before anyone noticed.",
            "Idempotency is designed against a specific observed failure: the 2026-07-08 double load.",
            "The notes admit the SCD2 close is not implemented, rather than shipping something that looks finished.",
        ],
        handoffs=[
            "Tests that protect this logic → 11 Test Generation Agent",
            "Review against standards → 35 Reviewer Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="11",
        chapter=CHAPTER,
        scenario=(
            "The pipeline is written. The agent generates CI tests from the mapping and the "
            "profile — each one tied to the specific failure it protects against. It asks the "
            "operator for nothing."
        ),
        inputs=[],
        upstream=[
            "mapping-spec.yaml — agent 09",
            "entity-model.yaml — agent 08",
            "profile.json — agent 01",
        ],
        outputs=[
            ExampleArtifact(
                filename="tests.yaml",
                title="Generated test suite",
                format="yaml",
                source="reasoned",
                body="""version: 2

models:
  - name: dim_customer
    tests:
      - unique:
          column_name: customer_id
          config: { severity: error }
          meta:
            protects_against: >-
              Duplicate current rows from the unclosed SCD2 versions flagged in
              agent 10's implementation notes. This test is expected to FAIL on
              the current pipeline — that is the point.

      - dbt_utils.expression_is_true:
          expression: "count(*) = count(distinct customer_id) or is_current = false"
          meta:
            protects_against: "More than one current row per customer."

    columns:
      - name: customer_id
        tests: [not_null]

      - name: email
        tests:
          - dbt_expectations.expect_column_values_to_match_regex:
              regex: "^[^@\\\\s]+@[^@\\\\s]+\\\\.[^@\\\\s]+$"
              row_condition: "email is not null"
              config: { severity: warn }
              meta:
                threshold_basis: >-
                  Profile: 186 of 192 non-null sampled values matched. Set to
                  warn, not error — 3% malformed is the current state of the
                  source, and failing the build on it would block the migration
                  rather than fix the data.

      - name: national_id_token
        tests:
          - dbt_expectations.expect_column_values_to_match_regex:
              regex: "^[a-f0-9]{64}$"
              config: { severity: error }
              meta:
                protects_against: >-
                  A raw national identifier reaching the warehouse because the
                  salt was unset. A 64-char hex string is the only acceptable
                  shape; anything else is a privacy incident.

      - name: birth_year
        tests:
          - dbt_utils.accepted_range:
              min_value: 1900
              max_value: 2026
              meta:
                protects_against: >-
                  Rule R-004 (agent 06): CRT_DT = 00000000 cast naively yields
                  year 0. This test catches that specific defect.

not_generated:
  - test: "row count matches source"
    reason: >-
      DIM_CUSTOMER unions two sources with different cardinality and one is
      SCD2. A row-count equality test would fail correctly and be silenced,
      which is worse than no test. Parity belongs to agent 18.""",
            ),
            ExampleArtifact(
                filename="test-plan.md",
                title="Test plan",
                format="markdown",
                source="reasoned",
                body="""# Test plan — DIM_CUSTOMER

## What is covered

| Test | Severity | Protects against |
|---|---|---|
| `customer_id` unique | error | Duplicate current rows from unclosed SCD2 versions |
| `customer_id` not null | error | Join failure downstream |
| `email` regex | warn | Format drift, at the source's actual 97% rate |
| `national_id_token` hex-64 | error | A raw identifier reaching the warehouse |
| `birth_year` range | error | The `00000000` sentinel cast (rule R-004) |

## One test is expected to fail

`customer_id` unique **will fail on the current pipeline**. Agent 10's notes say
the SCD2 close is not implemented, so a changed customer produces two current
rows. The test is generated anyway, at error severity, because a test suite that
only asserts what already passes is decoration.

## What is deliberately not tested here

**Row-count parity against the source.** `DIM_CUSTOMER` unions two sources of
different cardinality and versions rows over time, so a count-equality test
fails correctly and gets silenced within a week. A silenced test is worse than
a missing one. Parity is agent 18's job, with a comparison that understands
SCD2.

## Threshold honesty

The email test is `warn`, not `error`, and the reason is written into the test
metadata: 3% malformed is the **current state of Meridian's source data**. An
error-severity test would block every build until the CRM data is cleaned,
which converts a data-quality problem into a delivery problem. The threshold
records the profiled statistic it came from, so a reviewer can audit the number
rather than trust it.
""",
            ),
        ],
        highlights=[
            "Every test cites the failure it protects against, not just the assertion it makes.",
            "One test is generated knowing it will fail — a suite that only asserts what passes is decoration.",
            "It refuses to write a row-count test that would be correct, fail, and get silenced.",
        ],
        handoffs=[
            "Production quality rules and thresholds → 16 Data Quality Rules Agent",
            "Parity between old and new estates → 18 Reconciliation & Parity Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="12",
        chapter=CHAPTER,
        scenario=(
            "Analysts write their own joins and get different revenue numbers. The semantic "
            "layer defines the metrics once — including the 'active customer' term agent 05 "
            "found unbound anywhere in the estate."
        ),
        inputs=[
            Exhibit(
                label="telemetry/bi_measure_inventory.csv",
                kind="telemetry_export",
                origin="Sample artifacts / telemetry",
                format="csv",
                stat="6 existing measures · 3 duplicated definitions",
                note="Reconciles with what analysts already use rather than competing with it.",
                body="""measure,workspace,definition,owner
Revenue,Commercial,SUM(amount_usd),priya
Revenue (net),Commercial,SUM(amount_usd) - SUM(discount),raj
Total Revenue,Finance,SUM(amount_usd) WHERE status='COMPLETE',finance-systems
Active Customers,Marketing,COUNT(DISTINCT customer_id) last 24m,dana
Active Customers,Commercial,COUNT(DISTINCT customer_id) last 12m,priya
AOV,Commercial,SUM(amount_usd)/COUNT(DISTINCT order_id),priya""",
            ),
        ],
        upstream=["entity-model.yaml — agent 08", "term-bindings.json — agent 05"],
        outputs=[
            ExampleArtifact(
                filename="semantic-model.yaml",
                title="Semantic model",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: SemanticModel
metadata:
  product: customer-360
  governed_by: Meridian glossary v4.2

entities:
  - name: order_line
    base_table: ANALYTICS.FCT_ORDER_LINE
    primary_key: order_line_key

dimensions:
  - { name: order_date, type: time, grain: day, expr: DIM_DATE.date_actual }
  - { name: product_category, type: categorical, expr: DIM_PRODUCT.category }
  - { name: sales_region, type: categorical, expr: DIM_CUSTOMER.region_code,
      status: BLOCKED, note: "region_code is a declared gap in the mapping." }

metrics:
  - name: net_revenue
    label: Net revenue
    expr: SUM(net_amount_usd - discount_amount_usd)
    grain: order_line
    governed_term: Lifetime value (component)
    supersedes: ["Revenue", "Revenue (net)", "Total Revenue"]
    note: >-
      Three competing BI measures collapse into this one. `Total Revenue`
      additionally filtered on status='COMPLETE'; that filter is preserved
      below as an explicit qualifier rather than dropped.

  - name: completed_net_revenue
    label: Net revenue (completed orders)
    expr: SUM(CASE WHEN order_status = 'COMPLETE' THEN net_amount_usd - discount_amount_usd ELSE 0 END)
    note: "Preserves the Finance definition. The difference from net_revenue is now visible rather than argued about."

  - name: active_customers
    label: Active customers
    expr: COUNT(DISTINCT CASE WHEN last_order_date >= DATEADD(month, -12, CURRENT_DATE) THEN customer_key END)
    governed_term: Active customer
    window: 12 months
    note: >-
      Agent 05 found this term unbound to any physical column, which is why
      Marketing (24m) and Commercial (12m) both believed they were right. The
      governed definition is 12 months; this metric implements it, and the
      24-month variant is defined separately below rather than silently dropped.

  - name: active_customers_24m
    label: Active customers (24-month, marketing view)
    expr: COUNT(DISTINCT CASE WHEN last_order_date >= DATEADD(month, -24, CURRENT_DATE) THEN customer_key END)
    governed: false
    note: "Non-governed. Named so a report using it cannot claim to be the governed figure."

  - name: average_order_value
    label: Average order value
    expr: SUM(net_amount_usd) / NULLIF(COUNT(DISTINCT order_id), 0)
    note: "NULLIF guards the divide-by-zero the original BI measure did not."
""",
            ),
            ExampleArtifact(
                filename="metric-definitions.md",
                title="Metric definitions",
                format="markdown",
                source="reasoned",
                body="""# Metric definitions — customer-360

## Six BI measures become four metrics

| Was | Now | What changed |
|---|---|---|
| Revenue, Revenue (net) | `net_revenue` | One definition, discount always subtracted |
| Total Revenue | `completed_net_revenue` | Finance's status filter preserved explicitly |
| Active Customers ×2 | `active_customers` (12m) + `active_customers_24m` | Both survive; only one is governed |
| AOV | `average_order_value` | Divide-by-zero guarded |

## The active-customer disagreement

Marketing reported 24-month actives. Commercial reported 12-month. Both called
the number "active customers" and both were internally consistent, which is why
it survived so long.

The governed definition is 12 months. Rather than delete Marketing's measure —
which would break their reporting and start an argument — both exist, and only
one carries `governed: true`. A dashboard using the 24-month variant can no
longer present it as the governed figure.

## What is blocked

`sales_region` is defined and **marked BLOCKED**. It depends on
`DIM_CUSTOMER.region_code`, which the mapping declares a GAP. The dimension is
written down so the semantic layer is complete on paper, and blocked so nobody
builds a regional dashboard on a column that is not populated.

## What this layer does not do

It does not certify anything. Publication and certification are agent 29's,
after the contract, docs and quality scorecard are all in place.
""",
            ),
        ],
        highlights=[
            "Six competing BI measures collapse to four metrics without deleting anyone's — only one carries `governed: true`.",
            "The blocked region dimension is written down and marked blocked, so nobody builds on an empty column.",
            "It resolves a disagreement that survived because both sides were internally consistent.",
        ],
        handoffs=[
            "Certifying the product for self-serve → 29 Data Product Publishing Agent",
            "Answering analyst questions over this layer → 31 Analyst Assist Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="13",
        chapter=CHAPTER,
        scenario=(
            "Three teams now depend on FCT_ORDERS and none of them have been told what they can "
            "rely on. The contract states the commitment, and the schema-diff engine makes a "
            "breaking change impossible to ship by accident."
        ),
        inputs=[
            Exhibit(
                label="policies/data-product-slas.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="1 product · 3 registered consumers",
                body="""# Data product SLAs — revenue domain

## ANALYTICS.FCT_ORDERS
- Freshness: available by 06:00 UTC each day.
- Completeness: >= 99.5% of source orders present within 24 hours.
- Schema: breaking changes require 30 days' notice to registered consumers.
- Owner: revenue-data-team. Escalation: #revenue-data-oncall.

### Registered consumers
| Consumer | Contact | Dependency |
|---|---|---|
| Commercial BI | priya@meridian.example | rpt_001, rpt_003 |
| Finance close | finance-systems@meridian.example | Monthly statutory pack |
| Marketing CDP | dana@meridian.example | Nightly export |""",
            ),
        ],
        upstream=["schema.sql manifest — agent 07", "quality-rules.yaml — agent 16"],
        outputs=[
            ExampleArtifact(
                filename="data-contract.yaml",
                title="Data contract",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: DataContract
metadata:
  object: ANALYTICS.FCT_ORDERS
  version: "1.0.0"
  owner: revenue-data-team
  escalation: "#revenue-data-oncall"

schema:
  columns:
    - { name: order_id,     type: NUMBER(38,0),  nullable: false, stability: guaranteed }
    - { name: customer_id,  type: NUMBER(38,0),  nullable: false, stability: guaranteed }
    - { name: order_ts,     type: TIMESTAMP_NTZ, nullable: false, stability: guaranteed }
    - { name: amount_usd,   type: NUMBER(18,2),  nullable: false, stability: guaranteed }
    - { name: category,     type: VARCHAR(64),   nullable: true,  stability: evolving }

service_levels:
  freshness:
    commitment: "Available by 06:00 UTC daily"
    measured_by: "MAX(order_ts) vs load completion, from agent 17 baselines"
    current_p95: "05:42 UTC"
    headroom: "18 minutes"

  completeness:
    commitment: ">= 99.5% of source orders within 24 hours"
    measured_by: "agent 16 rule dq_fct_orders_completeness"
    current: "99.87%"

  accuracy:
    commitment: "amount_usd is USD at the order-date rate"
    status: AT_RISK
    detail: >-
      The current load applies COALESCE(rate, 1.0). On a rate-lookup miss a
      foreign-currency order is counted as dollars. This contract cannot honestly
      commit to accuracy until that is fixed. Recorded as AT_RISK rather than
      omitted.

breaking_change_policy:
  notice_period_days: 30
  breaking:
    - dropping a guaranteed column
    - narrowing a type
    - making a nullable column NOT NULL
    - changing the grain
  non_breaking:
    - adding a nullable column
    - widening a type
    - adding an evolving column

consumers:
  - { name: Commercial BI,  contact: "priya@meridian.example",           assets: [rpt_001, rpt_003] }
  - { name: Finance close,  contact: "finance-systems@meridian.example", assets: ["Monthly statutory pack"] }
  - { name: Marketing CDP,  contact: "dana@meridian.example",            assets: ["Nightly export"] }""",
            ),
            ExampleArtifact(
                filename="contract-changelog.md",
                title="Contract changelog",
                format="markdown",
                source="reasoned",
                body="""# Contract changelog — ANALYTICS.FCT_ORDERS

## v1.0.0 — first published contract

Before this, three teams depended on this table and none had been told what
they could rely on. Every commitment below is measured, not aspirational —
each cites the agent and rule that measures it.

### What is now guaranteed

- Four columns are `stability: guaranteed`. Dropping or narrowing any of them
  requires 30 days' notice to three named consumers.
- Freshness by 06:00 UTC, currently running p95 05:42 — 18 minutes of headroom.
- Completeness ≥ 99.5%, currently 99.87%.

### What is deliberately NOT guaranteed

**Accuracy of `amount_usd` is `AT_RISK`.** The FX COALESCE defect means a
foreign-currency order can be counted as dollars when the rate lookup misses.
Committing to accuracy while that exists would make the contract a fiction. It
is recorded at risk, with the fix tracked against agent 09's REVIEW item.

`category` is `evolving` — new categories may appear without notice. Consumers
must not hardcode the domain.

### What this changes operationally

The schema-diff engine now runs in CI against this contract. A pull request
that drops `amount_usd` fails the build with the three consumer contacts in the
failure message. That is the whole value: the notice period stops being a
policy people forget and becomes a check that blocks a merge.
""",
            ),
        ],
        highlights=[
            "Accuracy is recorded AT_RISK rather than committed to — a contract that overpromises is a fiction.",
            "Every commitment cites the agent and rule that measures it, with current headroom.",
            "The 30-day notice period becomes a CI check that fails a merge, not a policy people forget.",
        ],
        handoffs=[
            "Detecting drift against this contract → 21 Schema Drift & Impact Agent",
            "The quality rules it commits to → 16 Data Quality Rules Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="14",
        chapter=CHAPTER,
        scenario=(
            "The rules are inventoried and reviewed. Now the COBOL becomes Snowflake SQL — with "
            "a declared-delta register for the one thing that cannot be translated faithfully."
        ),
        inputs=[
            Exhibit(
                label="legacy/RSKCALC.cbl",
                kind="code_artifacts",
                origin="Sample artifacts / legacy",
                format="cobol",
                stat="20 lines · the dormancy override",
                body="""       0100-MAIN.
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
           IF DAYS-SINCE-ACTIVITY > 400
               MOVE 'L' TO RISK-IND
           END-IF.""",
            ),
            Exhibit(
                label="policies/target-conventions.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="Snowflake house style",
                body="""# Target conventions
- No stored procedures for row-level logic; use SQL expressions.
- Every translated rule carries a comment citing its legacy provenance.
- Rounding: HALF_UP to 2 decimals for money.""",
            ),
        ],
        upstream=["extracted-rules.json — agent 06", "mapping-spec.yaml — agent 09"],
        outputs=[
            ExampleArtifact(
                filename="translated-logic.sql",
                title="Translated logic",
                format="sql",
                source="reasoned",
                body="""-- Risk indicator · translated from RSKCALC.cbl
-- Provenance: rules R-001 (banding) and R-002 (dormancy override), agent 06.
-- Evaluation order is load-bearing: the override applies AFTER banding.

create or replace function ANALYTICS.fn_risk_indicator(
    bal_amt              number(18,2),
    cr_limit             number(18,2),
    days_since_activity  number(10,0)
)
returns varchar
as
$$
    case
        -- R-002 (RSKCALC.cbl:14-17): dormancy override, applied first in SQL
        -- because CASE short-circuits. In COBOL it ran last and overwrote the
        -- banded value; ordering it first here is equivalent, not a change.
        when days_since_activity > 400 then 'L'

        -- R-001 (RSKCALC.cbl:4-12): balance-versus-limit banding
        when bal_amt > cr_limit             then 'H'
        when bal_amt > cr_limit * 0.80      then 'M'
        else                                     'L'
    end
$$;

-- Behavioural equivalence check, runnable against both estates:
-- select count(*) from LEGACY.CUST_MAST
--  where RISK_IND <> ANALYTICS.fn_risk_indicator(BAL_AMT, CR_LIMIT, DAYS_SINCE_ACTIVITY);
-- Expected: 0 rows.""",
            ),
            ExampleArtifact(
                filename="modernization-report.md",
                title="Modernization report",
                format="markdown",
                source="reasoned",
                body="""# Modernization report — RSKCALC

## Behavioural equivalence

| Legacy rule | Translated | Equivalent? |
|---|---|---|
| R-001 banding (H/M/L) | `fn_risk_indicator` CASE arms 2–4 | Yes, exactly |
| R-002 dormancy override | `fn_risk_indicator` CASE arm 1 | Yes, by reordering |

**The reordering deserves explanation.** In COBOL the override ran *after*
banding and overwrote the result. SQL `CASE` short-circuits on the first match,
so putting the override first produces the same answer for every input. This is
an equivalence-preserving transformation, not a behaviour change — and it is
called out because a reviewer comparing the two side by side will notice the
order flipped and should not have to work out why.

A verification query is included in the SQL. Run it against both estates; zero
rows is the pass condition.

## Declared deltas

**One rule could not be translated faithfully.**

`DAYS-SINCE-ACTIVITY` is referenced by `RSKCALC` but **defined nowhere in the
supplied artifacts**. The COBOL reads it from a working-storage field populated
by an upstream batch step that was not provided. The translated function takes
it as a parameter, which pushes the problem to the caller rather than solving
it.

Until that upstream calculation is located, `fn_risk_indicator` cannot be
called correctly. This is a **hard blocker**, recorded as a declared delta
rather than papered over with `DATEDIFF(day, last_order_date, CURRENT_DATE)` —
which would be a plausible guess and might be wrong, because "activity" in a
credit system may mean payment rather than order.

## What was not attempted

The `STAT_CD` domain (rule R-003) is INFERRED from a comment, not enforced
anywhere. Translating it into a CHECK constraint would impose a rule the legacy
system never enforced, and would reject live data that exists today. Left
untranslated deliberately.
""",
            ),
        ],
        highlights=[
            "The COBOL-to-SQL reordering is explained as equivalence-preserving, so a reviewer is not left wondering.",
            "A verification query is shipped with the translation — zero rows is the pass condition.",
            "One rule is declared untranslatable rather than guessed: 'activity' in a credit system may not mean 'order'.",
            "It refuses to impose a constraint the legacy system never enforced.",
        ],
        handoffs=[
            "Parity verification across both estates → 18 Reconciliation & Parity Agent",
            "Reviewing the translation against standards → 35 Reviewer Agent",
        ],
    ),
    # ------------------------------------------------------------------ #
    WorkedExample(
        agent_id="15",
        chapter=CHAPTER,
        scenario=(
            "Meridian is reloading RETAIL.ORDERS in full every night — 8,000 rows today, but "
            "the same pattern is running on tables 1,000 times larger. The agent picks the "
            "load pattern the source can actually support."
        ),
        inputs=[
            Exhibit(
                label="ADE_DEMO.RETAIL.ORDERS",
                kind="database_objects",
                origin="ADE Demo Warehouse",
                format="table",
                stat="8,000 rows · has order_ts, no updated_at",
                body="order_id, customer_id, order_ts, currency, amount, status",
            ),
            Exhibit(
                label="policies/source-interface.md",
                kind="policy_document",
                origin="Sample artifacts / policies",
                format="markdown",
                stat="what the source can actually do",
                note="Decides whether an incremental pattern is even possible.",
                body="""# RETAIL source interface
- Extract: nightly file drop, 02:00 UTC, S3.
- CDC: not available. The vendor charges for the log-based option.
- Deletes: soft only (`status = 'CANCELLED'`). Rows are never removed.
- Late arrivals: orders can be amended for up to 7 days after order_ts.
- No `updated_at` column. The vendor has this on their roadmap.""",
            ),
        ],
        upstream=["profile.json — agent 01"],
        outputs=[
            ExampleArtifact(
                filename="ingestion-design.yaml",
                title="Ingestion design",
                format="yaml",
                source="reasoned",
                body="""apiVersion: ade/v1
kind: IngestionDesign
metadata:
  source: RETAIL.ORDERS
  target: RAW.ORDERS

pattern: incremental_window_merge
cadence: daily at 02:30 UTC (30 min after the file drop)

watermark:
  column: order_ts
  strategy: rolling_window
  window_days: 8
  reason: >-
    The source allows amendments for 7 days and has no updated_at column, so a
    high-watermark on order_ts alone would miss every amendment. An 8-day
    rolling re-read (7 + 1 day of safety margin) catches them.

change_detection:
  method: merge_on_natural_key
  key: [order_id]
  compare: hash of (customer_id, order_ts, currency, amount, status)
  reason: "Without updated_at, a content hash is the only way to detect an amendment."

deletes:
  handling: soft
  detection: "status = 'CANCELLED' in the source"
  note: >-
    The source never removes rows, so no hard-delete reconciliation is needed.
    If that ever changes this design breaks silently — recorded as an assumption
    to re-verify, not a fact.

volumetrics:
  daily_new_rows: ~180000
  daily_reread_rows: ~1440000
  note: "The 8-day window costs 8x the read for correctness. Justified below."

rejected_patterns:
  - pattern: full_refresh
    reason: "Currently in use. At 197M rows over 3 years this stops fitting the window."
  - pattern: cdc_log_based
    reason: "Not available — the vendor charges for it. Revisit if amendment volume grows."
  - pattern: high_watermark_append
    reason: "Would silently miss all amendments. This is the pattern most teams reach for first."
""",
            ),
            ExampleArtifact(
                filename="pattern-rationale.md",
                title="Pattern rationale",
                format="markdown",
                source="reasoned",
                body="""# Why an 8-day rolling window

## The constraint that decides it

The source has **no `updated_at` column** and allows amendments for **7 days**.
Those two facts together eliminate the obvious answer.

A high-watermark append on `order_ts` is what most teams build first. It is
cheap, it is simple, and it **silently misses every amendment** — an order
placed Monday and corrected Thursday keeps its Monday `order_ts`, so the
watermark never sees it again. The data is wrong, no job fails, and it is
discovered in a month-end reconciliation.

## The cost

Re-reading 8 days means ~1.44M rows per night against ~180k new ones — eight
times the read. That is a real cost and it is stated rather than buried.

It is worth paying because the alternative is not "slightly stale data", it is
"silently incorrect revenue", and the reconciliation that finds it costs more
than the compute.

## What changes this recommendation

- **If the vendor ships `updated_at`**, switch to a high-watermark on that
  column and the window collapses to 1 day.
- **If CDC is purchased**, this design is superseded entirely.
- **If the amendment window changes from 7 days**, the window must change with
  it. The number is not arbitrary and should not be tuned for cost.

## Assumption to re-verify

The source currently never hard-deletes. This design has no hard-delete
reconciliation, so if that behaviour ever changes, rows will linger in the
warehouse with nothing failing. Recorded as an assumption, not a fact.
""",
            ),
        ],
        highlights=[
            "The obvious pattern — high-watermark append — is explicitly rejected, with the failure mode spelled out.",
            "The 8x read cost is stated plainly and justified against the cost of silently wrong revenue.",
            "It names the three conditions that would change the recommendation.",
        ],
        handoffs=[
            "Implementing the pattern → 10 Coding Agent",
            "Scheduling and backfill of the window → 24 Orchestration & Backfill Agent",
        ],
    ),
]
