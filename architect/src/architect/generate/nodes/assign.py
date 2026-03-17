"""Assign agents to modules and build a dependency graph."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from pydantic_graph import BaseNode, GraphRunContext

from architect.core.models import AgentAssignment, GenerateGraphState, GenerateDeps
from architect.generate.nodes.gen_all import GenerateAllNode

__all__ = ["AssignNode"]

log = logging.getLogger("architect.generate.assign")

_SYSTEM_PROMPT = """\
You are a project manager for a multi-agent coding system. Given a list of code modules \
and user decisions, assign agents to implement each module.

For each agent assignment, provide:
- agent_id: A short identifier like "Agent-A", "Agent-B", etc.
- persona_name: A descriptive role name (e.g. "Core Architect", "API Engineer")
- modules: List of module names this agent is responsible for
- phase: The implementation phase (integer, starting from 1). \
  Modules with no dependencies should be in earlier phases.
- can_parallel_with: List of other agent_ids that can work simultaneously

Rules:
- Assign 2-6 agents depending on project size
- Each module should be assigned to exactly one agent
- Agents in the same phase can work in parallel if their modules don't depend on each other
- Foundation/core modules should be in Phase 1
- Dependent modules in later phases
"""


class AssignmentList(BaseModel):
    """Wrapper for structured LLM output."""

    assignments: list[AgentAssignment] = Field(min_length=1)


def _build_dependency_graph(
    modules: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Build a module dependency DAG from module definitions."""
    graph: dict[str, list[str]] = {}
    for module in modules:
        name = module.get("name", "")
        deps = module.get("dependencies", [])
        graph[name] = deps
    return graph


@dataclass
class AssignNode(BaseNode[GenerateGraphState, GenerateDeps]):
    """Assign agents to modules and build dependency graph."""

    async def run(
        self,
        ctx: GraphRunContext[GenerateGraphState, GenerateDeps],
    ) -> GenerateAllNode:
        modules = ctx.state.modules
        decisions = ctx.state.decisions
        llm = ctx.deps.llm

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "## Modules\n\n"
                    f"{json.dumps(modules, indent=2, ensure_ascii=False)}\n\n"
                    "## User Decisions\n\n"
                    f"{json.dumps(decisions, indent=2, ensure_ascii=False)}"
                ),
            },
        ]

        log.info("AssignNode: requesting assignments (modules=%d)", len(modules))

        result = await llm.complete_structured(
            messages=messages,
            response_model=AssignmentList,
            purpose="generate_md",
        )

        assignments = [a.model_dump() for a in result.assignments]
        dependency_graph = _build_dependency_graph(modules)

        log.info(
            "AssignNode: completed (agents=%d, graph_nodes=%d)",
            len(assignments),
            len(dependency_graph),
        )

        ctx.state.agent_assignments = assignments
        ctx.state.dependency_graph = dependency_graph
        return GenerateAllNode()
