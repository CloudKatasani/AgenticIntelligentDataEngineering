"""A worked example: what goes into an agent, and what comes out.

The fleet is hard to sell in the abstract. "Agent 14 modernizes legacy logic"
means nothing to a head of data engineering; a COBOL paragraph on the left, the
Snowflake SQL it became on the right, and a declared-delta register admitting
the one rule that could not be translated faithfully — that lands.

So every agent carries one worked example, and they are all set in the same
estate telling one story: a mainframe customer master and a legacy warehouse
becoming a certified customer-360 data product. Read end to end, the 35
examples are a migration; read one at a time, each is a demo of one agent.

These are **illustrations, not run records**. The distinction is kept sharp
everywhere: a worked example is labelled as one, carries no run id, and sits
beside a button that runs the same configuration for real. Presenting authored
content as system output would undo the thing this product is actually selling.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Exhibit(BaseModel):
    """One thing handed to the agent."""

    label: str
    kind: str
    """Matches ``InputKind``, or ``upstream_artifact`` for context-layer input."""

    origin: str
    """Where it came from, in the operator's words — "Sample artifacts /
    legacy", "ADE Demo Warehouse", "typed into the workbench"."""

    format: str
    """Drives syntax presentation: sql, cobol, csv, yaml, json, markdown, text."""

    body: str
    stat: str = ""
    """A counted fact about the exhibit — "2,000 rows · 12 columns"."""

    note: str = ""
    """Why this input matters, for the presenter."""


class ExampleArtifact(BaseModel):
    """One file the agent produced."""

    filename: str
    title: str
    format: str
    source: str
    """``deterministic`` or ``reasoned`` — the same distinction the run engine
    records, because "which numbers did a model produce" is the first question
    a serious buyer asks."""

    body: str
    note: str = ""


class WorkedExample(BaseModel):
    agent_id: str
    scenario: str
    """The business situation, in two sentences a data leader would recognise."""

    inputs: list[Exhibit] = Field(default_factory=list)
    upstream: list[str] = Field(default_factory=list)
    """Artifacts arriving from prior runs rather than from the operator."""

    outputs: list[ExampleArtifact] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    """What to point at while the client is looking at the screen."""

    handoffs: list[str] = Field(default_factory=list)
    """Work the agent deliberately refused, and who owns it."""

    chapter: str = ""
    """Where this sits in the migration story, for the fleet canvas."""
