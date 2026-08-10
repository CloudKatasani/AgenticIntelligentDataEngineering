"""Run lifecycle: the request, the state machine, and the provenance record."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.domain.connection import DatasetRef, TableProfile
from app.domain.input_contract import InputBinding
from app.domain.model import ModelSelection, TokenUsage


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    """The agent's tier is advisory: artifacts are proposals until accepted."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    """A hard dependency or guardrail refused the run before any work happened."""

    REJECTED = "rejected"
    PARTIAL = "partial"
    """Cost cap hit mid-run; whatever completed is persisted and marked."""


TERMINAL_STATUSES = {
    RunStatus.SUCCEEDED,
    RunStatus.FAILED,
    RunStatus.BLOCKED,
    RunStatus.REJECTED,
    RunStatus.PARTIAL,
}


class ArtifactKind(str, Enum):
    PROPOSAL = "proposal"
    """Produced by an L0/L1 agent — requires human acceptance."""

    RECORD = "record"
    """Produced by an agent permitted to act at its tier."""


class Artifact(BaseModel):
    id: str
    run_id: str
    agent_id: str
    key: str
    filename: str
    title: str
    description: str
    format: str
    source: str
    kind: ArtifactKind = ArtifactKind.PROPOSAL
    size_bytes: int = 0
    sha256: str = ""
    created_at: str = ""

    @property
    def download_path(self) -> str:
        return f"/api/artifacts/{self.id}/download"


class RunEvent(BaseModel):
    at: str
    level: str = "info"
    message: str
    data: dict[str, object] = Field(default_factory=dict)


class GateResult(BaseModel):
    """One guardrail decision, recorded whether it passed or not."""

    name: str
    passed: bool
    detail: str
    blocking: bool = True


class RunRequest(BaseModel):
    agent_id: str
    connection_id: str | None = None
    datasets: list[DatasetRef] = Field(default_factory=list)
    """Flattened from the input bindings, because the object budget, the
    dependency scope and the profiler all reason over "the tables this run
    touches" regardless of which slot they arrived in."""

    inputs: dict[str, InputBinding] = Field(default_factory=dict)
    """What the operator supplied, keyed by the agent's own slot keys."""

    model: ModelSelection
    parameters: dict[str, object] = Field(default_factory=dict)
    objective: str = ""
    """Free-text intent from the operator, appended to the task brief."""

    actor: str = "operator"
    """Who asked for this run.

    Self-declared: the product has no authentication, so this is an operator
    label rather than an authenticated identity. It is recorded anyway, because
    adoption cannot be measured without knowing who ran what, and a stated
    limitation is more useful than a missing field.
    """

    cost_cap_usd: float | None = None
    override_dependency_gate: bool = False
    override_reason: str = ""


class Run(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    agent_domain: str
    status: RunStatus = RunStatus.QUEUED
    request: RunRequest
    model_id: str
    effort: str

    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None

    events: list[RunEvent] = Field(default_factory=list)
    gates: list[GateResult] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    profiles: list[TableProfile] = Field(default_factory=list)

    usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost_usd: float = 0.0

    summary: str = ""
    findings: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    handoffs: list[dict[str, str]] = Field(default_factory=list)
    """Work this agent refused because another agent owns it."""

    error: str | None = None
    provider: str = ""

    requested_by: str = "operator"
    """Mirrored off the request so adoption queries never unpack it."""

    approved_by: str | None = None
    approved_at: str | None = None

    def add_event(self, message: str, *, level: str = "info", **data: object) -> None:
        from app.core.ids import utcnow_iso

        self.events.append(RunEvent(at=utcnow_iso(), level=level, message=message, data=data))
