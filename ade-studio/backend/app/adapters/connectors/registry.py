"""Factory and capability report for source adapters."""

from __future__ import annotations

from app.core.errors import NotFound
from app.domain.connection import SourceConnection, SourceKind
from app.adapters.connectors.csv_source import CSVConnector
from app.adapters.connectors.demo import DemoConnector
from app.adapters.connectors.sql_dialects import (
    BigQueryConnector,
    DatabricksConnector,
    MSSQLConnector,
    MySQLConnector,
    OracleConnector,
    PostgresConnector,
    RedshiftConnector,
    SnowflakeConnector,
)
from app.ports.source_connector import SourceConnector

_REGISTRY: dict[SourceKind, type[SourceConnector]] = {
    SourceKind.DEMO: DemoConnector,
    SourceKind.SNOWFLAKE: SnowflakeConnector,
    SourceKind.ORACLE: OracleConnector,
    SourceKind.POSTGRES: PostgresConnector,
    SourceKind.REDSHIFT: RedshiftConnector,
    SourceKind.MYSQL: MySQLConnector,
    SourceKind.MSSQL: MSSQLConnector,
    SourceKind.DATABRICKS: DatabricksConnector,
    SourceKind.BIGQUERY: BigQueryConnector,
    SourceKind.CSV: CSVConnector,
}

# Which credential fields each kind needs, so the UI renders the right form
# without hardcoding a form per source.
_FIELDS: dict[SourceKind, list[str]] = {
    SourceKind.DEMO: [],
    SourceKind.SNOWFLAKE: ["account", "username", "password", "warehouse", "database", "schema_name", "role"],
    SourceKind.ORACLE: ["host", "port", "service_name", "database", "username", "password"],
    SourceKind.POSTGRES: ["host", "port", "database", "schema_name", "username", "password"],
    SourceKind.REDSHIFT: ["host", "port", "database", "schema_name", "username", "password"],
    SourceKind.MYSQL: ["host", "port", "database", "username", "password"],
    SourceKind.MSSQL: ["host", "port", "database", "schema_name", "username", "password"],
    SourceKind.DATABRICKS: ["host", "http_path", "access_token", "database", "schema_name"],
    SourceKind.BIGQUERY: ["project_id", "schema_name"],
    SourceKind.CSV: ["file_path"],
}

_LABELS: dict[SourceKind, str] = {
    SourceKind.DEMO: "Demo warehouse (no credentials)",
    SourceKind.SNOWFLAKE: "Snowflake",
    SourceKind.ORACLE: "Oracle Database",
    SourceKind.POSTGRES: "PostgreSQL",
    SourceKind.REDSHIFT: "Amazon Redshift",
    SourceKind.MYSQL: "MySQL",
    SourceKind.MSSQL: "Microsoft SQL Server",
    SourceKind.DATABRICKS: "Databricks SQL",
    SourceKind.BIGQUERY: "Google BigQuery",
    SourceKind.CSV: "Files (CSV / Parquet / JSON)",
}


def connector_for(connection: SourceConnection) -> SourceConnector:
    cls = _REGISTRY.get(connection.kind)
    if cls is None:
        raise NotFound(f"No adapter for source kind {connection.kind}.")
    return cls(connection)


def capabilities() -> list[dict[str, object]]:
    """Every supported source with its driver status and required fields.

    Reporting an uninstalled driver honestly is better than letting the user
    configure a connection that can never open.
    """
    out: list[dict[str, object]] = []
    for kind, cls in _REGISTRY.items():
        available = cls.driver_available()
        out.append(
            {
                "kind": kind.value,
                "label": _LABELS[kind],
                "driver_installed": available,
                "install_hint": "" if available else cls.install_hint(),
                "fields": _FIELDS.get(kind, []),
            }
        )
    return out
