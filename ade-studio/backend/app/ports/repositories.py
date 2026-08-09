"""Ports: persistence for runs, artifacts and connections."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.connection import SourceConnection
from app.domain.run import Artifact, Run


class RunRepository(ABC):
    @abstractmethod
    def save(self, run: Run) -> None: ...

    @abstractmethod
    def get(self, run_id: str) -> Run | None: ...

    @abstractmethod
    def list(self, *, agent_id: str | None = None, limit: int = 100) -> list[Run]: ...

    @abstractmethod
    def find_successful(self, agent_id: str, dataset_fqns: set[str]) -> list[Run]:
        """Runs that satisfy a downstream agent's hard dependency for this scope."""


class ArtifactStore(ABC):
    @abstractmethod
    def write(self, run_id: str, artifact: Artifact, content: str | bytes) -> Artifact: ...

    @abstractmethod
    def read(self, artifact: Artifact) -> bytes: ...

    @abstractmethod
    def bundle(self, run: Run) -> bytes:
        """Every artifact of a run, plus its manifest, as a zip."""


class ConnectionRepository(ABC):
    @abstractmethod
    def save(self, connection: SourceConnection) -> None: ...

    @abstractmethod
    def get(self, connection_id: str) -> SourceConnection | None: ...

    @abstractmethod
    def list(self) -> list[SourceConnection]: ...

    @abstractmethod
    def delete(self, connection_id: str) -> None: ...
