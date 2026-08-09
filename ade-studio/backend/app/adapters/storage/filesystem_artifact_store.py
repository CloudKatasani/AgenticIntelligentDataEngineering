"""Artifacts on the local filesystem, one directory per run.

Every artifact is hashed on write. The zip bundle carries a manifest so a
downloaded pack is self-describing: which agent produced it, on which model,
against which objects, under which gates.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from app.core.errors import NotFound
from app.core.ids import utcnow_iso
from app.domain.run import Artifact, Run
from app.ports.repositories import ArtifactStore


class FilesystemArtifactStore(ArtifactStore):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str, filename: str) -> Path:
        directory = self.root / run_id
        directory.mkdir(parents=True, exist_ok=True)
        # Defend against a filename from a model response escaping the run dir.
        safe = Path(filename).name
        return directory / safe

    def write(self, run_id: str, artifact: Artifact, content: str | bytes) -> Artifact:
        payload = content.encode("utf-8") if isinstance(content, str) else content
        path = self._path(run_id, artifact.filename)
        path.write_bytes(payload)
        artifact.size_bytes = len(payload)
        artifact.sha256 = hashlib.sha256(payload).hexdigest()
        artifact.created_at = utcnow_iso()
        return artifact

    def read(self, artifact: Artifact) -> bytes:
        path = self.root / artifact.run_id / Path(artifact.filename).name
        if not path.exists():
            raise NotFound(f"Artifact file missing: {artifact.filename}")
        return path.read_bytes()

    def bundle(self, run: Run) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("MANIFEST.json", json.dumps(_manifest(run), indent=2, default=str))
            archive.writestr("README.md", _readme(run))
            for artifact in run.artifacts:
                try:
                    archive.writestr(f"artifacts/{artifact.filename}", self.read(artifact))
                except NotFound:
                    continue
        return buffer.getvalue()


def _manifest(run: Run) -> dict[str, object]:
    """Provenance: enough to reproduce and to audit the run."""
    return {
        "run_id": run.id,
        "agent": {"id": run.agent_id, "name": run.agent_name, "domain": run.agent_domain},
        "status": run.status.value,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
        "model": {"id": run.model_id, "effort": run.effort, "provider": run.provider},
        "usage": run.usage.model_dump(),
        "objects": [d.fqn for d in run.request.datasets],
        "parameters": run.request.parameters,
        "objective": run.request.objective,
        "gates": [g.model_dump() for g in run.gates],
        "approval": {"approved_by": run.approved_by, "approved_at": run.approved_at},
        "artifacts": [
            {
                "filename": a.filename,
                "title": a.title,
                "format": a.format,
                "source": a.source,
                "kind": a.kind.value,
                "sha256": a.sha256,
                "size_bytes": a.size_bytes,
            }
            for a in run.artifacts
        ],
        "handoffs": run.handoffs,
    }


def _readme(run: Run) -> str:
    proposal_note = (
        "These artifacts are **proposals**. The producing agent operates at an advisory tier, "
        "so nothing here takes effect until a human accepts it."
        if any(a.kind.value == "proposal" for a in run.artifacts)
        else "These artifacts are agent **records**, produced within the agent's autonomy tier."
    )
    lines = [
        f"# {run.agent_id} — {run.agent_name}",
        "",
        f"Run `{run.id}` · status **{run.status.value}** · model `{run.model_id}` "
        f"(effort `{run.effort}`, provider `{run.provider}`)",
        "",
        proposal_note,
        "",
        "## Summary",
        "",
        run.summary or "_No summary recorded._",
        "",
        "## Objects examined",
        "",
    ]
    lines += [f"- `{d.fqn}`" for d in run.request.datasets] or ["- None (estate-scoped run)."]
    if run.findings:
        lines += ["", "## Findings", ""] + [f"- {f}" for f in run.findings]
    if run.open_questions:
        lines += ["", "## Open questions for a human", ""] + [f"- {q}" for q in run.open_questions]
    if run.handoffs:
        lines += ["", "## Handoffs to other agents", ""]
        lines += [
            f"- **{h.get('to_agent_id')} {h.get('to_agent_name')}** — {h.get('reason')}"
            for h in run.handoffs
        ]
    lines += ["", "## Files", ""]
    lines += [f"- `artifacts/{a.filename}` — {a.title}" for a in run.artifacts]
    lines += ["", "Provenance for this run is in `MANIFEST.json`.", ""]
    return "\n".join(lines)
