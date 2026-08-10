"""Factory and capability report for document spaces.

Mirrors the source-connector registry, including the honest capability report:
a space kind whose dependency is missing is listed as unavailable with the
reason, rather than being hidden or failing at run time.
"""

from __future__ import annotations

from pathlib import Path

from app.core.errors import NotFound
from app.domain.document import DocumentSpace, SpaceKind
from app.ports.document_provider import DocumentProvider

# Fields each kind needs, so the UI renders one form driven by data.
_FIELDS: dict[SpaceKind, list[str]] = {
    SpaceKind.UPLOAD: [],
    SpaceKind.SHAREPOINT: ["site_url", "tenant_id", "client_id", "client_secret"],
    SpaceKind.TEAMS: ["team_id", "channel_name", "tenant_id", "client_id", "client_secret"],
    SpaceKind.SHARED_DRIVE: ["root_path"],
    SpaceKind.OBJECT_STORE: ["bucket", "prefix", "region"],
}

_LABELS: dict[SpaceKind, str] = {
    SpaceKind.UPLOAD: "Upload",
    SpaceKind.SHAREPOINT: "SharePoint",
    SpaceKind.TEAMS: "Teams channel",
    SpaceKind.SHARED_DRIVE: "Shared drive",
    SpaceKind.OBJECT_STORE: "Object storage (S3)",
}

_NOTES: dict[SpaceKind, str] = {
    SpaceKind.UPLOAD: "Always available. Files uploaded from the workbench.",
    SpaceKind.SHAREPOINT: "A document library, over Microsoft Graph with read-only app credentials.",
    SpaceKind.TEAMS: "A channel's Files tab — a folder in the team's SharePoint library.",
    SpaceKind.SHARED_DRIVE: "Any path the server can read, including a mounted network share.",
    SpaceKind.OBJECT_STORE: "An S3 or S3-compatible bucket.",
}


def build_provider(space: DocumentSpace, *, upload_root: Path) -> DocumentProvider:
    from app.adapters.documents.filesystem import DirectoryProvider, UploadProvider
    from app.adapters.documents.microsoft_graph import SharePointProvider, TeamsProvider
    from app.adapters.documents.object_store import ObjectStoreProvider

    if space.kind is SpaceKind.UPLOAD:
        return UploadProvider(space, upload_root / space.id)
    if space.kind is SpaceKind.SHARED_DRIVE:
        if not space.root_path:
            raise NotFound(f"Space {space.id!r} has no root path.")
        return DirectoryProvider(space, Path(space.root_path))
    if space.kind is SpaceKind.SHAREPOINT:
        return SharePointProvider(space)
    if space.kind is SpaceKind.TEAMS:
        return TeamsProvider(space)
    if space.kind is SpaceKind.OBJECT_STORE:
        return ObjectStoreProvider(space)
    raise NotFound(f"No provider for space kind {space.kind!r}")


def capabilities() -> list[dict[str, object]]:
    """What each space kind needs, and whether its dependency is installed."""
    report: list[dict[str, object]] = []
    for kind in SpaceKind:
        available, detail = _dependency_status(kind)
        report.append(
            {
                "kind": kind.value,
                "label": _LABELS[kind],
                "note": _NOTES[kind],
                "fields": _FIELDS[kind],
                "dependency_available": available,
                "dependency_detail": detail,
            }
        )
    return report


def _dependency_status(kind: SpaceKind) -> tuple[bool, str]:
    if kind in {SpaceKind.SHAREPOINT, SpaceKind.TEAMS}:
        try:
            import requests  # noqa: F401
        except ImportError:
            return False, "Install with: pip install -e 'backend[sharepoint]'"
        return True, "requests installed"
    if kind is SpaceKind.OBJECT_STORE:
        try:
            import boto3  # noqa: F401
        except ImportError:
            return False, "Install with: pip install -e 'backend[aws]'"
        return True, "boto3 installed"
    return True, "No extra dependency"


def fields_for(kind: SpaceKind) -> list[str]:
    return _FIELDS[kind]
