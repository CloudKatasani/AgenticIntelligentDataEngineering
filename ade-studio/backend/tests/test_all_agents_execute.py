"""Every agent in the fleet must actually run.

The workbench offers all 35 agents, so all 35 have to produce their declared
artifacts. This is the test that catches a spec whose artifact plan, parameters
or dataset requirement was never exercised by hand.
"""

from __future__ import annotations

import pytest

from app.domain.connection import DatasetRef
from app.domain.model import Effort, ModelSelection
from app.domain.run import RunRequest, RunStatus
from app.services.run_service import RunService

CUSTOMERS = DatasetRef(
    connection_id="conn_demo", database="ADE_DEMO", schema_name="RETAIL", table="CUSTOMERS"
)

# Agents whose spec declares a required free-text input.
REQUIRED_INPUTS: dict[str, dict[str, object]] = {
    "31": {"question": "What was revenue by channel last quarter?"},
    "32": {"request_text": "We need a weekly churn report for the EMEA sales team."},
    "33": {"goal": "Onboard the retail source and publish a customer-360 product."},
    "34": {"target_agent_id": "16"},
    "35": {"artifact_under_review": "quality-rules.yaml proposing 12 rules on RETAIL.CUSTOMERS."},
}


@pytest.mark.parametrize("agent_id", [f"{i:02d}" for i in range(1, 36)])
def test_agent_runs_and_produces_its_declared_artifacts(
    agent_id: str, run_service: RunService
) -> None:
    agent = run_service.catalog.get(agent_id)

    request = RunRequest(
        agent_id=agent_id,
        connection_id="conn_demo",
        datasets=[CUSTOMERS] if agent.requires_dataset else [],
        model=ModelSelection(model_id="claude-haiku-4-5", effort=Effort.LOW),
        parameters={"sample_rows": 50, **REQUIRED_INPUTS.get(agent_id, {})},
        # Every agent is exercised in isolation here, so upstream runs do not
        # exist. The override is the documented escape hatch and is recorded.
        override_dependency_gate=True,
        override_reason="Fleet-wide smoke test: each agent is exercised in isolation.",
    )

    run = run_service.execute(request)

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
        agent = run_service.catalog.get(agent_id)
        run = run_service.execute(
            RunRequest(
                agent_id=agent_id,
                connection_id="conn_demo",
                datasets=[CUSTOMERS] if agent.requires_dataset else [],
                model=ModelSelection(model_id="claude-haiku-4-5", effort=Effort.LOW),
                parameters={"sample_rows": 50},
                override_dependency_gate=True,
                override_reason="format check",
            )
        )
        for artifact in run.artifacts:
            body = run_service.artifacts.read(artifact).decode("utf-8")
            if artifact.format == "json":
                json.loads(body)
            elif artifact.format == "yaml":
                assert yaml.safe_load(body) is not None
