"""Integration tests validating 3 project types through the Execute Engine.

Each test mocks the LLM to return structured responses matching the
Supervisor Loop call sequence (SprintPlan -> AssignmentPlan ->
AgentCodeOutput -> ReviewResult -> RetrospectiveResult) and verifies
that the engine writes syntactically valid Python files to the workspace.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
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
# Shared helpers
# ---------------------------------------------------------------------------


async def _mock_validate(workspace_path: str, phase: int) -> list[ValidationResult]:
    """Return all-passing validation results."""
    return [
        ValidationResult(step="syntax", passed=True, errors=[], output="ok"),
        ValidationResult(step="lint", passed=True, errors=[], output="ok"),
        ValidationResult(step="typecheck", passed=True, errors=[], output="ok"),
        ValidationResult(step="unit_test", passed=True, errors=[], output="ok"),
    ]


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


def _make_retrospective(*, phase: int = 1, summary: str = "") -> RetrospectiveResult:
    return RetrospectiveResult(
        phase=phase,
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
        went_well=[summary or "All tasks passed first try"],
        went_wrong=[],
        root_causes=[],
        improvements=[],
        agent_performance={
            "Agent-A": {"success_rate": 1.0, "note": "Perfect"},
        },
    )


def _make_sprint_plan(
    *,
    goal: str,
    description: str,
    agent_id: str = "Agent-A",
) -> SprintPlan:
    return SprintPlan(
        sprint_number=1,
        sprint_goal=goal,
        tasks=[
            {
                "task_id": 1,
                "description": description,
                "agent_id": agent_id,
                "priority": 1,
                "risk": "low",
                "risk_reason": "",
                "prevention": "",
                "dependencies": [],
                "estimated_complexity": "low",
            },
        ],
        blocked_tasks=[],
        sprint_notes=goal,
    )


def _make_assignment_plan(agent_id: str = "Agent-A") -> AssignmentPlan:
    return AssignmentPlan(
        assignments=[
            {
                "agent_id": agent_id,
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
                "agents": [agent_id],
                "parallel": True,
                "after": "",
            },
        ],
    )


def _build_execute_mock_llm(
    sprint_plan: SprintPlan,
    assignment_plan: AssignmentPlan,
    agent_output: AgentCodeOutput,
    review: ReviewResult,
    retro: RetrospectiveResult,
) -> AsyncMock:
    """Build a mock LLM that returns the given sequence of structured responses."""
    mock_llm = AsyncMock()
    call_sequence: list[Any] = [
        sprint_plan,
        assignment_plan,
        agent_output,
        review,
        retro,
    ]
    mock_llm.complete_structured = AsyncMock(side_effect=call_sequence)
    mock_llm.cost_tracker = AsyncMock()
    mock_llm.cost_tracker.check_budget = lambda _: True
    return mock_llm


def _make_vibe_files(
    *,
    checklist_task: str,
    persona_desc: str,
    interface_snippet: str,
    spec_overview: str,
) -> dict[str, str]:
    """Build the minimal set of vibe files needed by the Execute Engine."""
    return {
        "checklist.md": f"# Checklist\n\n- [ ] #1 {checklist_task}\n",
        "shared-memory.md": "# Shared Memory\n\nNo exports yet.\n",
        "persona.md": (
            f"## Agent-A: Developer\n{persona_desc}\n"
            "Your directories: src/\n---\n"
        ),
        "interfaces.md": (
            f"# Interfaces\n\n```python\n{interface_snippet}\n```\n"
        ),
        "conventions.md": (
            "# Conventions\n- Python 3.12+\n- Type hints required\n- ruff format\n"
        ),
        "spec.md": f"# Spec\n\n## 1. Overview\n{spec_overview}\n",
    }


def _assert_py_compiles(file_path: Path) -> None:
    """Assert that a Python file compiles without syntax errors."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(file_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"py_compile failed for {file_path.name}: {result.stderr}"
    )


# ===========================================================================
# 1. TODO CRUD API (FastAPI + SQLite)
# ===========================================================================


@pytest.mark.asyncio()
@patch("architect.execute.engine._validate", side_effect=_mock_validate)
async def test_run_todo_crud_api_produces_valid_files(
    _mock_val: Any,
    tmp_path: Any,
) -> None:
    """Execute Engine produces a valid FastAPI TODO CRUD API project."""
    vibe_files = _make_vibe_files(
        checklist_task="Create TODO REST API with FastAPI and SQLite",
        persona_desc="You build FastAPI REST APIs with SQLite persistence.",
        interface_snippet="def create_todo(title: str) -> dict: ...",
        spec_overview="Build a TODO REST API with FastAPI and SQLite storage.",
    )

    main_content = (
        '"""TODO API with FastAPI."""\n'
        "\n"
        "from fastapi import FastAPI\n"
        "\n"
        "app = FastAPI(title='TODO API')\n"
        "\n"
        "\n"
        "@app.get('/todos')\n"
        "def list_todos() -> list[dict]:\n"
        "    return []\n"
    )
    models_content = (
        '"""Pydantic models for TODO API."""\n'
        "\n"
        "from pydantic import BaseModel\n"
        "\n"
        "\n"
        "class Todo(BaseModel):\n"
        "    id: int\n"
        "    title: str\n"
        "    done: bool = False\n"
    )
    routes_content = (
        '"""CRUD route handlers."""\n'
        "\n"
        "from fastapi import APIRouter\n"
        "\n"
        "router = APIRouter()\n"
        "todos: list[dict] = []\n"
        "\n"
        "\n"
        "@router.post('/todos')\n"
        "def create_todo(title: str) -> dict:\n"
        "    todo = {'id': len(todos) + 1, 'title': title, 'done': False}\n"
        "    todos.append(todo)\n"
        "    return todo\n"
    )

    agent_output = AgentCodeOutput(
        files=[
            CodeFile(path="main.py", content=main_content, action="create"),
            CodeFile(path="models.py", content=models_content, action="create"),
            CodeFile(path="routes.py", content=routes_content, action="create"),
        ],
        tests=[],
        shared_memory_updates=[],
        checklist_updates=[
            ChecklistUpdate(task_number=1, status="DONE", notes="created"),
        ],
        notes="FastAPI TODO CRUD API.",
    )

    mock_llm = _build_execute_mock_llm(
        sprint_plan=_make_sprint_plan(
            goal="Create TODO CRUD API",
            description="Create main.py, models.py, routes.py for FastAPI TODO API",
        ),
        assignment_plan=_make_assignment_plan(),
        agent_output=agent_output,
        review=_make_review_passed(),
        retro=_make_retrospective(summary="TODO API passed first try"),
    )

    workspace_dir = str(tmp_path / "workspace")
    engine = ExecuteEngine(mock_llm, workspace_dir)

    events: list[str] = []
    engine.on_progress(lambda event, _data: events.append(event))

    result = await engine.run(vibe_files)
    assert result is not None

    # Verify files exist
    ws = tmp_path / "workspace"
    for filename in ("main.py", "models.py", "routes.py"):
        fpath = ws / filename
        assert fpath.exists(), f"{filename} not written to workspace"
        _assert_py_compiles(fpath)

    # Verify content
    main_text = (ws / "main.py").read_text(encoding="utf-8")
    assert "FastAPI" in main_text

    models_text = (ws / "models.py").read_text(encoding="utf-8")
    assert "Todo" in models_text

    # Verify engine status
    status = engine.get_status()
    assert "system_status" in status
    assert "current_phase" in status

    # Verify file tree
    tree = engine.get_file_tree()
    assert any("main.py" in f for f in tree)
    assert any("models.py" in f for f in tree)
    assert any("routes.py" in f for f in tree)

    # Verify progress events
    assert "complete" in events


# ===========================================================================
# 2. CLI Tool (Typer + Rich)
# ===========================================================================


@pytest.mark.asyncio()
@patch("architect.execute.engine._validate", side_effect=_mock_validate)
async def test_run_cli_tool_produces_valid_files(
    _mock_val: Any,
    tmp_path: Any,
) -> None:
    """Execute Engine produces a valid Typer CLI tool project."""
    vibe_files = _make_vibe_files(
        checklist_task="Create CLI utility with Typer and Rich",
        persona_desc="You build CLI tools with Typer and Rich.",
        interface_snippet="def main(name: str) -> None: ...",
        spec_overview="Build a CLI utility using Typer for argument parsing and Rich for output.",
    )

    cli_content = (
        '"""CLI entry point using Typer."""\n'
        "\n"
        "import typer\n"
        "\n"
        "app = typer.Typer(name='mytool', help='A CLI utility.')\n"
        "\n"
        "\n"
        "@app.command()\n"
        "def hello(name: str = 'world') -> None:\n"
        "    typer.echo(f'Hello {name}!')\n"
        "\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    app()\n"
    )
    commands_content = (
        '"""Subcommands for the CLI tool."""\n'
        "\n"
        "import typer\n"
        "\n"
        "greet_app = typer.Typer()\n"
        "\n"
        "\n"
        "@greet_app.command()\n"
        "def greet(name: str) -> None:\n"
        "    typer.echo(f'Greetings, {name}!')\n"
    )
    utils_content = (
        '"""Helper utilities."""\n'
        "\n"
        "\n"
        "def format_name(name: str) -> str:\n"
        "    return name.strip().title()\n"
    )

    agent_output = AgentCodeOutput(
        files=[
            CodeFile(path="cli.py", content=cli_content, action="create"),
            CodeFile(path="commands.py", content=commands_content, action="create"),
            CodeFile(path="utils.py", content=utils_content, action="create"),
        ],
        tests=[],
        shared_memory_updates=[],
        checklist_updates=[
            ChecklistUpdate(task_number=1, status="DONE", notes="created"),
        ],
        notes="Typer CLI tool.",
    )

    mock_llm = _build_execute_mock_llm(
        sprint_plan=_make_sprint_plan(
            goal="Create CLI tool",
            description="Create cli.py, commands.py, utils.py for Typer CLI",
        ),
        assignment_plan=_make_assignment_plan(),
        agent_output=agent_output,
        review=_make_review_passed(),
        retro=_make_retrospective(summary="CLI tool passed first try"),
    )

    workspace_dir = str(tmp_path / "workspace")
    engine = ExecuteEngine(mock_llm, workspace_dir)

    events: list[str] = []
    engine.on_progress(lambda event, _data: events.append(event))

    result = await engine.run(vibe_files)
    assert result is not None

    # Verify files exist
    ws = tmp_path / "workspace"
    for filename in ("cli.py", "commands.py", "utils.py"):
        fpath = ws / filename
        assert fpath.exists(), f"{filename} not written to workspace"
        _assert_py_compiles(fpath)

    # Verify content
    cli_text = (ws / "cli.py").read_text(encoding="utf-8")
    assert "typer" in cli_text
    assert "app" in cli_text

    # Verify engine status
    status = engine.get_status()
    assert "system_status" in status
    assert "current_phase" in status

    # Verify file tree
    tree = engine.get_file_tree()
    assert any("cli.py" in f for f in tree)
    assert any("commands.py" in f for f in tree)
    assert any("utils.py" in f for f in tree)

    # Verify progress events
    assert "complete" in events


# ===========================================================================
# 3. Static Site Generator (Jinja2 + Markdown)
# ===========================================================================


@pytest.mark.asyncio()
@patch("architect.execute.engine._validate", side_effect=_mock_validate)
async def test_run_static_site_generator_produces_valid_files(
    _mock_val: Any,
    tmp_path: Any,
) -> None:
    """Execute Engine produces a valid Jinja2 static site generator project."""
    vibe_files = _make_vibe_files(
        checklist_task="Create static site generator with Jinja2 and Markdown",
        persona_desc="You build static site generators with Jinja2 templates.",
        interface_snippet="def build_site(source: str, output: str) -> None: ...",
        spec_overview="Build a static site generator using Jinja2 for templating and Markdown.",
    )

    builder_content = (
        '"""Main static site builder logic."""\n'
        "\n"
        "from pathlib import Path\n"
        "\n"
        "from jinja2 import Environment, FileSystemLoader\n"
        "\n"
        "\n"
        "def build_site(source: str, output: str) -> None:\n"
        "    src = Path(source)\n"
        "    out = Path(output)\n"
        "    out.mkdir(parents=True, exist_ok=True)\n"
        "    env = Environment(loader=FileSystemLoader(str(src / 'templates')))\n"
        "    template = env.get_template('base.html')\n"
        "    (out / 'index.html').write_text(template.render(title='Home'))\n"
    )
    templates_content = (
        '"""Jinja2 template helpers."""\n'
        "\n"
        "from jinja2 import Environment\n"
        "\n"
        "\n"
        "def create_env(template_dir: str) -> Environment:\n"
        "    from jinja2 import FileSystemLoader\n"
        "\n"
        "    return Environment(loader=FileSystemLoader(template_dir))\n"
    )
    config_content = (
        '"""Site configuration settings."""\n'
        "\n"
        "from dataclasses import dataclass\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class SiteConfig:\n"
        "    title: str = 'My Site'\n"
        "    base_url: str = 'http://localhost:8000'\n"
        "    output_dir: str = '_site'\n"
        "    template_dir: str = 'templates'\n"
    )

    agent_output = AgentCodeOutput(
        files=[
            CodeFile(path="builder.py", content=builder_content, action="create"),
            CodeFile(
                path="templates.py", content=templates_content, action="create"
            ),
            CodeFile(path="config.py", content=config_content, action="create"),
        ],
        tests=[],
        shared_memory_updates=[],
        checklist_updates=[
            ChecklistUpdate(task_number=1, status="DONE", notes="created"),
        ],
        notes="Static site generator.",
    )

    mock_llm = _build_execute_mock_llm(
        sprint_plan=_make_sprint_plan(
            goal="Create static site generator",
            description="Create builder.py, templates.py, config.py for site gen",
        ),
        assignment_plan=_make_assignment_plan(),
        agent_output=agent_output,
        review=_make_review_passed(),
        retro=_make_retrospective(summary="Site generator passed first try"),
    )

    workspace_dir = str(tmp_path / "workspace")
    engine = ExecuteEngine(mock_llm, workspace_dir)

    events: list[str] = []
    engine.on_progress(lambda event, _data: events.append(event))

    result = await engine.run(vibe_files)
    assert result is not None

    # Verify files exist
    ws = tmp_path / "workspace"
    for filename in ("builder.py", "templates.py", "config.py"):
        fpath = ws / filename
        assert fpath.exists(), f"{filename} not written to workspace"
        _assert_py_compiles(fpath)

    # Verify content
    builder_text = (ws / "builder.py").read_text(encoding="utf-8")
    assert "jinja2" in builder_text or "Jinja2" in builder_text

    # Verify engine status
    status = engine.get_status()
    assert "system_status" in status
    assert "current_phase" in status

    # Verify file tree
    tree = engine.get_file_tree()
    assert any("builder.py" in f for f in tree)
    assert any("templates.py" in f for f in tree)
    assert any("config.py" in f for f in tree)

    # Verify progress events
    assert "complete" in events
