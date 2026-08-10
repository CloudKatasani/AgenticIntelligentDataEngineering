"""What each agent needs from the operator before it can run.

The fleet does not take one kind of input. Agent 01 profiles database tables;
agent 06 reads COBOL copybooks and Informatica XML; agent 22 reads a warehouse
metering export; agent 33 takes a sentence describing a goal and no data at
all. Presenting all of them behind a table picker is not a UI simplification,
it is wrong — it asks for something most agents cannot use and fails to ask for
the thing they need.

So an agent declares **input slots**. Each slot names one thing the operator
must supply, what kind of thing it is, and where it may come from. The
workbench renders the slots; the run engine gates on the required ones.

Two axes:

``InputKind``
    What the thing *is* — database objects, code artifacts, a telemetry export,
    a policy document, a typed request. This decides how the input is read and
    how it is framed to the model.

``InputOrigin``
    Where it *comes from* — a registered database, an upload, a SharePoint
    library, a Teams channel, a shared drive, object storage. This decides
    which picker the operator gets and which adapter fetches the bytes.

The two are independent: legacy copybooks are ``code_artifacts`` whether they
arrive from SharePoint or a laptop, and the agent's prompt should not be able
to tell the difference.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class InputKind(str, Enum):
    DATABASE_OBJECTS = "database_objects"
    """Tables and columns in a registered source, profiled deterministically."""

    CODE_ARTIFACTS = "code_artifacts"
    """SQL, DDL, ETL exports, dbt projects, copybooks, stored procedure bodies."""

    TELEMETRY_EXPORT = "telemetry_export"
    """Query history, run logs, metering, schema snapshots, BI inventories."""

    POLICY_DOCUMENT = "policy_document"
    """Taxonomies, standards, regulation libraries, entitlement matrices, SLAs."""

    STRUCTURED_REQUEST = "structured_request"
    """Typed text: a goal, a question, a backfill request, an incident summary."""


class InputOrigin(str, Enum):
    CONNECTION = "connection"
    """A registered database source."""

    UPLOAD = "upload"
    SHAREPOINT = "sharepoint"
    TEAMS = "teams"
    SHARED_DRIVE = "shared_drive"
    OBJECT_STORE = "object_store"

    INLINE = "inline"
    """Typed into the workbench rather than fetched from anywhere."""


FILE_ORIGINS: tuple[InputOrigin, ...] = (
    InputOrigin.UPLOAD,
    InputOrigin.SHAREPOINT,
    InputOrigin.TEAMS,
    InputOrigin.SHARED_DRIVE,
    InputOrigin.OBJECT_STORE,
)
"""Origins that resolve to files. Any of them satisfies a file-shaped slot."""


_DEFAULT_ORIGINS: dict[InputKind, tuple[InputOrigin, ...]] = {
    InputKind.DATABASE_OBJECTS: (InputOrigin.CONNECTION,),
    InputKind.CODE_ARTIFACTS: FILE_ORIGINS,
    InputKind.TELEMETRY_EXPORT: FILE_ORIGINS + (InputOrigin.CONNECTION,),
    InputKind.POLICY_DOCUMENT: FILE_ORIGINS + (InputOrigin.INLINE,),
    InputKind.STRUCTURED_REQUEST: (InputOrigin.INLINE,),
}


class InputSlot(BaseModel):
    """One thing an agent asks the operator for."""

    key: str
    label: str
    kind: InputKind
    required: bool = True
    help: str = ""
    """Why this agent needs it, in the operator's language."""

    spec_reference: str = ""
    """The line in the agent's own spec that this slot implements."""

    origins: list[InputOrigin] = Field(default_factory=list)
    accepts: list[str] = Field(default_factory=list)
    """Indicative file extensions. Empty means the kind's usual set."""

    placeholder: str = ""
    """For inline slots only — an example of a good answer."""

    max_files: int = 25

    def model_post_init(self, _context: object) -> None:
        if not self.origins:
            self.origins = list(_DEFAULT_ORIGINS[self.kind])

    @property
    def accepts_files(self) -> bool:
        return any(origin in FILE_ORIGINS for origin in self.origins)


class InputBinding(BaseModel):
    """What the operator actually supplied for one slot."""

    slot_key: str
    origin: InputOrigin

    connection_id: str | None = None
    datasets: list[dict[str, object]] = Field(default_factory=list)
    """Database objects, when the origin is a connection."""

    file_ids: list[str] = Field(default_factory=list)
    """Resolved document ids, when the origin is file-shaped."""

    text: str = ""
    """The typed value, when the origin is inline."""

    def is_empty(self) -> bool:
        return not (self.datasets or self.file_ids or self.text.strip())
