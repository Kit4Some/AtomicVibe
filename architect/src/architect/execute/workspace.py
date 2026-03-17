"""Workspace — file I/O and Git operations for the Execute Engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import git

from architect.core.exceptions import WorkspaceError
from architect.core.models import CodeFile

__all__ = ["Workspace"]

log = logging.getLogger("architect.execute.workspace")


class Workspace:
    """Manages the generated-project directory and its Git history.

    Provides file read/write utilities and thin wrappers around GitPython
    so that the Supervisor loop can commit, tag, and rollback atomically.
    """

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        try:
            self._path.mkdir(parents=True, exist_ok=True)
            if (self._path / ".git").is_dir():
                self._repo = git.Repo(str(self._path))
            else:
                self._repo = git.Repo.init(str(self._path))
                # Create initial commit so tags/rollbacks have a base
                readme = self._path / "README.md"
                readme.write_text("# ARCHITECT workspace\n", encoding="utf-8")
                self._repo.index.add(["README.md"])
                self._repo.index.commit("chore: init workspace")
            log.info("Workspace ready at %s", self._path)
        except (git.exc.GitError, OSError) as exc:
            raise WorkspaceError(
                message="Failed to initialise workspace",
                detail=str(exc),
            ) from exc

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def write_files(self, files: list[CodeFile]) -> None:
        """Write a list of :class:`CodeFile` entries to the workspace."""
        for cf in files:
            full = self._path / cf.path
            try:
                full.parent.mkdir(parents=True, exist_ok=True)
                if cf.action == "append" and full.exists():
                    with full.open("a", encoding="utf-8") as fh:
                        fh.write(cf.content)
                else:
                    full.write_text(cf.content, encoding="utf-8")
                log.debug("write_files: %s (%s)", cf.path, cf.action)
            except OSError as exc:
                raise WorkspaceError(
                    message=f"Failed to write {cf.path}",
                    detail=str(exc),
                ) from exc

    def read_file(self, path: str) -> str:
        """Return the contents of a workspace file."""
        full = self._path / path
        if not full.is_file():
            raise WorkspaceError(message=f"File not found: {path}")
        try:
            return full.read_text(encoding="utf-8")
        except OSError as exc:
            raise WorkspaceError(
                message=f"Failed to read {path}",
                detail=str(exc),
            ) from exc

    def list_files(self, directory: str = ".") -> list[str]:
        """List all files under *directory* (relative paths)."""
        base = self._path / directory
        if not base.is_dir():
            return []
        return sorted(
            str(p.relative_to(self._path))
            for p in base.rglob("*")
            if p.is_file() and ".git" not in p.parts
        )

    def update_vibe_file(self, filename: str, content: str) -> None:
        """Write or overwrite a file inside the ``.vibe/`` directory."""
        vibe_dir = self._path / ".vibe"
        vibe_dir.mkdir(parents=True, exist_ok=True)
        target = vibe_dir / filename
        try:
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise WorkspaceError(
                message=f"Failed to update .vibe/{filename}",
                detail=str(exc),
            ) from exc

    # ------------------------------------------------------------------
    # Git operations
    # ------------------------------------------------------------------

    def git_commit(self, message: str) -> None:
        """Stage all changes and create a commit."""
        try:
            self._repo.index.add(".")
            if self._repo.is_dirty() or self._repo.untracked_files:
                self._repo.index.commit(message)
                log.info("git_commit: %s", message)
            else:
                log.debug("git_commit: nothing to commit")
        except git.exc.GitError as exc:
            raise WorkspaceError(
                message="Git commit failed",
                detail=str(exc),
            ) from exc

    def git_tag(self, tag: str) -> None:
        """Create a lightweight Git tag at HEAD."""
        try:
            self._repo.create_tag(tag)
            log.info("git_tag: %s", tag)
        except git.exc.GitError as exc:
            raise WorkspaceError(
                message=f"Git tag failed: {tag}",
                detail=str(exc),
            ) from exc

    def git_rollback(self, tag: str) -> None:
        """Restore the working tree to the state at *tag*."""
        try:
            self._repo.git.checkout(tag, "--", ".")
            log.info("git_rollback: restored to %s", tag)
        except git.exc.GitError as exc:
            raise WorkspaceError(
                message=f"Git rollback to {tag} failed",
                detail=str(exc),
            ) from exc

    def get_diff_since(self, tag: str) -> list[dict[str, Any]]:
        """Return a list of changed files since *tag*.

        Each entry: ``{"path": str, "status": str, "diff": str}``.
        """
        try:
            diffs: list[dict[str, Any]] = []
            for diff_item in self._repo.commit(tag).diff(None):
                diffs.append({
                    "path": diff_item.b_path or diff_item.a_path,
                    "status": diff_item.change_type,
                    "diff": diff_item.diff.decode("utf-8", errors="replace")
                    if diff_item.diff
                    else "",
                })
            return diffs
        except git.exc.GitError as exc:
            raise WorkspaceError(
                message=f"Git diff since {tag} failed",
                detail=str(exc),
            ) from exc
