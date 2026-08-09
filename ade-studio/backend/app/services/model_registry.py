"""The model catalog, and how a model is recommended for a given agent.

Every run carries an explicit model choice. The default is a recommendation,
never a silent decision: the workbench shows which model is suggested for the
agent and why, and the operator can override it per task.
"""

from __future__ import annotations

from app.core.errors import NotFound
from app.domain.agent import AgentSpec
from app.domain.model import Effort, ModelDescriptor, ModelTier

# Pricing and context windows as published for the current lineup.
MODELS: list[ModelDescriptor] = [
    ModelDescriptor(
        id="claude-opus-5",
        display_name="Claude Opus 5",
        tier=ModelTier.FRONTIER,
        context_window=1_000_000,
        max_output_tokens=128_000,
        input_usd_per_mtok=5.0,
        output_usd_per_mtok=25.0,
        strengths=[
            "Deep reasoning over ambiguous modelling and mapping decisions",
            "Long-horizon agentic work across many objects",
            "High-precision code review and bug finding",
        ],
        best_for_domains=["build", "quality", "governance", "cross-cutting"],
        notes="Default for design, modelling, contract and remediation work.",
    ),
    ModelDescriptor(
        id="claude-sonnet-5",
        display_name="Claude Sonnet 5",
        tier=ModelTier.BALANCED,
        context_window=1_000_000,
        max_output_tokens=128_000,
        input_usd_per_mtok=3.0,
        output_usd_per_mtok=15.0,
        strengths=[
            "Near-frontier quality on coding and agentic work",
            "Strong cost/latency balance for high-volume runs",
        ],
        best_for_domains=["discovery", "build", "operations", "consumption"],
        notes="Good default for repeated profiling, cataloguing and code generation at scale.",
    ),
    ModelDescriptor(
        id="claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        tier=ModelTier.FAST,
        context_window=200_000,
        max_output_tokens=64_000,
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=5.0,
        strengths=["Fastest and cheapest", "Well suited to narrow, well-specified extraction"],
        best_for_domains=["discovery", "consumption"],
        notes="Use for high-volume, low-ambiguity passes. Smaller context window.",
    ),
    ModelDescriptor(
        id="claude-opus-4-8",
        display_name="Claude Opus 4.8",
        tier=ModelTier.FRONTIER,
        context_window=1_000_000,
        max_output_tokens=128_000,
        input_usd_per_mtok=5.0,
        output_usd_per_mtok=25.0,
        strengths=["Previous-generation Opus", "Pin here for reproducibility of an earlier run"],
        best_for_domains=["build", "quality"],
        notes="Kept selectable so an audited run can be reproduced on its original model.",
    ),
    ModelDescriptor(
        id="claude-fable-5",
        display_name="Claude Fable 5",
        tier=ModelTier.FRONTIER,
        context_window=1_000_000,
        max_output_tokens=128_000,
        input_usd_per_mtok=10.0,
        output_usd_per_mtok=50.0,
        strengths=[
            "Most capable model for the hardest reasoning",
            "Long autonomous runs over large estates",
        ],
        best_for_domains=["build", "governance"],
        notes="Highest capability tier; priced above Opus. Requires 30-day data retention.",
    ),
]

_BY_ID = {m.id: m for m in MODELS}

# Agents whose work is genuinely hard reasoning get a frontier default; agents
# doing high-volume, well-specified extraction get the balanced model. This is
# the recommendation only — the operator chooses per run.
_FRONTIER_AGENTS = {
    "08",  # Data Modeling — open-ended design
    "09",  # Data Mapping — ambiguity resolution
    "13",  # Data Contract — commitments that bind downstream
    "14",  # Legacy Modernization — semantics recovery
    "19",  # Root Cause Analysis
    "20",  # Remediation — the only agent that may mutate production
    "26",  # Access & Entitlement
    "27",  # Privacy & Retention
    "28",  # Regulatory Evidence
    "33",  # Supervisor
    "35",  # Reviewer
}

_FAST_AGENTS = {
    "01",  # Source Profiling — numbers come from code, not the model
    "17",  # Anomaly & Freshness — baselines are computed
    "32",  # Request Intake — structured extraction
}


def list_models() -> list[ModelDescriptor]:
    return MODELS


def get_model(model_id: str) -> ModelDescriptor:
    model = _BY_ID.get(model_id)
    if model is None:
        raise NotFound(f"Unknown model {model_id!r}.")
    return model


def recommend_for(agent: AgentSpec) -> dict[str, object]:
    """Suggest a model and effort for one agent, with the reason shown to users."""
    if agent.id in _FRONTIER_AGENTS:
        model_id, effort = "claude-opus-5", Effort.XHIGH
        reason = (
            "This agent makes judgment calls that bind downstream work, so it defaults to the "
            "frontier model at high effort."
        )
    elif agent.id in _FAST_AGENTS:
        model_id, effort = "claude-haiku-4-5", Effort.MEDIUM
        reason = (
            "The numbers in this agent's output are computed deterministically; the model only "
            "interprets them, so a fast model is sufficient."
        )
    elif agent.tier.rank >= 3:
        model_id, effort = "claude-opus-5", Effort.HIGH
        reason = "This agent may act with limited supervision, so it defaults to the frontier model."
    else:
        model_id, effort = "claude-sonnet-5", Effort.HIGH
        reason = "Balanced default: near-frontier quality at lower cost for routine fleet work."

    return {
        "model_id": model_id,
        "effort": effort.value,
        "reason": reason,
        "max_output_tokens": 16_000,
    }


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    return get_model(model_id).estimate_cost_usd(input_tokens, output_tokens)


def estimate_tokens(text: str) -> int:
    """Rough pre-flight token estimate for the cost preview.

    Deliberately approximate and labelled as such in the UI; the run records
    actual usage reported by the provider.
    """
    return max(1, len(text) // 4)
