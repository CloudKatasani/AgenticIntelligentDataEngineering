"""Health and fleet-level dashboard figures."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter

from app.api.deps import catalog, get_connection_repository, get_graph_service, get_run_repository, get_run_service, settings

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> dict[str, object]:
    service = catalog()
    graph = get_graph_service()
    return {
        "status": "ok",
        "app": settings().app_name,
        "environment": settings().environment,
        "agents_loaded": len(service.list_agents()),
        "graph_acyclic": not graph.find_cycles(),
        "provider": get_run_service().provider_status(),
        "specs_root": str(settings().specs_root),
    }


@router.get("/dashboard")
def dashboard() -> dict[str, object]:
    service = catalog()
    agents = service.list_agents()
    runs = get_run_repository().list(limit=500)

    by_domain = Counter(a.domain for a in agents)
    by_tier = Counter(a.tier.value for a in agents)
    run_status = Counter(r.status.value for r in runs)
    run_by_agent = Counter(r.agent_id for r in runs)

    return {
        "fleet": {
            "agents": len(agents),
            "core_agents": sum(1 for a in agents if a.core_original_scope),
            "by_domain": dict(by_domain),
            "by_tier": dict(by_tier),
            "requiring_approval": sum(1 for a in agents if a.requires_approval),
        },
        "activity": {
            "total_runs": len(runs),
            "by_status": dict(run_status),
            "total_cost_usd": round(sum(r.usage.cost_usd for r in runs), 4),
            "total_artifacts": sum(len(r.artifacts) for r in runs),
            "awaiting_approval": sum(1 for r in runs if r.status.value == "awaiting_approval"),
            "agents_exercised": len(run_by_agent),
            "recent": [
                {
                    "id": r.id,
                    "agent_id": r.agent_id,
                    "agent_name": r.agent_name,
                    "status": r.status.value,
                    "created_at": r.created_at,
                    "artifact_count": len(r.artifacts),
                }
                for r in runs[:8]
            ],
        },
        "connections": len(get_connection_repository().list()),
    }
