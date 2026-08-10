"""Every agent in the fleet must actually run.

The workbench offers all 35 agents, so all 35 have to produce their declared
artifacts. This is the test that catches a spec whose artifact plan, parameters
or dataset requirement was never exercised by hand.
"""

from __future__ import annotations

import pytest

from app.domain.run import RunStatus
from app.services.run_service import RunService
from tests.support import request_for


@pytest.mark.parametrize("agent_id", [f"{i:02d}" for i in range(1, 36)])
def test_agent_runs_and_produces_its_declared_artifacts(
    agent_id: str, run_service: RunService
) -> None:
    agent = run_service.catalog.get(agent_id)

    # Built from the agent's own input contract, so each one is handed the kind
    # of material it actually consumes. Every agent runs in isolation here, so
    # the dependency override is the documented escape hatch and is recorded.
    run = run_service.execute(request_for(agent_id))

    assert run.status in {RunStatus.SUCCEEDED, RunStatus.AWAITING_APPROVAL}, (
        f"agent {agent_id} finished {run.status.value}: {run.error}"
    )
    produced = {a.key for a in run.artifacts}
    declared = {a.key for a in agent.artifacts}
    assert produced == declared, f"agent {agent_id} produced {produced}, declared {declared}"

    for artifact in run.artifacts:
        assert artifact.size_bytes > 0, f"{agent_id}/{artifact.filename} is empty"
        assert artifact.sha256, f"{agent_id}/{artifact.filename} has no hash"

    assert run.summary, f"agent {agent_id} produced no summary"

    # Advisory tiers must never emit records without a human decision.
    if agent.requires_approval:
        assert run.status is RunStatus.AWAITING_APPROVAL
        assert all(a.kind.value == "proposal" for a in run.artifacts)


def test_json_and_yaml_artifacts_parse(run_service: RunService) -> None:
    """Declared formats must actually be well-formed on disk."""
    import json

    import yaml

    for agent_id in ("01", "13", "16", "26", "29"):
        run = run_service.execute(request_for(agent_id))
        for artifact in run.artifacts:
            body = run_service.artifacts.read(artifact).decode("utf-8")
            if artifact.format == "json":
                json.loads(body)
            elif artifact.format == "yaml":
                assert yaml.safe_load(body) is not None
