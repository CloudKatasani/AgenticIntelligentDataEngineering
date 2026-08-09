"""Model catalog and per-agent recommendation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import catalog, get_run_service
from app.services.model_registry import list_models, recommend_for

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
def get_models() -> dict[str, object]:
    return {
        "models": [m.model_dump() for m in list_models()],
        "effort_levels": [
            {"value": "low", "label": "Low", "note": "Short, scoped tasks; lowest cost and latency."},
            {"value": "medium", "label": "Medium", "note": "Cost-conscious default."},
            {"value": "high", "label": "High", "note": "Recommended for most fleet work."},
            {"value": "xhigh", "label": "Extra high", "note": "Best for hard coding and agentic tasks."},
            {"value": "max", "label": "Max", "note": "Correctness over cost; can overthink simple work."},
        ],
        "provider": get_run_service().provider_status(),
    }


@router.get("/recommendation/{agent_id}")
def get_recommendation(agent_id: str) -> dict[str, object]:
    agent = catalog().get(agent_id)
    return {"agent_id": agent.id, **recommend_for(agent)}
