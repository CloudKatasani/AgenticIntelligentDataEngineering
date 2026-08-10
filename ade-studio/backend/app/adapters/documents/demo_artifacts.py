"""A seeded workspace of file inputs, so file-driven agents demo too.

The demo warehouse lets agent 01 run from a clean install. Most of the fleet
does not read tables, so without this the same clean install has nothing to
offer agent 04, 06, 14, 17, 22 or 26 — the majority. These files are the file
equivalent of the seeded warehouse: small, deliberately imperfect, and real
enough that the deterministic reader finds genuine things in them.

Everything here is invented sample data for a fictional estate. Nothing is
copied from any customer.
"""

from __future__ import annotations

import threading
from pathlib import Path

_SEED_LOCK = threading.Lock()

# ---------------------------------------------------------------------- #
# Legacy artifacts — agents 06 and 14
# ---------------------------------------------------------------------- #

_CUSTMAST_COPYBOOK = """      * CUSTOMER MASTER RECORD - MAINFRAME EXTRACT
      * LAST CHANGED 1998-11-02 BY BATCH TEAM
       01  CUST-MASTER-REC.
           05  CUST-NO             PIC 9(08).
           05  CUST-NAME.
               10  CUST-LAST       PIC X(20).
               10  CUST-FIRST      PIC X(15).
           05  ADDR-LINE-1         PIC X(30).
           05  ST-CD               PIC X(02).
           05  ZIP-CD              PIC X(09).
           05  STAT-CD             PIC X(01).
      *        A = ACTIVE, C = CLOSED, S = SUSPENDED, D = DECEASED
           05  CRT-DT              PIC 9(08).
      *        YYYYMMDD, 00000000 WHEN UNKNOWN
           05  BAL-AMT             PIC S9(9)V99 COMP-3.
           05  CR-LIMIT            PIC S9(7)V99 COMP-3.
           05  RISK-IND            PIC X(01).
      *        COMPUTED NIGHTLY BY RSKCALC, SEE RSKCALC.CBL
           05  FILLER              PIC X(12).
"""

_RSKCALC = """      * RSKCALC - NIGHTLY RISK INDICATOR
       IDENTIFICATION DIVISION.
       PROGRAM-ID. RSKCALC.
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
           GOBACK.
"""

_LOAD_ORDERS_SQL = """-- Nightly load: RAW -> ANALYTICS
-- Owner: revenue-data-team

CREATE OR REPLACE TABLE ANALYTICS.FCT_ORDERS AS
SELECT
    o.order_id,
    o.customer_id,
    o.order_ts,
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
SELECT 'FCT_ORDERS', CURRENT_TIMESTAMP(), COUNT(*) FROM ANALYTICS.FCT_ORDERS;
"""

_CUSTOMER_360_SQL = """-- Downstream mart consumed by the BI estate.
CREATE OR REPLACE VIEW ANALYTICS.CUSTOMER_360 AS
SELECT
    c.customer_id,
    c.email,
    c.national_id,          -- flagged as PII by agent 02
    SUM(f.amount_usd) AS lifetime_value,
    MAX(f.order_ts)    AS last_order_ts
FROM ANALYTICS.DIM_CUSTOMER c
LEFT JOIN ANALYTICS.FCT_ORDERS f ON f.customer_id = c.customer_id
GROUP BY 1, 2, 3;
"""

_INFORMATICA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<POWERMART>
  <REPOSITORY NAME="EDW_REPO" VERSION="9.6">
    <FOLDER NAME="RETAIL_LOAD">
      <MAPPING NAME="m_LOAD_CUSTOMER" DESCRIPTION="Legacy customer conform">
        <TRANSFORMATION NAME="SQ_CUST_MAST" TYPE="Source Qualifier">
          <TABLEATTRIBUTE NAME="Sql Query" VALUE="SELECT CUST_NO, CUST_NM, ST_CD, BAL_AMT FROM CUST_MAST"/>
        </TRANSFORMATION>
        <TRANSFORMATION NAME="EXP_CLEAN" TYPE="Expression">
          <TRANSFORMFIELD NAME="CUST_NM_CLEAN" EXPRESSION="LTRIM(RTRIM(UPPER(CUST_NM)))"/>
          <TRANSFORMFIELD NAME="STATE_STD" EXPRESSION="IIF(ST_CD='TX','TEXAS',IIF(ST_CD='CA','CALIFORNIA',ST_CD))"/>
        </TRANSFORMATION>
        <TRANSFORMATION NAME="FIL_ACTIVE" TYPE="Filter">
          <TABLEATTRIBUTE NAME="Filter Condition" VALUE="STAT_CD = 'A'"/>
        </TRANSFORMATION>
        <TARGET NAME="DIM_CUSTOMER"/>
      </MAPPING>
    </FOLDER>
  </REPOSITORY>
</POWERMART>
"""

# ---------------------------------------------------------------------- #
# Telemetry exports — agents 17, 21, 22, 23, 25, 30
# ---------------------------------------------------------------------- #

_METERING_CSV = """date,warehouse,credits,cost_usd,queries,owner_tag
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
2026-07-04,WH_ADHOC,101.0,202.00,377,
"""

_PIPELINE_TELEMETRY_CSV = """run_date,pipeline,status,rows_loaded,started_at,finished_at,duration_s
2026-07-01,load_fct_orders,SUCCESS,182450,2026-07-01T02:00:11Z,2026-07-01T02:14:02Z,831
2026-07-02,load_fct_orders,SUCCESS,181002,2026-07-02T02:00:09Z,2026-07-02T02:13:44Z,815
2026-07-03,load_fct_orders,SUCCESS,179884,2026-07-03T02:00:12Z,2026-07-03T02:15:20Z,908
2026-07-04,load_fct_orders,SUCCESS,180551,2026-07-04T02:00:10Z,2026-07-04T02:14:31Z,861
2026-07-05,load_fct_orders,SUCCESS,12004,2026-07-05T02:00:14Z,2026-07-05T02:03:02Z,168
2026-07-06,load_fct_orders,SUCCESS,178990,2026-07-06T02:00:08Z,2026-07-06T02:14:12Z,844
2026-07-07,load_fct_orders,FAILED,0,2026-07-07T02:00:11Z,2026-07-07T02:01:55Z,104
2026-07-08,load_fct_orders,SUCCESS,361200,2026-07-08T02:00:13Z,2026-07-08T02:41:07Z,2454
2026-07-09,load_fct_orders,SUCCESS,180117,2026-07-09T02:00:10Z,2026-07-09T02:14:55Z,885
2026-07-10,load_fct_orders,SUCCESS,181433,2026-07-10T05:41:02Z,2026-07-10T05:55:40Z,878
"""

_QUERY_HISTORY_CSV = """query_id,user,warehouse,started_at,elapsed_ms,bytes_scanned,rows,statement
q_1001,svc_etl,WH_ETL,2026-07-03T02:01:00Z,412000,88123456789,182450,INSERT INTO ANALYTICS.FCT_ORDERS SELECT ...
q_1002,analyst_a,WH_BI,2026-07-03T09:14:00Z,38200,2312456789,1204,SELECT * FROM ANALYTICS.CUSTOMER_360 WHERE lifetime_value > 1000
q_1003,analyst_b,WH_BI,2026-07-03T09:41:00Z,41100,2298113456,1188,SELECT * FROM ANALYTICS.CUSTOMER_360 WHERE last_order_ts > CURRENT_DATE - 30
q_1004,svc_bi,WH_BI,2026-07-03T10:00:00Z,712000,44123456789,88213,SELECT category SUM(amount_usd) FROM ANALYTICS.FCT_ORDERS GROUP BY 1
q_1005,analyst_a,WH_ADHOC,2026-07-03T11:22:00Z,1841000,192334455667,4,SELECT COUNT(*) FROM RAW.ORDERS o JOIN RAW.ORDER_ITEMS i ON 1=1
q_1006,svc_etl,WH_ETL,2026-07-04T02:01:00Z,398000,87991234567,180551,INSERT INTO ANALYTICS.FCT_ORDERS SELECT ...
"""

_GRANTS_CSV = """grantee,grantee_type,privilege,object,object_type,granted_by,granted_at
FINANCE_ANALYST,ROLE,SELECT,ANALYTICS.FCT_ORDERS,TABLE,SECURITYADMIN,2025-02-11
FINANCE_ANALYST,ROLE,SELECT,ANALYTICS.CUSTOMER_360,VIEW,SECURITYADMIN,2025-02-11
MARKETING,ROLE,SELECT,ANALYTICS.CUSTOMER_360,VIEW,SECURITYADMIN,2025-06-03
CONTRACTOR_TEMP,ROLE,SELECT,ANALYTICS.CUSTOMER_360,VIEW,SECURITYADMIN,2024-08-19
CONTRACTOR_TEMP,ROLE,SELECT,LEGACY.CUST_MAST,TABLE,SECURITYADMIN,2024-08-19
DATA_PLATFORM,ROLE,OWNERSHIP,ANALYTICS,SCHEMA,ACCOUNTADMIN,2024-01-05
PUBLIC,ROLE,SELECT,ANALYTICS.CUSTOMER_360,VIEW,SECURITYADMIN,2026-01-22
"""

_BI_INVENTORY_CSV = """report_id,name,workspace,owner,last_opened,views_30d,source_objects
rpt_001,Revenue by Category,Commercial,priya@example.com,2026-07-09,412,ANALYTICS.FCT_ORDERS
rpt_002,Revenue by Category (copy),Commercial,raj@example.com,2026-03-02,3,ANALYTICS.FCT_ORDERS
rpt_003,Revenue by Category FINAL v2,Commercial,raj@example.com,2026-07-08,388,ANALYTICS.FCT_ORDERS
rpt_004,Customer LTV,Marketing,dana@example.com,2026-07-10,204,ANALYTICS.CUSTOMER_360
rpt_005,Customer LTV OLD,Marketing,,2025-11-14,0,ANALYTICS.CUSTOMER_360
rpt_006,Ops Freshness Monitor,Data Platform,dana@example.com,2026-07-10,96,AUDIT.LOAD_LOG
"""

_SCHEMA_SNAPSHOTS_CSV = """snapshot_date,object,column,data_type,is_nullable
2026-06-01,ANALYTICS.FCT_ORDERS,order_id,NUMBER,NO
2026-06-01,ANALYTICS.FCT_ORDERS,customer_id,NUMBER,NO
2026-06-01,ANALYTICS.FCT_ORDERS,amount_usd,NUMBER(122),YES
2026-06-01,ANALYTICS.FCT_ORDERS,category,VARCHAR,YES
2026-07-01,ANALYTICS.FCT_ORDERS,order_id,NUMBER,NO
2026-07-01,ANALYTICS.FCT_ORDERS,customer_id,VARCHAR,NO
2026-07-01,ANALYTICS.FCT_ORDERS,amount_usd,NUMBER(122),YES
2026-07-01,ANALYTICS.FCT_ORDERS,category,VARCHAR,YES
2026-07-01,ANALYTICS.FCT_ORDERS,channel,VARCHAR,YES
"""

# ---------------------------------------------------------------------- #
# Policy documents — agents 02, 05, 13, 20, 26, 27, 28
# ---------------------------------------------------------------------- #

_TAXONOMY_MD = """# Sensitivity taxonomy — ACME Data Governance

| Label | Definition | Handling |
|---|---|---|
| PUBLIC | Publishable without restriction. | No control. |
| INTERNAL | Default for business data. | Authenticated access only. |
| CONFIDENTIAL | Commercially sensitive. | Named roles; access reviewed quarterly. |
| RESTRICTED | Personal or regulated data. | Masking required; access reviewed monthly. |

## Regulatory scope
- **GDPR** applies to any column identifying an EU natural person.
- **PCI-DSS** applies to cardholder data. Primary account numbers must never
  land in the analytics estate in clear text.
- **SOX** applies to any asset feeding statutory financial reporting.

## Rules
1. A column containing a national identifier is RESTRICTED without exception.
2. An email address belonging to a customer is RESTRICTED; an internal
   distribution list is INTERNAL.
3. A derived column inherits the highest sensitivity of its inputs.
"""

_GLOSSARY_MD = """# Governed business glossary — extract

## Customer
A party that has placed at least one completed order. Steward: commercial-ops.
Excludes prospects and closed accounts. Version 4.2, approved 2026-02-10.

## Active customer
A Customer with a completed order in the trailing 12 months. Steward:
commercial-ops. Note: the marketing team uses a 24-month definition in their
own reporting; the governed definition is 12 months.

## Lifetime value
Sum of net order value in USD across the whole relationship, excluding tax,
refunds and cancelled orders. Steward: finance. Version 2.0.

## Order date
The timestamp at which the order was accepted, not when it was placed or
shipped. Steward: commercial-ops.

## Region
The sales region of the shipping address, not the billing address. Steward:
commercial-ops.
"""

_ENTITLEMENT_MATRIX_MD = """# Role-entitlement matrix (human-owned)

| Role | Permitted sensitivity | Notes |
|---|---|---|
| FINANCE_ANALYST | Up to CONFIDENTIAL | No RESTRICTED columns. |
| MARKETING | Up to INTERNAL | Aggregates only over customer data. |
| DATA_PLATFORM | All | Break-glass; every use is logged and reviewed. |
| CONTRACTOR_TEMP | Up to INTERNAL | Time-boxed; must expire within 90 days. |
| PUBLIC | None | No grants to PUBLIC in any environment. |

## Standing rules
1. No role receives RESTRICTED access without a named data-protection approval.
2. Contractor roles are reviewed every 30 days and revoked on contract end.
3. Grants to PUBLIC are prohibited.
"""

_ACTION_CATALOG_MD = """# Approved remediation action catalog v3.1

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
- Unbounded backfills.
"""

_RETENTION_POLICY_MD = """# Retention and legal-hold policy

| Data class | Minimum retention | Maximum retention | Basis |
|---|---|---|---|
| Financial transactions | 7 years | 10 years | SOX |
| Customer personal data | Duration of relationship | +2 years | GDPR minimisation |
| Marketing telemetry | 13 months | 25 months | Consent terms |
| Pipeline logs | 90 days | 1 year | Operational |

## Legal holds in force
- `LEGACY.CUST_MAST` — hold LH-2026-004, opened 2026-03-11, no deletion or
  archival permitted while open.
"""

_SLA_MD = """# Data product SLAs — revenue domain

## ANALYTICS.FCT_ORDERS
- Freshness: available by 06:00 UTC each day.
- Completeness: >= 99.5% of source orders present within 24 hours.
- Schema: breaking changes require 30 days' notice to registered consumers.
- Owner: revenue-data-team. Escalation: #revenue-data-oncall.

### Registered consumers
| Consumer | Contact | Dependency |
|---|---|---|
| Commercial BI | priya@example.com | rpt_001, rpt_003 |
| Finance close | finance-systems@example.com | Monthly statutory pack |
| Marketing CDP | dana@example.com | Nightly export |
"""

_CONTROL_CATALOG_MD = """# Control catalog extract — SOC 2 / internal

| Control | Requirement | Evidence expected |
|---|---|---|
| CC6.1 | Logical access is restricted to authorised users. | Grants inventory + entitlement matrix + review record |
| CC7.2 | Anomalies are detected and acted upon. | Monitoring config + incident records |
| CC8.1 | Changes are authorised, tested and approved. | Change tickets + PR approvals |
| PI1.4 | Data is complete and accurate. | Reconciliation results + DQ scorecards |

## Evidence template
Every item requires: control ID, asset, evidence artifact, date produced,
producer, and the approval record that accepted it.
"""

_INCIDENT_LOG = """2026-07-07T02:00:11Z INFO  task=load_fct_orders run=r_88421 starting
2026-07-07T02:00:14Z INFO  task=load_fct_orders acquired warehouse WH_ETL
2026-07-07T02:00:52Z WARN  task=load_fct_orders source REF.EXCHANGE_RATES returned 0 rows for rate_date=2026-07-06
2026-07-07T02:01:40Z ERROR task=load_fct_orders SQL compilation error: invalid identifier 'O.CUSTOMER_ID'
2026-07-07T02:01:41Z ERROR task=load_fct_orders run failed after 104s, 0 rows loaded
2026-07-07T02:01:42Z INFO  task=load_fct_orders downstream tasks skipped: refresh_customer_360, export_marketing_cdp
2026-07-07T02:05:00Z INFO  alert=freshness_breach asset=ANALYTICS.FCT_ORDERS age_hours=26.1
2026-07-06T18:22:04Z INFO  deploy=revenue-pipelines commit=9f2c1ab "rename customer_id to cust_id in staging"
"""

_FILES: dict[str, str] = {
    "legacy/CUSTMAST.cpy": _CUSTMAST_COPYBOOK,
    "legacy/RSKCALC.cbl": _RSKCALC,
    "legacy/m_LOAD_CUSTOMER.xml": _INFORMATICA_XML,
    "warehouse-code/load_fct_orders.sql": _LOAD_ORDERS_SQL,
    "warehouse-code/customer_360.sql": _CUSTOMER_360_SQL,
    "telemetry/warehouse_metering.csv": _METERING_CSV,
    "telemetry/pipeline_runs.csv": _PIPELINE_TELEMETRY_CSV,
    "telemetry/query_history.csv": _QUERY_HISTORY_CSV,
    "telemetry/grants_inventory.csv": _GRANTS_CSV,
    "telemetry/bi_inventory.csv": _BI_INVENTORY_CSV,
    "telemetry/schema_snapshots.csv": _SCHEMA_SNAPSHOTS_CSV,
    "telemetry/incident_2026-07-07.log": _INCIDENT_LOG,
    "policies/sensitivity-taxonomy.md": _TAXONOMY_MD,
    "policies/business-glossary.md": _GLOSSARY_MD,
    "policies/role-entitlement-matrix.md": _ENTITLEMENT_MATRIX_MD,
    "policies/remediation-action-catalog.md": _ACTION_CATALOG_MD,
    "policies/retention-and-legal-hold.md": _RETENTION_POLICY_MD,
    "policies/data-product-slas.md": _SLA_MD,
    "policies/control-catalog.md": _CONTROL_CATALOG_MD,
}


def ensure_demo_documents(root: Path) -> None:
    """Write the sample workspace once, under a lock.

    Same shape as the demo warehouse seeding: two requests arriving together on
    a cold start must not both write the tree.
    """
    marker = root / ".seeded"
    if marker.exists():
        return
    with _SEED_LOCK:
        if marker.exists():
            return
        for relative, content in _FILES.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        marker.write_text("ADE Studio sample documents\n", encoding="utf-8")


FILE_COUNT = len(_FILES)
