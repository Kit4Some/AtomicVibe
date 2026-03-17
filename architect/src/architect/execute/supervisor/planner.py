"""Supervisor Planner — sprint planning for the Execute Engine."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from architect.core.exceptions import ExecuteError
from architect.core.models import ExecuteStateV2
from architect.llm import LLMRouter

__all__ = ["plan_sprint"]

log = logging.getLogger("architect.execute.supervisor.planner")

_SYSTEM_PROMPT = """\
You are a senior engineering PM responsible for sprint planning inside the \
ARCHITECT autonomous coding system.

Your job:
1. Analyse the current checklist to identify incomplete tasks.
2. Review shared-memory for blockers or requests from other agents.
3. Examine error_history for recurring failure patterns.
4. Check agent_performance to understand each agent's track record.
5. Produce a sprint plan with at most 5 tasks.

Rules:
- Never assign more than 5 tasks per sprint.
- If a task failed 2+ times before, flag it as HIGH RISK and include a \
  prevention note.
- If a task depends on incomplete tasks, mark it as BLOCKED.
- Prioritise unblocking other agents over new features.
- Consider agent workload balance.

Respond ONLY with valid JSON matching the SprintPlan schema.
"""


# ------------------------------------------------------------------
# Wrapper Pydantic models for structured LLM output
# ------------------------------------------------------------------


class _SprintTask(BaseModel):
    task_id: int
    description: str
    agent_id: str
    priority: int = 1
    risk: str = "medium"
    risk_reason: str = ""
    prevention: str = ""
    dependencies: list[int] = Field(default_factory=list)
    estimated_complexity: str = "medium"


class _BlockedTask(BaseModel):
    task_id: int
    blocked_by: int
    reason: str


class SprintPlan(BaseModel):
    """Structured output from the Planner LLM call."""

    sprint_number: int
    sprint_goal: str
    tasks: list[_SprintTask] = Field(min_length=1)
    blocked_tasks: list[_BlockedTask] = Field(default_factory=list)
    sprint_notes: str = ""


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


async def plan_sprint(
    state: ExecuteStateV2,
    *,
    llm: LLMRouter,
) -> dict[str, Any]:
    """Analyse project state and produce the next sprint plan.

    Returns a partial-state dict suitable for merging into
    :class:`ExecuteStateV2`.
    """
    vibe_files = state.get("vibe_files", {})
    checklist_md = vibe_files.get("checklist.md", "")
    if not checklist_md.strip():
        raise ExecuteError(message="checklist.md not found in vibe_files")

    shared_memory_md = vibe_files.get("shared-memory.md", "")
    error_history = state.get("error_history", [])
    agent_performance = state.get("agent_performance", {})
    current_sprint = state.get("current_sprint", 0)

    user_content = (
        f"## Current Sprint Number\n{current_sprint + 1}\n\n"
        f"## Checklist (current progress)\n\n{checklist_md}\n\n"
        f"## Shared-Memory\n\n{shared_memory_md}\n\n"
        f"## Error History (last 10)\n\n"
        f"{json.dumps(error_history[-10:], indent=2, ensure_ascii=False)}\n\n"
        f"## Agent Performance\n\n"
        f"{json.dumps(agent_performance, indent=2, ensure_ascii=False)}"
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    log.info("plan_sprint: requesting sprint %d plan", current_sprint + 1)

    result = await llm.complete_structured(
        messages=messages,
        response_model=SprintPlan,
        purpose="supervisor",
    )

    return {
        "sprint_plan": result.model_dump(),
        "sprint_tasks": [t.model_dump() for t in result.tasks],
        "current_sprint": current_sprint + 1,
    }
