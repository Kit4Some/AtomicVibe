"""Execute Engine — Supervisor Loop using pydantic-graph for autonomous code generation."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from pydantic_graph import Graph

from architect.core.exceptions import ExecuteError
from architect.core.models import ExecuteGraphState, ExecuteDeps, ExecuteStateV2
from architect.execute.knowledge import KnowledgeManager
from architect.execute.nodes.coding import (
    DispatchAgentsNode,
    ReviewCodeNode,
    ReviseCodeNode,
)
from architect.execute.nodes.lifecycle import (
    AdjustPlanNode,
    CheckBudgetNode,
    RequestUserNode,
    RetrospectiveNode,
    UpdateStateNode,
)
from architect.execute.nodes.sprint import (
    AssessRiskNode,
    AssignTasksNode,
    PlanSprintNode,
    ReadStateNode,
)
from architect.execute.nodes.validation import (
    ApplyFixNode,
    ApplyStrategyNode,
    DiagnoseNode,
    StrategizeNode,
    ValidateNode,
)
from architect.execute.workspace import Workspace
from architect.llm import LLMRouter

__all__ = ["ExecuteEngine"]

log = logging.getLogger("architect.execute.engine")

# Graph must be created at module level so pydantic-graph can resolve
# forward-reference return types via the parent frame's namespace.
_EXECUTE_GRAPH = Graph(
    nodes=[
        ReadStateNode, PlanSprintNode, AssessRiskNode, AssignTasksNode,
        DispatchAgentsNode, ReviewCodeNode, ReviseCodeNode,
        ValidateNode, DiagnoseNode, StrategizeNode,
        ApplyFixNode, ApplyStrategyNode,
        UpdateStateNode, RetrospectiveNode, AdjustPlanNode,
        CheckBudgetNode, RequestUserNode,
    ],
)


def _make_initial_state(
    vibe_files: dict[str, str],
    workspace_path: str,
) -> ExecuteGraphState:
    """Create the initial ExecuteGraphState for a fresh run."""
    checklist = vibe_files.get("checklist.md", "")
    phase_count = max(1, checklist.lower().count("phase"))

    return ExecuteGraphState(
        workspace_path=workspace_path,
        vibe_files=vibe_files,
        total_phases=phase_count,
        max_total_iterations=30,
        max_cost_usd=50.0,
        phase_status="starting",
        system_status="starting",
    )


class ExecuteEngine:
    """Orchestrate autonomous code generation through the Supervisor Loop.

    Usage::

        engine = ExecuteEngine(llm_router, "/path/to/workspace")
        result = await engine.run(vibe_files)
        print(engine.get_status())
    """

    def __init__(self, llm_router: LLMRouter, workspace_path: str) -> None:
        self._llm = llm_router
        self._workspace_path = workspace_path
        self._workspace = Workspace(workspace_path)
        self._knowledge = KnowledgeManager(
            os.path.join(workspace_path, ".vibe", "knowledge.md"),
        )
        self._graph = _EXECUTE_GRAPH
        self._state: ExecuteGraphState | None = None
        self._progress_callbacks: list[Callable[..., Any]] = []

    async def run(self, vibe_files: dict[str, str]) -> ExecuteStateV2:
        """Execute the full Supervisor Loop.

        Args:
            vibe_files: Mapping of filename -> content for all .vibe/ files.

        Returns:
            The final state as an ExecuteStateV2 TypedDict.
        """
        if not vibe_files:
            raise ExecuteError(message="vibe_files must not be empty")

        state = _make_initial_state(vibe_files, str(self._workspace._path))
        deps = ExecuteDeps(llm=self._llm, workspace=self._workspace)
        self._state = state

        log.info("ExecuteEngine.run: starting supervisor loop")

        async with self._graph.iter(ReadStateNode(), state=state, deps=deps) as run:
            async for node in run:
                node_name = type(node).__name__
                self._state = state
                self._notify_progress("progress", {
                    "node": node_name,
                    **state.to_typed_dict(),
                })

        self._state = state
        self._notify_progress("complete", state.to_typed_dict())

        log.info(
            "ExecuteEngine.run: finished — status=%s sprints=%s",
            state.system_status,
            state.current_sprint,
        )

        return state.to_typed_dict()

    async def pause(self) -> None:
        """Signal the engine to pause at the next safe point."""
        if self._state:
            self._state.system_status = "paused"
            log.info("ExecuteEngine.pause: paused")

    async def resume(self) -> ExecuteStateV2 | None:
        """Resume from a previously paused state."""
        if not self._state:
            log.warning("ExecuteEngine.resume: no saved state")
            return None

        self._state.system_status = "running"
        deps = ExecuteDeps(llm=self._llm, workspace=self._workspace)
        state = self._state

        log.info("ExecuteEngine.resume: resuming from sprint %s", state.current_sprint)

        # Resume from PlanSprintNode (safe re-entry point)
        async with self._graph.iter(PlanSprintNode(), state=state, deps=deps) as run:
            async for node in run:
                node_name = type(node).__name__
                self._state = state
                self._notify_progress("progress", {
                    "node": node_name,
                    **state.to_typed_dict(),
                })

        self._state = state
        self._notify_progress("complete", state.to_typed_dict())
        return state.to_typed_dict()

    def get_status(self) -> dict[str, Any]:
        """Return the current engine status."""
        if not self._state:
            return {"system_status": "idle"}
        return {
            "system_status": self._state.system_status,
            "phase_status": self._state.phase_status,
            "current_phase": self._state.current_phase,
            "total_phases": self._state.total_phases,
            "current_sprint": self._state.current_sprint,
            "total_iterations": self._state.total_iterations,
            "cost_usd": self._state.cost_usd,
        }

    def get_diff(self) -> list[dict[str, Any]]:
        """Return file diffs since the first sprint tag."""
        try:
            return self._workspace.get_diff_since("sprint-1")
        except Exception:  # noqa: BLE001
            return []

    def get_file_tree(self) -> list[str]:
        """Return the list of files in the workspace."""
        return self._workspace.list_files()

    def on_progress(self, callback: Callable[..., Any]) -> None:
        """Register a progress callback."""
        self._progress_callbacks.append(callback)

    def _notify_progress(self, event: str, data: Any = None) -> None:
        for cb in self._progress_callbacks:
            try:
                cb(event, data)
            except Exception:  # noqa: BLE001
                log.warning("Progress callback failed for event=%s", event)
