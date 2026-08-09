"""Concrete source adapters, one class per dialect.

Each supplies three things: how to open a connection, where its catalog
metadata lives, and how it limits a result set. Everything else is inherited
from :class:`SQLConnector`.

Drivers are optional. An adapter whose driver is missing reports
``driver_available() is False`` and the UI shows an install hint instead of the
app failing at import time.
"""

from __future__ import annotations

from typing import Any

from app.adapters.connectors.base import SQLConnector
from app.core.errors import ConnectionFailed
from app.domain.connection import DatasetRef, SourceKind


class SnowflakeConnector(SQLConnector):
    kind = SourceKind.SNOWFLAKE

    @classmethod
    def driver_available(cls) -> bool:
        try:
            import snowflake.connector  # noqa: F401
        except ImportError:
            return False
        return True

    @classmethod
    def install_hint(cls) -> str:
        return "pip install 'snowflake-connector-python>=3.10'"

    def _connect(self) -> Any:
        import snowflake.connector

        conn = self.connection
        return snowflake.connector.connect(
            account=conn.account or "",
            user=conn.username or "",
            password=conn.password.get_secret_value() if conn.password else None,
            warehouse=conn.warehouse or None,
            database=conn.database or None,
            schema=conn.schema_name or None,
            role=conn.role or None,
            client_session_keep_alive=False,
        )

    def _version_query(self) -> str:
        return "SELECT CURRENT_VERSION() AS version"

    def _databases_query(self) -> str | None:
        return "SELECT DATABASE_NAME FROM SNOWFLAKE.INFORMATION_SCHEMA.DATABASES ORDER BY 1"

    def _schemas_query(self, database: str | None) -> str:
        db = self.quote(database) if database else "CURRENT_DATABASE()"
        return (
            f"SELECT SCHEMA_NAME FROM {db}.INFORMATION_SCHEMA.SCHEMATA "
            "WHERE SCHEMA_NAME <> 'INFORMATION_SCHEMA' ORDER BY 1"
        )

    def _tables_query(self, database: str | None, schema: str | None) -> str:
        db = self.quote(database) if database else "CURRENT_DATABASE()"
        where = f"WHERE TABLE_SCHEMA = '{(schema or '').replace(chr(39), '')}'" if schema else ""
        return (
            "SELECT TABLE_NAME, TABLE_TYPE, ROW_COUNT AS ROW_COUNT, COMMENT AS COMMENT "
            f"FROM {db}.INFORMATION_SCHEMA.TABLES {where} ORDER BY TABLE_NAME"
        )

    def _columns_query(self, ref: DatasetRef) -> str:
        db = self.quote(ref.database) if ref.database else "CURRENT_DATABASE()"
        schema = (ref.schema_name or "").replace("'", "")
        table = ref.table.replace("'", "")
        return (
            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COMMENT AS COMMENT "
            f"FROM {db}.INFORMATION_SCHEMA.COLUMNS "
            f"WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}' ORDER BY ORDINAL_POSITION"
        )


class OracleConnector(SQLConnector):
    """Oracle exposes schemas as users; there is no separate catalog level."""

    kind = SourceKind.ORACLE
    supports_catalogs = False

    @classmethod
    def driver_available(cls) -> bool:
        try:
            import oracledb  # noqa: F401
        except ImportError:
            return False
        return True

    @classmethod
    def install_hint(cls) -> str:
        return "pip install 'oracledb>=2.2'"

    def _connect(self) -> Any:
        import oracledb

        conn = self.connection
        if conn.service_name:
            dsn = oracledb.makedsn(conn.host or "localhost", conn.port or 1521, service_name=conn.service_name)
        else:
            dsn = f"{conn.host or 'localhost'}:{conn.port or 1521}/{conn.database or 'ORCL'}"
        return oracledb.connect(
            user=conn.username or "",
            password=conn.password.get_secret_value() if conn.password else "",
            dsn=dsn,
        )

    def _version_query(self) -> str:
        return "SELECT banner AS version FROM v$version WHERE ROWNUM = 1"

    def _databases_query(self) -> str | None:
        return None  # Single catalog per connection.

    def _schemas_query(self, database: str | None) -> str:
        return (
            "SELECT username FROM all_users "
            "WHERE oracle_maintained = 'N' ORDER BY username"
        )

    def _tables_query(self, database: str | None, schema: str | None) -> str:
        owner = (schema or self.connection.username or "").upper().replace("'", "")
        return (
            "SELECT table_name AS TABLE_NAME, 'TABLE' AS TABLE_TYPE, num_rows AS ROW_COUNT "
            f"FROM all_tables WHERE owner = '{owner}' ORDER BY table_name"
        )

    def _columns_query(self, ref: DatasetRef) -> str:
        owner = (ref.schema_name or self.connection.username or "").upper().replace("'", "")
        table = ref.table.upper().replace("'", "")
        return (
            "SELECT column_name AS COLUMN_NAME, data_type AS DATA_TYPE, nullable AS IS_NULLABLE "
            f"FROM all_tab_columns WHERE owner = '{owner}' AND table_name = '{table}' "
            "ORDER BY column_id"
        )

    def _limit_clause(self, limit: int) -> str:
        return f"FETCH FIRST {int(limit)} ROWS ONLY"

    def qualify(self, ref: DatasetRef) -> str:
        parts = [p for p in (ref.schema_name, ref.table) if p]
        return ".".join(self.quote(p) for p in parts)


class PostgresConnector(SQLConnector):
    kind = SourceKind.POSTGRES

    @classmethod
    def driver_available(cls) -> bool:
        try:
            import psycopg  # noqa: F401
        except ImportError:
            return False
        return True

    @classmethod
    def install_hint(cls) -> str:
        return "pip install 'psycopg[binary]>=3.1'"

    def _connect(self) -> Any:
        import psycopg

        conn = self.connection
        return psycopg.connect(
            host=conn.host or "localhost",
            port=conn.port or 5432,
            dbname=conn.database or "postgres",
            user=conn.username or "",
            password=conn.password.get_secret_value() if conn.password else None,
            connect_timeout=10,
        )

    def _version_query(self) -> str:
        return "SELECT version() AS version"

    def _databases_query(self) -> str | None:
        return "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY 1"

    def _schemas_query(self, database: str | None) -> str:
        return (
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('information_schema','pg_catalog','pg_toast') ORDER BY 1"
        )

    def _tables_query(self, database: str | None, schema: str | None) -> str:
        s = (schema or "public").replace("'", "")
        return (
            "SELECT table_name, table_type, obj_description("
            "  (quote_ident(table_schema)||'.'||quote_ident(table_name))::regclass) AS comment "
            f"FROM information_schema.tables WHERE table_schema = '{s}' ORDER BY table_name"
        )

    def _columns_query(self, ref: DatasetRef) -> str:
        s = (ref.schema_name or "public").replace("'", "")
        t = ref.table.replace("'", "")
        return (
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            f"WHERE table_schema = '{s}' AND table_name = '{t}' ORDER BY ordinal_position"
        )

    def qualify(self, ref: DatasetRef) -> str:
        parts = [p for p in (ref.schema_name or "public", ref.table) if p]
        return ".".join(self.quote(p) for p in parts)


class RedshiftConnector(PostgresConnector):
    """Redshift speaks the Postgres wire protocol with a narrower catalog."""

    kind = SourceKind.REDSHIFT

    def _version_query(self) -> str:
        return "SELECT version() AS version"

    def _databases_query(self) -> str | None:
        return "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY 1"


class MySQLConnector(SQLConnector):
    kind = SourceKind.MYSQL
    quote_char = "`"

    @classmethod
    def driver_available(cls) -> bool:
        try:
            import pymysql  # noqa: F401
        except ImportError:
            return False
        return True

    @classmethod
    def install_hint(cls) -> str:
        return "pip install 'PyMySQL>=1.1'"

    def _connect(self) -> Any:
        import pymysql

        conn = self.connection
        return pymysql.connect(
            host=conn.host or "localhost",
            port=conn.port or 3306,
            user=conn.username or "",
            password=conn.password.get_secret_value() if conn.password else "",
            database=conn.database or None,
            connect_timeout=10,
        )

    def _version_query(self) -> str:
        return "SELECT VERSION() AS version"

    def _databases_query(self) -> str | None:
        return (
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('mysql','sys','performance_schema','information_schema') ORDER BY 1"
        )

    def _schemas_query(self, database: str | None) -> str:
        # MySQL conflates database and schema; the database list is the schema list.
        return self._databases_query() or ""

    def _tables_query(self, database: str | None, schema: str | None) -> str:
        s = (schema or database or "").replace("'", "")
        return (
            "SELECT table_name, table_type, table_rows AS row_count, table_comment AS comment "
            f"FROM information_schema.tables WHERE table_schema = '{s}' ORDER BY table_name"
        )

    def _columns_query(self, ref: DatasetRef) -> str:
        s = (ref.schema_name or ref.database or "").replace("'", "")
        t = ref.table.replace("'", "")
        return (
            "SELECT column_name, data_type, is_nullable, column_comment AS comment "
            f"FROM information_schema.columns WHERE table_schema = '{s}' AND table_name = '{t}' "
            "ORDER BY ordinal_position"
        )

    def qualify(self, ref: DatasetRef) -> str:
        parts = [p for p in (ref.schema_name or ref.database, ref.table) if p]
        return ".".join(self.quote(p) for p in parts)


class MSSQLConnector(SQLConnector):
    kind = SourceKind.MSSQL
    quote_char = "]"

    @classmethod
    def driver_available(cls) -> bool:
        try:
            import pymssql  # noqa: F401
        except ImportError:
            return False
        return True

    @classmethod
    def install_hint(cls) -> str:
        return "pip install 'pymssql>=2.3'"

    def quote(self, identifier: str) -> str:
        cleaned = identifier.replace("[", "").replace("]", "")
        if not cleaned or any(ch in cleaned for ch in ";\n\r"):
            raise ConnectionFailed(f"Rejected unsafe identifier: {identifier!r}")
        return f"[{cleaned}]"

    def _connect(self) -> Any:
        import pymssql

        conn = self.connection
        return pymssql.connect(
            server=conn.host or "localhost",
            port=str(conn.port or 1433),
            user=conn.username or "",
            password=conn.password.get_secret_value() if conn.password else "",
            database=conn.database or "master",
            login_timeout=10,
        )

    def _version_query(self) -> str:
        return "SELECT @@VERSION AS version"

    def _databases_query(self) -> str | None:
        return "SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name"

    def _schemas_query(self, database: str | None) -> str:
        return "SELECT name FROM sys.schemas WHERE principal_id = 1 ORDER BY name"

    def _tables_query(self, database: str | None, schema: str | None) -> str:
        s = (schema or "dbo").replace("'", "")
        return (
            "SELECT t.name AS table_name, 'TABLE' AS table_type, p.rows AS row_count "
            "FROM sys.tables t JOIN sys.schemas s ON t.schema_id = s.schema_id "
            "JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1) "
            f"WHERE s.name = '{s}' ORDER BY t.name"
        )

    def _columns_query(self, ref: DatasetRef) -> str:
        s = (ref.schema_name or "dbo").replace("'", "")
        t = ref.table.replace("'", "")
        return (
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            f"WHERE table_schema = '{s}' AND table_name = '{t}' ORDER BY ordinal_position"
        )

    def _limit_clause(self, limit: int) -> str:
        return ""  # SQL Server uses TOP, applied in sample_rows below.

    def sample_rows(self, ref: DatasetRef, limit: int) -> list[dict[str, Any]]:
        table = self.describe_table(ref)
        if not table.columns:
            return []
        projection = ", ".join(self.quote(c.name) for c in table.columns)
        return self._rows(f"SELECT TOP {int(limit)} {projection} FROM {self.qualify(ref)}")

    def qualify(self, ref: DatasetRef) -> str:
        parts = [p for p in (ref.schema_name or "dbo", ref.table) if p]
        return ".".join(self.quote(p) for p in parts)


class DatabricksConnector(SQLConnector):
    kind = SourceKind.DATABRICKS
    quote_char = "`"

    @classmethod
    def driver_available(cls) -> bool:
        try:
            import databricks.sql  # noqa: F401
        except ImportError:
            return False
        return True

    @classmethod
    def install_hint(cls) -> str:
        return "pip install 'databricks-sql-connector>=3.3'"

    def _connect(self) -> Any:
        import databricks.sql

        conn = self.connection
        return databricks.sql.connect(
            server_hostname=conn.host or "",
            http_path=conn.http_path or "",
            access_token=conn.access_token.get_secret_value() if conn.access_token else "",
        )

    def _version_query(self) -> str:
        return "SELECT current_version().dbsql_version AS version"

    def _databases_query(self) -> str | None:
        return "SELECT catalog_name FROM system.information_schema.catalogs ORDER BY 1"

    def _schemas_query(self, database: str | None) -> str:
        db = (database or "main").replace("'", "")
        return (
            f"SELECT schema_name FROM {self.quote(db)}.information_schema.schemata ORDER BY 1"
        )

    def _tables_query(self, database: str | None, schema: str | None) -> str:
        db = (database or "main").replace("'", "")
        s = (schema or "default").replace("'", "")
        return (
            "SELECT table_name, table_type, comment "
            f"FROM {self.quote(db)}.information_schema.tables WHERE table_schema = '{s}' ORDER BY table_name"
        )

    def _columns_query(self, ref: DatasetRef) -> str:
        db = (ref.database or "main").replace("'", "")
        s = (ref.schema_name or "default").replace("'", "")
        t = ref.table.replace("'", "")
        return (
            "SELECT column_name, data_type, is_nullable, comment "
            f"FROM {self.quote(db)}.information_schema.columns "
            f"WHERE table_schema = '{s}' AND table_name = '{t}' ORDER BY ordinal_position"
        )


class BigQueryConnector(SQLConnector):
    """BigQuery: ``project`` is the catalog and ``dataset`` is the schema."""

    kind = SourceKind.BIGQUERY
    quote_char = "`"

    @classmethod
    def driver_available(cls) -> bool:
        try:
            from google.cloud import bigquery  # noqa: F401
        except ImportError:
            return False
        return True

    @classmethod
    def install_hint(cls) -> str:
        return "pip install 'google-cloud-bigquery>=3.25' (auth via GOOGLE_APPLICATION_CREDENTIALS)"

    def _connect(self) -> Any:
        from google.cloud import bigquery
        from google.cloud.bigquery import dbapi

        client = bigquery.Client(project=self.connection.project_id or None)
        return dbapi.Connection(client)

    def _version_query(self) -> str:
        return "SELECT 'bigquery' AS version"

    def _databases_query(self) -> str | None:
        return None  # A connection is scoped to one project.

    def _schemas_query(self, database: str | None) -> str:
        project = (database or self.connection.project_id or "").replace("`", "")
        return f"SELECT schema_name FROM `{project}`.INFORMATION_SCHEMA.SCHEMATA ORDER BY 1"

    def _tables_query(self, database: str | None, schema: str | None) -> str:
        project = (database or self.connection.project_id or "").replace("`", "")
        dataset = (schema or "").replace("`", "")
        return (
            "SELECT table_name, table_type "
            f"FROM `{project}`.`{dataset}`.INFORMATION_SCHEMA.TABLES ORDER BY table_name"
        )

    def _columns_query(self, ref: DatasetRef) -> str:
        project = (ref.database or self.connection.project_id or "").replace("`", "")
        dataset = (ref.schema_name or "").replace("`", "")
        table = ref.table.replace("'", "")
        return (
            "SELECT column_name, data_type, is_nullable "
            f"FROM `{project}`.`{dataset}`.INFORMATION_SCHEMA.COLUMNS "
            f"WHERE table_name = '{table}' ORDER BY ordinal_position"
        )
