"""Composition root: wires ports to adapters, once."""

from __future__ import annotations

from functools import lru_cache

from app.adapters.storage.filesystem_artifact_store import FilesystemArtifactStore
from app.adapters.storage.json_repositories import JsonConnectionRepository, JsonRunRepository
from app.core.config import Settings, get_settings
from app.services.academy_service import AcademyService
from app.services.catalog_service import CatalogService, get_catalog_service
from app.services.graph_service import GraphService
from app.services.run_service import RunService


@lru_cache(maxsize=1)
def get_run_repository() -> JsonRunRepository:
    return JsonRunRepository(get_settings().runs_db_path)


@lru_cache(maxsize=1)
def get_artifact_store() -> FilesystemArtifactStore:
    return FilesystemArtifactStore(get_settings().artifacts_dir)


@lru_cache(maxsize=1)
def get_connection_repository() -> JsonConnectionRepository:
    return JsonConnectionRepository(get_settings().connections_path)


@lru_cache(maxsize=1)
def get_graph_service() -> GraphService:
    return GraphService(get_catalog_service())


@lru_cache(maxsize=1)
def get_academy_service() -> AcademyService:
    return AcademyService(get_catalog_service())


@lru_cache(maxsize=1)
def get_run_service() -> RunService:
    return RunService(
        catalog=get_catalog_service(),
        runs=get_run_repository(),
        artifacts=get_artifact_store(),
        connections=get_connection_repository(),
        settings=get_settings(),
    )


def catalog() -> CatalogService:
    return get_catalog_service()


def settings() -> Settings:
    return get_settings()
