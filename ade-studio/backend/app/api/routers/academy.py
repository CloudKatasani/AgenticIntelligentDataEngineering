"""Academy: fleet-level curriculum and per-agent lessons."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_academy_service

router = APIRouter(prefix="/api/academy", tags=["academy"])


@router.get("")
def overview() -> dict[str, object]:
    return get_academy_service().overview()


@router.get("/paths")
def paths() -> dict[str, object]:
    return {"paths": get_academy_service().learning_paths()}


@router.get("/agents/{agent_id}")
def lesson(agent_id: str) -> dict[str, object]:
    return get_academy_service().lesson(agent_id)
