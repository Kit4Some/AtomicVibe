"""Unit tests for the validate_coherence node."""

from __future__ import annotations

from typing import Any

import pytest

from architect.core.models import GenerateState
from architect.generate.nodes.validate import validate_coherence


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(files: dict[str, str], **overrides: Any) -> GenerateState:
    defaults: dict[str, Any] = {
        "plan_document": "# Test",
        "decisions": [],
        "modules": [],
        "agent_assignments": [],
        "dependency_graph": {},
        "generated_files": files,
        "validation_errors": [],
        "project_path": "/tmp/test",
        "retry_count": 0,
    }
    defaults.update(overrides)
    return defaults  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Coherent files (should pass)
# ---------------------------------------------------------------------------


_AGENT_MD_OK = """\
# agent.md

## 4. Agent-Directory Ownership

| Agent | Role | Directories | Phase |
|-------|------|-------------|-------|
| Agent-A | Core Architect | core/ | P1 |
| Agent-B | API Engineer | api/ | P2 |
"""

_PERSONA_MD_OK = """\
# persona.md

## Agent-A: Core Architect

### [INSTRUCTIONS]
Build the core module.

- [X] api/ 파일 수정 금지
- [X] LLM 직접 호출 금지

담당: core/

## Agent-B: API Engineer

### [INSTRUCTIONS]
Build the API routes.

- [X] core/ 파일 수정 금지

담당: api/
"""

_PLAN_MD_OK = """\
# plan.md

| # | Task | Agent | Dependencies | Priority |
|---|------|-------|-------------|----------|
| 1 | Build core models | Agent-A | - | HIGH |
| 2 | Build API routes | Agent-B | #1 | HIGH |
"""

_CHECKLIST_MD_OK = """\
# checklist.md

| # | Task | Status | Agent | Date | Notes |
|---|------|--------|-------|------|-------|
| 1 | Build core models | [TODO] | A | - | |
| 2 | Build API routes | [TODO] | B | - | |
"""

_INTERFACES_MD_OK = """\
# interfaces.md

```python
class CoreService:
    def get_data(self) -> dict: ...

class ApiRouter:
    def register_routes(self) -> None: ...
```
"""

_SPEC_MD_OK = """\
# spec.md

## 1. Core Models

The CoreService provides data access.

## 2. API Design

The ApiRouter registers all HTTP routes.
"""

_PROMPTS_MD_OK = """\
# OPERATION-GUIDE.md

## Phase 1

### Agent-A: Core Architect

```
Build the core module.
api/ 파일 수정 금지
LLM 직접 호출 금지
```

## Phase 2

### Agent-B: API Engineer

```
Build API routes.
core/ 파일 수정 금지
```
"""


# ---------------------------------------------------------------------------
# Tests: Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_validate_passes_for_coherent_files() -> None:
    """Coherent files should produce no validation errors."""
    files = {
        "agent.md": _AGENT_MD_OK,
        "persona.md": _PERSONA_MD_OK,
        "plan.md": _PLAN_MD_OK,
        "checklist.md": _CHECKLIST_MD_OK,
        "interfaces.md": _INTERFACES_MD_OK,
        "spec.md": _SPEC_MD_OK,
        "OPERATION-GUIDE.md": _PROMPTS_MD_OK,
    }
    state = _make_state(files)
    result = await validate_coherence(state)

    assert result["validation_errors"] == []
    assert result["retry_count"] == 0


# ---------------------------------------------------------------------------
# Tests: Agent mismatch detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_validate_detects_agent_mismatch() -> None:
    """agent.md has Agent-C but persona.md doesn't."""
    agent_md_bad = _AGENT_MD_OK + "| Agent-C | DB Admin | db/ | P1 |\n"
    files = {
        "agent.md": agent_md_bad,
        "persona.md": _PERSONA_MD_OK,
    }
    state = _make_state(files)
    result = await validate_coherence(state)

    assert len(result["validation_errors"]) > 0
    assert any("Agent-C" in e for e in result["validation_errors"])
    assert result["retry_count"] == 1


# ---------------------------------------------------------------------------
# Tests: Plan vs checklist mismatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_validate_detects_plan_checklist_mismatch() -> None:
    """Plan has tasks not in checklist."""
    plan_extra = _PLAN_MD_OK + "| 3 | Implement authentication system | Agent-C | - | HIGH |\n"
    plan_extra += "| 4 | Deploy infrastructure pipeline | Agent-C | - | HIGH |\n"
    plan_extra += "| 5 | Configure monitoring alerts | Agent-C | - | MEDIUM |\n"
    plan_extra += "| 6 | Setup logging aggregation | Agent-C | - | MEDIUM |\n"
    files = {
        "plan.md": plan_extra,
        "checklist.md": _CHECKLIST_MD_OK,
    }
    state = _make_state(files)
    result = await validate_coherence(state)

    # Should detect that extra tasks are not in checklist
    assert len(result["validation_errors"]) > 0
    assert any("plan" in e.lower() and "checklist" in e.lower() for e in result["validation_errors"])


# ---------------------------------------------------------------------------
# Tests: Retry count increment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_validate_increments_retry_count() -> None:
    """retry_count should increment when errors are found."""
    agent_md_bad = _AGENT_MD_OK + "| Agent-C | DB Admin | db/ | P1 |\n"
    files = {
        "agent.md": agent_md_bad,
        "persona.md": _PERSONA_MD_OK,
    }
    state = _make_state(files, retry_count=1)
    result = await validate_coherence(state)

    assert result["retry_count"] == 2


@pytest.mark.asyncio()
async def test_validate_no_increment_on_success() -> None:
    """retry_count should not increment when validation passes."""
    files = {
        "agent.md": _AGENT_MD_OK,
        "persona.md": _PERSONA_MD_OK,
    }
    state = _make_state(files)
    result = await validate_coherence(state)

    assert result["retry_count"] == 0


# ---------------------------------------------------------------------------
# Tests: Empty files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_validate_handles_empty_generated_files() -> None:
    """Empty generated_files should produce no errors (nothing to validate)."""
    state = _make_state({})
    result = await validate_coherence(state)

    assert result["validation_errors"] == []
