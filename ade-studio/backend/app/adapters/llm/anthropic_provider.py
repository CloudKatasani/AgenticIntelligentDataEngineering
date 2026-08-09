"""Anthropic-backed reasoning for agent runs."""

from __future__ import annotations

import json

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.domain.model import TokenUsage
from app.ports.llm_provider import LLMProvider, LLMRequest, LLMResponse
from app.services.model_registry import get_model

logger = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or get_settings().anthropic_api_key
        self._client = None

    def available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:  # pragma: no cover
            return False
        return True

    def _get_client(self):  # noqa: ANN202 — the SDK's client type
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def complete(self, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        selection = request.selection
        descriptor = get_model(selection.model_id)

        kwargs: dict[str, object] = {
            "model": selection.model_id,
            "max_tokens": min(selection.max_output_tokens, descriptor.max_output_tokens),
            "system": request.system,
            "messages": [{"role": "user", "content": request.user}],
            # Adaptive thinking; depth is controlled by effort, not a token budget.
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": selection.effort.value},
        }
        if request.output_schema is not None:
            # Constrain the response so artifact assembly never has to parse
            # free-form prose.
            kwargs["output_config"] = {
                "effort": selection.effort.value,
                "format": {"type": "json_schema", "schema": request.output_schema},
            }

        message = client.messages.create(**kwargs)  # type: ignore[arg-type]

        stop_reason = getattr(message, "stop_reason", "") or ""
        if stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            log_event(logger, "model_refusal", category=getattr(details, "category", None))
            return LLMResponse(
                text="",
                provider=self.name,
                model_id=selection.model_id,
                stop_reason=stop_reason,
                refused=True,
            )

        text = "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        )

        data: dict[str, object] = {}
        if request.output_schema is not None and text.strip():
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    data = parsed
            except json.JSONDecodeError:
                log_event(logger, "structured_output_parse_failed", length=len(text))

        raw_usage = getattr(message, "usage", None)
        usage = TokenUsage(
            input_tokens=getattr(raw_usage, "input_tokens", 0) or 0,
            output_tokens=getattr(raw_usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(raw_usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(raw_usage, "cache_creation_input_tokens", 0) or 0,
        )
        usage.cost_usd = round(
            descriptor.estimate_cost_usd(usage.input_tokens, usage.output_tokens), 6
        )

        return LLMResponse(
            text=text,
            data=data,
            usage=usage,
            provider=self.name,
            model_id=selection.model_id,
            stop_reason=stop_reason,
        )
