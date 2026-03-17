"""Full pipeline E2E test: Plan -> Generate -> Execute.

All LLM calls are mocked. Validates the entire flow from user request
through to code generation in the workspace.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from architect.core.models import (
    AgentCodeOutput,
    ChecklistUpdate,
    Choice,
    CodeFile,
    DomainAnalysis,
    PlanState,
    ReviewResult,
    ValidationResult,
)
from architect.execute.engine import ExecuteEngine, RetrospectiveResult
from architect.execute.supervisor.assigner import AssignmentPlan
from architect.execute.supervisor.planner import SprintPlan
from architect.generate import GenerateEngine
from architect.plan import PlanEngine
from architect.plan.states import DECISION_TOPICS

# ---------------------------------------------------------------------------
# Mock data factories
# ---------------------------------------------------------------------------


def _make_domain_analysis() -> DomainAnalysis:
    return DomainAnalysis(
        domain="Web API",
        project_type="Backend API",
        core_features=["CRUD operations", "TODO management"],
        implied_requirements=["data validation", "error handling"],
        complexity="small",
        estimated_agents=2,
        initial_questions=["Which database?"],
    )


def _make_choices(topic: str) -> list[Choice]:
    return [
        Choice(
            id="A",
            label=f"Option A for {topic}",
            description=f"Best option for {topic}",
            pros=["Simple", "Fast"],
            cons=["Limited"],
            recommended=True,
            reason="Best fit",
        ),
        Choice(
            id="B",
            label=f"Option B for {topic}",
            description=f"Alternative for {topic}",
            pros=["Flexible"],
            cons=["Complex"],
        ),
    ]


_GENERATED_VIBE_FILES: dict[str, str] = {
    "checklist.md": (
        "# Checklist\n\n"
        "- [ ] #1 Create main.py - FastAPI application\n"
    ),
    "shared-memory.md": "# Shared Memory\n\nNo exports yet.\n",
    "persona.md": (
        "## Agent-A: Core Developer\n"
        "You build FastAPI applications.\n"
        "Your directories: src/\n---\n"
    ),
    "interfaces.md": (
        "# Interfaces\n\n"
        "```python\n"
        "def create_todo(title: str) -> dict: ...\n"
        "```\n"
    ),
    "conventions.md": (
        "# Conventions\n- Python 3.12+\n- Type hints required\n- ruff format\n"
    ),
    "spec.md": (
        "# Spec\n\n## 1. Overview\n"
        "Build a TODO REST API with FastAPI.\n"
    ),
}


def _make_sprint_plan() -> SprintPlan:
    return SprintPlan(
        sprint_number=1,
        sprint_goal="Create TODO API",
        tasks=[
            {
                "task_id": 1,
                "description": "Create main.py with FastAPI app",
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
        sprint_notes="Simple TODO API.",
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
    main_content = (
        '"""TODO API with FastAPI."""\n'
        "\n"
        "from fastapi import FastAPI\n"
        "\n"
        "app = FastAPI(title='TODO API')\n"
        "todos: list[dict] = []\n"
        "\n"
        "\n"
        "@app.get('/todos')\n"
        "def list_todos() -> list[dict]:\n"
        "    return todos\n"
        "\n"
        "\n"
        "@app.post('/todos')\n"
        "def create_todo(title: str) -> dict:\n"
        "    todo = {'id': len(todos) + 1, 'title': title, 'done': False}\n"
        "    todos.append(todo)\n"
        "    return todo\n"
    )
    return AgentCodeOutput(
        files=[CodeFile(path="main.py", content=main_content, action="create")],
        tests=[],
        shared_memory_updates=[],
        checklist_updates=[
            ChecklistUpdate(task_number=1, status="DONE", notes="created"),
        ],
        notes="FastAPI TODO app.",
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
            "total_cost_usd": 0.2,
            "total_llm_calls": 5,
        },
        went_well=["TODO API passed first try"],
        went_wrong=[],
        root_causes=[],
        improvements=[],
        agent_performance={
            "Agent-A": {"success_rate": 1.0, "note": "Perfect"},
        },
    )


async def _mock_validate(workspace_path: str, phase: int) -> list[ValidationResult]:
    """Return all-passing validation results."""
    return [
        ValidationResult(step="syntax", passed=True, errors=[], output="ok"),
        ValidationResult(step="lint", passed=True, errors=[], output="ok"),
        ValidationResult(step="typecheck", passed=True, errors=[], output="ok"),
        ValidationResult(step="unit_test", passed=True, errors=[], output="ok"),
    ]


# ---------------------------------------------------------------------------
# Build mock LLM for Execute phase
# ---------------------------------------------------------------------------


def _build_execute_mock_llm() -> AsyncMock:
    """Mock LLM for Execute Engine with correct call sequence."""
    mock_llm = AsyncMock()
    call_sequence: list[Any] = [
        _make_sprint_plan(),
        _make_assignment_plan(),
        _make_agent_output(),
        _make_review_passed(),
        _make_retrospective(),
    ]
    mock_llm.complete_structured = AsyncMock(side_effect=call_sequence)
    mock_llm.cost_tracker = AsyncMock()
    mock_llm.cost_tracker.check_budget = lambda _: True
    return mock_llm


# ---------------------------------------------------------------------------
# Full Pipeline Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
@patch("architect.execute.engine._validate", side_effect=_mock_validate)
async def test_full_pipeline_plan_generate_execute(
    _mock_val: Any,
    tmp_path: Any,
) -> None:
    """Test the full Plan -> Generate -> Execute pipeline.

    Plan and Generate engines are mocked at the engine level.
    Execute engine uses mock LLM with the standard call sequence.

    Verifies:
    1. Plan produces a plan document and decisions.
    2. Generate produces vibe files.
    3. Execute creates code in the workspace.
    4. Generated main.py contains expected content.
    """
    # --- Plan (mocked) ---
    mock_plan_llm = AsyncMock()
    plan_engine = PlanEngine(mock_plan_llm)

    # Mock the graph to return an approved state directly
    approved_state: PlanState = {
        "user_request": "Python TODO REST API with FastAPI",
        "conversation_history": [
            {"role": "user", "content": "Python TODO REST API with FastAPI"},
            {"role": "assistant", "content": "I'll create a TODO API plan."},
        ],
        "domain_analysis": _make_domain_analysis().model_dump(),
        "decisions": [
            {"topic": t, "chosen": "A", "label": f"Option A for {t}", "rationale": "Best fit"}
            for t in DECISION_TOPICS
        ],
        "open_questions": [],
        "current_step": "finalized",
        "plan_document": "# TODO API Plan\n\nBuild a FastAPI TODO REST API with in-memory storage.",
        "approved": True,
    }

    assert plan_engine.is_complete(approved_state)
    plan_document = plan_engine.get_plan_document(approved_state)
    decisions = approved_state["decisions"]
    assert plan_document != ""
    assert len(decisions) == len(DECISION_TOPICS)

    # --- Generate (mocked) ---
    mock_gen_llm = AsyncMock()
    gen_engine = GenerateEngine(mock_gen_llm)

    # Mock generate to return predefined vibe files
    gen_engine.generate = AsyncMock(return_value=_GENERATED_VIBE_FILES)
    vibe_path = str(tmp_path / "vibe_output")
    vibe_files = await gen_engine.generate(plan_document, decisions, vibe_path)

    assert len(vibe_files) >= 6
    assert "checklist.md" in vibe_files
    assert "spec.md" in vibe_files

    # --- Execute (mock LLM, real engine) ---
    exec_llm = _build_execute_mock_llm()
    workspace_dir = str(tmp_path / "workspace")
    exec_engine = ExecuteEngine(exec_llm, workspace_dir)

    events: list[str] = []
    exec_engine.on_progress(lambda event, _data: events.append(event))

    result = await exec_engine.run(vibe_files)

    # -- Engine completed --
    assert result is not None

    # -- main.py was written --
    main_path = tmp_path / "workspace" / "main.py"
    assert main_path.exists(), "main.py not written to workspace"
    content = main_path.read_text(encoding="utf-8")
    assert "FastAPI" in content
    assert "todo" in content.lower()

    # -- Status API --
    status = exec_engine.get_status()
    assert "system_status" in status
    assert "current_phase" in status

    # -- File tree --
    tree = exec_engine.get_file_tree()
    assert any("main.py" in f for f in tree)

    # -- Progress events fired --
    assert "complete" in events


@pytest.mark.asyncio()
async def test_pipeline_generate_empty_plan_raises(tmp_path: Any) -> None:
    """GenerateEngine should reject an empty plan document."""
    from architect.core.exceptions import GenerateError

    mock_llm = AsyncMock()
    gen_engine = GenerateEngine(mock_llm)

    with pytest.raises(GenerateError):
        await gen_engine.generate("", [], str(tmp_path / "out"))
