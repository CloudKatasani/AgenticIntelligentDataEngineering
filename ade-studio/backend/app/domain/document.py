"""File-shaped inputs: where they live and what one looks like.

Most of the fleet reads files rather than tables — legacy copybooks, metering
exports, entitlement matrices, query history. In a real estate those files are
rarely on the operator's laptop. They are in a SharePoint library, a Teams
channel, a mounted share, or object storage, and asking someone to download and
re-upload them is how a tool stops being used.

A ``DocumentSpace`` is a registered place files come from. A ``DocumentRef`` is
one file inside one, resolved to bytes only when a run needs it.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, SecretStr


class SpaceKind(str, Enum):
    UPLOAD = "upload"
    """Files uploaded through the workbench. Always available."""

    SHAREPOINT = "sharepoint"
    TEAMS = "teams"
    """A Teams channel — backed by the team's SharePoint document library."""

    SHARED_DRIVE = "shared_drive"
    """A mounted network share or any path the server can read."""

    OBJECT_STORE = "object_store"
    """S3 or an S3-compatible bucket."""


class DocumentSpace(BaseModel):
    """A registered location that files can be read from."""

    id: str
    name: str
    kind: SpaceKind
    owner: str = ""
    regulated: bool = False
    """Same meaning as on a database source: caps the tier for agents 02/26/27."""

    # SharePoint and Teams (Microsoft Graph).
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: SecretStr | None = None
    site_url: str | None = None
    """e.g. https://contoso.sharepoint.com/sites/DataPlatform"""

    drive_id: str | None = None
    team_id: str | None = None
    channel_name: str | None = None

    # Shared drive.
    root_path: str | None = None

    # Object store.
    bucket: str | None = None
    prefix: str = ""
    region: str | None = None

    extra: dict[str, str] = Field(default_factory=dict)
    created_at: str = ""

    def redacted(self) -> dict[str, object]:
        payload = self.model_dump(mode="json", exclude={"client_secret"})
        payload["has_client_secret"] = self.client_secret is not None
        return payload


class DocumentRef(BaseModel):
    """One file in a space, as listed by a provider."""

    id: str
    """Opaque and provider-specific: ``<space_id>::<path-or-item-id>``."""

    space_id: str
    name: str
    path: str = ""
    size_bytes: int = 0
    modified_at: str = ""
    is_folder: bool = False
    content_type: str = ""

    @property
    def extension(self) -> str:
        _, _, suffix = self.name.rpartition(".")
        return f".{suffix.lower()}" if suffix and suffix != self.name else ""


class DocumentContent(BaseModel):
    """A fetched file. ``text`` is decoded lazily by the reader, not here."""

    ref: DocumentRef
    data: bytes

    model_config = {"arbitrary_types_allowed": True}
