"""Build user prompts for coding agents."""

from __future__ import annotations

import json
from typing import Any

__all__ = ["build_agent_user_prompt"]


def build_agent_user_prompt(
    tasks: list[dict[str, Any]],
    spec_section: str,
    shared_memory_exports: str,
    injected_knowledge: list[str],
    existing_code: dict[str, str],
    previous_errors: list[dict[str, Any]] | None = None,
) -> str:
    """Assemble the user prompt sent to a coding agent.

    Sections are ordered by priority: tasks first, then context, then
    optional error history for revision runs.
    """
    parts: list[str] = []

    # -- Tasks --
    parts.append("## Tasks\n")
    for i, task in enumerate(tasks, 1):
        tid = task.get("task_id", i)
        desc = task.get("description", str(task))
        parts.append(f"{i}. **[#{tid}]** {desc}")
    parts.append("")

    # -- Spec excerpt --
    if spec_section:
        parts.append("## Relevant Specification\n")
        parts.append(spec_section)
        parts.append("")

    # -- Shared-memory exports --
    if shared_memory_exports:
        parts.append("## Shared-Memory Exports (from other agents)\n")
        parts.append(shared_memory_exports)
        parts.append("")

    # -- Injected knowledge / prevention --
    if injected_knowledge:
        parts.append("## Prevention Knowledge\n")
        parts.append(
            "The following lessons were learned from previous sprints. "
            "Follow them carefully to avoid known pitfalls:\n"
        )
        for i, entry in enumerate(injected_knowledge, 1):
            parts.append(f"{i}. {entry}")
        parts.append("")

    # -- Existing code --
    if existing_code:
        parts.append("## Existing Code\n")
        for path, content in existing_code.items():
            parts.append(f"### `{path}`\n```python\n{content}\n```\n")
        parts.append("")

    # -- Previous errors (for revision / fix runs) --
    if previous_errors:
        parts.append("## Previous Errors (fix these)\n")
        parts.append(
            "The following errors occurred in the last run. "
            "Your code MUST fix all of them:\n"
        )
        parts.append(f"```json\n{json.dumps(previous_errors, indent=2)}\n```\n")

    return "\n".join(parts)
