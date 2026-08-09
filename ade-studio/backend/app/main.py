"""ADE Studio application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import academy, agents, connections, graph, health, models, runs
from app.core.config import get_settings
from app.core.errors import install_exception_handlers
from app.core.ids import utcnow_iso
from app.core.logging import configure_logging, get_logger, log_event

logger = get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Control plane for the Agentic Data Engineering fleet: run any of the 35 agents "
            "against a chosen database object, on a chosen model, and download the artifacts."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_exception_handlers(app)

    for router in (
        health.router,
        agents.router,
        graph.router,
        connections.router,
        models.router,
        runs.router,
        academy.router,
    ):
        app.include_router(router)

    _seed_demo_connection()
    _mount_frontend(app)

    log_event(logger, "app_started", environment=settings.environment, at=utcnow_iso())
    return app


def _seed_demo_connection() -> None:
    """Register the demo warehouse on first boot.

    A brand-new install should be able to run an agent immediately, without a
    credential or a setup step.
    """
    from app.api.deps import get_connection_repository
    from app.domain.connection import Environment, SourceConnection, SourceKind

    repo = get_connection_repository()
    if any(c.kind is SourceKind.DEMO for c in repo.list()):
        return
    repo.save(
        SourceConnection(
            id="conn_demo",
            name="ADE Demo Warehouse",
            kind=SourceKind.DEMO,
            environment=Environment.DEV,
            owner="ADE Studio",
            regulated=False,
            database="ADE_DEMO",
            created_at=utcnow_iso(),
        )
    )

    # Build the warehouse now rather than on whichever request happens to touch
    # it first, so the first page load is not the one that pays for it.
    from app.adapters.connectors.demo import ensure_demo_warehouse

    ensure_demo_warehouse(get_settings().demo_warehouse_path)
    log_event(logger, "demo_connection_seeded")


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA when it exists, so one process serves the product."""
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not dist.exists():
        return

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:  # noqa: ARG001 — client-side routing
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


app = create_app()
