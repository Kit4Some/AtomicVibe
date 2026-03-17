"""Unit tests for LLMRouter."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from architect.config import Settings
from architect.core.exceptions import (
    LLMBudgetExceededError,
    LLMError,
    LLMResponseParseError,
)
from architect.llm.router import LLMRouter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SampleModel(BaseModel):
    name: str
    value: int


def _make_response(
    content: str = "Hello",
    model: str = "claude-sonnet-4.6",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> SimpleNamespace:
    """Build a fake litellm ModelResponse-like object."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        model=model,
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


def _settings(**overrides: Any) -> Settings:
    """Create a Settings instance with sensible test defaults."""
    defaults: dict[str, Any] = {
        "openai_api_key": "test-openai-key",
        "anthropic_api_key": "test-anthropic-key",
        "max_cost_usd": 50.0,
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComplete:
    @pytest.mark.asyncio()
    @patch("architect.llm.router.litellm.acompletion", new_callable=AsyncMock)
    async def test_complete_returns_text_response(self, mock_acomp: AsyncMock) -> None:
        mock_acomp.return_value = _make_response(content="Test answer")
        router = LLMRouter(_settings())

        result = await router.complete(
            messages=[{"role": "user", "content": "Hi"}],
            purpose="plan_analysis",
        )

        assert result == "Test answer"
        mock_acomp.assert_called_once()

    @pytest.mark.asyncio()
    @patch("architect.llm.router.litellm.acompletion", new_callable=AsyncMock)
    async def test_complete_selects_model_by_purpose(
        self, mock_acomp: AsyncMock,
    ) -> None:
        mock_acomp.return_value = _make_response()
        router = LLMRouter(_settings())

        await router.complete(
            messages=[{"role": "user", "content": "Hi"}],
            purpose="supervisor",
        )

        call_kwargs = mock_acomp.call_args
        assert call_kwargs.kwargs["model"] == "claude-haiku-4.5"

    @pytest.mark.asyncio()
    @patch("architect.llm.router.litellm.acompletion", new_callable=AsyncMock)
    async def test_complete_fallback_on_primary_failure(
        self, mock_acomp: AsyncMock,
    ) -> None:
        mock_acomp.side_effect = [
            Exception("primary down"),
            Exception("primary down"),
            Exception("primary down"),
            _make_response(model="openai/gpt-4o"),
        ]
        router = LLMRouter(_settings())

        result = await router.complete(
            messages=[{"role": "user", "content": "Hi"}],
            purpose="plan_analysis",
        )

        assert result == "Hello"
        # Should have tried primary 3 times, then fallback
        assert mock_acomp.call_count == 4

    @pytest.mark.asyncio()
    @patch("architect.llm.router.litellm.acompletion", new_callable=AsyncMock)
    @patch("architect.llm.router.asyncio.sleep", new_callable=AsyncMock)
    async def test_complete_retry_on_transient_error(
        self, mock_sleep: AsyncMock, mock_acomp: AsyncMock,
    ) -> None:
        mock_acomp.side_effect = [
            Exception("transient"),
            _make_response(),
        ]
        router = LLMRouter(_settings())

        result = await router.complete(
            messages=[{"role": "user", "content": "Hi"}],
            purpose="plan_analysis",
        )

        assert result == "Hello"
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio()
    @patch("architect.llm.router.litellm.acompletion", new_callable=AsyncMock)
    async def test_complete_budget_exceeded_raises(
        self, mock_acomp: AsyncMock,
    ) -> None:
        mock_acomp.return_value = _make_response()
        router = LLMRouter(_settings(max_cost_usd=0.001))
        # First call succeeds and records cost
        await router.complete(
            messages=[{"role": "user", "content": "Hi"}],
            purpose="code_generation",
        )
        # Manually push cost over budget
        await router.cost_tracker.track("claude-sonnet-4.6", 100000, 50000, "x")

        with pytest.raises(LLMBudgetExceededError):
            await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                purpose="plan_analysis",
            )

    @pytest.mark.asyncio()
    @patch("architect.llm.router.litellm.acompletion", new_callable=AsyncMock)
    @patch("architect.llm.router.asyncio.sleep", new_callable=AsyncMock)
    async def test_complete_all_models_fail_raises_llm_error(
        self, _mock_sleep: AsyncMock, mock_acomp: AsyncMock,
    ) -> None:
        mock_acomp.side_effect = Exception("always fails")
        router = LLMRouter(_settings())

        with pytest.raises(LLMError, match="All models in fallback chain failed"):
            await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                purpose="plan_analysis",
            )


class TestCompleteStructured:
    @pytest.mark.asyncio()
    @patch("architect.llm.router.litellm.acompletion", new_callable=AsyncMock)
    async def test_complete_structured_parses_json(
        self, mock_acomp: AsyncMock,
    ) -> None:
        mock_acomp.return_value = _make_response(
            content='{"name": "test", "value": 42}',
        )
        router = LLMRouter(_settings())

        result = await router.complete_structured(
            messages=[{"role": "user", "content": "Give me data"}],
            response_model=_SampleModel,
            purpose="plan_analysis",
        )

        assert isinstance(result, _SampleModel)
        assert result.name == "test"
        assert result.value == 42

    @pytest.mark.asyncio()
    @patch("architect.llm.router.litellm.acompletion", new_callable=AsyncMock)
    async def test_complete_structured_retry_on_parse_failure(
        self, mock_acomp: AsyncMock,
    ) -> None:
        mock_acomp.side_effect = [
            _make_response(content="not json"),
            _make_response(content='{"name": "ok", "value": 1}'),
        ]
        router = LLMRouter(_settings())

        result = await router.complete_structured(
            messages=[{"role": "user", "content": "Give me data"}],
            response_model=_SampleModel,
            purpose="plan_analysis",
        )

        assert result.name == "ok"

    @pytest.mark.asyncio()
    @patch("architect.llm.router.litellm.acompletion", new_callable=AsyncMock)
    async def test_complete_structured_raises_on_repeated_parse_failure(
        self, mock_acomp: AsyncMock,
    ) -> None:
        mock_acomp.return_value = _make_response(content="not json at all")
        router = LLMRouter(_settings())

        with pytest.raises(LLMResponseParseError):
            await router.complete_structured(
                messages=[{"role": "user", "content": "Give me data"}],
                response_model=_SampleModel,
                purpose="plan_analysis",
            )
