"""Test configuration and shared helpers for Execute Engine tests."""

from __future__ import annotations

from typing import Any

import structlog

import architect.core.logging as _logging_mod
from architect.core.models import ExecuteStateV2


def pytest_configure() -> None:
    """Configure structlog for test environment."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    _logging_mod._configured = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_execute_state(**overrides: Any) -> ExecuteStateV2:
    """Create a fully populated :class:`ExecuteStateV2` with defaults."""
    defaults: dict[str, Any] = {
        "workspace_path": "/tmp/test_workspace",
        "vibe_files": {
            "checklist.md": (
                "# Checklist\n"
                "- [ ] #36 execute/states.py\n"
                "- [ ] #37 supervisor/planner.py\n"
                "- [x] #2 core/models.py\n"
            ),
            "shared-memory.md": (
                "# Shared Memory\n\n"
                "## Agent-A EXPORT\n"
                "core/models.py ready.\n"
            ),
            "persona.md": (
                "## Agent-A: Core Architect\n"
                "Responsible for core models.\n"
                "---\n"
                "## Agent-E: Execute Engineer\n"
                "Responsible for execute engine.\n"
            ),
            "interfaces.md": "# Interfaces\n\n## Execute Engine\n...\n",
            "conventions.md": "# Conventions\nPython 3.12+, ruff, mypy strict.\n",
            "spec.md": "# Spec\n\n## 6. Execute Engine\n...\n",
        },
        "current_phase": 1,
        "total_phases": 3,
        "current_sprint": 0,
        "sprint_plan": {},
        "sprint_tasks": [],
        "sprint_results": [],
        "assignments": [],
        "execution_plan": [],
        "current_group": 0,
        "agent_outputs": {},
        "review_results": {},
        "revision_count": 0,
        "validation_results": [],
        "diagnosis": {},
        "fix_strategy": {},
        "error_history": [],
        "error_patterns": [],
        "knowledge_base": [],
        "agent_performance": {},
        "risk_register": [],
        "iteration": 0,
        "max_sprint_iterations": 5,
        "total_iterations": 0,
        "max_total_iterations": 30,
        "cost_usd": 0.0,
        "max_cost_usd": 50.0,
        "phase_status": "running",
        "system_status": "active",
        "decisions": [],
        "retrospective_results": [],
    }
    defaults.update(overrides)
    return defaults  # type: ignore[return-value]
