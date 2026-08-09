"""Shared behaviour for DB-API 2.0 source adapters.

Each dialect differs only in how it names catalogs, where its information
schema lives, and how it limits a result set. Everything else — cursor
handling, row shaping, read-only enforcement, profiling — lives here once.
"""

from __future__ import annotations

import time
from abc import abstractmethod
from typing import Any, Iterable

from app.core.errors import ConnectionFailed, DriverUnavailable
from app.domain.connection import (
    ColumnMeta,
    ConnectionHealth,
    DatasetRef,
    TableMeta,
    TableProfile,
)
from app.ports.source_connector import SourceConnector, assert_read_only


class SQLConnector(SourceConnector):
    """A source reachable over a DB-API connection."""

    quote_char = '"'
    supports_catalogs = True

    # ------------------------------------------------------------------ #
    # Adapter hooks
    # ------------------------------------------------------------------ #

    @abstractmethod
    def _connect(self) -> Any:
        """Open a raw DB-API connection. Raises on failure."""

    @abstractmethod
    def _version_query(self) -> str: ...

    @abstractmethod
    def _databases_query(self) -> str | None: ...

    @abstractmethod
    def _schemas_query(self, database: str | None) -> str: ...

    @abstractmethod
    def _tables_query(self, database: str | None, schema: str | None) -> str: ...

    @abstractmethod
    def _columns_query(self, ref: DatasetRef) -> str: ...

    def _limit_clause(self, limit: int) -> str:
        return f"LIMIT {int(limit)}"

    # ------------------------------------------------------------------ #
    # Shared plumbing
    # ------------------------------------------------------------------ #

    def quote(self, identifier: str) -> str:
        """Quote an identifier, refusing anything that could break out of it."""
        cleaned = identifier.replace(self.quote_char, "")
        if not cleaned or any(ch in cleaned for ch in ";\n\r"):
            raise ConnectionFailed(f"Rejected unsafe identifier: {identifier!r}")
        return f"{self.quote_char}{cleaned}{self.quote_char}"

    def qualify(self, ref: DatasetRef) -> str:
        parts = [p for p in (ref.database, ref.schema_name, ref.table) if p]
        return ".".join(self.quote(p) for p in parts)

    def _rows(self, sql: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
        assert_read_only(sql)
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(sql, tuple(params or ()))
            if cursor.description is None:
                return []
            names = [d[0] for d in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
        except Exception as exc:  # noqa: BLE001 — surfaced to the operator verbatim
            raise ConnectionFailed(f"{self.kind.value}: {exc}") from exc
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 — closing must never mask the real error
                pass

    def _scalars(self, sql: str) -> list[str]:
        return [str(next(iter(row.values()))) for row in self._rows(sql) if row]

    # ------------------------------------------------------------------ #
    # SourceConnector implementation
    # ------------------------------------------------------------------ #

    def test_connection(self) -> ConnectionHealth:
        if not self.driver_available():
            return ConnectionHealth(
                ok=False,
                detail=f"Driver not installed. {self.install_hint()}",
                driver_installed=False,
            )
        started = time.perf_counter()
        try:
            rows = self._rows(self._version_query())
        except Exception as exc:  # noqa: BLE001
            return ConnectionHealth(ok=False, detail=str(exc), driver_installed=True)
        elapsed = int((time.perf_counter() - started) * 1000)
        version = str(next(iter(rows[0].values()))) if rows else "unknown"
        return ConnectionHealth(
            ok=True, detail="Connected (read-only).", latency_ms=elapsed, server_version=version
        )

    def list_databases(self) -> list[str]:
        query = self._databases_query()
        if query is None:
            return [self.connection.database] if self.connection.database else []
        return self._scalars(query)

    def list_schemas(self, database: str | None) -> list[str]:
        return self._scalars(self._schemas_query(database or self.connection.database))

    def list_tables(self, database: str | None, schema: str | None) -> list[TableMeta]:
        rows = self._rows(self._tables_query(database or self.connection.database, schema))
        tables: list[TableMeta] = []
        for row in rows:
            lowered = {str(k).lower(): v for k, v in row.items()}
            tables.append(
                TableMeta(
                    database=database,
                    schema_name=schema,
                    name=str(lowered.get("table_name", "")),
                    kind=str(lowered.get("table_type", "TABLE") or "TABLE"),
                    row_count=int(lowered["row_count"]) if lowered.get("row_count") is not None else None,
                    comment=(str(lowered["comment"]) if lowered.get("comment") else None),
                )
            )
        return tables

    def describe_table(self, ref: DatasetRef) -> TableMeta:
        rows = self._rows(self._columns_query(ref))
        columns: list[ColumnMeta] = []
        for index, row in enumerate(rows):
            lowered = {str(k).lower(): v for k, v in row.items()}
            name = str(lowered.get("column_name", ""))
            if ref.columns and name not in ref.columns:
                continue
            columns.append(
                ColumnMeta(
                    name=name,
                    data_type=str(lowered.get("data_type", "unknown")),
                    nullable=str(lowered.get("is_nullable", "YES")).upper() in {"YES", "TRUE", "1", "Y"},
                    comment=(str(lowered["comment"]) if lowered.get("comment") else None),
                    ordinal=index,
                )
            )
        return TableMeta(
            database=ref.database,
            schema_name=ref.schema_name,
            name=ref.table,
            columns=columns,
        )

    def sample_rows(self, ref: DatasetRef, limit: int) -> list[dict[str, Any]]:
        table = self.describe_table(ref)
        if not table.columns:
            return []
        projection = ", ".join(self.quote(c.name) for c in table.columns)
        sql = f"SELECT {projection} FROM {self.qualify(ref)} {self._limit_clause(limit)}"
        return self._rows(sql)

    def _row_count(self, ref: DatasetRef) -> int:
        rows = self._rows(f"SELECT COUNT(*) AS row_count FROM {self.qualify(ref)}")
        if not rows:
            return 0
        return int(next(iter(rows[0].values())) or 0)

    def profile_table(self, ref: DatasetRef, sample_limit: int) -> TableProfile:
        table = self.describe_table(ref)
        rows = self.sample_rows(ref, sample_limit)
        total = self._row_count(ref)
        strategy = (
            f"first {len(rows)} rows"
            if total > len(rows)
            else f"full scan ({total} rows, below sample limit)"
        )
        return self._profile_from_rows(table, rows, total, strategy)


def require_driver(module_name: str, hint: str) -> Any:
    """Import a driver, converting ``ImportError`` into a clear domain error."""
    try:
        return __import__(module_name)
    except ImportError as exc:  # pragma: no cover — depends on the host
        raise DriverUnavailable(f"{module_name} is not installed. {hint}") from exc
