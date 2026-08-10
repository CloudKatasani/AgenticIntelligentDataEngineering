"""Serving worked examples, checked against the runtime that would produce them.

The risk with authored demo content is that it drifts: an agent's artifact
contract changes, the example still shows the old filenames, and a client is
shown something the product no longer does. So every example is validated
against the live catalog — the filenames it claims, the input kinds it uses —
and a mismatch is a test failure rather than a slide nobody checked.
"""

from __future__ import annotations

from app.core.errors import NotFound
from app.domain.canvas import WorkedExample
from app.runtime.canvas import all_examples
from app.runtime.input_contracts import slots_for
from app.services.catalog_service import CatalogService


class CanvasService:
    def __init__(self, catalog: CatalogService) -> None:
        self.catalog = catalog
        self._examples = all_examples()

    # ------------------------------------------------------------------ #

    def get(self, agent_id: str) -> dict[str, object]:
        example = self._examples.get(agent_id)
        if example is None:
            raise NotFound(f"No worked example for agent {agent_id!r}.")
        agent = self.catalog.get(agent_id)

        return {
            **example.model_dump(mode="json"),
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "domain": agent.domain,
                "tier": agent.tier.value,
                "tier_name": agent.tier_name,
                "purpose": agent.purpose,
                "requires_approval": agent.requires_approval,
                "core": agent.core_original_scope,
            },
            "slots": [
                {"key": s.key, "label": s.label, "kind": s.kind.value, "required": s.required}
                for s in slots_for(agent_id)
            ],
            "is_illustration": True,
            "illustration_note": (
                "A worked example, not a run record. The same configuration can be executed "
                "for real from the workbench — the artifact filenames below are the ones that "
                "run produces."
            ),
        }

    def index(self) -> dict[str, object]:
        """The fleet canvas: every example, grouped into the story's chapters."""
        agents = {a.id: a for a in self.catalog.list_agents()}
        chapters: dict[str, list[dict[str, object]]] = {}

        for agent_id, example in sorted(self._examples.items()):
            agent = agents.get(agent_id)
            entry = {
                "agent_id": agent_id,
                "agent_name": agent.name if agent else agent_id,
                "domain": agent.domain if agent else "",
                "tier": agent.tier.value if agent else "",
                "scenario": example.scenario,
                "input_kinds": sorted({e.kind for e in example.inputs}) or ["upstream_artifacts"],
                "input_labels": [e.label for e in example.inputs],
                "output_files": [a.filename for a in example.outputs],
                "upstream_count": len(example.upstream),
                "highlight": example.highlights[0] if example.highlights else "",
            }
            chapters.setdefault(example.chapter, []).append(entry)

        return {
            "story": {
                "title": "Meridian Retail Group — mainframe to certified data product",
                "premise": (
                    "A mainframe customer master and a legacy warehouse become a certified "
                    "customer-360 product on Snowflake. Every agent's example is set in this "
                    "one estate, so the 35 read end to end as a single migration."
                ),
                "estate": (
                    "The seeded demo warehouse (ADE_DEMO) and the seeded sample file "
                    "workspace — the same objects a live run would read."
                ),
            },
            "chapters": [
                {"title": title, "agents": entries}
                for title, entries in sorted(chapters.items())
            ],
            "total": len(self._examples),
        }

    # ------------------------------------------------------------------ #

    def validate(self) -> list[str]:
        """Where an example has drifted from the runtime it illustrates.

        Used by the tests. Returned as a list rather than raised so a single
        run reports every problem at once.
        """
        problems: list[str] = []
        agents = {a.id: a for a in self.catalog.list_agents()}

        for agent_id in agents:
            if agent_id not in self._examples:
                problems.append(f"agent {agent_id} has no worked example")

        for agent_id, example in self._examples.items():
            agent = agents.get(agent_id)
            if agent is None:
                problems.append(f"example {agent_id} has no matching agent")
                continue

            declared = {a.filename for a in agent.artifacts}
            shown = {a.filename for a in example.outputs}
            if shown != declared:
                problems.append(
                    f"agent {agent_id}: example shows {sorted(shown)}, "
                    f"the agent produces {sorted(declared)}"
                )

            sources = {a.filename: a.source for a in agent.artifacts}
            for artifact in example.outputs:
                expected = sources.get(artifact.filename)
                if expected and artifact.source != expected.value:
                    problems.append(
                        f"agent {agent_id}/{artifact.filename}: example says "
                        f"{artifact.source!r}, the contract says {expected.value!r}"
                    )

            slot_kinds = {s.kind.value for s in slots_for(agent_id)}
            for exhibit in example.inputs:
                if exhibit.kind not in slot_kinds:
                    problems.append(
                        f"agent {agent_id}: exhibit {exhibit.label!r} is {exhibit.kind!r}, "
                        f"which is not among its input slots {sorted(slot_kinds)}"
                    )

            if not slot_kinds and example.inputs:
                problems.append(
                    f"agent {agent_id} declares no input slots but the example shows inputs"
                )
        return problems
