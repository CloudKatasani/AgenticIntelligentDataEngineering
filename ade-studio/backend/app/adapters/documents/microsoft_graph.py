"""SharePoint document libraries and Teams channel files, over Microsoft Graph.

Teams channel files are not a separate storage system: a channel's Files tab is
a folder in the team's SharePoint document library. So both spaces use the same
Graph drive API, and the only difference is how the drive is located — a site
URL for SharePoint, a team and channel name for Teams.

Authentication is client credentials, which is what an unattended service gets.
The app never sees a user's token, and the permission it needs is a read-only
one (``Sites.Read.All`` / ``Files.Read.All``): this whole product is read-only
by construction, and the credential should agree with that.

``requests`` is an optional dependency. Without it the space registers, reports
itself unreachable with the reason, and nothing else in the app fails — the
same treatment the database drivers get.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote, urlparse

from app.core.errors import ConnectionFailed, NotFound
from app.domain.document import DocumentContent, DocumentRef, DocumentSpace
from app.ports.document_provider import DocumentProvider

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "https://graph.microsoft.com/.default"

MAX_FILE_BYTES = 32 * 1024 * 1024


def _requests() -> Any:
    try:
        import requests
    except ImportError as exc:  # pragma: no cover — exercised by available()
        raise ConnectionFailed(
            "The 'requests' package is required for SharePoint and Teams. "
            "Install it with: pip install -e 'backend[sharepoint]'"
        ) from exc
    return requests


class GraphProvider(DocumentProvider):
    """Shared Graph plumbing. Subclasses only resolve the drive."""

    kind_label = "microsoft-graph"

    def __init__(self, space: DocumentSpace) -> None:
        super().__init__(space)
        self._token: str = ""
        self._token_expires_at: float = 0.0
        self._drive_id: str = space.drive_id or ""

    # ------------------------------------------------------------------ #

    def available(self) -> tuple[bool, str]:
        try:
            _requests()
        except ConnectionFailed as exc:
            return False, str(exc)

        missing = [
            name
            for name, value in (
                ("tenant ID", self.space.tenant_id),
                ("client ID", self.space.client_id),
                ("client secret", self.space.client_secret),
            )
            if not value
        ]
        if missing:
            return False, f"Missing {', '.join(missing)}."
        try:
            self._resolve_drive()
        except Exception as exc:  # noqa: BLE001 — surfaced to the operator verbatim
            return False, str(exc)
        return True, f"Connected to {self.space.name}"

    def _access_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token

        requests = _requests()
        secret = self.space.client_secret
        response = requests.post(
            f"https://login.microsoftonline.com/{self.space.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.space.client_id,
                "client_secret": secret.get_secret_value() if secret else "",
                "grant_type": "client_credentials",
                "scope": SCOPE,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise ConnectionFailed(
                f"Microsoft identity platform rejected the credentials "
                f"({response.status_code}). {response.text[:200]}"
            )
        payload = response.json()
        self._token = payload["access_token"]
        # Refresh a minute early rather than discovering expiry mid-run.
        self._token_expires_at = time.monotonic() + max(60, int(payload.get("expires_in", 3600)) - 60)
        return self._token

    def _get(self, url: str, **kwargs: Any) -> Any:
        requests = _requests()
        response = requests.get(
            url if url.startswith("http") else f"{GRAPH}{url}",
            headers={"Authorization": f"Bearer {self._access_token()}"},
            timeout=60,
            **kwargs,
        )
        if response.status_code == 404:
            raise NotFound(f"Graph returned 404 for {url}")
        if response.status_code >= 400:
            raise ConnectionFailed(f"Graph error {response.status_code}: {response.text[:200]}")
        return response

    def _resolve_drive(self) -> str:
        raise NotImplementedError

    # ------------------------------------------------------------------ #

    def _root(self) -> str:
        return ""

    def list(self, path: str = "") -> list[DocumentRef]:
        drive = self._resolve_drive()
        full = "/".join(p for p in (self._root(), path.strip("/")) if p)
        if full:
            url = f"/drives/{drive}/root:/{quote(full)}:/children"
        else:
            url = f"/drives/{drive}/root/children"
        items = self._get(url).json().get("value", [])
        return [self._to_ref(item, full) for item in items]

    def fetch(self, ref_id: str) -> DocumentContent:
        drive = self._resolve_drive()
        _, _, path = ref_id.partition("::")
        meta = self._get(f"/drives/{drive}/root:/{quote(path)}").json()
        size = int(meta.get("size", 0))
        if size > MAX_FILE_BYTES:
            raise ConnectionFailed(
                f"{meta.get('name')} is {size / 1_048_576:.0f} MB; the limit for a run input "
                f"is {MAX_FILE_BYTES // 1_048_576} MB."
            )
        data = self._get(f"/drives/{drive}/root:/{quote(path)}:/content").content
        return DocumentContent(ref=self._to_ref(meta, str(path).rsplit("/", 1)[0]), data=data)

    def search(self, query: str) -> list[DocumentRef]:
        if not query.strip():
            return []
        drive = self._resolve_drive()
        items = self._get(f"/drives/{drive}/root/search(q='{quote(query)}')").json().get("value", [])
        return [self._to_ref(item, "") for item in items[:100]]

    def _to_ref(self, item: dict[str, Any], parent: str) -> DocumentRef:
        name = item.get("name", "")
        path = f"{parent}/{name}".strip("/") if parent else name
        return DocumentRef(
            id=f"{self.space.id}::{path}",
            space_id=self.space.id,
            name=name,
            path=path,
            size_bytes=int(item.get("size", 0)),
            modified_at=item.get("lastModifiedDateTime", ""),
            is_folder="folder" in item,
            content_type=item.get("file", {}).get("mimeType", ""),
        )


class SharePointProvider(GraphProvider):
    kind_label = "sharepoint"

    def _resolve_drive(self) -> str:
        if self._drive_id:
            return self._drive_id
        if not self.space.site_url:
            raise ConnectionFailed("A SharePoint site URL is required.")

        parsed = urlparse(self.space.site_url)
        host, site_path = parsed.netloc, parsed.path.strip("/")
        if not host:
            raise ConnectionFailed(f"Could not read a hostname from {self.space.site_url!r}.")

        site = self._get(f"/sites/{host}:/{site_path}" if site_path else f"/sites/{host}").json()
        drive = self._get(f"/sites/{site['id']}/drive").json()
        self._drive_id = drive["id"]
        return self._drive_id


class TeamsProvider(GraphProvider):
    """A Teams channel's Files tab — a folder in the team's SharePoint drive."""

    kind_label = "teams"

    def __init__(self, space: DocumentSpace) -> None:
        super().__init__(space)
        self._folder: str = ""

    def _resolve_drive(self) -> str:
        if self._drive_id and self._folder:
            return self._drive_id
        if not self.space.team_id:
            raise ConnectionFailed("A team ID is required.")

        if not self._drive_id:
            self._drive_id = self._get(f"/groups/{self.space.team_id}/drive").json()["id"]

        # The channel's folder is named after the channel, but the display name
        # can drift from the folder name, so ask Graph for the real one.
        if self.space.channel_name and not self._folder:
            channels = self._get(f"/teams/{self.space.team_id}/channels").json().get("value", [])
            match = next(
                (c for c in channels if c.get("displayName") == self.space.channel_name), None
            )
            if not match:
                available = ", ".join(c.get("displayName", "?") for c in channels) or "none"
                raise NotFound(
                    f"No channel named {self.space.channel_name!r} in this team. Found: {available}"
                )
            folder = self._get(
                f"/teams/{self.space.team_id}/channels/{match['id']}/filesFolder"
            ).json()
            self._folder = folder.get("name", self.space.channel_name)
        return self._drive_id

    def _root(self) -> str:
        self._resolve_drive()
        return self._folder
