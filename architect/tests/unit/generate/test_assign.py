"""Unit tests for the assign_agents node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from architect.core.models import AgentAssignment, GenerateState
from architect.generate.nodes.assign import AssignmentList, assign_agents


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides: Any) -> GenerateState:
    defaults: dict[str, Any] = {
        "plan_document": "# Test Plan",
        "decisions": [{"topic": "language", "chosen": "Python", "label": "Python", "rationale": "default"}],
        "modules": [
            {"name": "core", "description": "Core module", "directory": "src/core/", "dependencies": [], "estimated_files": 3},
            {"name": "api", "description": "API routes", "directory": "src/api/", "dependencies": ["core"], "estimated_files": 5},
            {"name": "auth", "description": "Auth module", "directory": "src/auth/", "dependencies": ["core"], "estimated_files": 4},
        ],
        "agent_assignments": [],
        "dependency_graph": {},
        "generated_files": {},
        "validation_errors": [],
        "project_path": "/tmp/test",
        "retry_count": 0,
    }
    defaults.update(overrides)
    return defaults  # type: ignore[return-value]


def _sample_assignments() -> AssignmentList:
    return AssignmentList(
        assignments=[
            AgentAssignment(
                agent_id="Agent-A",
                persona_name="Core Architect",
                modules=["core"],
                phase=1,
                can_parallel_with=[],
            ),
            AgentAssignment(
                agent_id="Agent-B",
                persona_name="API Engineer",
                modules=["api", "auth"],
                phase=2,
                can_parallel_with=[],
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_assign_returns_assignments_and_graph() -> None:
    """Verify assign_agents returns both assignments and dependency graph."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_assignments())

    state = _make_state()
    result = await assign_agents(state, llm=mock_llm)

    assert "agent_assignments" in result
    assert "dependency_graph" in result
    assert len(result["agent_assignments"]) == 2
    assert result["agent_assignments"][0]["agent_id"] == "Agent-A"


@pytest.mark.asyncio()
async def test_assign_builds_correct_dependency_graph() -> None:
    """Verify dependency graph is built from module dependencies."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_assignments())

    state = _make_state()
    result = await assign_agents(state, llm=mock_llm)

    graph = result["dependency_graph"]
    assert graph["core"] == []
    assert graph["api"] == ["core"]
    assert graph["auth"] == ["core"]


@pytest.mark.asyncio()
async def test_assign_calls_llm_with_correct_purpose() -> None:
    """Verify the LLM is called with purpose='generate_md'."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_assignments())

    state = _make_state()
    await assign_agents(state, llm=mock_llm)

    call_kwargs = mock_llm.complete_structured.call_args
    assert call_kwargs.kwargs["purpose"] == "generate_md"
    assert call_kwargs.kwargs["response_model"] is AssignmentList


@pytest.mark.asyncio()
async def test_assign_includes_modules_in_prompt() -> None:
    """Verify modules are included in the LLM message."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_assignments())

    state = _make_state()
    await assign_agents(state, llm=mock_llm)

    messages = mock_llm.complete_structured.call_args.kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "core" in user_msg["content"]
    assert "api" in user_msg["content"]
