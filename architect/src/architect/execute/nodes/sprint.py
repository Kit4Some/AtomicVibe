"""Sprint lifecycle nodes: ReadState, PlanSprint, AssessRisk, AssignTasks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic_graph import BaseNode, GraphRunContext

from architect.core.models import ExecuteGraphState, ExecuteDeps
from architect.execute.supervisor.assigner import assign_tasks as _assign_tasks
from architect.execute.supervisor.planner import plan_sprint as _plan_sprint

log = logging.getLogger("architect.execute.nodes.sprint")


@dataclass
class ReadStateNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Initialise workspace and load existing files."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> PlanSprintNode:
        log.info("ReadStateNode — workspace=%s", ctx.state.workspace_path)
        ctx.state.system_status = "running"
        ctx.state.phase_status = "running"
        return PlanSprintNode()


@dataclass
class PlanSprintNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Delegate to planner.plan_sprint()."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> AssessRiskNode:
        log.info("PlanSprintNode — sprint=%d", ctx.state.current_sprint + 1)
        result = await _plan_sprint(ctx.state.to_typed_dict(), llm=ctx.deps.llm)
        # Apply result fields to state
        if "sprint_plan" in result:
            ctx.state.sprint_plan = result["sprint_plan"]
        if "sprint_tasks" in result:
            ctx.state.sprint_tasks = result["sprint_tasks"]
        if "current_sprint" in result:
            ctx.state.current_sprint = result["current_sprint"]
        ctx.state.revision_count = 0  # Reset for new sprint
        return AssessRiskNode()


@dataclass
class AssessRiskNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Evaluate risk for sprint tasks based on error history."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> AssignTasksNode:
        tasks = ctx.state.sprint_tasks
        error_history = ctx.state.error_history
        risk_register: list[dict[str, Any]] = []

        # Count failures per task_id
        fail_counts: dict[int, int] = {}
        for err in error_history:
            for tid in err.get("affected_tasks", []):
                fail_counts[tid] = fail_counts.get(tid, 0) + 1

        for task in tasks:
            tid = task.get("task_id", 0)
            fails = fail_counts.get(tid, 0)
            if fails >= 2 or task.get("risk") == "high":
                risk_register.append({
                    "task_id": tid,
                    "level": "high",
                    "reason": f"Failed {fails} times previously"
                    if fails >= 2
                    else task.get("risk_reason", "Flagged as high risk"),
                })

        log.info("AssessRiskNode — %d high-risk tasks", len(risk_register))
        ctx.state.risk_register = risk_register
        return AssignTasksNode()


@dataclass
class AssignTasksNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Delegate to assigner.assign_tasks()."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> DispatchAgentsNode:
        from architect.execute.nodes.coding import DispatchAgentsNode

        log.info("AssignTasksNode")
        result = await _assign_tasks(
            sprint_plan=ctx.state.sprint_plan,
            knowledge_base=ctx.state.knowledge_base,
            agent_performance=ctx.state.agent_performance,
            llm=ctx.deps.llm,
        )
        if "assignments" in result:
            ctx.state.assignments = result["assignments"]
        if "execution_plan" in result:
            ctx.state.execution_plan = result["execution_plan"]
        return DispatchAgentsNode()
