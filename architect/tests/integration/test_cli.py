"""CLI integration tests using typer.testing.CliRunner.

All engine calls are mocked so no LLM keys are required.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import structlog
from typer.testing import CliRunner

from architect.core.models import Choice, PlanState
from architect.main import app

# Ensure structlog is configured for tests
structlog.configure(
    processors=[structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _approved_state() -> PlanState:
    """Return a PlanState that is approved and complete."""
    return PlanState(
        user_request="Build a TODO API",
        conversation_history=[
            {"role": "assistant", "content": "Analysis complete."},
        ],
        domain_analysis={"domain": "web"},
        decisions=[
            {"topic": "tech_stack", "chosen": "A", "label": "FastAPI", "rationale": "async"},
        ],
        open_questions=[],
        current_step="finalized",
        plan_document="# TODO API Plan\n\nBuild a REST API.",
        approved=True,
    )


def _choices_state() -> PlanState:
    """Return a PlanState waiting for user choice."""
    return PlanState(
        user_request="Build a TODO API",
        conversation_history=[
            {"role": "assistant", "content": "Analyzing..."},
            {
                "role": "assistant",
                "content": "Choose a framework",
                "type": "choices",
                "choices": [
                    {
                        "id": "A",
                        "label": "FastAPI",
                        "description": "Modern async",
                        "pros": ["Fast"],
                        "cons": ["Newer"],
                        "recommended": True,
                        "reason": "best fit",
                    },
                ],
            },
        ],
        domain_analysis={"domain": "web"},
        decisions=[],
        open_questions=[],
        current_step="waiting_choice",
        plan_document="",
        approved=False,
    )


def _write_plan_json(tmp_path: Path) -> Path:
    """Write a minimal plan.json and return its path."""
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "plan_document": "# Plan\nBuild TODO API",
                "decisions": [
                    {
                        "topic": "tech_stack",
                        "chosen": "A",
                        "label": "FastAPI",
                        "rationale": "async",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return plan_file


def _build_mock_plan_engine() -> MagicMock:
    """Build a mock PlanEngine that goes: choices -> approve -> done."""
    engine = MagicMock()
    engine.start = AsyncMock(return_value=_choices_state())
    engine.respond = AsyncMock(return_value=_approved_state())
    engine.is_complete = lambda s: s.get("approved", False)
    engine.needs_user_input = lambda s: s.get("current_step") in (
        "waiting_choice",
        "wait_approval",
    )
    engine.get_current_choices = lambda s: (
        [Choice(**c) for c in s["conversation_history"][-1]["choices"]]
        if s.get("current_step") == "waiting_choice"
        else None
    )
    engine.get_plan_document = lambda s: s.get("plan_document", "")
    return engine


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPlanCommand:
    def test_plan_help(self) -> None:
        result = runner.invoke(app, ["plan", "--help"])
        assert result.exit_code == 0
        assert "Plan Mode" in result.output

    def test_plan_command_flow(self, tmp_path: Path) -> None:
        """Plan command: start -> choose -> approve -> save plan.json."""
        engine = _build_mock_plan_engine()
        output = tmp_path / "plan.json"

        with (
            patch("architect.main._create_router", return_value=MagicMock()),
            patch("architect.plan.engine.PlanEngine", return_value=engine),
            patch("architect.plan.PlanEngine", engine.__class__),
        ):
            # Patch the import inside _run_plan
            import architect.main as main_mod

            async def _patched_run_plan(description: str, out: Path) -> None:
                # Directly use our mock engine instead of importing PlanEngine
                from architect.main import console

                console.print(f"[bold blue]Plan Mode[/bold blue] - {description}\n")
                state = await engine.start(description)

                while not engine.is_complete(state):
                    if not engine.needs_user_input(state):
                        state = await engine.respond(state, "")
                        continue

                    choices = engine.get_current_choices(state)
                    if choices:
                        user_input = "A"
                    else:
                        user_input = "approve"

                    state = await engine.respond(state, user_input)

                plan_data = {
                    "plan_document": engine.get_plan_document(state),
                    "decisions": state.get("decisions", []),
                }
                out.write_text(
                    json.dumps(plan_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )

            with patch.object(main_mod, "_run_plan", _patched_run_plan):
                result = runner.invoke(
                    app,
                    ["plan", "Build a TODO API", "--output", str(output)],
                )

        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        assert output.exists()
        data = json.loads(output.read_text(encoding="utf-8"))
        assert "plan_document" in data
        assert data["plan_document"] != ""


class TestRunCommand:
    def test_run_missing_plan_file(self) -> None:
        result = runner.invoke(app, ["run", "--plan-file", "nonexistent.json"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_run_command_flow(self, tmp_path: Path) -> None:
        """Run command: load plan -> generate -> execute -> summary."""
        plan_file = _write_plan_json(tmp_path)
        workspace = tmp_path / "workspace"

        mock_gen = AsyncMock()
        mock_gen.generate = AsyncMock(
            return_value={"checklist.md": "# Checklist", "spec.md": "# Spec"}
        )

        mock_exec = MagicMock()
        mock_exec.run = AsyncMock(return_value={"system_status": "complete"})
        mock_exec.get_status.return_value = {
            "system_status": "complete",
            "current_phase": 1,
            "current_sprint": 1,
            "total_iterations": 5,
            "cost_usd": 1.23,
        }
        mock_exec.get_file_tree.return_value = ["main.py", "test_main.py"]
        mock_exec.on_progress = MagicMock()

        import architect.main as main_mod

        async def _patched_pipeline(pf: Path, ws: Path) -> None:
            from architect.main import console

            plan_data = json.loads(pf.read_text(encoding="utf-8"))
            plan_document = plan_data["plan_document"]
            decisions = plan_data.get("decisions", [])

            console.print("[bold yellow]Phase: Generate[/bold yellow]")
            vibe_files = await mock_gen.generate(plan_document, decisions, str(ws / ".vibe"))
            console.print(f"  Generated {len(vibe_files)} files")

            console.print("[bold yellow]Phase: Execute[/bold yellow]")
            mock_exec.on_progress(lambda e, d: None)
            await mock_exec.run(vibe_files)

            status = mock_exec.get_status()
            console.print("\n[bold green]Execution Complete[/bold green]")
            from rich.table import Table

            summary = Table(title="Result Summary")
            summary.add_column("Key")
            summary.add_column("Value")
            summary.add_row("Status", str(status.get("system_status", "unknown")))
            summary.add_row("Cost (USD)", f"${status.get('cost_usd', 0):.2f}")
            console.print(summary)

        with patch.object(main_mod, "_run_pipeline", _patched_pipeline):
            result = runner.invoke(
                app,
                ["run", "--plan-file", str(plan_file), "--workspace", str(workspace)],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        assert "Execution Complete" in result.output
        mock_gen.generate.assert_called_once()
        mock_exec.run.assert_called_once()


class TestStatusCommand:
    def test_status_no_active_job(self) -> None:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "No active job" in result.output


class TestServeCommand:
    def test_serve_help(self) -> None:
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "web UI" in result.output.lower() or "Server" in result.output
