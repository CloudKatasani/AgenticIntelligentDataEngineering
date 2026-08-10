"""Resolving what the operator supplied into what an agent can reason over.

Bindings arrive as references — a connection and some tables, a list of file
ids, a block of typed text. This turns them into evidence: profiles for the
tables, counted facts and excerpts for the files, the text as written.

Files are fetched here rather than in the run engine so the engine keeps
knowing nothing about SharePoint, S3 or uploads. It receives evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.adapters.documents.registry import build_provider
from app.core.errors import ConnectionFailed, NotFound
from app.core.logging import get_logger, log_event
from app.domain.input_contract import InputBinding, InputKind, InputOrigin, InputSlot
from app.ports.repositories import DocumentSpaceRepository
from app.runtime.deterministic.artifacts import ArtifactFacts, read_artifact

logger = get_logger(__name__)


@dataclass
class ResolvedInput:
    """One slot, resolved."""

    slot: InputSlot
    binding: InputBinding
    facts: list[ArtifactFacts] = field(default_factory=list)
    text: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.facts)

    def as_dict(self) -> dict[str, object]:
        return {
            "slot": self.slot.key,
            "label": self.slot.label,
            "kind": self.slot.kind.value,
            "origin": self.binding.origin.value,
            "files": [f.as_dict() for f in self.facts],
            "text": self.text,
            "errors": self.errors,
        }


class InputService:
    def __init__(self, spaces: DocumentSpaceRepository, upload_root: Path) -> None:
        self.spaces = spaces
        self.upload_root = upload_root

    def provider(self, space_id: str):  # noqa: ANN201 — DocumentProvider
        space = self.spaces.get(space_id)
        if space is None:
            raise NotFound(f"No document space {space_id!r}.")
        return build_provider(space, upload_root=self.upload_root)

    def resolve(self, slots: list[InputSlot], bindings: dict[str, InputBinding]) -> list[ResolvedInput]:
        """Fetch and read everything the operator supplied.

        A file that cannot be fetched is recorded as an error on its slot
        rather than failing the run. Losing one of twenty legacy artifacts to a
        permissions problem should not discard the other nineteen — but the run
        record has to say which one was lost, or the output silently describes
        a smaller estate than the operator asked about.
        """
        resolved: list[ResolvedInput] = []
        for slot in slots:
            binding = bindings.get(slot.key)
            if binding is None or binding.is_empty():
                continue

            entry = ResolvedInput(slot=slot, binding=binding)
            if binding.origin is InputOrigin.INLINE:
                entry.text = binding.text.strip()
            elif binding.origin is not InputOrigin.CONNECTION:
                entry.facts, entry.errors = self._read_files(binding.file_ids)
            resolved.append(entry)
        return resolved

    def _read_files(self, file_ids: list[str]) -> tuple[list[ArtifactFacts], list[str]]:
        facts: list[ArtifactFacts] = []
        errors: list[str] = []
        cache: dict[str, object] = {}

        for file_id in file_ids:
            space_id, _, _ = file_id.partition("::")
            try:
                provider = cache.get(space_id)
                if provider is None:
                    provider = self.provider(space_id)
                    cache[space_id] = provider
                content = provider.fetch(file_id)  # type: ignore[attr-defined]
                space = self.spaces.get(space_id)
                facts.append(read_artifact(content, space_name=space.name if space else space_id))
            except (NotFound, ConnectionFailed) as exc:
                errors.append(f"{file_id}: {exc}")
                log_event(logger, "input_file_unreadable", file_id=file_id, error=str(exc))
            except Exception as exc:  # noqa: BLE001 — one bad file must not sink the run
                errors.append(f"{file_id}: {exc}")
                log_event(logger, "input_file_failed", file_id=file_id, error=str(exc))
        return facts, errors


def brief_section(resolved: list[ResolvedInput]) -> str:
    """The supplied-inputs part of a task brief.

    Structured-request text goes in as the operator wrote it, labelled by the
    slot it answers, so an agent that asked for a goal statement can tell it
    apart from one that asked for an incident summary.
    """
    from app.runtime.deterministic.artifacts import summarise_for_prompt

    if not resolved:
        return ""

    blocks: list[str] = []
    for entry in resolved:
        if entry.slot.kind is InputKind.STRUCTURED_REQUEST and entry.text:
            blocks.append(f"## {entry.slot.label} (supplied by the operator)\n{entry.text}")
        elif entry.text:
            blocks.append(f"## {entry.slot.label}\n{entry.text}")

    file_entries = [e for e in resolved if e.facts]
    for entry in file_entries:
        header = f"## {entry.slot.label} — {len(entry.facts)} file(s)"
        blocks.append(f"{header}\n{summarise_for_prompt(entry.facts)}")

    for entry in resolved:
        if entry.errors:
            blocks.append(
                f"## {entry.slot.label}: files that could not be read\n"
                + "\n".join(f"- {e}" for e in entry.errors)
                + "\nSay so in your findings; do not describe these as if you had read them."
            )
    return "\n\n".join(blocks)
