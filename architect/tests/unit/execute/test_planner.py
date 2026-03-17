"""Unit tests for supervisor/planner.py — plan_sprint."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from architect.core.exceptions import ExecuteError
from architect.execute.supervisor.planner import SprintPlan, plan_sprint
from tests.unit.execute.conftest import make_execute_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_sprint_plan() -> SprintPlan:
    return SprintPlan(
        sprint_number=1,
        sprint_goal="Implement execute states and planner",
        tasks=[
            {
                "task_id": 36,
                "description": "execute/states.py",
                "agent_id": "Agent-E",
                "priority": 1,
                "risk": "low",
                "risk_reason": "",
                "prevention": "",
                "dependencies": [],
                "estimated_complexity": "low",
            },
            {
                "task_id": 37,
                "description": "supervisor/planner.py",
                "agent_id": "Agent-E",
                "priority": 2,
                "risk": "medium",
                "risk_reason": "LLM prompt complexity",
                "prevention": "Include explicit JSON schema",
                "dependencies": [36],
                "estimated_complexity": "high",
            },
        ],
        blocked_tasks=[],
        sprint_notes="Focus on foundation modules first.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_plan_sprint_returns_sprint_plan() -> None:
    """Verify plan_sprint returns correctly shaped result."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_sprint_plan())

    state = make_execute_state()
    result = await plan_sprint(state, llm=mock_llm)

    assert "sprint_plan" in result
    assert "sprint_tasks" in result
    assert len(result["sprint_tasks"]) == 2
    assert result["sprint_plan"]["sprint_goal"] == "Implement execute states and planner"


@pytest.mark.asyncio()
async def test_plan_sprint_calls_llm_with_supervisor_purpose() -> None:
    """Verify the LLM is called with purpose='supervisor'."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_sprint_plan())

    state = make_execute_state()
    await plan_sprint(state, llm=mock_llm)

    call_kwargs = mock_llm.complete_structured.call_args
    assert call_kwargs.kwargs["purpose"] == "supervisor"
    assert call_kwargs.kwargs["response_model"] is SprintPlan


@pytest.mark.asyncio()
async def test_plan_sprint_includes_checklist_in_prompt() -> None:
    """Verify checklist.md content appears in the user message."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_sprint_plan())

    state = make_execute_state()
    await plan_sprint(state, llm=mock_llm)

    messages = mock_llm.complete_structured.call_args.kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "#36" in user_msg["content"]
    assert "checklist" in user_msg["content"].lower()


@pytest.mark.asyncio()
async def test_plan_sprint_includes_error_history() -> None:
    """Verify error_history is included when non-empty."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_sprint_plan())

    state = make_execute_state(
        error_history=[{"error": "ImportError", "sprint": 1}]
    )
    await plan_sprint(state, llm=mock_llm)

    messages = mock_llm.complete_structured.call_args.kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "ImportError" in user_msg["content"]


@pytest.mark.asyncio()
async def test_plan_sprint_missing_checklist_raises() -> None:
    """Verify empty checklist raises ExecuteError."""
    mock_llm = AsyncMock()
    state = make_execute_state(vibe_files={})

    with pytest.raises(ExecuteError):
        await plan_sprint(state, llm=mock_llm)

    mock_llm.complete_structured.assert_not_called()


@pytest.mark.asyncio()
async def test_plan_sprint_increments_sprint_number() -> None:
    """Verify current_sprint is incremented in the result."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_sprint_plan())

    state = make_execute_state(current_sprint=2)
    result = await plan_sprint(state, llm=mock_llm)

    assert result["current_sprint"] == 3
