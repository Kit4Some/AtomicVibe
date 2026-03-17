"""Unit tests for validator.py — validate and all_passed."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from architect.core.exceptions import ValidationError
from architect.core.models import ValidationResult
from architect.execute.validator import all_passed, validate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_subprocess(rc: int = 0, stdout: str = "", stderr: str = ""):
    """Return a coroutine that simulates _run_subprocess."""
    async def _mock(*args, **kwargs):
        return (rc, stdout, stderr)
    return _mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_validate_runs_four_steps(tmp_path) -> None:
    """Non-phase-end validation runs syntax, lint, typecheck, unit_test."""
    # Create minimal workspace structure
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.py").write_text("print('hi')\n")
    tests = tmp_path / "tests"
    tests.mkdir()

    with patch(
        "architect.execute.validator._run_subprocess",
        side_effect=_ok_subprocess(),
    ):
        results = await validate(str(tmp_path), phase=1)

    assert len(results) == 4
    steps = [r.step for r in results]
    assert "syntax" in steps
    assert "lint" in steps
    assert "typecheck" in steps
    assert "unit_test" in steps


@pytest.mark.asyncio()
async def test_validate_includes_integration_at_phase_end(tmp_path) -> None:
    """phase=-1 should also run integration tests (5 steps total)."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.py").write_text("print('hi')\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    integration = tests / "integration"
    integration.mkdir()

    with patch(
        "architect.execute.validator._run_subprocess",
        side_effect=_ok_subprocess(),
    ):
        results = await validate(str(tmp_path), phase=-1)

    assert len(results) == 5
    assert any(r.step == "integration" for r in results)


@pytest.mark.asyncio()
async def test_all_passed_returns_true_when_all_pass() -> None:
    """all_passed returns True when every result passed."""
    results = [
        ValidationResult(step="syntax", passed=True, errors=[], output="ok"),
        ValidationResult(step="lint", passed=True, errors=[], output="ok"),
    ]
    assert all_passed(results) is True


@pytest.mark.asyncio()
async def test_all_passed_returns_false_when_any_fails() -> None:
    """all_passed returns False if any result failed."""
    results = [
        ValidationResult(step="syntax", passed=True, errors=[], output="ok"),
        ValidationResult(step="lint", passed=False, errors=[{"message": "E501"}], output="err"),
    ]
    assert all_passed(results) is False


@pytest.mark.asyncio()
async def test_validate_handles_subprocess_timeout(tmp_path) -> None:
    """Subprocess timeout → passed=False with timeout message."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.py").write_text("x = 1\n")
    tests = tmp_path / "tests"
    tests.mkdir()

    async def _timeout_mock(*args, **kwargs):
        return (1, "", "Process timed out after 300s")

    with patch(
        "architect.execute.validator._run_subprocess",
        side_effect=_timeout_mock,
    ):
        results = await validate(str(tmp_path), phase=1)

    # At least one should have failed due to "timeout" in stderr
    assert any(not r.passed for r in results)


@pytest.mark.asyncio()
async def test_validate_workspace_not_found_raises() -> None:
    """Nonexistent workspace path raises ValidationError."""
    with pytest.raises(ValidationError):
        await validate("/nonexistent/path/xyz", phase=1)
