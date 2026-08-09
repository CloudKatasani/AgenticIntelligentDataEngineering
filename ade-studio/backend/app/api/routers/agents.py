"""Agent catalog, dependency graph and per-agent detail."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import catalog, get_graph_service
from app.services.model_registry import recommend_for

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def list_agents() -> dict[str, object]:
    service = catalog()
    agents = service.list_agents()
    return {
        "count": len(agents),
        "domains": service.domains(),
        "agents": [
            {
                "id": a.id,
                "slug": a.slug,
                "name": a.name,
                "domain": a.domain,
                "tier": a.tier.value,
                "tier_name": a.tier_name,
                "core_original_scope": a.core_original_scope,
                "purpose": a.purpose,
                "requires_dataset": a.requires_dataset,
                "requires_approval": a.requires_approval,
                "hard_dependencies": [d.model_dump() for d in a.hard_dependencies],
                "soft_dependencies": [d.model_dump() for d in a.soft_dependencies],
                "artifact_count": len(a.artifacts),
                "recommended_model": recommend_for(a),
            }
            for a in agents
        ],
    }


@router.get("/{agent_id}")
def get_agent(agent_id: str) -> dict[str, object]:
    service = catalog()
    agent = service.get(agent_id)
    payload = agent.model_dump(mode="json")
    payload["recommended_model"] = recommend_for(agent)
    payload["dependents"] = [
        {"id": d.id, "name": d.name, "domain": d.domain} for d in service.dependents_of(agent.id)
    ]
    payload["seams"] = service.seams(agent.id)
    payload["execution_plan"] = [
        {"id": s.id, "name": s.name, "tier": s.tier.value}
        for s in get_graph_service().execution_plan_for(agent.id)
    ]
    return payload


@router.get("/{agent_id}/artifacts")
def get_agent_artifacts(agent_id: str) -> dict[str, object]:
    agent = catalog().get(agent_id)
    return {"agent_id": agent.id, "artifacts": [a.model_dump() for a in agent.artifacts]}
