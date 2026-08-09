"""The run engine and its guardrails.

Each test here corresponds to a design rule from the agent catalog. If one of
these fails, the product is no longer enforcing the contract it advertises.
"""

from __future__ import annotations

import json

from app.domain.connection import DatasetRef, Environment
from app.domain.model import Effort, ModelSelection
from app.domain.run import RunRequest, RunStatus
from app.services.run_service import RunService

CUSTOMERS = DatasetRef(
    connection_id="conn_demo", database="ADE_DEMO", schema_name="RETAIL", table="CUSTOMERS"
)


def _request(agent_id: str, **overrides) -> RunRequest:
    payload = {
        "agent_id": agent_id,
        "connection_id": "conn_demo",
        "datasets": [CUSTOMERS],
        "model": ModelSelection(model_id="claude-haiku-4-5", effort=Effort.MEDIUM),
        "parameters": {"sample_rows": 100},
    }
    payload.update(overrides)
    return RunRequest(**payload)


def test_profiling_agent_runs_and_writes_its_artifacts(run_service: RunService) -> None:
    run = run_service.execute(_request("01"))

    assert run.status is RunStatus.SUCCEEDED
    assert {a.filename for a in run.artifacts} == {
        "profile.json",
        "inferred-constraints.yaml",
        "profiling-run-report.md",
    }
    assert all(a.size_bytes > 0 and a.sha256 for a in run.artifacts)
    assert run.profiles and run.profiles[0].row_count == 2000
    assert run.findings


def test_numbers_in_artifacts_come_from_the_profiler(run_service: RunService) -> None:
    """Design rule 4: the model never computes the statistics."""
    run = run_service.execute(_request("01"))
    profile_artifact = next(a for a in run.artifacts if a.filename == "profile.json")
    payload = json.loads(run_service.artifacts.read(profile_artifact))

    computed = {c.column: c.null_ratio for c in run.profiles[0].columns}
    reported = {
        c["column"]: c["null_ratio"] for c in payload["objects"][0]["columns"]
    }
    assert reported == computed


def test_hard_dependencies_block_execution(run_service: RunService) -> None:
    """Design rule 2: hard dependencies block; they are not advisory."""
    run = run_service.execute(_request("07"))  # 07 needs 08 and 02

    assert run.status is RunStatus.BLOCKED
    assert run.artifacts == []
    assert "08" in (run.error or "") and "02" in (run.error or "")


def test_dependency_gate_can_be_overridden_with_a_recorded_reason(
    run_service: RunService,
) -> None:
    run = run_service.execute(
        _request("07", override_dependency_gate=True, override_reason="Greenfield build; no upstream yet.")
    )

    assert run.status is not RunStatus.BLOCKED
    gate = next(g for g in run.gates if g.name == "hard_dependencies")
    assert gate.passed is True
    assert "Greenfield build" in gate.detail


def test_satisfying_a_dependency_unblocks_the_downstream_agent(
    run_service: RunService,
) -> None:
    assert run_service.execute(_request("01")).status is RunStatus.SUCCEEDED
    # 02 depends on 01 only.
    run = run_service.execute(_request("02", parameters={"regulations": "GDPR"}))
    assert run.status is not RunStatus.BLOCKED


def test_advisory_tier_produces_proposals_needing_acceptance(
    run_service: RunService,
) -> None:
    """Design rule 3: an L1 agent proposes; a human accepts."""
    run_service.execute(_request("01"))
    run = run_service.execute(_request("02", parameters={"regulations": "GDPR"}))

    assert run.status is RunStatus.AWAITING_APPROVAL
    assert all(a.kind.value == "proposal" for a in run.artifacts)

    decided = run_service.decide(run.id, approve=True, actor="reviewer")
    assert decided.status is RunStatus.SUCCEEDED
    assert all(a.kind.value == "record" for a in decided.artifacts)
    assert decided.approved_by == "reviewer"


def test_rejecting_a_proposal_keeps_it_out_of_the_record(run_service: RunService) -> None:
    run_service.execute(_request("01"))
    run = run_service.execute(_request("02", parameters={"regulations": "GDPR"}))
    decided = run_service.decide(run.id, approve=False, actor="reviewer")

    assert decided.status is RunStatus.REJECTED
    assert all(a.kind.value == "proposal" for a in decided.artifacts)


def test_regulated_source_reports_the_tier_cap(run_service: RunService) -> None:
    """Agents 02, 26 and 27 are capped at L1 on regulated sources.

    All three already declare L1, so today the cap changes nothing — the run
    must say that honestly rather than claim it capped something. The mechanism
    still guards the rule if one of those agents is ever promoted.
    """
    connection = run_service.connections.get("conn_demo")
    assert connection is not None
    connection.regulated = True
    run_service.connections.save(connection)

    preview = run_service.preview(_request("26"))
    assert preview["effective_tier"] == "L1"
    gate = next(g for g in preview["gates"] if g["name"] == "autonomy_tier")
    assert "capped at L1 on regulated sources" in gate["detail"]
    assert "already meets that cap" in gate["detail"]


def test_tier_cap_would_bind_a_promoted_agent(run_service: RunService) -> None:
    """The cap is enforced by tier comparison, not by the current catalog values."""
    from app.domain.agent import AutonomyTier

    agent = run_service.catalog.get("26").model_copy(update={"tier": AutonomyTier.L3})
    assert agent.effective_tier(regulated=True) is AutonomyTier.L1
    assert agent.effective_tier(regulated=False) is AutonomyTier.L3


def test_agent_20_never_executes_against_production(run_service: RunService) -> None:
    """Only agent 20 may mutate production data — and this product still won't."""
    connection = run_service.connections.get("conn_demo")
    assert connection is not None
    connection.environment = Environment.PROD
    run_service.connections.save(connection)

    run = run_service.execute(
        _request("20", parameters={"allow_production_actions": True}, override_dependency_gate=True,
                 override_reason="test")
    )
    assert run.status is RunStatus.BLOCKED
    gate = next(g for g in run.gates if g.name == "production_actions")
    assert gate.passed is False


def test_required_parameters_are_enforced(run_service: RunService) -> None:
    run = run_service.execute(_request("31", datasets=[]))
    assert run.status is RunStatus.BLOCKED
    assert "Business question" in (run.error or "")


def test_object_selection_is_required_for_dataset_scoped_agents(
    run_service: RunService,
) -> None:
    run = run_service.execute(_request("01", datasets=[]))
    assert run.status is RunStatus.BLOCKED

    # Estate-scoped agents do not need objects.
    estate = run_service.execute(_request("22", datasets=[]))
    assert estate.status is not RunStatus.BLOCKED


def test_bundle_contains_every_artifact_and_a_manifest(run_service: RunService) -> None:
    import io
    import zipfile

    run = run_service.execute(_request("01"))
    archive = zipfile.ZipFile(io.BytesIO(run_service.artifacts.bundle(run)))
    names = archive.namelist()

    assert "MANIFEST.json" in names and "README.md" in names
    for artifact in run.artifacts:
        assert f"artifacts/{artifact.filename}" in names

    manifest = json.loads(archive.read("MANIFEST.json"))
    assert manifest["agent"]["id"] == "01"
    assert manifest["model"]["id"] == "claude-haiku-4-5"
    assert [g["name"] for g in manifest["gates"]]


def test_preview_reports_gates_without_executing(run_service: RunService) -> None:
    preview = run_service.preview(_request("07"))
    assert preview["blocked"] is True
    assert run_service.runs.list() == []


def test_upstream_output_is_offered_to_downstream_agents(run_service: RunService) -> None:
    upstream = run_service.execute(_request("01"))
    context = run_service._upstream_context(  # noqa: SLF001 — asserting internal contract
        run_service.catalog.get("02"), _request("02")
    )
    assert any(item["run_id"] == upstream.id for item in context)
