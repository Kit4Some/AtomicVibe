"""Coding nodes: DispatchAgents, ReviewCode, ReviseCode."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic_graph import BaseNode, GraphRunContext

from architect.core.models import CodeFile, ExecuteGraphState, ExecuteDeps
from architect.execute.dispatcher import dispatch, dispatch_parallel
from architect.execute.supervisor.reviewer import review_code as _review_code

log = logging.getLogger("architect.execute.nodes.coding")


def _collect_code_files(state: ExecuteGraphState, workspace: Any) -> dict[str, str]:
    """Gather code files from agent outputs for review."""
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
class DispatchAgentsNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Dispatch coding agents in parallel and write output files."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> ReviewCodeNode:
        assignments = ctx.state.assignments
        vibe_files = ctx.state.vibe_files
        workspace = ctx.deps.workspace

        # Read current workspace files
        file_list = workspace.list_files()
        workspace_files: dict[str, str] = {}
        for f in file_list[:100]:  # Cap to avoid huge prompts
            try:
                workspace_files[f] = workspace.read_file(f)
            except Exception:  # noqa: BLE001
                pass

        log.info("DispatchAgentsNode — %d assignments", len(assignments))

        outputs = await dispatch_parallel(
            assignments=assignments,
            vibe_files=vibe_files,
            workspace_files=workspace_files,
            llm=ctx.deps.llm,
        )

        # Write all generated files to workspace
        for agent_id, output in outputs.items():
            if output.files:
                workspace.write_files(output.files)
            for tf in output.tests:
                workspace.write_files([CodeFile(path=tf.path, content=tf.content)])

        ctx.state.agent_outputs = {k: v.model_dump() for k, v in outputs.items()}
        ctx.state.iteration = ctx.state.iteration + 1
        return ReviewCodeNode()


@dataclass
class ReviewCodeNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Delegate to reviewer.review_code()."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> ValidateNode | ReviseCodeNode:
        from architect.execute.nodes.validation import ValidateNode

        workspace = ctx.deps.workspace
        code_files = _collect_code_files(ctx.state, workspace)
        vibe = ctx.state.vibe_files

        if not code_files:
            log.warning("ReviewCodeNode — no code files to review, auto-passing")
            ctx.state.review_results = {
                "overall_score": 5.0,
                "passed": True,
                "dimensions": {},
                "critical_issues": [],
                "suggestions": [],
                "revision_instructions": "",
            }
            return ValidateNode()

        log.info("ReviewCodeNode — reviewing %d files", len(code_files))

        result = await _review_code(
            code_files=code_files,
            interfaces_md=vibe.get("interfaces.md", ""),
            conventions_md=vibe.get("conventions.md", ""),
            spec_md=vibe.get("spec.md", ""),
            llm=ctx.deps.llm,
        )

        ctx.state.review_results = result.model_dump()

        if result.passed or ctx.state.revision_count >= 2:
            return ValidateNode()
        return ReviseCodeNode()


@dataclass
class ReviseCodeNode(BaseNode[ExecuteGraphState, ExecuteDeps]):
    """Re-dispatch agents with review feedback as errors."""

    async def run(
        self,
        ctx: GraphRunContext[ExecuteGraphState, ExecuteDeps],
    ) -> ReviewCodeNode:
        review = ctx.state.review_results
        revision_instructions = review.get("revision_instructions", "")
        critical = review.get("critical_issues", [])
        workspace = ctx.deps.workspace

        errors: list[dict[str, Any]] = [
            {"type": "review_feedback", "message": revision_instructions},
        ]
        for issue in critical:
            errors.append({"type": "critical_issue", "message": issue})

        assignments = ctx.state.assignments
        vibe_files = ctx.state.vibe_files

        # Read workspace files
        file_list = workspace.list_files()
        workspace_files: dict[str, str] = {}
        for f in file_list[:100]:
            try:
                workspace_files[f] = workspace.read_file(f)
            except Exception:  # noqa: BLE001
                pass

        log.info(
            "ReviseCodeNode — revision %d, %d error(s)",
            ctx.state.revision_count + 1,
            len(errors),
        )

        # Re-dispatch each assignment with errors
        all_outputs: dict[str, dict[str, Any]] = {}
        for assignment in assignments:
            agent_id = assignment["agent_id"]
            output = await dispatch(
                agent_id=agent_id,
                task_ids=assignment.get("task_ids", []),
                vibe_files=vibe_files,
                workspace_files=workspace_files,
                injected_knowledge=assignment.get("injected_knowledge", []),
                errors=errors,
                llm=ctx.deps.llm,
            )
            if output.files:
                workspace.write_files(output.files)
            all_outputs[agent_id] = output.model_dump()

        ctx.state.agent_outputs = all_outputs
        ctx.state.revision_count = ctx.state.revision_count + 1
        return ReviewCodeNode()
