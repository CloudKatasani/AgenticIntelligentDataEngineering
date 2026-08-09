"""The model catalog the user picks from, per task."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ModelTier(str, Enum):
    FRONTIER = "frontier"
    BALANCED = "balanced"
    FAST = "fast"


class Effort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


class ModelDescriptor(BaseModel):
    """One selectable model, with the economics needed to choose between them."""

    id: str
    display_name: str
    tier: ModelTier
    context_window: int
    max_output_tokens: int
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    strengths: list[str] = Field(default_factory=list)
    best_for_domains: list[str] = Field(default_factory=list)
    notes: str = ""
    available: bool = True

    def estimate_cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1_000_000 * self.input_usd_per_mtok
            + output_tokens / 1_000_000 * self.output_usd_per_mtok
        )


class ModelSelection(BaseModel):
    """What the user chose for this specific task."""

    model_id: str
    effort: Effort = Effort.HIGH
    max_output_tokens: int = 16_000


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
