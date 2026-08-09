"""Seeding must be safe under the parallel requests the UI actually makes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.adapters.connectors.demo import DemoConnector, ensure_demo_warehouse
from app.domain.connection import SourceConnection, SourceKind


def test_concurrent_first_requests_seed_exactly_once(tmp_path: Path) -> None:
    """The object picker fires catalog, schema and table reads in parallel.

    Before the guard, each one started its own seed and DuckDB raised a
    write-write conflict on the first CREATE SCHEMA.
    """
    warehouse = tmp_path / "demo.duckdb"
    connection = SourceConnection(
        id="c", name="demo", kind=SourceKind.DEMO, file_path=str(warehouse)
    )

    def read() -> list[str]:
        return DemoConnector(connection).list_schemas(None)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = [future.result() for future in [pool.submit(read) for _ in range(6)]]

    assert all(set(result) == {"FINANCE", "LEGACY", "RETAIL"} for result in results)
    # No staging file is left behind.
    assert [p.name for p in tmp_path.iterdir()] == ["demo.duckdb"]


def test_seeding_is_atomic(tmp_path: Path) -> None:
    warehouse = tmp_path / "demo.duckdb"
    ensure_demo_warehouse(warehouse)
    assert warehouse.exists()
    first = warehouse.stat().st_mtime_ns

    # A second call is a no-op: the file is not rebuilt.
    ensure_demo_warehouse(warehouse)
    assert warehouse.stat().st_mtime_ns == first


def test_seed_is_deterministic(tmp_path: Path) -> None:
    """Two installs must produce identical demo data, so demos are reproducible."""
    import duckdb

    from app.adapters.connectors.demo import seed_demo_warehouse

    def fingerprint(path: Path) -> list[tuple]:
        seed_demo_warehouse(path)
        con = duckdb.connect(str(path), read_only=True)
        try:
            return con.execute(
                "SELECT customer_id, email, phone FROM RETAIL.CUSTOMERS ORDER BY customer_id LIMIT 50"
            ).fetchall()
        finally:
            con.close()

    assert fingerprint(tmp_path / "a.duckdb") == fingerprint(tmp_path / "b.duckdb")
