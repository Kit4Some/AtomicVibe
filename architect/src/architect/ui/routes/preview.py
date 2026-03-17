"""Preview API routes — real workspace file tree, content, test results."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request

from architect.core.exceptions import UIError
from architect.ui.engine_manager import EngineManager
from architect.ui.schemas import (
    FileContentResponse,
    FileTreeNode,
    TestResult,
    TestResultResponse,
)

router = APIRouter()

_EXT_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".sh": "shell",
    ".txt": "plaintext",
}


def _build_tree(root: str) -> FileTreeNode:
    """Recursively build a FileTreeNode from a filesystem directory."""
    root_path = Path(root)
    name = root_path.name

    children: list[FileTreeNode] = []
    try:
        entries = sorted(root_path.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        entries = []

    for entry in entries:
        # Skip hidden dirs/files and __pycache__
        if entry.name.startswith(".") or entry.name == "__pycache__":
            continue
        rel = str(entry.relative_to(root_path.parent)).replace("\\", "/")
        if entry.is_dir():
            children.append(_build_tree(str(entry)))
        else:
            children.append(FileTreeNode(name=entry.name, type="file", path=rel))

    return FileTreeNode(
        name=name,
        type="directory",
        path=str(root_path.relative_to(root_path.parent)).replace("\\", "/"),
        children=children if children else None,
    )


def _detect_language(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _EXT_LANGUAGE.get(ext, "plaintext")


def _get_workspace(job_id: str, request: Request) -> str:
    manager: EngineManager = request.app.state.engine_manager
    workspace = manager.get_workspace_path(job_id)
    if not workspace:
        raise UIError(message="Job not found", detail=job_id, status_code=404)
    return workspace


@router.get("/{job_id}/tree", response_model=FileTreeNode)
async def get_file_tree(job_id: str, request: Request) -> FileTreeNode:
    """Get the file tree for a job's generated output."""
    workspace = _get_workspace(job_id, request)
    if not os.path.isdir(workspace):
        raise UIError(message="Workspace not found", detail=workspace, status_code=404)
    return _build_tree(workspace)


@router.get("/{job_id}/file", response_model=FileContentResponse)
async def get_file_content(job_id: str, path: str, request: Request) -> FileContentResponse:
    """Get content of a specific file with language detection."""
    workspace = _get_workspace(job_id, request)
    full_path = os.path.normpath(os.path.join(workspace, path))

    # Prevent path traversal
    if not full_path.startswith(os.path.normpath(workspace)):
        raise UIError(message="Invalid path", detail=path, status_code=400)

    if not os.path.isfile(full_path):
        raise UIError(message="File not found", detail=path, status_code=404)

    try:
        with open(full_path, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        content = f"[Binary file: {path}]"

    return FileContentResponse(content=content, language=_detect_language(path))


@router.get("/{job_id}/tests", response_model=TestResultResponse)
async def get_test_results(job_id: str, request: Request) -> TestResultResponse:
    """Get test results for a job."""
    manager: EngineManager = request.app.state.engine_manager
    engine = manager.get_engine(job_id)

    if not engine:
        raise UIError(message="Job not found", detail=job_id, status_code=404)

    status = engine.get_status()
    validation_results = status.get("validation_results", [])

    results: list[TestResult] = []
    for vr in validation_results:
        name = vr.get("step", "unknown") if isinstance(vr, dict) else str(vr)
        passed = vr.get("passed", False) if isinstance(vr, dict) else False
        output = vr.get("message", "") if isinstance(vr, dict) else ""
        results.append(TestResult(name=name, passed=passed, output=output))

    passed_count = sum(1 for r in results if r.passed)
    return TestResultResponse(
        total=len(results),
        passed=passed_count,
        failed=len(results) - passed_count,
        results=results,
    )
