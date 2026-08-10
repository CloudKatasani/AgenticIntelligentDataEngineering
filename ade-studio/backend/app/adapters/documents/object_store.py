"""S3 and S3-compatible buckets.

Folders do not exist in object storage, so listing uses a delimiter query and
presents common prefixes as folders. That is a presentation choice, not a
pretence: the operator thinks in folders, and the alternative is a flat list of
several thousand keys.
"""

from __future__ import annotations

from typing import Any

from app.core.errors import ConnectionFailed, NotFound
from app.domain.document import DocumentContent, DocumentRef, DocumentSpace
from app.ports.document_provider import DocumentProvider

MAX_FILE_BYTES = 32 * 1024 * 1024


class ObjectStoreProvider(DocumentProvider):
    kind_label = "object_store"

    def __init__(self, space: DocumentSpace, client: Any | None = None) -> None:
        super().__init__(space)
        self._client = client

    def client(self) -> Any:
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:
                raise ConnectionFailed(
                    "boto3 is required for object storage. "
                    "Install it with: pip install -e 'backend[aws]'"
                ) from exc
            self._client = boto3.client("s3", region_name=self.space.region or None)
        return self._client

    def available(self) -> tuple[bool, str]:
        if not self.space.bucket:
            return False, "A bucket name is required."
        try:
            self.client().head_bucket(Bucket=self.space.bucket)
        except ConnectionFailed as exc:
            return False, str(exc)
        except Exception as exc:  # noqa: BLE001 — the operator wants the real reason
            return False, f"Cannot reach s3://{self.space.bucket}: {exc}"
        return True, f"Connected to s3://{self.space.bucket}"

    def _key(self, path: str) -> str:
        prefix = self.space.prefix.strip("/")
        parts = [p for p in (prefix, path.strip("/")) if p]
        return "/".join(parts)

    def list(self, path: str = "") -> list[DocumentRef]:
        prefix = self._key(path)
        if prefix:
            prefix += "/"
        response = self.client().list_objects_v2(
            Bucket=self.space.bucket, Prefix=prefix, Delimiter="/", MaxKeys=1000
        )
        base = self.space.prefix.strip("/")

        def relative(key: str) -> str:
            return key[len(base) :].strip("/") if base and key.startswith(base) else key

        refs: list[DocumentRef] = []
        for entry in response.get("CommonPrefixes", []):
            key = entry["Prefix"].rstrip("/")
            refs.append(
                DocumentRef(
                    id=f"{self.space.id}::{relative(key)}",
                    space_id=self.space.id,
                    name=key.rsplit("/", 1)[-1],
                    path=relative(key),
                    is_folder=True,
                )
            )
        for entry in response.get("Contents", []):
            key = entry["Key"]
            if key.endswith("/"):
                continue
            refs.append(
                DocumentRef(
                    id=f"{self.space.id}::{relative(key)}",
                    space_id=self.space.id,
                    name=key.rsplit("/", 1)[-1],
                    path=relative(key),
                    size_bytes=int(entry.get("Size", 0)),
                    modified_at=entry["LastModified"].isoformat() if entry.get("LastModified") else "",
                )
            )
        return refs

    def fetch(self, ref_id: str) -> DocumentContent:
        _, _, path = ref_id.partition("::")
        key = self._key(path)
        try:
            response = self.client().get_object(Bucket=self.space.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            raise NotFound(f"No object s3://{self.space.bucket}/{key}: {exc}") from exc

        size = int(response.get("ContentLength", 0))
        if size > MAX_FILE_BYTES:
            raise ConnectionFailed(
                f"{key} is {size / 1_048_576:.0f} MB; the limit for a run input is "
                f"{MAX_FILE_BYTES // 1_048_576} MB."
            )
        return DocumentContent(
            ref=DocumentRef(
                id=ref_id,
                space_id=self.space.id,
                name=key.rsplit("/", 1)[-1],
                path=path,
                size_bytes=size,
                content_type=response.get("ContentType", ""),
            ),
            data=response["Body"].read(),
        )
