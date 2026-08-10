"""Fleet observability and FinOps."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import get_observability_service, get_run_repository

router = APIRouter(prefix="/api/observability", tags=["observability"])


@router.get("")
def snapshot(window_days: int = Query(30, ge=1, le=365)) -> dict[str, object]:
    """Portfolio coverage, per-agent usage, spend and adoption in one payload.

    One request rather than five: the page is a single screen, the journal is
    read once to compute all of it, and splitting it would mean re-reading the
    same runs per section for no benefit.
    """
    runs = get_run_repository().list(limit=5000)
    return get_observability_service().snapshot(runs, window_days=window_days)
