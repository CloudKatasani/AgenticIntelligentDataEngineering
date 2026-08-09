"""A seeded DuckDB warehouse so the product demos without credentials.

The data is deliberately imperfect: null clusters, format drift, negative
amounts, duplicate keys and PII-shaped columns. Those defects are what give the
classification, quality, profiling and modernization agents something real to
find during a demo.

Generation is seeded, so every install produces byte-identical data and demo
runs are reproducible.
"""

from __future__ import annotations

import csv
import os
import random
import tempfile
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.domain.connection import (
    ColumnMeta,
    ConnectionHealth,
    DatasetRef,
    SourceKind,
    TableMeta,
    TableProfile,
)
from app.ports.source_connector import SourceConnector, assert_read_only

_SEED = 20260809
_FIRST = ["Ana", "Marcus", "Priya", "Chen", "Fatima", "Diego", "Sofia", "Kwame", "Yuki", "Omar",
          "Lena", "Tomas", "Nadia", "Ravi", "Elena", "Jonas", "Mei", "Ibrahim", "Clara", "Hugo"]
_LAST = ["Silva", "Okafor", "Nakamura", "Petrov", "Haddad", "Andersen", "Reyes", "Kaur", "Novak",
         "Fischer", "Moreau", "Dubois", "Yilmaz", "Costa", "Bauer", "Ivanov", "Rossi", "Khan"]
_CITIES = [("Lisbon", "PT"), ("Berlin", "DE"), ("Austin", "US"), ("Toronto", "CA"),
           ("Nairobi", "KE"), ("Osaka", "JP"), ("Bogota", "CO"), ("Dublin", "IE")]
_CATEGORIES = ["Outdoor", "Kitchen", "Audio", "Fitness", "Office", "Garden"]
_ORDER_STATUS = ["COMPLETED", "SHIPPED", "PENDING", "CANCELLED", "RETURNED"]
_CHANNELS = ["web", "mobile", "partner", "retail"]


class DemoConnector(SourceConnector):
    """DuckDB-backed sandbox warehouse.

    Presents itself like any other source: the run engine cannot tell it apart
    from Snowflake through the :class:`SourceConnector` interface.
    """

    kind = SourceKind.DEMO

    def __init__(self, connection: Any) -> None:  # noqa: ANN401 — SourceConnection
        super().__init__(connection)
        from app.core.config import get_settings

        self.path = Path(connection.file_path or get_settings().demo_warehouse_path)

    # ------------------------------------------------------------------ #

    @classmethod
    def driver_available(cls) -> bool:
        try:
            import duckdb  # noqa: F401
        except ImportError:  # pragma: no cover
            return False
        return True

    @classmethod
    def install_hint(cls) -> str:
        return "pip install duckdb"

    def _db(self) -> Any:
        import duckdb

        ensure_demo_warehouse(self.path)
        return duckdb.connect(str(self.path), read_only=True)

    def _rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        assert_read_only(sql)
        con = self._db()
        try:
            cursor = con.execute(sql, params)
            names = [d[0] for d in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
        finally:
            con.close()

    @staticmethod
    def _quote(identifier: str) -> str:
        cleaned = identifier.replace('"', "")
        return f'"{cleaned}"'

    def _fqn(self, ref: DatasetRef) -> str:
        parts = [p for p in (ref.schema_name, ref.table) if p]
        return ".".join(self._quote(p) for p in parts)

    # ------------------------------------------------------------------ #

    def test_connection(self) -> ConnectionHealth:
        if not self.driver_available():
            return ConnectionHealth(
                ok=False, detail=f"Driver not installed. {self.install_hint()}", driver_installed=False
            )
        rows = self._rows("SELECT count(*) AS n FROM information_schema.tables")
        return ConnectionHealth(
            ok=True,
            detail=f"Demo warehouse ready ({rows[0]['n']} objects). No credentials required.",
            latency_ms=1,
            server_version="duckdb (embedded demo warehouse)",
        )

    def list_databases(self) -> list[str]:
        return ["ADE_DEMO"]

    def list_schemas(self, database: str | None) -> list[str]:
        rows = self._rows(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('information_schema','pg_catalog','main') ORDER BY 1"
        )
        return [r["schema_name"] for r in rows]

    def list_tables(self, database: str | None, schema: str | None) -> list[TableMeta]:
        rows = self._rows(
            "SELECT table_name, table_type FROM information_schema.tables "
            "WHERE table_schema = ? ORDER BY table_name",
            (schema or "RETAIL",),
        )
        tables: list[TableMeta] = []
        for row in rows:
            ref = DatasetRef(
                connection_id=self.connection.id, database=database, schema_name=schema,
                table=row["table_name"],
            )
            count = self._rows(f"SELECT count(*) AS n FROM {self._fqn(ref)}")[0]["n"]
            tables.append(
                TableMeta(
                    database=database,
                    schema_name=schema,
                    name=row["table_name"],
                    kind=row["table_type"],
                    row_count=int(count),
                )
            )
        return tables

    def describe_table(self, ref: DatasetRef) -> TableMeta:
        rows = self._rows(
            "SELECT column_name, data_type, is_nullable, ordinal_position "
            "FROM information_schema.columns WHERE table_schema = ? AND table_name = ? "
            "ORDER BY ordinal_position",
            (ref.schema_name or "RETAIL", ref.table),
        )
        columns = [
            ColumnMeta(
                name=r["column_name"],
                data_type=str(r["data_type"]),
                nullable=str(r["is_nullable"]).upper() in {"YES", "TRUE"},
                ordinal=int(r["ordinal_position"]),
            )
            for r in rows
            if not ref.columns or r["column_name"] in ref.columns
        ]
        return TableMeta(
            database=ref.database, schema_name=ref.schema_name, name=ref.table, columns=columns
        )

    def sample_rows(self, ref: DatasetRef, limit: int) -> list[dict[str, Any]]:
        table = self.describe_table(ref)
        if not table.columns:
            return []
        projection = ", ".join(self._quote(c.name) for c in table.columns)
        return self._rows(f"SELECT {projection} FROM {self._fqn(ref)} LIMIT {int(limit)}")

    def profile_table(self, ref: DatasetRef, sample_limit: int) -> TableProfile:
        table = self.describe_table(ref)
        rows = self.sample_rows(ref, sample_limit)
        total = int(self._rows(f"SELECT count(*) AS n FROM {self._fqn(ref)}")[0]["n"])
        strategy = (
            f"first {len(rows)} rows of {total}"
            if total > len(rows)
            else f"full scan ({total} rows, below sample limit)"
        )
        return self._profile_from_rows(table, rows, total, strategy)


# --------------------------------------------------------------------------- #
# Seeding
# --------------------------------------------------------------------------- #


_NULL_SENTINEL = "\\N"


def _insert(con: Any, table: str, rows: list[tuple[Any, ...]], width: int) -> None:
    """Bulk-load rows via a temporary CSV.

    Seeding is on the first-request path — the demo warehouse is built the first
    time anything touches it — so it has to be fast. Row-at-a-time
    ``executemany`` takes ~2 minutes for this dataset and chunked multi-row
    ``INSERT`` still takes ~30 seconds; ``COPY`` from a CSV does it in well
    under a second.
    """
    if not rows:
        return
    assert all(len(row) == width for row in rows), f"{table}: row width mismatch"

    with tempfile.NamedTemporaryFile("w", suffix=".csv", newline="", delete=False) as handle:
        writer = csv.writer(handle)
        for row in rows:
            writer.writerow(
                [
                    _NULL_SENTINEL
                    if value is None
                    else ("true" if value is True else "false" if value is False else value)
                    for value in row
                ]
            )
        csv_path = handle.name

    try:
        con.execute(
            f"COPY {table} FROM '{csv_path}' "
            f"(FORMAT CSV, HEADER FALSE, NULLSTR '{_NULL_SENTINEL}')"
        )
    finally:
        Path(csv_path).unlink(missing_ok=True)


_SEED_LOCK = threading.Lock()


def ensure_demo_warehouse(path: Path) -> None:
    """Seed the warehouse once, safely, under concurrent first requests.

    The UI opens the object picker by firing catalog, schema and table requests
    in parallel. Without this guard each of them starts its own seed and DuckDB
    raises a write-write conflict on the first ``CREATE SCHEMA``.
    """
    if path.exists():
        return
    with _SEED_LOCK:
        if not path.exists():  # another thread may have finished while we waited
            seed_demo_warehouse(path)


def seed_demo_warehouse(path: Path) -> None:
    """Create the demo warehouse. Idempotent: rebuilds the file from scratch.

    Built under a temporary name and moved into place, so a reader never sees a
    half-populated database.
    """
    import duckdb

    rng = random.Random(_SEED)
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(f"{path.name}.{os.getpid()}.building")
    staging.unlink(missing_ok=True)

    con = duckdb.connect(str(staging))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS RETAIL")
        con.execute("CREATE SCHEMA IF NOT EXISTS FINANCE")
        con.execute("CREATE SCHEMA IF NOT EXISTS LEGACY")
        _seed_retail(con, rng)
        _seed_finance(con, rng)
        _seed_legacy(con, rng)
    finally:
        con.close()

    os.replace(staging, path)


def _seed_retail(con: Any, rng: random.Random) -> None:
    base = date(2024, 1, 1)

    con.execute(
        """
        CREATE TABLE RETAIL.CUSTOMERS (
            customer_id       BIGINT,
            first_name        VARCHAR,
            last_name         VARCHAR,
            email             VARCHAR,
            phone             VARCHAR,
            national_id       VARCHAR,
            date_of_birth     DATE,
            city              VARCHAR,
            country_code      VARCHAR,
            marketing_opt_in  BOOLEAN,
            signup_date       DATE,
            lifetime_value    DECIMAL(12,2)
        )
        """
    )
    customers: list[tuple[Any, ...]] = []
    for i in range(1, 2001):
        first, last = rng.choice(_FIRST), rng.choice(_LAST)
        city, country = rng.choice(_CITIES)
        # 4% missing e-mail, 3% malformed — a real completeness/validity finding.
        if i % 25 == 0:
            email = None
        elif i % 33 == 0:
            email = f"{first.lower()}.{last.lower()}@@invalid"
        else:
            email = f"{first.lower()}.{last.lower()}{i}@example.com"
        # Phone format drift across three conventions — a standardisation finding.
        digits = f"{rng.randint(200, 999)}{rng.randint(1000000, 9999999)}"
        phone = [f"+1-{digits[:3]}-{digits[3:6]}-{digits[6:]}",
                 f"({digits[:3]}) {digits[3:6]}-{digits[6:]}",
                 digits][i % 3]
        customers.append(
            (
                i, first, last, email, phone,
                f"{rng.randint(100, 899)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}",
                base - timedelta(days=rng.randint(6570, 25550)),
                city, country,
                rng.random() > 0.35,
                base + timedelta(days=rng.randint(0, 700)),
                round(rng.uniform(0, 8400), 2),
            )
        )
    _insert(con, "RETAIL.CUSTOMERS", customers, 12)

    con.execute(
        """
        CREATE TABLE RETAIL.PRODUCTS (
            product_id     BIGINT,
            sku            VARCHAR,
            product_name   VARCHAR,
            category       VARCHAR,
            unit_cost      DECIMAL(10,2),
            list_price     DECIMAL(10,2),
            active_flag    VARCHAR,
            introduced_on  DATE
        )
        """
    )
    products = []
    for i in range(1, 301):
        cost = round(rng.uniform(3, 320), 2)
        products.append(
            (
                i, f"SKU-{i:05d}", f"{rng.choice(_CATEGORIES)} item {i}", rng.choice(_CATEGORIES),
                cost, round(cost * rng.uniform(1.15, 2.6), 2),
                # Boolean encoded three different ways — a typing finding.
                ["Y", "N", "true", "1"][i % 4],
                base + timedelta(days=rng.randint(-900, 500)),
            )
        )
    _insert(con, "RETAIL.PRODUCTS", products, 8)

    con.execute(
        """
        CREATE TABLE RETAIL.ORDERS (
            order_id       BIGINT,
            customer_id    BIGINT,
            order_ts       TIMESTAMP,
            status         VARCHAR,
            channel        VARCHAR,
            order_total    DECIMAL(12,2),
            currency_code  VARCHAR,
            shipped_ts     TIMESTAMP
        )
        """
    )
    orders = []
    for i in range(1, 8001):
        ordered = base + timedelta(days=rng.randint(0, 730), hours=rng.randint(0, 23))
        status = rng.choices(_ORDER_STATUS, weights=[62, 18, 10, 6, 4])[0]
        # 0.5% carry a status not in the documented domain — a validity finding.
        if i % 200 == 0:
            status = "legacy_migrated"
        orders.append(
            (
                i, rng.randint(1, 2000), ordered, status, rng.choice(_CHANNELS),
                round(rng.uniform(8, 1200), 2), "USD",
                ordered + timedelta(days=rng.randint(1, 9)) if status in {"COMPLETED", "SHIPPED"} else None,
            )
        )
    _insert(con, "RETAIL.ORDERS", orders, 8)

    con.execute(
        """
        CREATE TABLE RETAIL.ORDER_ITEMS (
            order_item_id  BIGINT,
            order_id       BIGINT,
            product_id     BIGINT,
            quantity       INTEGER,
            unit_price     DECIMAL(10,2),
            discount_pct   DECIMAL(5,2),
            line_total     DECIMAL(12,2)
        )
        """
    )
    items = []
    line = 0
    for order_id in range(1, 8001):
        for _ in range(rng.randint(1, 4)):
            line += 1
            qty = rng.randint(1, 6)
            price = round(rng.uniform(4, 400), 2)
            # 0.2% negative unit price — a range-violation finding.
            if line % 500 == 0:
                price = -price
            discount = round(rng.choice([0, 0, 0, 5, 10, 15, 25]), 2)
            items.append(
                (line, order_id, rng.randint(1, 300), qty, price, discount,
                 round(qty * price * (1 - discount / 100), 2))
            )
    _insert(con, "RETAIL.ORDER_ITEMS", items, 7)

    con.execute(
        """
        CREATE TABLE RETAIL.PAYMENTS (
            payment_id       BIGINT,
            order_id         BIGINT,
            paid_ts          TIMESTAMP,
            method           VARCHAR,
            card_number      VARCHAR,
            card_holder      VARCHAR,
            amount           DECIMAL(12,2),
            auth_code        VARCHAR
        )
        """
    )
    payments = []
    for i in range(1, 7801):
        payments.append(
            (
                i, i, base + timedelta(days=rng.randint(0, 730)),
                rng.choice(["card", "card", "card", "paypal", "transfer"]),
                # PAN-shaped values: agent 02 should classify this as PCI data.
                f"4{rng.randint(10**14, 10**15 - 1)}",
                f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
                round(rng.uniform(8, 1200), 2),
                f"AUTH{rng.randint(100000, 999999)}",
            )
        )
    _insert(con, "RETAIL.PAYMENTS", payments, 8)


def _seed_finance(con: Any, rng: random.Random) -> None:
    base = date(2024, 1, 1)
    con.execute(
        """
        CREATE TABLE FINANCE.ACCOUNTS (
            account_id    BIGINT,
            account_code  VARCHAR,
            account_name  VARCHAR,
            account_type  VARCHAR,
            is_active     BOOLEAN
        )
        """
    )
    types = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"]
    _insert(
        con,
        "FINANCE.ACCOUNTS",
        [
            (i, f"{rng.randint(1000, 9999)}", f"Account {i}", rng.choice(types), rng.random() > 0.1)
            for i in range(1, 121)
        ],
        5,
    )

    con.execute(
        """
        CREATE TABLE FINANCE.GL_TRANSACTIONS (
            txn_id         BIGINT,
            account_id     BIGINT,
            posted_date    DATE,
            debit_amount   DECIMAL(14,2),
            credit_amount  DECIMAL(14,2),
            currency_code  VARCHAR,
            source_system  VARCHAR,
            memo           VARCHAR
        )
        """
    )
    txns = []
    for i in range(1, 5001):
        debit = round(rng.uniform(0, 50000), 2) if i % 2 else 0.0
        txns.append(
            (
                i, rng.randint(1, 120), base + timedelta(days=rng.randint(0, 730)),
                debit, 0.0 if debit else round(rng.uniform(0, 50000), 2),
                rng.choice(["USD", "USD", "EUR", "GBP"]),
                rng.choice(["ERP", "ERP", "LEGACY_GL", "MANUAL"]),
                # 8% of memos are blank — a completeness finding on a field
                # compliance reporting depends on.
                None if i % 12 == 0 else f"Journal entry {i}",
            )
        )
    _insert(con, "FINANCE.GL_TRANSACTIONS", txns, 8)

    con.execute(
        """
        CREATE TABLE FINANCE.EXCHANGE_RATES (
            rate_date      DATE,
            from_currency  VARCHAR,
            to_currency    VARCHAR,
            rate           DECIMAL(18,8)
        )
        """
    )
    rates = []
    for offset in range(200):
        for pair in [("EUR", "USD"), ("GBP", "USD")]:
            rates.append(
                (base + timedelta(days=offset), pair[0], pair[1], round(rng.uniform(0.8, 1.4), 8))
            )
    _insert(con, "FINANCE.EXCHANGE_RATES", rates, 4)


def _seed_legacy(con: Any, rng: random.Random) -> None:
    """A mainframe-style extract: cryptic names, packed fields, duplicate keys.

    This is the table the modernization and glossary agents are interesting on.
    """
    con.execute(
        """
        CREATE TABLE LEGACY.CUST_MAST (
            CUST_NO    VARCHAR,
            CUST_NM    VARCHAR,
            ADDR_LN1   VARCHAR,
            ST_CD      VARCHAR,
            ZIP_CD     VARCHAR,
            STAT_CD    VARCHAR,
            CRT_DT     VARCHAR,
            BAL_AMT    VARCHAR
        )
        """
    )
    rows = []
    for i in range(1, 2101):
        # 100 duplicated customer numbers: the legacy file has no enforced key.
        number = f"{(i if i <= 2000 else i - 2000):08d}"
        rows.append(
            (
                number,
                f"{rng.choice(_LAST).upper()}, {rng.choice(_FIRST).upper()}",
                f"{rng.randint(1, 9999)} {rng.choice(['MAIN', 'OAK', 'ELM'])} ST",
                rng.choice(["TX", "CA", "NY", "IL"]),
                f"{rng.randint(10000, 99999)}",
                rng.choice(["A", "I", "P"]),
                f"{rng.randint(1990, 2024)}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}",
                f"{rng.randint(0, 999999):09d}",  # implied 2 decimal places
            )
        )
    _insert(con, "LEGACY.CUST_MAST", rows, 8)
