"""Validation nodes: Validate, Diagnose, Strategize, ApplyFix, ApplyStrategy."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic_graph import BaseNode, GraphRunContext

from architect.core.models import DiagnosisResult, ExecuteGraphState, ExecuteDeps
from architect.execute.fixer import apply_fix as _apply_fix
from architect.execute.supervisor.diagnostician import diagnose as _diagnose
from architect.execute.supervisor.strategist import strategize as _strategize
from architect.execute.validator import validate as _validate

log = logging.getLogger("architect.execute.nodes.validation")


def _extract_validation_errors(
    validation_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract error dicts from validation results."""
    errors: list[dict[str, Any]] = []
    for vr in validation_results:
        if not vr.get("passed"):
            for err in vr.get("errors", []):
                errors.append({
                    "step": vr.get("step", "unknown"),
                    **err,
                })
    return errors


def _collect_code_files(state: ExecuteGraphState, workspace: Any) -> dict[str, str]:
    """Gather code files from agent outputs."""
    code_files: dict[str, str] = {}
    for _agent_id, output in state.agent_outputs.items():
        files = output.get("files", [])
        for f in files:
            path = f.get("path", "")
            if path:
                try:
                    code_files[path] = workspace.read_file(path)
                except Exception:  # noqa: BLE001
                    code_files[path] = f.get("content", "")
    return code_files


@dataclass
class ValidateNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Run the validation pipeline against the workspace."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> UpdateStateNode | DiagnoseNode:
        from architect.execute.nodes.lifecycle import UpdateStateNode

        ws_path = ctx.state.workspace_path
        phase = ctx.state.current_phase

        log.info("ValidateNode — workspace=%s phase=%d", ws_path, phase)

        results = await _validate(workspace_path=ws_path, phase=phase)
        ctx.state.validation_results = [r.model_dump() for r in results]

        if all(r.passed for r in results):
            return UpdateStateNode()
        return DiagnoseNode()


@dataclass
class DiagnoseNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Delegate to diagnostician.diagnose()."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> ApplyFixNode | StrategizeNode:
        errors = _extract_validation_errors(ctx.state.validation_results)
        code_context = _collect_code_files(ctx.state, ctx.deps.workspace)

        log.info("DiagnoseNode — %d error(s)", len(errors))

        result = await _diagnose(
            errors=errors,
            error_history=ctx.state.error_history,
            knowledge_base=ctx.state.knowledge_base,
            code_context=code_context,
            llm=ctx.deps.llm,
        )

        ctx.state.diagnosis = result.model_dump()
        ctx.state.error_history = [*ctx.state.error_history, result.model_dump()]

        approach = result.recommendation.get("approach", "")
        if approach in ("apply_known_fix", "retry_with_changes", "none"):
            return ApplyFixNode()
        return StrategizeNode()


@dataclass
class StrategizeNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Delegate to strategist.strategize()."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> CheckBudgetNode | ApplyStrategyNode | AssignTasksNode | RequestUserNode:
        from architect.execute.nodes.lifecycle import CheckBudgetNode, RequestUserNode
        from architect.execute.nodes.sprint import AssignTasksNode

        diag = DiagnosisResult.model_validate(ctx.state.diagnosis)
        budget_remaining = ctx.state.max_cost_usd - ctx.state.cost_usd
        iters_remaining = ctx.state.max_total_iterations - ctx.state.total_iterations

        log.info(
            "StrategizeNode — budget=%.2f iters=%d",
            budget_remaining,
            iters_remaining,
        )

        result = await _strategize(
            diagnosis=diag,
            spec_md=ctx.state.vibe_files.get("spec.md", ""),
            decisions=ctx.state.decisions,
            budget_remaining=budget_remaining,
            iterations_remaining=iters_remaining,
            llm=ctx.deps.llm,
        )

        ctx.state.fix_strategy = result
        ctx.state.decisions = [*ctx.state.decisions, result]

        decision = result.get("decision", "").lower()
        if decision == "retry_with_guidance":
            return CheckBudgetNode()
        if decision in ("change_implementation", "split_task", "modify_interface", "rollback_and_retry"):
            return ApplyStrategyNode()
        if decision == "reassign_agent":
            return AssignTasksNode()
        return RequestUserNode()


@dataclass
class ApplyFixNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Delegate to fixer.apply_fix() and write fixed files."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> CheckBudgetNode:
        from architect.execute.nodes.lifecycle import CheckBudgetNode

        diag = DiagnosisResult.model_validate(ctx.state.diagnosis)
        errors = _extract_validation_errors(ctx.state.validation_results)
        workspace = ctx.deps.workspace

        # Read workspace files
        file_list = workspace.list_files()
        workspace_files: dict[str, str] = {}
        for f in file_list[:100]:
            try:
                workspace_files[f] = workspace.read_file(f)
            except Exception:  # noqa: BLE001
                pass

        log.info("ApplyFixNode — applying fix for %s", diag.error_category)

        result = await _apply_fix(
            errors=errors,
            diagnosis=diag,
            vibe_files=ctx.state.vibe_files,
            workspace_files=workspace_files,
            llm=ctx.deps.llm,
        )

        if result.files:
            workspace.write_files(result.files)

        ctx.state.agent_outputs = {"fixer": result.model_dump()}
        ctx.state.total_iterations = ctx.state.total_iterations + 1
        return CheckBudgetNode()


@dataclass
class ApplyStrategyNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Apply strategic actions (spec changes, task invalidation, etc.)."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> PlanSprintNode:
        from architect.execute.nodes.sprint import PlanSprintNode

        strategy = ctx.state.fix_strategy
        actions = strategy.get("actions", [])
        workspace = ctx.deps.workspace

        log.info(
            "ApplyStrategyNode — decision=%s actions=%d",
            strategy.get("decision", "?"),
            len(actions),
        )

        vibe_files = dict(ctx.state.vibe_files)

        for action in actions:
            action_type = action.get("type", "")
            if action_type == "update_spec":
                details = action.get("details", "")
                if details:
                    current = vibe_files.get("spec.md", "")
                    vibe_files["spec.md"] = current + f"\n\n## Update\n{details}\n"
                    workspace.update_vibe_file("spec.md", vibe_files["spec.md"])
            elif action_type == "update_interface":
                details = action.get("details", action.get("change", ""))
                if details:
                    current = vibe_files.get("interfaces.md", "")
                    vibe_files["interfaces.md"] = (
                        current + f"\n\n## Update\n{details}\n"
                    )
                    workspace.update_vibe_file(
                        "interfaces.md", vibe_files["interfaces.md"]
                    )

        # Reset sprint for re-planning
        ctx.state.vibe_files = vibe_files
        ctx.state.sprint_plan = {}
        ctx.state.sprint_tasks = []
        ctx.state.revision_count = 0
        return PlanSprintNode()
