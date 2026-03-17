"""End-to-end integration test for the Execute Engine Supervisor Loop.

Uses mock LLM to drive a single sprint through the full loop:
  read_state → plan_sprint → assess_risk → assign_tasks → dispatch_agents
  → review_code → validate → update_state → retrospective → adjust_plan → END

The validator is patched to return all-passing results so the happy-path
flow completes without real subprocess calls.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from architect.core.models import (
    AgentCodeOutput,
    ChecklistUpdate,
    CodeFile,
    ReviewResult,
    ValidationResult,
)
from architect.execute.engine import ExecuteEngine, RetrospectiveResult
from architect.execute.supervisor.assigner import AssignmentPlan
from architect.execute.supervisor.planner import SprintPlan

# ---------------------------------------------------------------------------
# Mock LLM response factory
# ---------------------------------------------------------------------------


def _make_sprint_plan() -> SprintPlan:
    return SprintPlan(
        sprint_number=1,
        sprint_goal="Create hello world CLI",
        tasks=[
            {
                "task_id": 1,
                "description": "Create hello.py",
                "agent_id": "Agent-A",
                "priority": 1,
                "risk": "low",
                "risk_reason": "",
                "prevention": "",
                "dependencies": [],
                "estimated_complexity": "low",
            },
        ],
        blocked_tasks=[],
        sprint_notes="Single-file hello world.",
    )


def _make_assignment_plan() -> AssignmentPlan:
    return AssignmentPlan(
        assignments=[
            {
                "agent_id": "Agent-A",
                "task_ids": [1],
                "execution_order": 1,
                "parallel_group": "group-1",
                "injected_knowledge": [],
                "prevention_instructions": "",
            },
        ],
        execution_plan=[
            {
                "group": "group-1",
                "agents": ["Agent-A"],
                "parallel": True,
                "after": "",
            },
        ],
    )


def _make_agent_output() -> AgentCodeOutput:
    hello_content = (
        '"""Hello World CLI."""\n'
        "\n"
        "\n"
        "def main() -> None:\n"
        '    print("Hello, World!")\n'
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    main()\n"
    )
    return AgentCodeOutput(
        files=[
            CodeFile(
                path="hello.py",
                content=hello_content,
                action="create",
            ),
        ],
        tests=[],
        shared_memory_updates=[],
        checklist_updates=[
            ChecklistUpdate(
                task_number=1, status="DONE", notes="created",
            ),
        ],
        notes="Hello world script.",
    )


def _make_review_passed() -> ReviewResult:
    return ReviewResult(
        overall_score=4.5,
        dimensions={
            "interface_compliance": {"score": 5, "issues": []},
            "convention_adherence": {"score": 5, "issues": []},
            "architecture_consistency": {"score": 4, "issues": []},
            "implementation_quality": {"score": 4, "issues": []},
            "security": {"score": 5, "issues": []},
            "testability": {"score": 4, "issues": []},
        },
        critical_issues=[],
        suggestions=[],
        revision_instructions="",
    )


def _make_retrospective() -> RetrospectiveResult:
    return RetrospectiveResult(
        phase=1,
        metrics={
            "tasks_total": 1,
            "tasks_first_pass": 1,
            "tasks_with_fixes": 0,
            "tasks_failed": 0,
            "first_pass_rate": 1.0,
            "avg_fix_iterations": 0.0,
            "total_cost_usd": 0.1,
            "total_llm_calls": 5,
        },
        went_well=["Hello world passed first try"],
        went_wrong=[],
        root_causes=[],
        improvements=[],
        agent_performance={
            "Agent-A": {"success_rate": 1.0, "note": "Perfect"},
        },
    )


# ---------------------------------------------------------------------------
# Mock validator — always passes
# ---------------------------------------------------------------------------


async def _mock_validate(workspace_path: str, phase: int) -> list[ValidationResult]:
    """Return all-passing validation results without running subprocesses."""
    return [
        ValidationResult(step="syntax", passed=True, errors=[], output="ok"),
        ValidationResult(step="lint", passed=True, errors=[], output="ok"),
        ValidationResult(
            step="typecheck", passed=True, errors=[], output="ok",
        ),
        ValidationResult(
            step="unit_test", passed=True, errors=[], output="ok",
        ),
    ]


# ---------------------------------------------------------------------------
# Mock LLM setup
# ---------------------------------------------------------------------------


def _build_mock_llm() -> AsyncMock:
    """Create a mock LLM that returns appropriate responses per purpose."""
    mock_llm = AsyncMock()

    call_sequence: list[Any] = [
        _make_sprint_plan(),       # 1. plan_sprint
        _make_assignment_plan(),   # 2. assign_tasks
        _make_agent_output(),      # 3. dispatch (code_generation)
        _make_review_passed(),     # 4. review_code
        _make_retrospective(),     # 5. retrospective
    ]

    mock_llm.complete_structured = AsyncMock(side_effect=call_sequence)
    mock_llm.cost_tracker = AsyncMock()
    mock_llm.cost_tracker.check_budget = lambda _: True

    return mock_llm


# ---------------------------------------------------------------------------
# Vibe files fixture
# ---------------------------------------------------------------------------


_VIBE_FILES: dict[str, str] = {
    "checklist.md": (
        "# Checklist — Phase 1\n\n"
        "- [ ] #1 Create hello.py — Hello World CLI\n"
    ),
    "shared-memory.md": "# Shared Memory\n\nNo exports yet.\n",
    "persona.md": (
        "## Agent-A: Core Architect\n"
        "You are a Python developer specialising in CLI tools.\n"
        "Your directories: src/, main.py\n"
        "---\n"
    ),
    "interfaces.md": (
        "# Interfaces\n\n"
        "## CLI Module\n"
        "```python\n"
        "def main() -> None: ...\n"
        "```\n"
    ),
    "conventions.md": (
        "# Conventions\n"
        "- Python 3.12+\n"
        "- Type hints required\n"
        "- ruff format\n"
    ),
    "spec.md": (
        "# Spec\n\n"
        "## 1. Overview\n"
        "Build a Hello World CLI that prints a greeting.\n"
    ),
}


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
@patch("architect.execute.engine._validate", side_effect=_mock_validate)
async def test_execute_engine_hello_world(
    _mock_val: Any,
    tmp_path: Any,
) -> None:
    """Run the full Supervisor Loop for a Hello World project.

    Verifies:
    1. Engine completes without errors.
    2. hello.py is written to the workspace.
    3. hello.py is syntactically valid Python.
    4. Status API returns expected keys.
    """
    mock_llm = _build_mock_llm()
    workspace_dir = str(tmp_path / "workspace")

    engine = ExecuteEngine(mock_llm, workspace_dir)
    result = await engine.run(_VIBE_FILES)

    # -- Engine completed --
    assert result is not None
    assert result.get("system_status") in (
        "running", "paused", "complete",
    )

    # -- hello.py was written --
    hello_path = tmp_path / "workspace" / "hello.py"
    assert hello_path.exists(), "hello.py not written to workspace"

    content = hello_path.read_text(encoding="utf-8")
    assert "Hello" in content
    assert "def main" in content

    # -- hello.py is valid Python syntax --
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", str(hello_path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"Syntax error in hello.py: {proc.stderr}"
    )

    # -- Status API works --
    status = engine.get_status()
    assert "system_status" in status
    assert "current_phase" in status
    assert "current_sprint" in status

    # -- File tree includes generated file --
    tree = engine.get_file_tree()
    assert any("hello.py" in f for f in tree)


@pytest.mark.asyncio()
async def test_execute_engine_empty_vibe_raises(tmp_path: Any) -> None:
    """Empty vibe_files should raise ExecuteError."""
    from architect.core.exceptions import ExecuteError

    mock_llm = AsyncMock()
    engine = ExecuteEngine(mock_llm, str(tmp_path / "workspace"))

    with pytest.raises(ExecuteError):
        await engine.run({})


@pytest.mark.asyncio()
async def test_execute_engine_get_status_idle(tmp_path: Any) -> None:
    """Before run(), get_status() returns idle."""
    mock_llm = AsyncMock()
    engine = ExecuteEngine(mock_llm, str(tmp_path / "workspace"))

    status = engine.get_status()
    assert status["system_status"] == "idle"


@pytest.mark.asyncio()
@patch("architect.execute.engine._validate", side_effect=_mock_validate)
async def test_execute_engine_progress_callback(
    _mock_val: Any,
    tmp_path: Any,
) -> None:
    """on_progress callback is invoked when engine completes."""
    mock_llm = _build_mock_llm()
    engine = ExecuteEngine(mock_llm, str(tmp_path / "workspace"))

    events: list[str] = []
    engine.on_progress(lambda event, _data: events.append(event))

    await engine.run(_VIBE_FILES)

    assert "complete" in events
