"""Run submission, history, approval and artifact download."""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_artifact_store, get_run_repository, get_run_service
from app.core.errors import NotFound
from app.domain.model import Effort, ModelSelection
from app.domain.run import RunRequest
from app.services.run_service import dataset_from_dict

router = APIRouter(prefix="/api", tags=["runs"])


class DatasetInput(BaseModel):
    database: str | None = None
    schema_name: str | None = None
    table: str
    columns: list[str] = Field(default_factory=list)


class RunInput(BaseModel):
    agent_id: str
    connection_id: str | None = None
    datasets: list[DatasetInput] = Field(default_factory=list)
    model_id: str
    effort: Effort = Effort.HIGH
    max_output_tokens: int = 16_000
    parameters: dict[str, object] = Field(default_factory=dict)
    objective: str = ""
    actor: str = "operator"
    cost_cap_usd: float | None = None
    override_dependency_gate: bool = False
    override_reason: str = ""

    def to_domain(self) -> RunRequest:
        return RunRequest(
            agent_id=self.agent_id,
            connection_id=self.connection_id,
            datasets=[
                dataset_from_dict(self.connection_id or "", d.model_dump())
                for d in self.datasets
            ],
            model=ModelSelection(
                model_id=self.model_id,
                effort=self.effort,
                max_output_tokens=self.max_output_tokens,
            ),
            parameters=self.parameters,
            objective=self.objective,
            actor=self.actor,
            cost_cap_usd=self.cost_cap_usd,
            override_dependency_gate=self.override_dependency_gate,
            override_reason=self.override_reason,
        )


class DecisionInput(BaseModel):
    approve: bool
    actor: str = "operator"
    note: str = ""


@router.post("/runs/preview")
def preview_run(payload: RunInput) -> dict[str, object]:
    """Guardrail verdicts and a cost estimate, before anything executes."""
    return get_run_service().preview(payload.to_domain())


@router.post("/runs")
def create_run(payload: RunInput) -> dict[str, object]:
    run = get_run_service().execute(payload.to_domain())
    return _serialise(run)


@router.get("/runs")
def list_runs(agent_id: str | None = None, limit: int = Query(50, le=500)) -> dict[str, object]:
    runs = get_run_repository().list(agent_id=agent_id, limit=limit)
    return {"count": len(runs), "runs": [_summary(r) for r in runs]}


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    run = get_run_repository().get(run_id)
    if run is None:
        raise NotFound(f"No run {run_id!r}.")
    return _serialise(run)


@router.post("/runs/{run_id}/decision")
def decide_run(run_id: str, payload: DecisionInput) -> dict[str, object]:
    run = get_run_service().decide(
        run_id, approve=payload.approve, actor=payload.actor, note=payload.note
    )
    return _serialise(run)


@router.get("/runs/{run_id}/bundle")
def download_bundle(run_id: str) -> Response:
    run = get_run_repository().get(run_id)
    if run is None:
        raise NotFound(f"No run {run_id!r}.")
    payload = get_artifact_store().bundle(run)
    filename = f"{run.agent_id}-{run.agent_name.replace(' ', '-').lower()}-{run.id}.zip"
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str) -> Response:
    store = get_artifact_store()
    for run in get_run_repository().list(limit=1000):
        for artifact in run.artifacts:
            if artifact.id == artifact_id:
                data = store.read(artifact)
                quoted = urllib.parse.quote(artifact.filename)
                return Response(
                    content=data,
                    media_type=_media_type(artifact.format),
                    headers={
                        "Content-Disposition": f'attachment; filename="{quoted}"',
                        "X-Artifact-Kind": artifact.kind.value,
                    },
                )
    raise NotFound(f"No artifact {artifact_id!r}.")


@router.get("/artifacts/{artifact_id}/content")
def view_artifact(artifact_id: str) -> dict[str, object]:
    """Inline view for the workbench, so artifacts are readable before download."""
    store = get_artifact_store()
    for run in get_run_repository().list(limit=1000):
        for artifact in run.artifacts:
            if artifact.id == artifact_id:
                return {
                    **artifact.model_dump(mode="json"),
                    "content": store.read(artifact).decode("utf-8", errors="replace"),
                }
    raise NotFound(f"No artifact {artifact_id!r}.")


def _media_type(fmt: str) -> str:
    return {
        "json": "application/json",
        "yaml": "application/yaml",
        "markdown": "text/markdown",
        "sql": "application/sql",
        "csv": "text/csv",
        "python": "text/x-python",
    }.get(fmt, "text/plain")


def _summary(run) -> dict[str, object]:  # noqa: ANN001 — domain Run
    return {
        "id": run.id,
        "agent_id": run.agent_id,
        "agent_name": run.agent_name,
        "agent_domain": run.agent_domain,
        "status": run.status.value,
        "model_id": run.model_id,
        "effort": run.effort,
        "provider": run.provider,
        "requested_by": run.requested_by,
        "approved_by": run.approved_by,
        "created_at": run.created_at,
        "duration_ms": run.duration_ms,
        "artifact_count": len(run.artifacts),
        "cost_usd": run.usage.cost_usd,
        "objects": [d.fqn for d in run.request.datasets],
        "summary": run.summary,
        "error": run.error,
    }


def _serialise(run) -> dict[str, object]:  # noqa: ANN001 — domain Run
    payload = run.model_dump(mode="json")
    payload["artifacts"] = [
        {**a.model_dump(mode="json"), "download_url": f"/api/artifacts/{a.id}/download",
         "view_url": f"/api/artifacts/{a.id}/content"}
        for a in run.artifacts
    ]
    payload["bundle_url"] = f"/api/runs/{run.id}/bundle"
    return payload
