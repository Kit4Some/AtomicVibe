"""Job ↔ ExecuteEngine registry with async queue for WebSocket streaming."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from architect.config import settings
from architect.execute import ExecuteEngine
from architect.llm import LLMRouter
from architect.ui.schemas import ProgressMessage

__all__ = ["EngineManager"]

log = logging.getLogger(__name__)


@dataclass
class _JobContext:
    engine: ExecuteEngine
    queue: asyncio.Queue[ProgressMessage]
    task: asyncio.Task[Any] | None = None
    status: str = "starting"
    workspace_path: str = ""
    error: str = ""


NODE_LABELS: dict[str, str] = {
    "read_state": "Workspace initialized",
    "plan_sprint": "Sprint planned",
    "assess_risk": "Risk assessment complete",
    "assign_tasks": "Tasks assigned",
    "dispatch_agents": "Agents dispatched",
    "review_code": "Code review complete",
    "revise_code": "Code revision complete",
    "validate": "Validation complete",
    "diagnose": "Error diagnosis complete",
    "strategize": "Strategy decided",
    "apply_fix": "Fix applied",
    "apply_strategy": "Strategy applied",
    "update_state": "Sprint tasks committed",
    "retrospective": "Phase retrospective complete",
    "adjust_plan": "Plan adjusted",
    "check_budget": "Budget checked",
    "request_user": "Waiting for user input",
}


def _state_to_progress(event: str, data: dict[str, Any]) -> ProgressMessage:
    """Convert an engine callback event + state dict to a ProgressMessage."""
    node = data.get("node", "unknown") if isinstance(data, dict) else "unknown"
    state = data if isinstance(data, dict) else {}

    phase = state.get("current_phase", 0)
    sprint = state.get("current_sprint", 0)
    task_label = NODE_LABELS.get(node, node)
    system_status = state.get("system_status", "running")

    if event == "complete":
        msg_text = "Execution complete"
        status = "completed"
    else:
        msg_text = task_label
        status = system_status

    return ProgressMessage(
        type=event,
        phase=phase,
        sprint=sprint,
        task=node,
        status=status,
        message=msg_text,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )


class EngineManager:
    """Manages job_id → ExecuteEngine instances with progress queues."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self._llm = llm_router
        self._jobs: dict[str, _JobContext] = {}

    async def start(
        self,
        plan_id: str,
        vibe_files: dict[str, str],
        workspace_path: str = "",
    ) -> str:
        """Create an engine, register progress callback, launch background run."""
        wp = workspace_path or str(settings.workspace_path)
        job_id = str(uuid.uuid4())

        engine = ExecuteEngine(self._llm, wp)
        queue: asyncio.Queue[ProgressMessage] = asyncio.Queue(maxsize=1000)
        ctx = _JobContext(
            engine=engine,
            queue=queue,
            status="running",
            workspace_path=wp,
        )
        self._jobs[job_id] = ctx

        # Bridge sync callback → async queue
        loop = asyncio.get_running_loop()

        def _on_progress(event: str, data: Any) -> None:
            try:
                msg = _state_to_progress(event, data)
                loop.call_soon_threadsafe(queue.put_nowait, msg)
            except asyncio.QueueFull:
                log.warning("Progress queue full for job %s, dropping message", job_id)
            except Exception:  # noqa: BLE001
                log.warning("Progress callback error for job %s", job_id, exc_info=True)

        engine.on_progress(_on_progress)

        # Load vibe_files from workspace if not provided
        if not vibe_files:
            vibe_files = _load_vibe_files(wp)

        # Launch engine.run() as background task
        async def _run_engine() -> None:
            try:
                await engine.run(vibe_files)
                ctx.status = "completed"
            except Exception as exc:  # noqa: BLE001
                log.exception("Engine run failed for job %s", job_id)
                ctx.status = "error"
                ctx.error = str(exc)
                # Send error event to queue
                err_msg = ProgressMessage(
                    type="error",
                    phase=0,
                    sprint=0,
                    task="engine",
                    status="error",
                    message=f"Engine error: {exc}",
                    timestamp=datetime.now(tz=timezone.utc).isoformat(),
                )
                try:
                    queue.put_nowait(err_msg)
                except asyncio.QueueFull:
                    pass

        ctx.task = asyncio.create_task(_run_engine())
        log.info("EngineManager.start: job=%s workspace=%s", job_id, wp)
        return job_id

    async def stop(self, job_id: str) -> None:
        """Pause the engine and cancel the background task."""
        ctx = self._jobs.get(job_id)
        if not ctx:
            return
        await ctx.engine.pause()
        if ctx.task and not ctx.task.done():
            ctx.task.cancel()
        ctx.status = "stopped"
        log.info("EngineManager.stop: job=%s", job_id)

    def get_engine(self, job_id: str) -> ExecuteEngine | None:
        ctx = self._jobs.get(job_id)
        return ctx.engine if ctx else None

    def get_queue(self, job_id: str) -> asyncio.Queue[ProgressMessage] | None:
        ctx = self._jobs.get(job_id)
        return ctx.queue if ctx else None

    def get_status(self, job_id: str) -> dict[str, Any]:
        ctx = self._jobs.get(job_id)
        if not ctx:
            return {"system_status": "not_found"}
        engine_status = ctx.engine.get_status()
        return {
            **engine_status,
            "job_status": ctx.status,
            "error": ctx.error,
        }

    def get_workspace_path(self, job_id: str) -> str | None:
        ctx = self._jobs.get(job_id)
        return ctx.workspace_path if ctx else None


def _load_vibe_files(workspace_path: str) -> dict[str, str]:
    """Load .vibe/ files from the workspace directory."""
    vibe_dir = os.path.join(workspace_path, ".vibe")
    vibe_files: dict[str, str] = {}
    if not os.path.isdir(vibe_dir):
        return vibe_files
    for name in os.listdir(vibe_dir):
        fpath = os.path.join(vibe_dir, name)
        if os.path.isfile(fpath) and name.endswith(".md"):
            try:
                with open(fpath, encoding="utf-8") as f:
                    vibe_files[name] = f.read()
            except Exception:  # noqa: BLE001
                pass
    return vibe_files
