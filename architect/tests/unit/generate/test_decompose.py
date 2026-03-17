"""Unit tests for the decompose_modules node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from architect.core.exceptions import GenerateError
from architect.core.models import GenerateState, ModuleDefinition
from architect.generate.nodes.decompose import ModuleList, decompose_modules


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides: Any) -> GenerateState:
    defaults: dict[str, Any] = {
        "plan_document": "# My Project\n\nBuild a REST API with auth and database.",
        "decisions": [{"topic": "language", "chosen": "Python", "label": "Python", "rationale": "Team expertise"}],
        "modules": [],
        "agent_assignments": [],
        "dependency_graph": {},
        "generated_files": {},
        "validation_errors": [],
        "project_path": "/tmp/test",
        "retry_count": 0,
    }
    defaults.update(overrides)
    return defaults  # type: ignore[return-value]


def _sample_modules() -> ModuleList:
    return ModuleList(
        modules=[
            ModuleDefinition(
                name="auth",
                description="Authentication module",
                directory="src/auth/",
                dependencies=[],
                estimated_files=4,
            ),
            ModuleDefinition(
                name="database",
                description="Database models and connections",
                directory="src/database/",
                dependencies=[],
                estimated_files=3,
            ),
            ModuleDefinition(
                name="api",
                description="REST API routes",
                directory="src/api/",
                dependencies=["auth", "database"],
                estimated_files=5,
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_decompose_returns_modules() -> None:
    """Verify decompose_modules returns correctly shaped module list."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_modules())

    state = _make_state()
    result = await decompose_modules(state, llm=mock_llm)

    assert "modules" in result
    assert len(result["modules"]) == 3
    assert result["modules"][0]["name"] == "auth"
    assert result["modules"][2]["dependencies"] == ["auth", "database"]


@pytest.mark.asyncio()
async def test_decompose_calls_llm_with_correct_purpose() -> None:
    """Verify the LLM is called with purpose='generate_md'."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_modules())

    state = _make_state()
    await decompose_modules(state, llm=mock_llm)

    call_kwargs = mock_llm.complete_structured.call_args
    assert call_kwargs.kwargs["purpose"] == "generate_md"
    assert call_kwargs.kwargs["response_model"] is ModuleList


@pytest.mark.asyncio()
async def test_decompose_includes_decisions_in_prompt() -> None:
    """Verify decisions are included in the LLM message."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_modules())

    state = _make_state()
    await decompose_modules(state, llm=mock_llm)

    messages = mock_llm.complete_structured.call_args.kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "Python" in user_msg["content"]
    assert "language" in user_msg["content"]


@pytest.mark.asyncio()
async def test_decompose_empty_plan_raises() -> None:
    """Verify empty plan_document raises GenerateError."""
    mock_llm = AsyncMock()
    state = _make_state(plan_document="")

    with pytest.raises(GenerateError):
        await decompose_modules(state, llm=mock_llm)

    mock_llm.complete_structured.assert_not_called()


@pytest.mark.asyncio()
async def test_decompose_whitespace_plan_raises() -> None:
    """Verify whitespace-only plan_document raises GenerateError."""
    mock_llm = AsyncMock()
    state = _make_state(plan_document="   \n  ")

    with pytest.raises(GenerateError):
        await decompose_modules(state, llm=mock_llm)
