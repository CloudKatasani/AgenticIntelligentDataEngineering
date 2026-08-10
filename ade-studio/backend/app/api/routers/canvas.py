"""Worked examples: what goes into each agent, and what comes out."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_canvas_service

router = APIRouter(prefix="/api/canvas", tags=["canvas"])


@router.get("")
def fleet_canvas() -> dict[str, object]:
    """Every agent's example, grouped into the story's chapters."""
    return get_canvas_service().index()


@router.get("/{agent_id}")
def agent_canvas(agent_id: str) -> dict[str, object]:
    """One agent's worked example: exhibits in, artifacts out."""
    return get_canvas_service().get(agent_id)
