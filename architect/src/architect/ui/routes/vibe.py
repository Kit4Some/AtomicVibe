"""Vibe file CRUD REST API routes — manage .vibe/ markdown files during plan phase."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request

from architect.core.exceptions import UIError
from architect.ui.plan_session_manager import PlanSessionManager
from architect.ui.schemas import (
    VibeFile,
    VibeFileListResponse,
    VibeFileSaveRequest,
)

router = APIRouter()

log = logging.getLogger(__name__)


def _get_manager(request: Request) -> PlanSessionManager:
    return request.app.state.plan_session_manager  # type: ignore[no-any-return]


def _get_vibe_dir(manager: PlanSessionManager, plan_id: str) -> str:
    """Resolve the .vibe/ directory for a plan session's workspace."""
    session = manager._get_session(plan_id)
    state = session.state

    # Try workspace_path from state, fallback to config default
    workspace_path = state.get("workspace_path", "")
    if not workspace_path:
        from architect.config import settings
        workspace_path = str(settings.workspace_path)

    vibe_dir = os.path.join(workspace_path, ".vibe")
    os.makedirs(vibe_dir, exist_ok=True)
    return vibe_dir


@router.get("/{plan_id}/files", response_model=VibeFileListResponse)
async def list_vibe_files(plan_id: str, request: Request) -> VibeFileListResponse:
    """List all .vibe/ markdown files for a plan session."""
    manager = _get_manager(request)
    session = manager._get_session(plan_id)

    # Collect generated files from state if available
    generated = session.state.get("generated_files", {})

    # Also check workspace .vibe/ directory on disk
    vibe_files: list[VibeFile] = []
    seen: set[str] = set()

    # From in-memory state first
    for name, content in generated.items():
        vibe_files.append(VibeFile(name=name, path=name, content=content))
        seen.add(name)

    # From disk (if workspace exists)
    try:
        workspace_path = session.state.get("workspace_path", "")
        if workspace_path:
            vibe_dir = os.path.join(workspace_path, ".vibe")
            if os.path.isdir(vibe_dir):
                for fname in sorted(os.listdir(vibe_dir)):
                    if fname.endswith(".md") and fname not in seen:
                        fpath = os.path.join(vibe_dir, fname)
                        with open(fpath, "r", encoding="utf-8") as f:
                            content = f.read()
                        vibe_files.append(VibeFile(name=fname, path=fname, content=content))
    except Exception:  # noqa: BLE001
        log.warning("list_vibe_files: failed to read .vibe/ from disk")

    return VibeFileListResponse(files=vibe_files)


@router.get("/{plan_id}/files/{path:path}", response_model=VibeFile)
async def get_vibe_file(plan_id: str, path: str, request: Request) -> VibeFile:
    """Get a single vibe file's content."""
    manager = _get_manager(request)
    session = manager._get_session(plan_id)

    # Check in-memory state
    generated = session.state.get("generated_files", {})
    if path in generated:
        return VibeFile(name=path, path=path, content=generated[path])

    # Check disk
    workspace_path = session.state.get("workspace_path", "")
    if workspace_path:
        fpath = os.path.join(workspace_path, ".vibe", path)
        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            return VibeFile(name=path, path=path, content=content)

    raise UIError(message="Vibe file not found", detail=path, status_code=404)


@router.put("/{plan_id}/files/{path:path}")
async def save_vibe_file(
    plan_id: str, path: str, body: VibeFileSaveRequest, request: Request,
) -> dict[str, str]:
    """Create or update a vibe file."""
    manager = _get_manager(request)
    session = manager._get_session(plan_id)

    # Update in-memory state
    generated = dict(session.state.get("generated_files", {}))
    generated[path] = body.content
    session.state["generated_files"] = generated

    # Write to disk if workspace exists
    workspace_path = session.state.get("workspace_path", "")
    if workspace_path:
        vibe_dir = os.path.join(workspace_path, ".vibe")
        os.makedirs(vibe_dir, exist_ok=True)
        fpath = os.path.join(vibe_dir, path)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(body.content)

    log.info("save_vibe_file: %s updated for plan %s", path, plan_id)
    return {"status": "saved"}


@router.delete("/{plan_id}/files/{path:path}")
async def delete_vibe_file(plan_id: str, path: str, request: Request) -> dict[str, str]:
    """Delete a vibe file."""
    manager = _get_manager(request)
    session = manager._get_session(plan_id)

    # Remove from in-memory state
    generated = dict(session.state.get("generated_files", {}))
    generated.pop(path, None)
    session.state["generated_files"] = generated

    # Remove from disk
    workspace_path = session.state.get("workspace_path", "")
    if workspace_path:
        fpath = os.path.join(workspace_path, ".vibe", path)
        if os.path.isfile(fpath):
            os.remove(fpath)

    log.info("delete_vibe_file: %s removed for plan %s", path, plan_id)
    return {"status": "deleted"}
