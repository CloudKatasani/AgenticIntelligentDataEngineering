"""Worked examples, checked against the runtime that would produce them.

Authored demo content drifts. An agent's artifact contract changes, the example
keeps showing the old filenames, and six months later a client is shown
something the product does not do. These tests make that a build failure rather
than a discovery in front of a customer.
"""

from __future__ import annotations

import json

import pytest
import yaml

from app.runtime.canvas import all_examples
from app.runtime.input_contracts import slots_for
from app.services.canvas_service import CanvasService
from app.services.catalog_service import CatalogService

AGENT_IDS = [f"{i:02d}" for i in range(1, 36)]


@pytest.fixture(scope="module")
def canvas(catalog: CatalogService) -> CanvasService:
    return CanvasService(catalog)


# ---------------------------------------------------------------------- #
# Coverage and drift
# ---------------------------------------------------------------------- #


def test_every_agent_has_a_worked_example() -> None:
    assert set(all_examples()) == set(AGENT_IDS)


def test_no_example_has_drifted_from_the_runtime(canvas: CanvasService) -> None:
    """The whole point of the validator.

    It already caught one real drift while this was being written: agent 07
    declares three artifacts and the example showed two.
    """
    assert canvas.validate() == []


@pytest.mark.parametrize("agent_id", AGENT_IDS)
def test_outputs_match_the_agents_real_artifact_contract(
    agent_id: str, canvas: CanvasService, catalog: CatalogService
) -> None:
    """A client shown `profile.json` must get `profile.json` when they run it."""
    example = all_examples()[agent_id]
    assert {a.filename for a in example.outputs} == {
        a.filename for a in catalog.get(agent_id).artifacts
    }


@pytest.mark.parametrize("agent_id", AGENT_IDS)
def test_deterministic_artifacts_are_labelled_as_such(
    agent_id: str, catalog: CatalogService
) -> None:
    """"Which numbers did a model produce" is the first question a serious
    buyer asks. The example must answer it the same way the run record does."""
    declared = {a.filename: a.source.value for a in catalog.get(agent_id).artifacts}
    for artifact in all_examples()[agent_id].outputs:
        assert artifact.source == declared[artifact.filename]


@pytest.mark.parametrize("agent_id", AGENT_IDS)
def test_input_exhibits_match_the_agents_declared_slots(agent_id: str) -> None:
    """An example cannot show an input the agent would never be offered."""
    kinds = {slot.kind.value for slot in slots_for(agent_id)}
    for exhibit in all_examples()[agent_id].inputs:
        assert exhibit.kind in kinds, f"agent {agent_id}: {exhibit.kind} is not a declared slot"


def test_upstream_fed_agents_show_no_operator_input() -> None:
    """Agents 09 and 11 ask for nothing. Their examples must not imply otherwise."""
    for agent_id in ("09", "11"):
        example = all_examples()[agent_id]
        assert example.inputs == []
        assert example.upstream, f"agent {agent_id} should show what arrives from upstream"


# ---------------------------------------------------------------------- #
# Content quality — the things that make it a demo rather than a stub
# ---------------------------------------------------------------------- #


@pytest.mark.parametrize("agent_id", AGENT_IDS)
def test_every_artifact_body_has_real_content(agent_id: str) -> None:
    """A demo dies on a placeholder. 200 characters is a low bar that a stub
    like "TODO: example output" cannot clear."""
    for artifact in all_examples()[agent_id].outputs:
        assert len(artifact.body) >= 200, f"{agent_id}/{artifact.filename} is too thin"
        assert "TODO" not in artifact.body
        assert "lorem ipsum" not in artifact.body.lower()


@pytest.mark.parametrize("agent_id", AGENT_IDS)
def test_every_example_says_what_to_point_at(agent_id: str) -> None:
    example = all_examples()[agent_id]
    assert example.scenario and len(example.scenario) > 80
    assert example.highlights, f"agent {agent_id} has nothing for a presenter to point at"
    assert example.chapter


@pytest.mark.parametrize("agent_id", AGENT_IDS)
def test_json_artifact_bodies_are_valid_json(agent_id: str) -> None:
    """Malformed JSON on a demo screen is the kind of detail a data engineer
    notices immediately and never stops noticing."""
    for artifact in all_examples()[agent_id].outputs:
        if artifact.format == "json":
            json.loads(artifact.body)


@pytest.mark.parametrize("agent_id", AGENT_IDS)
def test_yaml_artifact_bodies_are_valid_yaml(agent_id: str) -> None:
    for artifact in all_examples()[agent_id].outputs:
        if artifact.format == "yaml":
            assert yaml.safe_load(artifact.body) is not None


@pytest.mark.parametrize("agent_id", AGENT_IDS)
def test_examples_use_the_seeded_estate(agent_id: str) -> None:
    """One story across one estate. An example naming a table that does not
    exist breaks the "run it for real" promise the canvas makes."""
    example = all_examples()[agent_id]
    text = " ".join(
        [example.scenario]
        + [e.label + e.body for e in example.inputs]
        + [a.body for a in example.outputs]
    )
    known = (
        "ADE_DEMO", "RETAIL", "FINANCE", "LEGACY", "ANALYTICS", "RAW", "AUDIT", "REF",
        "Meridian", "CUST_MAST", "sample artifacts", "Sample artifacts", "policies/",
        "telemetry/", "legacy/", "warehouse-code/",
    )
    assert any(token in text for token in known), f"agent {agent_id} is not set in the estate"


def test_handoffs_name_another_agent_or_a_human() -> None:
    """Non-overlapping scope is the catalog's first design rule. Every refusal
    must say who owns the work instead."""
    for agent_id, example in all_examples().items():
        for handoff in example.handoffs:
            assert "→" in handoff, f"agent {agent_id}: {handoff!r} names no owner"


# ---------------------------------------------------------------------- #
# The served payload
# ---------------------------------------------------------------------- #


def test_the_canvas_is_labelled_an_illustration(canvas: CanvasService) -> None:
    """Presenting authored content as system output would undo the thing this
    product is selling."""
    payload = canvas.get("01")
    assert payload["is_illustration"] is True
    assert "not a run record" in str(payload["illustration_note"])


def test_the_fleet_index_groups_into_chapters(canvas: CanvasService) -> None:
    index = canvas.index()
    assert index["total"] == 35
    chapters = index["chapters"]
    assert len(chapters) == 7
    assert sum(len(c["agents"]) for c in chapters) == 35


def test_an_agent_payload_carries_its_live_catalog_facts(canvas: CanvasService) -> None:
    """The tier shown beside the example is read from the catalog, not authored
    into the example — so it cannot disagree with the workbench."""
    payload = canvas.get("08")
    assert payload["agent"]["tier"] == "L0"
    assert payload["agent"]["requires_approval"] is True


def test_an_unknown_agent_is_a_clean_not_found(canvas: CanvasService) -> None:
    from app.core.errors import NotFound

    with pytest.raises(NotFound):
        canvas.get("99")
