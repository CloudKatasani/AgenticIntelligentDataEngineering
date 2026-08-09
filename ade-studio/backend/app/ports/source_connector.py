"""Port: read-only access to a source system.

Every source — Snowflake, Oracle, the demo warehouse — is reachable through
this one interface, so the run engine never learns what it is talking to.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.core.errors import ReadOnlyViolation
from app.domain.connection import (
    ColumnProfile,
    ConnectionHealth,
    DatasetRef,
    SourceConnection,
    SourceKind,
    TableMeta,
    TableProfile,
)

_MUTATING = re.compile(
    r"\b(insert|update|delete|merge|truncate|drop|alter|create|grant|revoke|call|copy)\b",
    re.IGNORECASE,
)


def assert_read_only(sql: str) -> None:
    """Refuse any statement that could mutate a source.

    Applied to every statement the connectors issue. The universal guardrail
    ("no write, DDL, or full-table export ever issued against the source") is
    enforced here in code rather than asked for in prose.
    """
    if _MUTATING.search(sql):
        raise ReadOnlyViolation(
            "Refused a statement that could mutate the source system.",
            details={"statement": sql[:400]},
        )


class SourceConnector(ABC):
    """Read-only metadata and sampling over one registered source."""

    kind: SourceKind

    def __init__(self, connection: SourceConnection) -> None:
        self.connection = connection

    @classmethod
    @abstractmethod
    def driver_available(cls) -> bool:
        """Whether this adapter's Python driver is importable right now."""

    @classmethod
    def install_hint(cls) -> str:
        return ""

    @abstractmethod
    def test_connection(self) -> ConnectionHealth: ...

    @abstractmethod
    def list_databases(self) -> list[str]: ...

    @abstractmethod
    def list_schemas(self, database: str | None) -> list[str]: ...

    @abstractmethod
    def list_tables(self, database: str | None, schema: str | None) -> list[TableMeta]: ...

    @abstractmethod
    def describe_table(self, ref: DatasetRef) -> TableMeta: ...

    @abstractmethod
    def sample_rows(self, ref: DatasetRef, limit: int) -> list[dict[str, object]]: ...

    @abstractmethod
    def profile_table(self, ref: DatasetRef, sample_limit: int) -> TableProfile: ...

    # Shared helper used by every SQL adapter's profiler.
    @staticmethod
    def _profile_from_rows(
        table_meta: TableMeta,
        rows: list[dict[str, object]],
        row_count: int,
        sample_strategy: str,
    ) -> TableProfile:
        from app.runtime.deterministic.profiler import profile_rows

        columns: list[ColumnProfile] = profile_rows(table_meta, rows)
        keys = [
            {"column": c.column, "confidence": round(c.distinct_ratio, 4), "evidence": "uniqueness in sample"}
            for c in columns
            if c.is_candidate_key
        ]
        from app.core.ids import utcnow_iso

        return TableProfile(
            table=table_meta.fqn,
            row_count=row_count,
            sampled_rows=len(rows),
            sample_strategy=sample_strategy,
            columns=columns,
            candidate_primary_keys=keys,
            computed_at=utcnow_iso(),
        )
