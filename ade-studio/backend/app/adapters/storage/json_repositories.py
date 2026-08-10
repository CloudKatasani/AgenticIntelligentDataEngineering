"""JSON-file persistence for runs and connections.

Deliberately simple: the deployable unit is a single process with a data
directory, which is what a client demo needs. Both classes implement ports, so
swapping in Postgres later touches no service code.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from app.domain.connection import SourceConnection
from app.domain.document import DocumentSpace
from app.domain.run import Run, RunStatus
from app.ports.repositories import (
    ConnectionRepository,
    DocumentSpaceRepository,
    RunRepository,
)


class JsonRunRepository(RunRepository):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[str, Run] | None = None

    def _load(self) -> dict[str, Run]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = {}
            return self._cache
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw = {}
        self._cache = {rid: Run.model_validate(data) for rid, data in raw.items()}
        return self._cache

    def _flush(self) -> None:
        assert self._cache is not None
        payload = {rid: run.model_dump(mode="json") for rid, run in self._cache.items()}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def save(self, run: Run) -> None:
        with self._lock:
            self._load()[run.id] = run
            self._flush()

    def get(self, run_id: str) -> Run | None:
        return self._load().get(run_id)

    def list(self, *, agent_id: str | None = None, limit: int = 100) -> list[Run]:
        runs = list(self._load().values())
        if agent_id:
            runs = [r for r in runs if r.agent_id == agent_id]
        runs.sort(key=lambda r: r.created_at, reverse=True)
        return runs[:limit]

    def find_successful(self, agent_id: str, dataset_fqns: set[str]) -> list[Run]:
        """Runs that can satisfy a downstream agent's hard dependency.

        A run counts only if it completed and covers at least one object in the
        requested scope — or was estate-scoped, in which case it applies to any
        scope.
        """
        out: list[Run] = []
        for run in self._load().values():
            if run.agent_id != agent_id:
                continue
            if run.status not in {RunStatus.SUCCEEDED, RunStatus.PARTIAL}:
                continue
            covered = {d.fqn for d in run.request.datasets}
            if not dataset_fqns or not covered or covered & dataset_fqns:
                out.append(run)
        out.sort(key=lambda r: r.created_at, reverse=True)
        return out


class JsonConnectionRepository(ConnectionRepository):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[str, SourceConnection] | None = None

    def _load(self) -> dict[str, SourceConnection]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = {}
            return self._cache
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw = {}
        self._cache = {cid: SourceConnection.model_validate(data) for cid, data in raw.items()}
        return self._cache

    def _flush(self) -> None:
        assert self._cache is not None
        payload = {
            cid: json.loads(
                conn.model_dump_json()  # SecretStr serialises to "**********"; see below
            )
            for cid, conn in self._cache.items()
        }
        # Persist the real secret values so a saved connection still works after
        # a restart. This file lives in the app's private data directory.
        for cid, conn in self._cache.items():
            if conn.password is not None:
                payload[cid]["password"] = conn.password.get_secret_value()
            if conn.access_token is not None:
                payload[cid]["access_token"] = conn.access_token.get_secret_value()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(self.path)

    def save(self, connection: SourceConnection) -> None:
        with self._lock:
            self._load()[connection.id] = connection
            self._flush()

    def get(self, connection_id: str) -> SourceConnection | None:
        return self._load().get(connection_id)

    def list(self) -> list[SourceConnection]:
        return sorted(self._load().values(), key=lambda c: c.name.lower())

    def delete(self, connection_id: str) -> None:
        with self._lock:
            self._load().pop(connection_id, None)
            self._flush()


class JsonDocumentSpaceRepository(DocumentSpaceRepository):
    """Registered file locations. Same shape as the connection repository,
    including persisting real secrets over the masked ``model_dump_json``
    output so a saved SharePoint space still works after a restart."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[str, DocumentSpace] | None = None

    def _load(self) -> dict[str, DocumentSpace]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = {}
            return self._cache
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw = {}
        self._cache = {sid: DocumentSpace.model_validate(data) for sid, data in raw.items()}
        return self._cache

    def _flush(self) -> None:
        assert self._cache is not None
        payload = {sid: json.loads(space.model_dump_json()) for sid, space in self._cache.items()}
        for sid, space in self._cache.items():
            if space.client_secret is not None:
                payload[sid]["client_secret"] = space.client_secret.get_secret_value()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(self.path)

    def save(self, space: DocumentSpace) -> None:
        with self._lock:
            self._load()[space.id] = space
            self._flush()

    def get(self, space_id: str) -> DocumentSpace | None:
        return self._load().get(space_id)

    def list(self) -> list[DocumentSpace]:
        return sorted(self._load().values(), key=lambda s: s.name.lower())

    def delete(self, space_id: str) -> None:
        with self._lock:
            self._load().pop(space_id, None)
            self._flush()
