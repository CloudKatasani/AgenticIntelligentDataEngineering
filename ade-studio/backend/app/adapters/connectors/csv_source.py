"""CSV / flat-file source.

Files in a directory are presented as tables, so a client can point an agent at
an extract without standing up a database. Reads are delegated to DuckDB, which
gives typed columns and pushdown for free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.errors import ConnectionFailed
from app.domain.connection import (
    ColumnMeta,
    ConnectionHealth,
    DatasetRef,
    SourceKind,
    TableMeta,
    TableProfile,
)
from app.ports.source_connector import SourceConnector

_SUFFIXES = {".csv", ".tsv", ".txt", ".parquet", ".json"}


class CSVConnector(SourceConnector):
    kind = SourceKind.CSV

    def __init__(self, connection: Any) -> None:  # noqa: ANN401 — SourceConnection
        super().__init__(connection)
        self.root = Path(connection.file_path or ".").expanduser().resolve()

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

    def _resolve(self, table: str) -> Path:
        """Resolve a table name to a file, refusing anything outside the root."""
        candidate = (self.root / table).resolve()
        if not candidate.is_relative_to(self.root):
            raise ConnectionFailed(f"Path escapes the configured root: {table!r}")
        if not candidate.exists():
            raise ConnectionFailed(f"File not found: {candidate}")
        return candidate

    def _reader(self, path: Path) -> str:
        if path.suffix == ".parquet":
            return f"read_parquet('{path}')"
        if path.suffix == ".json":
            return f"read_json_auto('{path}')"
        return f"read_csv_auto('{path}', SAMPLE_SIZE=-1)"

    def _query(self, sql: str) -> list[dict[str, Any]]:
        import duckdb

        con = duckdb.connect()
        try:
            cursor = con.execute(sql)
            names = [d[0] for d in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
        finally:
            con.close()

    def test_connection(self) -> ConnectionHealth:
        if not self.root.exists():
            return ConnectionHealth(ok=False, detail=f"Directory not found: {self.root}")
        files = [p for p in self.root.iterdir() if p.suffix.lower() in _SUFFIXES]
        return ConnectionHealth(
            ok=True, detail=f"{len(files)} readable files at {self.root}", latency_ms=1
        )

    def list_databases(self) -> list[str]:
        return [self.root.name or "files"]

    def list_schemas(self, database: str | None) -> list[str]:
        return ["files"]

    def list_tables(self, database: str | None, schema: str | None) -> list[TableMeta]:
        tables: list[TableMeta] = []
        for path in sorted(self.root.iterdir()):
            if path.suffix.lower() not in _SUFFIXES:
                continue
            try:
                count = self._query(f"SELECT count(*) AS n FROM {self._reader(path)}")[0]["n"]
            except Exception:  # noqa: BLE001 — an unreadable file is listed, not fatal
                count = None
            tables.append(
                TableMeta(
                    database=database, schema_name="files", name=path.name,
                    kind="FILE", row_count=int(count) if count is not None else None,
                )
            )
        return tables

    def describe_table(self, ref: DatasetRef) -> TableMeta:
        path = self._resolve(ref.table)
        rows = self._query(f"DESCRIBE SELECT * FROM {self._reader(path)}")
        columns = [
            ColumnMeta(
                name=str(r["column_name"]),
                data_type=str(r["column_type"]),
                nullable=str(r.get("null", "YES")).upper() != "NO",
                ordinal=i,
            )
            for i, r in enumerate(rows)
            if not ref.columns or r["column_name"] in ref.columns
        ]
        return TableMeta(schema_name="files", name=ref.table, kind="FILE", columns=columns)

    def sample_rows(self, ref: DatasetRef, limit: int) -> list[dict[str, Any]]:
        path = self._resolve(ref.table)
        table = self.describe_table(ref)
        projection = ", ".join(f'"{c.name}"' for c in table.columns) or "*"
        return self._query(f"SELECT {projection} FROM {self._reader(path)} LIMIT {int(limit)}")

    def profile_table(self, ref: DatasetRef, sample_limit: int) -> TableProfile:
        path = self._resolve(ref.table)
        table = self.describe_table(ref)
        rows = self.sample_rows(ref, sample_limit)
        total = int(self._query(f"SELECT count(*) AS n FROM {self._reader(path)}")[0]["n"])
        strategy = f"first {len(rows)} rows of {total}" if total > len(rows) else "full scan"
        return self._profile_from_rows(table, rows, total, strategy)
