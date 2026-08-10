"""The run engine.

A run is: check the guardrails, compute the facts, reason over them, write the
artifacts, and record how all of that happened. The guardrails are the reason
this is a service and not a chat window — each one is a design rule from the
catalog, enforced in code:

* hard dependencies block execution (rule 2)
* autonomy tiers are structural, and capped in regulated environments (rule 3)
* statistics come from the profiler, never the model (rule 4)
* every agent's non-goals become handoffs rather than scope creep (rule 1)
"""

from __future__ import annotations

import json
import time
from typing import Any

import yaml

from app.adapters.connectors.registry import connector_for
from app.adapters.llm.anthropic_provider import AnthropicProvider
from app.adapters.llm.simulation_provider import SimulationProvider
from app.core.config import Settings
from app.core.errors import NotFound, ValidationFailed
from app.core.ids import new_id, utcnow_iso
from app.core.logging import get_logger, log_event
from app.domain.agent import AgentSpec, ArtifactSpec
from app.domain.connection import DatasetRef, SourceConnection, TableProfile
from app.domain.model import Effort, ModelSelection
from app.domain.run import (
    Artifact,
    ArtifactKind,
    GateResult,
    Run,
    RunRequest,
    RunStatus,
)
from app.ports.llm_provider import LLMProvider, LLMRequest
from app.ports.repositories import ArtifactStore, ConnectionRepository, RunRepository
from app.runtime import prompt as prompt_builder
from app.services.catalog_service import CatalogService
from app.services.model_registry import estimate_tokens, get_model

logger = get_logger(__name__)


class RunService:
    def __init__(
        self,
        *,
        catalog: CatalogService,
        runs: RunRepository,
        artifacts: ArtifactStore,
        connections: ConnectionRepository,
        settings: Settings,
        provider: LLMProvider | None = None,
    ) -> None:
        self.catalog = catalog
        self.runs = runs
        self.artifacts = artifacts
        self.connections = connections
        self.settings = settings
        self._provider_override = provider

    # ------------------------------------------------------------------ #
    # Provider selection
    # ------------------------------------------------------------------ #

    def provider(self) -> LLMProvider:
        """Anthropic when a key is configured, otherwise the offline provider.

        Falling back rather than failing is deliberate: the product must be
        demonstrable with no credentials, and every artifact records which
        provider produced it.
        """
        if self._provider_override is not None:
            return self._provider_override
        anthropic = AnthropicProvider()
        return anthropic if anthropic.available() else SimulationProvider()

    def provider_status(self) -> dict[str, object]:
        anthropic = AnthropicProvider()
        live = anthropic.available()
        return {
            "provider": "anthropic" if live else "simulation",
            "live": live,
            "detail": (
                "Runs execute on the selected Claude model."
                if live
                else "No ADE_ANTHROPIC_API_KEY configured. Runs execute offline: statistics are "
                "real, narrative is templated, and every artifact is labelled as simulated."
            ),
        }

    # ------------------------------------------------------------------ #
    # Preflight
    # ------------------------------------------------------------------ #

    def preview(self, request: RunRequest) -> dict[str, Any]:
        """What the workbench shows before the operator commits to a run."""
        agent = self.catalog.get(request.agent_id)
        connection = self._connection(request)
        gates = self._evaluate_gates(agent, request, connection, dry_run=True)
        model = get_model(request.model.model_id)
        estimated_input, estimated_output, estimated_cost = self._estimate(agent, request)

        return {
            "agent": {"id": agent.id, "name": agent.name, "tier": agent.tier.value},
            "gates": [g.model_dump() for g in gates],
            "blocked": any(g.blocking and not g.passed for g in gates),
            "requires_approval": agent.effective_tier(
                bool(connection and connection.regulated)
            ).rank <= 1,
            "effective_tier": agent.effective_tier(
                bool(connection and connection.regulated)
            ).value,
            "artifacts": [a.model_dump() for a in agent.artifacts],
            "estimate": {
                "input_tokens": estimated_input,
                "output_tokens": estimated_output,
                "cost_usd": estimated_cost,
                "model": model.display_name,
                "note": "Approximate. The run records the provider's actual usage.",
            },
        }

    def _estimate(self, agent: Any, request: RunRequest) -> tuple[int, int, float]:
        """List-price cost of a run before it happens.

        Recorded on every run, not only shown in the preview. An offline run
        bills nothing, so without this the FinOps view has nothing to say until
        a model is connected — and "what would this fleet activity have cost"
        is exactly the question being asked at that point. It is list price
        against estimated tokens, and every surface that shows it says so.
        """
        model = get_model(request.model.model_id)
        # Rough: the brief is dominated by the profile table, ~90 tokens/column.
        columns = sum(max(len(d.columns), 12) for d in request.datasets) or 20
        estimated_input = estimate_tokens(agent.skill_markdown) + columns * 90 + 900
        estimated_output = min(request.model.max_output_tokens, 1200 * len(agent.artifacts) + 800)
        return (
            estimated_input,
            estimated_output,
            round(model.estimate_cost_usd(estimated_input, estimated_output), 6),
        )

    # ------------------------------------------------------------------ #
    # Gates
    # ------------------------------------------------------------------ #

    def _connection(self, request: RunRequest) -> SourceConnection | None:
        if not request.connection_id:
            return None
        connection = self.connections.get(request.connection_id)
        if connection is None:
            raise NotFound(f"No connection {request.connection_id!r}.")
        return connection

    def _evaluate_gates(
        self,
        agent: AgentSpec,
        request: RunRequest,
        connection: SourceConnection | None,
        *,
        dry_run: bool,
    ) -> list[GateResult]:
        gates: list[GateResult] = []

        # 1. Object selection.
        if agent.requires_dataset:
            ok = bool(request.datasets)
            gates.append(
                GateResult(
                    name="object_selection",
                    passed=ok,
                    detail=(
                        f"{len(request.datasets)} object(s) selected."
                        if ok
                        else "This agent reasons over specific database objects; select at least one."
                    ),
                )
            )
        if len(request.datasets) > self.settings.max_objects_per_run:
            gates.append(
                GateResult(
                    name="object_budget",
                    passed=False,
                    detail=(
                        f"{len(request.datasets)} objects exceeds the per-run limit of "
                        f"{self.settings.max_objects_per_run}. Split the run."
                    ),
                )
            )

        # 2. Required parameters.
        missing = [
            p.label for p in agent.parameters
            if p.required and not str(request.parameters.get(p.key, "")).strip()
        ]
        if missing:
            gates.append(
                GateResult(
                    name="required_parameters",
                    passed=False,
                    detail="Missing required input: " + ", ".join(missing),
                )
            )

        # 3. Hard dependencies (design rule 2).
        scope = {d.fqn for d in request.datasets}
        unmet: list[str] = []
        for dep in agent.hard_dependencies:
            if not self.runs.find_successful(dep.agent_id, scope):
                unmet.append(f"{dep.agent_id} {dep.agent_name}")
        if unmet:
            gates.append(
                GateResult(
                    name="hard_dependencies",
                    passed=bool(request.override_dependency_gate),
                    blocking=not request.override_dependency_gate,
                    detail=(
                        "Overridden by operator: " + request.override_reason
                        if request.override_dependency_gate
                        else "No completed run found for required upstream agent(s): "
                        + "; ".join(unmet)
                        + ". Run them first, or override with a recorded reason."
                    ),
                )
            )
        else:
            gates.append(
                GateResult(
                    name="hard_dependencies",
                    passed=True,
                    detail=(
                        "All hard dependencies satisfied."
                        if agent.hard_dependencies
                        else "This agent has no hard dependencies."
                    ),
                )
            )

        # 4. Autonomy tier (design rule 3).
        regulated = bool(connection and connection.regulated)
        effective = agent.effective_tier(regulated)
        if effective != agent.tier:
            tier_detail = (
                f"Capped to {effective.value} from {agent.tier.value}: the source is marked "
                "regulated."
            )
        elif regulated and agent.regulated_tier_cap is not None:
            # The cap is declared and active; the agent's own tier already
            # satisfies it, so nothing changes. Say so rather than implying the
            # cap did work it did not do.
            tier_detail = (
                f"Operating at declared tier {effective.value} ({agent.tier_name}). This agent is "
                f"capped at {agent.regulated_tier_cap.value} on regulated sources; its declared "
                "tier already meets that cap."
            )
        else:
            tier_detail = f"Operating at declared tier {effective.value} ({agent.tier_name})."
        gates.append(
            GateResult(name="autonomy_tier", passed=True, blocking=False, detail=tier_detail)
        )

        # 5. Production mutation. Agent 20 is the only agent permitted to mutate
        #    production data, and only from a versioned action catalog.
        if agent.id == "20" and request.parameters.get("allow_production_actions"):
            prod = bool(connection and connection.environment.value == "prod")
            gates.append(
                GateResult(
                    name="production_actions",
                    passed=not prod,
                    detail=(
                        "Production actions requested against a production source. ADE Studio "
                        "plans remediation but never executes it; the plan requires human "
                        "approval and an approved action-catalog entry."
                        if prod
                        else "Production actions requested in a non-production environment; the "
                        "plan is still emitted for review rather than executed."
                    ),
                    blocking=prod,
                )
            )

        # 6. Cost cap.
        cap = request.cost_cap_usd or self.settings.default_cost_cap_usd
        gates.append(
            GateResult(
                name="cost_cap",
                passed=True,
                blocking=False,
                detail=f"Per-run cap ${cap:.2f}. Work stops and partial results persist if reached.",
            )
        )
        return gates

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #

    def execute(self, request: RunRequest) -> Run:
        agent = self.catalog.get(request.agent_id)
        connection = self._connection(request)
        started = time.perf_counter()

        run = Run(
            id=new_id("run"),
            agent_id=agent.id,
            agent_name=agent.name,
            agent_domain=agent.domain,
            request=request,
            model_id=request.model.model_id,
            effort=request.model.effort.value,
            requested_by=request.actor.strip() or "operator",
            created_at=utcnow_iso(),
            started_at=utcnow_iso(),
        )
        run.add_event("Run created", agent=agent.id, model=request.model.model_id)
        run.estimated_cost_usd = self._estimate(agent, request)[2]

        gates = self._evaluate_gates(agent, request, connection, dry_run=False)
        run.gates = gates
        blocking = [g for g in gates if g.blocking and not g.passed]
        if blocking:
            run.status = RunStatus.BLOCKED
            run.error = "; ".join(g.detail for g in blocking)
            run.finished_at = utcnow_iso()
            run.add_event("Blocked by guardrail", level="error", gates=[g.name for g in blocking])
            self.runs.save(run)
            log_event(logger, "run_blocked", run_id=run.id, agent=agent.id)
            return run

        try:
            profiles = self._profile(run, agent, request, connection)
            run.profiles = profiles

            upstream = self._upstream_context(agent, request)
            effective_tier = agent.effective_tier(bool(connection and connection.regulated))

            system = prompt_builder.build_system_prompt(agent)
            brief = prompt_builder.build_task_brief(
                agent,
                connection=connection,
                profiles=profiles,
                parameters=request.parameters,
                objective=request.objective,
                upstream=upstream,
                effective_tier=effective_tier.value,
            )

            provider = self.provider()
            run.provider = provider.name
            run.add_event("Reasoning", provider=provider.name, model=request.model.model_id)

            response = provider.complete(
                LLMRequest(
                    system=system,
                    user=brief,
                    selection=request.model,
                    output_schema=prompt_builder.output_schema(agent),
                    context=prompt_builder.simulation_context(
                        agent,
                        profiles=profiles,
                        datasets=[d.fqn for d in request.datasets],
                        parameters=request.parameters,
                    ),
                )
            )

            if response.refused:
                run.status = RunStatus.FAILED
                run.error = (
                    "The model declined this request. Rephrase the objective or select a "
                    "different model."
                )
                run.add_event("Model declined the request", level="error")
                run.finished_at = utcnow_iso()
                self.runs.save(run)
                return run

            run.usage = response.usage
            run.summary = str(response.data.get("summary") or response.text or "").strip()
            run.findings = [str(f) for f in (response.data.get("findings") or [])]
            run.open_questions = [str(q) for q in (response.data.get("open_questions") or [])]
            run.handoffs = [
                {str(k): str(v) for k, v in h.items()}
                for h in (response.data.get("handoffs") or [])
                if isinstance(h, dict)
            ]

            cap = request.cost_cap_usd or self.settings.default_cost_cap_usd
            over_cap = response.usage.cost_usd > cap

            run.artifacts = self._write_artifacts(
                run, agent, response.data.get("artifacts"), effective_tier.rank <= 1
            )

            if over_cap:
                run.status = RunStatus.PARTIAL
                run.add_event(
                    "Cost cap exceeded; results persisted and marked PARTIAL",
                    level="warning",
                    cost_usd=response.usage.cost_usd,
                    cap_usd=cap,
                )
            elif effective_tier.rank <= 1:
                run.status = RunStatus.AWAITING_APPROVAL
                run.add_event(
                    "Awaiting human acceptance",
                    detail=f"Tier {effective_tier.value} is advisory; artifacts are proposals.",
                )
            else:
                run.status = RunStatus.SUCCEEDED
                run.add_event("Completed")

        except Exception as exc:  # noqa: BLE001 — recorded on the run, not swallowed
            run.status = RunStatus.FAILED
            run.error = str(exc)
            run.add_event("Run failed", level="error", error=str(exc))
            log_event(logger, "run_failed", run_id=run.id, agent=agent.id, error=str(exc))

        run.finished_at = utcnow_iso()
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        self.runs.save(run)
        log_event(
            logger,
            "run_finished",
            run_id=run.id,
            agent=agent.id,
            status=run.status.value,
            artifacts=len(run.artifacts),
            cost_usd=run.usage.cost_usd,
        )
        return run

    # ------------------------------------------------------------------ #

    def _profile(
        self,
        run: Run,
        agent: AgentSpec,
        request: RunRequest,
        connection: SourceConnection | None,
    ) -> list[TableProfile]:
        """Compute the deterministic facts the agent will reason over."""
        if not request.datasets or connection is None:
            return []
        sample = int(request.parameters.get("sample_rows") or 200)
        sample = max(10, min(sample, self.settings.max_sample_rows))
        connector = connector_for(connection)

        profiles: list[TableProfile] = []
        for dataset in request.datasets:
            try:
                profiles.append(connector.profile_table(dataset, sample))
                run.add_event("Profiled object", object=dataset.fqn, sample_rows=sample)
            except Exception as exc:  # noqa: BLE001 — one bad object must not fail the run
                run.add_event(
                    "Skipped object", level="warning", object=dataset.fqn, reason=str(exc)
                )
        return profiles

    def _upstream_context(self, agent: AgentSpec, request: RunRequest) -> list[dict[str, Any]]:
        """The most recent completed output of each dependency, for grounding."""
        scope = {d.fqn for d in request.datasets}
        out: list[dict[str, Any]] = []
        for dep in agent.hard_dependencies + agent.soft_dependencies:
            matches = self.runs.find_successful(dep.agent_id, scope)
            if not matches:
                continue
            latest = matches[0]
            out.append(
                {
                    "agent_id": dep.agent_id,
                    "agent_name": dep.agent_name,
                    "run_id": latest.id,
                    "summary": latest.summary,
                    "findings": latest.findings,
                }
            )
        return out

    def _write_artifacts(
        self,
        run: Run,
        agent: AgentSpec,
        raw: Any,
        is_proposal: bool,
    ) -> list[Artifact]:
        contents = _normalise_artifacts(raw)
        written: list[Artifact] = []
        for spec in agent.artifacts:
            body = contents.get(spec.key)
            if body is None:
                run.add_event("Artifact not produced", level="warning", key=spec.key)
                continue
            serialised = _serialise(spec, body)
            artifact = Artifact(
                id=new_id("art"),
                run_id=run.id,
                agent_id=agent.id,
                key=spec.key,
                filename=spec.filename,
                title=spec.title,
                description=spec.description,
                format=spec.format.value,
                source=spec.source.value,
                kind=ArtifactKind.PROPOSAL if is_proposal else ArtifactKind.RECORD,
            )
            written.append(self.artifacts.write(run.id, artifact, serialised))
        run.add_event("Artifacts written", count=len(written))
        return written

    # ------------------------------------------------------------------ #
    # Approval
    # ------------------------------------------------------------------ #

    def decide(self, run_id: str, *, approve: bool, actor: str, note: str = "") -> Run:
        run = self.runs.get(run_id)
        if run is None:
            raise NotFound(f"No run {run_id!r}.")
        if run.status is not RunStatus.AWAITING_APPROVAL:
            raise ValidationFailed(
                f"Run {run_id} is {run.status.value}; only a run awaiting approval can be decided."
            )
        run.status = RunStatus.SUCCEEDED if approve else RunStatus.REJECTED
        run.approved_by = actor
        run.approved_at = utcnow_iso()
        if approve:
            for artifact in run.artifacts:
                artifact.kind = ArtifactKind.RECORD
        run.add_event(
            "Accepted by human" if approve else "Rejected by human", actor=actor, note=note
        )
        self.runs.save(run)
        return run


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _normalise_artifacts(raw: Any) -> dict[str, Any]:
    """Accept either the schema's list form or a plain mapping."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        out: dict[str, Any] = {}
        for item in raw:
            if isinstance(item, dict) and "key" in item:
                out[str(item["key"])] = item.get("content")
        return out
    return {}


def _serialise(spec: ArtifactSpec, body: Any) -> str:
    """Render artifact content in its declared format.

    A model asked for JSON returns a JSON *string*; a dict may arrive from the
    offline provider. Both end up as well-formed files, and malformed JSON is
    preserved verbatim rather than silently dropped.
    """
    fmt = spec.format.value
    if fmt == "json":
        if isinstance(body, (dict, list)):
            return json.dumps(body, indent=2, default=str)
        text = str(body).strip()
        text = _strip_fence(text)
        try:
            return json.dumps(json.loads(text), indent=2)
        except json.JSONDecodeError:
            return json.dumps(
                {"_warning": "Model output was not valid JSON; preserved verbatim.", "raw": text},
                indent=2,
            )
    if fmt == "yaml":
        if isinstance(body, (dict, list)):
            return yaml.safe_dump(body, sort_keys=False, allow_unicode=True)
        return _strip_fence(str(body))
    return _strip_fence(str(body))


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip().startswith("```"):
        return "\n".join(lines[1:-1])
    return text


def build_default_selection(agent: AgentSpec) -> ModelSelection:
    from app.services.model_registry import recommend_for

    recommendation = recommend_for(agent)
    return ModelSelection(
        model_id=str(recommendation["model_id"]),
        effort=Effort(str(recommendation["effort"])),
        max_output_tokens=int(recommendation["max_output_tokens"]),
    )


def dataset_from_dict(connection_id: str, payload: dict[str, Any]) -> DatasetRef:
    return DatasetRef(
        connection_id=connection_id,
        database=payload.get("database"),
        schema_name=payload.get("schema_name") or payload.get("schema"),
        table=str(payload.get("table", "")),
        columns=[str(c) for c in payload.get("columns", []) or []],
    )
