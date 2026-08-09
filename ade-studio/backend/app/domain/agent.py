"""Agent domain model.

These types mirror ``ade-agent-specs/agents/NN-slug/spec.yaml``. The app never
hardcodes the fleet: adding a spec folder adds an agent, which is what the
catalog README means by "regenerate rather than hand-edit".
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AutonomyTier(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"

    @property
    def rank(self) -> int:
        return int(self.value[1])


class DependencyKind(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class Dependency(BaseModel):
    """A typed edge to another agent.

    ``hard`` blocks execution; ``soft`` only degrades quality when absent.
    """

    agent_id: str
    agent_name: str
    kind: DependencyKind


class NonGoal(BaseModel):
    """A boundary and who owns the excluded ground.

    ``owned_by`` is empty when the catalog records ``owned_by: null`` — the
    exclusion is human-owned or by design, and no agent picks it up.
    """

    exclusion: str
    owned_by: str = ""
    owner_name: str

    @property
    def human_owned(self) -> bool:
        return not self.owned_by


class ArtifactFormat(str, Enum):
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"
    SQL = "sql"
    CSV = "csv"
    PYTHON = "python"


class ArtifactSource(str, Enum):
    DETERMINISTIC = "deterministic"
    """Computed by code. Design rule 4: the LLM never computes numbers."""

    REASONED = "reasoned"
    """Drafted by the model, grounded in deterministic inputs."""


class ArtifactSpec(BaseModel):
    """One file a run of this agent is contracted to produce."""

    key: str
    filename: str
    title: str
    description: str
    format: ArtifactFormat
    source: ArtifactSource = ArtifactSource.REASONED


class ParameterType(str, Enum):
    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"


class AgentParameter(BaseModel):
    """A run-time knob surfaced in the workbench."""

    key: str
    label: str
    type: ParameterType
    description: str = ""
    default: object | None = None
    options: list[str] = Field(default_factory=list)
    required: bool = False


class AgentSpec(BaseModel):
    """The full, machine-readable contract for one agent."""

    id: str
    slug: str
    name: str
    domain: str
    core_original_scope: bool = False

    tier: AutonomyTier
    tier_name: str
    tier_definition: str

    purpose: str
    scope: list[str] = Field(default_factory=list)
    non_goals: list[NonGoal] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)

    hard_dependencies: list[Dependency] = Field(default_factory=list)
    soft_dependencies: list[Dependency] = Field(default_factory=list)
    context_layer_requirements: list[str] = Field(default_factory=list)

    triggers: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    evaluation: list[str] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)
    escalation: str = ""

    skill_markdown: str = ""
    """The operator-readable SKILL.md, loaded verbatim into the run prompt."""

    artifacts: list[ArtifactSpec] = Field(default_factory=list)
    parameters: list[AgentParameter] = Field(default_factory=list)

    requires_dataset: bool = True
    """False for agents that reason over the estate rather than a table set."""

    regulated_tier_cap: AutonomyTier | None = None
    """Design rule 3: agents 02, 26 and 27 are capped at L1 when regulated."""

    @property
    def dependency_ids(self) -> list[str]:
        return [d.agent_id for d in self.hard_dependencies + self.soft_dependencies]

    @property
    def requires_approval(self) -> bool:
        """L0 and L1 agents propose; a human accepts."""
        return self.tier.rank <= 1

    def effective_tier(self, regulated: bool) -> AutonomyTier:
        if regulated and self.regulated_tier_cap is not None:
            if self.tier.rank > self.regulated_tier_cap.rank:
                return self.regulated_tier_cap
        return self.tier
