"""The catalog must load every agent, and the graph must stay a DAG.

These assertions guard the invariants the whole product rests on: if a spec is
hand-edited into an inconsistent state, a test fails rather than a run
misbehaving in front of a client.
"""

from __future__ import annotations

from app.services.catalog_service import CatalogService
from app.services.graph_service import GraphService


def test_loads_the_whole_fleet(catalog: CatalogService) -> None:
    agents = catalog.list_agents()
    assert len(agents) == 35
    assert [a.id for a in agents] == [f"{i:02d}" for i in range(1, 36)]


def test_every_agent_has_a_runnable_contract(catalog: CatalogService) -> None:
    for agent in catalog.list_agents():
        assert agent.name, f"{agent.id} has no name"
        assert agent.purpose, f"{agent.id} has no purpose"
        assert agent.skill_markdown, f"{agent.id} has no SKILL.md"
        assert agent.artifacts, f"{agent.id} declares no artifacts"
        assert agent.acceptance_criteria, f"{agent.id} declares no acceptance criteria"
        filenames = [a.filename for a in agent.artifacts]
        assert len(filenames) == len(set(filenames)), f"{agent.id} has duplicate artifact filenames"


def test_dependencies_resolve_to_real_agents(catalog: CatalogService) -> None:
    ids = {a.id for a in catalog.list_agents()}
    for agent in catalog.list_agents():
        for dep in agent.hard_dependencies + agent.soft_dependencies:
            assert dep.agent_id in ids, f"{agent.id} depends on unknown agent {dep.agent_id}"
            assert dep.agent_id != agent.id, f"{agent.id} depends on itself"


def test_non_goals_name_a_real_owner_or_a_human(catalog: CatalogService) -> None:
    """`owned_by: null` in the catalog means the exclusion is human-owned."""
    ids = {a.id for a in catalog.list_agents()}
    human_owned = 0
    for agent in catalog.list_agents():
        for goal in agent.non_goals:
            if goal.human_owned:
                human_owned += 1
                assert goal.owner_name, f"{agent.id} human-owned exclusion has no description"
                continue
            assert goal.owned_by in ids, f"{agent.id} excludes work owned by unknown {goal.owned_by}"
    assert human_owned > 0, "expected some exclusions to be human-owned by design"


def test_hard_dependency_graph_is_acyclic(catalog: CatalogService) -> None:
    assert GraphService(catalog).find_cycles() == []


def test_topological_order_covers_the_fleet(catalog: CatalogService) -> None:
    graph = GraphService(catalog)
    order = graph.topological_order()
    assert len(order) == 35
    position = {agent_id: index for index, agent_id in enumerate(order)}
    for agent in catalog.list_agents():
        for dep in agent.hard_dependencies:
            assert position[dep.agent_id] < position[agent.id], (
                f"{dep.agent_id} must precede {agent.id}"
            )


def test_execution_plan_includes_transitive_prerequisites(catalog: CatalogService) -> None:
    plan = [spec.id for spec in GraphService(catalog).execution_plan_for("20")]
    # 20 needs 19 and 24; 19 and 24 both need 04.
    assert plan[-1] == "20"
    assert {"19", "24", "04"} <= set(plan)
    assert plan.index("04") < plan.index("19") < plan.index("20")


def test_regulated_tier_cap_applies_only_where_specified(catalog: CatalogService) -> None:
    capped = {a.id for a in catalog.list_agents() if a.regulated_tier_cap is not None}
    assert capped == {"02", "26", "27"}
    for agent_id in capped:
        agent = catalog.get(agent_id)
        assert agent.effective_tier(regulated=True).value == "L1"


def test_seams_are_reciprocal(catalog: CatalogService) -> None:
    """If A hands work to B, B's seam list shows it receiving from A."""
    for agent in catalog.list_agents():
        for goal in agent.non_goals:
            if goal.human_owned:
                continue
            counterpart = catalog.seams(goal.owned_by)
            assert any(
                seam["direction"] == "receives_from" and seam["counterpart_id"] == agent.id
                for seam in counterpart
            ), f"{goal.owned_by} does not show a seam back to {agent.id}"
