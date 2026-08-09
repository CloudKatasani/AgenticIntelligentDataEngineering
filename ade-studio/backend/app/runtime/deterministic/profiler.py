"""Deterministic column statistics.

Design rule 4 of the catalog: "Statistics, diffs, comparisons, and CI verdicts
come from deterministic tools; LLM reasoning interprets, drafts, and adjudicates
— it never computes numbers."

Every number an agent reports about data originates here.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Any

from app.domain.connection import ColumnMeta, ColumnProfile, TableMeta

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")),
    ("uuid", re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")),
    ("iso_date", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("iso_timestamp", re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")),
    ("us_phone", re.compile(r"^\+?1?[-.\s(]*\d{3}[-.\s)]*\d{3}[-.\s]*\d{4}$")),
    ("currency", re.compile(r"^-?\$?\d{1,3}(,\d{3})*(\.\d+)?$")),
    ("numeric_string", re.compile(r"^-?\d+(\.\d+)?$")),
    ("upper_code", re.compile(r"^[A-Z0-9_\-]{2,20}$")),
]


def _detect_patterns(values: list[str]) -> list[str]:
    if not values:
        return []
    hits: list[str] = []
    for label, pattern in _PATTERNS:
        matched = sum(1 for v in values if pattern.match(v))
        if matched / len(values) >= 0.8:
            hits.append(f"{label} ({matched}/{len(values)})")
    return hits


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def profile_column(column: ColumnMeta, values: list[Any]) -> ColumnProfile:
    """Compute statistics for one column from a sample of values."""
    total = len(values)
    non_null = [v for v in values if v is not None]
    null_count = total - len(non_null)

    # Hashable projection so Counter/set work on dicts, lists, bytes alike.
    def _key(v: Any) -> Any:
        return v if isinstance(v, (str, int, float, bool)) else str(v)

    keyed = [_key(v) for v in non_null]
    distinct = len(set(keyed))

    numeric = [f for f in (_to_float(v) for v in non_null) if f is not None]
    strings = [str(v) for v in non_null]

    min_value: str | None = None
    max_value: str | None = None
    mean_value: float | None = None
    if numeric:
        min_value = str(min(numeric))
        max_value = str(max(numeric))
        mean_value = round(statistics.fmean(numeric), 6)
    elif strings:
        min_value = min(strings)[:120]
        max_value = max(strings)[:120]

    counter = Counter(keyed)
    top = [
        {"value": str(value)[:120], "count": count, "ratio": round(count / len(keyed), 4)}
        for value, count in counter.most_common(5)
    ] if keyed else []

    distinct_ratio = distinct / len(non_null) if non_null else 0.0
    # A candidate key must be unique across every sampled row and never null.
    is_key = bool(non_null) and distinct == len(non_null) and null_count == 0 and total > 1

    return ColumnProfile(
        column=column.name,
        data_type=column.data_type,
        null_count=null_count,
        null_ratio=round(null_count / total, 6) if total else 0.0,
        distinct_count=distinct,
        distinct_ratio=round(distinct_ratio, 6),
        min_value=min_value,
        max_value=max_value,
        mean_value=mean_value,
        top_values=top,
        sample_patterns=_detect_patterns(strings) if not numeric else [],
        is_candidate_key=is_key,
    )


def profile_rows(table: TableMeta, rows: list[dict[str, Any]]) -> list[ColumnProfile]:
    """Profile every column of a table from sampled rows."""
    profiles: list[ColumnProfile] = []
    for column in table.columns:
        values = [row.get(column.name) for row in rows]
        profiles.append(profile_column(column, values))
    return profiles


def summarise_profile_for_prompt(profiles: list[ColumnProfile], max_columns: int = 60) -> str:
    """Render statistics as compact text the model can reason over.

    The model receives these as FACTs; it is instructed never to recompute them.
    """
    lines = ["column | type | null% | distinct | distinct% | min | max | top values | patterns"]
    for p in profiles[:max_columns]:
        top = "; ".join(f"{t['value']}×{t['count']}" for t in p.top_values[:3]) or "-"
        patterns = ", ".join(p.sample_patterns) or "-"
        lines.append(
            f"{p.column} | {p.data_type} | {p.null_ratio * 100:.2f}% | {p.distinct_count} | "
            f"{p.distinct_ratio * 100:.2f}% | {p.min_value or '-'} | {p.max_value or '-'} | {top} | {patterns}"
        )
    if len(profiles) > max_columns:
        lines.append(f"... {len(profiles) - max_columns} further columns omitted from this brief")
    return "\n".join(lines)
