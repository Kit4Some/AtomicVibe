"""Execute mode REST API routes — real ExecuteEngine integration."""

from __future__ import annotations

from fastapi import APIRouter, Request

from architect.core.exceptions import UIError
from architect.ui.engine_manager import EngineManager
from architect.ui.schemas import (
    ExecuteStartRequest,
    ExecuteStartResponse,
    ExecuteStatusResponse,
    ExecuteStopResponse,
)

router = APIRouter()


def _get_manager(request: Request) -> EngineManager:
    return request.app.state.engine_manager  # type: ignore[no-any-return]


@router.post("/start", status_code=201, response_model=ExecuteStartResponse)
async def start_execution(body: ExecuteStartRequest, request: Request) -> ExecuteStartResponse:
    """Start execution for an approved plan."""
    manager = _get_manager(request)
    job_id = await manager.start(
        plan_id=body.plan_id,
        vibe_files=body.vibe_files or {},
        workspace_path=body.workspace_path,
    )
    return ExecuteStartResponse(job_id=job_id)


@router.post("/{job_id}/stop", response_model=ExecuteStopResponse)
async def stop_execution(job_id: str, request: Request) -> ExecuteStopResponse:
    """Stop a running execution."""
    manager = _get_manager(request)
    await manager.stop(job_id)
    return ExecuteStopResponse(status="stopped")


@router.get("/{job_id}/status", response_model=ExecuteStatusResponse)
async def get_execution_status(job_id: str, request: Request) -> ExecuteStatusResponse:
    """Get current execution status."""
    manager = _get_manager(request)
    status = manager.get_status(job_id)

    if status.get("system_status") == "not_found":
        raise UIError(message="Job not found", detail=job_id, status_code=404)

    max_iters = status.get("max_total_iterations", 30) or 30
    total_iters = status.get("total_iterations", 0)
    progress = min(total_iters / max_iters, 1.0) if max_iters > 0 else 0.0

    return ExecuteStatusResponse(
        phase=status.get("current_phase", 0),
        sprint=status.get("current_sprint", 0),
        progress=progress,
        cost=status.get("cost_usd", 0.0),
        system_status=status.get("system_status", "idle"),
        phase_status=status.get("phase_status", "idle"),
        total_phases=status.get("total_phases", 4),
        total_iterations=total_iters,
    )
