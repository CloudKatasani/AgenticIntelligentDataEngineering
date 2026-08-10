"""Providers backed by a directory the server can read.

Two spaces share this implementation because they are the same mechanism with
different intent: ``upload`` is a managed directory the app writes to, and
``shared_drive`` is a path someone else owns and the app only reads.
"""

from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import ConnectionFailed, NotFound
from app.domain.document import DocumentContent, DocumentRef, DocumentSpace
from app.ports.document_provider import DocumentProvider

MAX_FILE_BYTES = 32 * 1024 * 1024
"""Refused above this. A run reads files into a prompt; a 200 MB parquet dump
is not a prompt input, and failing at selection time is kinder than failing
after the operator has waited for a run."""


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


class DirectoryProvider(DocumentProvider):
    """Lists and fetches files beneath a single root."""

    kind_label = "directory"

    def __init__(self, space: DocumentSpace, root: Path) -> None:
        super().__init__(space)
        self.root = root

    def available(self) -> tuple[bool, str]:
        if not self.root.exists():
            return False, f"Path not found: {self.root}"
        if not self.root.is_dir():
            return False, f"Not a directory: {self.root}"
        return True, f"Reading {self.root}"

    def _resolve(self, relative: str) -> Path:
        """Resolve a caller-supplied path inside the root, or refuse.

        The path arrives from an HTTP request, so ``../../etc/passwd`` is a
        thing that will eventually be tried. Resolving both sides and checking
        containment is the check that actually holds, rather than string
        matching on ``..``.
        """
        root = self.root.resolve()
        candidate = (root / relative.lstrip("/")).resolve() if relative else root
        if candidate != root and root not in candidate.parents:
            raise NotFound(f"Path outside the space: {relative!r}")
        return candidate

    def list(self, path: str = "") -> list[DocumentRef]:
        target = self._resolve(path)
        if not target.is_dir():
            raise NotFound(f"Not a folder: {path!r}")

        refs: list[DocumentRef] = []
        for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if entry.name.startswith("."):
                continue
            relative = str(entry.relative_to(self.root.resolve()))
            stat = entry.stat()
            refs.append(
                DocumentRef(
                    id=f"{self.space.id}::{relative}",
                    space_id=self.space.id,
                    name=entry.name,
                    path=relative,
                    size_bytes=0 if entry.is_dir() else stat.st_size,
                    modified_at=_iso(stat.st_mtime),
                    is_folder=entry.is_dir(),
                    content_type=mimetypes.guess_type(entry.name)[0] or "",
                )
            )
        return refs

    def fetch(self, ref_id: str) -> DocumentContent:
        _, _, relative = ref_id.partition("::")
        target = self._resolve(relative)
        if not target.is_file():
            raise NotFound(f"No file {relative!r}")
        size = target.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ConnectionFailed(
                f"{target.name} is {size / 1_048_576:.0f} MB; the limit for a run input is "
                f"{MAX_FILE_BYTES // 1_048_576} MB."
            )
        return DocumentContent(
            ref=DocumentRef(
                id=ref_id,
                space_id=self.space.id,
                name=target.name,
                path=relative,
                size_bytes=size,
                modified_at=_iso(target.stat().st_mtime),
                content_type=mimetypes.guess_type(target.name)[0] or "",
            ),
            data=target.read_bytes(),
        )

    def search(self, query: str) -> list[DocumentRef]:
        needle = query.lower().strip()
        if not needle:
            return []
        root = self.root.resolve()
        matches: list[DocumentRef] = []
        for entry in root.rglob("*"):
            if len(matches) >= 100:
                break
            if entry.is_dir() or entry.name.startswith("."):
                continue
            if needle not in entry.name.lower():
                continue
            relative = str(entry.relative_to(root))
            stat = entry.stat()
            matches.append(
                DocumentRef(
                    id=f"{self.space.id}::{relative}",
                    space_id=self.space.id,
                    name=entry.name,
                    path=relative,
                    size_bytes=stat.st_size,
                    modified_at=_iso(stat.st_mtime),
                    content_type=mimetypes.guess_type(entry.name)[0] or "",
                )
            )
        return matches


class UploadProvider(DirectoryProvider):
    """The managed upload area. Creates its root rather than reporting it missing."""

    kind_label = "upload"

    def available(self) -> tuple[bool, str]:
        self.root.mkdir(parents=True, exist_ok=True)
        count = sum(1 for p in self.root.rglob("*") if p.is_file())
        return True, f"{count} uploaded file{'' if count == 1 else 's'}"

    def store(self, filename: str, data: bytes) -> DocumentRef:
        """Save an uploaded file, never letting the client choose the path.

        Only the basename is kept, so an upload named ``../../app/main.py``
        lands as ``main.py`` in the upload area like anything else.
        """
        safe = Path(filename).name or "upload.bin"
        self.root.mkdir(parents=True, exist_ok=True)

        target = self.root / safe
        stem, suffix, index = target.stem, target.suffix, 1
        while target.exists():
            target = self.root / f"{stem}-{index}{suffix}"
            index += 1

        target.write_bytes(data)
        stat = target.stat()
        return DocumentRef(
            id=f"{self.space.id}::{target.name}",
            space_id=self.space.id,
            name=target.name,
            path=target.name,
            size_bytes=stat.st_size,
            modified_at=_iso(stat.st_mtime),
            content_type=mimetypes.guess_type(target.name)[0] or "",
        )
