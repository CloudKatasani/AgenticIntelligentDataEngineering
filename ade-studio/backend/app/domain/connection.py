"""Source systems and the database objects an agent run is pointed at."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, SecretStr


class SourceKind(str, Enum):
    SNOWFLAKE = "snowflake"
    ORACLE = "oracle"
    POSTGRES = "postgres"
    MYSQL = "mysql"
    MSSQL = "mssql"
    BIGQUERY = "bigquery"
    DATABRICKS = "databricks"
    REDSHIFT = "redshift"
    CSV = "csv"
    DEMO = "demo"
    """A seeded DuckDB warehouse so the product demos without credentials."""


class Environment(str, Enum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class SourceConnection(BaseModel):
    """A registered, read-only source.

    Secrets are held as ``SecretStr`` and never serialised back to the client;
    the API returns :meth:`redacted` instead.
    """

    id: str
    name: str
    kind: SourceKind
    environment: Environment = Environment.DEV
    owner: str = ""
    regulated: bool = False
    """Drives the tier cap for agents 02, 26 and 27."""

    host: str | None = None
    port: int | None = None
    database: str | None = None
    schema_name: str | None = None
    warehouse: str | None = None
    role: str | None = None
    account: str | None = None
    username: str | None = None
    password: SecretStr | None = None
    service_name: str | None = None
    project_id: str | None = None
    http_path: str | None = None
    access_token: SecretStr | None = None
    file_path: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)

    created_at: str = ""

    def redacted(self) -> dict[str, object]:
        data = self.model_dump(mode="json", exclude={"password", "access_token"})
        data["has_password"] = self.password is not None
        data["has_access_token"] = self.access_token is not None
        return data


class ColumnMeta(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    comment: str | None = None
    ordinal: int = 0


class TableMeta(BaseModel):
    database: str | None = None
    schema_name: str | None = None
    name: str = ""
    kind: str = "TABLE"
    row_count: int | None = None
    comment: str | None = None
    columns: list[ColumnMeta] = Field(default_factory=list)

    @property
    def fqn(self) -> str:
        return ".".join(p for p in (self.database, self.schema_name, self.name) if p)


class DatasetRef(BaseModel):
    """The user's object selection: which tables (and optionally columns)."""

    connection_id: str
    database: str | None = None
    schema_name: str | None = None
    table: str = ""
    columns: list[str] = Field(default_factory=list)
    """Empty means every column."""

    @property
    def fqn(self) -> str:
        return ".".join(p for p in (self.database, self.schema_name, self.table) if p)


class ConnectionHealth(BaseModel):
    ok: bool
    detail: str
    latency_ms: int | None = None
    driver_installed: bool = True
    server_version: str | None = None


class ColumnProfile(BaseModel):
    """Deterministic statistics. Never produced by a language model."""

    column: str
    data_type: str
    null_count: int
    null_ratio: float
    distinct_count: int
    distinct_ratio: float
    min_value: str | None = None
    max_value: str | None = None
    mean_value: float | None = None
    top_values: list[dict[str, object]] = Field(default_factory=list)
    sample_patterns: list[str] = Field(default_factory=list)
    is_candidate_key: bool = False


class TableProfile(BaseModel):
    table: str
    row_count: int
    sampled_rows: int
    sample_strategy: str
    columns: list[ColumnProfile] = Field(default_factory=list)
    candidate_primary_keys: list[dict[str, object]] = Field(default_factory=list)
    computed_at: str = ""
