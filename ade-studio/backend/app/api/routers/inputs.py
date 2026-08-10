"""Input contracts, document spaces, browsing and upload."""

from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile
from pydantic import BaseModel, Field, SecretStr

from app.adapters.documents.registry import capabilities, fields_for
from app.api.deps import catalog, get_input_service, get_space_repository
from app.core.errors import NotFound, ValidationFailed
from app.core.ids import new_id, utcnow_iso
from app.domain.document import DocumentSpace, SpaceKind
from app.runtime.input_contracts import primary_kind, slots_for

router = APIRouter(prefix="/api/inputs", tags=["inputs"])

KIND_LABELS: dict[str, str] = {
    "database_objects": "Database objects",
    "code_artifacts": "Code and ETL artifacts",
    "telemetry_export": "Telemetry export",
    "policy_document": "Policy document",
    "structured_request": "Written request",
    "upstream_artifacts": "Upstream artifacts only",
}


@router.get("/contract/{agent_id}")
def input_contract(agent_id: str) -> dict[str, object]:
    """What this agent needs from the operator, and where it may come from."""
    agent = catalog().get(agent_id)
    slots = slots_for(agent_id)
    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "primary_kind": primary_kind(agent_id),
        "primary_kind_label": KIND_LABELS.get(primary_kind(agent_id), primary_kind(agent_id)),
        "upstream_only": not slots,
        "upstream_note": (
            "This agent takes no direct input. Everything it needs is produced by upstream "
            "agents and arrives through the dependency gate."
            if not slots
            else ""
        ),
        "slots": [
            {
                **slot.model_dump(mode="json"),
                "kind_label": KIND_LABELS.get(slot.kind.value, slot.kind.value),
                "accepts_files": slot.accepts_files,
            }
            for slot in slots
        ],
    }


@router.get("/contracts")
def all_contracts() -> dict[str, object]:
    """Every agent's headline input kind, for the fleet view."""
    return {
        "agents": [
            {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "domain": agent.domain,
                "primary_kind": primary_kind(agent.id),
                "primary_kind_label": KIND_LABELS.get(
                    primary_kind(agent.id), primary_kind(agent.id)
                ),
                "required_slots": [s.label for s in slots_for(agent.id) if s.required],
                "optional_slots": [s.label for s in slots_for(agent.id) if not s.required],
            }
            for agent in catalog().list_agents()
        ],
        "kinds": KIND_LABELS,
    }


# ---------------------------------------------------------------------- #
# Document spaces
# ---------------------------------------------------------------------- #


class SpaceInput(BaseModel):
    name: str
    kind: SpaceKind
    owner: str = ""
    regulated: bool = False
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    site_url: str | None = None
    team_id: str | None = None
    channel_name: str | None = None
    root_path: str | None = None
    bucket: str | None = None
    prefix: str = ""
    region: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)

    def to_domain(self, space_id: str) -> DocumentSpace:
        payload = self.model_dump(exclude={"client_secret"})
        return DocumentSpace(
            id=space_id,
            created_at=utcnow_iso(),
            client_secret=SecretStr(self.client_secret) if self.client_secret else None,
            **payload,
        )


@router.get("/capabilities")
def space_capabilities() -> dict[str, object]:
    return {"kinds": capabilities()}


@router.get("/spaces")
def list_spaces() -> dict[str, object]:
    return {"spaces": [space.redacted() for space in get_space_repository().list()]}


@router.post("/spaces")
def create_space(payload: SpaceInput) -> dict[str, object]:
    missing = [
        field
        for field in fields_for(payload.kind)
        if field != "prefix" and not getattr(payload, field, None)
    ]
    if missing:
        raise ValidationFailed(
            f"A {payload.kind.value} space needs: {', '.join(missing)}."
        )
    space = payload.to_domain(new_id("space"))
    get_space_repository().save(space)
    return space.redacted()


@router.delete("/spaces/{space_id}")
def delete_space(space_id: str) -> dict[str, object]:
    get_space_repository().delete(space_id)
    return {"deleted": space_id}


@router.get("/spaces/{space_id}/test")
def test_space(space_id: str) -> dict[str, object]:
    provider = get_input_service().provider(space_id)
    ok, detail = provider.available()
    return {"space_id": space_id, "reachable": ok, "detail": detail}


@router.get("/spaces/{space_id}/browse")
def browse_space(space_id: str, path: str = "") -> dict[str, object]:
    provider = get_input_service().provider(space_id)
    ok, detail = provider.available()
    if not ok:
        raise ValidationFailed(detail)
    entries = provider.list(path)
    return {
        "space_id": space_id,
        "path": path,
        "parent": path.rsplit("/", 1)[0] if "/" in path else ("" if path else None),
        "entries": [entry.model_dump(mode="json") for entry in entries],
    }


@router.get("/spaces/{space_id}/search")
def search_space(space_id: str, q: str = Query("", min_length=0)) -> dict[str, object]:
    provider = get_input_service().provider(space_id)
    return {"entries": [entry.model_dump(mode="json") for entry in provider.search(q)]}


@router.post("/spaces/{space_id}/upload")
async def upload_files(space_id: str, files: list[UploadFile] = File(...)) -> dict[str, object]:
    """Store uploads in an upload space.

    Restricted to upload spaces on purpose. The other providers are read-only
    by design — this product never writes to a customer's SharePoint library or
    their S3 bucket, and the API should make that impossible rather than
    merely unlikely.
    """
    from app.adapters.documents.filesystem import UploadProvider

    space = get_space_repository().get(space_id)
    if space is None:
        raise NotFound(f"No document space {space_id!r}.")
    if space.kind is not SpaceKind.UPLOAD:
        raise ValidationFailed(
            f"{space.name} is a {space.kind.value} space, which ADE Studio only reads from. "
            "Upload into an upload space instead."
        )

    provider = get_input_service().provider(space_id)
    assert isinstance(provider, UploadProvider)
    stored = [provider.store(f.filename or "upload.bin", await f.read()) for f in files]
    return {"uploaded": [ref.model_dump(mode="json") for ref in stored]}
