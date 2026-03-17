"""Lifecycle nodes: UpdateState, Retrospective, AdjustPlan, CheckBudget, RequestUser."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from pydantic_graph import BaseNode, End, GraphRunContext

from architect.core.models import ExecuteGraphState, ExecuteDeps

log = logging.getLogger("architect.execute.nodes.lifecycle")


# ============================================================================
# Retrospective Pydantic models
# ============================================================================


class _RetrospectiveMetrics(BaseModel):
    tasks_total: int = 0
    tasks_first_pass: int = 0
    tasks_with_fixes: int = 0
    tasks_failed: int = 0
    first_pass_rate: float = 0.0
    avg_fix_iterations: float = 0.0
    total_cost_usd: float = 0.0
    total_llm_calls: int = 0


class _RootCause(BaseModel):
    issue: str
    cause: str
    fix: str


class _Improvement(BaseModel):
    action: str
    target: str
    priority: str = "medium"


class RetrospectiveResult(BaseModel):
    """Structured output from the retrospective LLM call."""

    phase: int
    metrics: _RetrospectiveMetrics = Field(default_factory=_RetrospectiveMetrics)
    went_well: list[str] = Field(default_factory=list)
    went_wrong: list[str] = Field(default_factory=list)
    root_causes: list[_RootCause] = Field(default_factory=list)
    improvements: list[_Improvement] = Field(default_factory=list)
    agent_performance: dict[str, dict[str, Any]] = Field(default_factory=dict)


_RETROSPECTIVE_PROMPT = """\
You are analysing the results of a phase in the ARCHITECT autonomous \
coding system. Produce a structured retrospective.

Analyse:
1. WHAT WENT WELL — Tasks passing first try, best agents, useful knowledge.
2. WHAT WENT WRONG — Most-retried tasks, common error types, regressions.
3. ROOT CAUSE ANALYSIS — Systemic causes of recurring errors.
4. IMPROVEMENT ACTIONS — Changes for next phase.
5. METRICS SUMMARY — Success rates, costs, iteration counts.

Respond ONLY with valid JSON matching the RetrospectiveResult schema.
"""


# ============================================================================
# Nodes
# ============================================================================


@dataclass
class UpdateStateNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Record completed tasks and commit workspace."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> PlanSprintNode | RetrospectiveNode:
        from architect.execute.nodes.sprint import PlanSprintNode

        workspace = ctx.deps.workspace
        sprint_num = ctx.state.current_sprint
        tasks = ctx.state.sprint_tasks

        # Mark all current sprint tasks as done
        for task in tasks:
            ctx.state.sprint_results.append({
                "task_id": task.get("task_id"),
                "status": "done",
                "sprint": sprint_num,
            })

        # Commit and tag
        try:
            workspace.git_commit(f"feat(execute): sprint-{sprint_num} complete")
            workspace.git_tag(f"sprint-{sprint_num}")
        except Exception:  # noqa: BLE001
            log.warning("UpdateStateNode — git commit/tag failed, continuing")

        log.info("UpdateStateNode — sprint %d done, %d tasks", sprint_num, len(tasks))
        ctx.state.phase_status = "running"

        # Check if sprint is complete
        all_task_ids = {t.get("task_id") for t in ctx.state.sprint_plan.get("tasks", [])}
        done_ids = {r.get("task_id") for r in ctx.state.sprint_results if r.get("status") == "done"}
        if all_task_ids and all_task_ids <= done_ids:
            return RetrospectiveNode()
        return PlanSprintNode()


@dataclass
class RetrospectiveNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Run a phase retrospective via LLM."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> AdjustPlanNode:
        phase = ctx.state.current_phase

        user_content = (
            f"## Phase {phase} — Retrospective Data\n\n"
            f"### Sprint Results\n"
            f"{json.dumps(ctx.state.sprint_results, indent=2)}\n\n"
            f"### Error History\n"
            f"{json.dumps(ctx.state.error_history[-20:], indent=2)}\n\n"
            f"### Knowledge Base\n"
            f"{json.dumps(ctx.state.knowledge_base[-10:], indent=2)}\n\n"
            f"### Decisions\n"
            f"{json.dumps(ctx.state.decisions[-10:], indent=2)}\n\n"
            f"### Current Cost: ${ctx.state.cost_usd:.2f}\n"
            f"### Total Iterations: {ctx.state.total_iterations}"
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _RETROSPECTIVE_PROMPT},
            {"role": "user", "content": user_content},
        ]

        log.info("RetrospectiveNode — phase=%d", phase)

        result = await ctx.deps.llm.complete_structured(
            messages=messages,
            response_model=RetrospectiveResult,
            purpose="supervisor",
        )

        ctx.state.retrospective_results = [
            *ctx.state.retrospective_results,
            result.model_dump(),
        ]
        return AdjustPlanNode()


@dataclass
class AdjustPlanNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Advance to the next phase based on retrospective."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> PlanSprintNode | End[ExecuteGraphState]:
        from architect.execute.nodes.sprint import PlanSprintNode

        current_phase = ctx.state.current_phase
        log.info("AdjustPlanNode — advancing from phase %d", current_phase)

        ctx.state.current_phase = current_phase + 1
        ctx.state.current_sprint = 0
        ctx.state.sprint_plan = {}
        ctx.state.sprint_tasks = []
        ctx.state.sprint_results = []
        ctx.state.revision_count = 0

        if current_phase >= ctx.state.total_phases:
            ctx.state.system_status = "complete"
            return End(ctx.state)
        return PlanSprintNode()


@dataclass
class CheckBudgetNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Check budget/iteration limits and dispatch or pause."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> DispatchAgentsNode | RequestUserNode:
        from architect.execute.nodes.coding import DispatchAgentsNode

        ctx.state.total_iterations = ctx.state.total_iterations + 1

        if ctx.state.cost_usd >= ctx.state.max_cost_usd:
            log.warning("CheckBudgetNode — cost limit reached")
            return RequestUserNode()
        if ctx.state.total_iterations >= ctx.state.max_total_iterations:
            log.warning("CheckBudgetNode — iteration limit reached")
            return RequestUserNode()

        return DispatchAgentsNode()


@dataclass
class RequestUserNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Pause execution and wait for user input."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> End[ExecuteGraphState]:
        log.warning("RequestUserNode — pausing for user input")
        ctx.state.system_status = "paused"
        ctx.state.phase_status = "waiting_user"
        return End(ctx.state)
