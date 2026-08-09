"""Fleet dependency graph: validation, ordering and readiness.

Design rule 2 says the hard-dependency graph is validated acyclic. The catalog
generator asserts that at generation time; this service re-asserts it at load
time, so a hand-edited spec cannot quietly introduce a cycle.
"""

from __future__ import annotations

from collections import defaultdict

from app.domain.agent import AgentSpec
from app.services.catalog_service import CatalogService


class GraphService:
    def __init__(self, catalog: CatalogService) -> None:
        self.catalog = catalog

    def nodes_and_edges(self) -> dict[str, object]:
        agents = self.catalog.list_agents()
        nodes = [
            {
                "id": a.id,
                "name": a.name,
                "domain": a.domain,
                "tier": a.tier.value,
                "core": a.core_original_scope,
            }
            for a in agents
        ]
        edges = []
        for agent in agents:
            for dep in agent.hard_dependencies:
                edges.append({"from": dep.agent_id, "to": agent.id, "kind": "hard"})
            for dep in agent.soft_dependencies:
                edges.append({"from": dep.agent_id, "to": agent.id, "kind": "soft"})
        return {"nodes": nodes, "edges": edges}

    def find_cycles(self) -> list[list[str]]:
        """Detect cycles in the hard-dependency graph.

        Returns an empty list for a valid catalog. Soft edges are excluded by
        design: the 13↔16 workflow seam is intentionally bidirectional as
        data-flow, and only the hard direction is modelled as an edge.
        """
        graph: dict[str, list[str]] = defaultdict(list)
        for agent in self.catalog.list_agents():
            for dep in agent.hard_dependencies:
                graph[dep.agent_id].append(agent.id)

        cycles: list[list[str]] = []
        WHITE, GREY, BLACK = 0, 1, 2
        colour: dict[str, int] = defaultdict(int)
        stack: list[str] = []

        def visit(node: str) -> None:
            colour[node] = GREY
            stack.append(node)
            for nxt in graph.get(node, []):
                if colour[nxt] == GREY:
                    cycles.append(stack[stack.index(nxt):] + [nxt])
                elif colour[nxt] == WHITE:
                    visit(nxt)
            stack.pop()
            colour[node] = BLACK

        for agent in self.catalog.list_agents():
            if colour[agent.id] == WHITE:
                visit(agent.id)
        return cycles

    def topological_order(self) -> list[str]:
        """Execution order honouring hard dependencies."""
        agents = self.catalog.list_agents()
        indegree: dict[str, int] = {a.id: len(a.hard_dependencies) for a in agents}
        dependents: dict[str, list[str]] = defaultdict(list)
        for agent in agents:
            for dep in agent.hard_dependencies:
                dependents[dep.agent_id].append(agent.id)

        ready = sorted([aid for aid, deg in indegree.items() if deg == 0])
        order: list[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for nxt in dependents.get(current, []):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
            ready.sort()
        return order

    def execution_plan_for(self, agent_id: str) -> list[AgentSpec]:
        """The agent plus every hard prerequisite, in runnable order."""
        needed: set[str] = set()

        def walk(current: str) -> None:
            if current in needed:
                return
            needed.add(current)
            for dep in self.catalog.get(current).hard_dependencies:
                walk(dep.agent_id)

        walk(str(agent_id).zfill(2))
        order = [aid for aid in self.topological_order() if aid in needed]
        return [self.catalog.get(aid) for aid in order]
