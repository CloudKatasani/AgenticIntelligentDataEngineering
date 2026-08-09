"""Sortable, human-legible identifiers."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone


def new_id(prefix: str) -> str:
    """Return e.g. ``run_20260809T143012_a1b2c3``.

    Lexicographic order matches chronological order, which keeps run listings
    sorted without a separate index.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{prefix}_{stamp}_{secrets.token_hex(3)}"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
