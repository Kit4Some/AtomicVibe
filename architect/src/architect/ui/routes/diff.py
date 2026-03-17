"""Diff API routes — real ExecuteEngine integration."""

from __future__ import annotations

from fastapi import APIRouter, Request

from architect.core.exceptions import UIError
from architect.ui.engine_manager import EngineManager
from architect.ui.schemas import DiffFile, DiffResponse

router = APIRouter()

_STATUS_MAP = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "modified",  # renamed → treat as modified
}


@router.get("/{job_id}", response_model=DiffResponse)
async def get_diff(job_id: str, request: Request) -> DiffResponse:
    """Get diff of generated/changed files for a job."""
    manager: EngineManager = request.app.state.engine_manager
    engine = manager.get_engine(job_id)

    if not engine:
        raise UIError(message="Job not found", detail=job_id, status_code=404)

    raw_diffs = engine.get_diff()

    files: list[DiffFile] = []
    for entry in raw_diffs:
        git_status = entry.get("status", "M")
        status = _STATUS_MAP.get(git_status, "modified")
        diff_text = entry.get("diff", "")

        # For added files: old is empty, new is the diff content
        # For deleted files: new is empty, old is the diff content
        # For modified: show unified diff in both fields for the DiffViewer
        if status == "added":
            old_content = ""
            new_content = diff_text
        elif status == "deleted":
            old_content = diff_text
            new_content = ""
        else:
            # Split unified diff into old/new for display
            old_lines: list[str] = []
            new_lines: list[str] = []
            for line in diff_text.splitlines():
                if line.startswith("-") and not line.startswith("---"):
                    old_lines.append(line[1:])
                elif line.startswith("+") and not line.startswith("+++"):
                    new_lines.append(line[1:])
                elif not line.startswith("@@"):
                    old_lines.append(line)
                    new_lines.append(line)
            old_content = "\n".join(old_lines)
            new_content = "\n".join(new_lines)

        files.append(DiffFile(
            path=entry.get("path", ""),
            old_content=old_content,
            new_content=new_content,
            status=status,
        ))

    return DiffResponse(files=files)
