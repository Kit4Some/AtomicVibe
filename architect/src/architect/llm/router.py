"""LLMRouter — centralised LLM gateway for all ARCHITECT engines.

Every LLM call in the system MUST go through this router.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING

import litellm

from architect.config import Settings
from architect.core.exceptions import (
    LLMBudgetExceededError,
    LLMError,
    LLMRateLimitError,
    LLMResponseParseError,
)
from architect.llm.cost_tracker import CostTracker
from architect.llm.models import FALLBACK_CHAINS, PURPOSE_MODEL_MAP, set_tier

if TYPE_CHECKING:
    from pydantic import BaseModel

log = logging.getLogger("architect.llm.router")

_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    """Remove Markdown code fences (```json ... ```) wrapping LLM output."""
    stripped = text.strip()
    m = _CODE_FENCE_RE.match(stripped)
    if m:
        return m.group(1)
    return stripped


class LLMRouter:
    """Route LLM calls by *purpose*, handle fallbacks, retries, and budgets."""

    def __init__(self, config: Settings) -> None:
        self._config = config
        self.cost_tracker = CostTracker()

        # Configure litellm API keys globally — set both the litellm
        # attribute AND the environment variable so litellm's provider-specific
        # lookup finds the key regardless of how it resolves credentials.
        import os

        if config.anthropic_api_key.get_secret_value():
            key = config.anthropic_api_key.get_secret_value()
            litellm.api_key = key
            os.environ["ANTHROPIC_API_KEY"] = key
        if config.openai_api_key.get_secret_value():
            key = config.openai_api_key.get_secret_value()
            litellm.openai_key = key
            os.environ["OPENAI_API_KEY"] = key

        litellm.drop_params = True
        litellm.set_verbose = False

        # Apply tier from config
        set_tier(config.tier)

        log.info("LLM router initialised with default_model=%s tier=%s", config.default_model, config.tier)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[dict[str, str]],
        purpose: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request, returning the text content.

        The model is chosen automatically from *purpose*.  On failure the
        router walks the fallback chain and retries with exponential backoff.
        """
        model = PURPOSE_MODEL_MAP.get(purpose, self._config.default_model)

        if not self.cost_tracker.check_budget(self._config.max_cost_usd):
            raise LLMBudgetExceededError(
                detail=f"Budget {self._config.max_cost_usd} USD exceeded",
            )

        response = await self._call_with_fallback(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            purpose=purpose,
        )

        content: str = response.choices[0].message.content or ""
        usage = response.usage
        if usage:
            await self.cost_tracker.track(
                model=response.model or model,
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                purpose=purpose,
            )

        return content

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        purpose: str,
    ) -> BaseModel:
        """Like :meth:`complete` but parse the response into a Pydantic model.

        On parse failure the call is retried once with an explicit JSON
        instruction appended.  Two consecutive failures raise
        :class:`LLMResponseParseError`.
        """
        model = PURPOSE_MODEL_MAP.get(purpose, self._config.default_model)

        if not self.cost_tracker.check_budget(self._config.max_cost_usd):
            raise LLMBudgetExceededError(
                detail=f"Budget {self._config.max_cost_usd} USD exceeded",
            )

        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        system_instruction = (
            "You MUST respond with valid JSON matching this schema.\n"
            "Do NOT wrap your response in markdown code fences or any other formatting.\n"
            "Output raw JSON only.\n\n"
            f"Schema:\n{schema_json}"
        )

        enriched: list[dict[str, str]] = [
            {"role": "system", "content": system_instruction},
            *messages,
        ]

        for attempt in range(2):
            response = await self._call_with_fallback(
                model=model,
                messages=enriched,
                temperature=0.0,
                max_tokens=4096,
                purpose=purpose,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content or ""
            # Strip markdown code fences that some models wrap JSON in
            raw = _strip_code_fences(raw)
            usage = response.usage
            if usage:
                await self.cost_tracker.track(
                    model=response.model or model,
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    purpose=purpose,
                )

            try:
                return response_model.model_validate_json(raw)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "Structured parse failed (attempt %d, model=%s): %s",
                    attempt + 1, model, exc,
                )
                if attempt == 0:
                    enriched.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous response was not valid JSON. "
                                "Respond ONLY in valid JSON matching the schema."
                            ),
                        },
                    )

        raise LLMResponseParseError(
            detail=f"Failed to parse response into {response_model.__name__} after 2 attempts",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_with_fallback(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        purpose: str,
        **kwargs: object,
    ) -> litellm.ModelResponse:
        """Try *model*, then each fallback in order."""
        chain = [model, *FALLBACK_CHAINS.get(model, [])]
        last_exc: Exception | None = None

        for candidate in chain:
            try:
                return await self._call_with_retry(
                    model=candidate,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except LLMRateLimitError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                log.warning(
                    "Fallback: model=%s failed for purpose=%s: %s",
                    candidate, purpose, exc,
                )

        raise LLMError(
            message="All models in fallback chain failed",
            detail=str(last_exc),
        )

    async def _call_with_retry(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs: object,
    ) -> litellm.ModelResponse:
        """Call ``litellm.acompletion`` with up to 3 retries + exponential backoff."""
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response: litellm.ModelResponse = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                return response
            except litellm.RateLimitError as exc:
                retry_after = getattr(exc, "retry_after", None)
                wait = (
                    float(retry_after)
                    if retry_after is not None
                    else _BACKOFF_BASE_SECONDS * (2 ** attempt)
                )
                log.warning(
                    "Rate limit hit: model=%s attempt=%d wait=%.1fs",
                    model, attempt + 1, wait,
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                    last_exc = exc
                else:
                    raise LLMRateLimitError(
                        detail=f"Rate limited on {model} after {_MAX_RETRIES} retries",
                    ) from exc
            except Exception as exc:  # noqa: BLE001
                wait = _BACKOFF_BASE_SECONDS * (2 ** attempt)
                log.warning(
                    "LLM call error: model=%s attempt=%d error=%s wait=%.1fs",
                    model, attempt + 1, exc, wait,
                )
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)

        raise LLMError(
            message=f"LLM call to {model} failed after {_MAX_RETRIES} retries",
            detail=str(last_exc),
        )
