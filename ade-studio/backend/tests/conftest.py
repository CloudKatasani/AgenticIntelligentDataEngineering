"""Test fixtures.

Each test gets an isolated data directory, so runs, artifacts and connections
never leak between tests or into a developer's real workspace.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.storage.filesystem_artifact_store import FilesystemArtifactStore  # noqa: E402
from app.adapters.storage.json_repositories import (  # noqa: E402
    JsonConnectionRepository,
    JsonDocumentSpaceRepository,
    JsonRunRepository,
)
from app.core.config import Settings  # noqa: E402
from app.core.ids import utcnow_iso  # noqa: E402
from app.domain.connection import Environment, SourceConnection, SourceKind  # noqa: E402
from app.services.catalog_service import CatalogService, get_catalog_service  # noqa: E402
from app.services.input_service import InputService  # noqa: E402
from app.services.run_service import RunService  # noqa: E402


@pytest.fixture(scope="session")
def catalog() -> CatalogService:
    return get_catalog_service()


@pytest.fixture(scope="session")
def seeded_warehouse(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Seed the demo warehouse once per session.

    Seeding writes ~30k rows; doing it per test dominated the suite's runtime.
    Each test still gets its own copy, so nothing is shared but the bytes.
    """
    from app.adapters.connectors.demo import seed_demo_warehouse

    path = tmp_path_factory.mktemp("warehouse") / "demo.duckdb"
    seed_demo_warehouse(path)
    return path


@pytest.fixture
def settings(tmp_path: Path, seeded_warehouse: Path) -> Settings:
    import shutil

    settings = Settings(data_root=tmp_path, specs_root=get_catalog_service().specs_root)
    settings.ensure_dirs()
    shutil.copy(seeded_warehouse, settings.demo_warehouse_path)
    return settings


@pytest.fixture
def demo_connection(settings: Settings) -> SourceConnection:
    return SourceConnection(
        id="conn_demo",
        name="Demo",
        kind=SourceKind.DEMO,
        environment=Environment.DEV,
        database="ADE_DEMO",
        file_path=str(settings.demo_warehouse_path),
        created_at=utcnow_iso(),
    )


@pytest.fixture
def run_service(
    settings: Settings,
    catalog: CatalogService,
    demo_connection: SourceConnection,
    input_service: InputService,
) -> RunService:
    settings.ensure_dirs()
    connections = JsonConnectionRepository(settings.connections_path)
    connections.save(demo_connection)
    return RunService(
        catalog=catalog,
        runs=JsonRunRepository(settings.runs_db_path),
        artifacts=FilesystemArtifactStore(settings.artifacts_dir),
        connections=connections,
        settings=settings,
        inputs=input_service,
    )


@pytest.fixture
def sample_space(settings: Settings) -> JsonDocumentSpaceRepository:
    """A shared-drive space holding the seeded sample artifacts.

    The same files the app seeds on first boot, so the tests exercise the
    document path against realistic content rather than a lorem-ipsum stub.
    """
    from app.adapters.documents.demo_artifacts import ensure_demo_documents
    from app.domain.document import DocumentSpace, SpaceKind

    root = settings.data_root / "sample_documents"
    ensure_demo_documents(root)

    spaces = JsonDocumentSpaceRepository(settings.spaces_path)
    spaces.save(
        DocumentSpace(
            id="space_samples",
            name="Sample artifacts",
            kind=SpaceKind.SHARED_DRIVE,
            root_path=str(root),
            created_at=utcnow_iso(),
        )
    )
    spaces.save(
        DocumentSpace(
            id="space_uploads",
            name="Uploads",
            kind=SpaceKind.UPLOAD,
            created_at=utcnow_iso(),
        )
    )
    return spaces


@pytest.fixture
def input_service(settings: Settings, sample_space: JsonDocumentSpaceRepository) -> InputService:
    return InputService(sample_space, settings.uploads_dir)
