"""Port: the reasoning engine behind an agent run."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from app.domain.model import ModelSelection, TokenUsage


class LLMRequest(BaseModel):
    system: str
    """The agent's SKILL.md plus the universal guardrails."""

    user: str
    """The task brief: objects, deterministic facts, parameters, objective."""

    selection: ModelSelection
    output_schema: dict[str, object] | None = None
    """When present the response is constrained to this JSON schema."""

    context: dict[str, object] = Field(default_factory=dict)
    """Structured facts already rendered into ``user``.

    The Anthropic provider ignores this — the prompt is authoritative. The
    offline simulation provider reads it so a credential-free demo still
    produces output grounded in the real profiled numbers.
    """


class LLMResponse(BaseModel):
    text: str = ""
    data: dict[str, object] = Field(default_factory=dict)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    provider: str = ""
    model_id: str = ""
    stop_reason: str = ""
    refused: bool = False


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse: ...
