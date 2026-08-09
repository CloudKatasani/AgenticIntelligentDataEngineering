"""Source connections and metadata browsing.

The object picker in the workbench is driven entirely by these endpoints, which
is why they are uniform across every source kind.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, SecretStr

from app.adapters.connectors.registry import capabilities, connector_for
from app.api.deps import get_connection_repository
from app.core.errors import NotFound
from app.core.ids import new_id, utcnow_iso
from app.domain.connection import DatasetRef, Environment, SourceConnection, SourceKind

router = APIRouter(prefix="/api/connections", tags=["connections"])


class ConnectionInput(BaseModel):
    name: str
    kind: SourceKind
    environment: Environment = Environment.DEV
    owner: str = ""
    regulated: bool = False
    host: str | None = None
    port: int | None = None
    database: str | None = None
    schema_name: str | None = None
    warehouse: str | None = None
    role: str | None = None
    account: str | None = None
    username: str | None = None
    password: str | None = None
    service_name: str | None = None
    project_id: str | None = None
    http_path: str | None = None
    access_token: str | None = None
    file_path: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)

    def to_domain(self, connection_id: str | None = None) -> SourceConnection:
        data = self.model_dump(exclude={"password", "access_token"})
        return SourceConnection(
            id=connection_id or new_id("conn"),
            created_at=utcnow_iso(),
            password=SecretStr(self.password) if self.password else None,
            access_token=SecretStr(self.access_token) if self.access_token else None,
            **data,
        )


@router.get("/capabilities")
def get_capabilities() -> dict[str, object]:
    return {"sources": capabilities()}


@router.get("")
def list_connections() -> dict[str, object]:
    repo = get_connection_repository()
    return {"connections": [c.redacted() for c in repo.list()]}


@router.post("")
def create_connection(payload: ConnectionInput) -> dict[str, object]:
    repo = get_connection_repository()
    connection = payload.to_domain()
    repo.save(connection)
    return connection.redacted()


@router.put("/{connection_id}")
def update_connection(connection_id: str, payload: ConnectionInput) -> dict[str, object]:
    repo = get_connection_repository()
    existing = repo.get(connection_id)
    if existing is None:
        raise NotFound(f"No connection {connection_id!r}.")
    updated = payload.to_domain(connection_id)
    # Keep the stored secret when the form submits a blank field.
    if updated.password is None:
        updated.password = existing.password
    if updated.access_token is None:
        updated.access_token = existing.access_token
    updated.created_at = existing.created_at
    repo.save(updated)
    return updated.redacted()


@router.delete("/{connection_id}")
def delete_connection(connection_id: str) -> dict[str, str]:
    get_connection_repository().delete(connection_id)
    return {"status": "deleted"}


def _load(connection_id: str) -> SourceConnection:
    connection = get_connection_repository().get(connection_id)
    if connection is None:
        raise NotFound(f"No connection {connection_id!r}.")
    return connection


@router.post("/{connection_id}/test")
def test_connection(connection_id: str) -> dict[str, object]:
    connector = connector_for(_load(connection_id))
    return connector.test_connection().model_dump()


@router.get("/{connection_id}/databases")
def list_databases(connection_id: str) -> dict[str, object]:
    connector = connector_for(_load(connection_id))
    return {"databases": connector.list_databases()}


@router.get("/{connection_id}/schemas")
def list_schemas(connection_id: str, database: str | None = None) -> dict[str, object]:
    connector = connector_for(_load(connection_id))
    return {"schemas": connector.list_schemas(database)}


@router.get("/{connection_id}/tables")
def list_tables(
    connection_id: str, database: str | None = None, schema: str | None = None
) -> dict[str, object]:
    connector = connector_for(_load(connection_id))
    tables = connector.list_tables(database, schema)
    return {"tables": [t.model_dump() for t in tables]}


@router.get("/{connection_id}/columns")
def describe_table(
    connection_id: str, table: str, database: str | None = None, schema: str | None = None
) -> dict[str, object]:
    connection = _load(connection_id)
    connector = connector_for(connection)
    ref = DatasetRef(
        connection_id=connection_id, database=database, schema_name=schema, table=table
    )
    return connector.describe_table(ref).model_dump()


@router.get("/{connection_id}/preview")
def preview_rows(
    connection_id: str,
    table: str,
    database: str | None = None,
    schema: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    connection = _load(connection_id)
    connector = connector_for(connection)
    ref = DatasetRef(
        connection_id=connection_id, database=database, schema_name=schema, table=table
    )
    rows = connector.sample_rows(ref, min(limit, 200))
    return {
        "table": ref.fqn,
        "row_count_returned": len(rows),
        "rows": [{k: (str(v) if v is not None else None) for k, v in row.items()} for row in rows],
    }
