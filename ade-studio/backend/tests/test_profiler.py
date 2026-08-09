"""The profiler is the source of every number an agent reports."""

from __future__ import annotations

from app.adapters.connectors.demo import DemoConnector
from app.domain.connection import ColumnMeta, DatasetRef, SourceConnection, SourceKind
from app.runtime.deterministic.profiler import profile_column


def _column(name: str = "c", data_type: str = "VARCHAR") -> ColumnMeta:
    return ColumnMeta(name=name, data_type=data_type)


def test_null_ratio_and_distinct_counts() -> None:
    profile = profile_column(_column(), ["a", "b", "b", None, None])
    assert profile.null_count == 2
    assert profile.null_ratio == 0.4
    assert profile.distinct_count == 2
    assert profile.distinct_ratio == round(2 / 3, 6)


def test_candidate_key_requires_uniqueness_and_no_nulls() -> None:
    assert profile_column(_column(), ["a", "b", "c"]).is_candidate_key is True
    assert profile_column(_column(), ["a", "b", "b"]).is_candidate_key is False
    assert profile_column(_column(), ["a", "b", None]).is_candidate_key is False


def test_numeric_columns_report_min_max_and_mean() -> None:
    profile = profile_column(_column("amount", "DECIMAL"), [1, 2, 3, 4])
    assert profile.min_value == "1.0"
    assert profile.max_value == "4.0"
    assert profile.mean_value == 2.5


def test_format_patterns_are_detected_above_the_threshold() -> None:
    emails = [f"user{i}@example.com" for i in range(9)] + ["not-an-email"]
    profile = profile_column(_column("email"), emails)
    assert any(p.startswith("email") for p in profile.sample_patterns)

    mixed = [f"user{i}@example.com" for i in range(5)] + ["x"] * 5
    assert profile_column(_column("email"), mixed).sample_patterns == []


def test_unhashable_values_do_not_break_profiling() -> None:
    profile = profile_column(_column("payload", "JSON"), [{"a": 1}, {"a": 1}, ["b"]])
    assert profile.distinct_count == 2


def test_demo_warehouse_profiles_the_seeded_defects(seeded_warehouse) -> None:
    """The demo data carries deliberate defects; the profiler must find them."""
    connection = SourceConnection(
        id="c", name="demo", kind=SourceKind.DEMO, file_path=str(seeded_warehouse)
    )
    connector = DemoConnector(connection)
    ref = DatasetRef(connection_id="c", schema_name="RETAIL", table="CUSTOMERS")
    profile = connector.profile_table(ref, 200)

    assert profile.row_count == 2000
    assert profile.sampled_rows == 200

    by_name = {c.column: c for c in profile.columns}
    # 4% of e-mails are null by construction.
    assert by_name["email"].null_ratio > 0.0
    # customer_id is the intended key.
    assert by_name["customer_id"].is_candidate_key is True
    assert any(k["column"] == "customer_id" for k in profile.candidate_primary_keys)


def test_connectors_refuse_mutating_statements() -> None:
    import pytest

    from app.core.errors import ReadOnlyViolation
    from app.ports.source_connector import assert_read_only

    assert_read_only("SELECT * FROM t")
    for statement in ("DROP TABLE t", "delete from t", "UPDATE t SET x = 1", "CREATE VIEW v AS SELECT 1"):
        with pytest.raises(ReadOnlyViolation):
            assert_read_only(statement)
