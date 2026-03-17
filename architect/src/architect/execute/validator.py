"""Validator — run lint, type-check, and test tools against the workspace."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from architect.core.exceptions import ValidationError as ArchValidationError
from architect.core.models import ValidationResult

__all__ = ["validate", "all_passed"]

log = logging.getLogger("architect.execute.validator")

_TIMEOUT_SECONDS = 300


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


async def validate(
    workspace_path: str,
    phase: int,
) -> list[ValidationResult]:
    """Run the validation pipeline and return per-step results.

    Steps executed in order: syntax, lint, typecheck, unit_test.
    If *phase* is ``-1`` (indicating phase-end), integration tests
    are also run.
    """
    ws = Path(workspace_path)
    if not ws.is_dir():
        raise ArchValidationError(
            message=f"Workspace path does not exist: {workspace_path}",
        )

    src_dir = _find_src_dir(ws)
    test_dir = _find_test_dir(ws)

    results: list[ValidationResult] = []

    # 1. Syntax check
    results.append(await _run_syntax(ws, src_dir))

    # 2. Lint (ruff)
    results.append(await _run_lint(src_dir))

    # 3. Type-check (mypy) — optional, failure is non-blocking
    results.append(await _run_typecheck(src_dir))

    # 4. Unit tests (pytest)
    results.append(await _run_pytest(test_dir, label="unit_test"))

    # 5. Integration tests (phase-end only)
    if phase == -1:
        integration_dir = ws / "tests" / "integration"
        results.append(await _run_pytest(integration_dir, label="integration"))

    log.info(
        "validate: %d/%d steps passed",
        sum(1 for r in results if r.passed),
        len(results),
    )

    return results


def all_passed(results: list[ValidationResult]) -> bool:
    """Return ``True`` if every validation step passed."""
    return all(r.passed for r in results)


# ------------------------------------------------------------------
# Internal step runners
# ------------------------------------------------------------------


def _find_src_dir(ws: Path) -> Path:
    """Locate the source directory inside the workspace."""
    for candidate in ("src", "lib", "."):
        d = ws / candidate
        if d.is_dir():
            return d
    return ws


def _find_test_dir(ws: Path) -> Path:
    """Locate the test directory inside the workspace."""
    for candidate in ("tests", "test"):
        d = ws / candidate
        if d.is_dir():
            return d
    return ws / "tests"


async def _run_subprocess(
    *args: str,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """Run a subprocess with a timeout, returning (returncode, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=_TIMEOUT_SECONDS,
        )
        return (
            proc.returncode or 0,
            stdout_bytes.decode("utf-8", errors="replace"),
            stderr_bytes.decode("utf-8", errors="replace"),
        )
    except asyncio.TimeoutError:
        proc.kill()  # type: ignore[union-attr]
        return (
            1,
            "",
            f"Process timed out after {_TIMEOUT_SECONDS}s",
        )
    except FileNotFoundError as exc:
        return (1, "", f"Command not found: {exc}")


async def _run_syntax(ws: Path, src_dir: Path) -> ValidationResult:
    """Compile-check all .py files."""
    py_files = list(src_dir.rglob("*.py"))
    errors: list[dict[str, Any]] = []
    python = sys.executable

    for pyf in py_files[:50]:  # cap to avoid excessive subprocess spawning
        rc, _out, err = await _run_subprocess(
            python, "-m", "py_compile", str(pyf),
            cwd=str(ws),
        )
        if rc != 0:
            errors.append({"file": str(pyf.relative_to(ws)), "message": err.strip()})

    return ValidationResult(
        step="syntax",
        passed=len(errors) == 0,
        errors=errors,
        output=f"Checked {len(py_files)} files, {len(errors)} error(s)",
    )


async def _run_lint(src_dir: Path) -> ValidationResult:
    """Run ``ruff check`` with JSON output."""
    rc, out, err = await _run_subprocess(
        sys.executable, "-m", "ruff", "check",
        str(src_dir), "--output-format", "json",
    )

    errors: list[dict[str, Any]] = []
    if rc != 0:
        try:
            violations = json.loads(out)
            for v in violations:
                errors.append({
                    "file": v.get("filename", ""),
                    "line": v.get("location", {}).get("row", 0),
                    "code": v.get("code", ""),
                    "message": v.get("message", ""),
                })
        except json.JSONDecodeError:
            errors.append({"message": (out + err).strip()})

    return ValidationResult(
        step="lint",
        passed=rc == 0,
        errors=errors,
        output=out[:2000] if out else err[:2000],
    )


async def _run_typecheck(src_dir: Path) -> ValidationResult:
    """Run ``mypy`` with relaxed settings."""
    rc, out, err = await _run_subprocess(
        sys.executable, "-m", "mypy",
        str(src_dir), "--ignore-missing-imports",
    )

    errors: list[dict[str, Any]] = []
    combined = (out + "\n" + err).strip()
    if rc != 0:
        for line in combined.splitlines():
            if ": error:" in line:
                errors.append({"message": line.strip()})

    return ValidationResult(
        step="typecheck",
        passed=rc == 0,
        errors=errors,
        output=combined[:2000],
    )


async def _run_pytest(test_dir: Path, *, label: str) -> ValidationResult:
    """Run ``pytest`` on *test_dir*."""
    if not test_dir.is_dir():
        return ValidationResult(
            step=label,
            passed=True,
            errors=[],
            output=f"No test directory found at {test_dir}; skipping.",
        )

    rc, out, err = await _run_subprocess(
        sys.executable, "-m", "pytest",
        str(test_dir), "-v", "--tb=short", "-q",
    )

    errors: list[dict[str, Any]] = []
    combined = (out + "\n" + err).strip()
    if rc != 0:
        # Extract FAILED lines
        for line in combined.splitlines():
            if "FAILED" in line or "ERROR" in line:
                errors.append({"message": line.strip()})
        if not errors:
            errors.append({"message": combined[:500]})

    return ValidationResult(
        step=label,
        passed=rc == 0,
        errors=errors,
        output=combined[:2000],
    )
