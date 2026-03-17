"""Supervisor Assigner — task-to-agent assignment with knowledge injection."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from architect.llm import LLMRouter

__all__ = ["assign_tasks"]

log = logging.getLogger("architect.execute.supervisor.assigner")

_SYSTEM_PROMPT = """\
You are the Task Assigner inside the ARCHITECT autonomous coding system.

Your job:
1. Match each sprint task to the most capable agent based on persona \
   scope and historical performance.
2. For each assignment, inject PREVENTION KNOWLEDGE — known pitfalls \
   and solutions from the knowledge base that are relevant to the task.
3. Identify which assignments can run in parallel and group them.

Rules:
- If Agent-X failed a similar task before, include the error + fix in \
  injected_knowledge so the agent can avoid repeating the mistake.
- If two agents need each other's output, sequence them (don't parallelise).
- Include relevant knowledge_base entries as injected_knowledge strings.
- Each assignment must specify a parallel_group identifier.

Respond ONLY with valid JSON matching the AssignmentPlan schema.
"""


# ------------------------------------------------------------------
# Wrapper Pydantic models
# ------------------------------------------------------------------


class _Assignment(BaseModel):
    agent_id: str
    task_ids: list[int] = Field(min_length=1)
    execution_order: int = 1
    parallel_group: str = "group-1"
    injected_knowledge: list[str] = Field(default_factory=list)
    prevention_instructions: str = ""


class _ExecutionGroup(BaseModel):
    group: str
    agents: list[str]
    parallel: bool = True
    after: str = ""


class AssignmentPlan(BaseModel):
    """Structured output from the Assigner LLM call."""

    assignments: list[_Assignment] = Field(min_length=1)
    execution_plan: list[_ExecutionGroup] = Field(min_length=1)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


async def assign_tasks(
    sprint_plan: dict[str, Any],
    knowledge_base: list[dict[str, Any]],
    agent_performance: dict[str, dict[str, Any]],
    *,
    llm: LLMRouter,
) -> dict[str, Any]:
    """Assign sprint tasks to agents and build an execution plan.

    Returns a partial-state dict with ``assignments`` and
    ``execution_plan`` keys.
    """
    user_content = (
        f"## Sprint Plan\n\n"
        f"{json.dumps(sprint_plan, indent=2, ensure_ascii=False)}\n\n"
        f"## Knowledge Base (recent entries)\n\n"
        f"{json.dumps(knowledge_base[-20:], indent=2, ensure_ascii=False)}\n\n"
        f"## Agent Performance\n\n"
        f"{json.dumps(agent_performance, indent=2, ensure_ascii=False)}"
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    log.info("assign_tasks: assigning %d tasks", len(sprint_plan.get("tasks", [])))

    result = await llm.complete_structured(
        messages=messages,
        response_model=AssignmentPlan,
        purpose="supervisor",
    )

    return {
        "assignments": [a.model_dump() for a in result.assignments],
        "execution_plan": [g.model_dump() for g in result.execution_plan],
    }
