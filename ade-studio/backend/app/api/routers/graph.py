"""Fleet dependency graph."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import catalog, get_graph_service

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("")
def get_graph() -> dict[str, object]:
    service = get_graph_service()
    data = service.nodes_and_edges()
    data["topological_order"] = service.topological_order()
    data["cycles"] = service.find_cycles()
    data["acyclic"] = not data["cycles"]
    return data


@router.get("/mermaid")
def get_mermaid() -> dict[str, str]:
    """Render the graph as Mermaid, grouped by domain like the catalog's own diagram."""
    service = catalog()
    by_domain: dict[str, list[str]] = {}
    for agent in service.list_agents():
        label = agent.name.replace('"', "'")
        by_domain.setdefault(agent.domain, []).append(f'    A{agent.id}["{agent.id} {label}"]')

    lines = ["graph TD"]
    for domain, nodes in by_domain.items():
        lines.append(f"  subgraph {domain.replace('-', '_')}")
        lines.extend(nodes)
        lines.append("  end")
    for agent in service.list_agents():
        for dep in agent.hard_dependencies:
            lines.append(f"  A{dep.agent_id} --> A{agent.id}")
        for dep in agent.soft_dependencies:
            lines.append(f"  A{dep.agent_id} -.-> A{agent.id}")
    return {"mermaid": "\n".join(lines)}
