"""Building a valid run request for any agent, from that agent's own contract.

The fleet does not share an input shape, so a test that hands every agent a
table is testing something the product no longer does. This reads each agent's
declared slots and fills them with material of the right kind — which also
means a new or changed contract is exercised without editing the tests.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.connection import DatasetRef
from app.domain.input_contract import InputBinding, InputKind, InputOrigin
from app.domain.model import Effort, ModelSelection
from app.domain.run import RunRequest
from app.runtime.input_contracts import slots_for

CUSTOMERS = DatasetRef(
    connection_id="conn_demo", database="ADE_DEMO", schema_name="RETAIL", table="CUSTOMERS"
)
ORDERS = DatasetRef(
    connection_id="conn_demo", database="ADE_DEMO", schema_name="RETAIL", table="ORDERS"
)

# One sample file per kind, from the seeded workspace.
_SAMPLE_FILES: dict[InputKind, list[str]] = {
    InputKind.CODE_ARTIFACTS: [
        "warehouse-code/load_fct_orders.sql",
        "legacy/CUSTMAST.cpy",
    ],
    InputKind.TELEMETRY_EXPORT: ["telemetry/warehouse_metering.csv"],
    InputKind.POLICY_DOCUMENT: ["policies/sensitivity-taxonomy.md"],
}

_SAMPLE_TEXT = (
    "Onboard the retail source end to end and publish a certified customer-360 "
    "data product for the commercial team."
)


def bindings_for(agent_id: str, *, space_id: str = "space_samples") -> dict[str, InputBinding]:
    """Fill every required slot, and any optional slot we have material for."""
    bindings: dict[str, InputBinding] = {}
    for slot in slots_for(agent_id):
        if slot.kind is InputKind.DATABASE_OBJECTS:
            # Agent 18 compares two estates, so its two slots must not be the
            # same table or the comparison is trivially equal.
            dataset = ORDERS if slot.key == "target_objects" else CUSTOMERS
            bindings[slot.key] = InputBinding(
                slot_key=slot.key,
                origin=InputOrigin.CONNECTION,
                connection_id="conn_demo",
                datasets=[dataset.model_dump()],
            )
        elif slot.kind is InputKind.STRUCTURED_REQUEST:
            bindings[slot.key] = InputBinding(
                slot_key=slot.key, origin=InputOrigin.INLINE, text=_SAMPLE_TEXT
            )
        else:
            paths = _SAMPLE_FILES.get(slot.kind, [])
            bindings[slot.key] = InputBinding(
                slot_key=slot.key,
                origin=InputOrigin.SHARED_DRIVE,
                file_ids=[f"{space_id}::{p}" for p in paths],
            )
    return bindings


def request_for(
    agent_id: str,
    *,
    sample_rows: int = 50,
    override: bool = True,
    parameters: dict[str, object] | None = None,
) -> RunRequest:
    """A runnable request for one agent, satisfying its declared contract."""
    bindings = bindings_for(agent_id)
    datasets: list[DatasetRef] = []
    seen: set[str] = set()
    for binding in bindings.values():
        for raw in binding.datasets:
            dataset = DatasetRef.model_validate(raw)
            if dataset.fqn not in seen:
                seen.add(dataset.fqn)
                datasets.append(dataset)

    return RunRequest(
        agent_id=agent_id,
        connection_id="conn_demo",
        datasets=datasets,
        inputs=bindings,
        model=ModelSelection(model_id="claude-haiku-4-5", effort=Effort.LOW),
        parameters={"sample_rows": sample_rows, **(parameters or {})},
        override_dependency_gate=override,
        override_reason=(
            "Fleet-wide smoke test: each agent is exercised in isolation." if override else ""
        ),
    )


def sample_file_ids(*relative_paths: str, space_id: str = "space_samples") -> list[str]:
    return [f"{space_id}::{path}" for path in relative_paths]


def written_sample(root: Path, relative: str, content: str) -> str:
    """Add a file to a sample space mid-test and return its id."""
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"space_samples::{relative}"
